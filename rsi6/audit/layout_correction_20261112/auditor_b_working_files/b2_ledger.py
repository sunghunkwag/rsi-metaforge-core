"""Auditor B, B2: the ledger.  Reads REPO/rsi6/ledger/main.jsonl; writes nothing under REPO.

(1) the package's own Ledger(path).verify();
(2) an independent check written from the rule in rsi6/kernel/ledger.py:
    h = sha256(prev + canon(record without h)), canon = JSON with sorted keys and compact separators,
    idx = position, prev = h of the previous record (64 zeros for the first);
(3) counts, the records that name knapsack or regression, the tail, the registration.
"""
import collections
import hashlib
import json
import os
import sys

REPO = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2/repo"
PATH = os.path.join(REPO, "rsi6", "ledger", "main.jsonl")
REG = os.path.join(REPO, "rsi6", "registry", "registration.json")

# ---------------------------------------------------------------- (1) the package's verification
sys.path.insert(0, REPO)
from rsi6.kernel import ledger as ledgers          # noqa: E402

size_before = os.path.getsize(PATH)
sha_before = hashlib.sha256(open(PATH, "rb").read()).hexdigest()
book = ledgers.Ledger(PATH)                         # reads and verifies; appends nothing
book.verify()
print("(1) rsi6.kernel.ledger.Ledger(path).verify(): no exception;", len(book.records), "records; head", book.head())

# ---------------------------------------------------------------- (2) independent verification
raw = open(PATH, "rb").read()
lines = raw.split(b"\n")
print("(2) file: bytes", len(raw), "| ends with newline:", raw.endswith(b"\n"), "| blank lines inside:",
      sum(1 for line in lines[:-1] if not line.strip()))
lines = [line for line in lines if line.strip()]


def no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate key in a JSON object")
    return dict(pairs)


def canon(value):
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


prev, problems, records = "0" * 64, [], []
for i, line in enumerate(lines):
    text = line.decode("utf-8")
    record = json.loads(text, object_pairs_hook=no_duplicates)
    records.append(record)
    if record.get("idx") != i:
        problems.append((i, "idx"))
    if record.get("prev") != prev:
        problems.append((i, "prev"))
    body = {k: v for k, v in record.items() if k != "h"}
    if hashlib.sha256((prev + canon(body)).encode()).hexdigest() != record.get("h"):
        problems.append((i, "h"))
    if canon(record) != text:
        problems.append((i, "line is not the canonical form of its record"))
    prev = record["h"]
print("    independent chain check:", len(records), "records;", "NO PROBLEM" if not problems else problems[:10])
print("    head (independent):", prev, "| equals package head:", prev == book.head())
print("    records parsed by the package equal mine:", book.records == records)

# ---------------------------------------------------------------- (3) counts
types = collections.Counter(r.get("type") for r in records)
print("(3) records by type:", dict(types))
runs = [r for r in records if r.get("type") == "run"]
print("    run records by env:", dict(collections.Counter(r["env"] for r in runs)))
print("    run records by category:", dict(collections.Counter(r["category"] for r in runs)))
print("    run records by role:", dict(collections.Counter(r.get("role") for r in runs)))
print("    run records by purpose:")
for purpose, n in sorted(collections.Counter(r["purpose"] for r in runs).items()):
    print("       ", purpose, n)
print("    run records by budget:")
for budget, n in sorted(collections.Counter(canon(r["budget"]) for r in runs).items()):
    print("       ", budget, n)
print("    run records by (env, budget part):",
      dict(sorted(collections.Counter((r["env"], r["budget"].get("part", "-"), r["budget"]["n_train"]) for r in runs).items())))
print("    run records by seed:", dict(sorted(collections.Counter(r["seed"] for r in runs).items())))
print("    distinct version digests in run records:", len({r["version"] for r in runs}))
print("    run records with memory_in != 0:", sum(1 for r in runs if r.get("memory_in")))
print("    run records without key:", sum(1 for r in runs if "key" not in r), "| duplicate keys:",
      len(runs) - len({r["key"] for r in runs}))
print("    fields of a run record:", sorted(runs[0]))


def mentions(value, words=("knapsack", "regression")):
    found = set()
    if isinstance(value, str):
        low = value.lower()
        found |= {w for w in words if w in low}
    elif isinstance(value, dict):
        for k, v in value.items():
            found |= mentions(k, words) | mentions(v, words)
    elif isinstance(value, list):
        for v in value:
            found |= mentions(v, words)
    return found


print("    records that name knapsack or regression anywhere (keys or values):")
hits = 0
for r in records:
    found = mentions(r)
    if found:
        hits += 1
        where = sorted(k for k, v in r.items() if mentions(k) or mentions(v))
        print("        idx", r["idx"], "type", r.get("type"), "names", sorted(found), "in fields", where)
print("    total such records:", hits)
print("    run records with env or category knapsack/regression:",
      sum(1 for r in runs if r["env"] in ("knapsack", "regression") or r["category"] in ("knapsack", "regression")))
print("    raw text search of the file: 'knapsack' occurs", raw.count(b"knapsack"), "times; 'regression'",
      raw.count(b"regression"), "times; 'adoption:2'", raw.count(b"adoption:2"), "times")

print("    non-run records, in order:")
for r in records:
    if r.get("type") != "run":
        brief = {k: v for k, v in r.items() if k in ("type", "tag", "role", "round", "name", "improver", "evaluated",
                                                     "improving", "best_cost", "nominee", "adopted", "lineage", "digest",
                                                     "mean_min", "cpu_used", "start", "incumbent", "envs", "seeds",
                                                     "improver_version", "lineages")}
        print("        idx", r["idx"], json.dumps(brief, sort_keys=True))
last = records[-1]
print("    LAST record: idx", last["idx"], json.dumps({k: v for k, v in last.items()}, sort_keys=True)[:400])
unlocks = [r for r in records if r.get("type") == "unlock"]
print("    unlock records:", [(r["idx"], r["role"], r.get("round")) for r in unlocks])
u2 = [r for r in unlocks if r["role"] == "adoption:2"]
if u2:
    after = records[u2[-1]["idx"] + 1:]
    print("    records after the unlock of adoption:2:", len(after), [(r["idx"], r.get("type")) for r in after][:20])
print("    release records:", [(r["idx"], r["role"], r.get("round")) for r in records if r.get("type") == "release"])
print("    round_done records:", [(r["idx"], r.get("round")) for r in records if r.get("type") == "round_done"])

# ---------------------------------------------------------------- registration
reg_file = json.load(open(REG))
regs = [r for r in records if r.get("type") == "registration"]
print("(4) registration records:", [(r["idx"]) for r in regs])
for r in regs:
    mine = hashlib.sha256(canon(reg_file).encode()).hexdigest()
    print("    recorded digest:        ", r["digest"])
    print("    digest of the file now: ", mine, "(package digest:", ledgers.digest(reg_file) + ")")
    print("    digest of the recorded registration body:", hashlib.sha256(canon(r["registration"]).encode()).hexdigest())
    print("    recorded digest == file digest:", r["digest"] == mine, "| recorded body == file content:",
          r["registration"] == reg_file)
print("    ledger untouched by this script:", os.path.getsize(PATH) == size_before and
      hashlib.sha256(open(PATH, "rb").read()).hexdigest() == sha_before)
