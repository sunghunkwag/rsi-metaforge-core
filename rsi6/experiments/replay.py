"""Replay every search from the runs in the ledger, without running anything: the searches of the two
registered rounds, of the continued process, the climbs of process c and the searches of its recursion check.

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
from rsi6.learner import designs
from rsi6.meta import rounds, space

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def conditions(record, ledger) -> tuple:
    """``(registration, seed, edit statistics)`` of a recorded search: what its driver gave it besides
    what the record itself holds. The two registered rounds (generations.py), the continued process
    (continued.py), the climbs of process c (alternating.py) and the searches of the recursion check
    (recursion.py) each have their registration and their rule for the seed."""
    own = 1 if record["improver"] == "learner" else 2
    registration = lambda kind: ledger.select(type=kind)[0]["registration"]
    earlier = lambda tag: ledger.select(type="search", tag=tag)
    if record["type"] == "recursion_search":
        return registration("registration_c"), (3000 if record["name"] == "gen0" else 4000) + record["generation"], None
    label = record["round"]
    if isinstance(label, int):
        before = earlier(f"search:{label - 1}:self")
        return registration("registration"), 1000 * label + own, before[-1].get("edit_stats") if (record["name"] == "self" and before) else None
    g = int(label[1:])
    if label.startswith("b"):
        before = earlier(f"search:b{g - 1}:self")
        return registration("registration_b"), 2000 * g + own, before[-1].get("edit_stats") if (record["name"] == "self" and before) else None
    if label.startswith("c"):
        return registration("registration_c"), 3000 + g, None
    raise RuntimeError(f"a search of an unknown process: round {label!r}")


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

    keep_run, keep_problem, keep_rules = run.run, space.VersionProblem, dict(rounds.RULES)
    run.run = refuse
    searches = [r for r in ledger.records if r.get("type") in ("search", "recursion_search")]
    by_digest = {designs.digest(designs.default(d)): designs.default(d) for d in ("a", "b")}
    for record in searches:                              # every version a search started from was a default, a nominee or adopted
        if record["nominee_version"] is not None:
            by_digest[record["nominee"]] = record["nominee_version"]
    for record in ledger.select(type="adopt"):
        by_digest[record["digest"]] = record["version"]
    out = {}
    try:
        for record in searches:
            kind = record["improver"]
            reg, seed, stats = conditions(record, ledger)
            rounds.RULES.clear()
            rounds.RULES.update(keep_rules)
            rounds.RULES.update(reg["rules"])
            start = by_digest[record["start"]]
            improver = by_digest[record["improver_version"]] if kind == "learner" else None
            made = []

            class Recorded(keep_problem):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    made.append(self)

            space.VersionProblem = Recorded
            again = rounds.search(kind, improver, start, record["envs"], record["seeds"], reg["budgets"]["search"],
                                  record["cpu_limit"], cache, record["tag"], seed=seed, edit_stats=stats,
                                  objective=rounds.breadth if record.get("objective") == "breadth" else None)
            same = all(again[k] == record[k] for k in ("costs", "nominee", "evaluated", "improving", "best_cost", "expected"))
            out[record["tag"]] = {
                "replayed_identically": bool(same),
                "candidates": [{"digest": designs.digest(h["version"]), "cost": h["cost"], "cpu": h["cpu"],
                                "changes": {k: [d["from"], d["to"]] for k, d in designs.differences(start, h["version"]).items()}}
                               for h in made[0].history]}
    finally:
        run.run, space.VersionProblem = keep_run, keep_problem
        rounds.RULES.clear()
        rounds.RULES.update(keep_rules)
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
