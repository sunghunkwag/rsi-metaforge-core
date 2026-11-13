"""The recursion check of process c (amendment 4). It adopts nothing and changes no lineage.

    python -m rsi6.experiments.recursion [--ledger PATH]

An adoption in process c shows a modified learner. It does not show that the modified learner
is a better improver of the learner, which is what "recursive" would mean. In every generation
the climb's improver is the current version itself. This driver runs, for every generation
g >= 2 that started from a version other than generation 0, two more searches from the same
start, on the same categories, with the same seeds, budget, objective and CPU limit as that
generation's climb:

  gen0      the improver is generation 0 of the first design (search seed 3000+g, as the climb)
  random    the random proposer (search seed 4000+g)

and puts each nominee through that generation's gate and confirmation (the same set-aside
categories, seeds and bootstrap seed). If the climb's nominees are no better at the gate than
those of generation 0 as improver, the improver did not improve.

The driver refuses to start before process c is frozen. Its runs carry purposes that begin
with ``recursion:`` and are not counted as compute of process c.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from rsi6.experiments.alternating import split_of
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(os.path.dirname(HERE), "registry")
LIVE = os.path.join(os.path.dirname(HERE), "ledger", "live.jsonl")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=LIVE)
    args = parser.parse_args()
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    registered = find(ledger, type="registration_c")
    if registered is None or find(ledger, type="freeze", process="c") is None:
        raise SystemExit("process c is not frozen: the recursion check runs after it, so that it cannot change it")
    reg = registered["registration"]
    amendment = json.load(open(os.path.join(REGISTRY, "amendment_4.json")))
    if find(ledger, type="amendment", number=4) is None:
        ledger.append({"type": "amendment", "number": 4, "digest": ledgers.digest(amendment), "amendment": amendment})
    rounds.RULES.update(reg["rules"])
    v0 = designs.default(reg["design"])
    cache = Cache(ledger)
    adopted = {a["round"]: a["version"] for a in ledger.select(type="adopt", process="c")}
    current, compared = v0, []
    for g in range(1, reg["generations_planned"] + 1):
        if designs.digest(current) != designs.digest(v0):
            light, _, aside = split_of(g, reg)
            seeds = [1000 + 10 * g + 1, 1000 + 10 * g + 2]
            gate_seeds = [2000 + 10 * g + k for k in range(1, 7)]
            confirm_seeds = [3000 + 10 * g + k for k in range(1, 7)]
            row = {"generation": g, "start": designs.digest(current)}
            climb = find(ledger, type="search", tag=f"search:c{g}:climb")
            own_gate = find(ledger, type="gate", tag=f"gate:c{g}:climb")
            own_check = find(ledger, type="confirm", tag=f"confirm:c{g}:climb")
            row["self"] = {"found": None if climb["best_cost"] is None else -climb["best_cost"], "nominee": climb["nominee"],
                           "gate": own_gate["mean_min"] if own_gate else 0.0, "gate_passes": bool(own_gate and own_gate["adopted"]),
                           "confirmation": own_check["mean_min"] if own_check else 0.0}
            for name, kind, improver, seed in (("gen0", "learner", v0, 3000 + g), ("random", "random", None, 4000 + g)):
                tag = f"recursion:c{g}:{name}"
                record = find(ledger, type="search", tag=tag)
                if record is None:
                    record = rounds.search(kind, improver, current, light, seeds, reg["budgets"]["search"], reg["climb_cpu_limit"],
                                           cache, tag, seed=seed, objective=rounds.breadth)
                    record = ledger.append(dict(record, round=f"c{g}", name=f"recursion:{name}", process="c", diagnostic="recursion",
                                                objective="breadth"))
                entry = {"found": None if record["best_cost"] is None else -record["best_cost"], "nominee": record["nominee"],
                         "gate": 0.0, "gate_passes": False, "confirmation": 0.0}
                nominee = record["nominee_version"]
                if nominee is not None:
                    decision = find(ledger, type="gate", tag=tag + ":gate")
                    if decision is None:
                        decision = ledger.append(dict(rounds.gate(current, nominee, aside, gate_seeds, reg["budgets"]["run"], cache,
                                                                  tag + ":gate", seed=200 + g),
                                                      round=f"c{g}", name=f"recursion:{name}", process="c", diagnostic="recursion"))
                    check = find(ledger, type="confirm", tag=tag + ":confirm")
                    if check is None:
                        check = ledger.append(dict(rounds.confirm(current, nominee, aside, confirm_seeds, reg["budgets"]["run"], cache,
                                                                  tag + ":confirm"),
                                                   round=f"c{g}", name=f"recursion:{name}", process="c", diagnostic="recursion"))
                    entry.update({"gate": decision["mean_min"], "gate_passes": bool(decision["adopted"]), "confirmation": check["mean_min"]})
                row[name] = entry
                say(f"generation {g} {name}: found {entry['found']} | gate {entry['gate']:+.4f} (passes {entry['gate_passes']})",
                    f"| confirmation {entry['confirmation']:+.4f}")
            row["D_gen0"] = row["self"]["gate"] - row["gen0"]["gate"]
            row["D_random"] = row["self"]["gate"] - row["random"]["gate"]
            say(f"generation {g}: the climb's nominee at the gate {row['self']['gate']:+.4f}; minus generation 0 as improver",
                f"{row['D_gen0']:+.4f}; minus the random proposer {row['D_random']:+.4f}")
            compared.append(row)
        if g in adopted:
            current = adopted[g]
    if find(ledger, type="recursion_done") is None:
        ledger.append({"type": "recursion_done", "process": "c", "generations": compared,
                       "better_than_gen0": int(sum(r["D_gen0"] > 0 for r in compared)),
                       "better_than_random": int(sum(r["D_random"] > 0 for r in compared)), "compared": len(compared)})
    say("generations compared:", len(compared), "| climb better than generation 0 as improver in", sum(r["D_gen0"] > 0 for r in compared),
        "| better than the random proposer in", sum(r["D_random"] > 0 for r in compared))
    return 0


if __name__ == "__main__":
    sys.exit(main())
