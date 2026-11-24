"""Auditor B, B1: hashes of the learner's files against freeze_L0.json (last correction) and of the
files listed in corrections.json; git blob ids of the four files of the diff against the diff's
'index' lines.  Standard library only; reads REPO and the diff; writes nothing."""
import hashlib
import json
import os
import re

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
DIFF = os.path.join(BASE, "correction.diff")


def sha256(rel):
    return hashlib.sha256(open(os.path.join(REPO, rel), "rb").read()).hexdigest()


def blob(rel):
    data = open(os.path.join(REPO, rel), "rb").read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


freeze = json.load(open(os.path.join(REPO, "rsi6/registry/freeze_L0.json")))
corr = json.load(open(os.path.join(REPO, "rsi6/registry/corrections.json")))
reg = json.load(open(os.path.join(REPO, "rsi6/registry/registration.json")))

print("== freeze_L0.json: 'files' (generation 0, as first frozen) vs REPO")
for rel, want in freeze["files"].items():
    got = sha256(rel)
    print(f"  {rel}: frozen {want[:16]}  repo {got[:16]}  {'SAME' if got == want else 'DIFFERENT'}")
print("== registration.json: freeze_L0 equals freeze_L0.json files:", reg["freeze_L0"] == freeze["files"])
print("== freeze_L0.json: number of corrections:", len(freeze["corrections"]))
last = freeze["corrections"][-1]
print("   last correction utc:", last["utc"], "| before_any_registered_round:", last.get("before_any_registered_round"))
ok = True
for rel, want in last["files"].items():
    got = sha256(rel)
    same = got == want
    ok &= same
    print(f"  {rel}:\n     last correction {want}\n     repo            {got}  {'SAME' if same else 'DIFFERENT'}")
print("B1a: learner files have exactly the hashes of the last recorded correction:", ok)

print("== corrections.json: number of corrections:", len(corr["corrections"]))
ok2 = True
for c in corr["corrections"]:
    print("   utc:", c["utc"])
    for rel, want in c["files"].items():
        got = sha256(rel)
        same = got == want
        ok2 &= same
        print(f"  {rel}:\n     stated {want}\n     repo   {got}  {'SAME' if same else 'DIFFERENT'}")
    shared = {k: (c["files"][k], last["files"][k]) for k in c["files"] if k in last["files"]}
    print("   files listed in both records agree:", all(a == b for a, b in shared.values()), sorted(shared))
    print("   files of the diff NOT listed in corrections.json 'files':",
          [f for f in ("rsi6/environments/knapsack.py", "rsi6/environments/regression.py", "rsi6/kernel/run.py",
                       "rsi6/tests/test_kernel.py") if f not in c["files"]])
print("B1b: corrections.json states the true hashes of the files it lists:", ok2)

print("== the diff: git blob ids of the post-image against the files in REPO")
text = open(DIFF).read()
for m in re.finditer(r"^diff --git a/(\S+) b/(\S+)\nindex ([0-9a-f]+)\.\.([0-9a-f]+)", text, flags=re.M):
    rel, old, new = m.group(2), m.group(3), m.group(4)
    got = blob(rel)
    print(f"  {rel}: diff says {old}..{new}; repo blob {got[:len(new)]}  {'SAME' if got.startswith(new) else 'DIFFERENT'}")
print("== sha256 of other files of interest")
for rel in ("rsi6/tests/test_kernel.py", "rsi6/registry/corrections.json", "rsi6/registry/freeze_L0.json",
            "rsi6/registry/registration.json", "rsi6/registry/roles.json", "rsi6/ledger/main.jsonl",
            "rsi6/kernel/ledger.py", "rsi6/kernel/environment.py", "rsi6/kernel/roles.py", "rsi6/meta/rounds.py",
            "rsi6/meta/space.py", "rsi6/experiments/generations.py", "rsi6/environments/__init__.py",
            "rsi6/environments/forecasting.py", "rsi6/environments/jobshop.py", "rsi6/environments/binpacking.py",
            "rsi6/environments/quadassign.py", "rsi6/environments/pmedian.py", "rsi6/fetch.py"):
    print(f"  {sha256(rel)}  {rel}")
