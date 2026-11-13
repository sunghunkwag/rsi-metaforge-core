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

A budget is raised level by level (amendment 4, reading d): doubled at first, then by the
factor that the measured CPU-seconds of the last two levels say is needed, at least 2 and at
most 64 per level, at most twelve levels. As implemented: the first of the twelve levels is the
registered budget itself; the factor aims a tenth above the matched CPU, so that noise of the
measurement does not cost another level; where the last two levels show no rise of CPU the
factor is the largest allowed. A pair that is still below its matched CPU after the last level
is recorded as not reached, and the report voids every comparison against that arm.

The list of targets (``registry/targets.json``): ``admitted``, the categories whose adapters
passed their audit; ``replacements``, reserves that take the role of a target that could not be
built (``replaced``, ``reserve``, ``why``); ``missing``, targets left without an adapter when no
reserve remains (``category``, ``why``). The list is checked against the roles in the ledger
before anything is written: it must be exactly the categories that have the role of a target
once the replacements are applied, less the missing ones. The test is run once: the list is
recorded with the unlock, a later start must present the same list, and after the closing
record nothing is measured again. Runs are recorded in small batches so that a driver that is
stopped and started again repeats little.

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
from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles, run
from rsi6.learner import designs
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(os.path.dirname(HERE), "registry")


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
                factor = 64.0 if slope <= 0 else min(64.0, max(2.0, (v2 + (1.1 * want[pair] - c2) / slope) / v2))
            value[pair] *= factor
        pending = [pair for pair in pending if cpu(last[pair]) < want[pair]]
        say(arm, "level done;", len(pending), "pairs below the matched CPU")
    rows = [dict(last[pair], matched_cpu=want[pair], reached=cpu(last[pair]) >= want[pair]) for pair in want]
    keys = [r["key"] for r in rows]
    if not [r for r in ledger.select(type="matched", arm=arm) if r["keys"] == keys]:      # once, also when the driver is started again
        ledger.append({"type": "matched", "arm": arm, "field": field, "share_per_run": share, "spent": spent, "keys": keys,
                       "pairs": [[name, seed] for name, seed in want], "matched_cpu": [want[pair] for pair in want],
                       "cpu": [cpu(last[pair]) for pair in want], "levels": [len(seen[pair]) for pair in want],
                       "budget": [seen[pair][-1][0] for pair in want], "reached": [bool(r["reached"]) for r in rows]})
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
    starts = {tag + ":start" for tag in names["search"]}        # the runs that measured the version a search started from
    total += sum(cpu(r) for r in ledger.records if r.get("type") == "run" and r.get("purpose") in starts)
    for kind in ("gate", "confirm"):
        total += sum(r["cpu"]["incumbent"] + r["cpu"]["nominee"] for r in ledger.select(type=kind, name="self") if r["tag"] in names[kind])
    return float(total)


def spent_by_process_c(ledger) -> float:
    """Measured CPU of every run of the generations of process c: the searches of all its
    techniques, its gates and its confirmations. The external gate is a test of the outcome and
    is not counted."""
    mine = re.compile(r"^(search|gate|confirm):c\d+:")
    return float(sum(cpu(r) for r in ledger.records if r.get("type") == "run" and mine.match(r.get("purpose", ""))))


