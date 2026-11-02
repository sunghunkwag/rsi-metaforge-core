"""Self-edit evaluation: the kernel judges a candidate mutable tree on the archive (OWNER_DIRECTIVE.md §5).

The Builder proposes a candidate tree (a patched copy of its live tree);
the kernel snapshots it and runs fresh ``B_inst`` solves from the
candidate and from the incumbent snapshot on the same task set: every
open task plus a replay sample of crossed tasks. A solve counts only when
the checker accepts the program on the task's hidden instances, and, as
in the crossing check, everything learned from the task itself is
excluded from its solve, so the count is a count of crossings in the
kernel's sense. The gain is measured on the open tasks only: the
candidate is adopted iff its accepted solves of open tasks per logical
budget spent on them strictly exceed the incumbent's and every crossed
task of the replay sample that the incumbent still solves is still
solved. The crossed sample is the regression test and nothing else: a
re-solve of a task crossed long ago is not a crossing and adds nothing
to the gain. The judgement is the kernel's count of executions, not a
score the Builder computes.

An executor failure while either tree is evaluated (child crash or
timeout) is not a verdict: the candidate is refused with the reason, no
score is cached, and nothing is adopted on a wall-clock event.

The isolation guard around the evaluation: every file of the run
directory outside the candidate's own directory and its own snapshot
must be unchanged (path, size, modification time) before and after; a
patch whose code wrote elsewhere is rejected. ``refuse`` ledgers a
candidate the Builder's scope guard turned down without evaluation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import random

from .snapshot import tree_sha256


def directory_digest(directory: Path, exclude: tuple = ()) -> str:
    digest = hashlib.sha256()
    directory = Path(directory)
    excluded = [Path(e) for e in exclude]
    for path in sorted(directory.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        if any(path == e or e in path.parents for e in excluded):
            continue
        stat = path.stat()
        digest.update(f"{path.relative_to(directory)}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8"))
    return digest.hexdigest()


class EditJudge:
    def __init__(self, executor, vault, archive, snapshots, ledger, b_inst: int, sample: int = 6):
        self.executor = executor
        self.vault = vault
        self.archive = archive
        self.snapshots = snapshots
        self.ledger = ledger
        self.b_inst = int(b_inst)
        self.sample = int(sample)
        self._cache: dict = {}                  # (sha, task key) -> completed score

    def _accepts(self, task_id: str, program) -> tuple:
        hidden = self.vault.sealed_hidden(task_id)
        checker = self.vault.sealed_checker(task_id)
        return self.executor.accepts(program, [i["inputs"][0] for i in hidden], checker, module="edits")

    def task_set(self, generation: int) -> list:
        rng = random.Random(f"swarm-edit-sample-{generation}")
        crossed = sorted(t["id"] for t in self.archive.crossed_tasks())
        sampled = sorted(rng.sample(crossed, min(self.sample, len(crossed))))
        return sorted(t["id"] for t in self.archive.open_tasks()) + sampled

    def score(self, sha: str, task_ids: list) -> dict:
        """Accepted solves and the candidates spent on open tasks; ``failed`` when the executor failed."""
        key = (sha, tuple(task_ids))
        if key in self._cache:
            return self._cache[key]
        tasks = [{"id": t, "examples": self.archive.tasks[t]["examples"]} for t in task_ids]
        results = self.snapshots.solve_excluded(sha, tasks, self.b_inst, agent="kernel") if tasks else []
        if results is None:
            return {"solved": set(), "open_budget": 0, "failed": True, "reason": "solver failed"}
        solved, open_budget = set(), 0
        for result in results:
            task_id = result["id"]
            if self.archive.tasks[task_id]["status"] == "open":
                open_budget += int(result.get("candidates", 0))
            if result.get("program") is None:
                continue
            accepted, failed = self._accepts(task_id, result["program"])
            if failed:
                return {"solved": set(), "open_budget": 0, "failed": True, "reason": "hidden check failed"}
            if accepted:
                solved.add(task_id)
        score = {"solved": solved, "open_budget": max(open_budget, 1), "failed": False, "reason": None}
        self._cache[key] = score
        return score

    def refuse(self, generation: int, patch: dict, reason: str) -> dict:
        """Ledger a candidate turned down before evaluation (the Builder's scope guard)."""
        decision = {"generation": int(generation), "candidate": None, "incumbent": None,
                    "patch": patch, "tasks": 0, "open_tasks": 0,
                    "incumbent_solved": 0, "candidate_solved": 0,
                    "incumbent_open_solved": 0, "candidate_open_solved": 0,
                    "incumbent_budget": 0, "candidate_budget": 0, "regressed": [],
                    "adopted": False, "reason": reason}
        self.ledger.append("self_edit", decision)
        return decision

    def judge(self, candidate_dir: Path, incumbent_sha: str, generation: int, run_dir: Path,
              patch: dict) -> dict:
        """Snapshot the candidate, compare with the incumbent on the archive, ledger the decision."""
        candidate_dir = Path(candidate_dir)
        candidate_sha = tree_sha256(candidate_dir)
        excluded = (candidate_dir, self.snapshots.store / candidate_sha, self.snapshots.store / (candidate_sha + ".tmp"))
        before = directory_digest(run_dir, exclude=excluded)
        assert self.snapshots.take(candidate_dir) == candidate_sha
        task_ids = self.task_set(generation)
        open_ids = {t for t in task_ids if self.archive.tasks[t]["status"] == "open"}
        crossed = {t for t in task_ids if self.archive.tasks[t]["status"] == "crossed"}
        incumbent = self.score(incumbent_sha, task_ids)
        candidate = self.score(candidate_sha, task_ids) if not incumbent["failed"] else {
            "solved": set(), "open_budget": 0, "failed": True, "reason": "not evaluated"}
        after = directory_digest(run_dir, exclude=excluded)
        regressed = sorted((incumbent["solved"] & crossed) - candidate["solved"])
        rate_candidate = len(candidate["solved"] & open_ids) / candidate["open_budget"] if not candidate["failed"] else -1.0
        rate_incumbent = len(incumbent["solved"] & open_ids) / incumbent["open_budget"] if not incumbent["failed"] else -1.0
        adopted = (before == after and not incumbent["failed"] and not candidate["failed"]
                   and not regressed and rate_candidate > rate_incumbent)
        reason = ("adopted" if adopted
                  else "wrote outside its tree" if before != after
                  else f"incumbent evaluation failed: {incumbent['reason']}" if incumbent["failed"]
                  else f"candidate evaluation failed: {candidate['reason']}" if candidate["failed"]
                  else f"regressed {regressed}" if regressed
                  else "no strict gain")
        decision = {"generation": int(generation), "candidate": candidate_sha, "incumbent": incumbent_sha,
                    "patch": patch, "tasks": len(task_ids), "open_tasks": len(open_ids),
                    "incumbent_solved": len(incumbent["solved"]), "candidate_solved": len(candidate["solved"]),
                    "incumbent_open_solved": len(incumbent["solved"] & open_ids),
                    "candidate_open_solved": len(candidate["solved"] & open_ids),
                    "incumbent_budget": incumbent["open_budget"], "candidate_budget": candidate["open_budget"],
                    "regressed": regressed, "adopted": adopted, "reason": reason}
        self.ledger.append("self_edit", decision)
        return decision
