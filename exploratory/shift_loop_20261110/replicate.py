"""The registered replication (PREDICTIONS.md, Addendum 7), start to finish in one process.

Expert iteration with representation search from generation 0, configuration B, then the
evaluation and the controls, with no step between them that a person decides:

  1. fork the workers; generate FRESH-3 in the driver (``fresh3.py``) and check that it is the
     registered set; no loop step runs it;
  2. ``expert.run`` with machinery S + C + f + R;
  3. generation 0 (same machinery, no learned symbol) at the cumulative budget ceilings, with
        T  = student runs x 338 x student budget + teacher runs x 214 x teacher budget
        for an evaluation set of N tasks, D = N x deployment budget
        C2 = (T + D) / N       the whole budget on the evaluated tasks alone (both sets)
        C1 = (T + D) / 338     every task of the study gets the same share (held-out B)
        mid = sqrt(deployment budget x C2)   one more rung for the union (FRESH-3)
     and at the student and deployment budgets; the final vocabulary at those two budgets;
     the earlier combination (the 15 symbols of results/expertB.json) at the deployment budget
     on FRESH-3 as a secondary arm;
  4. the audit (sound counts); the primary comparison on FRESH-3 against everything generation
     0 solves at any budget run; for each task only one arm solves, what the other arm did on
     it; the family, output-type and leave-one-routine-out breakdowns; the outcome class by
     the registered rule; the predictions scored.

    python replicate.py <out.json> [workers] [--tiny] [--from-loop <earlier out.json>]

``--tiny`` is a smoke test at toy budgets on a separate smoke set of tasks (another seed); it
never runs the registered FRESH-3 set and decides nothing. ``--from-loop`` takes the loop
report of an earlier, interrupted run instead of running the loop again (the loop is
deterministic); the report says when it was used. Results do not depend on the worker count.
"""
from __future__ import annotations

import json
import math
import os
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
REGISTERED_DIGEST = "4da13e671411da8c"          # the first 16 hex digits; Addendum 7 gives all 64
EARLIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "expertB.json")


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
    wins = {cluster: value for cluster, value in sorted(net.items()) if value > 0}
    losses = {cluster: value for cluster, value in sorted(net.items()) if value < 0}
    return {"for_trained": wins, "for_control": losses, "level": len(net) - len(wins) - len(losses),
            "p_one_sided": round(sign_test(len(wins), len(losses)), 5)}


class Sound:
    """Sound verdicts for the exposed partitions (audit_all) and for FRESH-3 (its own references)."""

    def __init__(self, fresh_tasks, fresh3):
        import audit_all
        import oracles
        self.auditor = audit_all.Auditor()
        self.oracles = oracles
        self.fresh3 = fresh3
        self.fresh = {task.name: task for task in fresh_tasks}
        self.inputs = {}
        self.cache = {}
        self.pool = None
        self.pool_cache = {}

    def _agrees(self, task, text, inputs) -> bool:
        term = parse(text)
        for xs in inputs:
            want = task.reference(list(xs))
            if want is None or self.fresh3._kind(want) is None:      # outside the domain the task was made on
                continue
            got = evaluate(term, (list(xs),), step_budget=STEPS)
            if not got.ok or got.value != want or type(got.value) is not type(want):
                return False
        return True

    def __call__(self, key: str, text: str) -> bool:
        partition, name = key.split("/", 1)
        if partition != "fresh3":
            return bool(self.auditor.sound(key, text))
        if (key, text) not in self.cache:
            task = self.fresh[name]
            if name not in self.inputs:
                self.inputs[name] = self.oracles.fresh_inputs(key, task, [task.reference])
            self.cache[(key, text)] = self._agrees(task, text, self.inputs[name])
        return self.cache[(key, text)]

    def on_pool(self, key: str, text: str) -> bool:
        """FRESH-3 only, a stricter secondary reading: the program agrees with the generating
        function on every input of the FRESH input pool that the function is defined on."""
        if (key, text) not in self.pool_cache:
            if self.pool is None:
                self.pool = list(self.fresh3.input_pool())
            self.pool_cache[(key, text)] = self._agrees(self.fresh[key.split("/", 1)[1]], text, self.pool)
        return self.pool_cache[(key, text)]


def status(key: str, row: dict) -> str:
    """What a run did on a task it did not solve soundly."""
    if key in row["programs"]:
        return "verified, not sound"
    if key in row["rejected"]:
        return "rejected"
    return "no public match"