def check_list(listed: dict, ledger) -> list:
    """Check the list of targets against the roles in the ledger, writing nothing. Returns the
    replacements that are not in the ledger yet. Stops the driver if the list is not exactly
    the categories with the role of a target once the replacements are applied, less the
    categories the list states as missing."""
    admitted, problems = list(listed["admitted"]), []
    if not admitted or len(set(admitted)) != len(admitted):
        problems.append("the admitted list is empty or names a category twice")
    expected = {c for c in roles.CANDIDATES if roles.effective_role(c, ledger) == "target"}
    pending = []
    for change in listed.get("replacements", []):
        old, new = change["replaced"], change["reserve"]
        recorded = ledger.select(type="replace", replaced=old)
        if recorded:
            if recorded[-1]["reserve"] != new or recorded[-1]["role"] != "target":
                problems.append(f"the ledger already replaces {old} by {recorded[-1]['reserve']}")
            continue
        if roles.role_of(old) != "target" or roles.effective_role(old, ledger) != "target":
            problems.append(f"{old} does not have the role of a target")
        if roles.role_of(new) != "reserve" or roles.effective_role(new, ledger) != "reserve":
            problems.append(f"{new} is not an unused reserve")
        if any(r.get("type") == "run" and r.get("category") == new for r in ledger.records):
            problems.append(f"the ledger holds a run on {new}")
        if not change.get("why"):
            problems.append(f"the replacement of {old} states no reason")
        expected = (expected - {old}) | {new}
        pending.append(change)
    for gone in listed.get("missing", []):
        # only a target that has no adapter can be missing: a target with an admitted adapter is never left out
        if gone["category"] not in expected or gone["category"] in admitted or gone["category"] in environments.REGISTRY \
                or not gone.get("why"):
            problems.append(f"{gone.get('category')} is stated as missing but is not a target without an adapter, or no reason is given")
        expected = expected - {gone["category"]}
    if set(admitted) != expected:
        problems.append(f"the admitted list {sorted(admitted)} is not the set of target categories {sorted(expected)}")
    if len(admitted) + len(listed.get("missing", [])) != roles.N_TARGET:
        problems.append(f"admitted and missing categories together are not the {roles.N_TARGET} drawn")
    problems += [f"no adapter is registered for {n}" for n in admitted if n not in environments.REGISTRY]
    if problems:
        raise SystemExit("the list of targets is refused, nothing was written: " + "; ".join(problems))
    return pending


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=guard.working())
    parser.add_argument("--targets", default=os.path.join(REGISTRY, "targets.json"),
                        help="the list of admitted target adapters (another file only for a development run)")
    parser.add_argument("--dev", type=int, default=None,
                        help="development only: this many seeds, on a scratch ledger, with a list of source categories as targets")
    args = parser.parse_args()
    dev = args.dev is not None
    if dev and (guard.is_registered(args.ledger) or args.dev < 1):
        raise SystemExit("--dev needs a scratch ledger and at least one seed")
    if not dev and not guard.is_registered(args.ledger):
        raise SystemExit("outside the development mode the ledger is ledger/live.jsonl or ledger/main.jsonl")
    guard.same_history(args.ledger)
    guard.single_writer(args.ledger)
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
    if ledger.select(type="recursion_search") and not ledger.select(type="recursion_done"):
        raise SystemExit("the recursion check has started and is not finished: no target run beside it")
    if ledger.select(type="target_done"):
        say("the target test is recorded: it is run once, nothing is measured again")
        return 0
    listed = json.load(open(args.targets))
    targets = sorted(listed["admitted"])
    if not dev:
        for number in (3, 4):                          # the amendments whose readings this driver applies
            if ledger.select(type="registration_c") and not ledger.select(type="amendment", amendment=number):
                raise SystemExit(f"amendment {number} is not recorded in this ledger")
        pending = check_list(listed, ledger)
        unlocked = ledger.select(type="unlock", role="target")
        if unlocked and (unlocked[-1]["targets"] != targets or pending):
            raise SystemExit(f"the target role was unlocked for {unlocked[-1]['targets']}: a later start must present the same list")
        for change in pending:                         # a reserve takes the role of a target that could not be built
            ledger.append({"type": "replace", "replaced": change["replaced"], "reserve": change["reserve"], "role": "target",
                           "why": change["why"]})
        if any(roles.effective_role(n, ledger) != "target" for n in targets):
            raise SystemExit("after the replacements the admitted categories do not all have the role of a target")
        if not unlocked:
            ledger.append({"type": "unlock", "role": "target", "targets": targets, "missing": listed.get("missing", [])})
    cache = run.Cache(ledger)
    seeds, budget = reg["seeds"]["target"][:args.dev], reg["budgets"]["run"]
    earlier = [n for n in rounds.pool(ledger) if n not in targets]
    part = 1.0                                         # the share of a process's spending that the matched arms receive
    if dev:                                            # development only: two environments in memory, a small share to match
        earlier, part = earlier[:2], 0.002
    # ---- the two registered rounds
    tags = lambda kind, label: {f"{kind}:{label}{g}:self" for g in range(1, 10)}
    names_a = {kind: tags(kind, "") for kind in ("search", "gate", "confirm")}
    adopted_a = [r for r in ledger.select(type="adopt", lineage="self") if r.get("process") != "b"]
    results, primary, _, _ = process_arms("", designs.default("a"), frozen_a[-1]["lineages"], adopted_a, part * spent_by(ledger, names_a),
                                          targets, seeds, budget, cache, ledger, earlier)
    done = {"type": "target_done", "primary_arm": primary, "targets": targets, "seeds": seeds, "memory_from": earlier}
    # ---- the continued process
    if frozen_b:
        names_b = {kind: tags(kind, "b") for kind in ("search", "gate", "confirm")}
        adopted_b = ledger.select(type="adopt", process="b", lineage="self")
        more, primary_b, want_b, share_b = process_arms("b:", designs.default("b"), frozen_b[-1]["lineages"], adopted_b,
                                                        part * spent_by(ledger, names_b), targets, seeds, budget, cache, ledger, earlier)
        results.update(more)
        results["compute@b"] = matched("compute@b", designs.default("a"), "train", want_b, targets, seeds, budget, cache, ledger,
                                       part * spent_by(ledger, names_b), share_b)
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
        spent_c = part * spent_by_process_c(ledger)
        share_c = spent_c / (len(targets) * len(seeds))
        want_c = {(r["env"], r["seed"]): cpu(r) + share_c for r in results["c:self"]}
        for arm, field in (("c:compute", "train"), ("c:search", "test_e")):
            results[arm] = matched(arm, v0, field, want_c, targets, seeds, budget, cache, ledger, spent_c, share_c)
        done["primary_arm_c"] = "c:self" if adopted_c else "c:frozen"
    ledger.append(dict(done, arms={arm: [r["key"] for r in rows] for arm, rows in results.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
