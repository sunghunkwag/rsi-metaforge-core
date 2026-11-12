"""The test on the sealed target categories. Run once, after the rounds are finished and frozen.

    python -m rsi6.experiments.targets [--ledger PATH]

It refuses to start unless the ledger holds the record that freezes every lineage, and unless
``registry/targets.json`` lists the target adapters that passed their audit. It then unlocks
the target role and measures, on every target environment and every registered seed:

  frozen      the learner at generation 0, empty memory
  self:g      the self lineage's version after round g, empty memory (the last one is the primary)
  fixed       the final version of the lineage whose improver was always generation 0
  random      the final version of the lineage whose improver was the random proposer
  skills      generation 0 with the memory of its own acquisitions on every earlier environment
  memory      the final self version with the memory of its own acquisitions
  compute     generation 0 with its training budget raised until its measured CPU-seconds reach
              those of the final self version plus an equal share of what the self lineage spent
              on its rounds
  search      generation 0 with no training and its test-time budget raised to the same CPU

Statistics are computed by ``report.py`` from the ledger.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from rsi6 import environments
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles, run
from rsi6.learner import version as versions
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(os.path.dirname(HERE), "registry")
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def memory_of(version: dict, envs, budget: dict, ledger, purpose: str) -> dict:
    """The memory a version has after acquiring on the given environments, in order."""
    memory = None
    for name in envs:
        roles.check(environments.load(name).category, ledger)
        result = run.measure({"env": name, "version": version, "seed": 1, "budget": budget, "purpose": purpose,
                              "memory": memory, "return_memory": True})
        result["record"]["role"] = "source"
        result["record"]["key"] = run.key_of({"env": name, "version": version, "seed": 1, "budget": budget, "memory": memory})
        ledger.append(result["record"])
        memory = result["memory"]
    return memory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    args = parser.parse_args()
    reg = json.load(open(os.path.join(REGISTRY, "registration.json")))
    ledger = ledgers.Ledger(args.ledger)
    frozen = ledger.select(type="freeze")
    if not frozen:
        raise SystemExit("the lineages are not frozen: no target run before that")
    admitted = json.load(open(os.path.join(REGISTRY, "targets.json")))["admitted"]
    targets = sorted(admitted)
    if not ledger.select(type="unlock", role="target"):
        ledger.append({"type": "unlock", "role": "target", "targets": targets})
    cache = run.Cache(ledger)
    seeds, budget = reg["seeds"]["target"], reg["budgets"]["run"]
    v0 = versions.default()
    lineage = frozen[-1]["lineages"]
    arms = {"frozen": v0}
    for record in ledger.select(type="adopt", lineage="self"):
        arms[f"self:{record['round']}"] = record["version"]
    final_self = lineage["self"]
    arms["fixed"], arms["random"] = lineage["fixed"], lineage["random"]
    results = {}
    for arm, version in arms.items():
        results[arm] = cache.get(rounds.jobs_for(version, targets, seeds, budget, f"target:{arm}"))
        say(arm, versions.digest(version)[:12], "acquired %.4f gain %+.4f" % (
            sum(r["acquired"] for r in results[arm]) / len(results[arm]), sum(r["gain"] for r in results[arm]) / len(results[arm])))
    # arms with memory: what each version carries from every environment it met before the targets
    earlier = rounds.pool(ledger)
    for arm, version in (("skills", v0), ("memory", final_self)):
        memory = memory_of(version, earlier, budget, ledger, f"memory:{arm}")
        jobs = [dict(job, memory=memory) for job in rounds.jobs_for(version, targets, seeds, budget, f"target:{arm}")]
        results[arm] = cache.get(jobs)
        say(arm, "entries in memory", len(memory["entries"]), "acquired %.4f gain %+.4f" % (
            sum(r["acquired"] for r in results[arm]) / len(results[arm]), sum(r["gain"] for r in results[arm]) / len(results[arm])))
    # compute-matched arms. What the self lineage spent on improving itself, shared equally over the target runs.
    spent = sum(r["cpu_used"] for r in ledger.select(type="search", name="self"))
    spent += sum(r["cpu"]["incumbent"] + r["cpu"]["nominee"] for r in ledger.select(type="gate", name="self"))
    spent += sum(r["cpu"]["incumbent"] + r["cpu"]["nominee"] for r in ledger.select(type="confirm", name="self"))
    share = spent / (len(targets) * len(seeds))
    primary_arm = [a for a in arms if a.startswith("self:")][-1] if any(a.startswith("self:") for a in arms) else "frozen"
    for arm, field, start in (("compute", "train", budget["train"]), ("search", "test_e", budget["test_e"])):
        rows = []
        for name in targets:
            for seed in seeds:
                reference = [r for r in results[primary_arm] if r["env"] == name and r["seed"] == seed][0]
                want = reference["cpu"]["acquire"] + reference["cpu"]["apply"] + share
                value, record = start, None
                for _ in range(12):
                    this = dict(budget, **{field: value})
                    if arm == "search":
                        this["train"] = 0.0
                    record = cache.get([{"env": name, "version": v0, "seed": seed, "budget": this, "purpose": f"target:{arm}"}])[0]
                    if record["cpu"]["acquire"] + record["cpu"]["apply"] >= want:
                        break
                    value *= 2.0
                rows.append(dict(record, matched_cpu=want, reached=record["cpu"]["acquire"] + record["cpu"]["apply"] >= want))
        results[arm] = rows
        ledger.append({"type": "matched", "arm": arm, "share_per_run": share, "spent_by_self_lineage": spent,
                       "keys": [r["key"] for r in rows], "reached": [bool(r["reached"]) for r in rows]})
        say(arm, "share per run %.0f CPU-s" % share, "acquired %.4f" % (sum(r["acquired"] for r in rows) / len(rows)),
            "reached the matched CPU in", sum(1 for r in rows if r["reached"]), "of", len(rows))
    ledger.append({"type": "target_done", "arms": {arm: [r["key"] for r in rows] for arm, rows in results.items()},
                   "primary_arm": primary_arm, "targets": targets, "seeds": seeds})
    return 0


if __name__ == "__main__":
    sys.exit(main())
