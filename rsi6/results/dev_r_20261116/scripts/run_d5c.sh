#!/bin/sh
# Development D5, dry run A stopped once (SIGTERM) and restarted, on a copy of A's ledger cut just
# before its held-out stage; the restarted stage must replay and agree, and its acquired scores
# must equal A's run for run.
S=<scratch>
cd $S
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONHASHSEED=0 PYTHONPATH=<repo>
C=$S/dev_r_d5c.jsonl
python3 - <<'PY'
import json
S = "<scratch>"
lines = open(S + "/dev_r_d5a.jsonl").read().split("\n")
out = []
for line in lines:                                   # up to and with the meta stage's r_stage_done record
    if not line.strip():
        continue
    out.append(line)
    r = json.loads(line)
    if r.get("type") == "r_stage_done" and r.get("stage") == "meta":
        break
assert json.loads(out[-1]).get("stage") == "meta"
open(S + "/dev_r_d5c.jsonl", "w").write("\n".join(out) + "\n")
print("cut at", len(out))
PY
nice -n 10 python3 -m rsi6.open.relay --stage heldout --dev --ledger $C --registration $S/registration_r_d5a.json > $S/dev_r_d5c_h1.log 2>&1 &
P=$!
until grep -q "held-out offpolicy" $S/dev_r_d5c_h1.log || ! kill -0 $P 2>/dev/null; do sleep 3; done
kill -TERM $P; sleep 20; echo "stopped C after: $(tail -n 1 $S/dev_r_d5c_h1.log | cut -c1-120)"
nice -n 10 python3 -m rsi6.open.relay --stage heldout --dev --ledger $C --registration $S/registration_r_d5a.json > $S/dev_r_d5c_h2.log 2>&1 || { echo "C restart failed"; exit 1; }
nice -n 10 python3 -m rsi6.open.relay_report --ledger $C --registration $S/registration_r_d5a.json --json $S/dev_r_d5c_report.json > $S/dev_r_d5c_report.txt 2>&1 || { echo "C report failed"; exit 1; }
python3 - <<'PY'
import json
S = "<scratch>"
from rsi6.kernel import ledger as ledgers
A, C = ledgers.Ledger(S + "/dev_r_d5a.jsonl"), ledgers.Ledger(S + "/dev_r_d5c.jsonl")
acq = lambda L: {r["key"]: (r["acquired"], r["gain"]) for r in L.records if r.get("type") == "run" and str(r.get("purpose", "")).startswith("relay-heldout:")}
a, c = acq(A), acq(C)
same = all(a[k] == c[k] for k in a if k in c)
print("held-out runs A", len(a), "C", len(c), "common", len(set(a) & set(c)), "identical acquired and gain:", same)
print("C records:", sorted({r["type"] for r in C.records if str(r.get("type", "")).startswith("r_")}))
PY
echo "D5c done"
