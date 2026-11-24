"""Development: every mechanism of design s on one category of the pool (a table, not a search).

Development only: categories of the source pool, a scratch ledger, seeds no other run uses,
nothing here is evidence. Design s (``rsi6/learner/design_s.py``) has a list of 324 mechanisms:
every combination of the values of the six fields its search reads. This module measures every
one of them on one category for the given seeds, at the run budget of the registrations, on all
the fresh instances. With the whole list measured, a search over the list needs no new runs:
``rsi6/meta/chain_s.py`` looks its evaluations up in the tables, so chains of self-modification
can be repeated thousands of times and from every starting mechanism.

    python -m rsi6.experiments.dev_grid <category> --seeds 731001 731002 731003 731004 --out DIR

Mechanisms that run the same acquisition (``design_s.behaviour``: ``model.elite`` enters only
through the number of candidates kept, which is 2 for a population of 8 at 0.1 and at 0.25) are
measured once and listed under both versions.

All runs of one process are measured on one machine, so CPU is comparable inside a file and not
across files. A stopped process started again with the same ``--out`` repeats at most one chunk.

``--out`` gets ``grid_<category>_<first seed>.json``: per seed and mechanism the untrained and
acquired scores on all fresh instances and on the two halves the registered gate and its
confirmation use (``kernel.run.halves``), CPU-seconds, whether the acquisition was kept and its
number of rounds; and the run records beside it.
``--smoke`` checks the plumbing only (six mechanisms, a quarter of the training budget, a seed
nothing else uses, files named ``smoke_*``); its numbers mean nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6 import environments
from rsi6.environments import fresh
from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import Cache, halves, key_of
from rsi6.learner import design_s, designs
from rsi6.meta import rounds

POOL = ("binpacking", "jobshop", "knapsack", "partitioning", "pmedian", "quadassign", "setcover",
        "tardiness", "quadratic", "projects", "clique")              # the assignment categories of the source pool
BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}    # the run budget of the registrations
CHUNK = 16


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("category", choices=POOL)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    design_s.install()
    fresh.install()
    category, seeds, budget = args.category, list(args.seeds), dict(BUDGET)
    versions = design_s.mechanisms()
    if args.smoke:
        versions, budget, seeds = versions[::60], dict(BUDGET, train=10.0), [9731001]
    elif any(not 731000 <= s < 732000 for s in seeds):
        raise SystemExit("the seeds of this development measurement are 731000 to 731999")
    stem = ("smoke_" if args.smoke else "") + f"grid_{category}_{seeds[0]}"
    os.makedirs(args.out, exist_ok=True)
    scratch = os.path.join(args.out, stem + ".scratch.jsonl")
    if guard.is_registered(scratch):
        raise SystemExit("development writes a scratch ledger, never a registered one")
    if not os.path.exists(scratch):
        shutil.copy(guard.MAIN, scratch)
    ledger = ledgers.Ledger(scratch)
    started = ledger.select(type="grid_started")
    if not started:                                                # a process started again finds its own marker
        started = [ledger.append({"type": "grid_started", "category": category, "seeds": seeds, "budget": budget})]
    before = started[0]["idx"]
    cache = Cache(ledger)
    first = {}                                                     # behaviour -> index of the version that is measured for it
    for k, v in enumerate(versions):
        first.setdefault(design_s.behaviour(v), k)
    measured = sorted(first.values())
    jobs = [job for s in seeds for k in measured for job in rounds.jobs_for(versions[k], [category], [s], budget, "dev-grid-s")]
    records = []
    for at in range(0, len(jobs), CHUNK):
        records += cache.get(jobs[at:at + CHUNK], workers=args.workers)
        print(f"{min(at + CHUNK, len(jobs))} of {len(jobs)} runs", flush=True)
    env = environments.load(category)
    by, at = {}, 0
    for s in seeds:
        for k in measured:
            r = records[at]
            at += 1
            assert r["key"] == key_of({"env": category, "version": versions[k], "seed": s, "budget": budget})
            part_a, part_b = halves(env, r["fresh_ids"])
            where = {i: n for n, i in enumerate(r["fresh_ids"])}
            mean = lambda scores, ids: float(np.mean([scores[where[i]] for i in ids]))
            by[(s, k)] = {"untrained": r["untrained"], "acquired": r["acquired"],
                          "untrained_a": mean(r["fresh_untrained"], part_a), "acquired_a": mean(r["fresh_acquired"], part_a),
                          "untrained_b": mean(r["fresh_untrained"], part_b), "acquired_b": mean(r["fresh_acquired"], part_b),
                          "cpu": r["cpu"]["acquire"] + r["cpu"]["apply"], "learned": bool(r["report"].get("learned")),
                          "rounds": int(r["report"].get("iterations", 0)),
                          "used": r["units"]["train_used"] / max(r["units"]["train_limit"], 1e-9)}
    names = ("untrained", "acquired", "untrained_a", "acquired_a", "untrained_b", "acquired_b", "cpu", "learned", "rounds", "used")
    same_as = [first[design_s.behaviour(v)] for v in versions]
    out = {"what": "development: every mechanism of design s on one category of the pool",
           "category": category, "seeds": seeds, "budget": budget, "smoke": bool(args.smoke),
           "fields": list(design_s.MECHANISM), "levels": {f: list(design_s.LEVELS[f]) for f in design_s.MECHANISM},
           "versions": [designs.digest(v) for v in versions], "index": [list(design_s.index_of(v)) for v in versions],
           "measured_as": same_as,
           "machine": {"python": sys.version.split()[0], "numpy": np.__version__, "cpus": os.cpu_count(),
                       "platform": platform.platform(), "processor": _processor()},
           "table": {name: [[by[(s, same_as[k])][name] for k in range(len(versions))] for s in seeds] for name in names}}
    json.dump(out, open(os.path.join(args.out, stem + ".json"), "w"))
    with open(os.path.join(args.out, stem + ".records.jsonl"), "w") as handle:
        for r in ledger.records[before:]:
            handle.write(json.dumps(r, sort_keys=True) + "\n")
    os.remove(scratch)                                             # the copy of the committed ledger is not part of what is kept
    acquired = np.array(out["table"]["acquired"]).mean(axis=0)
    order = np.argsort(-acquired)
    show = lambda k: " ".join(f"{f.split('.')[1]}={versions[k][f]}" for f in design_s.MECHANISM)
    print(f"{category}: {len(measured)} mechanisms measured for {len(versions)} versions, {len(seeds)} seeds")
    for k in list(order[:5]) + list(order[-3:]):
        print(f"  {acquired[k]:.4f}  {show(k)}")
    return 0


def _processor() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


if __name__ == "__main__":
    sys.exit(main())
