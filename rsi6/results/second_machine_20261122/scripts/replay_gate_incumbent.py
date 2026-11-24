"""Re-measure, on this machine and without writing any ledger, the 18 recorded incumbent runs of the
gate of generation 2 of process c, and compare scores and CPU with the ledger's records."""
import json, multiprocessing, os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1"); os.environ.setdefault("OMP_NUM_THREADS", "1")
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import key_of, measure
from rsi6.learner import designs

repo = sys.argv[1]; out = sys.argv[2]; workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
L = ledgers.Ledger(os.path.join(repo, "rsi6/ledger/main.jsonl"))
reg = L.select(type="registration_c")[-1]["registration"]
adopt = [a for a in L.select(type="adopt", process="c") if a["round"] == 1][-1]
version = adopt["version"]
assert designs.digest(version) == adopt["digest"]
gate = L.select(type="gate", tag="gate:c2:single")[-1]
envs, seeds = gate["envs"], gate["seeds"]
budget = dict(reg["budgets"]["run"], part="A")
jobs = [{"env": e, "version": version, "seed": s, "budget": budget, "purpose": "replay-check"} for e in envs for s in seeds]
by_key = {r["key"]: r for r in L.records if r.get("type") == "run" and "key" in r}
recorded = [by_key[key_of(j)] for j in jobs]
t0 = time.time()
with multiprocessing.get_context("fork").Pool(workers) as pool:
    results = pool.map(measure, jobs, chunksize=1)
wall = time.time() - t0
rows = []
for job, rec, res in zip(jobs, recorded, results):
    new = res["record"]
    same = all(new[k] == rec[k] for k in ("untrained", "acquired", "gain", "fresh_untrained", "fresh_acquired", "capability", "train_acquired", "units"))
    rows.append({"env": job["env"], "seed": job["seed"], "identical": bool(same),
                 "acquired_recorded": rec["acquired"], "acquired_here": new["acquired"],
                 "cpu_recorded": rec["cpu"]["acquire"] + rec["cpu"]["apply"], "cpu_here": new["cpu"]["acquire"] + new["cpu"]["apply"]})
cpu_rec = sum(r["cpu_recorded"] for r in rows); cpu_here = sum(r["cpu_here"] for r in rows)
summary = {"runs": len(rows), "identical": sum(r["identical"] for r in rows), "workers": workers, "cpus": os.cpu_count(), "wall_seconds": round(wall, 1),
           "cpu_recorded": round(cpu_rec, 3), "cpu_here": round(cpu_here, 3), "cpu_ratio_here_over_recorded": round(cpu_here / cpu_rec, 4),
           "gate_record_incumbent_cpu": gate["cpu"]["incumbent"],
           "per_env": {e: {"cpu_recorded": round(sum(r["cpu_recorded"] for r in rows if r["env"] == e), 2),
                           "cpu_here": round(sum(r["cpu_here"] for r in rows if r["env"] == e), 2)} for e in envs},
           "rows": rows}
json.dump(summary, open(out, "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))