def kinds_of(treated: set, control: set, treated_row: dict, control_row: dict) -> dict:
    """The tasks only one arm solves, by what the other arm's run did on them. 'no public match'
    means that run spent its whole budget ceiling; in the other two it stopped at a wrong first
    match and the rest of its budget was not spent."""
    table = {"trained_only": {}, "control_only": {}}
    for side, winners, loser in (("trained_only", treated - control, control_row),
                                 ("control_only", control - treated, treated_row)):
        for key in sorted(winners):
            table[side].setdefault(status(key, loser), []).append(key)
    wins = len(table["trained_only"].get("no public match", []))
    losses = len(table["control_only"].get("no public match", []))
    return {"trained_only": {kind: len(keys) for kind, keys in table["trained_only"].items()},
            "control_only": {kind: len(keys) for kind, keys in table["control_only"].items()},
            "budget_bound": {"trained_only": wins, "control_only": losses,
                             "p_one_sided": round(sign_test(wins, losses), 5)},
            "tasks": table}


def outcome_class(flags: dict) -> str:
    """The registered reading (Addendum 7), from values computed by ``main``."""
    if flags["missing"]:
        return "no class: " + flags["missing"]
    if not flags["accepted"]:
        return "not replicated: the loop accepted no symbol, so the trained state is generation 0"
    if not flags["lead"]:
        return ("not replicated on FRESH-3. " +
                ("The trained state leads on held-out B, so the earlier lead is read as specific to the tasks it "
                 "was chosen on" if flags["held_out_b"] else
                 "It has no lead on held-out B either: the loop with R from generation 0 did not rebuild the "
                 "combined state, and the run says nothing about the earlier lead"))
    if not flags["significant"]:
        return "not established: a lead on FRESH-3 that the sign test does not separate from chance"
    endings = [{"none": "for the divisibility family only",
                "not separated": "outside the divisibility family not separated from chance",
                "significant": "beyond the divisibility family"}[flags["outside_family"]]]
    endings.append("with reach beyond the budget" if flags["budget_bound_lead"]
                   else "as a different first match, not reach beyond the budget")
    if not flags["reductions"]:
        endings.append("for list outputs only")
    endings.append("and on held-out B" if flags["held_out_b"] else "not on held-out B")
    return "replicated on FRESH-3 against everything generation 0 solves at any budget run; " + "; ".join(endings)


