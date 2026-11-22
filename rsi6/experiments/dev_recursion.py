"""Development: is the changed learner a better improver of the learner?

Development only: categories of the source pool, a scratch ledger, seeds no other run uses.
Nothing here is evidence.

Why this module exists. In the first design the learner improves a version by local changes of
a known answer (``meta/rounds.search``): only its fields ``edit.*`` take part. The one change
that held on new seeds (``model.batch`` 2, ``results/dev_landscape_20261122``) is on the other
side, in how the learner acquires, so as an improver that learner is generation 0 exactly, and
the recursion check of amendment 4 could only ever report "no difference". The second half of
the hypothesis ("the modified mechanism is also better at producing the next modification") has
an answer only if the improver runs on the part of the learner that was modified.

What it does. The improver here is the learner's acquisition loop applied to the space of
versions: a transcription of the population search of ``Learner._acquire_assign`` (the same
fields ``model.pop``, ``model.batch``, ``model.elite``, ``model.sigma``, ``model.decay``,
``model.keep_best``, ``assess.holdback``, ``assess.strict``, the same order of random draws, the
learner's own ``_fitness``), in which

* a candidate is a point in the space of versions (one real coordinate per field, in units of
  the field's grid of ``meta/space.py``, rounded to the nearest grid value), drawn around the
  current mean with the learner's ``model.sigma`` times ``SCALE``;
* a training problem is a pair (category, seed), and rolling a candidate out on it is one
  measured acquisition run at the search budget of the registrations; its value is the smaller
  of the changes of the acquired score and of the gain against the start version on the same
  pair, and a candidate whose runs cost more than 1.25 times the start's CPU gets the worst
  value (the registered search rule);
* the budget is counted as the learner counts its own: ``TRAIN`` (40) times the cost of all
  problems, every rollout of every candidate charged, three checks held in reserve; the cost of
  a problem is a fixed number per category (the mean CPU-seconds of a run in the registered
  ledger), so that every arm gets the same budget on every machine;
* at the end the learned version meets the start on the held-back problems and is kept only if
  it wins there (``assess.strict``), exactly as the learner keeps or drops what it learned.

Three arms from the same start (generation 0 with ``model.batch`` 2), on the same problems, with
the same budget:

  recursive   the improver is the start version itself
  frozen      the improver is generation 0 (same search seed: the two differ in ``model.batch``)
  random      no learning: candidates drawn as in a first round, each measured on as many
              problems as generation 0 measures one, the best by mean value met with the same
              final check

Every nominee is then measured against the start on the four categories with seeds no search
used, at the run budget, on all fresh instances.

    python -m rsi6.experiments.dev_recursion K --out DIR        # K: 1, 2, ... one repetition
    python -m rsi6.experiments.dev_recursion 1 --out DIR --smoke
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

from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.learner.learner import Learner
from rsi6.meta import rounds, space

CATEGORIES = ("binpacking", "jobshop", "pmedian", "quadassign")       # the light categories of registration c
NOMINAL = {"binpacking": 10.66, "jobshop": 7.66, "pmedian": 7.13, "quadassign": 1.58}   # mean CPU-s of a run, registered ledger
START = {"model.batch": 2}
SCALE = 0.26               # at model.sigma 1.0 a candidate differs from the mean in about two of the 38 fields
TRAIN = 40.0
SEARCH = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 12, "n_fresh": 24, "part": "A"}
RUN = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}
CPU_RATIO = 1.25
ASSESS_SEEDS = list(range(745001, 745017))


def problems_of(k: int, categories) -> list:
    return [(c, 740000 + 100 * k + j) for c in categories for j in range(1, 5)]


class Measure:
    """Values of versions on problems, against the start version on the same problem."""

    def __init__(self, start: dict, cache: Cache, tag: str):
        self.start, self.cache, self.tag = start, cache, tag
        self.runs = 0
        self.distinct = set()

    def records(self, versions, problems) -> list:
        jobs = [{"env": c, "version": v, "seed": s, "budget": SEARCH, "purpose": self.tag} for v in versions for c, s in problems]
        self.runs += len(jobs)
        self.distinct.update(designs.digest(v) for v in versions)
        got = self.cache.get(jobs)
        return [got[i * len(problems):(i + 1) * len(problems)] for i in range(len(versions))]

    def values(self, versions, problems) -> np.ndarray:
        base = self.cache.get([{"env": c, "version": self.start, "seed": s, "budget": SEARCH, "purpose": self.tag + ":start"}
                               for c, s in problems])
        out = np.zeros((len(versions), len(problems)))
        for i, rows in enumerate(self.records(versions, problems)):
            for j, (r, b) in enumerate(zip(rows, base)):
                out[i, j] = min(r["acquired"] - b["acquired"], r["gain"] - b["gain"])
            if rounds.cpu_of(rows) > CPU_RATIO * rounds.cpu_of(base):
                out[i, :] = -1.0
        return out


def decode(z, start: dict) -> dict:
    _, grids, _ = space.layout_of(start)
    index = [int(min(max(round(float(x)), 0), len(g) - 1)) for x, g in zip(z, grids)]
    return space.decode(np.array(index, dtype=np.int64), start)


def split(v: dict, n: int, rng):
    order = rng.permutation(n)
    n_check = min(max(1, int(round(v["assess.holdback"] * n))), n - 1) if n > 1 else 0
    return order[:n_check], order[n_check:]


def final_check(v: dict, start: dict, learned: dict, problems, check, measure: Measure) -> dict:
    """The learner's self-assessment: the learned version against the start on the held-back problems."""
    values = measure.values([start, learned], [problems[i] for i in check])
    keys = np.zeros((2, len(check), 2))
    keys[:, :, 1] = -values
    f = Learner._fitness(keys)
    return {"held_back": [list(problems[i]) for i in check], "values": values[1].tolist(),
            "kept": bool(f[1] > f[0] or not v["assess.strict"])}


