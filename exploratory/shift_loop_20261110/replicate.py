"""The registered replication (PREDICTIONS.md, Addendum 7), start to finish in one process.

Expert iteration with representation search from generation 0, configuration B, then the
evaluation and the controls, with no step between them that a person decides:

  1. fork the workers; generate FRESH-3 in the driver (``fresh3.py``); no loop step runs it;
  2. ``expert.run`` with machinery S + C + f + R;
  3. the final vocabulary and generation 0 at the student budget and at the deployment budget
     on the held-out partitions of configuration B and on FRESH-3;
  4. generation 0 at the cumulative budgets, with
        T  = student runs x 338 x student budget + teacher runs x 214 x teacher budget
        for an evaluation set of N tasks, D = N x deployment budget
        C1 = (T + D) / 338     every task of the study gets the same share (held-out B only)
        C2 = (T + D) / N       the whole budget is spent on the evaluated tasks alone
  5. the audit (sound counts), exact one-sided sign tests on the discordant tasks, the same
     over routine clusters, and the outcome class by the registered rule.

    python replicate.py <out.json> [workers] [--tiny] [--from-loop <earlier out.json>]

``--tiny`` is a smoke test at toy budgets and decides nothing. ``--from-loop`` takes the loop
report of an earlier, interrupted run instead of running the loop again (the loop is
deterministic); the report says when it was used.
"""
from __future__ import annotations

import json
import math
import sys
import time

import expert
from expert_ablate import spec_without
from hybrid import ALL, Harness, spec_of, summary
from loop import CONFIGS
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

COMPONENTS = "SCfR"
DEPLOY = 100_000
TASKS = 338                      # the exposed tasks every student run covers
STEPS = 2000
ALPHA = 0.05


