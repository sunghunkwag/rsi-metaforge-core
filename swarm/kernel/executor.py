"""The frozen executor: runs checker-language programs in an isolated subprocess.

Every program the kernel judges (witnesses for Ka and Kd, checkers, the
Builder's compiled solutions for Kb and crossings) runs here: a child
Python process with a memory cap, a wall-clock timeout and a filesystem
guard, fed one JSON job on stdin, answering one JSON result on stdout.
Items are batched per call to amortize process start-up; a timeout fails
the whole batch, which the kernel treats as a crash of every item in it
(charged nothing: a wall-clock event fabricates no logical cost).
Interpreter steps reported by the child are charged to the meter by the
caller.

``isolated_call`` is the same mechanism for running a Builder tree's
entry point (``snapshot.py``): the child's ``sys.path`` holds the tree's
directory and the repository root (for the kernel's checker language,
which the tree's pinned evaluator imports), and the guard confines the
child. The guard is an audit hook installed before anything else is
imported: the child may read its own tree, the kernel package
(``swarm/kernel``) and the Python installation; it may write only inside
its own tree; it may import no other ``swarm`` module; and it may not
spawn processes, open sockets or load native libraries. The run directory
(vault dump, archive, ledger, the other trees) is therefore unreadable
from any Builder code, which is the directive's filesystem path guard
(§9). Children run with ``-s -P -B`` and a fixed environment carrying
``PYTHONHASHSEED=0``, so string hashing is the same in every child.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from . import checker_lang

ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_S = 2.0
MEMORY_MB = 512
BATCH = 64
KERNEL_READS = [str(ROOT / "swarm" / "__init__.py"), str(ROOT / "swarm" / "__pycache__"),
                str(ROOT / "swarm" / "kernel"),
                str(ROOT / "swarm" / "builder" / "mutable" / "evaluator.py")]
ALLOWED_SWARM = ["swarm", "swarm.kernel", "swarm.kernel.hashes", "swarm.kernel.checker_lang"]
DENIED_MODULES = ["subprocess", "socket", "ctypes", "multiprocessing", "asyncio", "http", "urllib",
                  "ftplib", "smtplib", "telnetlib", "xmlrpc", "pty", "signal", "webbrowser",
                  "swarm.breaker", "swarm.builder", "swarm.loop", "swarm.experiment", "swarm.report",
                  "swarm.mapper", "swarm.latent", "swarm.tests"]

_GUARD = r"""
import os, sys
def _install_guard(spec):
    import os, sys
    read_roots = [os.path.realpath(p) for p in spec["read"]]
    write_roots = [os.path.realpath(p) for p in spec["write"]]
    listable = {os.path.realpath(p) for p in spec["list"]}      # import machinery lists sys.path entries
    prefixes = [os.path.realpath(p) for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix}]
    denied = tuple(spec["denied_modules"])
    allowed_swarm = set(spec["allowed_swarm"])
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
    def within(path, roots):
        if isinstance(path, bytes):
            path = os.fsdecode(path)
        if not isinstance(path, str):
            return False
        real = os.path.realpath(path)
        return any(real == r or real.startswith(r + os.sep) for r in roots)
    def deny(what):
        raise RuntimeError("guard: " + what)
    def hook(event, args):
        if event == "import":
            name = args[0]
            if any(name == d or name.startswith(d + ".") for d in denied):
                deny("import of " + name)
            if (name == "swarm" or name.startswith("swarm.")) and name not in allowed_swarm:
                deny("import of " + name)
        elif event == "open":
            path, mode, flags = args[0], args[1], args[2]
            if isinstance(path, int) or path in ("/dev/null", b"/dev/null"):
                return
            writing = (any(c in mode for c in "wax+") if isinstance(mode, str)
                       else bool((flags or 0) & write_flags))
            if writing:
                if not within(path, write_roots):
                    deny("write to " + str(path))
            elif not (within(path, read_roots) or within(path, prefixes)):
                deny("read of " + str(path))
        elif event == "io.open_code":
            if not (within(args[0], read_roots) or within(args[0], prefixes)):
                deny("code read of " + str(args[0]))
        elif event in ("os.listdir", "os.scandir", "glob.glob"):
            path = args[0] if args and args[0] is not None else "."
            if isinstance(path, int):
                return
            if isinstance(path, bytes):
                path = os.fsdecode(path)
            if not (within(path, read_roots) or within(path, prefixes)
                    or (isinstance(path, str) and os.path.realpath(path) in listable)):
                deny(event + " of " + str(path))
        elif event in ("os.remove", "os.unlink", "os.rename", "os.replace", "os.rmdir", "os.mkdir",
                       "os.truncate", "os.chmod", "os.chown", "os.link", "os.symlink", "shutil.rmtree",
                       "shutil.copyfile", "shutil.copymode", "shutil.move", "shutil.copytree",
                       "os.utime", "tempfile.mkstemp", "tempfile.mkdtemp"):
            for p in args[:2]:
                if isinstance(p, (str, bytes)) and not within(p, write_roots):
                    deny(event + " outside the tree: " + str(p))
        elif event.startswith(("subprocess.", "os.system", "os.exec", "os.fork", "os.posix_spawn",
                               "os.spawn", "socket.", "ctypes.", "os.kill", "os.killpg", "pty.",
                               "webbrowser.", "os.putenv", "os.unsetenv", "os.add_dll_directory")):
            deny(event)
    sys.addaudithook(hook)
