"""The end of process c (amendment 3): its freeze record and its external gate.

    python -m rsi6.experiments.external [--ledger PATH]

Process c adopts versions provisionally: the categories it sets aside in one generation are
searched on in others, and every generation tests several nominees. What it found is therefore
tested once more here, on two categories that no process has used and no learner has met: the
reserves ``tour`` and ``colouring`` (registration_c.json, ``decision``). Their adapters were
built and audited by independent agents (``audit/adapters_targets``).

The driver refuses to start before every planned generation of process c is recorded. It then

1. writes the record that freezes process c (its final version; nothing of the process can
   change afterwards, and only after this record may the target test run);
2. gives the two reserves the role ``adoption:4`` (a ``reassign`` record, as amendment 2 wrote
   for this role) and unlocks that role;
3. puts the final version through the registered gate against generation 0 on the deciding
   half of their fresh instances (seeds 4001 to 4006), and through the confirmation on the
   other half (seeds 5001 to 5006);
4. records the outcome and releases the role.

The external gate counts as passed if the gate's three conditions hold and the confirmation is
above zero: the rule by which process c adopted, applied once. If process c adopted nothing its
final version is generation 0 and there is nothing to test; that is recorded as such.
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
from rsi6.kernel import roles
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration_c.json")
LIVE = os.path.join(os.path.dirname(HERE), "ledger", "live.jsonl")
MAIN = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")
ENVIRONMENTS = ("colouring", "tour")
ROLE = "adoption:4"
GATE_SEEDS = [4001, 4002, 4003, 4004, 4005, 4006]
CONFIRM_SEEDS = [5001, 5002, 5003, 5004, 5005, 5006]


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LIVE)
    parser.add_argument("--registration", default=REGISTRATION)
    parser.add_argument("--dev", action="store_true", help="development only: a scratch ledger, the generations recorded so far "
                        "taken as the whole process, and two source categories in the place of the reserves")
    args = parser.parse_args()
    if args.dev and os.path.abspath(args.ledger) in (os.path.abspath(LIVE), os.path.abspath(MAIN)):
        raise SystemExit("--dev needs a scratch ledger")
    names, role = (("binpacking", "jobshop"), "source") if args.dev else (ENVIRONMENTS, ROLE)
    reg = json.load(open(args.registration))
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    recorded = find(ledger, type="registration_c")
    if recorded is None or recorded["digest"] != ledgers.digest(reg):
        raise SystemExit("process c is not registered in this ledger, or its registration file differs from the recorded one")
    missing = [g for g in range(1, reg["generations_planned"] + 1) if find(ledger, type="c_generation_done", generation=g) is None]
    if missing and not args.dev:
        raise SystemExit(f"process c has not finished: generations {missing} are not recorded")
    rounds.RULES.update(reg["rules"])
    v0 = designs.default(reg["design"])
    adoptions = ledger.select(type="adopt", process="c")
    final = adoptions[-1]["version"] if adoptions else v0
    if find(ledger, type="freeze", process="c") is None:
        ledger.append({"type": "freeze", "process": "c", "version": final, "digest": designs.digest(final),
                       "adoptions": [{"generation": a["round"], "technique": a["technique"], "digest": a["digest"]} for a in adoptions],
                       "changes_from_generation_0": designs.differences(v0, final)})
    say("process c is frozen at", designs.digest(final)[:12], "after", len(adoptions), "adoptions")
    if find(ledger, type="external_gate", process="c") is not None:
        say("the external gate is already recorded")
        return 0
    if not adoptions:
        ledger.append({"type": "external_gate", "process": "c", "passed": False, "run": False,
                       "why": "process c adopted no version: its final version is generation 0 and there is nothing to test"})
        say("no version was adopted: the external gate has nothing to test")
        return 0
    absent = [n for n in names if n not in environments.REGISTRY]
    if absent:
        raise SystemExit(f"no admitted adapter for {absent}")
    for n in names:
        if roles.effective_role(environments.load(n).category, ledger) == "reserve":
            ledger.append({"type": "reassign", "category": n, "role": role, "round": "c:external", "amendment": 3})
    if any(roles.effective_role(environments.load(n).category, ledger) != role for n in names):
        raise SystemExit(f"the environments of the external gate do not all have the role {role}")
    if not args.dev and find(ledger, type="unlock", role=role) is None:
        ledger.append({"type": "unlock", "role": role, "round": "c:external"})
    cache = Cache(ledger)
    envs = sorted(names)
    decision = find(ledger, type="gate", tag="gate:c:external")
    if decision is None:
        decision = ledger.append(dict(rounds.gate(v0, final, envs, GATE_SEEDS, reg["budgets"]["run"], cache, "gate:c:external", seed=300),
                                      round="c:external", name="external", process="c"))
    say(f"external gate: passes {decision['adopted']} | min-change {decision['mean_min']:+.4f} gain {decision['mean_gain_change']:+.4f}",
        f"acquired {decision['mean_acquired_change']:+.4f} lower bound {decision['gain_lower_bound']:+.4f} cpu x{decision['cpu_ratio']:.2f}")
    check = find(ledger, type="confirm", tag="confirm:c:external")
    if check is None:
        check = ledger.append(dict(rounds.confirm(v0, final, envs, CONFIRM_SEEDS, reg["budgets"]["run"], cache, "confirm:c:external"),
                                   round="c:external", name="external", process="c"))
    say(f"confirmation: min-change {check['mean_min']:+.4f} gain {check['mean_gain_change']:+.4f} acquired {check['mean_acquired_change']:+.4f}")
    passed = bool(decision["adopted"] and check["mean_min"] > 0.0)
    ledger.append({"type": "external_gate", "process": "c", "passed": passed, "run": True, "gate_passed": bool(decision["adopted"]),
                   "gate_min_change": decision["mean_min"], "gate_lower_bound": decision["gain_lower_bound"],
                   "confirmation_min_change": check["mean_min"], "envs": envs, "final": designs.digest(final),
                   "rule": "the gate's three conditions and a confirmation above zero"})
    if not args.dev:
        ledger.append({"type": "release", "role": role, "round": "c:external"})
    say("external gate passed:", passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
