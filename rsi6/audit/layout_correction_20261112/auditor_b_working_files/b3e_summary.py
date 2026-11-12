"""Auditor B, B3: summary of the repetitions, and two negative controls of the comparison.

    python3 b3e_summary.py [controls]

Reads WORK/rerun_*.jsonl and REPO; with the argument "controls" it also runs four jobs on
quadassign and forecasting that are deliberately NOT the recorded ones (another seed, another
version), to show that the comparison does report differences when there are any.
"""
import collections
import glob
import json
import os
import sys

import numpy as np

BASE = "/tmp/claude-0/-home-user-rsi-metaforge-core/49317f35-39aa-5636-a36c-c80f42cd346e/scratchpad/audit2"
REPO = os.path.join(BASE, "repo")
WORK = os.path.join(BASE, "work_b")
sys.path.insert(0, REPO)

records = {}
for line in open(os.path.join(REPO, "rsi6", "ledger", "main.jsonl")):
    if line.strip():
        r = json.loads(line)
        records[r["idx"]] = r
runs = {i: r for i, r in records.items() if r["type"] == "run"}
plan = json.load(open(os.path.join(WORK, "plan.json")))

done = {}
per_phase = collections.OrderedDict()
for path in sorted(glob.glob(os.path.join(WORK, "rerun_phase*_*.jsonl"))):
    phase = os.path.basename(path).split("_")[1]
    for line in open(path):
        if line.strip():
            row = json.loads(line)
            per_phase.setdefault(phase, []).append(row)
            done.setdefault(row["idx"], []).append(row)
NAMED = ["untrained", "acquired", "gain", "train_untrained", "train_acquired", "fresh_untrained", "fresh_acquired",
         "fresh_ids", "units", "capability"]
for phase, rows in per_phase.items():
    planned = plan[phase]
    planned = [i for env in sorted(planned) for i in planned[env]] if isinstance(planned, dict) else planned
    print(f"{phase}: planned {len(planned)}, repeated {len(rows)}, all planned done: {set(planned) == {r['idx'] for r in rows}}, "
          f"identical {sum(r['same'] for r in rows)}, different {sum(not r['same'] for r in rows)}, "
          f"key recomputed equal {sum(r['key_ok'] for r in rows)}, "
          f"by env {dict(sorted(collections.Counter(r['env'] for r in rows).items()))}, "
          f"version digests {len({r['version'] for r in rows})}")
rows = [v[0] for v in done.values()]
print("ALL PHASES: distinct run records repeated:", len(rows), "of", len(runs),
      "| identical:", sum(r["same"] for r in rows), "| different:", sum(not r["same"] for r in rows))
print("   records repeated twice (in two phases):", sum(1 for v in done.values() if len(v) > 1),
      "| of these, both repetitions identical to the ledger:", sum(1 for v in done.values() if len(v) > 1 and all(x["same"] for x in v)))
print("   by environment:", {e: f"{n} of {sum(1 for r in runs.values() if r['env'] == e)}"
                             for e, n in sorted(collections.Counter(r["env"] for r in rows).items())})
print("   version digests:", len({r["version"] for r in rows}), "of", len({r["version"] for r in runs.values()}))
print("   budgets:", dict(collections.Counter((r["budget"]["n_train"], r["budget"].get("part")) for r in rows)))
print("   purposes:", dict(sorted(collections.Counter(r["purpose"].rsplit(":", 1)[0] if r["purpose"].count(":") > 2 else r["purpose"] for r in rows).items())))
print("   seeds:", dict(sorted(collections.Counter(r["seed"] for r in rows).items())))
fields = collections.Counter(tuple(r["fields_compared"]) for r in rows)
print("   fields compared in every repetition:", [list(k) for k in fields][0] if len(fields) == 1 else dict(fields))
print("   the ten fields named in the task present and compared in every repetition:",
      all(r["named_fields_present"] and set(NAMED) <= set(r["fields_compared"]) for r in rows))
for r in rows:
    if not r["same"]:
        print("   DIFFERENCE idx", r["idx"], r["env"], json.dumps(r["diff"], sort_keys=True)[:500])
