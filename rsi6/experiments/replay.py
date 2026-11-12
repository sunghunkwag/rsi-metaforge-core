"""Replay every search from the runs in the ledger, without running anything.

    python -m rsi6.experiments.replay [--ledger PATH] [--out candidates.json]

A search is deterministic given its seed and the measurements it received. Every measurement is
a run in the ledger, so the search can be played again from the ledger alone: the same
candidates in the same order, the same costs, the same nominee. This is a check of the record
(a replay that would need a run the ledger does not hold stops with an error; a replay that
differs from the search record is reported), and it recovers what the search records do not
hold: the version record of every candidate.

The ledger is read from a temporary copy; nothing is appended to it.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from rsi6.kernel import ledger as ledgers
from rsi6.kernel import run
from rsi6.learner import version as versions
from rsi6.meta import rounds, space

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def replay(path: str) -> dict:
    folder = tempfile.mkdtemp()
    copy = os.path.join(folder, "ledger.jsonl")
    shutil.copy(path, copy)
    ledger = ledgers.Ledger(copy)
    ledger.verify()
    size = len(ledger.records)
    cache = run.Cache(ledger)

    def refuse(jobs, ledger_, workers=4):
        if jobs:
            raise RuntimeError("the replay needs a run that is not in the ledger")
        return []

    keep_run, keep_problem = run.run, space.VersionProblem
    run.run = refuse
    reg = ledger.select(type="registration")[0]["registration"]
    rounds.RULES.update(reg["rules"])
    v0 = versions.default()
    by_digest = {versions.digest(v0): v0}
    for record in ledger.select(type="search"):
        if record["nominee_version"] is not None:
            by_digest[record["nominee"]] = record["nominee_version"]
    out = {}
    try:
        for record in ledger.select(type="search"):
            g, name, kind = record["round"], record["name"], record["improver"]
            start = by_digest[record["start"]]
            improver = by_digest[record["improver_version"]] if kind == "learner" else None
            previous = ledger.select(type="search", tag=f"search:{g - 1}:self")
            stats = previous[-1].get("edit_stats") if (name == "self" and previous) else None
            made = []

            class Recorded(keep_problem):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    made.append(self)

            space.VersionProblem = Recorded
            again = rounds.search(kind, improver, start, record["envs"], record["seeds"], reg["budgets"]["search"],
                                  record["cpu_limit"], cache, record["tag"], seed=1000 * g + (1 if kind == "learner" else 2),
                                  edit_stats=stats)
            same = all(again[k] == record[k] for k in ("costs", "nominee", "evaluated", "improving", "best_cost", "expected"))
            out[record["tag"]] = {
                "replayed_identically": bool(same),
                "candidates": [{"digest": versions.digest(h["version"]), "cost": h["cost"], "cpu": h["cpu"],
                                "changes": {k: [d["from"], d["to"]] for k, d in versions.differences(start, h["version"]).items()}}
                               for h in made[0].history]}
    finally:
        run.run, space.VersionProblem = keep_run, keep_problem
    if len(ledger.records) != size:
        raise RuntimeError("the replay appended to its copy of the ledger")
    shutil.rmtree(folder)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    table = replay(args.ledger)
    for tag, entry in table.items():
        print(f"{tag:22s} replayed identically: {entry['replayed_identically']} | candidates {len(entry['candidates'])}")
    if args.out:
        json.dump(table, open(args.out, "w"), indent=1)
    return 0 if all(entry["replayed_identically"] for entry in table.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
