"""The witness vault: write-once, memory-only, readable by the kernel alone (Phase K's K1).

A task's witness (the Breaker's proof that the task is solvable), its
checker and its hidden evaluation instances are sealed here at emission,
before any admission certificate runs. Every accessor name starts with
``sealed_`` and the class is ``Vault``; ``tests/test_integrity.py`` audits
the AST of every module outside ``swarm/kernel`` for those symbols and for
imports of this module. The vault can be dumped at the end of a run into
a kernel-only artifact so that ``replay.py`` can re-derive every
certificate offline; the Builder never runs in a process that holds it.
"""
from __future__ import annotations

import hashlib
import json


class SealedError(RuntimeError):
    pass


def _sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     default=str).encode("utf-8")).hexdigest()


class Vault:
    def __init__(self):
        self._sealed: dict = {}

    def seal(self, task_id: str, witness, checker, hidden: list) -> dict:
        """Seal a task's secrets once; returns the public digests only."""
        if task_id in self._sealed:
            raise SealedError(f"{task_id} is already sealed")
        if not hidden:
            raise SealedError("a task needs hidden instances")
        # Sealed as a detached copy: the sealer keeps no reference into the vault.
        record = json.loads(json.dumps({"witness": witness, "checker": checker, "hidden": list(hidden)}))
        self._sealed[task_id] = record
        return {"witness_sha": _sha(witness), "checker_sha": _sha(checker),
                "hidden_sha": _sha(record["hidden"]), "hidden_count": len(hidden)}

    def sealed_witness(self, task_id: str):
        return json.loads(json.dumps(self._sealed[task_id]["witness"]))

    def sealed_checker(self, task_id: str):
        return json.loads(json.dumps(self._sealed[task_id]["checker"]))

    def sealed_hidden(self, task_id: str) -> list:
        return json.loads(json.dumps(self._sealed[task_id]["hidden"]))

    def has(self, task_id: str) -> bool:
        return task_id in self._sealed

    def __len__(self) -> int:
        return len(self._sealed)

    def dump(self) -> dict:
        """Kernel-only artifact for offline replay; never handed to an agent."""
        return {task_id: dict(record) for task_id, record in self._sealed.items()}

    @classmethod
    def load(cls, dumped: dict) -> "Vault":
        vault = cls()
        for task_id, record in dumped.items():
            vault.seal(task_id, record["witness"], record["checker"], record["hidden"])
        return vault
