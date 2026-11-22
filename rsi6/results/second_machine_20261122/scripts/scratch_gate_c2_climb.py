"""Outside the ledger: the gate and the confirmation that generation 2 of process c had not yet run
for its fourth nominee (technique 'climb'), computed with the package's own rule (rsi6.meta.rounds).

Incumbent records are the ledger's (their scores were re-measured on this machine and are identical).
The nominee's 36 runs are measured here. Nothing is written to any ledger. Two CPU ratios are
reported: the one the registered rule would compute from mixed machines, and the same-machine one."""
import json, multiprocessing, os, sys, time
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1"); os.environ.setdefault("OMP_NUM_THREADS", "1")
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import key_of, measure
from rsi6.learner import designs
from rsi6.meta import rounds

repo, outdir, replay_path = sys.argv[1], sys.argv[2], sys.argv[3]
L = ledgers.Ledger(os.path.join(repo, "rsi6/ledger/main.jsonl"))
reg = L.select(type="registration_c")[-1]["registration"]
rounds.RULES.update(reg["rules"])
g = 2
current = [a for a in L.select(type="adopt", process="c") if a["round"] < g][-1]["version"]
nom_rec = L.select(type="c_nominee", tag="c2:climb")[-1]
nominee = nom_rec["version"]
assert designs.digest(nominee) == nom_rec["nominee"]
ref_gate = L.select(type="gate", tag="gate:c2:single")[-1]
aside = ref_gate["envs"]
gate_seeds = [2000 + 10 * g + k for k in range(1, 7)]
confirm_seeds = [3000 + 10 * g + k for k in range(1, 7)]
budget = reg["budgets"]["run"]
by_key = {r["key"]: r for r in L.records if r.get("type") == "run" and "key" in r}


class Scratch:
    """Serves recorded runs from the ledger and the runs measured here; writes nothing."""
    def __init__(self):
        self.new = {}
    def get(self, jobs, workers: int = 4):
        missing = [j for j in jobs if key_of(j) not in by_key and key_of(j) not in self.new]
        if missing:
            with multiprocessing.get_context("fork").Pool(workers) as pool:
                results = pool.map(measure, missing, chunksize=1)
            for j, res in zip(missing, results):
                rec = dict(res["record"], key=key_of(j))
                self.new[rec["key"]] = rec
                with open(os.path.join(outdir, "nominee_runs.jsonl"), "a") as h:
                    h.write(json.dumps(rec, sort_keys=True) + "\n")
        return [by_key.get(key_of(j)) or self.new[key_of(j)] for j in jobs]


cache = Scratch()
# 1. the harness reproduces a recorded decision from recorded runs alone
single = L.select(type="c_nominee", tag="c2:single")[-1]["version"]
again = rounds.gate(current, single, aside, gate_seeds, budget, cache, "gate:c2:single", seed=200 + g)
keys = ("mean_min", "mean_gain_change", "mean_acquired_change", "gain_lower_bound", "cpu_ratio", "conditions", "adopted")
harness_ok = all(again[k] == ref_gate[k] for k in keys) and not cache.new
print("harness reproduces the recorded gate of c2:single:", harness_ok, flush=True)
if not harness_ok:
    raise SystemExit("the harness does not reproduce a recorded gate; nothing further is computed")
# 2. the pending nominee
t0 = time.time()
decision = rounds.gate(current, nominee, aside, gate_seeds, budget, cache, "gate:c2:climb", seed=200 + g)
t1 = time.time()
check = rounds.confirm(current, nominee, aside, confirm_seeds, budget, cache, "confirm:c2:climb")
t2 = time.time()
replay = json.load(open(replay_path))
same_machine = decision["cpu"]["nominee"] / replay["cpu_here"]
out = {"what": "computed outside the ledger on a second machine; not a registered record",
       "generation": g, "technique": "climb", "incumbent": designs.digest(current), "nominee": designs.digest(nominee),
       "changes": nom_rec.get("changes"), "set_aside": aside, "gate_seeds": gate_seeds, "confirm_seeds": confirm_seeds,
       "harness_reproduces_recorded_gate_c2_single": harness_ok,
       "gate": decision, "confirm": check,
       "cpu": {"incumbent_gate_recorded_first_machine": decision["cpu"]["incumbent"],
               "incumbent_gate_this_machine": replay["cpu_here"], "nominee_gate_this_machine": decision["cpu"]["nominee"],
               "ratio_as_the_rule_would_compute_it_mixed_machines": decision["cpu_ratio"],
               "ratio_same_machine": same_machine, "limit": rounds.RULES["cpu_ratio"]},
       "score_conditions": {"improvement": decision["conditions"]["improvement"], "gain_interval": decision["conditions"]["gain_interval"]},
       "cpu_condition_same_machine": bool(same_machine <= rounds.RULES["cpu_ratio"]),
       "would_be_adopted_by_rule_with_same_machine_cpu": bool(decision["conditions"]["improvement"] and decision["conditions"]["gain_interval"]
                                                             and same_machine <= rounds.RULES["cpu_ratio"] and check["mean_min"] > 0.0),
       "wall_seconds": {"gate": round(t1 - t0, 1), "confirm": round(t2 - t1, 1)}, "workers": 4, "cpus": os.cpu_count()}
json.dump(out, open(os.path.join(outdir, "gate_c2_climb.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ("changes",)}, indent=1))
