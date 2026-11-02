"""Self-edit evaluation: the kernel judges a candidate mutable tree on the archive (OWNER_DIRECTIVE.md §5).

The Builder proposes a candidate tree (a patched copy of its live tree);
the kernel snapshots it and runs fresh ``B_inst`` solves from the
candidate and from the incumbent snapshot on the same task set: every
open task plus a replay sample of crossed tasks. A solve counts only when
the checker accepts the program on the task's hidden instances, and, as
in the crossing check, every library entry or forged primitive sourced
from the task itself is excluded from its solve, so the count is a count
of crossings in the kernel's sense. The candidate is adopted iff its
crossings per logical budget strictly exceed the incumbent's and every
crossed task the incumbent still crosses is still crossed. The judgement
is the kernel's count of executions, not a score the Builder computes.

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
        self._cache: dict = {}                  # (sha, task key) -> accepted solves, budget

    def _accepts(self, task_id: str, program) -> bool:
        hidden = self.vault.sealed_hidden(task_id)
        checker = self.vault.sealed_checker(task_id)
        runs = self.executor.run_batch(program, [[i["inputs"][0]] for i in hidden], module="edits")
        outputs = [r["value"] if r["ok"] else None for r in runs]
        verdicts = self.executor.check_batch(checker, [(i["inputs"][0], o) for i, o in zip(hidden, outputs)],
                                             module="edits")
        return all(v is True for v in verdicts)

    def task_set(self, generation: int) -> list:
        rng = random.Random(f"swarm-edit-sample-{generation}")
        crossed = sorted(t["id"] for t in self.archive.crossed_tasks())
        sampled = sorted(rng.sample(crossed, min(self.sample, len(crossed))))
        return sorted(t["id"] for t in self.archive.open_tasks()) + sampled

    def score(self, sha: str, task_ids: list) -> dict:
        key = (sha, tuple(task_ids))
        if key in self._cache:
            return self._cache[key]
        tasks = [{"id": t, "examples": self.archive.tasks[t]["examples"]} for t in task_ids]
        results = self.snapshots.solve_excluded(sha, tasks, self.b_inst, agent="kernel") if tasks else []
        if results is None:
            score = {"solved": set(), "budget": 0, "failed": True}
        else:
            solved = {r["id"] for r in results
                      if r.get("program") is not None and self._accepts(r["id"], r["program"])}
            budget = sum(int(r.get("candidates", 0)) for r in results)
            score = {"solved": solved, "budget": max(budget, 1), "failed": False}
        self._cache[key] = score
        return score

    def refuse(self, generation: int, patch: dict, reason: str) -> dict:
        """Ledger a candidate turned down before evaluation (the Builder's scope guard)."""
        decision = {"generation": int(generation), "candidate": None, "incumbent": None,
                    "patch": patch, "tasks": 0, "incumbent_solved": 0, "candidate_solved": 0,
                    "incumbent_budget": 0, "candidate_budget": 0, "regressed": [],
                    "adopted": False, "reason": reason}
        self.ledger.append("self_edit", decision)
        return decision

    def judge(self, candidate_dir: Path, incumbent_sha: str, generation: int, run_dir: Path,
              patch: dict) -> dict:
        """Snapshot the candidate, compare with the incumbent on the archive, ledger the decision."""
        candidate_dir = Path(candidate_dir)
        candidate_sha = tree_sha256(candidate_dir)
        excluded = (candidate_dir, self.snapshots.store / candidate_sha)
        before = directory_digest(run_dir, exclude=excluded)
        assert self.snapshots.take(candidate_dir) == candidate_sha
        task_ids = self.task_set(generation)
        incumbent = self.score(incumbent_sha, task_ids)
        candidate = self.score(candidate_sha, task_ids)
        after = directory_digest(run_dir, exclude=excluded)
        crossed = {t for t in task_ids if self.archive.tasks[t]["status"] == "crossed"}
        regressed = sorted((incumbent["solved"] & crossed) - candidate["solved"])
        rate_candidate = len(candidate["solved"]) / candidate["budget"] if not candidate["failed"] else -1.0
        rate_incumbent = len(incumbent["solved"]) / incumbent["budget"] if not incumbent["failed"] else -1.0
        adopted = (before == after and not candidate["failed"] and not regressed
                   and rate_candidate > rate_incumbent)
        reason = ("adopted" if adopted else "wrote outside its tree" if before != after
                  else "candidate crashed" if candidate["failed"] else f"regressed {regressed}" if regressed
                  else "no strict gain")
        decision = {"generation": int(generation), "candidate": candidate_sha, "incumbent": incumbent_sha,
                    "patch": patch, "tasks": len(task_ids), "incumbent_solved": len(incumbent["solved"]),
                    "candidate_solved": len(candidate["solved"]), "incumbent_budget": incumbent["budget"],
                    "candidate_budget": candidate["budget"], "regressed": regressed,
                    "adopted": adopted, "reason": reason}
        self.ledger.append("self_edit", decision)
        return decision
