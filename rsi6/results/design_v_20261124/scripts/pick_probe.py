"""Scratch: does it matter WHICH variables a repair takes out? Equal units (E * n_vars^2), repair size r, training instances.
Modes: random; cost (those whose option cost most when it was assigned, by the exact change at that time); regret (those that
had the least to lose by another option); late (assigned last); mixed (half by cost, half random)."""
# Development script, kept as it was run (2026-11-24) apart from the path below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
from rsi6 import environments
from rsi6.kernel.environment import split
from rsi6.kernel.problem import Meter, BudgetExhausted

def cost(P, tot):
    soft = ~P.hard & ~P.detail
    return (float(tot[P.hard].sum()), float(tot[soft].sum()))

def key(P, rows):
    soft = ~P.hard & ~P.detail
    return rows[..., P.hard].sum(axis=-1) * 1e9 + rows[..., soft].sum(axis=-1) + rows[..., P.detail].sum(axis=-1) * 1e-3

def fill(P, s, left, info, clock, regret=True):
    left = sorted(left) if P.ordered else list(left)
    while left:
        look = left if regret and not P.ordered else left[:1]
        k = key(P, P.candidates(s, look))
        ok = np.broadcast_to(P.allowed(s), k.shape).copy()
        if P.domain is not None:
            ok &= P.domain[look]
        k = np.where(ok, k, np.inf)
        if not np.isfinite(k).any(axis=1).all():
            return False
        two = np.partition(k, 1, axis=1)[:, :2] if k.shape[1] > 1 else np.column_stack([k[:, 0], k[:, 0]])
        reg = np.where(np.isfinite(two[:, 1]), two[:, 1] - two[:, 0], 1e18)
        i = int(np.argmax(reg)) if len(k) > 1 else 0
        o = int(np.argmin(k[i]))
        v = left[i]
        info["cost"][v], info["regret"][v], info["when"][v] = k[i, o] - np.nanmin(np.where(np.isfinite(k[i]), k[i], np.nan)) + k[i, o], reg[i], clock[0]
        clock[0] += 1
        P.assign(s, v, o)
        left.pop(i)
    return True

def run(P, rng, r, mode):
    n = P.n_vars
    info = {"cost": np.zeros(n), "regret": np.zeros(n), "when": np.zeros(n)}
    clock = [0]
    best = c_best = None
    try:
        s = P.start()
        if not fill(P, s, range(n), info, clock, regret=False):
            return None
        best, c_best = P.assignment(s), cost(P, P.totals(s))
        while True:
            if P.ordered:
                out = list(range(max(n - r, 0), n))
            else:
                if mode == "random":
                    score = rng.random(n)
                elif mode == "cost":
                    score = np.argsort(np.argsort(info["cost"])) / n + 0.3 * rng.random(n)
                elif mode == "regret":
                    score = -np.argsort(np.argsort(info["regret"])) / n + 0.3 * rng.random(n)
                elif mode == "late":
                    score = np.argsort(np.argsort(info["when"])) / n + 0.3 * rng.random(n)
                else:
                    score = np.where(rng.random(n) < 0.5, np.argsort(np.argsort(info["cost"])) / n, rng.random(n)) + 0.3 * rng.random(n)
                out = [int(v) for v in np.argsort(-score)[:r]]
            keep = {k: v.copy() for k, v in info.items()}
            s = P.start()
            gone = set(out)
            for v in range(n):
                if v not in gone:
                    P.assign(s, v, int(best[v]))
            if not fill(P, s, out, info, clock):
                info = keep
                continue
            c = cost(P, P.totals(s))
            if c <= c_best:
                best, c_best = P.assignment(s), c
            else:
                info = keep
    except BudgetExhausted:
        return best

for kind in sys.argv[2:]:
    E = float(sys.argv[1])
    env = environments.load(kind)
    train_ids, _ = split(env, 16, 24)
    rows, started = {}, time.process_time()
    for i in train_ids[:6]:
        P, decode = env.problem(i, Meter(float("inf")), 0, True)
        for r in (4, 12):
            for mode in ("random", "cost", "regret", "late", "mixed"):
                P.meter = Meter(P.construction_units() + E * P.n_vars * P.n_vars)
                b = run(P, np.random.default_rng(3), r, mode)
                P.meter = Meter(float("inf"))
                rows.setdefault(f"r{r} {mode}", []).append(env.score(i, decode(b)) if b is not None else 0.0)
    print(f"{kind:10s} E={E:g} n {P.n_vars}x{P.n_opts} | " + " | ".join(f"{k} {np.mean(v):.3f}" for k, v in rows.items()) + f" | cpu {time.process_time() - started:.0f}s", flush=True)
