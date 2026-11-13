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

The driver refuses to start before process c is frozen and its external gate is recorded, so
that it can change neither. Its records have their own types (``recursion_search``,
``recursion_gate``, ``recursion_confirm``, ``recursion_done``) and its runs carry purposes that
begin with ``recursion:``: nothing of it is read as a search, a gate or compute of process c.
It should run alone on the machine, like the climbs it is compared with.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from rsi6.experiments import guard
from rsi6.experiments.alternating import split_of
from rsi6.kernel import ledger as ledgers
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.meta import rounds


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=guard.LIVE)
    parser.add_argument("--dev", type=float, default=None, help="development only: a scratch ledger, this many CPU-seconds "
                        "for a search, and only the generations recorded in it")
    args = parser.parse_args()
    dev = args.dev is not None
    if dev and (guard.is_registered(args.ledger) or args.dev <= 0):
        raise SystemExit("--dev needs a scratch ledger and a positive number of CPU-seconds")
    if not dev and not guard.is_registered(args.ledger):
        raise SystemExit("outside the development mode the ledger is ledger/live.jsonl or ledger/main.jsonl")
    guard.same_history(args.ledger)
    guard.single_writer(args.ledger)
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    registered = find(ledger, type="registration_c")
    frozen = find(ledger, type="freeze", process="c")
    if registered is None or frozen is None or find(ledger, type="external_gate", process="c") is None:
        raise SystemExit("process c is not frozen or its external gate is not recorded: the recursion check runs after both")
    if find(ledger, type="recursion_done") is not None:
        say("the recursion check is already recorded")
        return 0
    reg = registered["registration"]
    guard.amendment(ledger, 4, guard.AMENDMENT_4)
    rounds.RULES.update(reg["rules"])
    v0 = designs.default(reg["design"])
    cache = Cache(ledger)
    adoptions = ledger.select(type="adopt", process="c")
    adopted = {a["round"]: a["version"] for a in adoptions}
    if len(adopted) != len(adoptions):
        raise SystemExit("process c has more than one adoption in a generation")
    cpu_limit = args.dev if dev else reg["climb_cpu_limit"]
    current, compared = v0, []
    for g in range(1, reg["generations_planned"] + 1):
        if find(ledger, type="c_generation_done", generation=g) is None:
            if not dev:
                raise SystemExit(f"generation {g} of process c is not recorded although the process is frozen")
            break
        if designs.digest(current) != designs.digest(v0):
            light, _, aside = split_of(g, reg)
            seeds = [1000 + 10 * g + 1, 1000 + 10 * g + 2]
            gate_seeds = [2000 + 10 * g + k for k in range(1, 7)]
            confirm_seeds = [3000 + 10 * g + k for k in range(1, 7)]
            row = {"generation": g, "start": designs.digest(current)}
            climb = find(ledger, type="search", tag=f"search:c{g}:climb")
            if climb is None or climb["start"] != designs.digest(current) or sorted(climb["envs"]) != sorted(light):
                raise SystemExit(f"generation {g}: the recorded climb did not start from the version this generation started from")
            own_gate = find(ledger, type="gate", tag=f"gate:c{g}:climb")
            own_check = find(ledger, type="confirm", tag=f"confirm:c{g}:climb")
            for record in (own_gate, own_check):
                if record is not None and (record["incumbent"] != designs.digest(current) or record["nominee"] != climb["nominee"]):
                    raise SystemExit(f"generation {g}: the recorded gate of the climb compares other versions than its start and its nominee")
            row["self"] = {"found": None if climb["best_cost"] is None else -climb["best_cost"], "nominee": climb["nominee"],
                           "gate": own_gate["mean_min"] if own_gate else 0.0, "gate_passes": bool(own_gate and own_gate["adopted"]),
                           "confirmation": own_check["mean_min"] if own_check else 0.0}
            for name, kind, improver, seed in (("gen0", "learner", v0, 3000 + g), ("random", "random", None, 4000 + g)):
                tag = f"recursion:c{g}:{name}"
                record = find(ledger, type="recursion_search", tag=tag)
                if record is None:
                    record = rounds.search(kind, improver, current, light, seeds, reg["budgets"]["search"], cpu_limit,
                                           cache, tag, seed=seed, objective=rounds.breadth)
                    record = ledger.append(dict(record, type="recursion_search", generation=g, name=name, process="c",
                                                objective="breadth"))
                entry = {"found": None if record["best_cost"] is None else -record["best_cost"], "nominee": record["nominee"],
                         "gate": 0.0, "gate_passes": False, "confirmation": 0.0}
                nominee = record["nominee_version"]
                if nominee is not None:
                    decision = find(ledger, type="recursion_gate", tag=tag + ":gate")
                    if decision is None:
                        decision = ledger.append(dict(rounds.gate(current, nominee, aside, gate_seeds, reg["budgets"]["run"], cache,
                                                                  tag + ":gate", seed=200 + g),
                                                      type="recursion_gate", generation=g, name=name, process="c"))
                    check = find(ledger, type="recursion_confirm", tag=tag + ":confirm")
                    if check is None:
                        check = ledger.append(dict(rounds.confirm(current, nominee, aside, confirm_seeds, reg["budgets"]["run"], cache,
                                                                  tag + ":confirm"),
                                                   type="recursion_confirm", generation=g, name=name, process="c"))
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
    ledger.append({"type": "recursion_done", "process": "c", "generations": compared, "compared": len(compared),
                   "climb_named_a_nominee": int(sum(r["self"]["nominee"] is not None for r in compared)),
                   "better_than_gen0": int(sum(r["D_gen0"] > 0 for r in compared)),
                   "better_than_random": int(sum(r["D_random"] > 0 for r in compared))})
    say("generations compared:", len(compared), "| climb better than generation 0 as improver in", sum(r["D_gen0"] > 0 for r in compared),
        "| better than the random proposer in", sum(r["D_random"] > 0 for r in compared))
    return 0


if __name__ == "__main__":
    sys.exit(main())
