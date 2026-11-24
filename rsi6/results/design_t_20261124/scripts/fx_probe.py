"""Scratch (pre-study): what is constructing attributes worth on the development kinds?
Greedy forward construction: candidates are one-argument maps of a column and two-argument combinations of columns (and, at
depth 2, of constructed attributes); each step adds the candidate that most raises the leave-one-out skill of a ridge fit;
compared with the ridge on the columns as they are and with the best of the 600 programs of the pool."""
# Development script, kept as it was run (2026-11-24) apart from the two paths below.
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV = _os.environ.get("RSI6_T_DEV", "t_dev")
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os
import pickle, sys, time, warnings
warnings.filterwarnings("ignore")
import numpy as np
from rsi6.learner import design_t as T
import t_pool

def zs(A):
    mu, sd = A.mean(0), A.std(0)
    return mu, np.where(sd > 0, sd, 1.0)

def loo_ridge(F, y, lam=1e-3):
    """Leave-one-out predictions of a ridge fit on F (with intercept)."""
    A = np.column_stack([F, np.ones(len(F))])
    G = A.T @ A + lam * len(F) * np.eye(A.shape[1])
    G[-1, -1] -= lam * len(F)
    try:
        Ginv = np.linalg.inv(G)
    except np.linalg.LinAlgError:
        return None
    H = np.einsum("ij,jk,ik->i", A, Ginv, A)
    fit = A @ (Ginv @ (A.T @ y))
    return y - (y - fit) / np.maximum(1 - H, 1e-6)

def unary(col):
    out = {}
    a = np.abs(col)
    pos = a[a > 0]
    low = pos.min() * 1e-3 if len(pos) else 1.0
    out["log"] = np.log(np.maximum(a, low))
    out["sq"] = col * col
    out["sqrt"] = np.sqrt(a)
    out["inv"] = 1.0 / np.where(a > low, col, np.sign(col + 1e-300) * low)
    return out

def candidates(cols, names, depth_tag):
    out = []
    d = len(cols)
    for i in range(d):
        for op, v in unary(cols[i]).items():
            out.append((f"{op}({names[i]})", v))
    for i in range(d):
        for j in range(i + 1, d):
            out.append((f"{names[i]}*{names[j]}", cols[i] * cols[j]))
            out.append((f"{names[i]}-{names[j]}", cols[i] - cols[j]))
        for j in range(d):
            if i != j:
                den = cols[j]
                a = np.abs(den); pos = a[a > 0]; low = pos.min() * 1e-3 if len(pos) else 1.0
                out.append((f"{names[i]}/{names[j]}", cols[i] / np.where(a > low, den, low)))
    return out

def construct(X, y, Q, steps=6, depth=1, ylog=False, max_cols=12):
    keep = np.flatnonzero(X.std(axis=0) > 0)
    if len(keep) > max_cols:                                    # the columns most related to the target, by rank correlation
        r = [abs(np.corrcoef(np.argsort(np.argsort(X[:, j])), np.argsort(np.argsort(y)))[0, 1]) for j in keep]
        keep = keep[np.argsort(r)[-max_cols:]]
    Z = np.vstack([X[:, keep], Q[:, keep]])
    n = len(X)
    t = y
    back = lambda z: z
    if ylog and (np.all(y > 0) or np.all(y < 0)):
        s = np.sign(y[0]); t = np.log(np.abs(y)); back = lambda z: s * np.exp(np.clip(z, -700, 700))
    scale = T.spread(y)
    base_cols = [Z[:, j] for j in range(Z.shape[1])]
    names = [f"x{j}" for j in range(Z.shape[1])]
    chosen_cols, chosen_names = list(base_cols), list(names)
    def score(cols):
        F = np.column_stack(cols)
        mu, sd = zs(F[:n])
        F = (F - mu) / sd
        F = np.clip(F, -1e6, 1e6)
        p = loo_ridge(F[:n], t)
        if p is None or not np.all(np.isfinite(p)):
            return -1.0, None
        return T.skill(back(p), y, scale), F
    best, F = score(chosen_cols)
    tried = 0
    pool_cols, pool_names = list(base_cols), list(names)
    for step in range(steps):
        cands = candidates(pool_cols, pool_names, depth)
        top = None
        for name, v in cands:
            if name in chosen_names or not np.all(np.isfinite(v)) or v[:n].std() == 0:
                continue
            tried += 1
            s, _ = score(chosen_cols + [v])
            if top is None or s > top[0]:
                top = (s, name, v)
        if top is None or top[0] <= best + 1e-4:
            break
        best = top[0]
        chosen_cols.append(top[2]); chosen_names.append(top[1])
        if depth > 1:
            pool_cols.append(top[2]); pool_names.append("(" + top[1] + ")")
    F = np.column_stack(chosen_cols)
    mu, sd = zs(F[:n]); F = np.clip((F - mu) / sd, -1e6, 1e6)
    A = np.column_stack([F[:n], np.ones(n)])
    lam = 1e-3
    G = A.T @ A + lam * n * np.eye(A.shape[1]); G[-1, -1] -= lam * n
    w = np.linalg.solve(G, A.T @ t)
    pred = back(np.column_stack([F[n:], np.ones(len(F) - n)]) @ w)
    return pred, best, chosen_names[len(names):], tried

def main():
    probs = t_pool.load("unordered")
    pool = pickle.load(open(os.path.join(DEV, "pool_unordered.pkl"), "rb"))
    S, kind = pool["skill"], np.array(pool["kind"])
    rows = {}
    for j, (k, P) in enumerate(probs):
        scale = T.spread(P.ctx_y)
        res = {}
        for label, kw in (("ridge", dict(steps=0)), ("built d1", dict(steps=6, depth=1)), ("built d2", dict(steps=6, depth=2))):
            best = None
            for ylog in (False, True):
                started = time.process_time()
                pred, inner, names, tried = construct(P.ctx_x, P.ctx_y, P.qry_x, ylog=ylog, **kw)
                cand = (inner, T.skill(pred, P.qry_y, scale), names, tried, time.process_time() - started)
                if best is None or cand[0] > best[0]:
                    best = cand                                           # the y map is chosen on the observed entities alone
            res[label] = best
        rows.setdefault(k, []).append((res, S[:, j].max(), j))
        if j < 3 or (k == "friedman" and len(rows[k]) <= 3):
            print(k, j, {a: (round(b[1], 3), b[2][:6], b[3], round(b[4], 2)) for a, b in res.items()}, flush=True)
    for k, lst in rows.items():
        cols = kind == k
        best_single = S[:, cols].mean(axis=1).max()
        print(f"{k:11s} pool: best single program {best_single:+.3f}, per-problem best {np.mean([r[1] for r in lst]):+.3f} | " +
              " | ".join(f"{a} {np.mean([r[0][a][1] for r in lst]):+.3f} (tried {np.mean([r[0][a][3] for r in lst]):.0f}, cpu {np.mean([r[0][a][4] for r in lst]):.2f}s)" for a in ("ridge", "built d1", "built d2")))

main()
