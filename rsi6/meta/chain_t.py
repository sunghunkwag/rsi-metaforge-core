"""Self-modification of design t: the learner applied to itself.

A step (``improve``) makes the next version from runs of a learner on the categories the
improver may use:

* the library: the candidates are the programs those runs ended on (the best ``PER_RUN`` of
  each) and the programs already in the library; every candidate is run on the training
  problems of every such category (``cross``), and the next library is grown one program at a
  time, each chosen for the categories it adds (``cover``);
* the memory: the programs the runs tried, with their skill where they were tried;
* the model of its own programs: one acquisition by a learner on the prediction problems made
  from that memory (``design_t.self_model``).

Which learner made the runs and the model is what the arms of a chain differ in:

``recursive``  the runs and the model are the current version's;
``frozen``     generation 0's, whatever has been adopted since;
``shuffled``   the current version's, but the runs offer programs at random instead of their
               best, and the remembered skills are shuffled before the model is acquired (what
               a step is worth without the learner's own ranking).

Every arm starts from the same version, reads the same categories with the same seeds, and
makes one nominee; a nominee replaces the version only through the gate, on categories none of
this read. The development readings (one kind left out, no gate) are in
``rsi6/results/design_t_20261124/README.md``.

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


def remembered(records, form: str) -> list:
    """What the runs tried, as rows ``[program, skill, category]`` (a program tried in several runs of one
    category: its mean skill there)."""
    by_kind = {}
    for record in records:
        trace = record["report"].get("trace") or []
        if trace and trace[0][0]["form"] == form[0]:
            seen = by_kind.setdefault(record["env"], {})
            for program, value, _ in trace:
                seen.setdefault(json.dumps(program, sort_keys=True), [program, []])[1].append(float(value))
    return [[program, float(np.clip(np.mean(vals), -1.0, 1.0)), kind] for kind in sorted(by_kind) for program, vals in by_kind[kind].values()]


def improve(version: dict, records, maker=None, rng=None, train: float = 12.0, seed: int = 0) -> tuple:
    """The version one step on, and what the step read. ``records`` are runs (``env`` and ``report.trace``) of a
    learner on the categories the improver may use; ``maker`` is the learner that acquires the next model (the
    version itself when not given). Per form:

    * the library: the candidates are the version's library and what the runs offer; every candidate is run on
      every category of that form among the records; the new library is ``cover`` of those scores;
    * what is remembered: the programs the runs tried, with their skill where they were tried, added to what
      the version remembered (a random ``KNOWN_AT_MOST`` of them when there are more);
    * the model: one acquisition by ``maker`` on the problems made from what is remembered
      (``design_t.self_model``).

    With ``rng`` (the control without the learner's own ranking) the runs offer programs at random and the
    skills of the remembered programs are shuffled among them before the model is acquired. A form with no
    runs keeps everything."""
    out, detail = copy.deepcopy(version), {}
    maker = version if maker is None else maker
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
        local = np.random.default_rng([seed, design_t.FORMS.index(form), 753])
        rows = [list(row) for row in version["known"][form]] + remembered(records, form)
        if len(rows) > design_t.KNOWN_AT_MOST:
            rows = [rows[int(i)] for i in sorted(local.choice(len(rows), size=design_t.KNOWN_AT_MOST, replace=False))]
        if rng is not None:
            mixed = local.permutation(len(rows))
            rows = [[row[0], rows[int(j)][1], row[2]] for row, j in zip(rows, mixed)]
        out["known"][form] = rows
        model, report = design_t.self_model(maker, rows, local, train)
        out["model"][form] = model
        detail[form] = {"categories": kinds_, "candidates": len(candidates), "from_library": len(version["library"][form]),
                        "kept_from_library": sum(1 for c in chosen if c < len(version["library"][form])), "passes": passes,
                        "scores_of_chosen": [[round(float(x), 5) for x in scores[c]] for c in chosen],
                        "remembered": len(rows), "model": None if model is None else {"rule": model["rule"], "programs": len(model["programs"])},
                        "model_units": report.get("used"), "model_fit_skill": report.get("fit_skill")}
    return design_t.validate(out), detail


def foresight(version: dict, rows) -> dict:
    """How well a version's model says how programs do in a place it has no memory of: ``rows`` are programs
    with their skill there. Per form: the rank correlation between what the model predicts and the skill."""
    from rsi6.kernel.problem import PredictProblem
    out = {}
    for form in design_t.FORMS:
        mine = [row for row in rows if row[0]["form"] == form[0]]
        model, known = version["model"][form], version["known"][form]
        if model is None or len(mine) < 8 or len(known) < 8:
            continue
        P = PredictProblem([design_t.features(r[0]) for r in known], design_t.values(known), [design_t.features(r[0]) for r in mine], False)
        predicted = design_t.LearnerT(version).apply({"kind": "predict", "design": "t", "rule": model["rule"], "programs": model["programs"],
                                                      "learned": True}, P)
        a = np.argsort(np.argsort(predicted)).astype(float)
        b = np.argsort(np.argsort([r[1] for r in mine])).astype(float)
        out[form] = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 0.0
    return out


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


def loko(kinds_, trace_seeds, eval_seeds, out, workers=2, train=12.0, generations=3):
    """For every kind as the one left out: generation 1 made from the runs of generation 0 on the other kinds of
    its form, then further steps by each arm, every version measured on the kind left out. Two more versions
    say what each part of generation 1 is worth: its library alone and its model alone."""
    from rsi6 import environments
    from rsi6.environments import kinds as kinds_module
    design_t.install()
    kinds_module.install()
    runs, v0 = Runs(dict(BUDGET, train=train), workers), design_t.default()
    form_of = {k: ("ordered" if environments.load(k).problem(environments.load(k).instance_ids()[0], None, 0, False)[0].ordered
                   else "unordered") for k in kinds_}
    seeds_e = list(range(745001, 745001 + eval_seeds))
    result = {"kinds": list(kinds_), "train": train, "eval_seeds": seeds_e, "targets": {}}
    names = ["generation 0", "generation 1", "library only", "model only"] + [f"{arm} {g}" for g in range(2, generations + 1) for arm in ARMS]
    for target in kinds_:
        others = [k for k in kinds_ if k != target and form_of[k] == form_of[target]]
        seeds = lambda g: list(range(741001 + 1000 * (g - 1), 741001 + 1000 * (g - 1) + trace_seeds))
        v1, _ = improve(v0, runs.get(v0, others, seeds(1)), maker=v0, train=train, seed=1)
        bare = dict(copy.deepcopy(v1), known={f: [] for f in design_t.FORMS}, model={f: None for f in design_t.FORMS})
        versions = {"generation 0": v0, "generation 1": v1, "library only": bare,
                    "model only": dict(copy.deepcopy(v1), library={f: [] for f in design_t.FORMS})}
        current = {arm: v1 for arm in ARMS}
        for g in range(2, generations + 1):
            step = {"recursive": improve(current["recursive"], runs.get(current["recursive"], others, seeds(g)), train=train, seed=g)[0],
                    "frozen": improve(current["frozen"], runs.get(v0, others, seeds(g)), maker=v0, train=train, seed=g)[0],
                    "shuffled": improve(current["shuffled"], runs.get(current["shuffled"], others, seeds(g)),
                                        rng=np.random.default_rng(746000 + g), train=train, seed=g)[0]}
            for arm in ARMS:                                   # in development every step is taken: there is no gate here
                current[arm] = step[arm]
                versions[f"{arm} {g}"] = step[arm]
        rows = {name: runs.get(v, [target], seeds_e) for name, v in versions.items()}
        scores = {name: [r["acquired"] for r in rows[name]] for name in versions}
        there = remembered(rows["generation 0"], form_of[target])              # what generation 0 tried on the kind left out
        sight = {name: foresight(v, there).get(form_of[target]) for name, v in versions.items()}
        result["targets"][target] = {"others": others, "untrained": rows["generation 0"][0]["untrained"], "acquired": scores,
                                     "kept": {name: float(np.mean([bool(r["report"].get("learned")) for r in rows[name]])) for name in versions},
                                     "from_library": {name: float(np.mean([r["report"].get("from_library", 0) for r in rows[name]])) for name in versions},
                                     "foresight": sight,
                                     "cpu": {name: float(np.mean([r["cpu"] for r in rows[name]])) for name in versions},
                                     "libraries": {name: v["library"][form_of[target]] for name, v in versions.items()},
                                     "models": {name: v["model"][form_of[target]] for name, v in versions.items()}}
        a = {name: np.array(x) for name, x in scores.items()}
        print(f"{target:11s} untrained {rows['generation 0'][0]['untrained']:.4f} | " + " | ".join(f"{name} {a[name].mean():.4f}" for name in names), flush=True)
        pairs = [("generation 1", "generation 0"), ("library only", "generation 0"), ("model only", "generation 0")] \
            + [(f"recursive {g}", y) for g in range(2, generations + 1) for y in ("generation 0", f"frozen {g}", f"shuffled {g}")]
        print("            " + " ; ".join(f"{x} - {y}: {(a[x] - a[y]).mean():+.4f} ({(a[x] - a[y]).std(ddof=1) / np.sqrt(len(a[x])):.4f})" for x, y in pairs), flush=True)
        print("            foresight: " + " | ".join(f"{name} {sight[name]:+.3f}" for name in names if sight.get(name) is not None), flush=True)
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
    cmd.add_argument("--train", type=float, default=12.0)
    cmd.add_argument("--generations", type=int, default=3)
    cmd.add_argument("--out", required=True)
    args = parser.parse_args()
    loko(args.kinds, args.trace_seeds, args.eval_seeds, args.out, args.workers, args.train, args.generations)
    return 0


if __name__ == "__main__":
    sys.exit(main())
