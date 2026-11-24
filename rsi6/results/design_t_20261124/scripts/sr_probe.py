"""Scratch: how far does a fitted monomial (log-linear regression) go on the laws of the regression kind?"""
# Development script, kept as it was run (2026-11-24/25) apart from the two paths below.
# REPO: the root of the repository; DEV: a scratch directory for pools and outputs (RSI6_T_DEV).
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV = _os.environ.get("RSI6_T_DEV", "t_dev")
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import sys, warnings
warnings.filterwarnings("ignore")
import numpy as np
from rsi6 import environments
from rsi6.kernel.environment import split
from rsi6.kernel.problem import Meter
env = environments.load("regression")
train_ids, fresh_ids = split(env, 16, 24)
print("instances", len(env.instance_ids()), "train", [i for i in train_ids][:16], "\nfresh tiers", sorted({i.split('/')[0] for i in fresh_ids}), "train tiers", sorted({i.split('/')[0] for i in train_ids}))
def r2(pred, y):
    s = ((y - y.mean()) ** 2).sum()
    return float(np.clip(1 - ((pred - y) ** 2).sum() / s, 0, 1)) if s > 0 and np.all(np.isfinite(pred)) else 0.0
def monomial(X, y, Q):
    keep = X.std(axis=0) > 0
    X, Q = X[:, keep], Q[:, keep]
    if not (np.all(y > 0) or np.all(y < 0)) or np.any(X == 0) or np.any(Q == 0):
        return None
    A = np.column_stack([np.log(np.abs(X)), np.ones(len(X))])
    w = np.linalg.lstsq(A, np.log(np.abs(y)), rcond=None)[0]
    return np.sign(y[0]) * np.exp(np.column_stack([np.log(np.abs(Q)), np.ones(len(Q))]) @ w), w[:-1]
rows = []
for i in env.instance_ids():
    P = env.problem(i, Meter(float("inf")), 0, True)[0]
    X, y, Q, t = P.ctx_x, P.ctx_y, P.qry_x, P.qry_y
    d = int((X.std(axis=0) > 0).sum())
    out = monomial(X, y, Q)
    score = r2(out[0], t) if out else -1
    neg = bool(np.any(X < 0)) or bool(np.any(y < 0))
    rows.append((i, d, score, neg, None if out is None else np.round(out[1], 2).tolist()))
rows.sort(key=lambda r: -r[2])
solved = [r for r in rows if r[2] > 0.999]
print("laws", len(rows), "| monomial fit recovers (R2 > 0.999):", len(solved), "| R2 > 0.9:", sum(r[2] > 0.9 for r in rows), "| not applicable (signs/zeros):", sum(r[2] < 0 for r in rows))
for tier in ("easy", "medium", "hard"):
    mine = [r for r in rows if r[0].startswith(tier)]
    print(f"  {tier}: {len(mine)} laws, recovered {sum(r[2] > 0.999 for r in mine)}, mean R2 (not applicable = 0) {np.mean([max(r[2], 0) for r in mine]):.3f}")
print("fresh instances: recovered", sum(r[2] > 0.999 for r in rows if r[0] in fresh_ids), "of", len(fresh_ids), "mean R2", round(float(np.mean([max(r[2], 0) for r in rows if r[0] in fresh_ids])), 3))
print("not recovered, examples:")
for r in [r for r in rows if r[2] <= 0.999][:45]:
    print("  ", r[0], "vars", r[1], "R2", round(r[2], 4), "neg" if r[3] else "", r[4])
