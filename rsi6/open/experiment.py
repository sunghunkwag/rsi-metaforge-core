"""The registered experiment of the open design (amendment 5).

    python -m rsi6.open.experiment --stage discovery|selection|swap|heldout [--ledger PATH]

Four stages, each run once, in this order, on the working ledger. Every rule is in
``registry/registration_o.json``; the driver reads it and checks that the ledger holds the same
file. A stopped stage is resumed by starting the driver again: it replays the stage from its
start (every measurement served from the ledger, every random choice repeated), checks that
each replayed record agrees with the recorded one, and goes on.

``discovery``  five arms from generation 0 of the open design, two independent lineages each, on
               the discovery categories, their steps interleaved so that the load of the machine
               falls on every arm alike; every lineage stops when it has used the registered CPU.
``selection``  the last parent of every lineage, and generation 0, on the confirming half of the
               fresh instances of the discovery categories with seeds no stage has used; the
               better lineage of an arm on these measurements is the arm's final mechanism.
``swap``       does a discovered learning principle make discovery better? If the final
               mechanism of the recursive arm has a learning principle other than generation 0's,
               paired replicates of discovery from generation 0 are run, one with the
               discoverer's weights learned by that principle and one by generation 0's, at equal
               CPU and on the same seeds; otherwise the stage records that the recursion was never
               exercised.
``heldout``    every arm's final mechanism, generation 0 of both designs, and every one of them
               except the recursive arm's with its training budget raised to the CPU of the
               recursive arm's final mechanism (the compute-matched comparison of every control),
               on the held-out categories, which no stage before touches, at the registered run
               budget; and the other lineage of every arm at the registered budget, to show the
               spread between lineages.
``heldout_later``  the same on the six categories of the earlier processes' sealed target test,
               with seeds of its own, once that test has run on them (it refuses before); no run
               of the open design touches them until then.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6 import environments
from rsi6.experiments import guard
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.open import discovery, evaluate

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRATION = os.path.join(os.path.dirname(HERE), "registry", "registration_o.json")
ARMS = ("recursive", "frozen", "uniform", "shuffled", "tune")
ORDER = ("discovery", "selection", "swap", "heldout", "heldout_later")


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def find(ledger, **where):
    hits = ledger.select(**where)
    return hits[-1] if hits else None


def make_lineages(reg, cache, ledger, memo, stage, plan, seeds_of, confirm_of):
    """``plan``: (arm, index, mode, principle source or None) for every lineage. Lineage k of every
    arm draws from the same random stream, so that arms differ only where their stated difference
    acts."""
    v0 = designs.default("o")
    out = []
    for arm, k, mode, source in plan:
        rng = np.random.default_rng([reg["seed"], sum(map(ord, stage)), k])
        out.append((arm, discovery.Lineage(f"{stage}:{arm}{k}", v0, reg["discovery"], seeds_of(arm, k), confirm_of(arm, k), cache,
                                           ledger, rng, dict(reg["knobs"]), mode=mode, memo=memo, reference=v0,
                                           principle_source=source)))
    return out


def run_until_spent(lineages, budget, stage, ledger) -> None:
    """Interleaved steps until every lineage has used ``budget`` CPU-seconds (the step that
    crosses the budget is completed and counted)."""
    while True:
        active = [(arm, L) for arm, L in lineages if L.spent < budget]
        if not active:
            break
        for arm, L in active:
            r = L.step()
            say(f"{L.name} step {r['step']}: parent {r['parent_score']:.4f}" + (f" -> {r['parent_score_after']:.4f}" if r["accepted"] else ""),
                f"| spent {L.spent:.0f} of {budget:.0f}")
    for arm, L in lineages:
        discovery.append_once(ledger, {"type": "o_lineage_done", "stage": stage, "arm": arm, "lineage": L.name, "steps": L.steps,
                                       "final": L.parent, "final_digest": designs.digest(L.parent), "final_score": L.parent_score,
                                       "spent": L.spent, "accepted": L.accepted,
                                       "discoverer": {"knobs": L.D.knobs, "weights": [float(x) for x in L.D.weights()],
                                                      "library": L.D.library, "principle_now": L.D.source, "mode": L.D.mode}},
                              ("lineage",))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=guard.LIVE)
    parser.add_argument("--stage", choices=ORDER, required=True)
    parser.add_argument("--registration", default=REGISTRATION)
    parser.add_argument("--dev", action="store_true", help="development only: a scratch ledger, the CPU budgets divided by 20")
    args = parser.parse_args()
    if args.dev == guard.is_registered(args.ledger):
        raise SystemExit("the registered experiment writes the working ledger; --dev writes a scratch ledger")
    if not args.dev:
        if os.path.realpath(args.registration) != os.path.realpath(REGISTRATION):
            raise SystemExit("the registered experiment reads registry/registration_o.json and no other file")
        if not os.path.exists(guard.LIVE) or not os.path.samefile(args.ledger, guard.LIVE):
            raise SystemExit("the registered experiment writes ledger/live.jsonl, which must exist")
    guard.same_history(args.ledger)
    guard.single_writer(args.ledger)
    reg = json.load(open(args.registration))
    if not args.dev:                                       # the code that runs is the code that was registered
        root = os.path.dirname(os.path.dirname(HERE))
        wrong = [f for f, sha in reg["generation_0"]["files"].items()
                 if hashlib.sha256(open(os.path.join(root, f), "rb").read()).hexdigest() != sha]
        if wrong or designs.digest(designs.default("o")) != reg["generation_0"]["version_digest"]:
            raise SystemExit(f"the files or generation 0 differ from the registration: {wrong or 'version digest'}")
    ledger = ledgers.Ledger(args.ledger)
    ledger.verify()
    if not args.dev:
        recorded = find(ledger, type="registration_o")
        if recorded is None:
            guard.amendment(ledger, 5, "the open design and the discovery of its mechanisms are registered (registration_o.json)")
            recorded = ledger.append({"type": "registration_o", "digest": ledgers.digest(reg), "registration": reg})
        if recorded["digest"] != ledgers.digest(reg):
            raise SystemExit("registration_o.json differs from the file recorded in the ledger")
    else:
        reg = dict(reg, cpu_per_lineage=reg["cpu_per_lineage"] / 20, swap=dict(reg["swap"], cpu=reg["swap"]["cpu"] / 20, replicates=1))
    for e in reg["discovery"] + reg["heldout"]:
        if roles.effective_role(environments.load(e).category, ledger) != "source":
            raise SystemExit(f"{e} is not in the source pool")
    if args.stage == "heldout_later" and not ledger.select(type="target_done"):
        raise SystemExit("the later held-out stage runs only after the sealed target test of the earlier processes")
    cache = Cache(ledger)
    memo = {}
    v0, a0 = designs.default("o"), designs.default("a")
    stage, S = args.stage, reg["seeds"]
    if find(ledger, type="o_stage_done", stage=stage):
        say(f"the stage {stage} is recorded")
        return 0
    if stage != ORDER[0] and not find(ledger, type="o_stage_done", stage=ORDER[ORDER.index(stage) - 1]):
        raise SystemExit(f"the stage {stage} follows {ORDER[ORDER.index(stage) - 1]}")
    if stage == "discovery":
        plan = [(arm, k, arm, None) for arm in ARMS for k in range(reg["lineages"])]
        lineages = make_lineages(reg, cache, ledger, memo, "discovery", plan, lambda arm, k: S["discovery"],
                                 lambda arm, k: S["confirm_base"] + discovery.SEED_STRIDE * (ARMS.index(arm) * reg["lineages"] + k))
        run_until_spent(lineages, reg["cpu_per_lineage"], "discovery", ledger)
        ledger.append({"type": "o_stage_done", "stage": "discovery"})
    elif stage == "selection":
        done = ledger.select(type="o_lineage_done", stage="discovery")
        envs, seeds, budget = reg["discovery"], S["selection"], discovery.ASSESS_BUDGET
        base = evaluate.runs(cache, v0, envs, seeds, "open-selection:o0", budget)
        table, finals = {}, {}
        for r in done:
            got = evaluate.runs(cache, r["final"], envs, seeds, f"open-selection:{r['lineage']}", budget)
            table[r["lineage"]] = {"arm": r["arm"], "digest": r["final_digest"], "score": discovery.score_of(got),
                                   "minus_o0": float(discovery.paired(got, base).mean())}
        for arm in ARMS:
            mine = {k: v for k, v in table.items() if v["arm"] == arm}
            finals[arm] = max(sorted(mine), key=lambda k: mine[k]["score"])
            say(f"selection {arm}: {[(k, round(v['minus_o0'], 4)) for k, v in mine.items()]} -> {finals[arm]}")
        ledger.append({"type": "o_stage_done", "stage": "selection", "seeds": seeds, "part": "B", "table": table, "finals": finals,
                       "o0_score": discovery.score_of(base)})
    elif stage == "swap":
        sel = find(ledger, type="o_stage_done", stage="selection")
        final = next(r for r in ledger.select(type="o_lineage_done", stage="discovery") if r["lineage"] == sel["finals"]["recursive"])
        if discovery.principle(final["final"]) == discovery.principle(v0):
            ledger.append({"type": "o_stage_done", "stage": "swap", "exercised": False,
                           "why": "the recursive arm's final mechanism has generation 0's learning principle: the recursion was never exercised"})
            say("swap: the recursion was never exercised")
            return 0
        source = final["final"]
        plan = []
        for k in range(reg["swap"]["replicates"]):
            plan += [("discovered", k, "frozen", source), ("generation0", k, "frozen", v0)]
        lineages = make_lineages(reg, cache, ledger, memo, "swap", plan,
                                 lambda arm, k: [S["swap_base"] + 3 * k + j for j in range(3)],    # paired: the same seeds for both
                                 lambda arm, k: S["swap_confirm_base"] + discovery.SEED_STRIDE * (2 * k + (arm == "discovered")))
        run_until_spent(lineages, reg["swap"]["cpu"], "swap", ledger)
        envs, seeds, budget = reg["discovery"], S["swap_assess"], discovery.ASSESS_BUDGET
        base = evaluate.runs(cache, v0, envs, seeds, "open-swap:o0", budget)
        pairs = []
        for k in range(reg["swap"]["replicates"]):
            row = {"replicate": k}
            for arm, L in lineages:
                if L.name.endswith(f"{arm}{k}"):
                    got = evaluate.runs(cache, L.parent, envs, seeds, f"open-swap:{L.name}", budget)
                    row[arm] = float(discovery.paired(got, base).mean())
            pairs.append(row)
        diffs = [p["discovered"] - p["generation0"] for p in pairs]
        ledger.append({"type": "o_stage_done", "stage": "swap", "exercised": True, "principle": discovery.principle(source),
                       "from": final["lineage"], "pairs": pairs, "mean_difference": float(np.mean(diffs)),
                       "positive": int(sum(d > 0 for d in diffs)), "seeds": seeds, "part": "B"})
        say(f"swap: discovered principle minus generation 0's, per replicate {[round(d, 4) for d in diffs]}")
    else:
        sel = find(ledger, type="o_stage_done", stage="selection")
        lineage = {r["lineage"]: r for r in ledger.select(type="o_lineage_done", stage="discovery")}
        later = stage == "heldout_later"
        envs = reg["heldout_later"]["categories"] if later else reg["heldout"]
        seeds = reg["heldout_later"]["seeds"] if later else S["heldout"]
        arms = {"a0": a0, "o0": v0}
        for arm in ARMS:
            arms[arm] = lineage[sel["finals"][arm]]["final"]
            other = [r for r in lineage.values() if r["arm"] == arm and r["lineage"] != sel["finals"][arm]]
            for r in other:                                    # the other lineage, to show the spread between lineages
                arms[f"{arm}:other"] = r["final"]
        results = {}
        for name, version in arms.items():
            results[name] = evaluate.runs(cache, version, envs, seeds, f"open-{stage}:{name}")
            say(f"held-out {name}: acquired {np.mean([r['acquired'] for r in results[name]]):.4f}")
        want = {(r["env"], r["seed"]): evaluate.cpu(r) for r in results["recursive"]}
        controls = [("o0", v0), ("a0", a0)] + [(arm, arms[arm]) for arm in ARMS if arm != "recursive"]
        for base_name, version in controls:
            rows = evaluate.raise_until(cache, version, want, f"open-{stage}:{base_name}@recursive")
            results[f"{base_name}@recursive"] = rows
            discovery.append_once(ledger, {"type": "o_matched", "stage": stage, "arm": f"{base_name}@recursive",
                                           "keys": [r["key"] for r in rows], "reached": [bool(r["reached"]) for r in rows],
                                           "levels": [r["levels"] for r in rows], "budgets": [r["budget"]["train"] for r in rows]},
                                  ("stage", "arm"))
        ledger.append({"type": "o_stage_done", "stage": stage, "envs": envs, "seeds": seeds,
                       "arms": {name: [r["key"] for r in rows] for name, rows in results.items()},
                       "versions": {name: designs.digest(v) for name, v in arms.items()}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
