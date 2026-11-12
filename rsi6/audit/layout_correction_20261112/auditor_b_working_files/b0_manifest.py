"""Auditor B, step 0: are all data files present and pinned, so that loading an environment
neither fetches anything nor rewrites a manifest?  Standard library only; reads REPO, writes nothing."""
import hashlib
import json
import os
import sys

REPO = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2/repo"
MAN = os.path.join(REPO, "rsi6", "environments", "manifests")
DATA = os.path.join(REPO, "rsi6", "data")
FORBIDDEN_FILES = {"seed.json", "list_tasks2.json", "test.json"}


def forbidden(path):
    parts = os.path.normpath(path).split(os.sep)
    return "judge" in parts or parts[-1] in FORBIDDEN_FILES


bad = 0
for name in sorted(os.listdir(MAN)):
    manifest = json.load(open(os.path.join(MAN, name)))
    env = name[:-5]
    n = present = missing_flag = absent = nohash = mismatch = skipped = 0
    keys = sorted(k for k in manifest if k != "files")
    for entry in manifest["files"]:
        n += 1
        target = os.path.join(DATA, env, entry["path"])
        if forbidden(target):
            skipped += 1
            continue
        if entry.get("missing"):
            missing_flag += 1
            continue
        if not os.path.exists(target):
            absent += 1
            print("  ABSENT (would be fetched):", env, entry["path"])
            continue
        present += 1
        if entry.get("sha256") is None:
            nohash += 1
            print("  NO HASH (manifest would be rewritten):", env, entry["path"])
            continue
        sha = hashlib.sha256(open(target, "rb").read()).hexdigest()
        if sha != entry["sha256"]:
            mismatch += 1
            print("  HASH DIFFERS:", env, entry["path"])
    bad += absent + nohash + mismatch
    print(f"{env}: entries {n}, present {present}, flagged missing {missing_flag}, absent {absent}, "
          f"without hash {nohash}, hash mismatch {mismatch}, skipped(forbidden name) {skipped}; "
          f"other manifest keys {keys}; allow_missing={manifest.get('allow_missing')}")
print("TOTAL PROBLEMS:", bad)
sys.exit(1 if bad else 0)
