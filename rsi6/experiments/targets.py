"""The test on the sealed target categories. Run once, after every improvement process is frozen.

    python -m rsi6.experiments.targets [--ledger PATH]

It refuses to start unless the ledger holds the record that freezes the lineages of the two
registered rounds; if the continued process of amendment 2 was registered, the record that
freezes its lineages too; if process c of amendment 3 was registered, its freeze record and
the record of its external gate; and unless ``registry/targets.json`` lists the target adapters
that passed their audit. It then unlocks the target role and measures, on every target
environment and every registered seed, the arms of every process.

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

Arms of process c (first design; amendment 3), named with the prefix ``c:``: ``c:frozen`` and
``c:skills`` are the arms ``frozen`` and ``skills`` above (the same version, the same runs);
``c:self`` is the final version of process c with empty memory, ``c:memory`` the same with the
memory of its own acquisitions; ``c:compute`` and ``c:search`` are generation 0 with its
training budget, or its test-time budget and no training, raised until its measured CPU-seconds
reach those of ``c:self`` plus an equal share of everything process c ran in its generations
(every search, gate and confirmation of every technique).

A budget is raised level by level: doubled at first, then by the factor that the measured
CPU-seconds of the last two levels say is needed (at least 2, at most 64 per level; at most
twelve levels). Runs are recorded in small batches so that a driver that is started again
repeats little.

Statistics are computed by ``report.py`` from the ledger.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


def in_batches(cache, jobs, size: int = 4) -> list:
    """The records of the jobs, run and written to the ledger a few at a time."""
    out = []
    for k in range(0, len(jobs), size):
        out += cache.get(jobs[k:k + size])
    return out


def matched(arm, version, field, want, targets, seeds, budget, cache, ledger, spent, share) -> list:
    """Generation 0 with one budget raised, pair by pair, until its measured CPU reaches ``want``."""
    value, last, seen = {pair: budget[field] for pair in want}, {}, {pair: [] for pair in want}
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
        for pair, record in zip(pending, in_batches(cache, jobs)):
            last[pair] = record
            seen[pair].append((value[pair], cpu(record)))
            factor = 2.0
            if len(seen[pair]) >= 2:                         # what the last two levels say is needed, with a tenth to spare
                (v1, c1), (v2, c2) = seen[pair][-2:]
                slope = (c2 - c1) / (v2 - v1)
                factor = 8.0 if slope <= 0 else min(64.0, max(2.0, (v2 + (1.1 * want[pair] - c2) / slope) / v2))
            value[pair] *= factor
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


def spent_by_process_c(ledger) -> float:
    """Measured CPU of every run of the generations of process c: the searches of all its
    techniques, its gates and its confirmations. The external gate is a test of the outcome and
    is not counted."""
    mine = re.compile(r"^(search|gate|confirm):c\d+:")
    return float(sum(cpu(r) for r in ledger.records if r.get("type") == "run" and mine.match(r.get("purpose", ""))))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--targets", default=os.path.join(REGISTRY, "targets.json"),
                        help="the list of admitted target adapters (another file only for a development run)")
    args = parser.parse_args()
    reg = json.load(open(os.path.join(REGISTRY, "registration.json")))
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    frozen_a = [r for r in ledger.select(type="freeze") if not r.get("process")]
    frozen_b = ledger.select(type="freeze", process="b")
    frozen_c = ledger.select(type="freeze", process="c")
    if not frozen_a:
        raise SystemExit("the lineages are not frozen: no target run before that")
    if ledger.select(type="registration_b") and not frozen_b:
        raise SystemExit("the continued process is registered and not frozen: no target run before that")
    if ledger.select(type="registration_c") and not (frozen_c and ledger.select(type="external_gate", process="c")):
        raise SystemExit("process c is registered and not finished (freeze record and external gate): no target run before that")
    listed = json.load(open(args.targets))
    targets = sorted(listed["admitted"])
    for change in listed.get("replacements", []):      # a reserve takes the role of a target that could not be built
        if not ledger.select(type="replace", replaced=change["replaced"]):
            ledger.append({"type": "replace", "replaced": change["replaced"], "reserve": change["reserve"], "role": "target",
                           "why": change["why"]})
    wrong = [n for n in targets if roles.effective_role(environments.load(n).category, ledger) != "target"]
    if wrong or len(targets) != roles.N_TARGET:
        raise SystemExit(f"the admitted list must be the {roles.N_TARGET} categories with the role target; not so: {wrong or targets}")
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
    # ---- process c
    if frozen_c:
        v0, final = designs.default("a"), frozen_c[-1]["version"]
        adopted_c = bool(frozen_c[-1]["adoptions"])
        results["c:frozen"], results["c:skills"] = results["frozen"], results["skills"]
        results["c:self"] = cache.get(rounds.jobs_for(final, targets, seeds, budget, "target:c:self"))
        say("c:self", designs.digest(final)[:12], "acquired %.4f gain %+.4f" % (mean(results["c:self"], "acquired"), mean(results["c:self"], "gain")))
        memory = memory_of(final, earlier, budget, cache, "memory:c:memory")
        results["c:memory"] = cache.get([dict(job, memory=memory) for job in rounds.jobs_for(final, targets, seeds, budget, "target:c:memory")])
        say("c:memory", "entries in memory", len(memory["entries"]),
            "acquired %.4f gain %+.4f" % (mean(results["c:memory"], "acquired"), mean(results["c:memory"], "gain")))
        spent_c = spent_by_process_c(ledger)
        share_c = spent_c / (len(targets) * len(seeds))
        want_c = {(r["env"], r["seed"]): cpu(r) + share_c for r in results["c:self"]}
        for arm, field in (("c:compute", "train"), ("c:search", "test_e")):
            results[arm] = matched(arm, v0, field, want_c, targets, seeds, budget, cache, ledger, spent_c, share_c)
        done["primary_arm_c"] = "c:self" if adopted_c else "c:frozen"
    ledger.append(dict(done, arms={arm: [r["key"] for r in rows] for arm, rows in results.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
