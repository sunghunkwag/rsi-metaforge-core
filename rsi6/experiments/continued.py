"""The continued process (amendment 2): rounds of self-modification of the second design.

    python -m rsi6.experiments.continued [--dev] [--cpu N]

The same procedure as the two registered rounds (``generations.py``), on the same ledger, with
what amendment 2 registers: generation 0 is the default version of the second design; the
searches count improvement by ``rounds.breadth``; round 1 is gated on the third adoption set
of the draw. The gate, the confirmation and the adoption rule are unchanged. A second round is
run only if the self lineage adopted a version in the first: from an unchanged version it
would repeat the first.

Its records carry ``"round": "b1"``, ``"b2"`` and tags ``search:b1:self`` and so on, so that
nothing here can be mistaken for a record of the two registered rounds.

``--dev`` runs the same code on the development ledger with the source pool standing in for
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
from rsi6.learner import designs
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration_b.json")
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")
DEV_LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "dev_b.jsonl")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--cpu", type=float, default=None, help="search CPU-seconds (development only)")
    parser.add_argument("--registration", default=REGISTRATION)
    args = parser.parse_args()
    reg = json.load(open(args.registration))
    ledger = ledgers.Ledger(DEV_LEDGER if args.dev else LEDGER)
    cache = Cache(ledger)
    if not args.dev:
        if find(ledger, type="freeze") is None:
            raise SystemExit("the two registered rounds are not finished")
        if find(ledger, type="registration_b") is None:
            ledger.append({"type": "registration_b", "digest": ledgers.digest(reg), "registration": reg})
        if find(ledger, type="registration_b")["digest"] != ledgers.digest(reg):
            raise SystemExit("the registration file of the continued process differs from the one recorded in the ledger")
    rounds.RULES.update(reg["rules"])
    cpu_limit = args.cpu if (args.dev and args.cpu) else reg["search_cpu_limit"]
    v0 = designs.default("b")
    if designs.digest(v0) != reg["generation_0"]["version_digest"]:
        raise SystemExit("the default version of the second design is not the registered generation 0")
    lineage = {"self": v0, "fixed": v0, "random": v0}
    for record in ledger.select(type="adopt", process="b"):
        lineage[record["lineage"]] = record["version"]
    for g in range(1, reg["rounds_planned"] + 1):
        label = f"b{g}"
        if find(ledger, type="round_done", round=label):
            continue
        if g > 1 and find(ledger, type="adopt", process="b", round=g - 1, lineage="self") is None:
            if find(ledger, type="round_skipped", round=label) is None:
                ledger.append({"type": "round_skipped", "round": label,
                               "why": "the self lineage adopted no version in the round before; the registered rule is to stop"})
            say(f"round {label}: not run (no adoption in the round before)")
            break
        source = rounds.pool(ledger)
        if args.dev:
            adoption = source
        else:
            adoption = sorted(reg["gates"][str(g)]["environments"])
            role = reg["gates"][str(g)]["role"]
        say(f"round {label}: source pool {source}; adoption set {adoption}")
        plan = [("self", "learner", lineage["self"], lineage["self"]), ("fixed", "learner", v0, lineage["fixed"]),
                ("random", "random", None, lineage["random"])]
        if g >= 2:
            plan += [("fixed@self", "learner", v0, lineage["self"]), ("random@self", "random", None, lineage["self"])]
        previous = find(ledger, type="search", tag=f"search:b{g - 1}:self")
        found = {}
        for name, kind, improver, start in plan:
            tag = f"search:{label}:{name}"
            record = find(ledger, type="search", tag=tag)
            if record is None:
                stats = previous.get("edit_stats") if (name == "self" and previous) else None
                record = rounds.search(kind, improver, start, source, reg["seeds"]["search"], reg["budgets"]["search"],
                                       cpu_limit, cache, tag, seed=2000 * g + (1 if kind == "learner" else 2),
                                       edit_stats=stats, objective=rounds.breadth)
                record = ledger.append(dict(record, round=label, name=name, process="b", objective="breadth"))
            found[name] = (record, start)
            say(f"  {tag}: evaluated {record['evaluated']}, improving {record['improving']}, best {record['best_cost']},",
                "nominee changes", sorted(record["nominee_changes"]) if record["nominee_changes"] else None)
        if not args.dev:
            # the searches need the source pool only; the adapters of the gate are required from here on
            missing = [n for n in adoption if n not in environments.REGISTRY]
            if missing:
                raise SystemExit(f"round {label}: the searches are recorded; no adapter yet for {missing}; start again when it is admitted")
            for n in adoption:                       # reserves that amendment 2 turns into this round's gate
                if reg["gates"][str(g)].get("from") == "reserve" and roles.effective_role(n, ledger) == "reserve":
                    ledger.append({"type": "reassign", "category": n, "role": role, "round": label, "amendment": 2})
            if find(ledger, type="release", role=role) is None and any(
                    roles.effective_role(environments.load(n).category, ledger) != role for n in adoption):
                raise SystemExit(f"round {label}: its gate environments do not all have the role {role}")
        if not args.dev and find(ledger, type="unlock", role=role) is None:
            ledger.append({"type": "unlock", "role": role, "round": label})
        for name, (record, start) in found.items():
            nominee = record["nominee_version"]
            if nominee is None:
                if find(ledger, type="no_nominee", round=label, name=name) is None:
                    ledger.append({"type": "no_nominee", "round": label, "name": name})
                continue
            tag = f"gate:{label}:{name}"
            decision = find(ledger, type="gate", tag=tag)
            if decision is None:
                decision = ledger.append(dict(rounds.gate(start, nominee, adoption, reg["seeds"]["gate"], reg["budgets"]["run"],
                                                          cache, tag, seed=100 + g), round=label, name=name, process="b"))
            say(f"  {tag}: adopted {decision['adopted']} | min-change {decision['mean_min']:+.4f} gain {decision['mean_gain_change']:+.4f}",
                f"acquired {decision['mean_acquired_change']:+.4f} lower bound {decision['gain_lower_bound']:+.4f} cpu x{decision['cpu_ratio']:.2f}")
            tag = f"confirm:{label}:{name}"
            if find(ledger, type="confirm", tag=tag) is None:
                check = ledger.append(dict(rounds.confirm(start, nominee, adoption, reg["seeds"]["confirm"],
                                                          reg["budgets"]["run"], cache, tag), round=label, name=name, process="b"))
                say(f"  {tag}: gain {check['mean_gain_change']:+.4f} acquired {check['mean_acquired_change']:+.4f}")
            if name in lineage and decision["adopted"] and find(ledger, type="adopt", process="b", round=g, lineage=name) is None:
                ledger.append({"type": "adopt", "process": "b", "round": g, "lineage": name, "version": nominee,
                               "digest": designs.digest(nominee), "changes": designs.differences(start, nominee)})
                lineage[name] = nominee
        if not args.dev:
            ledger.append({"type": "release", "role": role, "round": label})
        ledger.append({"type": "round_done", "round": label, "process": "b",
                       "lineages": {k: designs.digest(v) for k, v in lineage.items()}})
    if not args.dev and find(ledger, type="freeze", process="b") is None:
        # every lineage of the continued process is fixed from here on; only now may the targets be built
        ledger.append({"type": "freeze", "process": "b", "lineages": lineage,
                       "digests": {k: designs.digest(v) for k, v in lineage.items()}})
    say("lineages:", {k: designs.digest(v)[:12] for k, v in lineage.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