"""

_RUNNER = _GUARD + r"""
import json, resource, sys
root, mem, spec = sys.argv[1], int(sys.argv[2]), json.loads(sys.argv[3])
_install_guard(spec)
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

_ISOLATED = _GUARD + r"""
import json, resource, sys, importlib
entries, mem, spec = json.loads(sys.argv[1]), int(sys.argv[2]), json.loads(sys.argv[3])
_install_guard(spec)
sys.path[:0] = entries
try:
    resource.setrlimit(resource.RLIMIT_AS, (mem << 20, mem << 20))
except (ValueError, OSError):
    pass
module = importlib.import_module(sys.argv[4])
payload = json.load(sys.stdin)
sys.stdout.write(json.dumps(getattr(module, sys.argv[5])(payload)))
"""


def child_environment() -> dict:
    """The fixed environment of every child: a seeded hash, one thread, nothing inherited."""
    return {"PYTHONHASHSEED": "0", "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def guard_spec(read: list = (), write: list = (), entries: list = ()) -> dict:
    """What a child may read, write and list: its tree, the kernel package, the import directories."""
    return {"read": [str(p) for p in read] + KERNEL_READS, "write": [str(p) for p in write],
            "list": [str(p) for p in entries] + [str(ROOT), str(ROOT / "swarm")],
            "denied_modules": DENIED_MODULES, "allowed_swarm": ALLOWED_SWARM}


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
            completed = subprocess.run([sys.executable, "-s", "-P", "-B", "-c", code, *argv],
                                       input=json.dumps(payload), capture_output=True,
                                       text=True, timeout=timeout, cwd=str(ROOT), env=child_environment())
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
        """Run ``(program, args)`` pairs, batched per child; returns one dict per item.

        A chunk whose child crashed or timed out yields ``ok: False`` with
        error ``timeout_or_crash`` and zero steps for every item in it.
        """
        results = []
        spec = json.dumps(guard_spec(entries=[ROOT]))
        for start in range(0, len(items), BATCH):
            chunk = items[start:start + BATCH]
            payload = {"step_budget": self.step_budget,
                       "items": [{"program": program, "args": [checker_lang.to_jsonable(a) for a in args]}
                                 for program, args in chunk]}
            timeout = self.timeout_s * (1 + len(chunk) / 16)
            out = self._child(_RUNNER, [str(ROOT), str(self.memory_mb), spec], payload, timeout)
            if out is None:
                out = [{"ok": False, "value": None, "error": "timeout_or_crash", "steps": 0} for _ in chunk]
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

    def accepts(self, program, inputs: list, checker, module: str = "executor") -> tuple:
        """(accepted, failed): does the checker accept ``program``'s output on every input?

        ``failed`` is True when a child crashed or timed out while running
        the program or the checker; that is not a verdict. A program that
        errors inside the interpreter, or a checker that does, is a
        rejection, not a failure.
        """
        runs = self.run_batch(program, [[x] for x in inputs], module)
        if any(r.get("error") == "timeout_or_crash" for r in runs):
            return False, True
        outputs = [r["value"] if r["ok"] else None for r in runs]
        checks = self.run_batch(checker, [[x, o] for x, o in zip(inputs, outputs)], module)
        if any(c.get("error") == "timeout_or_crash" for c in checks):
            return False, True
        return all(c["ok"] and c["value"] is True for c in checks), False

    def isolated_call(self, path_entries: list, module: str, function: str, payload: dict,
                      timeout: float, read: list = (), write: list = ()) -> dict | None:
        """Import ``module`` with ``sys.path`` = path_entries and call ``function(payload)`` under the guard.

        ``read`` and ``write`` are the directories the child may read and
        write beyond the kernel package and the Python installation; by
        default the first path entry (the tree's parent) for both.
        """
        read = list(read) or [path_entries[0]]
        write = list(write) or [path_entries[0]]
        spec = json.dumps(guard_spec(read, write, entries=list(path_entries)))
        return self._child(_ISOLATED, [json.dumps([str(p) for p in path_entries]), str(self.memory_mb),
                                       spec, module, function], payload, timeout)
