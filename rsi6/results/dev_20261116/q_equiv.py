"""Development check of design q on source categories (scratch ledger, a copy of main):
(1) share 0 must give exactly design o's runs; (2) q0 against o0 on a few seeds."""
import json
import os
import shutil
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import q_dispatch  # noqa: F401  (development dispatch for design q)

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.kernel import run as R
from rsi6.learner import design_o as O, design_q as Q

S = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.join(S, os.environ.get("DEV_LEDGER", "dev_q.jsonl"))
if not os.path.exists(DEV):
    shutil.copy("/home/user/rsi-metaforge-core/rsi6/ledger/main.jsonl", DEV)
ledger = ledgers.Ledger(DEV)
cache = R.Cache(ledger)
BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 12, "n_fresh": 24, "part": "A"}
envs = sys.argv[1].split(",") if len(sys.argv) > 1 else ["quadassign"]
seeds = [int(s) for s in sys.argv[2].split(",")] if len(sys.argv) > 2 else [9001]
mode = sys.argv[3] if len(sys.argv) > 3 else "equiv"

o0 = O.default()
q_off = Q.default()
q_off["inner"]["share"] = 0.0
q0 = Q.default()


def jobs(version, purpose):
    return [{"env": e, "version": version, "seed": s, "budget": BUDGET, "purpose": purpose} for e in envs for s in seeds]


t = time.time()
if mode == "equiv":
    a = cache.get(jobs(o0, "dev:q:equiv:o0"), workers=1)
    b = cache.get(jobs(q_off, "dev:q:equiv:share0"), workers=1)
    for x, y in zip(a, b):
        same = (x["acquired"] == y["acquired"] and x["untrained"] == y["untrained"] and x["fresh_acquired"] == y["fresh_acquired"]
                and x["capability"] == y["capability"])
        print(x["env"], x["seed"], "o0", round(x["acquired"], 4), "q share 0", round(y["acquired"], 4), "identical" if same else "DIFFERENT",
              "cpu", x["cpu"], y["cpu"])
else:
    a = cache.get(jobs(o0, "dev:q:compare:o0"), workers=1)
    b = cache.get(jobs(q0, "dev:q:compare:q0"), workers=1)
    for x, y in zip(a, b):
        rep = y["report"]
        print(f"{x['env']:12s} {x['seed']} o0 acq {x['acquired']:.4f} gain {x['gain']:+.4f} cpu {x['cpu']['acquire']:.1f} | "
              f"q0 acq {y['acquired']:.4f} gain {y['gain']:+.4f} cpu {y['cpu']['acquire']:.1f} rounds {rep.get('iterations')} "
              f"program rounds {rep.get('program_rounds')} switches {rep.get('switches')} learned {rep.get('learned')} size {rep.get('program_size')}")
    d = np.array([y["acquired"] - x["acquired"] for x, y in zip(a, b)])
    print("q0 minus o0, acquired: mean", round(float(d.mean()), 4), "per run", np.round(d, 4).tolist())
print("wall", round(time.time() - t, 1))
