"""Scratch: a memory of ways to search, keyed by what a problem looks like; simulated on the tables of dev_ways.

Acquisition on a kind = a sweep race from a starting way: setting by setting (random order), the three levels are tried on
`b` problems each and the best by mean rank of the cost stays, until `cap` trials are used. Problems of a kind: a random
10 for races, the other 6 to say what a way is worth (score).

For each kind left out K (the others are the kinds the improver may use):
  generation 0   on K: sweep from the generic way.
  generation 1   memory = what generation 0 acquired on the others; on K: sweep from the way remembered for the nearest
                 kind (by a generic description of its problems).
  recursive g    memory made by generation g-1 acquiring on the others (each sweep starts from what it remembers for that
                 kind itself); on K as above.
  frozen g       memory made by generation 0 again (new draws), whatever came before.
  shuffled g     recursive, with the descriptions dealt out at random among the remembered kinds.
  recall only    the remembered way of generation 1 without any sweep on K.

    python3 -I sim_memory.py TABLE_DIR [cap] [b] [sims]
"""
# Development script, kept as it was run (2026-11-24) apart from the path below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import glob
import json
import os
import sys

import numpy as np

from rsi6.learner import design_v as V

WAYS = V.ways()
NAMES = list(V.LEVELS)
INDEX = {tuple(w[n] for n in NAMES): i for i, w in enumerate(WAYS)}
OWN = WAYS.index(V.MECH)


def describe(P):
    cap = P.capacity
    return np.array([np.log10(P.n_vars) / 3.0, np.log10(P.n_opts) / 3.0, min(P.n_opts / P.n_vars, 1.0), float(P.ordered), float(cap is None),
                     float(cap is not None and int(cap.max()) == 1), float(P.domain is not None), min(int(P.hard.sum()), 4) / 4.0,
                     min(int((~P.hard & ~P.detail).sum()), 4) / 4.0, float(len(P.var_var) > 0), float(len(P.opt_opt) > 0), float(len(P.var_opt) > 0),
                     float(P.start_answer is not None)])


def load(directory):
    from rsi6 import environments
    from rsi6.environments import fresh
    from rsi6.kernel.problem import Meter
    fresh.install()
    cost, score, about = {}, {}, {}
    for path in sorted(glob.glob(os.path.join(directory, "ways_*.json"))):
        d = json.load(open(path))
        if len(d["ways"]) != len(WAYS):
            continue
        big = 1e30
        cost[d["kind"]] = np.array([[[(t[0] if t[0] is not None else big) * 1e9 + (t[1] if t[1] is not None else big) for t in p] for p in w] for w in d["results"]])
        score[d["kind"]] = np.array([[[t[3] for t in p] for p in w] for w in d["results"]])
        env = environments.load(d["kind"])
        about[d["kind"]] = describe(env.problem(d["problems"][0], Meter(float("inf")), 0, True)[0])
    return cost, score, about


def sweep(cost, problems, start, rng, cap, b):
    """A sweep race on ``cost[way, problem, trial]`` from the way ``start``. Returns the way it ends on."""
    way = [WAYS[start][n] for n in NAMES]
    used, at, n_trials = 0, 0, cost.shape[2]
    while used + 3 * b <= cap:
        for f in rng.permutation(len(NAMES)):
            if used + 3 * b > cap:
                break
            cands = []
            for lv in range(3):
                w = list(way)
                w[f] = lv
                cands.append(INDEX[tuple(w)])
            ps = [problems[(at + j) % len(problems)] for j in range(b)]
            at += b
            ranks = np.zeros(3)
            for p in ps:
                c = np.array([cost[w, p, int(rng.integers(n_trials))] for w in cands])
                order = np.argsort(np.argsort(c, kind="stable"), kind="stable").astype(float)
                for value in np.unique(c):
                    order[c == value] = order[c == value].mean()
                ranks += order
            used += 3 * b
            best = int(np.argmin(ranks))
            if ranks[best] < ranks[way[f]] - 1e-9:
                way[f] = best
    return INDEX[tuple(way)]


