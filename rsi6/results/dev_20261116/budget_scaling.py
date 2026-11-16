"""Development measurement (source categories, scratch ledger, not evidence): how the effect of a
single edit of the open design and the noise of a paired run scale with the training budget.

Eight single edits of generation 0 of design o, drawn uniformly over the edit cells with a fixed
generator, and generation 0 itself, each run on jobshop, pmedian and quadassign with four seeds,
at the registered search budget (train 40) and at five times its training budget (train 200).
For each budget: sigma = the spread over seeds of a paired difference (edit minus generation 0,
same seed), tau = the spread over edits of their true mean effect (variance of the per-edit,
per-category means minus sigma^2 / seeds), and the share of edits whose mean beats 0.01.

    python budget_scaling.py run      # measure (slow; low priority)
    python budget_scaling.py report   # read the scratch ledger and print the estimates
"""
import json
import os
import shutil
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.kernel import run as R
from rsi6.learner import design_o as O
from rsi6.open import edits

S = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.join(S, "dev_budget.jsonl")
ENVS = ["jobshop", "pmedian", "quadassign"]
SEEDS = [9101, 9102, 9103, 9104]
B40 = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 12, "n_fresh": 24, "part": "A"}
B200 = dict(B40, train=200.0)


def candidates():
    rng = np.random.default_rng(424242)
    parent = O.default()
    seen = {edits.behaviour(parent)}
    out = []
    while len(out) < 8:
        cell = edits.CELLS[int(rng.integers(len(edits.CELLS)))]
        new, info = edits.apply_edit(parent, cell, [], rng)
        if new is None or edits.behaviour(new) in seen:
            continue
        seen.add(edits.behaviour(new))
        out.append((new, "/".join(cell)))
    return parent, out


def jobs(version, budget, tag):
    return [{"env": e, "version": version, "seed": s, "budget": budget, "purpose": f"dev:budget:{tag}"} for e in ENVS for s in SEEDS]


def main():
    if not os.path.exists(DEV):
        shutil.copy("/home/user/rsi-metaforge-core/rsi6/ledger/main.jsonl", DEV)
    ledger = ledgers.Ledger(DEV)
    cache = R.Cache(ledger)
    parent, cands = candidates()
    mode = sys.argv[1] if len(sys.argv) > 1 else "report"
    out = {}
    for name, budget in (("train40", B40), ("train200", B200)):
        if mode == "run":
            cache.get(jobs(parent, budget, f"{name}:o0"), workers=1)
            for k, (m, cell) in enumerate(cands):
                cache.get(jobs(m, budget, f"{name}:edit{k}"), workers=1)
                print(name, "edit", k, cell, "done", flush=True)
        if any(R.key_of(j) not in cache.by_key for j in jobs(parent, budget, "") + [j for m, _ in cands for j in jobs(m, budget, "")]):
            out[name] = "not measured yet"
            continue
        base = {(r["env"], r["seed"]): r for r in (cache.by_key[R.key_of(j)] for j in jobs(parent, budget, ""))}
        d = np.zeros((len(cands), len(ENVS), len(SEEDS)))
        cpu = []
        for k, (m, cell) in enumerate(cands):
            for j in jobs(m, budget, ""):
                r = cache.by_key[R.key_of(j)]
                d[k, ENVS.index(r["env"]), SEEDS.index(r["seed"])] = r["acquired"] - base[(r["env"], r["seed"])]["acquired"]
                cpu.append(r["cpu"]["acquire"] + r["cpu"]["apply"])
        sigma = {e: float(np.sqrt(np.mean(d[:, i, :].var(axis=1, ddof=1)))) for i, e in enumerate(ENVS)}
        means = d.mean(axis=2)                                    # per edit, per category
        tau = {e: float(np.sqrt(max(0.0, means[:, i].var(ddof=1) - sigma[e] ** 2 / len(SEEDS)))) for i, e in enumerate(ENVS)}
        over = d.mean(axis=(1, 2))                                # per edit, over the categories
        sd_pair_mean = float(np.sqrt(np.mean([sigma[e] ** 2 for e in ENVS]) / (len(ENVS) * len(SEEDS))))
        out[name] = {"sigma_by_category": sigma, "tau_by_category": tau,
                     "edit_means_over_categories": [round(float(x), 4) for x in over],
                     "per_edit_per_category": np.round(means, 4).tolist(),
                     "sd_of_a_12_pair_mean_from_noise": sd_pair_mean,
                     "sd_of_edit_means_over_categories": float(over.std(ddof=1)),
                     "untrained_parent": float(np.mean([r["untrained"] for r in base.values()])),
                     "acquired_parent": float(np.mean([r["acquired"] for r in base.values()])),
                     "gain_parent": float(np.mean([r["gain"] for r in base.values()])),
                     "cpu_per_run": float(np.mean(cpu)),
                     "cells": [cell for _, cell in cands]}
    print(json.dumps(out, indent=1))
    json.dump(out, open(os.path.join(S, "budget_scaling.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
