"""Scratch: can design t's own learner model the landscape of its own programs?
A pool of programs with their skills on the training problems of four kinds. For each kind left out:
  the 'general value' of a program = mean over the other three kinds of its rank there (0..1);
  known = a random half of the pool, candidates = the other half;
  the learner (generation 0 of design t) acquires on landscape problems made from the known half
  (attributes of a program -> value), then predicts the candidates.
Read: rank correlation of the prediction with (a) the candidates' general value, (b) their value on the kind left out;
and what the top 10% by prediction are worth on the kind left out, against a random 10% and the best possible.

    python3 -I u_landscape.py POOL.pkl [train]
"""
# Development script, kept as it was run (2026-11-24) apart from the two paths below.
# REPO: the root of the repository; DEV: a scratch directory for pools and outputs (RSI6_T_DEV).
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV = _os.environ.get("RSI6_T_DEV", "t_dev")
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os
import pickle
import sys
import warnings

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np

warnings.filterwarnings("ignore")
from rsi6.kernel.problem import Meter, PredictProblem
from rsi6.learner import design_t as T


def features(program):
    if program["form"] == "o":
        f = [float(program["y"] == "log"), float(program["snap"]), float(program["season"]),
             (program["thr"] - T.THR[0]) / (T.THR[1] - T.THR[0])]
        f += [float(program["model"] == m) for m in T.O_MODELS]
        for m in T.O_MODELS:
            for name, b in T.O_NUM[m].items():
                f.append((program[name] - b[0]) / (b[1] - b[0]) if program["model"] == m else 0.0)
            for name, c in T.O_CAT[m].items():
                f.append(float(c.index(program[name])) / max(len(c) - 1, 1) if program["model"] == m else 0.0)
        return f
    f = [float(program["y"] == "log"), float(program["snap"]), len(program["stages"]) / T.MAX_STAGES]
    for k in range(T.MAX_STAGES):
        s = program["stages"][k] if k < len(program["stages"]) else None
        f.append(float(s is not None))
        f += [float(s is not None and s["model"] == m) for m in T.U_MODELS]
        f += [float(s is not None and s["x"] == x) for x in T.U_X]
        for m in T.U_MODELS:
            for name, b in T.U_NUM[m].items():
                f.append((s[name] - b[0]) / (b[1] - b[0]) if s is not None and s["model"] == m else 0.0)
            for name, c in T.U_CAT[m].items():
                f.append(float(c.index(s[name])) / max(len(c) - 1, 1) if s is not None and s["model"] == m else 0.0)
        f.append((s["shrink"] - T.SHRINK[0]) / (T.SHRINK[1] - T.SHRINK[0]) if s is not None and "shrink" in s else 0.0)
    return f


def ranks(v):
    return np.argsort(np.argsort(v)) / (len(v) - 1.0)


def spearman(a, b):
    return float(np.corrcoef(ranks(a), ranks(b))[0, 1])


def model(version, X, y, Xq, rng, train=12.0, n_problems=12, n_ctx=128, n_qry=64, targets=None):
    """The learner's own model of a landscape: acquire on problems cut from the known programs, then answer.
    ``targets``: a list of value vectors (one per source kind) to make the training problems from; default [y]."""
    targets = targets or [y]
    n = len(y)
    meter = Meter(0.0)
    problems = []
    for j in range(n_problems):
        perm = rng.permutation(n)
        c, q = perm[:min(n_ctx, n - 8)], perm[min(n_ctx, n - 8):min(n_ctx, n - 8) + n_qry]
        t = targets[j % len(targets)]
        problems.append(PredictProblem(X[c], t[c], X[q], False, target=t[q], meter=meter))
    meter.limit = train * sum(P.construction_units() for P in problems)
    learner = T.LearnerT(version)
    capability, _, report = learner.acquire(problems, rng)
    keep = rng.permutation(n)[:256]
    P = PredictProblem(X[keep], y[keep], Xq, False, meter=Meter(float("inf")))
    return learner.apply(capability, P, rng), report, meter.used


def main():
    pool = pickle.load(open(sys.argv[1], "rb"))
    train = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    S, kind = pool["skill"], np.array(pool["kind"])
    kinds = list(dict.fromkeys(pool["kind"]))
    X = np.array([features(p) for p in pool["programs"]])
    per_kind = {k: S[:, kind == k].mean(axis=1) for k in kinds}
    print("pool", S.shape, "attributes", X.shape[1], "train", train)
    v0 = T.default()
    rows = []
    for target in kinds:
        others = [k for k in kinds if k != target]
        general = np.mean([ranks(per_kind[k]) for k in others], axis=0)
        for rep in range(6):
            rng = np.random.default_rng(1000 * rep + 7)
            perm = rng.permutation(len(X))
            known, cand = perm[:len(X) // 2], perm[len(X) // 2:]
            pred, report, used = model(v0, X[known], general[known], X[cand], rng, train=train,
                                       targets=[ranks(per_kind[k])[known] for k in others])
            near = general[known][np.argmin(((X[cand][:, None, :] - X[known][None, :, :]) ** 2).sum(-1), axis=1)]
            top = np.argsort(-pred)[:len(cand) // 10]
            top_near = np.argsort(-near)[:len(cand) // 10]
            tv = per_kind[target][cand]
            rows.append((target, spearman(pred, general[cand]), spearman(near, general[cand]), spearman(pred, tv), spearman(near, tv),
                         spearman(general[cand], tv), tv[top].mean(), tv[top_near].mean(), tv.mean(),
                         tv[np.argsort(-general[cand])[:len(cand) // 10]].mean(), np.sort(tv)[-len(cand) // 10:].mean(),
                         tv[top].max(), tv.max(), report.get("members"), report.get("rule"), bool(report.get("learned"))))
    names = ["rho(model, general)", "rho(nearest, general)", "rho(model, left-out)", "rho(nearest, left-out)", "rho(general, left-out)",
             "left-out value of top 10% by model", "... by nearest", "... of all", "... by true general value", "... best possible",
             "best of the model's top 10%", "best of all"]
    for target in kinds:
        mine = [r for r in rows if r[0] == target]
        print(f"== left out: {target}   (members {[r[13] for r in mine]}, rule {[r[14] for r in mine]}, kept {[r[15] for r in mine]})")
        for i, name in enumerate(names):
            print(f"   {name:38s} {np.mean([r[i + 1] for r in mine]):+.4f}")


if __name__ == "__main__":
    main()