def recall(memory, about_k, shuffled=None):
    """The way remembered for the kind whose description is nearest (None when nothing is remembered)."""
    if not memory:
        return OWN
    names = list(memory)
    d = [np.mean(np.abs(memory[n][0] - about_k)) for n in names]
    return memory[names[int(np.argmin(d))]][1]


def main():
    cost, score, about = load(sys.argv[1])
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 36
    b = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    sims = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    kinds = sorted(cost)
    print("kinds", kinds, "| cap", cap, "trials | b", b, "| sims", sims)
    print("nearest kind by description:", {k: min((o for o in kinds if o != k), key=lambda o: np.mean(np.abs(about[o] - about[k]))) for k in kinds})
    names = ["generation 0", "recall only", "generation 1", "recursive 2", "frozen 2", "shuffled 2", "recursive 3", "frozen 3", "shuffled 3"]
    out = {k: {n: [] for n in names} for k in kinds}
    for s in range(sims):
        rng = np.random.default_rng([s, 97])
        split = {}
        for k in kinds:
            perm = [int(i) for i in rng.permutation(cost[k].shape[1])]
            n_eval = max(2, len(perm) * 3 // 8)
            split[k] = (perm[n_eval:], perm[:n_eval])
        worth = lambda k, w: float(score[k][w][split[k][1]].mean())
        for K in kinds:
            others = [o for o in kinds if o != K]
            base = worth(K, OWN)
            acquire = lambda k, start, r: sweep(cost[k], split[k][0], start, r, cap, b)
            out[K]["generation 0"].append(worth(K, acquire(K, OWN, rng)) - base)
            m1 = {o: (about[o], acquire(o, OWN, rng)) for o in others}
            out[K]["recall only"].append(worth(K, recall(m1, about[K])) - base)
            out[K]["generation 1"].append(worth(K, acquire(K, recall(m1, about[K]), rng)) - base)
            mem = {"recursive": m1, "frozen": m1, "shuffled": m1}
            for g in (2, 3):
                new = {"recursive": {o: (about[o], acquire(o, mem["recursive"][o][1], rng)) for o in others},
                       "frozen": {o: (about[o], acquire(o, OWN, rng)) for o in others}}
                perm = [others[int(i)] for i in rng.permutation(len(others))]
                new["shuffled"] = {o: (about[p], acquire(o, mem["shuffled"][o][1], rng)) for o, p in zip(others, perm)}
                for arm in ("recursive", "frozen", "shuffled"):
                    mem[arm] = new[arm]
                    out[K][f"{arm} {g}"].append(worth(K, acquire(K, recall(mem[arm], about[K]), rng)) - base)
    print("gain over the generic way on the kind left out (score, problems no race used); standard error in brackets")
    for K in kinds:
        print(f"  {K:11s} " + " | ".join(f"{n} {np.mean(out[K][n]):+.4f}" for n in names))
    mean = {n: np.mean([np.mean(out[K][n]) for K in kinds]) for n in names}
    print("  mean        " + " | ".join(f"{n} {mean[n]:+.4f}" for n in names))
    for a, c in (("generation 1", "generation 0"), ("recursive 2", "frozen 2"), ("recursive 3", "frozen 3"), ("recursive 3", "shuffled 3"), ("recursive 3", "generation 1")):
        d = np.mean([np.array(out[K][a]) - np.array(out[K][c]) for K in kinds], axis=0)
        per = [float(np.mean(np.array(out[K][a]) - np.array(out[K][c]))) for K in kinds]
        print(f"  {a} - {c}: {d.mean():+.4f} ({d.std(ddof=1) / np.sqrt(len(d)):.4f}) | per kind " + " ".join(f"{x:+.3f}" for x in per))


if __name__ == "__main__":
    main()
