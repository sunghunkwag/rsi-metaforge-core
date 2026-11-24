"""Scratch (E2): with the same library and the same remembered programs, does it matter WHICH learner made the model?

For each unordered kind left out: knowledge from the pool on the other three kinds (library = greedy cover of all pool
programs; remembered = 85 pool programs x 3 kinds). Versions measured on the kind left out (real runs, train 12):
  none            generation 0
  library         the library alone
  model0          the model alone, made by generation 0
  both0[k]        library + model made by generation 0            (k = model seed)
  both1[k]        library + model made by the version both0[k]    (the modified learner makes the next model)
  mixed[k]        library + model made by generation 0 from shuffled values
Read: both1 - both0 (does the modified learner make a better model: the second half), both0 - none (the first half),
both0 - mixed (is the model worth anything).

    python3 -I e2_maker.py OUT.json [run_seeds] [model_seeds] [train]
"""
# Development script, kept as it was run (2026-11-24) apart from the two paths below.
# REPO: the root of the repository; DEV: a scratch directory for pools and outputs (RSI6_T_DEV).
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV = _os.environ.get("RSI6_T_DEV", "t_dev")
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import json
import multiprocessing
import os
import pickle
import sys
import warnings

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np

warnings.filterwarnings("ignore")
from rsi6.learner import design_t as T
from rsi6.meta import chain_t

POOL = pickle.load(open(os.path.join(DEV, "pool_unordered.pkl"), "rb"))
KINDS = list(dict.fromkeys(POOL["kind"]))


def knowledge(left, n_known=85, seed=0):
    S, kind = POOL["skill"], np.array(POOL["kind"])
    cols = kind != left
    chosen, best = [], np.full(cols.sum(), -1.0)
    for _ in range(6):
        gains = [np.maximum(best, S[p, cols]).mean() if p not in chosen else -9.0 for p in range(len(S))]
        c = int(np.argmax(gains))
        chosen.append(c)
        best = np.maximum(best, S[c, cols])
    library = [POOL["programs"][c] for c in chosen]
    picked = np.random.default_rng(880 + seed).permutation(len(S))[:n_known]
    rows = [[POOL["programs"][int(p)], float(np.clip(S[int(p), kind == k].mean(), -1, 1)), k] for p in picked for k in KINDS if k != left]
    return library, rows


def version(library=None, rows=None, model=None):
    v = T.default()
    if library:
        v["library"]["unordered"] = library
    if rows and model:
        v["known"]["unordered"], v["model"]["unordered"] = rows, model
    return T.validate(v)


def main():
    out = sys.argv[1]
    run_seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    model_seeds = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    train = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
    T.install()
    from rsi6.environments import kinds as kinds_module
    kinds_module.install()
    runs = chain_t.Runs(dict(chain_t.BUDGET, train=train), 2)
    seeds = list(range(747001, 747001 + run_seeds))
    result = {}
    for left in KINDS:
        library, rows = knowledge(left)
        versions = {"none": version(), "library": version(library)}
        m0, _ = T.self_model(T.default(), rows, np.random.default_rng(1), train)
        versions["model0"] = version(None, rows, m0) if m0 else version()
        info = {}
        for k in range(model_seeds):
            a, ra = T.self_model(T.default(), rows, np.random.default_rng([k, 11]), train)
            both0 = version(library, rows, a) if a else version(library)
            b, rb = T.self_model(both0, rows, np.random.default_rng([k, 11]), train)
            mixed_rows = [[r[0], rows[int(j)][1], r[2]] for r, j in zip(rows, np.random.default_rng([k, 12]).permutation(len(rows)))]
            c, rc = T.self_model(T.default(), mixed_rows, np.random.default_rng([k, 11]), train)
            versions[f"both0[{k}]"] = both0
            versions[f"both1[{k}]"] = version(library, rows, b) if b else version(library)
            versions[f"mixed[{k}]"] = version(library, mixed_rows, c) if c else version(library)
            info[k] = {"fit0": ra.get("fit_skill"), "fit1": rb.get("fit_skill"), "fitm": rc.get("fit_skill"),
                       "m0": None if a is None else len(a["programs"]), "m1": None if b is None else len(b["programs"])}
        res = {name: runs.get(v, [left], seeds) for name, v in versions.items()}
        acq = {name: [r["acquired"] for r in rows_] for name, rows_ in res.items()}
        cpu = {name: float(np.mean([r["cpu"] for r in rows_])) for name, rows_ in res.items()}
        tried = {name: float(np.mean([sum(1 for t in r["report"]["trace"] if t[2] == "proposed") for r in rows_])) for name, rows_ in res.items()}
        result[left] = {"acquired": acq, "cpu": cpu, "info": info, "proposed_tried": tried}
        g = lambda prefix: np.mean([acq[n] for n in acq if n.startswith(prefix)], axis=0)
        line = {n: float(np.mean(acq[n])) for n in ("none", "library", "model0")}
        d10, d0n, d0m = g("both1") - g("both0"), g("both0") - np.array(acq["none"]), g("both0") - g("mixed")
        se = lambda d: float(np.std(d, ddof=1) / np.sqrt(len(d)))
        print(f"{left:11s} none {line['none']:.4f} library {line['library']:.4f} model0 {line['model0']:.4f} both0 {g('both0').mean():.4f} "
              f"both1 {g('both1').mean():.4f} mixed {g('mixed').mean():.4f} | both1-both0 {d10.mean():+.4f} ({se(d10):.4f}) | "
              f"both0-none {d0n.mean():+.4f} ({se(d0n):.4f}) | both0-mixed {d0m.mean():+.4f} ({se(d0m):.4f}) | fit {info} | "
              f"cpu none {cpu['none']:.2f} both0 {np.mean([cpu[n] for n in cpu if n.startswith('both0')]):.2f}", flush=True)
        json.dump(result, open(out, "w"))


if __name__ == "__main__":
    main()
