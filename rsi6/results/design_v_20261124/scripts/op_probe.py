"""Scratch: are there moves, built from the same generic parts, that are worth much more than the three arms of design v?
At the budget of a fresh problem under the registrations (2 constructions + n^2 units), on training instances:
  generic   design v's generic way
  best way  the best of the 729 ways for the kind (from the tables), where a table exists
  empty     take ALL variables off one option (at most `cap`), close that option for them, assign them again greedily
  empty+    the same, the option not closed
  block     take a run of consecutive variables off, assign them again
  mixed     empty and random repair, even shares
"""
# Development script, kept as it was run (2026-11-24) apart from the two paths below (tables in RSI6_V_DEV).
import os, os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
_sys.path.insert(0, REPO)
import sys, time, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
from rsi6 import environments
from rsi6.environments import fresh
from rsi6.kernel.environment import split
from rsi6.kernel.problem import Meter, BudgetExhausted
from rsi6.learner import design_v as V
fresh.install()

def refill(P, s, left, banned=None):
    left = list(left)
    while left:
        rows = P.candidates(s, left)
        k = V._key(P, rows)
        ok = np.broadcast_to(P.allowed(s), k.shape).copy()
        if P.domain is not None:
            ok &= P.domain[left]
        if banned is not None:
            ok[:, banned] = False
        k = np.where(ok, k, np.inf)
        if not np.isfinite(k).any(axis=1).all():
            return False
        if len(k) > 1 and k.shape[1] > 1:
            two = np.partition(k, 1, axis=1)[:, :2]
            i = int(np.argmax(np.where(np.isfinite(two[:, 1]), two[:, 1] - two[:, 0], np.inf)))
        else:
            i = 0
        P.assign(s, left[i], int(np.argmin(k[i])))
        left.pop(i)
    return True

def run(P, rng, mode, cap=24):
    best = c_best = None
    try:
        best, c_best = V.construct(P, 1)
        if best is None or P.ordered:
            return best
        while True:
            pick = mode if mode != "mixed" else ("empty" if rng.random() < 0.5 else "random")
            banned = None
            if pick in ("empty", "empty+"):
                o = int(best[int(rng.integers(P.n_vars))])
                out = np.flatnonzero(best == o)
                if len(out) > cap:
                    out = rng.choice(out, size=cap, replace=False)
                banned = o if pick == "empty" else None
            elif pick == "block":
                r = int(rng.integers(2, cap + 1)); a = int(rng.integers(P.n_vars))
                out = np.arange(a, min(a + r, P.n_vars))
            else:
                out = rng.choice(P.n_vars, size=min(8, P.n_vars), replace=False)
            gone = set(int(v) for v in out)
            s = P.start()
            for v in range(P.n_vars):
                if v not in gone:
                    P.assign(s, v, int(best[v]))
            if not refill(P, s, sorted(gone), banned):
                continue
            c = V.cost(P, P.totals(s))
            if c <= c_best:
                best, c_best = P.assignment(s), c
    except BudgetExhausted:
        return best

tables = {}
for kind in sys.argv[1:]:
    env = environments.load(kind)
    train_ids, _ = split(env, 16, 24)
    ways = V.ways()
    best_way = None
    try:
        d = json.load(open(os.path.join(os.environ.get("RSI6_V_DEV", "v_dev"), f"ways_{kind}.json")))
        best_way = ways[int(np.argmax(np.array([[[t[3] for t in p] for p in w] for w in d["results"]]).mean(axis=(1, 2))))]
    except OSError:
        pass
    rows, started = {}, time.process_time()
    for i in train_ids[:6]:
        P, decode = env.problem(i, Meter(float("inf")), 0, True)
        limit = 2 * P.construction_units() + P.n_vars * P.n_vars
        def score(b):
            return float(env.score(i, decode(b))) if b is not None and P.well_formed(b) else 0.0
        for name, mech in (("generic", V.MECH), ("best way", best_way)):
            if mech is None:
                continue
            P.meter = Meter(limit)
            rows.setdefault(name, []).append(score(V.search(P, mech, np.random.default_rng(5))[0]))
        for mode in ("empty", "empty+", "block", "mixed"):
            P.meter = Meter(limit)
            rows.setdefault(mode, []).append(score(run(P, np.random.default_rng(5), mode)))
        P.meter = Meter(float("inf"))
    print(f"{kind:11s} n {P.n_vars}x{P.n_opts} | " + " | ".join(f"{k} {np.mean(v):.4f}" for k, v in rows.items()) + f" | cpu {time.process_time() - started:.0f}s", flush=True)
