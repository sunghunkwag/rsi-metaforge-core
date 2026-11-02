"""The kernel runtime: every kernel object wired over a run directory, and the run's artifacts.

The loop (``swarm/loop.py``) drives the kernel through this object and
never names the vault: it certifies through ``admission``, checks
crossings through ``crossings``, judges self-edits through ``judge``,
calls into the Builder's live tree through ``live_call`` and into
snapshots through ``snapshots``, hands the agents the metered runners
built here, and asks for ``public_view``, ``ledger_view`` and
``checkpoint``. Three executors share one meter, the kernel's own and one
each for the Breaker's and the Builder's program runs, so every
interpreter step is attributed to the agent that spent it. A live call
that fails (crash, timeout, unreadable output) is ledgered with the
child's error so the failure is a fact of the run, not a silent zero.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .admit import CERTIFICATES, Admission
from .archive import Archive
from .budget import Meter
from .crossing import Crossings
from .edits import EditJudge
from .executor import Executor
from .ledger import Ledger
from .snapshot import SnapshotStore, solve_timeout
from .vault import Vault


class KernelRuntime:
    def __init__(self, run_dir: Path, b_inst: int, probe_seed: int, horizon: int,
                 executor_timeout_s: float = 2.0, executor_mem_mb: int = 512, regression_sample: int = 6):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.b_inst, self.probe_seed = int(b_inst), int(probe_seed)
        self.executor_timeout_s, self.executor_mem_mb = float(executor_timeout_s), int(executor_mem_mb)
        self.meter = Meter()
        args = dict(timeout_s=self.executor_timeout_s, memory_mb=self.executor_mem_mb, meter=self.meter)
        self.executor = Executor(agent="kernel", **args)
        self.breaker_executor = Executor(agent="breaker", **args)
        self.builder_executor = Executor(agent="builder", **args)
        self.ledger = Ledger()
        self.vault = Vault()
        self.archive = Archive(horizon=int(horizon))
        self.snapshots = SnapshotStore(self.dir / "snapshots", self.executor, self.meter)
        self.admission = Admission(self.executor, self.vault, self.archive, self.snapshots, self.ledger,
                                   self.meter, b_inst=self.b_inst, probe_seed=self.probe_seed)
        self.crossings = Crossings(self.executor, self.vault, self.archive, self.snapshots, self.ledger,
                                   b_inst=self.b_inst)
        self.judge = EditJudge(self.executor, self.vault, self.archive, self.snapshots, self.ledger,
                               b_inst=self.b_inst, sample=int(regression_sample))

    # ---- what the agents are handed ------------------------------------------------
    def breaker_runner(self, program, inputs):
        """Outputs of ``program`` on ``inputs``, or None when any run fails; charged to the Breaker."""
        out = self.breaker_executor.run_batch(program, [[x] for x in inputs], module="breaker")
        return None if any(not r["ok"] for r in out) else [r["value"] for r in out]

    def builder_runner(self, programs, inputs):
        """Per program, its outputs on ``inputs`` or None; charged to the Builder (the forge).

        Every program checked here against a task's public inputs is one
        candidate evaluation by the meter's definition, charged as such
        under ``builder/forge``: the forge spends the Builder's budget.
        """
        out = self.builder_executor.run_items([(p, [x]) for p in programs for x in inputs], module="forge")
        self.meter.charge("builder", "forge", evaluations=len(programs))
        results = []
        for index in range(len(programs)):
            chunk = out[index * len(inputs):(index + 1) * len(inputs)]
            results.append(None if any(not r["ok"] for r in chunk) else [r["value"] for r in chunk])
        return results

    def live_call(self, tree_dir: Path, function: str, payload: dict):
        """A metered isolated call into the Builder's live tree; failures are ledgered."""
        budget = payload.get("budget", 0) if function == "solve_many" else 0
        total = sum(budget.values()) if isinstance(budget, dict) else int(budget)
        result = self.snapshots.call_tree(tree_dir, function, payload, agent="builder",
                                          timeout=solve_timeout(total))
        if result is None:
            self.ledger.append("live_call_failed", {"generation": self.meter.generation, "function": function,
                                                    "error": self.executor.last_error})
        return result

    # ---- views ----------------------------------------------------------------------------
    def public_view(self) -> list:
        return self.archive.public_view()

    def ledger_view(self) -> dict:
        """Public outcomes: rejections per certificate, crossings, self-edits adopted."""
        rejections = {c: 0 for c in CERTIFICATES}
        for entry in self.ledger.of_kind("rejection"):
            certificate = entry["payload"]["certificate"]
            rejections[certificate] = rejections.get(certificate, 0) + 1
        return {"rejections": rejections, "crossings": len(self.ledger.of_kind("crossing")),
                "self_edits_adopted": sum(e["payload"]["adopted"] for e in self.ledger.of_kind("self_edit")),
                "live_calls_failed": len(self.ledger.of_kind("live_call_failed")),
                "kernel_failed": len(self.ledger.of_kind("kernel_failed")),
                "crossing_checks_failed": len(self.ledger.of_kind("crossing_check_failed"))}

    @staticmethod
    def field_nonce(seed: int) -> int:
        """The seed of the field's secret permutation (arm S5): derived here, never handed to an agent."""
        return int(hashlib.sha256(f"swarm-field-permutation|{int(seed)}".encode("utf-8")).hexdigest()[:15], 16)

    def timeouts(self) -> dict:
        return {name: {"timeouts": e.timeouts, "failures": e.failures}
                for name, e in (("kernel", self.executor), ("breaker", self.breaker_executor),
                                ("builder", self.builder_executor))}

    # ---- artifacts --------------------------------------------------------------------
    @staticmethod
    def write_atomic(path: Path, text: str, mode: int | None = None) -> None:
        """Write ``text`` to ``path`` through a temporary file renamed into place."""
        path = Path(path)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)

    def checkpoint(self) -> None:
        """Write the ledger, the kernel-only vault dump, the archive and the replay configuration.

        Every artifact is written atomically; the vault dump is owner-readable
        only and, like every file of the run directory, outside what the
        executor's guard lets a Builder tree read.
        """
        self.ledger.write(self.dir / "ledger.jsonl")
        self.write_atomic(self.dir / "vault.json", json.dumps(self.vault.dump()), mode=0o600)
        self.write_atomic(self.dir / "archive.json", json.dumps(self.archive.dump(), default=str))
        self.write_atomic(self.dir / "run_config.json", json.dumps(
            {"B_inst": self.b_inst, "probe_set_seed": self.probe_seed,
             "executor_timeout_s": self.executor_timeout_s, "executor_mem_mb": self.executor_mem_mb},
            indent=1))
