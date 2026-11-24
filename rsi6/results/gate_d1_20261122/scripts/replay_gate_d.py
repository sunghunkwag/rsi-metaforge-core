"""Re-measure a sample of the runs of the gate of process d on this machine and compare with the returned ledger.
    python3 replay_gate_d.py LEDGER OUT.json
Scores must agree to the last digit; CPU-seconds are another machine's and are only reported."""
import json, multiprocessing, os, sys
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1"); os.environ.setdefault("OMP_NUM_THREADS", "1")
from rsi6.environments import fresh
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import measure, key_of
from rsi6.learner import designs

fresh.install()
L = ledgers.Ledger(sys.argv[1])
runs = [r for r in L.records if r.get("type") == "run" and str(r.get("purpose", "")).split(":")[1:2] == ["d"]]
v0 = designs.default("a"); nominee = designs.validate(dict(v0, **{"model.batch": 2}))
by_digest = {designs.digest(v0): v0, designs.digest(nominee): nominee}
sample = [r for r in runs if r["seed"] in (8101, 8117, 9101, 9117)]          # two seeds of the gate, two of the confirmation, both versions, four categories
jobs = [{"env": r["env"], "version": by_digest[r["version"]], "seed": r["seed"], "budget": r["budget"], "purpose": r["purpose"]} for r in sample]
assert all(key_of(j) == r["key"] for j, r in zip(jobs, sample))
with multiprocessing.get_context("fork").Pool(2) as pool:
    results = pool.map(measure, jobs, chunksize=1)
IGNORE = {"cpu", "idx", "prev", "h", "key", "role"}
rows, same = [], 0
for r, got in zip(sample, results):
    rec = got["record"]
    differ = sorted(k for k in set(r) | set(rec) if k not in IGNORE and r.get(k) != rec.get(k))
    same += not differ
    rows.append({"env": r["env"], "seed": r["seed"], "version": r["version"][:12], "purpose": r["purpose"], "fields_that_differ": differ,
                 "acquired": [r["acquired"], rec["acquired"]], "untrained": [r["untrained"], rec["untrained"]],
                 "cpu_recorded": r["cpu"]["acquire"] + r["cpu"]["apply"], "cpu_here": rec["cpu"]["acquire"] + rec["cpu"]["apply"]})
out = {"what": "a sample of the runs of the gate of process d, measured again on the session's machine", "runs": len(rows), "identical": same,
       "cpu_here_over_recorded": sum(x["cpu_here"] for x in rows) / sum(x["cpu_recorded"] for x in rows), "rows": rows}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(f"runs {len(rows)} identical {same}; cpu here / recorded {out['cpu_here_over_recorded']:.3f}")
for x in rows:
    if x["fields_that_differ"]:
        print("DIFFERS", x["env"], x["seed"], x["version"], x["fields_that_differ"])
