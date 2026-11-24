"""Design "t": a learner whose mechanism is what it tries first, learned from its own acquisitions.

Why another design (``rsi6/results/design_s_20261124/README.md``): where the first design stands,
what it acquires is bounded by what the weights of its policy can express. No change of how it
searches for those weights lifts it, and a version that acquires better is not a better
improver. A further attempt has to change what the learner can acquire, and has to make
improving itself the same kind of work as acquiring.

Design t works in the prediction form, where the first design acquires nothing above the
nearest observed value and where a run costs a second, so that a difference can be measured
instead of guessed at.

**What is acquired.** A capability is a small set of *programs*. A program predicts the
queries of a problem from its observed entities: for unordered problems a chain of up to three
fitted stages, each fitting what the stages before it left over (a transform of the attributes,
one of four generic models, its settings); for ordered problems a forecaster (a transform, an
optional seasonal part found in the history, one of five generic models, its settings). Each
program also says how well it does on the observed entities alone (leave-one-out for unordered
problems, the end of the history held back for ordered ones), so a capability can let, problem
by problem, the member that does best there answer. Applying a capability costs at most the
four passes the kernel allows on a fresh problem.

**How it is acquired.** One operation, used on two time scales. The learner holds a *proposal*:
a distribution over programs. In an acquisition it repeats: draw programs from the proposal,
run them on the training problems of the category, and move the proposal towards the programs
that did best (``fit`` and ``mix``). At the end it builds the capability from the programs it
tried and checks it on held-back training problems against the nearest observed value.

**What a version is.** The proposal the learner starts every acquisition from, and nothing
else of substance. Generation 0 starts from a flat proposal: every model, transform and setting
as likely as any other.

**How a version is modified.** By the same operation, one level up
(``rsi6/meta/chain_t.py``): the learner's acquisitions on the categories it may use are its
experience; the proposal it starts from is moved towards the programs that did best in them.
The improver is therefore the learner's own acquisition: what it tried, and how well it could
tell what was good, is the evidence the next version is made from. A version that acquires
better tries better programs and so leaves better evidence. Whether that is true, and whether
it carries over to kinds of problem the learner has not met, is what is measured.

``rsi6/learner/designs.py`` is pinned by hash by earlier registrations and does not name this
design; a driver calls ``install()`` first.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys

import numpy as np

from rsi6.kernel.problem import BudgetExhausted

TINY = 1e-12
PASSES = 4.0                                   # the kernel's limit on a fresh prediction problem, in passes over it
SEARCH = {"rounds": 3, "elite": 0.25, "adapt": 0.5, "holdback": 0.25, "strict": 1, "shortlist": 12}
FLOOR_P, FLOOR_SD = 0.02, 0.05                 # no choice below this probability; no spread below this share of a range
FLAT = 2.0                                     # spread of a setting in a flat proposal, in ranges of the setting

# ---- the space of programs ----------------------------------------------------------------------
U_MODELS = ("knn", "ridge", "krr", "loclin")
U_X = ("z", "log", "rank")
U_NUM = {"knn": {"K": (0.0, 6.0)}, "ridge": {"lam": (-8.0, 1.0)}, "krr": {"ell": (-3.0, 3.0), "lam": (-9.0, 0.0)},
         "loclin": {"K": (2.0, 7.0), "lam": (-8.0, 0.0)}}
U_CAT = {"knn": {"power": (0, 1, 2)}, "ridge": {"degree": (1, 2)}, "krr": {}, "loclin": {}}
SHRINK = (0.3, 1.0)
MAX_STAGES = 3
O_MODELS = ("level", "trend", "theta", "ar", "window")
O_NUM = {"level": {"alpha": (0.02, 1.0)}, "trend": {"alpha": (0.02, 1.0), "beta": (0.0, 0.5), "phi": (0.7, 1.0)},
         "theta": {"alpha": (0.02, 1.0), "w": (0.0, 1.0)}, "ar": {"p": (0.0, 5.0), "lam": (-6.0, 2.0)},
         "window": {"w": (1.0, 6.0), "phi": (0.0, 1.0)}}
O_CAT = {"level": {}, "trend": {}, "theta": {}, "ar": {"diff": (0, 1)}, "window": {}}
THR = (0.1, 0.7)
Y = ("raw", "log")


# ---- transforms -----------------------------------------------------------------------------------
def _slog(column):
    """A log-like map fitted on observed values: the logarithm if they have one sign, else asinh."""
    if np.all(column > 0):
        low = column.min() * 1e-3
        return lambda a: np.log(np.maximum(a, low))
    if np.all(column < 0):
        high = -column.max() * 1e-3
        return lambda a: -np.log(np.maximum(-a, high))
    scale = np.median(np.abs(column))
    scale = scale if scale > 0 else np.mean(np.abs(column)) + TINY
    return lambda a: np.arcsinh(a / scale)


def xmap(X, Q, how):
    keep = X.std(axis=0) > 0
    X, Q = X[:, keep], Q[:, keep]
    if X.shape[1] == 0:
        return np.zeros((len(X), 1)), np.zeros((len(Q), 1))
    if how == "log":
        maps = [_slog(X[:, j]) for j in range(X.shape[1])]
        X = np.column_stack([f(X[:, j]) for j, f in enumerate(maps)])
        Q = np.column_stack([f(Q[:, j]) for j, f in enumerate(maps)])
    elif how == "rank":
        ordered = np.sort(X, axis=0)
        rank = lambda A: np.column_stack([np.searchsorted(ordered[:, j], A[:, j], side="right") / len(ordered)
                                          for j in range(A.shape[1])])
        X, Q = rank(X), rank(Q)
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    return (X - mu) / sd, (Q - mu) / sd


def ymap(y, how):
    if how != "log":
        return np.asarray(y, dtype=float), (lambda z: z)
    f = _slog(y)
    if np.all(y > 0):
        return f(y), (lambda z: np.exp(np.clip(z, -700.0, 700.0)))
    if np.all(y < 0):
        return f(y), (lambda z: -np.exp(np.clip(z, -700.0, 700.0)))
    scale = np.median(np.abs(y))
    scale = scale if scale > 0 else np.mean(np.abs(y)) + TINY
    return f(y), (lambda z: scale * np.sinh(np.clip(z, -700.0, 700.0)))


# ---- unordered models: leave-one-out predictions on the observed, predictions on the queries -----
def _d2(A, B):
    return np.maximum((A * A).sum(1)[:, None] + (B * B).sum(1)[None, :] - 2.0 * A @ B.T, 0.0)


def _knn(X, t, Q, K, power):
    n = len(X)
    K = int(min(max(K, 1), n - 1))
    dxx = _d2(X, X)
    np.fill_diagonal(dxx, np.inf)

    def predict(dist):
        idx = np.argpartition(dist, K - 1, axis=1)[:, :K]
        dd = np.take_along_axis(dist, idx, axis=1)
        w = np.ones_like(dd) if power == 0 else 1.0 / (dd ** (power / 2.0) + 1e-9)
        return (w * t[idx]).sum(1) / w.sum(1)

    return predict(dxx), predict(_d2(Q, X))


def _poly(A, degree, cap=120):
    cols = [np.ones(len(A))] + [A[:, j] for j in range(A.shape[1])]
    if degree == 2:
        d = A.shape[1]
        pairs = [(i, j) for i in range(d) for j in range(i, d)]
        for i, j in pairs[:max(0, cap - len(cols))]:
            cols.append(A[:, i] * A[:, j])
    return np.column_stack(cols)


def _ridge(X, t, Q, degree, lam):
    F, G = _poly(X, degree), _poly(Q, degree)
    n, p = F.shape
    reg = lam * n * np.eye(p)
    reg[0, 0] = 0.0
    A = np.linalg.solve(F.T @ F + reg + 1e-10 * np.eye(p), F.T)
    w = A @ t
    h = np.einsum("ij,ji->i", F, A)
    fitted = F @ w
    return (fitted - h * t) / np.maximum(1.0 - h, 1e-6), G @ w


def _krr(X, t, Q, ell, lam):
    n = len(X)
    dxx = _d2(X, X)
    med = np.median(dxx[dxx > 0]) if np.any(dxx > 0) else 1.0
    s = 2.0 * ell * ell * med
    m = t.mean()
    C = np.linalg.inv(np.exp(-dxx / s) + (lam * n + 1e-10) * np.eye(n))
    alpha = C @ (t - m)
    return t - alpha / np.maximum(np.diag(C), TINY), np.exp(-_d2(Q, X) / s) @ alpha + m


def _loclin(X, t, Q, K, lam):
    n, d = X.shape
    K = int(min(max(K, d + 2), n - 1))
    dxx = _d2(X, X)
    np.fill_diagonal(dxx, np.inf)

    def predict(P, dist):
        idx = np.argpartition(dist, K - 1, axis=1)[:, :K]
        dd = np.take_along_axis(dist, idx, axis=1)
        w = (1.0 - (dd / (dd.max(axis=1, keepdims=True) + TINY)) ** 1.5) ** 3 + 1e-6
        Z = np.concatenate([np.ones((len(P), K, 1)), X[idx] - P[:, None, :]], axis=2)
        WZ = Z * w[:, :, None]
        A = np.einsum("mki,mkj->mij", WZ, Z) + lam * K * np.eye(d + 1)[None]
        A[:, 0, 0] -= lam * K
        A += 1e-9 * np.eye(d + 1)[None]
        return np.linalg.solve(A, np.einsum("mki,mk->mi", WZ, t[idx])[:, :, None])[:, 0, 0]

    return predict(X, dxx), predict(Q, _d2(Q, X))


def _stage(X, t, Q, s):
    if s["model"] == "knn":
        return _knn(X, t, Q, int(round(2.0 ** s["K"])), s["power"])
    if s["model"] == "ridge":
        return _ridge(X, t, Q, s["degree"], 10.0 ** s["lam"])
    if s["model"] == "krr":
        return _krr(X, t, Q, 2.0 ** s["ell"], 10.0 ** s["lam"])
    return _loclin(X, t, Q, int(round(2.0 ** s["K"])), 10.0 ** s["lam"])


def _run_unordered(program, ctx_x, ctx_y, qry_x):
    t, back = ymap(ctx_y, program["y"])
    inner, out, left = np.zeros(len(t)), np.zeros(len(qry_x)), t.copy()
    for k, s in enumerate(program["stages"]):
        X, Q = xmap(ctx_x, qry_x, s["x"])
        loo, q = _stage(X, left, Q, s)
        shrink = 1.0 if k == 0 else s["shrink"]
        inner, out = inner + shrink * loo, out + shrink * q
        left = t - inner
    return back(inner), ctx_y, back(out)


# ---- ordered models -----------------------------------------------------------------------------
def _period(t, thr):
    n = len(t)
    if n < 12:
        return 0
    d = np.diff(t)
    d = d - d.mean()
    den = float((d * d).sum())
    if den <= 0.0:
        return 0
    top = min(n // 3, 200)
    acf = np.correlate(d, d, mode="full")[len(d) - 1:] / den
    lags = np.arange(2, top + 1)
    if len(lags) == 0:
        return 0
    k = int(lags[np.argmax(acf[2:top + 1])])
    return k if acf[k] > thr else 0


def _seasonal(t, p):
    n = len(t)
    kernel = np.ones(p) / p
    smooth = np.convolve(t, kernel, mode="same") / np.convolve(np.ones(n), kernel, mode="same")
    rest = t - smooth
    index = np.array([rest[k::p].mean() for k in range(p)])
    return index - index.mean()


def _forecast(program, y, h):
    t, back = ymap(y, program["y"])
    n = len(t)
    p = _period(t, program["thr"]) if program["season"] else 0
    index = _seasonal(t, p) if p else None
    z = t - index[np.arange(n) % p] if p else t
    steps = np.arange(1, h + 1)
    model = program["model"]
    if model == "level":
        level = z[0]
        for v in z[1:]:
            level = program["alpha"] * v + (1.0 - program["alpha"]) * level
        f = np.full(h, level)
    elif model == "trend":
        a, b, phi = program["alpha"], program["beta"], program["phi"]
        level, slope = z[0], (z[1] - z[0] if n > 1 else 0.0)
        for v in z[1:]:
            last = level
            level = a * v + (1.0 - a) * (level + phi * slope)
            slope = b * (level - last) + (1.0 - b) * phi * slope
        f = level + slope * np.cumsum(phi ** steps)
    elif model == "theta":
        level = z[0]
        for v in z[1:]:
            level = program["alpha"] * v + (1.0 - program["alpha"]) * level
        slope = np.polyfit(np.arange(n), z, 1)[0] if n > 2 else 0.0
        f = level + program["w"] * slope * steps
    elif model == "ar":
        order = int(min(max(int(round(2.0 ** program["p"])), 1), max(1, n // 3)))
        s = np.diff(z) if program["diff"] else z - z.mean()
        if len(s) <= order + 1:
            f = np.full(h, z[-1])
        else:
            rows = np.column_stack([s[order - k - 1:len(s) - k - 1] for k in range(order)])
            target = s[order:]
            coef = np.linalg.solve(rows.T @ rows + (10.0 ** program["lam"]) * len(target) * np.eye(order) + 1e-10 * np.eye(order),
                                   rows.T @ target)
            hist, out = list(s[-order:][::-1]), []
            for _ in range(h):
                nxt = float(np.dot(coef, hist[:order]))
                out.append(nxt)
                hist.insert(0, nxt)
            f = z[-1] + np.cumsum(out) if program["diff"] else z.mean() + np.array(out)
    else:
        w = int(min(max(int(round(2.0 ** program["w"])), 2), n))
        tail = z[-w:]
        slope = np.polyfit(np.arange(w), tail, 1)[0] if w > 2 else 0.0
        f = tail.mean() + program["phi"] * slope * (steps + (w - 1) / 2.0)
    if p:
        f = f + index[(n + steps - 1) % p]
    f = back(f)
    return np.where(np.isfinite(f), f, y[-1])


def _run_ordered(program, ctx_y, n_queries):
    """The forecast of the queries, and the forecast of the end of the history from what came before it."""
    n = len(ctx_y)
    h = int(min(n_queries, n // 3))
    out = _forecast(program, ctx_y, n_queries)
    if h < 1 or n - h < 4:
        return None, None, out
    return _forecast(program, ctx_y[:-h], h), ctx_y[-h:], out


SNAP_AT_MOST = 8


def _snap(program, ctx_y, *predictions):
    """With ``snap`` on and at most ``SNAP_AT_MOST`` different observed targets, every prediction becomes the
    nearest of the values the observed targets take."""
    if not program.get("snap"):
        return predictions
    values = np.unique(ctx_y)
    if len(values) > SNAP_AT_MOST:
        return predictions
    return tuple(None if p is None else values[np.argmin(np.abs(np.asarray(p)[:, None] - values[None, :]), axis=1)]
                 for p in predictions)


def passes(program, backtest=True) -> int:
    """Passes over a problem one run of the program costs."""
    if program["form"] == "u":
        return len(program["stages"])
    return 2 if backtest else 1


def run(program, ctx_x, ctx_y, qry_x, backtest=True):
    """``(inner predictions, their targets, predictions of the queries)``; the first two are ``None`` when the
    observed entities do not allow an inner check."""
    if program["form"] == "u":
        inner, target, out = _run_unordered(program, ctx_x, ctx_y, qry_x)
    elif not backtest:
        inner, target, out = None, None, _forecast(program, ctx_y, len(qry_x))
    else:
        inner, target, out = _run_ordered(program, ctx_y, len(qry_x))
    inner, out = _snap(program, ctx_y, inner, out)
    return inner, target, out


def anchor(ctx_x, ctx_y, qry_x, ordered):
    """The answer without a capability: the last observed value, or the target of the nearest observed entity."""
    if ordered:
        return np.full(len(qry_x), ctx_y[-1])
    X, Q = xmap(ctx_x, qry_x, "z")
    return ctx_y[np.argmin(_d2(Q, X), axis=1)]


def skill(prediction, target, scale) -> float:
    """One minus the mean absolute error in units of the spread of the observed targets; at least -1."""
    if prediction is None or not np.all(np.isfinite(prediction)):
        return -1.0
    return float(max(-1.0, 1.0 - np.mean(np.abs(prediction - target)) / scale))


def spread(ctx_y) -> float:
    return float(np.mean(np.abs(ctx_y - np.median(ctx_y))) + TINY)


# ---- proposals ----------------------------------------------------------------------------------
def _flat_num(table):
    return {m: {k: [(lo + hi) / 2.0, FLAT * (hi - lo)] for k, (lo, hi) in ps.items()} for m, ps in table.items()}


def _flat_cat(table):
    return {m: {k: [1.0 / len(c)] * len(c) for k, c in ps.items()} for m, ps in table.items()}


def flat_proposal() -> dict:
    """Generation 0: every model, transform and setting as likely as any other."""
    def position():
        return {"model": [1.0 / len(U_MODELS)] * len(U_MODELS), "x": {m: [1.0 / len(U_X)] * len(U_X) for m in U_MODELS},
                "num": _flat_num(U_NUM), "cat": _flat_cat(U_CAT)}
    later = position()
    later["shrink"] = [(SHRINK[0] + SHRINK[1]) / 2.0, FLAT * (SHRINK[1] - SHRINK[0])]
    return {"unordered": {"y": [0.5, 0.5], "snap": [0.5, 0.5], "stages": [1.0 / MAX_STAGES] * MAX_STAGES, "first": position(),
                          "later": later},
            "ordered": {"y": [0.5, 0.5], "snap": [0.5, 0.5], "season": [0.5, 0.5], "thr": [(THR[0] + THR[1]) / 2.0, FLAT * (THR[1] - THR[0])],
                        "model": [1.0 / len(O_MODELS)] * len(O_MODELS), "num": _flat_num(O_NUM), "cat": _flat_cat(O_CAT)}}


def _draw(rng, pair, bounds) -> float:
    lo, hi = bounds
    for _ in range(8):
        x = pair[0] + pair[1] * rng.standard_normal()
        if lo <= x <= hi:
            return round(float(x), 5)
    return round(float(rng.uniform(lo, hi)), 5)          # a proposal far outside its range falls back to the range


def _pick(rng, probabilities) -> int:
    return int(rng.choice(len(probabilities), p=np.asarray(probabilities) / np.sum(probabilities)))


def sample(proposal, form, rng) -> dict:
    """One program drawn from a proposal; ``form`` is ``"unordered"`` or ``"ordered"``."""
    q = proposal[form]
    if form == "ordered":
        model = O_MODELS[_pick(rng, q["model"])]
        program = {"form": "o", "y": Y[_pick(rng, q["y"])], "snap": _pick(rng, q["snap"]), "season": _pick(rng, q["season"]),
                   "thr": _draw(rng, q["thr"], THR), "model": model}
        for k, bounds in O_NUM[model].items():
            program[k] = _draw(rng, q["num"][model][k], bounds)
        for k, choices in O_CAT[model].items():
            program[k] = choices[_pick(rng, q["cat"][model][k])]
        return program
    stages = []
    for k in range(1 + _pick(rng, q["stages"])):
        part = q["first" if k == 0 else "later"]
        model = U_MODELS[_pick(rng, part["model"])]
        s = {"model": model, "x": U_X[_pick(rng, part["x"][model])]}
        for name, bounds in U_NUM[model].items():
            s[name] = _draw(rng, part["num"][model][name], bounds)
        for name, choices in U_CAT[model].items():
            s[name] = choices[_pick(rng, part["cat"][model][name])]
        if k > 0:
            s["shrink"] = _draw(rng, part["shrink"], SHRINK)
        stages.append(s)
    return {"form": "u", "y": Y[_pick(rng, q["y"])], "snap": _pick(rng, q["snap"]), "stages": stages}


def _share(values, weights, n):
    out = np.full(n, 1e-9)
    for v, w in zip(values, weights):
        out[v] += w
    return (out / out.sum()).tolist()


def _moment(values, weights, bounds):
    if not values:
        return None
    v, w = np.asarray(values, dtype=float), np.asarray(weights, dtype=float)
    mean = float((w * v).sum() / w.sum())
    sd = float(np.sqrt((w * (v - mean) ** 2).sum() / w.sum()))
    return [mean, max(sd, FLOOR_SD * (bounds[1] - bounds[0]))]


def fit(programs, weights, form) -> dict:
    """The proposal that is the weighted programs themselves: shares of their choices, means and spreads of
    their settings. A part no program uses is ``None`` (``mix`` then keeps what was there)."""
    w = list(weights)
    if form == "ordered":
        out = {"y": _share([Y.index(p["y"]) for p in programs], w, 2), "snap": _share([p["snap"] for p in programs], w, 2),
               "season": _share([p["season"] for p in programs], w, 2),
               "thr": _moment([p["thr"] for p in programs], w, THR),
               "model": _share([O_MODELS.index(p["model"]) for p in programs], w, len(O_MODELS)), "num": {}, "cat": {}}
        for m in O_MODELS:
            mine = [(p, x) for p, x in zip(programs, w) if p["model"] == m]
            out["num"][m] = {k: _moment([p[k] for p, _ in mine], [x for _, x in mine], b) for k, b in O_NUM[m].items()}
            out["cat"][m] = {k: (_share([c.index(p[k]) for p, _ in mine], [x for _, x in mine], len(c)) if mine else None)
                             for k, c in O_CAT[m].items()}
        return out
    out = {"y": _share([Y.index(p["y"]) for p in programs], w, 2), "snap": _share([p["snap"] for p in programs], w, 2),
           "stages": _share([len(p["stages"]) - 1 for p in programs], w, MAX_STAGES)}
    for name in ("first", "later"):
        stages = [(s, x) for p, x in zip(programs, w) for k, s in enumerate(p["stages"]) if (k == 0) == (name == "first")]
        part = {"model": (_share([U_MODELS.index(s["model"]) for s, _ in stages], [x for _, x in stages], len(U_MODELS))
                          if stages else None), "x": {}, "num": {}, "cat": {}}
        for m in U_MODELS:
            mine = [(s, x) for s, x in stages if s["model"] == m]
            part["x"][m] = _share([U_X.index(s["x"]) for s, _ in mine], [x for _, x in mine], len(U_X)) if mine else None
            part["num"][m] = {k: _moment([s[k] for s, _ in mine], [x for _, x in mine], b) for k, b in U_NUM[m].items()}
            part["cat"][m] = {k: (_share([c.index(s[k]) for s, _ in mine], [x for _, x in mine], len(c)) if mine else None)
                              for k, c in U_CAT[m].items()}
        if name == "later":
            part["shrink"] = _moment([s["shrink"] for s, _ in stages], [x for _, x in stages], SHRINK)
        out[name] = part
    return out


NUMERIC = ("num", "thr", "shrink")                      # parts of a proposal that are [mean, spread] of a setting


def mix(old, new, rate, numeric=False):
    """Move a proposal (one form's part) towards another: ``(1 - rate) * old + rate * new``, part by part; a
    part the other does not have stays; no probability falls below ``FLOOR_P``."""
    if new is None:
        return copy.deepcopy(old)
    if isinstance(old, dict):
        return {k: mix(old[k], new.get(k), rate, numeric or k in NUMERIC) for k in old}
    blended = [(1.0 - rate) * a + rate * b for a, b in zip(old, new)]
    if numeric:
        return blended
    blended = np.maximum(np.asarray(blended), FLOOR_P)
    return (blended / blended.sum()).tolist()


# ---- versions -----------------------------------------------------------------------------------
def default() -> dict:
    return {"design": "t", "search": dict(SEARCH), "proposal": flat_proposal()}


def _rounded(x):
    if isinstance(x, dict):
        return {k: _rounded(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_rounded(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    return x


def _same_shape(a, b) -> bool:
    if isinstance(a, dict):
        return isinstance(b, dict) and set(a) == set(b) and all(_same_shape(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(isinstance(x, (int, float)) for x in b)
    return isinstance(b, (int, float))


def validate(version: dict) -> dict:
    if version.get("design") != "t" or set(version) != {"design", "search", "proposal"}:
        raise ValueError("not a version of design t")
    if set(version["search"]) != set(SEARCH):
        raise ValueError("search settings differ from the schema")
    s = version["search"]
    if not (1 <= int(s["rounds"]) <= 8 and 0.05 <= s["elite"] <= 0.9 and 0.0 <= s["adapt"] <= 1.0 and 0.0 < s["holdback"] <= 0.5
            and s["strict"] in (0, 1) and 2 <= int(s["shortlist"]) <= 64):
        raise ValueError("search settings out of range")
    if not _same_shape(flat_proposal(), version["proposal"]):
        raise ValueError("the proposal has not the layout of a proposal")
    return _rounded(version)


def digest(version: dict) -> str:
    return hashlib.sha256(json.dumps(validate(version), separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def _leaves(x, trail=""):
    if isinstance(x, dict):
        for k in sorted(x):
            yield from _leaves(x[k], f"{trail}.{k}" if trail else str(k))
    else:
        yield trail, x


def differences(a: dict, b: dict) -> dict:
    """The parts of two versions that differ, by path; every part of a proposal belongs to exploring."""
    left, right = dict(_leaves(validate(a))), dict(_leaves(validate(b)))
    return {k: {"from": left[k], "to": right[k], "function": "explore" if k.startswith("proposal") else "decide"}
            for k in left if left[k] != right[k]}


FIELDS = ("search", "proposal")
SCHEMA = {}                                             # design t has no closed list of field values


def install() -> None:
    """Make the kernel's dispatch know design t in this process (and the workers it forks)."""
    from rsi6.learner import designs
    if getattr(designs, "_t_installed", False):
        return
    make, module = designs.make, designs._module
    here = sys.modules[__name__]
    designs.make = lambda version: LearnerT(version) if version.get("design") == "t" else make(version)
    designs._module = lambda version: here if version.get("design") == "t" else module(version)
    designs._t_installed = True


# ---- the learner --------------------------------------------------------------------------------
def combine(inner_skills, predictions, rule, base=None):
    """The answer of a set of programs on one problem: the mean of their predictions, or the prediction of the
    member that does best on the observed entities. Under ``select`` the nearest observed value competes too
    (``base``: its skill on the observed entities and its answer), so a capability falls back to it, problem by
    problem, where no member does better there."""
    if rule == "mean":
        return np.mean(predictions, axis=0)
    k = int(np.argmax(inner_skills))
    if base is not None and base[0] >= inner_skills[k]:
        return base[1]
    return predictions[k]


def anchor_inner(ctx_x, ctx_y, ordered, n_queries, scale):
    """How well the answer without a capability does on the observed entities alone: every observed entity
    predicted by its nearest other one, or the end of the history by the value before it."""
    if ordered:
        h = int(min(n_queries, len(ctx_y) // 3))
        if h < 1 or len(ctx_y) - h < 4:
            return -1.0
        return skill(np.full(h, ctx_y[-h - 1]), ctx_y[-h:], scale)
    X, _ = xmap(ctx_x, ctx_x[:1], "z")
    d = _d2(X, X)
    np.fill_diagonal(d, np.inf)
    return skill(ctx_y[np.argmin(d, axis=1)], ctx_y, scale)


def build(tried, n_problems, targets, scales, shortlist, bases):
    """The capability an acquisition ends on: grown one member at a time from the best programs tried, for each
    way of combining, within the passes a fresh problem allows. ``bases[j]`` is the nearest observed value on
    problem ``j`` (its skill on the observed entities, its answer). Returns ``(members, rule, skill)``."""
    order = sorted(range(len(tried)), key=lambda i: -tried[i]["skill"])[:shortlist]

    def value(members, rule):
        total = 0.0
        for j in range(n_problems):
            answer = combine([tried[i]["inner"][j] for i in members], [tried[i]["answers"][j] for i in members], rule, bases[j])
            total += skill(answer, targets[j], scales[j])
        return total / n_problems

    best = None
    for rule in ("select", "mean"):
        members, used, current = [], 0.0, -np.inf
        while True:
            options = [(value(members + [i], rule), i) for i in order
                       if i not in members and used + passes(tried[i]["program"], rule == "select") <= PASSES]
            if not options:
                break
            top, i = max(options)
            if members and top <= current + 1e-9:
                break
            members.append(i)
            used += passes(tried[i]["program"], rule == "select")
            current = top
        if members and (best is None or current > best[2] + 1e-9):
            best = (members, rule, current)
    return best


class LearnerT:
    """Acquires, for one category of prediction problems, a small set of programs and a way to combine them."""

    def __init__(self, version: dict):
        self.v = validate(version)
        self.trace = {}

    # the kernel's two calls
    def acquire(self, problems, rng, memory=None):
        """``(capability, memory, report)`` from the training problems of one category. The memory is handed back
        as it came: this design keeps nothing between categories."""
        memory = {"entries": list((memory or {}).get("entries", []))}
        capability, report = self._acquire(problems, rng)
        return capability, memory, report

    def _acquire(self, problems, rng):
        if not problems or problems[0].kind != "predict":
            return None, {"form": "assign", "failed": "design t acquires in the prediction form only", "learned": False,
                          "iterations": 0}
        s = self.v["search"]
        n = len(problems)
        order = rng.permutation(n)
        n_check = min(max(1, int(round(s["holdback"] * n))), n - 1) if n > 1 else 0
        check, fit_ids = [int(i) for i in order[:n_check]], [int(i) for i in order[n_check:]]
        form = "ordered" if problems[0].ordered else "unordered"
        meter = problems[0].meter
        units = [P.construction_units() for P in problems]
        fit_units, reserve = sum(units[i] for i in fit_ids), PASSES * sum(units[i] for i in check)
        scales = [spread(problems[i].ctx_y) for i in fit_ids]
        targets = [problems[i].qry_y for i in fit_ids]
        proposal, tried = {form: copy.deepcopy(self.v["proposal"][form])}, []
        report = {"form": "predict", "fit": len(fit_ids), "held_back": len(check), "iterations": 0, "failed": None, "tried": 0}
        rounds = int(s["rounds"])
        share = (meter.left() - reserve) / rounds
        try:
            for r in range(rounds):
                spent, out_of_budget = 0.0, False
                while spent < share:                       # a round ends when its share of the budget is used
                    program = sample(proposal, form, rng)
                    cost = passes(program) * fit_units
                    if meter.left() - reserve < cost:
                        out_of_budget = True
                        break
                    row = {"program": program, "inner": [], "answers": [], "skill": 0.0}
                    for j, i in enumerate(fit_ids):
                        P = problems[i]
                        meter.charge(passes(program) * units[i])
                        try:
                            inner, inner_target, answer = run(program, P.ctx_x, P.ctx_y, P.qry_x)
                        except (np.linalg.LinAlgError, FloatingPointError, ValueError, ZeroDivisionError):
                            inner, inner_target, answer = None, None, np.full(P.n_queries, np.nan)
                        row["inner"].append(skill(inner, inner_target, scales[j]) if inner is not None else -1.0)
                        row["answers"].append(answer)
                        row["skill"] += skill(answer, targets[j], scales[j]) / len(fit_ids)
                    tried.append(row)
                    spent += cost
                report["iterations"] = r + 1
                if out_of_budget:
                    break
                if r < rounds - 1 and len(tried) >= 2:
                    ranked = sorted(tried, key=lambda row: -row["skill"])
                    elite = ranked[:max(2, int(round(s["elite"] * len(ranked))))]
                    proposal[form] = mix(proposal[form], fit([row["program"] for row in elite], [1.0] * len(elite), form), s["adapt"])
        except BudgetExhausted:
            report["failed"] = "decide: the budget ended inside a run"
        report["tried"] = len(tried)
        report["trace"] = [[row["program"], round(row["skill"], 6)] for row in tried]
        if not tried:
            report.update(failed=report["failed"] or "decide: the budget did not allow one program", learned=False)
            return None, report
        bases = []
        for j, i in enumerate(fit_ids):
            P = problems[i]
            bases.append((anchor_inner(P.ctx_x, P.ctx_y, P.ordered, P.n_queries, scales[j]),
                          anchor(P.ctx_x, P.ctx_y, P.qry_x, P.ordered)))
        members, rule, value = build(tried, len(fit_ids), targets, scales, int(s["shortlist"]), bases)
        capability = {"kind": "predict", "design": "t", "rule": rule, "programs": [tried[i]["program"] for i in members],
                      "learned": True}
        report.update(members=len(members), rule=rule, fit_skill=round(value, 6))
        if n_check:
            try:
                mine, base = [], []
                for i in check:
                    P = problems[i]
                    scale = spread(P.ctx_y)
                    mine.append(skill(self.apply(capability, P, rng), P.qry_y, scale))
                    base.append(skill(anchor(P.ctx_x, P.ctx_y, P.qry_x, P.ordered), P.qry_y, scale))
                report["held_back_start"], report["held_back_learned"] = float(np.mean(base)), float(np.mean(mine))
                if s["strict"] and not np.mean(mine) > np.mean(base):
                    report["failed"] = "model: the acquired programs did not beat the nearest observed value on held-back problems"
                    capability = {"kind": "predict", "design": "t", "rule": rule, "programs": [], "learned": False}
            except BudgetExhausted:
                report["failed"] = "decide: the budget ended inside the held-back check"
                capability = {"kind": "predict", "design": "t", "rule": rule, "programs": [], "learned": False}
        report["learned"] = bool(capability["learned"])
        return capability, report

    def apply(self, capability, P, rng=None):
        base = anchor(P.ctx_x, P.ctx_y, P.qry_x, P.ordered)
        if not capability or not capability.get("learned") or not capability.get("programs"):
            return base
        select = capability["rule"] == "select"
        scale = spread(P.ctx_y)
        inner_skills, answers = [], []
        for program in capability["programs"]:
            P.meter.charge(passes(program, select) * P.construction_units())
            try:
                inner, inner_target, answer = run(program, P.ctx_x, P.ctx_y, P.qry_x, backtest=select)
            except (np.linalg.LinAlgError, FloatingPointError, ValueError, ZeroDivisionError):
                continue
            if not np.all(np.isfinite(answer)):
                continue
            inner_skills.append(skill(inner, inner_target, scale) if inner is not None else -1.0)
            answers.append(answer)
        if not answers:
            return base
        mine = (anchor_inner(P.ctx_x, P.ctx_y, P.ordered, P.n_queries, scale), base) if select else None
        return combine(inner_skills, answers, capability["rule"], mine)
