"""The crossing check and the mined-solve gate (OWNER_DIRECTIVE.md §2; Phase K §6 steps 4-5).

Two kernel judgements on a task, both by execution of the checker on the
hidden instances and nothing else:

- **Mined solve.** A program the Builder found in its own wake (any
  budget, resumed state) is run on the hidden inputs; if the checker
  accepts every output, the task is *mined* and the Builder may learn
  from that program. This is Phase K's sealed solve gate; it is not a
  crossing.
- **Crossing.** The Builder's current snapshot, run fresh at the
  instrument budget ``B_inst`` on the task's public examples with
  everything learned from the task itself excluded (library entries and
  forged primitives sourced from it, every entry that references one of
  them, and the grammar weights refit without the task's own solutions;
  see ``builder/mutable/solve.py``), produces a program the checker
  accepts on every hidden instance. The admission record proves the
  admission-time snapshot failed at the same budget, so the difference
  is attributable to substrate change driven by other tasks. The
  crossing record carries the program, the fragments it used (closed
  through the library entries' own bodies) and their source tasks: the
  credit chain ``replay.py`` re-derives.

Solves are memoized per (snapshot, task, budget) in the snapshot store
and their verdicts here: an unchanged snapshot cannot newly cross a task,
so a task is judged once per snapshot. A task admitted in the current
generation is not checked: Kb ran on the same snapshot. An executor
failure (child crash or timeout) during a check is ledgered as a failed
check and leaves no verdict, so the task is checked again next
generation; it is never read as a rejection or an acceptance.
"""
from __future__ import annotations


class Crossings:
    def __init__(self, executor, vault, archive, snapshots, ledger, b_inst: int):
        self.executor = executor
        self.vault = vault
        self.archive = archive
        self.snapshots = snapshots
        self.ledger = ledger
        self.b_inst = int(b_inst)
        self._verdicts: dict = {}          # (sha, task id, budget) -> "unsolved" | "rejected" | "crossed"

    def _accepts(self, task_id: str, program) -> tuple:
        """(accepted, failed): the checker's verdict on the hidden instances, or an executor failure."""
        hidden = self.vault.sealed_hidden(task_id)
        checker = self.vault.sealed_checker(task_id)
        return self.executor.accepts(program, [i["inputs"][0] for i in hidden], checker, module="crossing")

    def mined(self, task_id: str, program, generation: int):
        """The sealed solve gate on a wake solution: True, False, or None when the check failed."""
        task = self.archive.tasks[task_id]
        if task["status"] != "open":
            return False
        ok, failed = self._accepts(task_id, program)
        if failed:
            self.ledger.append("mined_check_failed", {"id": task_id, "generation": generation})
            return None
        self.ledger.append("mined", {"id": task_id, "generation": generation, "accepted": ok})
        if ok:
            self.archive.mark_mined(task_id, generation, program)
        return ok

    @staticmethod
    def _closure(names, library: dict) -> list:
        """Fragment names closed through the inventory's per-entry references."""
        out, stack = set(), list(names)
        while stack:
            name = stack.pop()
            if name in out:
                continue
            out.add(name)
            entry = library.get(name)
            if entry:
                stack.extend(entry.get("references", []))
        return sorted(out)

    def check(self, task_ids: list, snapshot_sha: str, generation: int) -> list:
        """Fresh B_inst solves from the snapshot with own-task exclusion; returns crossed ids."""
        tasks = [self.archive.tasks[t] for t in task_ids
                 if self.archive.tasks[t]["status"] == "open"
                 and self.archive.tasks[t]["admitted_generation"] < int(generation)]
        pending = [t for t in tasks if (snapshot_sha, t["id"], self.b_inst) not in self._verdicts]
        if not pending:
            return []
        public = [{"id": t["id"], "examples": t["examples"]} for t in pending]
        results = self.snapshots.solve_excluded(snapshot_sha, public, self.b_inst, agent="kernel")
        if results is None:
            self.ledger.append("crossing_check_failed", {"generation": generation, "snapshot": snapshot_sha,
                                                         "reason": "solver failed"})
            return []
        inventory = self.snapshots.inventory(snapshot_sha)
        if inventory is None:
            self.ledger.append("crossing_check_failed", {"generation": generation, "snapshot": snapshot_sha,
                                                         "reason": "inventory unavailable"})
            return []
        crossed = []
        for result in results:
            task_id = result["id"]
            key = (snapshot_sha, task_id, self.b_inst)
            if result.get("program") is None:
                self._verdicts[key] = "unsolved"
                continue
            accepted, failed = self._accepts(task_id, result["program"])
            if failed:
                self.ledger.append("crossing_check_failed", {"generation": generation, "snapshot": snapshot_sha,
                                                             "id": task_id, "reason": "executor failed"})
                continue
            if not accepted:
                self._verdicts[key] = "rejected"
                self.ledger.append("crossing_rejected", {"id": task_id, "generation": generation,
                                                         "reason": "checker rejects on hidden"})
                continue
            fragments = self._closure(result.get("fragments", []), inventory["library"])
            sources = {}
            for name in fragments:
                entry = inventory["library"].get(name) or inventory["forged"].get(name)
                sources[name] = [] if entry is None else list(entry.get("sources", []))
            if any(task_id in s for s in sources.values()):
                self._verdicts[key] = "rejected"
                self.ledger.append("crossing_rejected", {"id": task_id, "generation": generation,
                                                         "reason": "own-solution fragment"})
                continue
            crossing = {"generation": int(generation), "snapshot": snapshot_sha,
                        "program": result["program"], "dsl": result.get("dsl"),
                        "term": result.get("term"),
                        "fragments": fragments, "sources": sources,
                        "candidates": result.get("candidates"),
                        "generations_to_crossing": int(generation) - self.archive.tasks[task_id]["admitted_generation"]}
            self._verdicts[key] = "crossed"
            self.archive.mark_crossed(task_id, generation, crossing)
            self.ledger.append("crossing", {"id": task_id, **crossing})
            crossed.append(task_id)
        return crossed
