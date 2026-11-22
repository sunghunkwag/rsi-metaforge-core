"""D1 (development, source categories, scratch ledger, not evidence): design r with an empty memory
against generation 0 of the open design at training budget 200, the open design raised to r's
CPU, and r at budget 800; job shop, quadratic assignment, p-median; six seeds.

    python3 dev_r_d1.py TAG ACCEPT

TAG names the run's records (purposes dev:r:TAG:...), ACCEPT is design r's acceptance rule. The
first D1 (tag d1, rule rank, the design as it then was) found the defect that rule hard_first
repairs; its records and summary (dev_r_d1_rank.json) are kept. The summary holds every run it
used, so later checks read it and not the ledger.
"""
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
TAG, ACCEPT = sys.argv[1], sys.argv[2]
DEV = os.path.join(S, "dev_r.jsonl")
ledger = ledgers.Ledger(DEV)
cache = R.Cache(ledger)
ENVS = ["jobshop", "quadassign", "pmedian"]
SEEDS = [9201, 9202, 9203, 9204, 9205, 9206]
B = {"train": 200.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}
B800 = dict(B, train=800.0)
r0, o0 = dict(design_r.default(), accept=ACCEPT), designs.default("o")


def jobs(v, b, tag):
    return [{"env": e, "version": v, "seed": s, "budget": b, "purpose": f"dev:r:{TAG}:{tag}"} for e in ENVS for s in SEEDS]


rr = cache.get(jobs(r0, B, "r0"))
print("r0 done", flush=True)
oo = cache.get(jobs(o0, B, "o0"))
print("o0 done", flush=True)
want = {(r["env"], r["seed"]): evaluate.cpu(r) for r in rr}
om = evaluate.raise_until(cache, o0, want, f"dev:r:{TAG}:o0@r0", B)
print("o0@r0 done", flush=True)
r8 = cache.get(jobs(r0, B800, "r0@800"))
out = {"tag": TAG, "accept": ACCEPT, "version_digest": designs.digest(r0)}
rows_of = {"r0": rr, "o0": oo, "o0@r0": om, "r0@800": r8}
for name, rows in rows_of.items():
    out[name] = {e: {"acquired": float(np.mean([r["acquired"] for r in rows if r["env"] == e])),
                     "gain": float(np.mean([r["gain"] for r in rows if r["env"] == e])),
                     "train_gain": float(np.mean([r["train_acquired"] - r["train_untrained"] for r in rows if r["env"] == e])),
                     "cpu": float(np.mean([evaluate.cpu(r) for r in rows if r["env"] == e])),
                     "switches": float(np.mean([(r.get("report") or {}).get("switches", 0) for r in rows if r["env"] == e])),
                     "vetoes": float(np.mean([(r.get("report") or {}).get("vetoes", 0) for r in rows if r["env"] == e])),
                     "program_rounds": float(np.mean([(r.get("report") or {}).get("program_rounds", 0) for r in rows if r["env"] == e])),
                     "kept_program": float(np.mean([bool((r.get("report") or {}).get("program_size")) for r in rows if r["env"] == e])),
                     "instances_scored_0": int(sum(sum(1 for x in r["fresh_acquired"] if x == 0) for r in rows if r["env"] == e)),
                     "instances": int(sum(len(r["fresh_acquired"]) for r in rows if r["env"] == e))}
                 for e in ENVS}
for a, b in (("r0", "o0"), ("r0", "o0@r0"), ("r0@800", "r0")):
    c = evaluate.compare([dict(x) for x in rows_of[a]], [dict(x) for x in rows_of[b]], name=f"{a} minus {b}")
    out[f"{a} minus {b}"] = {"min_change": c["min_change"], "acquired": c["acquired_change"], "per_env": c["per_env"], "cpu_ratio": c["cpu_ratio"]}
pairs = {}
for e in ENVS:
    d = [x["acquired"] - y["acquired"] for x, y in zip([r for r in rr if r["env"] == e], [r for r in oo if r["env"] == e])]
    pairs[e] = {"mean": float(np.mean(d)), "sd": float(np.std(d, ddof=1))}
out["paired r0 minus o0 by category"] = pairs
out["runs"] = {name: [{"env": r["env"], "seed": r["seed"], "train": r["budget"]["train"], "acquired": r["acquired"], "gain": r["gain"],
                       "cpu": evaluate.cpu(r), "key": r["key"]} for r in rows] for name, rows in rows_of.items()}
json.dump(out, open(os.path.join(S, f"dev_r_{TAG}.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "runs"}, indent=1))
