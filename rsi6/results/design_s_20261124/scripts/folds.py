"""The chains of PREDICTION.md on a directory of tables: four folds, then the reading.

    python scripts/folds.py TABLES OUT [--workers 2] [--reps 30] [--boot 2000]

Every category of the table is a test category in one fold, a gate category in one and a
discovery category in two. Writes OUT/chains_<k>.json, OUT/quality_<k>.json and OUT/reading.json.
Run from the repository root (it imports the package).
"""
import argparse
import json
import multiprocessing
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..")))
from rsi6.meta import chain_s  # noqa: E402

PAIRS = [["quadassign", "quadratic"], ["pmedian", "tardiness"], ["binpacking", "clique"], ["jobshop", "knapsack"]]
FOLDS = [{"test": PAIRS[k], "gate": PAIRS[(k + 1) % 4], "discovery": PAIRS[(k + 2) % 4] + PAIRS[(k + 3) % 4]} for k in range(4)]
GENERATIONS, SEED, TRAIN = 4, 1, 40.0
QUALITY = {"incumbents": 40, "reps": 6, "seed": 2}


def one(job):
    directory, out, k, what, reps = job
    tables, fold = chain_s.Tables(directory), FOLDS[k]
    if what == "chains":
        result = chain_s.simulate(tables, fold["discovery"], fold["gate"], range(len(tables.versions)), reps, GENERATIONS, SEED,
                                  train=TRAIN)
    else:
        rng = np.random.default_rng([QUALITY["seed"], 0])
        incumbents = sorted(int(x) for x in rng.choice(len(tables.versions), size=QUALITY["incumbents"], replace=False))
        after = chain_s.quality(tables, fold["discovery"], fold["gate"], incumbents, QUALITY["reps"], QUALITY["seed"], train=TRAIN)
        result = {"discovery": fold["discovery"], "gate": fold["gate"], "incumbents": incumbents, "reps": QUALITY["reps"],
                  "seed": QUALITY["seed"], "train": TRAIN, "after": after.tolist()}
    result["test"] = fold["test"]
    result["seeds"] = {c: tables.cats[c]["seeds"] for c in sorted(tables.cats)}
    json.dump(result, open(os.path.join(out, f"{what}_{k + 1}.json"), "w"))
    return f"{what} of fold {k + 1}: test {fold['test']}, gate {fold['gate']}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tables")
    parser.add_argument("out")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--reps", type=int, default=30)
    parser.add_argument("--boot", type=int, default=2000)
    parser.add_argument("--no-quality", action="store_true")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    kinds = ["chains"] if args.no_quality else ["chains", "quality"]
    jobs = [(args.tables, args.out, k, what, args.reps) for what in kinds for k in range(4)
            if not os.path.exists(os.path.join(args.out, f"{what}_{k + 1}.json"))]
    with multiprocessing.get_context("fork").Pool(args.workers) as pool:
        for line in pool.imap_unordered(one, jobs, chunksize=1):
            print(line, flush=True)
    tables, folds = chain_s.Tables(args.tables), []
    for k in range(4):
        result = json.load(open(os.path.join(args.out, f"chains_{k + 1}.json")))
        fold = {"result": result, "test": result["test"]}
        if not args.no_quality:
            q = json.load(open(os.path.join(args.out, f"quality_{k + 1}.json")))
            fold.update(after=q["after"], incumbents=q["incumbents"])
        folds.append(fold)
    reading = chain_s.read(tables, folds, boot=args.boot)
    json.dump(reading, open(os.path.join(args.out, "reading.json"), "w"), indent=1)
    last = lambda row: f"mean {row['mean'][-1]:+.5f}  5 % point {row['q05'][-1]:+.5f}  95 % point {row['q95'][-1]:+.5f}"
    print(f"\nmean of {reading['folds']} folds, generation {reading['generations']}, {reading['starts']} starts x {reading['reps']} repetitions")
    for name, row in reading["statistics"].items():
        print(f"  {name:36s} {last(row)}")
    for k, fold in enumerate(reading["per_fold"]):
        s = fold["statistics"]
        print(f"fold {k + 1} test {fold['test']}: recursive {last(s['recursive'])} | recursive-frozen {last(s['recursive-frozen'])}")


if __name__ == "__main__":
    main()
