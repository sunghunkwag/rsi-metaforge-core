"""Scratch: races over ways to search, simulated on the tables of dev_ways (no search is run here).

A race (settings theta = width, reach, keep, batch, check): the version's own way and width-1 ways within `reach` changed
settings of it; rounds on `batch` new problems each (one trial per way and problem, drawn from the table), the best `keep`
share by mean rank of the cost stays; the last one standing must beat the own way on `check` held-back problems.
Problems of a kind are split at random: 10 for the race, 6 to say what the chosen way is worth (score, against the own way).

Read: (1) does theta matter for what a race ends on, per kind; (2) is a theta that is good on some kinds good on others;
(3) is a theta that is good for acquiring on kinds good for the pooled race (the improver's race over all kinds together).

    python3 -I race_sim.py TABLE_DIR [sims]
"""
# Development script, kept as it was run (2026-11-24) apart from the path below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import glob
import itertools
import json
import os
import sys

import numpy as np

from rsi6.learner import design_v as V

WAYS = V.ways()
INDEX = {tuple(w[n] for n in V.LEVELS): i for i, w in enumerate(WAYS)}
OWN = WAYS.index(V.MECH)
NAMES = list(V.LEVELS)
THETAS = [dict(zip(V.RACE_LEVELS, combo)) for combo in itertools.product(*[range(len(v)) for v in V.RACE_LEVELS.values()])]


def load(directory):
    cost, score = {}, {}
    for path in sorted(glob.glob(os.path.join(directory, "ways_*.json"))):
        d = json.load(open(path))
        if len(d["ways"]) != len(WAYS):
            continue
        r = d["results"]
        big = 1e30
        cost[d["kind"]] = np.array([[[(t[0] if t[0] is not None else big) * 1e9 + (t[1] if t[1] is not None else big) for t in p] for p in w] for w in r])
        score[d["kind"]] = np.array([[[t[3] for t in p] for p in w] for w in r])
    return cost, score


def neighbours(own, width, reach, rng):
    out, seen = [own], {own}
    base = [WAYS[own][n] for n in NAMES]
    tries = 0
    while len(out) < width and tries < 200:
        tries += 1
        w = list(base)
        for f in rng.choice(len(NAMES), size=int(rng.integers(1, reach + 1)), replace=False):
            w[f] = int(rng.choice([lv for lv in range(3) if lv != base[f]]))
        i = INDEX[tuple(w)]
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def race(cost, problems, theta, rng, own=OWN, cap=10 ** 9):
    """``cost[way, problem, trial]``; ``problems``: the problem indices the race may use, in order. Returns
    ``(chosen way, trials used)``."""
    width, reach = V.RACE_LEVELS["width"][theta["width"]], V.RACE_LEVELS["reach"][theta["reach"]]
    keep, batch, check = V.RACE_LEVELS["keep"][theta["keep"]], V.RACE_LEVELS["batch"][theta["batch"]], V.RACE_LEVELS["check"][theta["check"]]
    alive = neighbours(own, width, reach, rng)
    held, free = list(problems[:check]), list(problems[check:])
    ranks = {w: [] for w in alive}
    used, at = 0, 0
    n_trials = cost.shape[2]
    while len(alive) > 1 and at < len(free) and used + len(alive) * batch <= cap:
        for p in free[at:at + batch]:
            c = np.array([cost[w, p, int(rng.integers(n_trials))] for w in alive])
            order = np.argsort(np.argsort(c, kind="stable"), kind="stable").astype(float)
            for value in np.unique(c):
                same = c == value
                order[same] = order[same].mean()
            for w, r in zip(alive, order / max(len(alive) - 1, 1)):
                ranks[w].append(r)
            used += len(alive)
        at += batch
        alive = sorted(alive, key=lambda w: np.mean(ranks[w]))[:max(1, int(np.ceil(keep * len(alive))) if keep * len(alive) < len(alive) - 1e-9 else len(alive) - 1)]
    winner = min(alive, key=lambda w: np.mean(ranks[w]) if ranks[w] else 1.0)
    if winner != own and check:
        a = np.array([cost[winner, p, int(rng.integers(n_trials))] for p in held])
        b = np.array([cost[own, p, int(rng.integers(n_trials))] for p in held])
        used += 2 * check
        if not (a < b).sum() > (a > b).sum():
            winner = own
    return winner, used


