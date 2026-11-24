"""Self-modification of design t: the learner's own acquisitions, one level up.

An acquisition tries programs on the training problems of one category and builds a capability
from them, each member chosen for the problems it adds (``design_t.build``). ``improve`` does
the same over categories. Its candidates are the programs the learner's acquisitions on the
categories it may use came out with (the best ``PER_RUN`` of each run) and the programs
already in the library. Every candidate is run on the training problems of every such category
(``cross``), and the next library is grown one program at a time, each chosen for the
categories it adds (``cover``): the library is to categories what a capability is to problems.

What a step is made from is what a learner found. So which learner made the runs matters, and
the arms of a chain differ only in that:

``recursive``  the candidates come from the runs of the current version;
``frozen``     from the runs of generation 0, whatever has been adopted since;
``shuffled``   from the runs of the current version, but as many programs drawn at random
               from all it tried, not its best (what a step is worth without the learner's
               own ranking).

Every arm starts from the same version (its library is among the candidates of each), reads
the same categories with the same seeds, and makes one nominee; a nominee replaces the version
only through the gate, on categories none of this read.

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
PER_RUN = 2                                    # programs a run offers as candidates


def offered(trace, rng=None) -> list:
    """The programs a run offers: its best ``PER_RUN`` by its own ranking, or, with ``rng``, as many drawn at
    random from all it tried."""
    n = min(PER_RUN, len(trace))
    if rng is not None:
        return [trace[int(i)][0] for i in rng.choice(len(trace), size=n, replace=False)]
    return [row[0] for row in sorted(trace, key=lambda row: -row[1])[:n]]


def cross(programs, kind: str, n_train: int = 16, seed: int = 0):
    """How every program does on the training problems of a category: its mean skill, and the passes spent."""
    from rsi6 import environments
    from rsi6.kernel.environment import split
    from rsi6.kernel.problem import Meter
    env = environments.load(kind)
    train_ids, _ = split(env, n_train, 24)
    problems = [env.problem(i, Meter(float("inf")), seed, True)[0] for i in train_ids]
    scales = [design_t.spread(P.ctx_y) for P in problems]
    out, spent = [], 0.0
    for program in programs:
        total = 0.0
        for P, scale in zip(problems, scales):
            try:
                answer = design_t.run(program, P.ctx_x, P.ctx_y, P.qry_x, backtest=False)[2]
            except (np.linalg.LinAlgError, FloatingPointError, ValueError, ZeroDivisionError):
                answer = None
            total += design_t.skill(answer, P.qry_y, scale)
            spent += design_t.passes(program, backtest=False)
        out.append(total / len(problems))
    return out, spent


def cover(scores, slots: int) -> list:
    """Grow a library from candidates: ``scores[c][k]`` is how candidate ``c`` does on category ``k``. Within a
    category the candidates are put on one scale (their rank, from 0 to 1). The library's value is the mean over
    categories of its best member there; each step adds the candidate that raises it most (the earliest of
    equals); when none raises it, the best remaining candidate on average. Returns candidate indices in order."""
    scores = np.asarray(scores, dtype=float)
    n = len(scores)
    if n == 0:
        return []
    ranks = np.zeros_like(scores)
    for k in range(scores.shape[1]):
        order = np.argsort(np.argsort(scores[:, k], kind="stable"), kind="stable")
        ranks[:, k] = order / max(n - 1, 1)
        for value in np.unique(scores[:, k]):                       # equal scores share a rank
            same = scores[:, k] == value
            ranks[same, k] = ranks[same, k].mean()
    chosen, best = [], np.full(scores.shape[1], -1.0)
    while len(chosen) < min(slots, n):
        gains = [(np.maximum(best, ranks[c]).mean() - best.mean() if c not in chosen else -np.inf) for c in range(n)]
        c = int(np.argmax(gains))
        if gains[c] <= 1e-12:
            rest = [(ranks[i].mean(), -i) for i in range(n) if i not in chosen]
            c = -max(rest)[1]
        chosen.append(c)
        best = np.maximum(best, ranks[c])
    return chosen


def improve(version: dict, records, rng=None) -> tuple:
    """The version one step on, and what the step read. ``records`` are runs (``env`` and ``report.trace``) of a
    learner on the categories the improver may use. Per form: the candidates are the version's library and what
    the runs offer; every candidate is run on every category of that form among the records; the new library
    is ``cover`` of those scores. A form with no runs keeps its library."""
    out, detail = copy.deepcopy(version), {}
    slots = int(version["search"]["slots"])
    for form in design_t.FORMS:
        by_kind = {}
        for record in records:
            trace = record["report"].get("trace") or []
            if trace and trace[0][0]["form"] == form[0]:
                by_kind.setdefault(record["env"], []).append(trace)
        if not by_kind:
            continue
        candidates, seen = [], set()
        for program in list(version["library"][form]) + [p for kind in sorted(by_kind) for trace in by_kind[kind] for p in offered(trace, rng)]:
            key = json.dumps(program, sort_keys=True)
            if key not in seen:
                seen.add(key)
                candidates.append(program)
        kinds_ = sorted(by_kind)
        table, passes = [], 0.0
        for kind in kinds_:
            column, spent = cross(candidates, kind)
            table.append(column)
            passes += spent
        scores = np.array(table).T
        chosen = cover(scores, slots)
        out["library"][form] = [candidates[c] for c in chosen]
        detail[form] = {"categories": kinds_, "candidates": len(candidates), "from_library": len(version["library"][form]),
                        "kept_from_library": sum(1 for c in chosen if c < len(version["library"][form])), "passes": passes,
                        "scores_of_chosen": [[round(float(x), 5) for x in scores[c]] for c in chosen]}
    return design_t.validate(out), detail


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

    def __init__(self, budget: dict, workers: int = 2):
        self.done, self.workers, self.budget = {}, workers, dict(budget)

    def get(self, version, kinds_, seeds):
        d = design_t.digest(version)
        todo = [(k, s) for k in kinds_ for s in seeds if (d, k, s) not in self.done]
        if todo:
            jobs = [{"env": k, "version": version, "seed": s, "budget": dict(self.budget), "purpose": "dev-t"} for k, s in todo]
            with multiprocessing.get_context("fork").Pool(self.workers) as pool:
                for (k, s), row in zip(todo, pool.map(_measure, jobs, chunksize=1)):
                    self.done[(d, k, s)] = row
        return [self.done[(d, k, s)] for k in kinds_ for s in seeds]


def loko(kinds_, trace_seeds, eval_seeds, out, workers=2, train=40.0, generations=2):
    """For every kind as the one left out: generation 1 made from the runs of generation 0 on the other kinds of
    its form, then further steps by each arm, every version measured on the kind left out."""
    from rsi6 import environments
    from rsi6.environments import kinds as kinds_module
    design_t.install()
    kinds_module.install()
    runs, v0 = Runs(dict(BUDGET, train=train), workers), design_t.default()
    form_of = {k: ("ordered" if environments.load(k).problem(environments.load(k).instance_ids()[0], None, 0, False)[0].ordered
                   else "unordered") for k in kinds_}
    seeds_e = list(range(745001, 745001 + eval_seeds))
    result = {"kinds": list(kinds_), "train": train, "eval_seeds": seeds_e, "targets": {}}
    names = ["generation 0", "generation 1"] + [f"{arm} {g}" for g in range(2, generations + 1) for arm in ARMS]
    for target in kinds_:
        others = [k for k in kinds_ if k != target and form_of[k] == form_of[target]]
        seeds = lambda g: list(range(741001 + 1000 * (g - 1), 741001 + 1000 * (g - 1) + trace_seeds))
        v1, _ = improve(v0, runs.get(v0, others, seeds(1)))
        versions, current = {"generation 0": v0, "generation 1": v1}, {arm: v1 for arm in ARMS}
        for g in range(2, generations + 1):
            step = {"recursive": improve(current["recursive"], runs.get(current["recursive"], others, seeds(g)))[0],
                    "frozen": improve(current["frozen"], runs.get(v0, others, seeds(g)))[0],
                    "shuffled": improve(current["shuffled"], runs.get(current["shuffled"], others, seeds(g)),
                                        np.random.default_rng(746000 + g))[0]}
            for arm in ARMS:                                   # in development every step is taken: there is no gate here
                current[arm] = step[arm]
                versions[f"{arm} {g}"] = step[arm]
        rows = {name: runs.get(v, [target], seeds_e) for name, v in versions.items()}
        scores = {name: [r["acquired"] for r in rows[name]] for name in versions}
        result["targets"][target] = {"others": others, "untrained": rows["generation 0"][0]["untrained"], "acquired": scores,
                                     "kept": {name: float(np.mean([bool(r["report"].get("learned")) for r in rows[name]])) for name in versions},
                                     "from_library": {name: float(np.mean([r["report"].get("from_library", 0) for r in rows[name]])) for name in versions},
                                     "libraries": {name: v["library"][form_of[target]] for name, v in versions.items()}}
        a = {name: np.array(x) for name, x in scores.items()}
        print(f"{target:11s} untrained {rows['generation 0'][0]['untrained']:.4f} | " + " | ".join(f"{name} {a[name].mean():.4f}" for name in names), flush=True)
        pairs = [("generation 1", "generation 0")] + [(f"recursive {g}", y) for g in range(2, generations + 1)
                                                      for y in (f"generation 1" if g == 2 else f"recursive {g - 1}", f"frozen {g}", f"shuffled {g}")]
        print("            " + " ; ".join(f"{x} - {y}: {(a[x] - a[y]).mean():+.4f} ({(a[x] - a[y]).std(ddof=1) / np.sqrt(len(a[x])):.4f})" for x, y in pairs), flush=True)
        os.makedirs(out, exist_ok=True)
        json.dump(result, open(os.path.join(out, "loko.json"), "w"))
    means = {n: np.mean([np.mean(result["targets"][t]["acquired"][n]) for t in kinds_]) for n in names}
    print("mean over the kinds left out: " + " | ".join(f"{n} {means[n]:.4f}" for n in names))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("loko")
    cmd.add_argument("--kinds", nargs="+", required=True)
    cmd.add_argument("--trace-seeds", type=int, default=8)
    cmd.add_argument("--eval-seeds", type=int, default=32)
    cmd.add_argument("--workers", type=int, default=2)
    cmd.add_argument("--train", type=float, default=40.0)
    cmd.add_argument("--generations", type=int, default=2)
    cmd.add_argument("--out", required=True)
    args = parser.parse_args()
    loko(args.kinds, args.trace_seeds, args.eval_seeds, args.out, args.workers, args.train, args.generations)
    return 0


if __name__ == "__main__":
    sys.exit(main())
