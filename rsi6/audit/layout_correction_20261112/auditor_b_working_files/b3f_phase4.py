"""Auditor B, B3, phase 4 (added after phases 1 and 2 were complete and identical): every binpacking
and jobshop run record not yet in phases 1 or 3, in a random order (random.Random(20261113)), so
that whatever part of it is finished when the audit is written is itself a random sample.
Reads REPO and WORK/plan.json; adds the key "phase4" to WORK/plan.json."""
import json
import os
import random

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
WORK = os.path.join(BASE, "work_b")
plan = json.load(open(os.path.join(WORK, "plan.json")))
records = [json.loads(line) for line in open(os.path.join(REPO, "rsi6", "ledger", "main.jsonl")) if line.strip()]
taken = set(plan["phase2"])
for phase in ("phase1", "phase3"):
    for env in plan[phase]:
        taken |= set(plan[phase][env])
rest = sorted(r["idx"] for r in records if r["type"] == "run" and r["env"] in ("binpacking", "jobshop") and r["idx"] not in taken)
random.Random(20261113).shuffle(rest)
assert "phase4" not in plan
plan["phase4"] = rest
json.dump(plan, open(os.path.join(WORK, "plan.json"), "w"), indent=0, sort_keys=True)
print("phase 4:", len(rest), "records; first ten:", rest[:10])
