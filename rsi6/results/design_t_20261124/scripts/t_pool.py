"""Scratch: a pool of programs drawn evenly from design t's space, each run on the training problems of the
development kinds of its form. Output: one pickle per form with skill[p, j], inner[p, j], kind of problem j.

    python3 -I t_pool.py FORM N OUT.pkl [SEED]
"""
# Development script, kept as it was run (2026-11-24/25) apart from the two paths below.
# REPO: the root of the repository; DEV: a scratch directory for pools and outputs (RSI6_T_DEV).
import os as _os, sys as _sys
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "..", ".."))
DEV = _os.environ.get("RSI6_T_DEV", "t_dev")
_sys.path.insert(0, REPO)
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import os
import pickle
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import multiprocessing
import warnings

import numpy as np

warnings.filterwarnings("ignore")
from rsi6.learner import design_t

KINDS = {"unordered": ["regression", "friedman", "table", "binary"], "ordered": ["forecasting", "cif", "nn5", "fredmd"]}
PROBLEMS, SCALES = [], []


def load(form, n_train=16):
    from rsi6 import environments
    from rsi6.environments import kinds
    from rsi6.kernel.environment import split
    from rsi6.kernel.problem import Meter
    kinds.install()
    out = []
    for kind in KINDS[form]:
        env = environments.load(kind)
        train_ids, _ = split(env, n_train, 24)
        for i in train_ids:
            out.append((kind, env.problem(i, Meter(float("inf")), 0, True)[0]))
    return out


def one(program):
    row_s, row_i = [], []
    started = time.process_time()
    for (kind, P), scale in zip(PROBLEMS, SCALES):
        try:
            inner, target, answer = design_t.run(program, P.ctx_x, P.ctx_y, P.qry_x)
        except (np.linalg.LinAlgError, FloatingPointError, ValueError, ZeroDivisionError):
            inner, target, answer = None, None, None
        row_s.append(design_t.skill(answer, P.qry_y, scale))
        row_i.append(design_t.skill(inner, target, scale) if inner is not None else -1.0)
    return row_s, row_i, time.process_time() - started


def main():
    form, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    global PROBLEMS, SCALES
    PROBLEMS = load(form)
    SCALES = [design_t.spread(P.ctx_y) for _, P in PROBLEMS]
    rng = np.random.default_rng(750000 + seed)
    programs = [design_t.fresh(form, rng) for _ in range(n)]
    with multiprocessing.get_context("fork").Pool(2) as pool:
        rows = pool.map(one, programs, chunksize=4)
    anchors = []
    for (kind, P), scale in zip(PROBLEMS, SCALES):
        anchors.append(design_t.skill(design_t.anchor(P.ctx_x, P.ctx_y, P.qry_x, P.ordered), P.qry_y, scale))
    pickle.dump({"form": form, "programs": programs, "skill": np.array([r[0] for r in rows]), "inner": np.array([r[1] for r in rows]),
                 "cpu": np.array([r[2] for r in rows]), "kind": [k for k, _ in PROBLEMS], "anchor": np.array(anchors),
                 "units": [P.construction_units() for _, P in PROBLEMS]}, open(out, "wb"))
    s = np.array([r[0] for r in rows])
    print(form, "programs", n, "problems", len(PROBLEMS), "cpu", round(sum(r[2] for r in rows), 1))
    for kind in KINDS[form]:
        sel = np.array([k == kind for k, _ in PROBLEMS])
        m = s[:, sel].mean(axis=1)
        print(f"  {kind:11s} anchor {np.array(anchors)[sel].mean():+.4f} | programs: mean {m.mean():+.4f} median {np.median(m):+.4f} "
              f"top decile {np.quantile(m, 0.9):+.4f} best {m.max():+.4f} | per-problem best {s[:, sel].max(axis=0).mean():+.4f}")


if __name__ == "__main__":
    main()
