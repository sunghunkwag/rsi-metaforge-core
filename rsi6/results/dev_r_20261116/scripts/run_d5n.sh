#!/bin/sh
# Development D5 with the new driver and report: dry runs A (stopped once and restarted) and B.
S=<scratch>
cd $S
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONHASHSEED=0 PYTHONPATH=<repo>
A=$S/dev_r_d5a.jsonl; B=$S/dev_r_d5b.jsonl
cp <repo>/rsi6/ledger/main.jsonl $A
nice -n 10 python3 -m rsi6.open.relay --stage meta --dev --ledger $A --registration $S/registration_r_d5a.json > $S/dev_r_d5a_meta.log 2>&1 || { echo "meta failed"; exit 1; }
cp $A $B
nice -n 10 python3 -m rsi6.open.relay --stage heldout --dev --ledger $A --registration $S/registration_r_d5a.json > $S/dev_r_d5a_h1.log 2>&1 &
P=$!
until grep -q "held-out offpolicy" $S/dev_r_d5a_h1.log || ! kill -0 $P 2>/dev/null; do sleep 5; done
kill -INT $P; wait $P; echo "stopped A: $(tail -n 1 $S/dev_r_d5a_h1.log | cut -c1-120)"
nice -n 10 python3 -m rsi6.open.relay --stage heldout --dev --ledger $A --registration $S/registration_r_d5a.json > $S/dev_r_d5a_h2.log 2>&1 || { echo "A restart failed"; exit 1; }
nice -n 10 python3 -m rsi6.open.relay_report --ledger $A --registration $S/registration_r_d5a.json --json $S/dev_r_d5a_report.json > $S/dev_r_d5a_report.txt 2>&1 || { echo "A report failed"; exit 1; }
python3 - <<'PY'
import json
S = "<scratch>"
from rsi6.kernel import ledger as ledgers
L = ledgers.Ledger(S + "/dev_r_d5b.jsonl")
meta = sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in L.records if r.get("type") == "run" and r.get("purpose", "").startswith(("relay-meta:", "relay-retention:")))
b = json.load(open(S + "/registration_r_d5b_template.json"))
b["heldout"]["cpu_total"] = 1.15 * meta + 1.15 * 45.0
json.dump(b, open(S + "/registration_r_d5b.json", "w"), indent=1)
print("B cpu_total", b["heldout"]["cpu_total"], "meta", meta)
PY
nice -n 10 python3 -m rsi6.open.relay --stage heldout --dev --ledger $B --registration $S/registration_r_d5b.json > $S/dev_r_d5b_h.log 2>&1 || { echo "B failed"; exit 1; }
nice -n 10 python3 -m rsi6.open.relay_report --ledger $B --registration $S/registration_r_d5b.json --json $S/dev_r_d5b_report.json > $S/dev_r_d5b_report.txt 2>&1 || { echo "B report failed"; exit 1; }
echo "D5 new done"
