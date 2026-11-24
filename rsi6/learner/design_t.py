"""Design "t": a learner whose mechanism is what it tries first, made from its own acquisitions.

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
by problem, the member that does best there answer, or the nearest observed value if none
does better. Applying a capability costs at most the four passes the kernel allows on a fresh
problem.

**How it is acquired.** The learner tries programs on the training problems of the category
until its budget ends: first the programs of its *library*, in order, for at most half of what
the run can spend; then, as long as budget is left, either the best program so far with one
small change (``vary``) or the next program its *model* proposes (``propose``; a program drawn
evenly from the whole space when it has no model). From everything it tried it builds the
capability (``build``: grown one member at a time, each chosen for what it adds to the others)
and checks it on held-back training problems against the nearest observed value.

**What a version is.** What the learner knows about its own programs: the library (at most
``slots`` programs per form); what it remembers (programs with their skill where they were
tried); and a model that says, from the settings of a program, how well it is likely to do
(``features``: a program is an entity with attributes like any other). Generation 0 knows
nothing: everything it tries is drawn evenly or varied from what it just found.

**How a version is modified.** By the learner itself (``rsi6/meta/chain_t.py``). The library is
built from the programs its acquisitions ended on, as a capability is built from programs. The
model is *acquired*: the remembered programs are made into prediction problems (``landscape``)
and the learner runs one ordinary acquisition on them (``self_model``). So the improver is the
learner applied to itself, and a learner that acquires better makes a better model of its own
programs. Whether that is true, whether anything follows from it, and whether it carries over
to kinds of problem the learner has not met is what is measured; the development readings are
in ``rsi6/results/design_t_20261124/README.md``.

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


# ---- drawing and varying programs ----------------------------------------------------------------
STEP = 0.15                                    # a varied setting moves by about this share of its range


def _even(rng, bounds) -> float:
    return round(float(rng.uniform(bounds[0], bounds[1])), 5)


def _one(rng, choices):
    return choices[int(rng.integers(len(choices)))]


def _stage_u(rng, later: bool) -> dict:
    model = _one(rng, U_MODELS)
    s = {"model": model, "x": _one(rng, U_X)}
    for name, bounds in U_NUM[model].items():
        s[name] = _even(rng, bounds)
    for name, choices in U_CAT[model].items():
        s[name] = _one(rng, choices)
    if later:
        s["shrink"] = _even(rng, SHRINK)
    return s


def _model_o(rng, program: dict) -> dict:
    for name in list(program):
        if name not in ("form", "y", "snap", "season", "thr"):
            del program[name]
    program["model"] = _one(rng, O_MODELS)
    for name, bounds in O_NUM[program["model"]].items():
        program[name] = _even(rng, bounds)
    for name, choices in O_CAT[program["model"]].items():
        program[name] = _one(rng, choices)
    return program


def fresh(form: str, rng) -> dict:
    """A program with every choice and every setting drawn evenly; ``form`` is ``"unordered"`` or ``"ordered"``."""
    if form == "ordered":
        return _model_o(rng, {"form": "o", "y": _one(rng, Y), "snap": int(rng.integers(2)), "season": int(rng.integers(2)),
                              "thr": _even(rng, THR)})
    return {"form": "u", "y": _one(rng, Y), "snap": int(rng.integers(2)),
            "stages": [_stage_u(rng, k > 0) for k in range(1 + int(rng.integers(MAX_STAGES)))]}


def _step(rng, value, bounds) -> float:
    return round(float(np.clip(value + STEP * (bounds[1] - bounds[0]) * rng.standard_normal(), bounds[0], bounds[1])), 5)


def _other(rng, value, choices):
    rest = [c for c in choices if c != value]
    return _one(rng, rest) if rest else value


def vary(program: dict, rng) -> dict:
    """The program with one small change: a setting moved by a step, one choice made differently, a model drawn
    again, or (unordered) a stage added at the end or dropped."""
    p = copy.deepcopy(program)
    if p["form"] == "o":
        settings = ["thr"] + list(O_NUM[p["model"]])
        move = _one(rng, ["setting", "setting", "choice", "model"])
        if move == "setting":
            name = _one(rng, settings)
            p[name] = _step(rng, p[name], THR if name == "thr" else O_NUM[p["model"]][name])
        elif move == "choice":
            name = _one(rng, ["y", "snap", "season"] + list(O_CAT[p["model"]]))
            p[name] = _other(rng, p[name], {"y": Y, "snap": (0, 1), "season": (0, 1)}.get(name) or O_CAT[p["model"]][name])
        else:
            _model_o(rng, p)
        return p
    moves = ["setting", "setting", "choice", "model"] + (["add"] if len(p["stages"]) < MAX_STAGES else []) \
        + (["drop"] if len(p["stages"]) > 1 else [])
    move = _one(rng, moves)
    k = int(rng.integers(len(p["stages"])))
    stage = p["stages"][k]
    if move == "setting":
        names = list(U_NUM[stage["model"]]) + (["shrink"] if k > 0 else [])
        name = _one(rng, names)
        stage[name] = _step(rng, stage[name], SHRINK if name == "shrink" else U_NUM[stage["model"]][name])
    elif move == "choice":
        name = _one(rng, ["y", "snap", "x"] + list(U_CAT[stage["model"]]))
        if name in ("y", "snap"):
            p[name] = _other(rng, p[name], Y if name == "y" else (0, 1))
        else:
            stage[name] = _other(rng, stage[name], U_X if name == "x" else U_CAT[stage["model"]][name])
    elif move == "model":
        p["stages"][k] = _stage_u(rng, k > 0)
    elif move == "add":
        p["stages"].append(_stage_u(rng, True))
    else:
        del p["stages"][k]
        p["stages"][0].pop("shrink", None)
    return p


def check_program(program: dict, form: str) -> dict:
    """The program, if it is one of the space; ``ValueError`` otherwise."""
    def inside(value, bounds):
        return isinstance(value, (int, float)) and bounds[0] <= value <= bounds[1]

    ok = isinstance(program, dict) and program.get("y") in Y and program.get("snap") in (0, 1)
    if ok and form == "ordered":
        m = program.get("model")
        ok = (program.get("form") == "o" and m in O_MODELS and program.get("season") in (0, 1) and inside(program.get("thr"), THR)
              and set(program) == {"form", "y", "snap", "season", "thr", "model"} | set(O_NUM.get(m, {})) | set(O_CAT.get(m, {}))
              and all(inside(program[k], b) for k, b in O_NUM[m].items()) and all(program[k] in c for k, c in O_CAT[m].items()))
    elif ok:
        stages = program.get("stages")
        ok = program.get("form") == "u" and set(program) == {"form", "y", "snap", "stages"} and isinstance(stages, list) \
            and 1 <= len(stages) <= MAX_STAGES
        for k, s in enumerate(stages if ok else []):
            m = s.get("model")
            ok = ok and m in U_MODELS and s.get("x") in U_X \
                and set(s) == {"model", "x"} | set(U_NUM[m]) | set(U_CAT[m]) | ({"shrink"} if k > 0 else set()) \
                and all(inside(s[n], b) for n, b in U_NUM[m].items()) and all(s[n] in c for n, c in U_CAT[m].items()) \
                and (k == 0 or inside(s["shrink"], SHRINK))
    if not ok:
        raise ValueError(f"not a program of the {form} space: {program}")
    return program


# ---- a program as an entity: what the learner's model of its own programs reads ---------------------
def features(program: dict) -> list:
    """The program as a row of numbers: every choice as 0 or 1 per value, every setting as its place in its
    range, 0 where the program has no such part. One length per form."""
    if program["form"] == "o":
        row = [float(program["y"] == "log"), float(program["snap"]), float(program["season"]),
               (program["thr"] - THR[0]) / (THR[1] - THR[0])]
        row += [float(program["model"] == m) for m in O_MODELS]
        for m in O_MODELS:
            for name, b in O_NUM[m].items():
                row.append((program[name] - b[0]) / (b[1] - b[0]) if program["model"] == m else 0.0)
            for name, c in O_CAT[m].items():
                row.append(c.index(program[name]) / max(len(c) - 1, 1) if program["model"] == m else 0.0)
        return row
    row = [float(program["y"] == "log"), float(program["snap"]), len(program["stages"]) / MAX_STAGES]
    for k in range(MAX_STAGES):
        s = program["stages"][k] if k < len(program["stages"]) else None
        row.append(float(s is not None))
        row += [float(s is not None and s["model"] == m) for m in U_MODELS]
        row += [float(s is not None and s["x"] == x) for x in U_X]
        for m in U_MODELS:
            for name, b in U_NUM[m].items():
                row.append((s[name] - b[0]) / (b[1] - b[0]) if s is not None and s["model"] == m else 0.0)
            for name, c in U_CAT[m].items():
                row.append(c.index(s[name]) / max(len(c) - 1, 1) if s is not None and s["model"] == m else 0.0)
        row.append((s["shrink"] - SHRINK[0]) / (SHRINK[1] - SHRINK[0]) if s is not None and "shrink" in s else 0.0)
    return row


# ---- versions -----------------------------------------------------------------------------------
SEARCH = {"slots": 6, "vary": 0.5, "holdback": 0.25, "strict": 1, "shortlist": 12, "offer": 256, "take": 8}
FORMS = ("unordered", "ordered")
KNOWN_AT_MOST = 256                            # programs a version remembers per form
SHARE = 0.5                                    # of what a run can spend on trying programs, the most its library may take


def default() -> dict:
    """Generation 0: nothing tried first, nothing remembered, no model of its own programs."""
    return {"design": "t", "search": dict(SEARCH), "library": {form: [] for form in FORMS},
            "known": {form: [] for form in FORMS}, "model": {form: None for form in FORMS}}


def _rounded(x):
    if isinstance(x, dict):
        return {k: _rounded(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_rounded(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    return x


def validate(version: dict) -> dict:
    if version.get("design") != "t" or set(version) != {"design", "search", "library", "known", "model"}:
        raise ValueError("not a version of design t")
    s = version["search"]
    if set(s) != set(SEARCH) or not (0 <= int(s["slots"]) <= 16 and 0.0 <= s["vary"] <= 1.0 and 0.0 < s["holdback"] <= 0.5
                                      and s["strict"] in (0, 1) and 2 <= int(s["shortlist"]) <= 64
                                      and 1 <= int(s["take"]) <= int(s["offer"]) <= 4096):
        raise ValueError("search settings missing or out of range")
    for part in ("library", "known", "model"):
        if set(version[part]) != set(FORMS):
            raise ValueError(f"{part}: one entry per form")
    for form in FORMS:
        if len(version["library"][form]) > int(s["slots"]):
            raise ValueError("more programs in a library than slots")
        for program in version["library"][form]:
            check_program(program, form)
        if len(version["known"][form]) > KNOWN_AT_MOST:
            raise ValueError("more programs remembered than a version may")
        for row in version["known"][form]:
            if len(row) != 3 or not (-1.0 <= float(row[1]) <= 1.0) or not isinstance(row[2], str):
                raise ValueError("a remembered program is [program, its skill where it was tried, where that was]")
            check_program(row[0], form)
        model = version["model"][form]
        if model is not None:
            if set(model) != {"rule", "programs"} or model["rule"] not in ("select", "mean") or not model["programs"]:
                raise ValueError("a model is a rule and the programs it combines")
            for program in model["programs"]:
                check_program(program, "unordered")                 # a model of programs reads rows of numbers
    return _rounded(version)


def digest(version: dict) -> str:
    return hashlib.sha256(json.dumps(validate(version), separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    """What differs between two versions: search settings by name, and per form how many programs of the
    library are new, how many programs are remembered, and whether the model changed. All of it is what the
    learner explores from."""
    a, b = validate(a), validate(b)
    out = {f"search.{k}": {"from": a["search"][k], "to": b["search"][k], "function": "decide"}
           for k in SEARCH if a["search"][k] != b["search"][k]}
    for form in FORMS:
        old = [json.dumps(p, sort_keys=True) for p in a["library"][form]]
        new = [json.dumps(p, sort_keys=True) for p in b["library"][form]]
        if old != new:
            out[f"library.{form}"] = {"from": len(old), "to": len(new), "new": sum(1 for p in new if p not in old), "function": "explore"}
        if a["known"][form] != b["known"][form]:
            out[f"known.{form}"] = {"from": len(a["known"][form]), "to": len(b["known"][form]), "function": "explore"}
        if a["model"][form] != b["model"][form]:
            out[f"model.{form}"] = {"from": None if a["model"][form] is None else len(a["model"][form]["programs"]),
                                    "to": None if b["model"][form] is None else len(b["model"][form]["programs"]), "function": "explore"}
    return out


FIELDS = ("search", "library", "known", "model")
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
        waiting, tried, proposed = list(self.v["library"][form]), [], None
        library_until = meter.used + SHARE * max(meter.left() - reserve, 0.0)
        report = {"form": "predict", "fit": len(fit_ids), "held_back": len(check), "iterations": 0, "failed": None, "modelled": 0}
        try:
            while True:
                if waiting and meter.used + passes(waiting[0]) * fit_units > library_until:
                    waiting = []                                    # the library has had its share
                if waiting:
                    program, origin = waiting.pop(0), "library"
                elif tried and rng.random() < s["vary"]:
                    program, origin = vary(max(tried, key=lambda row: row["skill"])["program"], rng), "varied"
                else:
                    if proposed is None:
                        proposed = self.propose(form, rng, meter, reserve + fit_units)
                        report["modelled"] = len(proposed)
                    program, origin = (proposed.pop(0), "proposed") if proposed else (fresh(form, rng), "fresh")
                if meter.left() - reserve < passes(program) * fit_units:
                    break
                row = {"program": program, "origin": origin, "inner": [], "answers": [], "skill": 0.0}
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
                report["iterations"] += 1
        except BudgetExhausted:
            report["failed"] = "decide: the budget ended inside a run"
        report["trace"] = [[row["program"], round(row["skill"], 6), row["origin"]] for row in tried]
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
        report.update(members=len(members), rule=rule, fit_skill=round(value, 6),
                      from_library=sum(1 for i in members if tried[i]["origin"] == "library"))
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

    def propose(self, form, rng, meter=None, keep=0.0) -> list:
        """Programs to try, the ones the version's model of its own programs puts first: ``offer`` programs are
        drawn evenly, the model predicts the value of each from the programs the version remembers, and the
        ``take`` best by that prediction come back, best first. Reading the model is charged like any other
        use of a capability; a version without a model proposes nothing (the caller then draws evenly)."""
        from rsi6.kernel.problem import Meter, PredictProblem
        s, known, model = self.v["search"], self.v["known"][form], self.v["model"][form]
        if model is None or len(known) < 8:
            return []
        drawn = [fresh(form, rng) for _ in range(int(s["offer"]))]
        P = PredictProblem([features(row[0]) for row in known], values(known), [features(p) for p in drawn], False)
        cost = sum(passes(p, model["rule"] == "select") for p in model["programs"]) * P.construction_units()
        if meter is not None:
            if meter.left() - keep < cost:
                return []
            meter.charge(cost)
        P.meter = Meter(float("inf"))
        predicted = self.apply({"kind": "predict", "design": "t", "rule": model["rule"], "programs": model["programs"], "learned": True}, P)
        return [drawn[int(i)] for i in np.argsort(-np.asarray(predicted), kind="stable")[:int(s["take"])]]

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


# ---- the learner's model of its own programs ------------------------------------------------------
def values(known) -> np.ndarray:
    """The value of every remembered program: the rank of its skill among the programs remembered from the same
    place, from 0 (worst there) to 1 (best there). Places differ in how hard they are; ranks do not."""
    skills = np.array([float(row[1]) for row in known])
    where = np.array([row[2] for row in known])
    out = np.zeros(len(known))
    for place in set(where.tolist()):
        idx = np.flatnonzero(where == place)
        order = np.argsort(np.argsort(skills[idx], kind="stable"), kind="stable")
        out[idx] = order / max(len(idx) - 1, 1)
    return out


def landscape(known, rng, meter, n_problems=12, n_observed=128, n_queries=64) -> list:
    """Prediction problems made from remembered programs (``[program, skill, where it was tried]``). In each, the
    programs tried in one place are the queries and their values there the targets; what is observed are
    programs tried in the other places, with their values there. (With one place only: a random split.) So a
    learner trained on them is trained to say how a program will do somewhere it has not been tried."""
    from rsi6.kernel.problem import PredictProblem
    X = np.array([features(row[0]) for row in known])
    v = values(known)
    where = np.array([row[2] for row in known])
    places = sorted(set(where.tolist()))
    problems = []
    for j in range(n_problems):
        if len(places) > 1:
            place = places[j % len(places)]
            inside, outside = np.flatnonzero(where == place), np.flatnonzero(where != place)
            q = rng.choice(inside, size=min(n_queries, len(inside)), replace=False)
            c = rng.choice(outside, size=min(n_observed, len(outside)), replace=False)
        else:
            order = rng.permutation(len(known))
            cut = min(n_observed, (2 * len(known)) // 3)
            c, q = order[:cut], order[cut:cut + n_queries]
        problems.append(PredictProblem(X[c], v[c], X[q], False, target=v[q], meter=meter))
    return problems


def self_model(maker: dict, known, rng, train: float = 12.0):
    """The model of its programs that the learner ``maker`` acquires from ``known``: one acquisition, with the
    budget of a run, on the problems of ``landscape``. ``(model or None, report)``; the model is the acquired
    capability (a rule and unordered programs), ``None`` when the learner ended on nothing."""
    from rsi6.kernel.problem import Meter
    if len(known) < 24:
        return None, {"failed": "too few programs remembered", "used": 0.0}
    meter = Meter(0.0)
    problems = landscape(known, rng, meter)
    meter.limit = train * sum(P.construction_units() for P in problems)
    capability, _, report = LearnerT(maker).acquire(problems, rng)
    report = {k: v for k, v in report.items() if k != "trace"}
    report["used"] = meter.used
    if not capability or not capability.get("learned") or not capability.get("programs"):
        return None, report
    return {"rule": capability["rule"], "programs": capability["programs"]}, report
