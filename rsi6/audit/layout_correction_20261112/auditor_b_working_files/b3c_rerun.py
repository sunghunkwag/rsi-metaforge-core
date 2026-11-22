"""Auditor B, B3: repeat recorded runs with the corrected code and compare with the ledger.

    python3 b3c_rerun.py <phase> <worker> <workers>

For every chosen run record: job = {env, version (recovered dictionary), seed, the record's budget,
purpose "audit"}; the job's key must equal the record's key; rsi6.kernel.run.measure(job) is called
(it writes nothing); every field of the new record is compared with the ledger's, except the
measured CPU and the fields the ledger adds (purpose, role, key, idx, prev, h).

Only the five environments that have run records are ever passed to measure().  Reads REPO; appends
to WORK/rerun_<phase>_<worker>.jsonl (already finished records are skipped, so it can be resumed).
"""
import json
import os
import sys
import time

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
WORK = os.path.join(BASE, "work_b")
sys.path.insert(0, REPO)
assert os.environ.get("OPENBLAS_NUM_THREADS") == "1" and os.environ.get("OMP_NUM_THREADS") == "1"

from rsi6.kernel import ledger as ledgers          # noqa: E402
from rsi6.kernel import run                        # noqa: E402
from rsi6.learner import version as versions       # noqa: E402

ALLOWED = {"forecasting", "jobshop", "binpacking", "quadassign", "pmedian"}
SKIP = {"cpu", "purpose", "role", "key", "idx", "prev", "h"}
NAMED = ["untrained", "acquired", "gain", "train_untrained", "train_acquired", "fresh_untrained", "fresh_acquired",
         "fresh_ids", "units", "capability"]

phase, worker, workers = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
plan = json.load(open(os.path.join(WORK, "plan.json")))
known = json.load(open(os.path.join(WORK, "versions.json")))
chosen = plan[phase]
if isinstance(chosen, dict):
    chosen = [i for env in sorted(chosen) for i in chosen[env]]
records = {}
for line in open(os.path.join(REPO, "rsi6", "ledger", "main.jsonl")):
    if line.strip():
        r = json.loads(line)
        records[r["idx"]] = r
out_path = os.path.join(WORK, f"rerun_{phase}_{worker}.jsonl")
done = set()
if os.path.exists(out_path):
    done = {json.loads(line)["idx"] for line in open(out_path) if line.strip()}
# spread the long runs over the workers: order by environment, then deal out
mine = [i for k, i in enumerate(chosen) if k % workers == worker]
for idx in mine:
    if idx in done:
        continue
    old = records[idx]
    assert old["type"] == "run" and old["env"] in ALLOWED, (idx, old.get("env"))
    version = versions.validate(known[old["version"]])
    job = {"env": old["env"], "version": version, "seed": old["seed"], "budget": old["budget"], "purpose": "audit"}
    key_ok = run.key_of(job) == old["key"] and versions.digest(version) == old["version"]
    started = time.process_time()
    new = run.measure(dict(job))["record"]
    cpu_total = time.process_time() - started
    fields = sorted((set(old) | set(new)) - SKIP)
    diff = {}
    for f in fields:
        if f not in old or f not in new:
            diff[f] = ["absent in ledger" if f not in old else old[f], "absent in repetition" if f not in new else new[f]]
        elif ledgers.canon(old[f]) != ledgers.canon(new[f]):
            diff[f] = [old[f], new[f]]
    line = {"idx": idx, "env": old["env"], "version": old["version"], "seed": old["seed"], "budget": old["budget"],
            "purpose": old["purpose"], "key_ok": key_ok, "fields_compared": fields,
            "named_fields_present": all(f in old and f in new for f in NAMED),
            "same": not diff, "diff": diff, "cpu_ledger": old["cpu"], "cpu_repetition": new["cpu"],
            "cpu_process": round(cpu_total, 3),
            "values": {f: new[f] for f in ("untrained", "acquired", "gain", "train_untrained", "train_acquired", "capability")}}
    with open(out_path, "a") as handle:
        handle.write(json.dumps(line, sort_keys=True) + "\n")
print("worker", worker, "of", workers, "phase", phase, "finished:", len(mine), "records")