# the values really are the ledger's (belt and braces: compare the stored new values with the ledger again)
again = 0
for r in rows:
    old = runs[r["idx"]]
    again += any(old[f] != r["values"][f] for f in r["values"])
print("   repetitions whose stored values (untrained, acquired, gain, train_*, capability) differ from the ledger on a second comparison:", again)
informative = collections.Counter()
for r in rows:
    old = runs[r["idx"]]
    informative[(r["env"], "learned" if old["report"].get("learned") else "not learned",
                 "gain != 0" if old["gain"] != 0 else "gain == 0")] += 1
print("   what the repeated records contain (env, learned, gain):", dict(sorted(informative.items())))
ratio = collections.defaultdict(list)
for r in rows:
    a = r["cpu_ledger"]["acquire"] + r["cpu_ledger"]["apply"]
    b = r["cpu_repetition"]["acquire"] + r["cpu_repetition"]["apply"]
    if a > 0.2:
        ratio[r["env"]].append(b / a)
print("   measured CPU, repetition / ledger (not a result; for information):",
      {e: f"median {np.median(v):.2f} (n {len(v)})" for e, v in sorted(ratio.items())})
part = collections.defaultdict(list)
for r in rows:
    for which in ("acquire", "apply"):
        if r["cpu_ledger"][which] > 0.2:
            part[(r["env"], which)].append(r["cpu_repetition"][which] / r["cpu_ledger"][which])
print("   the same, separately for acquire (the new check is outside its clock) and apply (the new check is inside):",
      {f"{e}/{w}": f"median {np.median(v):.2f} (n {len(v)})" for (e, w), v in sorted(part.items())})
phase1 = [i for env in sorted(plan["phase1"]) for i in plan["phase1"][env]]
print("   phase 1 alone (the stratified random sample, seed", plan["seed"], "):", len(phase1), "records,",
      sum(done[i][0]["same"] for i in phase1 if i in done), "identical;",
      len({runs[i]["version"] for i in phase1}), "version digests;",
      dict(sorted(collections.Counter(runs[i]["env"] for i in phase1).items())))
if "phase4" in plan:
    order = plan["phase4"]
    finished = [i for i in order if i in done]
    print("   phase 4 (the rest of binpacking and jobshop in random order):", len(finished), "of", len(order), "finished")
print("   total CPU-seconds of the repetitions (process time):", round(sum(r["cpu_process"] for v in done.values() for r in v), 1))

if len(sys.argv) > 1 and sys.argv[1] == "controls":
    from rsi6.kernel import ledger as ledgers          # noqa: E402
    from rsi6.kernel import run                        # noqa: E402
    from rsi6.learner import version as versions       # noqa: E402
    known = json.load(open(os.path.join(WORK, "versions.json")))
    SKIP = {"cpu", "purpose", "role", "key", "idx", "prev", "h"}
    print("NEGATIVE CONTROLS (jobs that are deliberately not the recorded ones)")
    for idx in (plan["phase1"]["quadassign"][0], plan["phase1"]["forecasting"][0]):
        old = runs[idx]
        version = versions.validate(known[old["version"]])
        other_seed = {"env": old["env"], "version": version, "seed": old["seed"] + 1000, "budget": old["budget"], "purpose": "audit-control"}
        changed = dict(version)
        changed["predict.K" if old["env"] == "forecasting" else "model.pop"] = 16 if old["env"] == "forecasting" and version["predict.K"] != 16 else (4 if old["env"] == "forecasting" else (32 if version["model.pop"] != 32 else 8))
        other_version = {"env": old["env"], "version": versions.validate(changed), "seed": old["seed"], "budget": old["budget"], "purpose": "audit-control"}
        same_job = {"env": old["env"], "version": version, "seed": old["seed"], "budget": old["budget"], "purpose": "audit-control"}
        for label, job in (("the recorded job", same_job), ("another seed", other_seed), ("another version", other_version)):
            new = run.measure(dict(job))["record"]
            diff = sorted(f for f in (set(old) | set(new)) - SKIP if ledgers.canon(old.get(f)) != ledgers.canon(new.get(f)))
            print(f"   idx {idx} {old['env']}: {label}: fields that differ from the ledger record: {diff}")
