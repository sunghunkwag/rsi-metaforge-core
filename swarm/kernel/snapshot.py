"""Content-addressed snapshots of the Builder's mutable tree, and isolated calls into them.

A snapshot is the SHA-256 over the sorted relative paths and contents of
every source and data file of a mutable tree (caches and search state
excluded); the files are copied to ``<store>/<sha>/mutable/``. Kb runs the
Builder's solver from the snapshot taken at admission, never from the live
tree, and crossing checks run from the current snapshot: the certificate is
computed on code that cannot change under it (``tests/test_kernel.py``
plants a sandbagging live tree and asserts the snapshot is what runs).

Calls into a snapshot go through ``Executor.isolated_call``: a guarded
child whose ``sys.path`` is the snapshot directory and the repository
root, confined by the executor's guard to reading its own tree and the
kernel package and to writing inside its own tree, with the memory cap
and a timeout; the child imports ``mutable.solve`` from the snapshot and
returns JSON. Evaluation counts come back in the payload from the pinned
evaluator and are charged to the meter here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pkl"}
SOLVE_TIMEOUT_S = 120.0
SECONDS_PER_CANDIDATE = 0.03      # measured 0.005-0.012 s per candidate on the development machine; 2.5x margin


def solve_timeout(candidates: int) -> float:
    """Wall-clock allowance for a solve of ``candidates`` logical candidates in a child."""
    return SOLVE_TIMEOUT_S + SECONDS_PER_CANDIDATE * max(int(candidates), 0)


def tree_files(tree_dir: Path) -> list:
    tree_dir = Path(tree_dir)
    files = []
    for path in sorted(tree_dir.rglob("*")):
        if path.is_dir() or any(part in EXCLUDED_DIRS for part in path.relative_to(tree_dir).parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES or path.name.startswith("."):
            continue
        files.append(path)
    return files


def tree_sha256(tree_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in tree_files(tree_dir):
        digest.update(str(path.relative_to(tree_dir)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class SnapshotStore:
    def __init__(self, store_dir: Path, executor, meter=None):
        self.store = Path(store_dir)
        self.store.mkdir(parents=True, exist_ok=True)
        self.executor = executor
        self.meter = meter
        self._memo: dict = {}          # (sha, task id, budget) -> result of the self-excluded fresh solve

    def take(self, tree_dir: Path) -> str:
        """Snapshot a mutable tree; returns its content hash (idempotent)."""
        sha = tree_sha256(tree_dir)
        final = self.store / sha
        if not (final / "mutable").exists():
            # Copy into a temporary directory and rename it into place, so a
            # kill mid-copy never leaves a partial snapshot under its hash.
            staging = self.store / (sha + ".tmp")
            if staging.exists():
                shutil.rmtree(staging)
            target = staging / "mutable"
            for path in tree_files(tree_dir):
                destination = target / path.relative_to(tree_dir)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
            (staging / "SHA256").write_text(sha + "\n", encoding="utf-8")
            os.replace(staging, final)
        return sha

    def path(self, sha: str) -> Path:
        path = self.store / sha
        if not (path / "mutable").exists():
            raise KeyError(f"no snapshot {sha}")
        return path

    def call(self, sha: str, function: str, payload: dict, agent: str = "builder",
             timeout: float = SOLVE_TIMEOUT_S) -> dict | None:
        result = self.executor.isolated_call([self.path(sha), ROOT], "mutable.solve", function,
                                             payload, timeout, read=[self.path(sha)], write=[self.path(sha)])
        if result is not None and self.meter is not None and "meter" in result:
            self.meter.charge(agent, f"snapshot:{function}", steps=result["meter"].get("steps", 0),
                              evaluations=result["meter"].get("candidates",
                                                              result["meter"].get("evaluations", 0)))
        return result

    def call_tree(self, tree_dir: Path, function: str, payload: dict, agent: str = "builder",
                  timeout: float = SOLVE_TIMEOUT_S) -> dict | None:
        """A metered isolated call into a live tree (the Builder's wake and learning).

        ``tree_dir`` is the tree's ``mutable`` directory; the child imports
        ``mutable.solve`` from its parent, under the executor's memory cap
        and ``timeout``. Counts come back from the pinned evaluator and are
        charged to ``agent`` here, as for snapshots.
        """
        tree_dir = Path(tree_dir)
        if tree_dir.name != "mutable":
            raise ValueError("a live tree is a directory named 'mutable'")
        result = self.executor.isolated_call([tree_dir.parent, ROOT], "mutable.solve", function,
                                             payload, timeout, read=[tree_dir.parent], write=[tree_dir.parent])
        if result is not None and self.meter is not None and "meter" in result:
            self.meter.charge(agent, f"live:{function}", steps=result["meter"].get("steps", 0),
                              evaluations=result["meter"].get("candidates",
                                                              result["meter"].get("evaluations", 0)))
        return result

    def solve(self, sha: str, tasks: list, budget: int, exclude: dict | None = None,
              agent: str = "kernel") -> list | None:
        """Fresh solves of ``tasks`` (public views) at ``budget`` in the snapshot; None on failure."""
        result = self.call(sha, "solve_many", {"tasks": tasks, "budget": int(budget),
                                                "exclude": exclude or {}}, agent=agent,
                           timeout=solve_timeout(int(budget) * len(tasks)))
        return None if result is None else result["results"]

    def solve_excluded(self, sha: str, tasks: list, budget: int, agent: str = "kernel") -> list | None:
        """Fresh solves at ``budget`` with each task's own fragments excluded, memoized per (sha, task, budget).

        A solve from a content-addressed snapshot is deterministic and
        independent across tasks, so a (sha, task, budget) result is final:
        the crossing check and the self-edit judge share this memo, and a
        memoized result charges nothing because its cost was counted when
        it was run. Returns None when the solver child failed.
        """
        budget = int(budget)
        pending = [t for t in tasks if (sha, t["id"], budget) not in self._memo]
        if pending:
            results = self.solve(sha, pending, budget, exclude={t["id"]: [t["id"]] for t in pending},
                                 agent=agent)
            if results is None:
                return None
            for result in results:
                self._memo[(sha, result["id"], budget)] = result
        return [self._memo[(sha, t["id"], budget)] for t in tasks]

    def inventory(self, sha: str) -> dict | None:
        result = self.executor.isolated_call([self.path(sha), ROOT], "mutable.solve", "inventory",
                                             {}, 30.0, read=[self.path(sha)], write=[self.path(sha)])
        if result is None:
            result = self.executor.isolated_call([self.path(sha), ROOT], "mutable.solve", "inventory",
                                                 {}, 30.0, read=[self.path(sha)], write=[self.path(sha)])
        return result