def learner_search(v: dict, start: dict, problems, measure: Measure, rng, train: float) -> dict:
    """The loop of ``Learner._acquire_assign`` (variant cem), with versions for policies and measured runs for rollouts."""
    if v["model.variant"] != "cem":
        raise SystemExit("only the cem variant is transcribed")
    n = len(problems)
    check, fit = split(v, n, rng)
    cost = np.array([NOMINAL[c] for c, _ in problems])
    limit, used = train * float(cost.sum()), 0.0
    reserve = 3.0 * float(cost[check].sum())
    z0 = space.encode(start).astype(float)
    d = len(z0)
    mu, sigma = z0.copy(), np.full(d, float(v["model.sigma"]) * SCALE)
    pop, batch = int(v["model.pop"]), min(int(v["model.batch"]), len(fit))
    n_elite = max(2, int(round(v["model.elite"] * pop)))
    best, iterations, path = z0.copy(), 0, []
    while d > 0 and len(fit) > 0:
        chosen = rng.choice(len(fit), size=batch, replace=False)
        need = pop * float(cost[fit[chosen]].sum())
        if limit - used - reserve < need:
            break
        cands = mu + sigma * rng.standard_normal((pop, d))
        if v["model.keep_best"]:
            cands[0] = mu
        values = measure.values([decode(c, start) for c in cands], [problems[fit[i]] for i in chosen])
        used += need
        keys = np.zeros((pop, batch, 2))
        keys[:, :, 1] = -values
        elite = cands[np.argsort(-Learner._fitness(keys), kind="stable")[:n_elite]]
        mu = elite.mean(axis=0)
        sigma = np.maximum(sigma * v["model.decay"], 0.02 * SCALE)
        iterations += 1
        best = mu.copy()
        path.append(designs.differences(start, decode(mu, start)))
    learned = decode(best, start)
    out = {"iterations": iterations, "counted": used, "limit": limit, "path": path,
           "learned_changes": designs.differences(start, learned), "nominee": None, "check": None}
    if iterations == 0 or designs.digest(learned) == designs.digest(start):
        out["why"] = "the learned version is the start"
        return out
    out["check"] = final_check(v, start, learned, problems, check, measure)
    if out["check"]["kept"]:
        out["nominee"] = learned
    else:
        out["why"] = "the learned version did not beat the start on the held-back problems"
    return out


def random_search(v0: dict, start: dict, problems, measure: Measure, rng, train: float, split_rng) -> dict:
    """No learning: candidates drawn as in a first round of generation 0, measured on as many problems as
    generation 0 measures a candidate on, the best by mean value met with the same final check (on the
    held-back problems of the two other arms: ``split_rng`` is seeded as their searches are)."""
    n = len(problems)
    check, fit = split(v0, n, split_rng)
    cost = np.array([NOMINAL[c] for c, _ in problems])
    limit, used = train * float(cost.sum()), 0.0
    reserve = 3.0 * float(cost[check].sum())
    z0 = space.encode(start).astype(float)
    pop, batch = int(v0["model.pop"]), min(int(v0["model.batch"]), len(fit))
    sigma = float(v0["model.sigma"]) * SCALE
    best, best_value, groups = None, 0.0, 0
    while True:
        chosen = rng.choice(len(fit), size=batch, replace=False)
        need = pop * float(cost[fit[chosen]].sum())
        if limit - used - reserve < need:
            break
        cands = [decode(z0 + sigma * rng.standard_normal(len(z0)), start) for _ in range(pop)]
        values = measure.values(cands, [problems[fit[i]] for i in chosen]).mean(axis=1)
        used += need
        groups += 1
        for c, value in zip(cands, values):
            if value > best_value and designs.digest(c) != designs.digest(start):
                best, best_value = c, float(value)
    out = {"iterations": groups, "counted": used, "limit": limit, "path": [],
           "learned_changes": None if best is None else designs.differences(start, best), "nominee": None, "check": None}
    if best is None:
        out["why"] = "no candidate was above the start"
        return out
    out["check"] = final_check(v0, start, best, problems, check, measure)
    if out["check"]["kept"]:
        out["nominee"] = best
    else:
        out["why"] = "the best candidate did not beat the start on the held-back problems"
    return out


