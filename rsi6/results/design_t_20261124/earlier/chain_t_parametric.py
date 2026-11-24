"""Self-modification of design t: the learner's own operation, one level up.

Inside an acquisition the learner draws programs from its proposal, runs them, and moves the
proposal towards the programs that did best (``design_t.fit`` and ``design_t.mix``, with the
share kept and the rate of the version's ``search`` settings). ``improve`` is the same step
taken over acquisitions instead of inside one: from the runs of a learner on the categories it
may use, the programs each acquisition kept as its best are pooled, every category counting the
same, and the proposal the version starts from is moved towards them at the same rate.

What the step is made from is what a learner tried and how it ranked it. So which learner made
the runs matters, and the arms of a chain differ only in that:

``recursive``  the runs are those of the current version;
``frozen``     the runs are those of generation 0, whatever has been adopted since;
``shuffled``   the runs are those of the current version, but the programs kept from each are
               drawn at random from what it tried, not its best (what a step is worth when the
               learner's own ranking is thrown away).

Every arm starts from the same version, uses the same categories and seeds, and makes one
nominee; a nominee replaces the version only through the gate, on categories none of this read.

    python -m rsi6.meta.chain_t loko --kinds regression friedman table binary --out DIR      # development
"""
from __future__ import annotations

import argparse
import copy
import json
import multiprocessing
import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6.learner import design_t

ARMS = ("recursive", "frozen", "shuffled")
BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}    # the run budget of the registrations


def kept(trace, share, rng=None) -> list:
    """The programs an acquisition leaves as evidence: its best ``share`` (at least two), or, with ``rng``, as
    many drawn at random from all it tried."""
    n = min(len(trace), max(2, int(round(share * len(trace)))))
    if rng is not None:
        return [trace[int(i)][0] for i in rng.choice(len(trace), size=n, replace=False)]
    return [row[0] for row in sorted(trace, key=lambda row: -row[1])[:n]]


def improve(version: dict, records, rng=None) -> dict:
    """The version one step on: its proposal moved towards the programs kept from the given runs.

    ``records`` are run records (or anything with ``env`` and ``report.trace``) of acquisitions on the
    categories the improver may read. Every category counts the same, every run of a category the same, every
    program kept from a run the same. A form no run has leaves its part of the proposal as it is."""
    search = version["search"]
    out = copy.deepcopy(version)
    for form in ("unordered", "ordered"):
        by_kind = {}
        for record in records:
            trace = record["report"].get("trace") or []
            if trace and trace[0][0]["form"] == form[0]:
                by_kind.setdefault(record["env"], []).append(trace)
        programs, weights = [], []
        for kind in sorted(by_kind):
            for trace in by_kind[kind]:
                chosen = kept(trace, search["elite"], rng)
                programs += chosen
                weights += [1.0 / (len(chosen) * len(by_kind[kind]) * len(by_kind))] * len(chosen)
        if programs:
            out["proposal"][form] = design_t.mix(version["proposal"][form], design_t.fit(programs, weights, form), search["adapt"])
    return design_t.validate(out)


# ---- development: leave one kind out -------------------------------------------------------------
def _measure(job):
    from rsi6.environments import kinds
    from rsi6.kernel.run import measure
    design_t.install()
    kinds.install()
    r = measure(job)["record"]
    return {"env": r["env"], "seed": r["seed"], "version": r["version"], "untrained": r["untrained"], "acquired": r["acquired"],
            "gain": r["gain"], "cpu": r["cpu"]["acquire"] + r["cpu"]["apply"], "report": r["report"]}


class Runs:
    """Runs by (version, category, seed), measured once."""

    def __init__(self, workers: int = 2):
        self.done, self.workers = {}, workers

    def get(self, version, kinds_, seeds):
        d = design_t.digest(version)
        todo = [(k, s) for k in kinds_ for s in seeds if (d, k, s) not in self.done]
        if todo:
            jobs = [{"env": k, "version": version, "seed": s, "budget": dict(BUDGET), "purpose": "dev-t"} for k, s in todo]
            with multiprocessing.get_context("fork").Pool(self.workers) as pool:
                for (k, s), row in zip(todo, pool.map(_measure, jobs, chunksize=1)):
                    self.done[(d, k, s)] = row
        return [self.done[(d, k, s)] for k in kinds_ for s in seeds]


def loko(kinds_, trace_seeds, eval_seeds, out, workers=2):
    """For every kind as the one left out: generation 1 made from the runs of generation 0 on the other kinds,
    then a second step by each arm, all four versions measured on the kind left out."""
    runs, v0 = Runs(workers), design_t.default()
    seeds_1 = list(range(741001, 741001 + trace_seeds))
    seeds_2 = list(range(742001, 742001 + trace_seeds))
    seeds_e = list(range(745001, 745001 + eval_seeds))
    result = {"kinds": list(kinds_), "trace_seeds": [seeds_1, seeds_2], "eval_seeds": seeds_e, "targets": {}}
    for target in kinds_:
        others = [k for k in kinds_ if k != target]
        v1 = improve(v0, runs.get(v0, others, seeds_1))
        versions = {"generation 0": v0, "generation 1": v1,
                    "recursive": improve(v1, runs.get(v1, others, seeds_2)),
                    "frozen": improve(v1, runs.get(v0, others, seeds_2)),
                    "shuffled": improve(v1, runs.get(v1, others, seeds_2), np.random.default_rng(746001))}
        scores = {name: [r["acquired"] for r in runs.get(v, [target], seeds_e)] for name, v in versions.items()}
        kept_share = {name: float(np.mean([bool(r["report"].get("learned")) for r in runs.get(v, [target], seeds_e)]))
                      for name, v in versions.items()}
        untrained = runs.get(v0, [target], seeds_e)[0]["untrained"]
        result["targets"][target] = {"others": others, "untrained": untrained, "acquired": scores, "kept": kept_share,
                                     "versions": {name: design_t.digest(v) for name, v in versions.items()},
                                     "proposals": {name: v["proposal"] for name, v in versions.items()}}
        a = {name: np.array(x) for name, x in scores.items()}
        line = " | ".join(f"{name} {a[name].mean():.4f}" for name in versions)
        print(f"{target:11s} untrained {untrained:.4f} | {line}", flush=True)
        for x, y in (("generation 1", "generation 0"), ("recursive", "generation 1"), ("recursive", "frozen"), ("recursive", "shuffled")):
            d = a[x] - a[y]
            print(f"            {x} - {y}: {d.mean():+.4f} (se {d.std(ddof=1) / np.sqrt(len(d)):.4f})", flush=True)
        os.makedirs(out, exist_ok=True)
        json.dump(result, open(os.path.join(out, "loko.json"), "w"))
    names = ("generation 0", "generation 1", "recursive", "frozen", "shuffled")
    means = {n: np.mean([np.mean(result["targets"][t]["acquired"][n]) for t in kinds_]) for n in names}
    print("mean over the kinds left out: " + " | ".join(f"{n} {means[n]:.4f}" for n in names))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("loko")
    cmd.add_argument("--kinds", nargs="+", required=True)
    cmd.add_argument("--trace-seeds", type=int, default=12)
    cmd.add_argument("--eval-seeds", type=int, default=32)
    cmd.add_argument("--workers", type=int, default=2)
    cmd.add_argument("--out", required=True)
    args = parser.parse_args()
    loko(args.kinds, args.trace_seeds, args.eval_seeds, args.out, args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
