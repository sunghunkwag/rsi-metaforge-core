"""The test on the sealed target categories. Run once, after every improvement process is frozen.

    python -m rsi6.experiments.targets [--ledger PATH]

It refuses to start unless the ledger holds the record that freezes the lineages of the two
registered rounds and, if the continued process of amendment 2 was registered, the record that
freezes its lineages too; and unless ``registry/targets.json`` lists the target adapters that
passed their audit. It then unlocks the target role and measures, on every target environment
and every registered seed, the arms of both processes.

Arms of the two registered rounds (first design of the learner):

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

Arms of the continued process (second design), named with the prefix ``b:``: the same eight,
with generation 0 of the second design in the place of generation 0. And one arm across the
designs: ``compute@b``, generation 0 of the first design with its training budget raised until
its measured CPU-seconds reach those of the primary arm of the continued process plus an equal
share of what that process spent on its rounds.

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
from rsi6.learner import designs
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(os.path.dirname(HERE), "registry")
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def memory_of(version: dict, envs, budget: dict, cache, purpose: str) -> dict:
    """The memory a version has after acquiring on the given environments, in order. The memory
    itself is not in the ledger, so the acquisitions are repeated when the driver is started
    again; their records are written once."""
    memory = None
    for name in envs:
        roles.check(environments.load(name).category, cache.ledger)
        job = {"env": name, "version": version, "seed": 1, "budget": budget, "purpose": purpose, "memory": memory}
        result = run.measure(dict(job, return_memory=True))
        key = run.key_of(job)
        if key not in cache.by_key:
            cache.by_key[key] = cache.ledger.append(dict(result["record"], role="source", key=key))
        memory = result["memory"]
    return memory


def mean(rows, field) -> float:
    return sum(r[field] for r in rows) / len(rows)


def cpu(record) -> float:
    return record["cpu"]["acquire"] + record["cpu"]["apply"]


def matched(arm, version, field, want, targets, seeds, budget, cache, ledger, spent, share) -> list:
    """Generation 0 with one budget raised, pair by pair, until its measured CPU reaches ``want``."""
    value, last = {pair: budget[field] for pair in want}, {}
    pending = list(want)
    for _ in range(12):
        if not pending:
            break
        jobs = []
        for name, seed in pending:
            this = dict(budget, **{field: value[(name, seed)]})
            if field == "test_e":
                this["train"] = 0.0
            jobs.append({"env": name, "version": version, "seed": seed, "budget": this, "purpose": f"target:{arm}"})
        for pair, record in zip(pending, cache.get(jobs)):
            last[pair] = record
            value[pair] *= 2.0
        pending = [pair for pair in pending if cpu(last[pair]) < want[pair]]
        say(arm, "level done;", len(pending), "pairs below the matched CPU")
    rows = [dict(last[pair], matched_cpu=want[pair], reached=cpu(last[pair]) >= want[pair]) for pair in want]
    ledger.append({"type": "matched", "arm": arm, "share_per_run": share, "spent_by_self_lineage": spent,
                   "keys": [r["key"] for r in rows], "reached": [bool(r["reached"]) for r in rows]})
    say(arm, "share per run %.0f CPU-s" % share, "acquired %.4f" % mean(rows, "acquired"),
        "reached the matched CPU in", sum(1 for r in rows if r["reached"]), "of", len(rows))
    return rows


def process_arms(prefix, v0, lineage, adopted, spent, targets, seeds, budget, cache, ledger, earlier) -> tuple:
    """The eight arms of one process. Returns the results by arm and the name of its primary arm."""
    results = {}
    arms = {f"{prefix}frozen": v0}
    for record in adopted:
        arms[f"{prefix}self:{record['round']}"] = record["version"]
    arms[f"{prefix}fixed"], arms[f"{prefix}random"] = lineage["fixed"], lineage["random"]
    for arm, version in arms.items():
        results[arm] = cache.get(rounds.jobs_for(version, targets, seeds, budget, f"target:{arm}"))
        say(arm, designs.digest(version)[:12], "acquired %.4f gain %+.4f" % (mean(results[arm], "acquired"), mean(results[arm], "gain")))
    for arm, version in ((f"{prefix}skills", v0), (f"{prefix}memory", lineage["self"])):
        memory = memory_of(version, earlier, budget, cache, f"memory:{arm}")
        jobs = [dict(job, memory=memory) for job in rounds.jobs_for(version, targets, seeds, budget, f"target:{arm}")]
        results[arm] = cache.get(jobs)
        say(arm, "entries in memory", len(memory["entries"]), "acquired %.4f gain %+.4f" % (mean(results[arm], "acquired"), mean(results[arm], "gain")))
    selfs = [a for a in arms if a.startswith(f"{prefix}self:")]
    primary = selfs[-1] if selfs else f"{prefix}frozen"
    share = spent / (len(targets) * len(seeds))
    want = {(r["env"], r["seed"]): cpu(r) + share for r in results[primary]}
    results[f"{prefix}compute"] = matched(f"{prefix}compute", v0, "train", want, targets, seeds, budget, cache, ledger, spent, share)
    results[f"{prefix}search"] = matched(f"{prefix}search", v0, "test_e", want, targets, seeds, budget, cache, ledger, spent, share)
    return results, primary, want, share


def spent_by(ledger, names) -> float:
    """Measured CPU of the searches, gates and confirmations of the self lineage with these tags."""
    total = sum(r["cpu_used"] for r in ledger.select(type="search", name="self") if r["tag"] in names["search"])
    for kind in ("gate", "confirm"):
        total += sum(r["cpu"]["incumbent"] + r["cpu"]["nominee"] for r in ledger.select(type=kind, name="self") if r["tag"] in names[kind])
    return float(total)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--targets", default=os.path.join(REGISTRY, "targets.json"),
                        help="the list of admitted target adapters (another file only for a development run)")
    args = parser.parse_args()
    reg = json.load(open(os.path.join(REGISTRY, "registration.json")))
    ledger = ledgers.Ledger(args.ledger)
    frozen_a = [r for r in ledger.select(type="freeze") if r.get("process") != "b"]
    frozen_b = ledger.select(type="freeze", process="b")
    if not frozen_a:
        raise SystemExit("the lineages are not frozen: no target run before that")
    if ledger.select(type="registration_b") and not frozen_b:
        raise SystemExit("the continued process is registered and not frozen: no target run before that")
    admitted = json.load(open(args.targets))["admitted"]
    targets = sorted(admitted)
    if not ledger.select(type="unlock", role="target"):
        ledger.append({"type": "unlock", "role": "target", "targets": targets})
    cache = run.Cache(ledger)
    seeds, budget = reg["seeds"]["target"], reg["budgets"]["run"]
    earlier = rounds.pool(ledger)
    # ---- the two registered rounds
    tags = lambda kind, label: {f"{kind}:{label}{g}:self" for g in range(1, 10)}
    names_a = {kind: tags(kind, "") for kind in ("search", "gate", "confirm")}
    adopted_a = [r for r in ledger.select(type="adopt", lineage="self") if r.get("process") != "b"]
    results, primary, _, _ = process_arms("", designs.default("a"), frozen_a[-1]["lineages"], adopted_a, spent_by(ledger, names_a),
                                          targets, seeds, budget, cache, ledger, earlier)
    done = {"type": "target_done", "primary_arm": primary, "targets": targets, "seeds": seeds}
    # ---- the continued process
    if frozen_b:
        names_b = {kind: tags(kind, "b") for kind in ("search", "gate", "confirm")}
        adopted_b = ledger.select(type="adopt", process="b", lineage="self")
        more, primary_b, want_b, share_b = process_arms("b:", designs.default("b"), frozen_b[-1]["lineages"], adopted_b,
                                                        spent_by(ledger, names_b), targets, seeds, budget, cache, ledger, earlier)
        results.update(more)
        results["compute@b"] = matched("compute@b", designs.default("a"), "train", want_b, targets, seeds, budget, cache, ledger,
                                       spent_by(ledger, names_b), share_b)
        done["primary_arm_b"] = primary_b
    ledger.append(dict(done, arms={arm: [r["key"] for r in rows] for arm, rows in results.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
