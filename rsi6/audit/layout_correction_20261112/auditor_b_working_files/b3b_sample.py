"""Auditor B, B3: the plan of repetitions, fixed before any repetition was run.

SEED = 20261112 (python's random.Random).  The frame is all 1192 run records of the ledger (every
version digest was recovered, see b3a_versions.py).

  phase 1: a stratified random sample: 12 run records from each of the five environments (60).
  phase 2: every run record of forecasting, quadassign and pmedian (640 records; these include all
           72 records of the round-1 gates and confirmations).
  phase 3: 48 more random run records from each of binpacking and jobshop (96), drawn after
           phase 1 from the same generator.

Reads REPO; writes WORK/plan.json.
"""
import collections
import json
import os
import random
import sys

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
WORK = os.path.join(BASE, "work_b")
SEED = 20261112

records = [json.loads(line) for line in open(os.path.join(REPO, "rsi6", "ledger", "main.jsonl")) if line.strip()]
runs = [r for r in records if r["type"] == "run"]
by_env = collections.defaultdict(list)
for r in runs:
    by_env[r["env"]].append(r["idx"])
rng = random.Random(SEED)
phase1 = {}
for env in sorted(by_env):
    phase1[env] = sorted(rng.sample(sorted(by_env[env]), 12))
phase3 = {}
for env in ("binpacking", "jobshop"):
    rest = sorted(set(by_env[env]) - set(phase1[env]))
    phase3[env] = sorted(rng.sample(rest, 48))
phase2 = sorted(i for env in ("forecasting", "quadassign", "pmedian") for i in by_env[env])
plan = {"seed": SEED, "phase1": phase1, "phase2": phase2, "phase3": phase3}
json.dump(plan, open(os.path.join(WORK, "plan.json"), "w"), indent=0, sort_keys=True)

rec = {r["idx"]: r for r in runs}
p1 = [i for env in sorted(phase1) for i in phase1[env]]
print("seed", SEED)
print("phase 1:", len(p1), "records")
for env in sorted(phase1):
    print("  ", env, phase1[env])
print("   version digests in phase 1:", len({rec[i]["version"] for i in p1}))
print("   purposes:", dict(collections.Counter(rec[i]["purpose"] for i in p1)))
print("   budgets:", dict(collections.Counter((rec[i]["budget"]["n_train"], rec[i]["budget"].get("part")) for i in p1)))
print("   seeds:", dict(sorted(collections.Counter(rec[i]["seed"] for i in p1).items())))
print("phase 2:", len(phase2), "records; of which not in phase 1:", len(set(phase2) - set(p1)))
p3 = [i for env in sorted(phase3) for i in phase3[env]]
print("phase 3:", len(p3), "records")
allp = set(p1) | set(phase2) | set(p3)
print("all phases:", len(allp), "distinct records of", len(runs), "; version digests covered:",
      len({rec[i]["version"] for i in allp}), "of", len({r["version"] for r in runs}))
