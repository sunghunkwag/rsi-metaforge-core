"""D1 (development, source categories, scratch ledger, not evidence): design r with an empty memory
(= design q) against generation 0 of the open design at training budget 200, the open design
raised to r's CPU, and r at budget 800; job shop, quadratic assignment, p-median; six seeds."""
import json
import os
import shutil
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.kernel import run as R
from rsi6.learner import design_r, designs, dispatch_extra
from rsi6.open import evaluate

dispatch_extra.install()
S = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.join(S, "dev_r.jsonl")
if not os.path.exists(DEV):
    shutil.copy("<repo>/rsi6/ledger/main.jsonl", DEV)
ledger = ledgers.Ledger(DEV)
cache = R.Cache(ledger)
ENVS = ["jobshop", "quadassign", "pmedian"]
SEEDS = [9201, 9202, 9203, 9204, 9205, 9206]
B = {"train": 200.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}
B800 = dict(B, train=800.0)
r0, o0 = design_r.default(), designs.default("o")


def jobs(v, b, tag):
    return [{"env": e, "version": v, "seed": s, "budget": b, "purpose": f"dev:r:d1:{tag}"} for e in ENVS for s in SEEDS]


rr = cache.get(jobs(r0, B, "r0"), workers=1)
print("r0 done", flush=True)
oo = cache.get(jobs(o0, B, "o0"), workers=1)
print("o0 done", flush=True)
want = {(r["env"], r["seed"]): evaluate.cpu(r) for r in rr}
om = evaluate.raise_until(cache, o0, want, "dev:r:d1:o0@r0", B)
print("o0@r0 done", flush=True)
r8 = cache.get(jobs(r0, B800, "r0@800"), workers=1)
out = {}
for name, rows in (("r0", rr), ("o0", oo), ("o0@r0", om), ("r0@800", r8)):
    out[name] = {e: {"acquired": float(np.mean([r["acquired"] for r in rows if r["env"] == e])),
                     "gain": float(np.mean([r["gain"] for r in rows if r["env"] == e])),
                     "cpu": float(np.mean([evaluate.cpu(r) for r in rows if r["env"] == e])),
                     "switches": float(np.mean([(r.get("report") or {}).get("switches", 0) for r in rows if r["env"] == e])),
                     "program_rounds": float(np.mean([(r.get("report") or {}).get("program_rounds", 0) for r in rows if r["env"] == e])),
                     "kept_program": float(np.mean([bool((r.get("report") or {}).get("program_size")) for r in rows if r["env"] == e]))}
                 for e in ENVS}
rows_of = {"r0": rr, "o0": oo, "o0@r0": om, "r0@800": r8}
for a, b in (("r0", "o0"), ("r0", "o0@r0"), ("r0@800", "r0")):
    c = evaluate.compare([dict(x) for x in rows_of[a]], [dict(x) for x in rows_of[b]], name=f"{a} minus {b}")
    out[f"{a} minus {b}"] = {"min_change": c["min_change"], "acquired": c["acquired_change"], "per_env": c["per_env"], "cpu_ratio": c["cpu_ratio"]}
pairs = {}
for e in ENVS:
    d = [x["acquired"] - y["acquired"] for x, y in zip([r for r in rr if r["env"] == e], [r for r in oo if r["env"] == e])]
    pairs[e] = {"mean": float(np.mean(d)), "sd": float(np.std(d, ddof=1))}
out["paired r0 minus o0 by category"] = pairs
json.dump(out, open(os.path.join(S, "dev_r_d1.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
