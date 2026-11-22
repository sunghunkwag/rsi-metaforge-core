"""Process d, generation 1 (amendment 6): one modification, found in development, put once through
the registered gate on four categories no learner has run on.

    python -m rsi6.experiments.gate_d --prepare          # the records that open the categories, nothing else
    python -m rsi6.experiments.gate_d [--copy-to DIR]    # the gate, the confirmation, the outcome

The nominee is generation 0 of the first design with ``model.batch`` 2. No registered search
produced it: a development scan of every single-field change of generation 0 on the nine
categories of the pool, and two measurements on new seeds, the second with the choice fixed
beforehand (``rsi6/results/dev_landscape_20261122/``). What is registered is this gate only.

The categories are the four with the role ``fresh`` (weighted tardiness, quadratic 0-1, project
scheduling, maximum clique): adapters built and audited by independent agents
(``audit/adapters_fresh_20261116``), installed by ``environments/fresh.py``, locked until now.
The driver

1. writes the record of amendment 6;
2. gives the four categories the role ``adoption:5`` (``reassign`` records) and unlocks that
   role. ``--prepare`` stops here, so that the opening of the categories can be committed
   before anything is measured on them;
3. measures generation 0 and the nominee on the deciding half of the fresh instances with the
   gate's seeds, and on the other half with the confirmation's seeds, in alternating blocks of
   four seeds (both versions of a block in one call of the kernel, on one machine);
4. applies the registered gate (``rsi6.meta.rounds.gate``, the rules of registration c
   unchanged) and the confirmation (``rounds.confirm``) to those runs;
5. releases the role (the categories join the pool) and records the outcome: passed if the
   gate's three conditions hold and the confirmation is above zero (amendment 4, reading a).
   If passed, the nominee is adopted as generation 1 of process d.

One nominee, one gate. If it does not pass, nothing is adopted and the change is not put
through another gate. A pass shows one independently validated modification of the acquisition
mechanism. It does not show recursion: the learner as improver (``rounds.search``) works with
the fields ``edit.*`` only, which this nominee does not change.

A driver that is started again repeats nothing: every record is looked up before it is written
and every run is served from the ledger. ``--copy-to DIR`` copies the working ledger there after
every block (a job on a hosted runner uploads that directory whatever happens to it).
``--dev`` rehearses the whole driver on a scratch ledger with two categories of the pool in the
place of the four, four seeds each, and writes no amendment record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from rsi6 import environments
from rsi6.environments import fresh
from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(os.path.dirname(HERE), "registry")
REGISTRATION = os.path.join(REGISTRY, "registration_c.json")
AMENDMENT = os.path.join(REGISTRY, "amendment_6.json")
ENVIRONMENTS = ("clique", "projects", "quadratic", "tardiness")
ROLE = "adoption:5"
ROUND = "d:1"
NOMINEE = {"model.batch": 2}
GATE_SEEDS = list(range(8101, 8133))
CONFIRM_SEEDS = list(range(9101, 9133))
BOOTSTRAP_SEED = 600
BLOCK = 4
WHAT = ("after the development scan of generation 0 (results/dev_landscape_20261122) and the Owner's instruction 18: process d, "
        "generation 1. One nominee from development (generation 0 with model.batch 2) is put once through the registered gate, "
        "rules unchanged, against generation 0 on the four categories with the role fresh, which get the role adoption:5; 32 "
        "seeds at the gate, 32 at the confirmation; passed if the gate's three conditions hold and the confirmation is above zero")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def _sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=guard.LIVE)
    parser.add_argument("--prepare", action="store_true", help="write the amendment, reassign and unlock records and stop")
    parser.add_argument("--copy-to", default=None, help="copy the working ledger into this directory after every block")
    parser.add_argument("--dev", action="store_true", help="development only: a scratch ledger, two pool categories, four seeds")
    args = parser.parse_args()
    if args.dev and guard.is_registered(args.ledger):
        raise SystemExit("--dev needs a scratch ledger")
    if not args.dev and not guard.is_registered(args.ledger):
        raise SystemExit("outside the development mode the ledger is ledger/live.jsonl or ledger/main.jsonl")
    if not os.path.exists(args.ledger):
        shutil.copy(guard.MAIN, args.ledger)
    guard.same_history(args.ledger)
    guard.single_writer(args.ledger)
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()

    def keep() -> None:
        if args.copy_to:
            os.makedirs(args.copy_to, exist_ok=True)
            shutil.copy(args.ledger, os.path.join(args.copy_to, "live.jsonl"))

    reg = json.load(open(REGISTRATION))
    recorded = find(ledger, type="registration_c")
    if recorded is None or recorded["digest"] != ledgers.digest(reg):
        raise SystemExit("process c is not registered in this ledger, or its registration file differs from the recorded one")
    rounds.RULES.update(reg["rules"])
    budget = reg["budgets"]["run"]
    amendment = json.load(open(AMENDMENT))
    v0 = designs.default(reg["design"])
    nominee = designs.validate(dict(v0, **NOMINEE))
    stated = amendment["registered"]
    mine = {"nominee": designs.digest(nominee), "incumbent": designs.digest(v0), "changes": NOMINEE, "categories": sorted(ENVIRONMENTS),
            "role": ROLE, "gate_seeds": [GATE_SEEDS[0], GATE_SEEDS[-1]], "confirm_seeds": [CONFIRM_SEEDS[0], CONFIRM_SEEDS[-1]],
            "budget": budget, "rules": {k: reg["rules"][k] for k in ("margin", "cpu_ratio", "bootstrap", "level")},
            "bootstrap_seed": BOOTSTRAP_SEED, "block": BLOCK}
    if stated != mine:
        raise SystemExit("amendment_6.json and this driver do not state the same test")

    if args.dev:
        names, role, gate_seeds, confirm_seeds = ("pmedian", "quadassign"), "source", [9738101 + k for k in range(4)], [9739101 + k for k in range(4)]
    else:
        names, role, gate_seeds, confirm_seeds = ENVIRONMENTS, ROLE, GATE_SEEDS, CONFIRM_SEEDS
        installed = fresh.install()
        table = fresh.table()["categories"]
        for n in names:
            if n not in installed or n not in environments.REGISTRY:
                raise SystemExit(f"no admitted adapter for {n}")
            path = os.path.join(os.path.dirname(HERE), "environments", n + ".py")
            if _sha(path) != table[n]["sha256"]:
                raise SystemExit(f"the adapter of {n} is not the audited file")
        guard.amendment(ledger, 6, WHAT)
    outcome = find(ledger, type="gate_d", generation=1)
    if outcome is not None:
        say("the outcome is already recorded: passed", outcome["passed"])
        keep()
        return 0
    if not args.dev and find(ledger, type="release", role=role) is None:
        for n in names:
            if roles.effective_role(environments.load(n).category, ledger) == "fresh":
                ledger.append({"type": "reassign", "category": n, "role": role, "round": ROUND, "amendment": 6})
        if any(roles.effective_role(environments.load(n).category, ledger) != role for n in names):
            raise SystemExit(f"the categories of the gate do not all have the role {role}")
        if find(ledger, type="unlock", role=role) is None:
            ledger.append({"type": "unlock", "role": role, "round": ROUND})
            say("the four categories are open: role", role, "unlocked")
    keep()
    if args.prepare:
        say("prepared: the amendment, reassign and unlock records are written; nothing was measured")
        return 0

    cache = Cache(ledger)
    envs = sorted(names)
    plan = (("gate", gate_seeds, dict(budget, part="A"), "gate:d:1"), ("confirm", confirm_seeds, dict(budget, part="B"), "confirm:d:1"))
    for label, seeds, part, tag in plan:
        for k in range(0, len(seeds), BLOCK):
            block = seeds[k:k + BLOCK]
            # the two versions of a block in one call: measured side by side on this machine. The purposes are
            # the ones rounds.gate and rounds.confirm give, and the keys do not depend on them.
            jobs = (rounds.jobs_for(v0, envs, block, part, tag + ":incumbent") + rounds.jobs_for(nominee, envs, block, part, tag + ":nominee"))
            cache.get(jobs)
            keep()
            say(f"{label}: seeds {block[0]} to {block[-1]} measured ({min(k + BLOCK, len(seeds))} of {len(seeds)})")
    decision = find(ledger, type="gate", tag="gate:d:1")
    if decision is None:
        decision = ledger.append(dict(rounds.gate(v0, nominee, envs, gate_seeds, budget, cache, "gate:d:1", seed=BOOTSTRAP_SEED),
                                      round=ROUND, name="scan", process="d"))
    say(f"gate: passes {decision['adopted']} | min-change {decision['mean_min']:+.4f} gain {decision['mean_gain_change']:+.4f}",
        f"acquired {decision['mean_acquired_change']:+.4f} lower bound {decision['gain_lower_bound']:+.4f} cpu x{decision['cpu_ratio']:.2f}")
    for e, row in decision["per_env"].items():
        say(f"   {e:12s} acquired {row['acquired_change']:+.4f} gain {row['gain_change']:+.4f}")
    check = find(ledger, type="confirm", tag="confirm:d:1")
    if check is None:
        check = ledger.append(dict(rounds.confirm(v0, nominee, envs, confirm_seeds, budget, cache, "confirm:d:1"),
                                   round=ROUND, name="scan", process="d"))
    say(f"confirmation: min-change {check['mean_min']:+.4f} gain {check['mean_gain_change']:+.4f} acquired {check['mean_acquired_change']:+.4f}")
    for record in (decision, check):
        if record["incumbent"] != designs.digest(v0) or record["nominee"] != designs.digest(nominee):
            raise SystemExit("a recorded measurement of this gate compares other versions than generation 0 and the nominee")
    # the role is released before the outcome is recorded, so that a driver stopped in between leaves nothing undone
    if not args.dev and find(ledger, type="release", role=role) is None:
        ledger.append({"type": "release", "role": role, "round": ROUND})
    passed = bool(decision["adopted"] and check["mean_min"] > 0.0)
    ledger.append({"type": "gate_d", "process": "d", "generation": 1, "passed": passed, "gate_passed": bool(decision["adopted"]),
                   "conditions": decision["conditions"], "gate_min_change": decision["mean_min"],
                   "gate_lower_bound": decision["gain_lower_bound"], "gate_cpu_ratio": decision["cpu_ratio"],
                   "confirmation_min_change": check["mean_min"], "envs": envs, "incumbent": designs.digest(v0),
                   "nominee": designs.digest(nominee), "changes": NOMINEE, "dev": bool(args.dev),
                   "rule": "the gate's three conditions and a confirmation above zero"})
    if passed and not args.dev and find(ledger, type="adopt", process="d") is None:
        ledger.append({"type": "adopt", "process": "d", "round": ROUND, "lineage": "d", "technique": "scan", "version": nominee,
                       "digest": designs.digest(nominee), "changes": designs.differences(v0, nominee), "provisional": False})
    keep()
    say("passed:", passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
