"""Scratch: chains of the self-model improver, simulated on the pools (no new program is run: candidates come from the pool).

For one kind of each form left out (paired by index). All arms share the first step (12 programs taken blind).
Every later step: 48 candidates the arm has not evaluated; a model of the landscape (attributes of a program -> its
rank on each of the three other kinds), acquired by a learner from what the arm has evaluated so far; the 12 candidates
the model puts first are evaluated (pool lookup); the library is rebuilt (six programs, greedy cover of the training
problems of the three other kinds).

  recursive  the model is acquired by the learner that carries the arm's current libraries
  frozen     the model is acquired by generation 0 (no library)
  random     no model: 12 of the 48 at random

Read on the kind left out (never used by a chain): the mean value of the programs a step evaluated, the best value
found so far, and what the library covers there.

    python3 -I u_chain_sim2.py OUT.json [n_seeds] [train] [steps]
"""
# Development script, kept as it was run (2026-11-24/25) apart from the two paths below.
# REPO: the root of the repository; DEV: a scratch directory for pools and outputs (RSI6_T_DEV).
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV = _os.environ.get("RSI6_T_DEV", "t_dev")
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json
import multiprocessing
import os
import pickle
import sys
import warnings

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np

warnings.filterwarnings("ignore")
from rsi6.learner import design_t as T
from u_landscape import features, model, ranks

POOL = {f: pickle.load(open(os.path.join(DEV, f"pool_{f}.pkl"), "rb")) for f in ("unordered", "ordered")}
X = {f: np.array([features(p) for p in POOL[f]["programs"]]) for f in POOL}
KINDS = {f: list(dict.fromkeys(POOL[f]["kind"])) for f in POOL}
ARMS = ("recursive", "frozen", "random", "recursive_max", "frozen_max", "oracle_mean", "oracle_max")
N_FIRST, N_CAND, N_TAKE, SLOTS = 12, 48, 12, 6


def cover(form, members, cols):
    S = POOL[form]["skill"][:, cols]
    chosen, best = [], np.full(cols.sum(), -1.0)
    for _ in range(min(SLOTS, len(members))):
        gains = [np.maximum(best, S[p]).mean() if p not in chosen else -9.0 for p in members]
        c = members[int(np.argmax(gains))]
        if np.maximum(best, S[c]).mean() <= best.mean() + 1e-12 and chosen:
            break
        chosen.append(c)
        best = np.maximum(best, S[c])
    return chosen


