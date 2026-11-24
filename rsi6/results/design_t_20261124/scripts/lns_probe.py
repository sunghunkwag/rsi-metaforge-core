"""Scratch: at equal units (E * n_vars^2), random exchanges scored by full evaluations against a generic destroy-and-repair
search (unassign r random variables, re-assign them greedily by the exact changes candidates() gives; keep if not worse)."""
# Development script, kept as it was run (2026-11-25) apart from the path below. Importing ls_probe runs its own loop first.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
from rsi6 import environments
from rsi6.kernel.environment import split
from rsi6.kernel.problem import Meter, BudgetExhausted
from ls_probe import cost, greedy

def key(P, rows):
    soft = ~P.hard & ~P.detail
    return rows[..., P.hard].sum(axis=-1) * 1e9 + rows[..., soft].sum(axis=-1) + rows[..., P.detail].sum(axis=-1) * 1e-3

def swaps(P, a, rng):
    best, c_best = a.copy(), cost(P, P.evaluate(a))
    try:
        while True:
            b = best.copy()
            i, j = rng.choice(P.n_vars, size=2, replace=False)
            if b[i] == b[j]:
                continue
            b[i], b[j] = b[j], b[i]
            if not P.well_formed(b):
                continue
            c = cost(P, P.evaluate(b))
            if c <= c_best:
                best, c_best = b, c
    except BudgetExhausted:
        return best

def lns(P, a, rng, r):
    best, c_best = a.copy(), cost(P, P.evaluate(a))
    try:
        while True:
            if P.ordered:
                return best
            out = set(int(v) for v in rng.choice(P.n_vars, size=min(r, P.n_vars), replace=False))
            s = P.start()
            for v in range(P.n_vars):
                if v not in out:
                    P.assign(s, v, int(best[v]))
            left = sorted(out)
            while left:
                rows = P.candidates(s, left)
                k = key(P, rows)
                ok = np.broadcast_to(P.allowed(s), k.shape).copy()
                if P.domain is not None:
                    ok &= P.domain[left]
                k = np.where(ok, k, np.inf)
                if not np.isfinite(k).any():
                    break
                srt = np.sort(k, axis=1)
                regret = np.where(np.isfinite(srt[:, 1]) if k.shape[1] > 1 else False, srt[:, 1] - srt[:, 0], 1e18) if k.shape[1] > 1 else np.zeros(len(left))
                regret = np.where(np.isfinite(srt[:, 0]), regret, -np.inf)
                i = int(np.argmax(regret))                       # the variable that loses most if it does not get its best option
                P.assign(s, left[i], int(np.argmin(k[i])))
                left.pop(i)
            if left:
                continue
            b = P.assignment(s)
            c = cost(P, P.totals(s))
            if c <= c_best:
                best, c_best = b, c
    except BudgetExhausted:
        return best

for kind in sys.argv[1:]:
    env = environments.load(kind)
    train_ids, _ = split(env, 16, 24)
    rows, started = {}, time.process_time()
    for i in train_ids[:4]:
        P, decode = env.problem(i, Meter(float("inf")), 0, True)
        a = greedy(P, np.random.default_rng(1))
        if a is None:
            continue
        rows.setdefault("greedy", []).append(env.score(i, decode(a)))
        for E in (1, 5):
            for name, fn in (("swap", lambda: swaps(P, a, np.random.default_rng(2))), ("lns4", lambda: lns(P, a, np.random.default_rng(2), 4)),
                             ("lns12", lambda: lns(P, a, np.random.default_rng(2), 12))):
                P.meter = Meter(E * P.n_vars * P.n_vars)
                b = fn()
                P.meter = Meter(float("inf"))
                rows.setdefault(f"{name} E={E}", []).append(env.score(i, decode(b)))
    print(f"{kind:11s} n {P.n_vars}x{P.n_opts} | " + " | ".join(f"{k} {np.mean(v):.3f}" for k, v in rows.items()) + f" | cpu {time.process_time() - started:.0f}s", flush=True)