def assess(start: dict, nominee: dict, categories, seeds, cache: Cache) -> dict:
    """The nominee against the start at the run budget, all fresh instances, seeds no search used."""
    per, cpu_n, cpu_s = {}, 0.0, 0.0
    for c in categories:
        base = cache.get(rounds.jobs_for(start, [c], seeds, RUN, "dev-recursion:assess"))
        rows = cache.get(rounds.jobs_for(nominee, [c], seeds, RUN, "dev-recursion:assess"))
        d = [min(r["acquired"] - b["acquired"], r["gain"] - b["gain"]) for r, b in zip(rows, base)]
        per[c] = {"mean": float(np.mean(d)), "se": float(np.std(d, ddof=1) / len(d) ** 0.5) if len(d) > 1 else None,
                  "above": int(sum(x > 0 for x in d)), "below": int(sum(x < 0 for x in d)), "per_seed": d}
        cpu_n += float(np.mean([r["cpu"]["acquire"] + r["cpu"]["apply"] for r in rows]))
        cpu_s += float(np.mean([r["cpu"]["acquire"] + r["cpu"]["apply"] for r in base]))
    return {"value": float(np.mean([per[c]["mean"] for c in categories])), "per_category": per, "cpu_ratio": cpu_n / max(cpu_s, 1e-9)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("k", type=int)
    parser.add_argument("--out", required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    k = args.k
    if not 1 <= k <= 99:
        raise SystemExit("a repetition is numbered 1 to 99")
    categories, train, assess_seeds = CATEGORIES, TRAIN, ASSESS_SEEDS
    if args.smoke:
        categories, train, assess_seeds = ("pmedian", "quadassign"), 16.0, [9745001, 9745002]
    v0 = designs.default("a")
    start = designs.validate(dict(v0, **START))
    problems = problems_of(k, categories) if not args.smoke else [(c, 9740000 + j) for c in categories for j in range(1, 5)]
    stem = ("smoke_" if args.smoke else "") + f"recursion_{k:02d}"
    os.makedirs(args.out, exist_ok=True)
    scratch = os.path.join(args.out, stem + ".scratch.jsonl")
    if guard.is_registered(scratch):
        raise SystemExit("development writes a scratch ledger, never a registered one")
    if not os.path.exists(scratch):
        shutil.copy(guard.MAIN, scratch)
    ledger = ledgers.Ledger(scratch)
    started = ledger.select(type="dev_recursion_started")
    if not started:
        started = [ledger.append({"type": "dev_recursion_started", "k": k, "problems": [list(p) for p in problems], "train": train})]
    before = started[0]["idx"]
    cache = Cache(ledger)
    arms = {}
    plan = (("recursive", start, 3000 + k), ("frozen", v0, 3000 + k), ("random", None, 4000 + k))
    for name, improver, seed in plan:
        measure = Measure(start, cache, f"dev-recursion:{name}")
        rng = np.random.default_rng(seed)
        if name == "random":
            result = random_search(v0, start, problems, measure, rng, train, np.random.default_rng(3000 + k))
        else:
            result = learner_search(improver, start, problems, measure, rng, train)
        result.update({"improver": None if improver is None else designs.digest(improver), "search_seed": seed,
                       "rollouts": measure.runs, "distinct_versions": len(measure.distinct)})
        if result["nominee"] is not None:
            result["nominee_digest"] = designs.digest(result["nominee"])
            result["nominee_changes"] = designs.differences(start, result["nominee"])
            result["assessment"] = assess(start, result["nominee"], categories, assess_seeds, cache)
        arms[name] = result
        value = result.get("assessment", {}).get("value")
        print(f"{name:9s} rounds {result['iterations']:3d} rollouts {result['rollouts']:5d} versions {result['distinct_versions']:4d}"
              f" learned {sorted(result['learned_changes'] or {})} kept {None if result['check'] is None else result['check']['kept']}"
              f" value {'-' if value is None else format(value, '+.4f')}", flush=True)
    out = {"what": "development: the learner's acquisition loop as the improver of versions; start generation 0 with model.batch 2; "
                   "improver the start itself (recursive), generation 0 (frozen), none (random)",
           "k": k, "smoke": bool(args.smoke), "categories": list(categories), "problems": [list(p) for p in problems], "train": train,
           "scale": SCALE, "nominal_cost": NOMINAL, "assess_seeds": assess_seeds, "start": designs.digest(start),
           "generation_0": designs.digest(v0), "arms": arms,
           "machine": {"python": sys.version.split()[0], "numpy": np.__version__, "cpus": os.cpu_count(), "platform": platform.platform()}}
    json.dump(out, open(os.path.join(args.out, stem + ".json"), "w"), indent=1)
    with open(os.path.join(args.out, stem + ".records.jsonl"), "w") as handle:
        for r in ledger.records[before:]:
            handle.write(json.dumps(r, sort_keys=True) + "\n")
    os.remove(scratch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
