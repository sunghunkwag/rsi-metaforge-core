"""The frozen executor: runs checker-language programs in an isolated subprocess.

Every program the kernel judges (witnesses for Ka and Kd, checkers, the
Builder's compiled solutions for Kb and crossings) runs here: a child
``python -I`` process with a memory cap and a wall-clock timeout, fed one
JSON job on stdin, answering one JSON result on stdout. Items are batched
per call to amortize process start-up; a timeout fails the whole batch,
which the kernel treats as a crash of every item in it. Interpreter steps
reported by the child are charged to the meter by the caller.

``isolated_call`` is the same mechanism for running a Builder snapshot's
entry point (``snapshot.py``): the child's ``sys.path`` holds the snapshot
directory and the repository root only, so the snapshot's own modules are
the ones that run.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from . import checker_lang

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_S = 2.0
MEMORY_MB = 512
BATCH = 64

_RUNNER = r"""
import json, resource, sys
root, mem = sys.argv[1], int(sys.argv[2])
sys.path.insert(0, root)
try:
    resource.setrlimit(resource.RLIMIT_AS, (mem << 20, mem << 20))
except (ValueError, OSError):
    pass
from swarm.kernel import checker_lang as cl
job = json.load(sys.stdin)
out = []
for item in job["items"]:
    args = [cl.from_jsonable(a) for a in item["args"]]
    r = cl.run(item["program"], args, job["step_budget"])
    out.append({"ok": r.ok, "value": cl.to_jsonable(r.value) if r.ok else None,
                "error": r.error, "steps": r.steps})
sys.stdout.write(json.dumps(out))
"""


class Executor:
    def __init__(self, timeout_s: float = TIMEOUT_S, memory_mb: int = MEMORY_MB,
                 step_budget: int = checker_lang.MAX_STEPS, meter=None, agent: str = "kernel"):
        self.timeout_s = float(timeout_s)
        self.memory_mb = int(memory_mb)
        self.step_budget = int(step_budget)
        self.meter = meter
        self.agent = agent
        self.calls = 0
        self.timeouts = 0
        self.failures = 0
        self.last_error = None          # tail of the child's stderr on its last failure

    def _child(self, code: str, argv: list, payload: dict, timeout: float) -> list:
        self.calls += 1
        try:
            completed = subprocess.run([sys.executable, "-I", "-c", code, *argv],
                                       input=json.dumps(payload), capture_output=True,
                                       text=True, timeout=timeout, cwd=str(ROOT))
        except subprocess.TimeoutExpired:
            self.timeouts += 1
            self.last_error = f"timeout after {timeout:.0f}s"
            return None
        if completed.returncode != 0:
            self.failures += 1
            self.last_error = f"exit {completed.returncode}: {completed.stderr[-1500:]}"
            return None
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError:
            self.failures += 1
            self.last_error = f"unreadable output: {completed.stdout[-300:]!r}"
            return None

    def run_batch(self, program, inputs: list, module: str = "executor") -> list:
        """Run ``program`` on each input list; returns one dict per input."""
        return self.run_items([(program, args) for args in inputs], module)

    def run_items(self, items: list, module: str = "executor") -> list:
        """Run ``(program, args)`` pairs, batched per child; returns one dict per item."""
        results = []
        for start in range(0, len(items), BATCH):
            chunk = items[start:start + BATCH]
            payload = {"step_budget": self.step_budget,
                       "items": [{"program": program, "args": [checker_lang.to_jsonable(a) for a in args]}
                                 for program, args in chunk]}
            timeout = self.timeout_s * (1 + len(chunk) / 16)
            out = self._child(_RUNNER, [str(ROOT), str(self.memory_mb)], payload, timeout)
            if out is None:
                out = [{"ok": False, "value": None, "error": "timeout_or_crash",
                        "steps": self.step_budget} for _ in chunk]
            for item in out:
                item["value"] = checker_lang.from_jsonable(item["value"]) if item["ok"] else None
            results.extend(out)
        if self.meter is not None:
            self.meter.charge(self.agent, module, steps=sum(r["steps"] for r in results))
        return results

    def run(self, program, args: list, module: str = "executor") -> dict:
        return self.run_batch(program, [args], module)[0]

    def check_batch(self, checker, pairs: list, module: str = "executor") -> list:
        """Checker verdicts on (x, y) pairs: True, False, or None when the checker failed."""
        results = self.run_batch(checker, [[x, y] for x, y in pairs], module)
        verdicts = []
        for item in results:
            if item["ok"] and type(item["value"]) is bool:
                verdicts.append(item["value"])
            else:
                verdicts.append(None)
        return verdicts

    def isolated_call(self, path_entries: list, module: str, function: str, payload: dict,
                      timeout: float) -> dict | None:
        """Import ``module`` with ``sys.path`` = path_entries and call ``function(payload)``."""
        code = r"""
import json, resource, sys, importlib
entries = json.loads(sys.argv[1]); mem = int(sys.argv[2])
sys.path[:0] = entries
try:
    resource.setrlimit(resource.RLIMIT_AS, (mem << 20, mem << 20))
except (ValueError, OSError):
    pass
module = importlib.import_module(sys.argv[3])
payload = json.load(sys.stdin)
sys.stdout.write(json.dumps(getattr(module, sys.argv[4])(payload)))
"""
        return self._child(code, [json.dumps([str(p) for p in path_entries]), str(self.memory_mb),
                                  module, function], payload, timeout)
