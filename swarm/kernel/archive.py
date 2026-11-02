"""The task archive: every admitted task's public face, status and certificates (kernel-held).

The archive is the Breaker's task set as the kernel keeps it: public
examples, lineage, the admission generation and snapshot, the Kb margin,
and the crossing record when one exists. Checkers, witnesses and hidden
instances are not here; they are in the vault. Agents receive
``public_view`` only. A task is ``open`` until it is crossed or until
``horizon`` generations pass without a crossing, when it becomes a
``marker`` (Phase K's frontier marker): kept, never deleted, no longer
checked every generation.
"""
from __future__ import annotations

import json


def _copy(value):
    """A detached copy through JSON: what leaves or enters the archive shares no object with it."""
    return json.loads(json.dumps(value, default=str))


class Archive:
    def __init__(self, horizon: int):
        self.horizon = int(horizon)
        self.tasks: dict = {}            # id -> record
        self.signatures: set = set()

    def add(self, record: dict) -> None:
        if record["id"] in self.tasks:
            raise KeyError(f"duplicate task {record['id']}")
        self.tasks[record["id"]] = dict(_copy(record), status="open", crossed_generation=None,
                                        crossing=None, mined=None)
        self.signatures.add(record["signature"])

    def open_tasks(self) -> list:
        return [t for t in self.tasks.values() if t["status"] == "open"]

    def crossed_tasks(self) -> list:
        return [t for t in self.tasks.values() if t["status"] == "crossed"]

    def mark_crossed(self, task_id: str, generation: int, crossing: dict) -> None:
        task = self.tasks[task_id]
        task["status"] = "crossed"
        task["crossed_generation"] = int(generation)
        task["crossing"] = _copy(crossing)

    def mark_mined(self, task_id: str, generation: int, program) -> None:
        task = self.tasks[task_id]
        if task["mined"] is None:
            task["mined"] = {"generation": int(generation), "program": _copy(program)}

    def retire(self, generation: int) -> list:
        """Open tasks admitted more than ``horizon`` generations ago become markers."""
        retired = []
        for task in self.open_tasks():
            if generation - task["admitted_generation"] >= self.horizon:
                task["status"] = "marker"
                retired.append(task["id"])
        return retired

    def public_view(self) -> list:
        """What agents may see: ids, public examples, lineage, status, generations (a copy, never a reference)."""
        return [{"id": t["id"], "lineage": t["lineage"], "examples": _copy(t["examples"]),
                 "input_kind": t["input_kind"], "status": t["status"],
                 "admitted_generation": t["admitted_generation"],
                 "crossed_generation": t["crossed_generation"],
                 "crossing_program": None if t["crossing"] is None else _copy(t["crossing"]["program"]),
                 "crossing_term": None if t["crossing"] is None else _copy(t["crossing"].get("term")),
                 "mined": t["mined"] is not None}
                for t in self.tasks.values()]

    def counts(self) -> dict:
        out = {"open": 0, "crossed": 0, "marker": 0}
        for task in self.tasks.values():
            out[task["status"]] += 1
        out["total"] = len(self.tasks)
        return out

    def dump(self) -> dict:
        return {"horizon": self.horizon, "tasks": json.loads(json.dumps(self.tasks, default=str))}

    @classmethod
    def load(cls, dumped: dict) -> "Archive":
        archive = cls(dumped["horizon"])
        for record in dumped["tasks"].values():
            archive.tasks[record["id"]] = record
            archive.signatures.add(record["signature"])
        return archive
