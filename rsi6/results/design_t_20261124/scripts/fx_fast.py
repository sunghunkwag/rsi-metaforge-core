"""Scratch: the same greedy construction with every candidate of a step scored at once (rank-one updates of a ridge fit),
to see what scoring all candidates costs next to a pass (about 2.7 ms per problem: the mean CPU of one flat stage)."""
# Development script, kept as it was run (2026-11-25) apart from the two paths below.
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

def columns(cols, n):
    """All candidates over the pool: (names, matrix)."""
    k = len(cols)
    C = np.column_stack(cols)
    a = np.abs(C); low = np.where(a > 0, a, np.inf).min(axis=0) * 1e-3; low = np.where(np.isfinite(low), low, 1.0)
    safe = np.where(a > low, C, np.where(C < 0, -low, low))
    out = [np.log(np.maximum(a, low)), C * C, np.sqrt(a), 1.0 / safe]
    names = [(op, i, -1) for op in ("log", "sq", "sqrt", "inv") for i in range(k)]
    iu, ju = np.triu_indices(k, 1)
    out += [C[:, iu] * C[:, ju], C[:, iu] - C[:, ju]]
    names += [("mul", int(i), int(j)) for i, j in zip(iu, ju)] + [("sub", int(i), int(j)) for i, j in zip(iu, ju)]
    io, jo = np.nonzero(~np.eye(k, dtype=bool))
    out.append(C[:, io] / safe[:, jo])
    names += [("div", int(i), int(j)) for i, j in zip(io, jo)]
    return names, np.column_stack(out)

def construct(X, y, Q, steps=6, lam=1e-3, max_cols=12):
    keep = np.flatnonzero(X.std(axis=0) > 0)
    n = len(X)
    Z = np.vstack([X[:, keep], Q[:, keep]])
    pool = [Z[:, j] for j in range(Z.shape[1])]
    scale = T.spread(y)
    used, scored = set(), 0
    def design(cols):
        F = np.column_stack(cols); mu = F[:n].mean(0); sd = F[:n].std(0); sd = np.where(sd > 0, sd, 1.0)
        return np.clip((F - mu) / sd, -1e6, 1e6)
    chosen = list(pool)
    for step in range(steps + 1):
        F = design(chosen)
        A = np.column_stack([F[:n], np.ones(n)])
        P = lam * n * np.eye(A.shape[1]); P[-1, -1] = 0.0
        Ginv = np.linalg.inv(A.T @ A + P)
        h = np.einsum("ij,jk,ik->i", A, Ginv, A)
        fit = A @ (Ginv @ (A.T @ y))
        current = T.skill(y - (y - fit) / np.maximum(1 - h, 1e-6), y, scale)
        if step == steps:
            break
        names, V = columns(pool, n)
        ok = np.all(np.isfinite(V), axis=0) & (V[:n].std(axis=0) > 0)
        ok &= np.array([nm not in used for nm in names])
        V = V[:, ok]; names = [nm for nm, o in zip(names, ok) if o]
        if not names:
            break
        Vn = V[:n]; mu = Vn.mean(0); sd = Vn.std(0)
        Vn = np.clip((Vn - mu) / sd, -1e6, 1e6)
        U = Vn - A @ (Ginv @ (A.T @ Vn))
        s = (Vn * U).sum(axis=0) + lam * n
        fits = fit[:, None] + U * ((U.T @ y) / s)[None, :]
        hh = h[:, None] + U * U / s[None, :]
        loo = y[:, None] - (y[:, None] - fits) / np.maximum(1 - hh, 1e-6)
        skills = np.maximum(-1.0, 1.0 - np.abs(loo - y[:, None]).mean(axis=0) / scale)
        skills = np.where(np.isfinite(skills), skills, -1.0)
        scored += len(names)
        b = int(np.argmax(skills))
        if skills[b] <= current + 1e-4:
            break
        used.add(names[b])
        chosen.append(V[:, b]); pool.append(V[:, b])
    F = design(chosen)
    A = np.column_stack([F[:n], np.ones(n)]); P = lam * n * np.eye(A.shape[1]); P[-1, -1] = 0.0
    w = np.linalg.solve(A.T @ A + P, A.T @ y)
    return np.column_stack([F[n:], np.ones(len(F) - n)]) @ w, current, scored, len(chosen) - len(keep)

probs = t_pool.load("unordered")
pool = pickle.load(open(os.path.join(DEV, "pool_unordered.pkl"), "rb"))
S, kind = pool["skill"], np.array(pool["kind"])
out = {}
for j, (k, P) in enumerate(probs):
    scale = T.spread(P.ctx_y)
    best = None
    started = time.process_time()
    for ylog in (False, True):
        y, back = P.ctx_y, (lambda z: z)
        if ylog:
            if not (np.all(y > 0) or np.all(y < 0)):
                continue
            sgn = np.sign(y[0]); y = np.log(np.abs(y)); back = (lambda z, sgn=sgn: sgn * np.exp(np.clip(z, -700, 700)))
        for steps in (0, 6):
            pred, inner, scored, added = construct(P.ctx_x, y, P.qry_x, steps=steps)
            row = (inner, T.skill(back(pred), P.qry_y, scale), scored, added, steps, ylog)
            best = row if steps == 6 and (best is None or row[0] > best[0]) else best
    cpu = time.process_time() - started
    out.setdefault(k, []).append((best, cpu, P.ctx_x.shape, int((P.ctx_x.std(axis=0) > 0).sum())))
for k, lst in out.items():
    cols = kind == k
    print(f"{k:11s} pool best single {S[:, cols].mean(axis=1).max():+.3f} per-problem best {S[:, cols].max(axis=0).mean():+.3f} | built (6 steps, all candidates) {np.mean([r[0][1] for r in lst]):+.3f} "
          f"| candidates scored {np.mean([r[0][2] for r in lst]):.0f} | cpu per problem, 4 fits {1000 * np.mean([r[1] for r in lst]):.1f} ms (one 6-step fit about {1000 * np.mean([r[1] for r in lst]) / 2.6:.1f} ms = {np.mean([r[1] for r in lst]) / 2.6 / 0.0027:.1f} passes) | columns {np.mean([r[3] for r in lst]):.1f}")
