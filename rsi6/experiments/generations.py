"""The rounds of self-modification, for three lineages.

    python -m rsi6.experiments.generations --rounds 2 [--ledger PATH] [--dev]

Lineages. ``self``: every round is performed by the lineage's newest version of the learner
(the recursive arm). ``fixed``: every round is performed by the learner at generation 0.
``random``: every round is performed by random single-field changes. From round 2 on, the
generation-0 learner and the random proposer are also started from the ``self`` lineage's
current version (``fixed@self``, ``random@self``): the comparison in which only the improver
differs.

A round: each improver searches the source pool within the registered CPU; the round's adoption
set is unlocked; every nominee is put through the gate against the version it started from and
measured again on the confirmation half; lineages adopt what passed; the adoption set joins the
source pool.

``--dev`` runs the same code on a development ledger with the source categories standing in for
the adoption set. Nothing it writes is evidence.
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
from rsi6.learner import version as versions
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration.json")
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")
DEV_LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "dev.jsonl")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, required=True)
    parser.add_argument("--ledger", default=None)
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--cpu", type=float, default=None, help="search CPU-seconds (development only)")
    args = parser.parse_args()
    reg = json.load(open(REGISTRATION))
    ledger = ledgers.Ledger(args.ledger or (DEV_LEDGER if args.dev else LEDGER))
    cache = Cache(ledger)
    if not args.dev and find(ledger, type="registration") is None:
        ledger.append({"type": "registration", "digest": ledgers.digest(reg), "registration": reg})
    if not args.dev and find(ledger, type="registration")["digest"] != ledgers.digest(reg):
        raise SystemExit("the registration file differs from the one recorded in the ledger")
    rounds.RULES.update(reg["rules"])
    cpu_limit = args.cpu if (args.dev and args.cpu) else reg["search_cpu_limit"]
    v0 = versions.default()
    lineage = {"self": v0, "fixed": v0, "random": v0}
    for record in ledger.select(type="adopt"):
        lineage[record["lineage"]] = record["version"]
    for g in range(1, args.rounds + 1):
        if find(ledger, type="round_done", round=g):
            continue
        source = rounds.pool(ledger)
        if args.dev:
            adoption = source
        else:
            adoption = sorted(n for n in environments.REGISTRY if roles.role_of(environments.load(n).category) == f"adoption:{g}")
            if len(adoption) < 2:
                raise SystemExit(f"round {g}: fewer than two adapters for its adoption set")
        say(f"round {g}: source pool {source}; adoption set {adoption}")
        plan = [("self", "learner", lineage["self"], lineage["self"]), ("fixed", "learner", v0, lineage["fixed"]),
                ("random", "random", None, lineage["random"])]
        if g >= 2:
            plan += [("fixed@self", "learner", v0, lineage["self"]), ("random@self", "random", None, lineage["self"])]
        previous = find(ledger, type="search", tag=f"search:{g - 1}:self")
        found = {}
        for name, kind, improver, start in plan:
            tag = f"search:{g}:{name}"
            record = find(ledger, type="search", tag=tag)
            if record is None:
                stats = previous.get("edit_stats") if (name == "self" and previous) else None
                record = rounds.search(kind, improver, start, source, reg["seeds"]["search"], reg["budgets"]["search"],
                                       cpu_limit, cache, tag, seed=1000 * g + (1 if kind == "learner" else 2),
                                       edit_stats=stats)
                record = ledger.append(dict(record, round=g, name=name))
            found[name] = (record, start)
            say(f"  {tag}: evaluated {record['evaluated']}, improving {record['improving']}, best {record['best_cost']},",
                "nominee changes", sorted(record["nominee_changes"]) if record["nominee_changes"] else None)
        if not args.dev and find(ledger, type="unlock", role=f"adoption:{g}") is None:
            ledger.append({"type": "unlock", "role": f"adoption:{g}", "round": g})
        for name, (record, start) in found.items():
            nominee = record["nominee_version"]
            if nominee is None:
                ledger.append({"type": "no_nominee", "round": g, "name": name}) if find(ledger, type="no_nominee", round=g, name=name) is None else None
                continue
            tag = f"gate:{g}:{name}"
            decision = find(ledger, type="gate", tag=tag)
            if decision is None:
                decision = ledger.append(dict(rounds.gate(start, nominee, adoption, reg["seeds"]["gate"], reg["budgets"]["run"],
                                                          cache, tag, seed=g), round=g, name=name))
            say(f"  {tag}: adopted {decision['adopted']} | min-change {decision['mean_min']:+.4f} gain {decision['mean_gain_change']:+.4f}",
                f"acquired {decision['mean_acquired_change']:+.4f} lower bound {decision['gain_lower_bound']:+.4f} cpu x{decision['cpu_ratio']:.2f}")
            tag = f"confirm:{g}:{name}"
            if find(ledger, type="confirm", tag=tag) is None:
                check = ledger.append(dict(rounds.confirm(start, nominee, adoption, reg["seeds"]["confirm"],
                                                          reg["budgets"]["run"], cache, tag), round=g, name=name))
                say(f"  {tag}: gain {check['mean_gain_change']:+.4f} acquired {check['mean_acquired_change']:+.4f}")
            if name in lineage and decision["adopted"] and find(ledger, type="adopt", round=g, lineage=name) is None:
                ledger.append({"type": "adopt", "round": g, "lineage": name, "version": nominee,
                               "digest": versions.digest(nominee), "changes": versions.differences(start, nominee)})
                lineage[name] = nominee
        if not args.dev:
            ledger.append({"type": "release", "role": f"adoption:{g}", "round": g})
        ledger.append({"type": "round_done", "round": g, "lineages": {k: versions.digest(v) for k, v in lineage.items()}})
    if not args.dev and find(ledger, type="round_done", round=reg["rounds_planned"]) and find(ledger, type="freeze") is None:
        # every lineage is fixed from here on; the target categories may be built and unlocked only after this
        ledger.append({"type": "freeze", "lineages": lineage, "digests": {k: versions.digest(v) for k, v in lineage.items()},
                       "rounds": reg["rounds_planned"]})
    say("lineages:", {k: versions.digest(v)[:12] for k, v in lineage.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