def chain(args):
    pair, seed, train, steps = args
    out = {}
    left = {f: KINDS[f][pair] for f in POOL}
    cols = {f: np.array([k != left[f] for k in POOL[f]["kind"]]) for f in POOL}
    per_kind = {f: {k: POOL[f]["skill"][:, np.array(POOL[f]["kind"]) == k].mean(axis=1) for k in KINDS[f]} for f in POOL}
    order = {f: np.random.default_rng(900 + seed).permutation(len(X[f])) for f in POOL}
    for arm in ARMS:
        rng = np.random.default_rng(31 * seed + 5)
        known = {f: [int(i) for i in order[f][:N_FIRST]] for f in POOL}
        library = {f: cover(f, known[f], cols[f]) for f in POOL}
        rows = []
        for step in range(steps + 1):
            row = {}
            if step > 0:
                version = T.default()
                if arm.startswith("recursive"):
                    version["library"] = {f: [POOL[f]["programs"][c] for c in library[f]] for f in POOL}
                for f in POOL:
                    rest = [int(i) for i in order[f] if int(i) not in set(known[f])]
                    cand = [rest[int(i)] for i in np.random.default_rng(77 * seed + step).permutation(len(rest))[:N_CAND]]
                    k = np.array(known[f])
                    others = [q for q in KINDS[f] if q != left[f]]
                    truth = np.mean([per_kind[f][q][np.array(cand)] for q in others], axis=0)
                    if arm == "random":
                        take = cand[:N_TAKE]
                        rho = 0.0
                    elif arm.startswith("oracle"):
                        allk = np.array(known[f] + cand)
                        per_all = [ranks(per_kind[f][q][allk])[len(known[f]):] for q in others]
                        pred = np.mean(per_all, axis=0) if arm == "oracle_mean" else np.max(per_all, axis=0)
                        take = [cand[int(i)] for i in np.argsort(-pred)[:N_TAKE]]
                        rho = 1.0
                    else:
                        per = [ranks(per_kind[f][q][k]) for q in others]
                        general = np.mean(per, axis=0)
                        nc = min(128, (2 * len(k)) // 3)
                        if arm.endswith("_max"):
                            preds = [model(version, X[f][k], t, X[f][np.array(cand)], rng, train=train, targets=per, n_ctx=nc,
                                           n_qry=min(64, len(k) - nc))[0] for t in per]
                            pred = np.max(preds, axis=0)
                        else:
                            pred = model(version, X[f][k], general, X[f][np.array(cand)], rng, train=train, targets=per, n_ctx=nc,
                                         n_qry=min(64, len(k) - nc))[0]
                        take = [cand[int(i)] for i in np.argsort(-pred)[:N_TAKE]]
                        rho = float(np.corrcoef(ranks(pred), ranks(truth))[0, 1]) if np.std(pred) > 0 else 0.0
                    row[f] = {"rho": rho, "taken_left_out": float(per_kind[f][left[f]][np.array(take)].mean()),
                              "taken_others": float(np.mean([per_kind[f][q][np.array(take)] for q in KINDS[f] if q != left[f]]))}
                    known[f] += take
                    library[f] = cover(f, library[f] + take, cols[f])
            for f in POOL:
                S = POOL[f]["skill"]
                row.setdefault(f, {})
                row[f]["library_left_out"] = float(S[np.ix_(library[f], ~cols[f])].max(axis=0).mean())
                row[f]["library_others"] = float(S[np.ix_(library[f], cols[f])].max(axis=0).mean())
                row[f]["best_left_out"] = float(per_kind[f][left[f]][np.array(known[f])].max())
                row[f]["first_left_out"] = float(S[np.ix_(library[f][:2], ~cols[f])].max(axis=0).mean())
            rows.append(row)
        out[arm] = rows
    return {"pair": pair, "seed": seed, "left": left, "arms": out}


def main():
    out = sys.argv[1]
    n_seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    train = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
    steps = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    jobs = [(pair, seed, train, steps) for pair in range(4) for seed in range(n_seeds)]
    with multiprocessing.get_context("fork").Pool(2) as pool:
        results = pool.map(chain, jobs, chunksize=1)
    json.dump(results, open(out, "w"))
    for f in POOL:
        print(f"== {f}: mean over {len(results)} chains (4 kinds left out x {n_seeds} seeds), train {train}")
        for key in ("rho", "taken_left_out", "taken_others", "library_left_out", "library_others", "best_left_out", "first_left_out"):
            print(f"  {key}")
            for arm in ARMS:
                line = []
                for step in range(steps + 1):
                    vals = [r["arms"][arm][step][f].get(key) for r in results]
                    line.append("   --  " if vals[0] is None else f"{np.mean(vals):+.4f}")
                print(f"    {arm:10s}" + " ".join(line))
            for a, b in (("recursive", "frozen"), ("recursive", "random"), ("recursive_max", "frozen_max"), ("recursive_max", "random"),
                         ("oracle_mean", "random"), ("oracle_max", "random")):
                d = [np.mean([r["arms"][a][s][f][key] - r["arms"][b][s][f][key] for s in range(1, steps + 1)]) for r in results
                     if results[0]["arms"][a][1][f].get(key) is not None]
                if d:
                    print(f"    {a} - {b}, mean over steps 1..{steps}: {np.mean(d):+.4f} (se {np.std(d, ddof=1) / np.sqrt(len(d)):.4f}; positive in {sum(x > 0 for x in d)} of {len(d)})")


if __name__ == "__main__":
    main()