def main():
    cost, score = load(sys.argv[1])
    sims = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    kinds = sorted(cost)
    print("kinds", kinds, "| thetas", len(THETAS), "| sims", sims)
    gain = np.zeros((len(THETAS), len(kinds)))
    used = np.zeros((len(THETAS), len(kinds)))
    for ki, k in enumerate(kinds):
        n_p = cost[k].shape[1]
        for ti, theta in enumerate(THETAS):
            g, u = [], []
            for s in range(sims):
                rng = np.random.default_rng([s, ki, 91])
                perm = [int(i) for i in rng.permutation(n_p)]
                n_eval = max(2, n_p * 3 // 8)
                ev, rc = perm[:n_eval], perm[n_eval:]
                rng2 = np.random.default_rng([s, ki, ti, 92])
                w, t = race(cost[k], rc, theta, rng2)
                g.append(score[k][w][ev].mean() - score[k][OWN][ev].mean())
                u.append(t)
            gain[ti, ki], used[ti, ki] = np.mean(g), np.mean(u)
    np.save(os.path.join(sys.argv[1], "race_gain.npy"), gain)
    np.save(os.path.join(sys.argv[1], "race_used.npy"), used)
    se = lambda k: None
    print("per kind: gain of acquiring by a race over the own way, on problems the race did not use")
    for ki, k in enumerate(kinds):
        best_way = score[k].mean(axis=(1, 2))
        print(f"  {k:11s} theta: mean {gain[:, ki].mean():+.4f} worst {gain[:, ki].min():+.4f} best {gain[:, ki].max():+.4f} | default theta {gain[THETAS.index(V.RACE), ki]:+.4f} "
              f"| the kind's best way is worth {best_way.max() - best_way[OWN]:+.4f} | trials used: {used[:, ki].min():.0f} to {used[:, ki].max():.0f}")
    z = (gain - gain.mean(axis=0)) / (gain.std(axis=0) + 1e-12)
    print("is a theta that is good on some kinds good on another? correlation over thetas of the gain on one kind with the mean on the others:")
    for ki, k in enumerate(kinds):
        others = [j for j in range(len(kinds)) if j != ki]
        print(f"  {k:11s} {np.corrcoef(z[:, ki], z[:, others].mean(axis=1))[0, 1]:+.3f}")
    print("main effects of the race settings on the gain (mean over kinds):")
    for name in V.RACE_LEVELS:
        eff = [gain[[i for i, t in enumerate(THETAS) if t[name] == lv]].mean() for lv in range(3)]
        tr = [used[[i for i, t in enumerate(THETAS) if t[name] == lv]].mean() for lv in range(3)]
        print(f"  {name:6s} {V.RACE_LEVELS[name]}: gain " + " / ".join(f"{e:+.4f}" for e in eff) + " | trials " + " / ".join(f"{t:.0f}" for t in tr))
    # the pooled race: problems of all kinds together (ranks are within a problem, so kinds mix)
    big = np.concatenate([cost[k] for k in kinds], axis=1)
    big_score = np.concatenate([(score[k] - score[k][OWN].mean()) / (score[k].mean(axis=(1, 2)).std() + 1e-12) for k in kinds], axis=1)
    pooled = np.zeros(len(THETAS))
    for ti, theta in enumerate(THETAS):
        g = []
        for s in range(sims):
            rng = np.random.default_rng([s, 93])
            perm = [int(i) for i in rng.permutation(big.shape[1])]
            ev, rc = perm[:big.shape[1] * 3 // 8], perm[big.shape[1] * 3 // 8:]
            w, _ = race(big, rc, theta, np.random.default_rng([s, ti, 94]))
            g.append(big_score[w][ev].mean() - big_score[OWN][ev].mean())
        pooled[ti] = np.mean(g)
    np.save(os.path.join(sys.argv[1], "race_pooled.npy"), pooled)
    print(f"pooled race (all kinds together; standardised score): mean {pooled.mean():+.4f} worst {pooled.min():+.4f} best {pooled.max():+.4f} default {pooled[THETAS.index(V.RACE)]:+.4f}")
    print(f"alignment: correlation over thetas of the mean gain as acquirer (standardised over kinds) with the gain in the pooled race: {np.corrcoef(z.mean(axis=1), pooled)[0, 1]:+.3f}")


if __name__ == "__main__":
    main()