def main(out_path: str, workers: int, tiny: bool, from_loop: str | None = None) -> None:
    global DEPLOY
    if tiny:
        expert.STUDENT, expert.TEACHER, DEPLOY = 300, 1500, 1500
    learn = CONFIGS["B"]
    held = [p for p in ALL if p not in learn]
    harness = Harness(workers, ALL)
    import fresh3                                   # loads the FRESH partitions: after the fork
    tally = {}
    fresh_tasks = fresh3.make(60, fresh3.SMOKE_SEED, tally) if tiny else fresh3.make(statistics=tally)
    digest = fresh3.digest(fresh_tasks)
    if not tiny and (len(fresh_tasks) != fresh3.COUNT or not digest.startswith(REGISTERED_DIGEST)):
        raise SystemExit(f"this is not the registered FRESH-3 set: {len(fresh_tasks)} tasks, digest {digest}")
    harness.add_partition("fresh3", fresh_tasks, [task.public_view() for task in fresh_tasks])
    out = {"components": COMPONENTS, "student": expert.STUDENT, "teacher": expert.TEACHER, "deploy": DEPLOY,
           "tiny": tiny, "workers": workers,
           "fresh3": {"digest": digest, "tally": tally, "description": fresh3.describe(fresh_tasks),
                      "names": [task.name for task in fresh_tasks], "kinds": [task.kind for task in fresh_tasks],
                      "modulo": [task.modulo for task in fresh_tasks]}}
    print(f"FRESH-3: {len(fresh_tasks)} tasks, digest {digest[:16]}", flush=True)

    # ---- 2. the loop ---------------------------------------------------------------------------
    if from_loop:
        earlier = json.load(open(from_loop))
        if earlier["fresh3"]["digest"] != digest or earlier["components"] != COMPONENTS \
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
    ceiling = {name: round((training + sizes[name] * DEPLOY) / sizes[name]) for name in sets}
    budgets = {"heldB": {"C2": ceiling["heldB"], "C1": round((training + sizes["heldB"] * DEPLOY) / TASKS)},
               "fresh3": {"mid": round(math.sqrt(DEPLOY * ceiling["fresh3"])), "C2": ceiling["fresh3"]}}
    out["training_candidates"], out["set_sizes"], out["control_budgets"] = training, sizes, budgets
    print(f"training ceiling {training} candidates; control budgets {budgets}", flush=True)

    # ---- 3. evaluation runs ------------------------------------------------------------------------
    rows = {}

    def measure(label, spec, partitions):
        started = time.perf_counter()
        result = harness.run(spec, partition_names=partitions)
        records = {f"{p}/{r['name']}": {"matched": r["term"] is not None, "solved": bool(r["solved"]), "route": r["route"],
                                        "candidates": r["candidates"], "to_solution": r["to_solution"]}
                   for p, rs in result.items() for r in rs}
        rows[label] = {"budget": spec["budget"], "partitions": list(partitions), "counts": summary(result),
                       "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                                    for p, rs in result.items() for r in rs if r["solved"]},
                       "rejected": {f"{p}/{r['name']}": r["program"] for p, rs in result.items() for r in rs
                                    if r["term"] is not None and not r["solved"]},
                       "used": {f"{p}/{r['name']}": r["used"] for p, rs in result.items() for r in rs if r["solved"]},
                       "records": records, "spent": sum(r["candidates"] for r in records.values()),
                       "ceiling": spec["budget"] * len(records),
                       "seconds": round(time.perf_counter() - started)}
        print(f"{label:24s} budget {spec['budget']:>8} {rows[label]['counts']} | spent {rows[label]['spent']} of "
              f"{rows[label]['ceiling']} | {rows[label]['seconds']} s", flush=True)
        out["rows"] = rows
        json.dump(out, open(out_path, "w"), indent=1)

    both = held + ["fresh3"]
    gen0 = lambda budget: spec_of("gen0", budget, COMPONENTS)
    trained = lambda budget: spec_without(report, budget, "trained", set(), COMPONENTS)
    # the largest runs first: a failure for lack of memory then comes before any FRESH-3 outcome
    measure("gen0@C2:heldB", gen0(budgets["heldB"]["C2"]), held)
    measure("gen0@C1:heldB", gen0(budgets["heldB"]["C1"]), held)
    measure("trained@deploy", trained(DEPLOY), both)
    measure("gen0@deploy", gen0(DEPLOY), both)
    measure("trained@student:fresh3", trained(expert.STUDENT), ["fresh3"])
    measure("gen0@student:fresh3", gen0(expert.STUDENT), ["fresh3"])
    measure("gen0@mid:fresh3", gen0(budgets["fresh3"]["mid"]), ["fresh3"])
    measure("gen0@C2:fresh3", gen0(budgets["fresh3"]["C2"]), ["fresh3"])
    if os.path.exists(EARLIER):                      # secondary arm: the combination of Addendum 5b on the new tasks
        measure("combination@deploy:fresh3", spec_without(json.load(open(EARLIER)), DEPLOY, "combination", set(), COMPONENTS),
                ["fresh3"])

    # ---- 4. audit and tests ------------------------------------------------------------------------
    sound = Sound(fresh_tasks, fresh3)
    for row in rows.values():
        row["sound"] = sorted(key for key, value in row["programs"].items() if sound(key, value[0]))
        row["sound_counts"] = {p: sum(1 for key in row["sound"] if key.startswith(p + "/")) for p in row["partitions"]}
    first = report["timeline"][0]                     # generation 0 at the student budget, every exposed task
    last = {t["run"]: t for t in report["timeline"]}[report["student_last"]]
    student = {label: {"sound": {key for key, value in state["programs"].items() if sound(key, value[0])},
                       "verified": set(state["programs"])}
               for label, state in (("gen0", first), ("trained", last))}

    def solved(label, parts, measure_="sound"):
        keys = rows[label]["sound"] if measure_ == "sound" else rows[label]["programs"]
        return {key for key in keys if key.split("/", 1)[0] in parts}

    def within(keys, parts):
        return {key for key in keys if key.split("/", 1)[0] in parts}

    def arms_for(measure_):
        arms = {}
        for name, parts in sets.items():
            controls = {"equal": solved("gen0@deploy", parts, measure_)}
            for control in budgets[name]:
                controls[control] = solved(f"gen0@{control}:{name}", parts, measure_)
            low = solved("gen0@student:fresh3", parts, measure_) if name == "fresh3" \
                else within(student["gen0"][measure_], parts)
            controls["any"] = set().union(low, *controls.values())
            arms[name] = {"trained": solved("trained@deploy", parts, measure_), "controls": controls}
        return arms

    arms = arms_for("sound")
    comparisons = {}
    for name in sets:
        for control, reference in arms[name]["controls"].items():
            comparisons[f"{name}: trained@deploy vs gen0@{control}"] = paired(arms[name]["trained"], reference)
    comparisons["fresh3: trained@student vs gen0@student"] = paired(
        solved("trained@student:fresh3", ["fresh3"]), solved("gen0@student:fresh3", ["fresh3"]))
    comparisons["heldB: trained@student vs gen0@student"] = paired(
        within(student["trained"]["sound"], held), within(student["gen0"]["sound"], held))
    for control in ("C2", "any"):
        comparisons[f"pooled: trained@deploy vs gen0@{control}"] = paired(
            arms["heldB"]["trained"] | arms["fresh3"]["trained"],
            arms["heldB"]["controls"][control] | arms["fresh3"]["controls"][control])
    if "combination@deploy:fresh3" in rows:
        comparisons["fresh3: combination@deploy vs gen0@any"] = paired(
            solved("combination@deploy:fresh3", ["fresh3"]), arms["fresh3"]["controls"]["any"])
    out["comparisons"] = comparisons

    # the primary comparison and its breakdowns
    treated, control = arms["fresh3"]["trained"], arms["fresh3"]["controls"]["any"]
    task_of = {f"fresh3/{task.name}": task for task in fresh_tasks}
    out["kinds"] = {"fresh3: trained@deploy vs gen0@any": kinds_of(treated, control, rows["trained@deploy"], rows["gen0@C2:fresh3"]),
                    "heldB: trained@deploy vs gen0@any": kinds_of(arms["heldB"]["trained"], arms["heldB"]["controls"]["any"],
                                                                  rows["trained@deploy"], rows["gen0@C2:heldB"])}

    def stratum(test):
        chosen = {key for key, task in task_of.items() if test(task)}
        return dict(paired(treated & chosen, control & chosen), tasks=len(chosen))

    out["strata"] = {"with a divisibility-family stage": stratum(lambda task: task.modulo),
                     "without one": stratum(lambda task: not task.modulo),
                     "list outputs": stratum(lambda task: task.kind == "list"),
                     "integer and boolean outputs": stratum(lambda task: task.kind != "list")}
    family = lambda routine: "divisibility family" if routine in fresh3.MODULO else routine
    out["clusters"] = {
        "by first-stage routine": clustered(treated, control, {key: family(task.stages[0][0]) for key, task in task_of.items()}),
        "by second-stage routine": clustered(treated, control, {key: family(task.stages[1][0]) for key, task in task_of.items()})}
    routines = sorted({stage[0] for task in fresh_tasks for stage in task.stages})
    without = {}
    for routine in routines:
        kept = {key for key, task in task_of.items() if routine not in (task.stages[0][0], task.stages[1][0])}
        without[routine] = dict(paired(treated & kept, control & kept), tasks=len(kept))
    worst = max(without, key=lambda routine: (without[routine]["p_one_sided"], routine))
    out["leave_one_routine_out"] = {"largest_p": without[worst]["p_one_sided"], "routine": worst, "all": without}
    symbols = {}
    for key in sorted(treated - control):
        for symbol in rows["trained@deploy"]["used"].get(key) or ["(no learned symbol)"]:
            symbols[symbol] = symbols.get(symbol, 0) + 1
    out["trained_only_by_symbol"] = dict(sorted(symbols.items(), key=lambda item: -item[1]))
    strict = {label: {key for key, value in rows[label]["programs"].items()
                      if key.startswith("fresh3/") and sound.on_pool(key, value[0])}
              for label in rows if "fresh3" in rows[label]["partitions"]}
    out["fresh3_on_whole_pool"] = paired(strict["trained@deploy"], set().union(
        *(keys for label, keys in strict.items() if label.startswith("gen0@"))))

    # ---- the outcome class, on sound counts and, beside it, on verified counts -----------------------
    def flags_for(measure_):
        a = arms_for(measure_)
        t, c = a["fresh3"]["trained"], a["fresh3"]["controls"]["any"]
        primary = paired(t, c)
        outside = {key for key, task in task_of.items() if not task.modulo}
        rest = paired(t & outside, c & outside)
        reductions = {key for key, task in task_of.items() if task.kind != "list"}
        kinds = kinds_of(t, c, rows["trained@deploy"], rows["gen0@C2:fresh3"])["budget_bound"]
        held_b = paired(a["heldB"]["trained"], a["heldB"]["controls"]["any"])
        expected = {"gen0@C2:heldB", "gen0@C1:heldB", "trained@deploy", "gen0@deploy", "trained@student:fresh3",
                    "gen0@student:fresh3", "gen0@mid:fresh3", "gen0@C2:fresh3"}
        return {"missing": "" if expected <= set(rows) else f"runs missing: {sorted(expected - set(rows))}",
                "accepted": any(t_.get("accepted") for t_ in report["timeline"]),
                "lead": primary["trained"] > primary["control"],
                "significant": primary["p_one_sided"] < ALPHA,
                "outside_family": "none" if rest["trained"] <= rest["control"]
                else ("significant" if rest["p_one_sided"] < ALPHA else "not separated"),
                "budget_bound_lead": kinds["trained_only"] > kinds["control_only"],
                "reductions": len(t & reductions) >= len(c & reductions),
                "held_out_b": held_b["trained"] > held_b["control"]}

    out["accepted_cycles"] = sum(1 for t in report["timeline"] if t.get("accepted"))
    out["flags"] = flags_for("sound")
    out["outcome"] = outcome_class(out["flags"])
    out["outcome_on_verified_counts"] = outcome_class(flags_for("verified"))

    # ---- the predictions of Addendum 7 -----------------------------------------------------------------
    primary = comparisons["fresh3: trained@deploy vs gen0@any"]
    held_student = comparisons["heldB: trained@student vs gen0@student"]
    held_deploy = comparisons["heldB: trained@deploy vs gen0@equal"]
    equal = (comparisons["fresh3: trained@student vs gen0@student"], comparisons["fresh3: trained@deploy vs gen0@equal"])
    budget_bound = out["kinds"]["fresh3: trained@deploy vs gen0@any"]["budget_bound"]
    verdict = lambda ok: "PASS" if ok else "FAIL"
    out["predictions"] = {
        "Q1": verdict(out["accepted_cycles"] >= 3 and last["learn"] >= 138),
        "Q2": verdict(held_student["trained"] >= 28),
        "Q3": verdict(held_deploy["trained"] >= 40),
        "Q4": verdict(comparisons["heldB: trained@deploy vs gen0@C1"]["trained"] > comparisons["heldB: trained@deploy vs gen0@C1"]["control"]),
        "Q5": verdict(comparisons["heldB: trained@deploy vs gen0@any"]["trained"] > comparisons["heldB: trained@deploy vs gen0@any"]["control"]),
        "Q6": verdict(all(c["trained"] - c["control"] >= 6 for c in equal)),
        "Q7": verdict(primary["trained"] > primary["control"]),
        "Q8": verdict(primary["p_one_sided"] < ALPHA) if primary["trained"] > primary["control"] else "not scored (Q7 failed)",
        "Q9": verdict(out["strata"]["without one"]["trained"] > out["strata"]["without one"]["control"]),
        "Q10": verdict(budget_bound["trained_only"] > budget_bound["control_only"])}
    json.dump(out, open(out_path, "w"), indent=1)

    print()
    for label, row in rows.items():
        print(f"{label:26s} verified {row['counts']} sound {row['sound_counts']}")
    for label, c in comparisons.items():
        print(f"{label:44s} sound {c['trained']} against {c['control']}; only trained {c['trained_only']}, "
              f"only control {c['control_only']}; one-sided p {c['p_one_sided']}")
    for label, k in out["kinds"].items():
        print(f"{label:44s} only trained {k['trained_only']}; only control {k['control_only']}; budget-bound {k['budget_bound']}")
    print("strata:", json.dumps(out["strata"]))
    print("clusters:", json.dumps(out["clusters"]))
    print("leave one routine out: largest p", out["leave_one_routine_out"]["largest_p"], "without", worst)
    print("trained-only tasks by learned symbol:", json.dumps(out["trained_only_by_symbol"]))
    print("FRESH-3 on the whole input pool:", json.dumps(out["fresh3_on_whole_pool"]))
    print("loop: verdicts read", report.get("verdicts_read"), "| seconds in compression", report.get("propose_seconds"))
    print("predictions:", json.dumps(out["predictions"]))
    print("flags:", json.dumps(out["flags"]))
    print("OUTCOME:", out["outcome"])
    print("on verified counts:", out["outcome_on_verified_counts"])
    harness.close()


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 4, "--tiny" in sys.argv,
         sys.argv[sys.argv.index("--from-loop") + 1] if "--from-loop" in sys.argv else None)