def sign_test(wins: int, losses: int) -> float:
    """One-sided exact p: the chance of at least ``wins`` heads in wins + losses fair tosses."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def paired(treated: set, control: set) -> dict:
    wins, losses = len(treated - control), len(control - treated)
    return {"trained": len(treated), "control": len(control), "trained_only": wins, "control_only": losses,
            "p_one_sided": round(sign_test(wins, losses), 5)}


def clustered(treated: set, control: set, cluster_of: dict) -> dict:
    """The sign test over clusters of tasks: a cluster counts once, by the sign of its net."""
    net = {}
    for key in treated ^ control:
        net[cluster_of[key]] = net.get(cluster_of[key], 0) + (1 if key in treated else -1)
    wins = sum(1 for value in net.values() if value > 0)
    losses = sum(1 for value in net.values() if value < 0)
    return {"clusters_for_trained": wins, "clusters_for_control": losses, "clusters_level": len(net) - wins - losses,
            "p_one_sided": round(sign_test(wins, losses), 5)}


class Sound:
    """Sound verdicts for the exposed partitions (audit_all) and for FRESH-3 (its own references)."""

    def __init__(self, fresh_tasks):
        import audit_all
        import oracles
        self.auditor = audit_all.Auditor()
        self.oracles = oracles
        self.fresh = {task.name: task for task in fresh_tasks}
        self.inputs = {}
        self.cache = {}

    def __call__(self, key: str, text: str) -> bool:
        partition, name = key.split("/", 1)
        if partition != "fresh3":
            return bool(self.auditor.sound(key, text))
        if (key, text) in self.cache:
            return self.cache[(key, text)]
        task = self.fresh[name]
        if name not in self.inputs:
            self.inputs[name] = self.oracles.fresh_inputs(key, task, [task.reference])
        term = parse(text)
        verdict = True
        for xs in self.inputs[name]:
            want = task.reference(list(xs))
            if want is None:
                continue
            got = evaluate(term, (list(xs),), step_budget=STEPS)
            if not got.ok or got.value != want or type(got.value) is not type(want):
                verdict = False
                break
        self.cache[(key, text)] = verdict
        return verdict


def outcome_class(primary: dict, generous: dict, held: dict, accepted_cycles: int) -> str:
    """The registered reading (Addendum 7). ``primary``: FRESH-3, trained at the deployment budget
    against generation 0 at C2; ``generous``: the same against everything generation 0 solves at
    any budget run; ``held``: held-out B against generation 0 at C1."""
    if accepted_cycles == 0:
        return "not replicated: the loop accepted no symbol, so the trained state is generation 0"
    if primary["trained"] <= primary["control"]:
        return "not replicated: no lead on FRESH-3 over generation 0 at the cumulative budget"
    if primary["p_one_sided"] >= ALPHA:
        return "not established: a lead on FRESH-3 that the sign test does not separate from chance"
    if held["trained"] <= held["control"]:
        return "replicated on FRESH-3 only: no lead on held-out B over generation 0 at C1"
    if generous["trained"] > generous["control"] and generous["p_one_sided"] < ALPHA:
        return "replicated strongly: also ahead of everything generation 0 solves at any budget run"
    return "replicated"


def main(out_path: str, workers: int, tiny: bool, from_loop: str | None = None) -> None:
    global DEPLOY
    if tiny:
        expert.STUDENT, expert.TEACHER, DEPLOY = 300, 1500, 1500
    learn = CONFIGS["B"]
    held = [p for p in ALL if p not in learn]
    harness = Harness(workers, ALL)
    import fresh3                                   # loads the FRESH partitions: after the fork
    tally = {}
    fresh_tasks = fresh3.make(statistics=tally)
    harness.add_partition("fresh3", fresh_tasks, [task.public_view() for task in fresh_tasks])
    out = {"components": COMPONENTS, "student": expert.STUDENT, "teacher": expert.TEACHER, "deploy": DEPLOY,
           "tiny": tiny, "fresh3": {"digest": fresh3.digest(fresh_tasks), "tally": tally,
                                    "names": [task.name for task in fresh_tasks],
                                    "requests": [str(task.request) for task in fresh_tasks]}}
    print(f"FRESH-3: {len(fresh_tasks)} tasks, digest {out['fresh3']['digest'][:16]}", flush=True)

    # ---- 2. the loop ---------------------------------------------------------------------------
    if from_loop:
        earlier = json.load(open(from_loop))
        if earlier["fresh3"]["digest"] != out["fresh3"]["digest"] or earlier["components"] != COMPONENTS \
                or (earlier["student"], earlier["teacher"]) != (expert.STUDENT, expert.TEACHER):
            raise SystemExit("the earlier report is not of this protocol")
        report = earlier["loop"]
        out["loop_taken_from"] = from_loop
    else:
        report = expert.run(harness, learn, max_cycles=1 if tiny else expert.MAX_CYCLES, components=COMPONENTS)
    out["loop"] = report
    json.dump(out, open(out_path, "w"), indent=1)
    learn_tasks = sum(len(harness.public[p]) for p in learn)
    training = report["executions"]["student"] * TASKS * expert.STUDENT \
        + report["executions"]["teacher"] * learn_tasks * expert.TEACHER
    sets = {"heldB": held, "fresh3": ["fresh3"]}
    sizes = {name: sum(len(harness.public[p]) for p in parts) for name, parts in sets.items()}
    budgets = {"heldB": {"C1": round((training + sizes["heldB"] * DEPLOY) / TASKS),
                         "C2": round((training + sizes["heldB"] * DEPLOY) / sizes["heldB"])},
               "fresh3": {"C2": round((training + sizes["fresh3"] * DEPLOY) / sizes["fresh3"])}}
    out["training_candidates"], out["set_sizes"], out["control_budgets"] = training, sizes, budgets
    print(f"training {training} candidates; control budgets {budgets}", flush=True)

    # ---- 3 and 4. evaluation runs ---------------------------------------------------------------
    rows = {}

    def measure(label, spec, partitions):
        started = time.perf_counter()
        result = harness.run(spec, partition_names=partitions)
        rows[label] = {"budget": spec["budget"], "partitions": list(partitions), "counts": summary(result),
                       "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                                    for p, rs in result.items() for r in rs if r["solved"]},
                       "rejected": sorted(f"{p}/{r['name']}" for p, rs in result.items() for r in rs
                                          if r["term"] is not None and not r["solved"]),
                       "used": {f"{p}/{r['name']}": r["used"] for p, rs in result.items() for r in rs if r["solved"]},
                       "seconds": round(time.perf_counter() - started)}
        print(f"{label:22s} budget {spec['budget']:>8} {rows[label]['counts']} | {rows[label]['seconds']} s", flush=True)
        out["rows"] = rows
        json.dump(out, open(out_path, "w"), indent=1)

    both = held + ["fresh3"]
    measure("trained@student:fresh3", spec_without(report, expert.STUDENT, "trained", set(), COMPONENTS), ["fresh3"])
    measure("gen0@student:fresh3", spec_of("gen0", expert.STUDENT, COMPONENTS), ["fresh3"])
    measure("trained@deploy", spec_without(report, DEPLOY, "trained", set(), COMPONENTS), both)
    measure("gen0@deploy", spec_of("gen0", DEPLOY, COMPONENTS), both)
    for name, parts in sets.items():
        for control in budgets[name]:
            measure(f"gen0@{control}:{name}", spec_of("gen0", budgets[name][control], COMPONENTS), parts)

    # ---- 5. audit and tests ------------------------------------------------------------------------
    sound = Sound(fresh_tasks)
    for row in rows.values():
        row["sound"] = sorted(key for key, value in row["programs"].items() if sound(key, value[0]))
        row["sound_counts"] = {p: sum(1 for key in row["sound"] if key.startswith(p + "/")) for p in row["partitions"]}
    first = report["timeline"][0]                     # generation 0 at the student budget, every exposed task
    last = {t["run"]: t for t in report["timeline"]}[report["student_last"]]
    student = {label: {key for key, value in state["programs"].items() if sound(key, value[0])}
               for label, state in (("gen0", first), ("trained", last))}

    def restricted(label, parts):
        return {key for key in rows[label]["sound"] if key.split("/", 1)[0] in parts}

    def within(keys, parts):
        return {key for key in keys if key.split("/", 1)[0] in parts}

    arms = {}
    for name, parts in sets.items():
        controls = {"equal": restricted("gen0@deploy", parts)}
        for control in budgets[name]:
            controls[control] = restricted(f"gen0@{control}:{name}", parts)
        any_budget = set().union(*controls.values())
        any_budget |= restricted("gen0@student:fresh3", parts) if name == "fresh3" else within(student["gen0"], parts)
        controls["any"] = any_budget
        arms[name] = {"trained": restricted("trained@deploy", parts), "controls": controls}
    comparisons = {}
    for name in sets:
        for control, reference in arms[name]["controls"].items():
            comparisons[f"{name}: trained@deploy vs gen0@{control}"] = paired(arms[name]["trained"], reference)
    comparisons["fresh3: trained@student vs gen0@student"] = paired(
        restricted("trained@student:fresh3", ["fresh3"]), restricted("gen0@student:fresh3", ["fresh3"]))
    comparisons["heldB: trained@student vs gen0@student"] = paired(within(student["trained"], held), within(student["gen0"], held))
    pooled_control = arms["heldB"]["controls"]["C1"] | arms["fresh3"]["controls"]["C2"]
    comparisons["pooled: trained@deploy vs gen0@(C1 on heldB, C2 on fresh3)"] = paired(
        arms["heldB"]["trained"] | arms["fresh3"]["trained"], pooled_control)
    out["comparisons"] = comparisons

    # sensitivity: FRESH-3 tasks share routines, so the same test over routine clusters
    stage = {f"fresh3/{task.name}": task.stages for task in fresh_tasks}
    primary_arms = (arms["fresh3"]["trained"], arms["fresh3"]["controls"]["C2"])
    out["clusters"] = {
        "by first-stage routine": clustered(*primary_arms, {key: stages[0][0] for key, stages in stage.items()}),
        "by second-stage routine": clustered(*primary_arms, {key: stages[1][0] for key, stages in stage.items()})}
    kinds = {f"fresh3/{task.name}": str(task.request).split("->")[-1].strip() for task in fresh_tasks}
    out["by_output_type"] = {kind: {"tasks": sum(1 for value in kinds.values() if value == kind),
                                    "trained": sum(1 for key in primary_arms[0] if kinds[key] == kind),
                                    "control": sum(1 for key in primary_arms[1] if kinds[key] == kind)}
                             for kind in sorted(set(kinds.values()))}
    accepted = sum(1 for t in report["timeline"] if t.get("accepted"))
    out["accepted_cycles"] = accepted
    out["outcome"] = outcome_class(comparisons["fresh3: trained@deploy vs gen0@C2"],
                                   comparisons["fresh3: trained@deploy vs gen0@any"],
                                   comparisons["heldB: trained@deploy vs gen0@C1"], accepted)
    json.dump(out, open(out_path, "w"), indent=1)
    print()
    for label, row in rows.items():
        print(f"{label:22s} verified {row['counts']} sound {row['sound_counts']}")
    for label, c in comparisons.items():
        print(f"{label:58s} sound {c['trained']} against {c['control']}; only trained {c['trained_only']}, "
              f"only control {c['control_only']}; one-sided p {c['p_one_sided']}")
    print("clusters:", json.dumps(out["clusters"]))
    print("by output type:", json.dumps(out["by_output_type"]))
    print("OUTCOME:", out["outcome"])
    harness.close()


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 4, "--tiny" in sys.argv,
         sys.argv[sys.argv.index("--from-loop") + 1] if "--from-loop" in sys.argv else None)
