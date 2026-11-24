"""Development: every way to search of design v, on the training problems of one kind.

    python -m rsi6.experiments.dev_ways KIND --out DIR [--trials 2] [--slice 3.0] [--e 0] [--problems 16] [--workers 4]

For each of the 729 ways (``design_v.ways``) and each training problem of the kind: ``trials``
searches, each allowed ``slice`` constructions of units and ``e`` units per pair of variables
(``--slice 2 --e 1`` is what a fresh problem gets under the budget of the registrations). Written
to ``DIR/ways_<kind>.json``: the cost each search ended on (hard totals, objective), the units
it used, and the score of its assignment. The score is read on *training* instances only, to
say in the benchmark's own terms what a way is worth; no learner sees it and no fresh instance
is opened. Development: scratch output, nothing here is evidence.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6.learner import design_v

_STATE = {}


def _load(kind: str, n_problems: int):
    from rsi6 import environments
    from rsi6.environments import fresh
    from rsi6.kernel.environment import split
    fresh.install()
    env = environments.load(kind)
    train_ids, _ = split(env, n_problems, 24)
    return env, list(train_ids)


def _one(job):
    way_index, trials, slice_, per_pair = job
    from rsi6.kernel.problem import Meter
    env, ids, ways = _STATE["env"], _STATE["ids"], _STATE["ways"]
    out = []
    for j, i in enumerate(ids):
        row = []
        for t in range(trials):
            P, decode = env.problem(i, Meter(0.0), 0, True)
            P.meter.limit = slice_ * P.construction_units() + per_pair * P.n_vars * P.n_vars
            rng = np.random.default_rng([760000 + t, j, way_index])
            best, c, _ = design_v.search(P, ways[way_index], rng)
            if best is None:
                row.append([None, None, P.meter.used, 0.0])
            else:
                row.append([c[0], c[1], P.meter.used, float(env.score(i, decode(best))) if P.well_formed(best) else 0.0])
        out.append(row)
    return way_index, out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind")
    parser.add_argument("--out", required=True)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--slice", type=float, default=design_v.SLICE)
    parser.add_argument("--e", type=float, default=0.0, help="units per pair of variables added to a trial (the test budget is slice 2, e 1)")
    parser.add_argument("--problems", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--first", type=int, default=0)
    parser.add_argument("--count", type=int, default=0)
    args = parser.parse_args()
    env, ids = _load(args.kind, args.problems)
    ways = design_v.ways()
    _STATE.update(env=env, ids=ids, ways=ways)
    chosen = list(range(len(ways)))[args.first:args.first + args.count if args.count else None]
    started = time.time()
    with multiprocessing.get_context("fork").Pool(args.workers) as pool:
        rows = dict(pool.imap_unordered(_one, [(w, args.trials, args.slice, args.e) for w in chosen], chunksize=4))
    os.makedirs(args.out, exist_ok=True)
    name = f"ways_{args.kind}" + (f"_{args.first}" if args.count else "") + ".json"
    json.dump({"kind": args.kind, "slice": args.slice, "e": args.e, "trials": args.trials, "problems": ids, "ways": [ways[w] for w in chosen],
               "index": chosen, "results": [rows[w] for w in chosen], "seconds": round(time.time() - started, 1)},
              open(os.path.join(args.out, name), "w"))
    score = np.array([[[t[3] for t in problem] for problem in rows[w]] for w in chosen]).mean(axis=(1, 2))
    print(f"{args.kind}: {len(chosen)} ways x {len(ids)} problems x {args.trials} trials in {time.time() - started:.0f}s | score: "
          f"own way {score[chosen.index(ways.index(design_v.MECH))] if ways.index(design_v.MECH) in chosen else float('nan'):.4f} "
          f"median {np.median(score):.4f} best {score.max():.4f} worst {score.min():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
