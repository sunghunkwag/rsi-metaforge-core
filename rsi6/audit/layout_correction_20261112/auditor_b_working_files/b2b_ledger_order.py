"""Auditor B, B2 (order): was every recorded run made on a category whose role was unlocked at that
point of the ledger, and is the recorded role the role at that point?  Reads REPO; writes nothing."""
import collections
import json
import os
import sys

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
sys.path.insert(0, REPO)

from rsi6.kernel import roles                      # noqa: E402

records = [json.loads(line) for line in open(os.path.join(REPO, "rsi6", "ledger", "main.jsonl")) if line.strip()]


class Prefix:
    def __init__(self, upto):
        self.records = records[:upto]


bad_role = locked = 0
first = {}
last = {}
for position, r in enumerate(records):
    if r.get("type") != "run":
        continue
    before = Prefix(position)
    role = roles.effective_role(r["category"], before)
    bad_role += role != r["role"]
    locked += role not in roles.unlocked(before)
    first.setdefault(r["env"], r["idx"])
    last[r["env"]] = r["idx"]
print("run records:", sum(1 for r in records if r.get("type") == "run"))
print("run records whose recorded role is not the role at that point of the ledger:", bad_role)
print("run records made while the category's role was locked:", locked)
print("first and last run record per environment:", {e: (first[e], last[e]) for e in sorted(first)})
print("unlock / release / round_done positions:",
      [(r["idx"], r["type"], r.get("role"), r.get("round")) for r in records if r.get("type") in ("unlock", "release", "round_done")])
table = roles.load()["roles"]
print("roles of the seven adapters:", {c: table[c] for c in ("forecasting", "jobshop", "binpacking", "quadassign", "pmedian", "knapsack", "regression")})
print("draw reproduces roles.json:", roles.draw(roles.load()["commit"])["roles"] == table)
segments = collections.OrderedDict()
for r in records:
    if r.get("type") == "run":
        segments.setdefault(r["purpose"], [r["idx"], r["idx"], 0])
        segments[r["purpose"]][1] = r["idx"]
        segments[r["purpose"]][2] += 1
print("run purposes in ledger order (first idx, last idx, count):")
for purpose, (a, b, n) in segments.items():
    print("   ", purpose, a, b, n)
