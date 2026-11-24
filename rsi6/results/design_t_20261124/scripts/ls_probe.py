"""Scratch (pre-study B1): what is a plain local search worth after a greedy construction, on training instances of
assignment kinds, as a function of the evaluations allowed (E * n_vars full evaluations)?"""
# Development script, kept as it was run (2026-11-24) apart from the path below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
from rsi6 import environments
from rsi6.kernel.environment import split
from rsi6.kernel.problem import Meter

def cost(P, tot):
    soft = ~P.hard & ~P.detail
    return (float(tot[P.hard].sum()), float(tot[soft].sum()))

def greedy(P, rng, noise=0.0):
    s = P.start()
    while not P.complete(s):
        un = P.unassigned(s)
        v = int(un[0]) if P.ordered or noise == 0.0 else int(rng.choice(un))
        rows = P.candidates(s, [v])[0]
        ok = P.allowed(s).copy()
        if P.domain is not None:
            ok &= P.domain[v]
        if not ok.any():
            return None
        soft = ~P.hard & ~P.detail
        key = rows[:, P.hard].sum(axis=1) * 1e9 + rows[:, soft].sum(axis=1) + rows[:, P.detail].sum(axis=1) * 1e-3
        if noise:
            key = key + noise * np.abs(key).mean() * rng.standard_normal(len(key))
        key = np.where(ok, key, np.inf)
        P.assign(s, v, int(np.argmin(key)))
    return P.assignment(s)

def search(P, a, rng, evals, swap=0.5):
    best, c_best = a.copy(), cost(P, P.evaluate(a))
    used = np.bincount(a, minlength=P.n_opts)
    for _ in range(evals):
        b = best.copy()
        if rng.random() < swap:
            i, j = rng.choice(P.n_vars, size=2, replace=False)
            if b[i] == b[j]:
                continue
            b[i], b[j] = b[j], b[i]
        else:
            i = int(rng.integers(P.n_vars)); o = int(rng.integers(P.n_opts))
            if o == b[i] or (P.capacity is not None and used[o] >= P.capacity[o]):
                continue
            b[i] = o
        if not P.well_formed(b):
            continue
        c = cost(P, P.evaluate(b))
        if c <= c_best:
            best, c_best = b, c
            used = np.bincount(best, minlength=P.n_opts)
    return best

for kind in sys.argv[1:]:
    env = environments.load(kind)
    train_ids, _ = split(env, 16, 24)
    rows = {}
    started = time.process_time()
    for i in train_ids[:6]:
        P, decode = env.problem(i, Meter(float("inf")), 0, True)
        rng = np.random.default_rng(1)
        a = greedy(P, rng)
        if a is None:
            continue
        rows.setdefault("greedy", []).append(env.score(i, decode(a)))
        for E in (5, 20, 50):
            for name, sw in (("shift", 0.0), ("shift+swap", 0.5)):
                b = search(P, a, np.random.default_rng(2), E * P.n_vars, sw)
                rows.setdefault(f"{name} E={E}", []).append(env.score(i, decode(b)))
    print(f"{kind:12s} n_vars {P.n_vars} n_opts {P.n_opts} ordered {P.ordered} | " + " | ".join(f"{k} {np.mean(v):.4f}" for k, v in rows.items()) + f" | cpu {time.process_time() - started:.1f}s", flush=True)
