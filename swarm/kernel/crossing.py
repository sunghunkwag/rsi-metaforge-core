"""The crossing check and the mined-solve gate (OWNER_DIRECTIVE.md §2; Phase K §6 steps 4-5).

Two kernel judgements on a task, both by execution of the checker on the
hidden instances and nothing else:

- **Mined solve.** A program the Builder found in its own wake (any
  budget, resumed state) is run on the hidden inputs; if the checker
  accepts every output, the task is *mined* and the Builder may learn
  from that program. This is Phase K's sealed solve gate; it is not a
  crossing.
- **Crossing.** The Builder's current snapshot, run fresh at the
  instrument budget ``B_inst`` on the task's public examples with every
  library entry and forged primitive sourced from the task itself
  excluded, produces a program the checker accepts on every hidden
  instance. The admission record proves the admission-time snapshot
  failed at the same budget, so the difference is attributable to
  substrate change driven by other tasks (own-solution fragments
  excluded). The crossing record carries the program, the fragments it
  used and their source tasks: the credit chain ``replay.py`` re-derives.
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

    def _accepts(self, task_id: str, program) -> bool:
        hidden = self.vault.sealed_hidden(task_id)
        checker = self.vault.sealed_checker(task_id)
        runs = self.executor.run_batch(program, [[i["inputs"][0]] for i in hidden], module="crossing")
        outputs = [r["value"] if r["ok"] else None for r in runs]
        verdicts = self.executor.check_batch(
            checker, [(i["inputs"][0], o) for i, o in zip(hidden, outputs)], module="crossing")
        return all(v is True for v in verdicts)

    def mined(self, task_id: str, program, generation: int) -> bool:
        """The sealed solve gate on a wake solution."""
        task = self.archive.tasks[task_id]
        if task["status"] != "open":
            return False
        ok = self._accepts(task_id, program)
        self.ledger.append("mined", {"id": task_id, "generation": generation, "accepted": ok})
        if ok:
            self.archive.mark_mined(task_id, generation, program)
        return ok

    def check(self, task_ids: list, snapshot_sha: str, generation: int) -> list:
        """Fresh B_inst solves from the snapshot with own-task exclusion; returns crossed ids."""
        tasks = [self.archive.tasks[t] for t in task_ids if self.archive.tasks[t]["status"] == "open"]
        if not tasks:
            return []
        public = [{"id": t["id"], "examples": t["examples"]} for t in tasks]
        results = self.snapshots.solve(snapshot_sha, public, self.b_inst,
                                       exclude={t["id"]: [t["id"]] for t in tasks}, agent="kernel")
        if results is None:
            self.ledger.append("crossing_check_failed", {"generation": generation,
                                                         "snapshot": snapshot_sha})
            return []
        inventory = self.snapshots.inventory(snapshot_sha) or {"library": {}, "forged": {}}
        crossed = []
        for result in results:
            task_id = result["id"]
            if result.get("program") is None:
                continue
            if not self._accepts(task_id, result["program"]):
                self.ledger.append("crossing_rejected", {"id": task_id, "generation": generation,
                                                         "reason": "checker rejects on hidden"})
                continue
            fragments = result.get("fragments", [])
            sources = {}
            for name in fragments:
                entry = inventory["library"].get(name) or inventory["forged"].get(name)
                sources[name] = [] if entry is None else list(entry.get("sources", []))
            if any(task_id in s for s in sources.values()):
                self.ledger.append("crossing_rejected", {"id": task_id, "generation": generation,
                                                         "reason": "own-solution fragment"})
                continue
            crossing = {"generation": int(generation), "snapshot": snapshot_sha,
                        "program": result["program"], "dsl": result.get("dsl"),
                        "term": result.get("term"),
                        "fragments": fragments, "sources": sources,
                        "candidates": result.get("candidates"),
                        "generations_to_crossing": int(generation) - self.archive.tasks[task_id]["admitted_generation"]}
            self.archive.mark_crossed(task_id, generation, crossing)
            self.ledger.append("crossing", {"id": task_id, **crossing})
            crossed.append(task_id)
        return crossed
