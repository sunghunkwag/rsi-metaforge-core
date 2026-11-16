"""D6 (development, no CPU beyond arithmetic): null calibration of the chain-mean t-test.

20,000 simulated nulls: pair differences resampled, after centring, from the measured paired
differences of the specification's pool (D1's r0 minus o0 at train 200, q_compare's q0 minus o0),
plus chain noise N(0, tau*^2), at the registered J, S and four categories. The rejection rate at
t(0.99, J-1) must not exceed 0.013; if it does, the endpoints switch to a sign-flip permutation
test on chain means. Reported besides, not deciding: the same with D2's relay minus frozen pair
differences added to the pool.

    python3 dev_r_d6.py J S tau
"""
import json
import math
import os
import sys

import numpy as np

S_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "<repo>")
from rsi6.kernel import ledger as ledgers
from rsi6.open.relay_report import t_quantile

J, S, tau = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3])


def d1_pool():
    """r0 minus o0 at train 200 of the D1 that the registration rests on (the repaired design)."""
    summary = json.load(open(os.path.join(S_DIR, "dev_r_d1h.json")))
    by = {}
    for arm in ("r0", "o0"):
        for x in summary["runs"][arm]:
            by.setdefault((x["env"], x["seed"]), {})[arm] = x["acquired"]
    return [v["r0"] - v["o0"] for v in by.values() if "r0" in v and "o0" in v]


def q_pool():
    out = []
    for name in ("q_compare1.txt", "q_compare2.txt"):
        path = os.path.join(S_DIR, name)
        if not os.path.exists(path):
            path = os.path.join("<repo>/rsi6/results/dev_20261116", name)
        for line in open(path):
            if "q0 minus o0, acquired" in line:
                out += [float(x) for x in line.split("per run")[1].strip().strip("[]").split(",")]
    return out


def d2_pool():
    out = []
    for f in ("quadassign", "jobshop", "pmedian"):
        path = os.path.join(S_DIR, f"dev_r_d2n_{f}.jsonl")
        if not os.path.exists(path):
            continue
        L = ledgers.Ledger(path)
        by = {}
        for r in L.records:
            if r.get("type") == "run" and r.get("purpose", "").startswith(("dev-d2:relay:", "dev-d2:frozen:")):
                by.setdefault(r["seed"], {})[r["purpose"].split(":")[1]] = r["acquired"]
        out += [v["relay"] - v["frozen"] for v in by.values() if "relay" in v and "frozen" in v]
    return out


def rate(pool, seed):
    pool = np.array(pool, float)
    pool = pool - pool.mean()
    rng = np.random.default_rng(seed)
    crit = t_quantile(0.01, J - 1)
    reject, N = 0, 20000
    for _ in range(N):
        pairs = rng.choice(pool, size=(J, 4 * S), replace=True)
        means = pairs.mean(axis=1) + rng.normal(0.0, tau, J)
        t = means.mean() / (means.std(ddof=1) / math.sqrt(J))
        reject += t >= crit
    return {"pool_size": int(len(pool)), "pool_sd": float(pool.std(ddof=1)), "critical_t": crit, "rejection_rate": reject / N}


spec = d1_pool() + q_pool()
out = {"J": J, "S": S, "tau": tau, "pools": {"D1 r0 minus o0": len(d1_pool()), "q_compare q0 minus o0": len(q_pool())},
       "deciding (the specification's pool)": rate(spec, 20261116)}
out["switch_to_permutation_test"] = bool(out["deciding (the specification's pool)"]["rejection_rate"] > 0.013)
extra = d2_pool()
if extra:
    out["reported, not deciding: with D2's relay minus frozen pairs"] = dict(rate(spec + extra, 20261117), d2_pairs=len(extra))
json.dump(out, open(os.path.join(S_DIR, "dev_r_d6.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
