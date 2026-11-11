"""The registered test of the deepening loop (PREDICTIONS.md, Addendum 8), start to finish.

One process, no step between its parts that a person decides:

  1. fork the workers; generate FRESH-4 in the driver (``fresh4.py``) and check that it is the
     registered set; no loop step runs it. FRESH-3 (run once, by Addendum 7, and used as a
     development set since) is generated for descriptive rows;
  2. ``deepen.run``, configuration B, machinery S + C + f + R: the state called *new*;
  3. evaluation. Three vocabularies with the same machinery: *new*; *old*, the final vocabulary
     of the Addendum 7 loop (``results/replication.json``); and generation 0, no learned symbol.
        T_new, T_old   the training ceilings of the two loops (every run they made, at its ceiling)
        on FRESH-4 (N tasks):   C2 = (T + N x deployment budget) / N   for each loop, and
                                STRICT = 524,267, the whole-budget rung of Addendum 7
        on held-out B:          413,254 and 1,126,452, the rungs of Addendum 7, and
                                C1new = (T_new + 124 x deployment budget) / 338 when it fits in memory
     Generation 0 runs at the student budget, the deployment budget and every rung; *new* and
     *old* at the student and the deployment budget;
  4. after the loop and outside it, for criterion R2: generation 0 on each later cycle's unsolved
     learning tasks at that cycle's teacher budget, and the final vocabulary without the
     first-cycle symbols and the symbols built on them;
  5. the audit (sound counts); the primary comparison on FRESH-4, *new* at the deployment budget
     against everything generation 0 solves at any budget run; the breakdowns; the outcome class
     by the registered rule; the predictions scored.

    python confirm.py <out.json> [workers] [--tiny] [--resume]

``--tiny`` is a smoke test at toy budgets. It never generates a FRESH-4 candidate: FRESH-3 tasks
stand in for both generated sets. ``--resume`` continues an interrupted run from its own output
file: the loop report is taken if the loop had finished (otherwise the loop runs again from the
start; it is deterministic) and every evaluation row already there is kept if it was made by
the same vocabulary at the same budget on the same tasks. Results do not depend on the worker
count or on where a run was interrupted.
"""
from __future__ import annotations

import json
import os
import sys
import time

import deepen
from expert_ablate import spec_without
from hybrid import ALL, Harness, summary
from loop import CONFIGS
from replicate import clustered, kinds_of, paired
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

COMPONENTS = "SCfR"
DEPLOY = 100_000
TASKS = 338                      # the exposed tasks
STEPS = 2000
ALPHA = 0.05
MIN_EVIDENCE = 20                # fresh in-domain inputs a sound verdict on a generated task needs
REGISTERED_DIGEST = "d54c6593098b4540"          # the first 16 hex digits; Addendum 8 gives all 64
STRICT = 524_267                 # generation 0's whole-budget rung on FRESH-3 in Addendum 7
HELD_RUNGS = {"C1old": 413_254, "C2old": 1_126_452}
MEMORY_LIMIT = 1_700_000         # candidates per task that four workers can hold on this machine
EARLIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "replication.json")
EARLIER_FAMILY = "slice-k-n"     # with the divisibility family: the routines the old symbols encode


class Sound:
    """Sound verdicts: ``audit_all`` for the exposed partitions; for a generated task its own
    generating function on fresh inputs (at least MIN_EVIDENCE of them inside its domain)."""

    def __init__(self, generated: dict):
        import audit_all
        import fresh3
        import oracles
        self.auditor = audit_all.Auditor()
        self.oracles, self.kind, self.pool_of = oracles, fresh3._kind, fresh3.input_pool
        self.tasks = {f"{partition}/{task.name}": task for partition, tasks in generated.items() for task in tasks}
        self.inputs, self.cache, self.pool, self.pool_cache = {}, {}, None, {}

    def _agrees(self, task, text, inputs):
        """(agrees on every in-domain input, number of in-domain inputs)."""
        term, checked = parse(text), 0
        for xs in inputs:
            want = task.reference(list(xs))
            if want is None or self.kind(want) is None:              # outside the domain the task was made on
                continue
            checked += 1
            got = evaluate(term, (list(xs),), step_budget=STEPS)
            if not got.ok or got.value != want or type(got.value) is not type(want):
                return False, checked
        return True, checked

    def verdict(self, key: str, text: str):
        """(sound, evidence): evidence is None for an exposed task."""
        task = self.tasks.get(key)
        if task is None:
            return bool(self.auditor.sound(key, text)), None
        if (key, text) not in self.cache:
            if key not in self.inputs:
                self.inputs[key] = self.oracles.fresh_inputs(key, task, [task.reference])
            agrees, checked = self._agrees(task, text, self.inputs[key])
            self.cache[(key, text)] = (agrees and checked >= MIN_EVIDENCE, checked)
        return self.cache[(key, text)]

    def on_pool(self, key: str, text: str) -> bool:
        """Generated tasks only, a stricter secondary reading: the program agrees with the
        generating function on every input of the FRESH input pool the function is defined on."""
        if (key, text) not in self.pool_cache:
            if self.pool is None:
                self.pool = list(self.pool_of())
            self.pool_cache[(key, text)] = self._agrees(self.tasks[key], text, self.pool)[0]
        return self.pool_cache[(key, text)]


def descendants(library: dict, roots: set) -> set:
    """``roots`` and every symbol whose definition names one of them, transitively."""
    found, grew = set(roots), True
    while grew:
        grew = False
        for name, entry in library.items():
            if name not in found and any(f"{other} " in entry["definition"] + " " or f"({other} " in entry["definition"]
                                         or f" {other})" in entry["definition"] for other in found):
                found.add(name)
                grew = True
    return found


def outcome_class(flags: dict) -> str:
    """The registered reading (Addendum 8), from values computed by ``main``."""
    if flags["missing"]:
        return "no class: " + flags["missing"]
    if not flags["accepted"]:
        return "not confirmed: the loop accepted no symbol, so the new state is generation 0"
    if not flags["lead"]:
        return "not confirmed: no lead on FRESH-4 over what generation 0 solves at any budget run"
    if not flags["significant"]:
        return "not established: a lead on FRESH-4 that the sign test does not separate from chance"
    endings = [{"none": "only where a routine of the earlier symbols is present",
                "not separated": "outside the routines of the earlier symbols not separated from chance",
                "significant": "also outside the routines of the earlier symbols"}[flags["outside_earlier"]],
               {"none": "no more than the earlier loop",
                "not separated": "not separated from the earlier loop",
                "significant": "and more than the earlier loop"}[flags["over_old"]],
               "with reach beyond the budget" if flags["budget_bound_lead"]
               else "as a different first match, not reach beyond the budget",
               {"none": "not on the tasks no dream of the loop computed",
                "not separated": "on the tasks no dream of the loop computed not separated from chance",
                "significant": "also on the tasks no dream of the loop computed"}[flags["undreamt"]]]
    return "confirmed on FRESH-4 against everything generation 0 solves at any budget run; " + "; ".join(endings)


def graded(comparison: dict) -> str:
    if comparison["trained"] <= comparison["control"]:
        return "none"
    return "significant" if comparison["p_one_sided"] < ALPHA else "not separated"


def main(out_path: str, workers: int, tiny: bool, resume: bool) -> None:
    global DEPLOY, STRICT, HELD_RUNGS, MIN_EVIDENCE
    if tiny:
        deepen.STUDENT, deepen.TEACHER, deepen.CAP = 300, 1500, 5000
        deepen.DREAMS_GATE, deepen.DREAMS_CORPUS, deepen.MAX_BATCHES = 20, 40, 4
        DEPLOY, STRICT, HELD_RUNGS = 1500, 2500, {"C1old": 2000, "C2old": 3000}
    learn = CONFIGS["B"]
    held = [p for p in ALL if p not in learn]
    harness = Harness(workers, ALL)
    import fresh3                                   # loads the FRESH partitions: after the fork
    import fresh4
    third = fresh3.make()
    if not fresh3.digest(third).startswith("4da13e671411da8c"):
        raise SystemExit("fresh3.make() no longer gives the registered FRESH-3 set")
    tally = {}
    if tiny:                                        # FRESH-3 tasks stand in: no FRESH-4 candidate is made
        fourth, third = third[:60], third[60:100]
    else:
        fourth = fresh4.make(statistics=tally)
    digest = fresh3.digest(fourth)
    if not tiny and (len(fourth) != fresh4.COUNT or not digest.startswith(REGISTERED_DIGEST)):
        raise SystemExit(f"this is not the registered FRESH-4 set: {len(fourth)} tasks, digest {digest}")
    harness.add_partition("fresh4", fourth, [task.public_view() for task in fourth])
    harness.add_partition("fresh3", third, [task.public_view() for task in third])
    protocol = {"components": COMPONENTS, "student": deepen.STUDENT, "teacher": deepen.TEACHER, "cap": deepen.CAP,
                "batch": deepen.BATCH, "rejects": deepen.REJECTS, "max_batches": deepen.MAX_BATCHES,
                "max_cycles": deepen.MAX_CYCLES, "dreams": [deepen.DREAMS_GATE, deepen.DREAMS_CORPUS],
                "deploy": DEPLOY, "tiny": tiny, "fresh4_digest": digest}
    previous = json.load(open(out_path)) if resume and os.path.exists(out_path) else {}
    if previous and previous.get("protocol") != protocol:
        raise SystemExit("the file to resume from is not of this protocol")
    out = {"protocol": protocol, "workers": workers, "resumed": bool(previous) or None,
           "fresh4": {"digest": digest, "tally": tally, "description": fresh3.describe(fourth),
                      "names": [task.name for task in fourth], "kinds": [task.kind for task in fourth],
                      "modulo": [task.modulo for task in fourth],
                      "stages": [[task.stages[0][0], task.stages[1][0]] for task in fourth]}}
    print(f"FRESH-4: {len(fourth)} tasks, digest {digest[:16]}", flush=True)

    def save():
        json.dump(out, open(out_path, "w"), indent=1)

    # ---- 2. the loop ---------------------------------------------------------------------------
    if previous.get("loop", {}).get("finished"):
        report = previous["loop"]
        out["loop_taken_from_interrupted_run"] = True
    else:
        report = deepen.run(harness, learn, components=COMPONENTS)
    out["loop"] = report
    save()
    earlier = json.load(open(EARLIER))
    libraries = {"gen0": {}, "new": report["library"], "old": earlier["loop"]["library"]}
    training = {"new": report["training_ceiling"], "old": earlier["training_candidates"]}
    sets = {"heldB": held, "fresh4": ["fresh4"], "fresh3": ["fresh3"]}
    sizes = {name: sum(len(harness.public[p]) for p in parts) for name, parts in sets.items()}
    c2 = lambda which: round((training[which] + sizes["fresh4"] * DEPLOY) / sizes["fresh4"])
    budgets = {"fresh4": {"C2old": c2("old"), "C2new": c2("new"), "strict": STRICT}, "heldB": dict(HELD_RUNGS)}
    c1new = round((training["new"] + sizes["heldB"] * DEPLOY) / TASKS)
    if c1new <= MEMORY_LIMIT:
        budgets["heldB"]["C1new"] = c1new
    out["training_candidates"], out["set_sizes"], out["control_budgets"] = training, sizes, budgets
    out["c1new_on_held_out_b"] = {"budget": c1new, "run": c1new <= MEMORY_LIMIT}
    print(f"training ceilings {training}; control budgets {budgets}", flush=True)

    # ---- 3. evaluation runs ------------------------------------------------------------------------
    rows = dict(previous.get("rows") or {})
    out["rows"] = rows

    def measure(label, state, budget, partitions, only=None):
        fingerprint = {"state": state, "budget": budget, "partitions": list(partitions),
                       "library": sorted(libraries[state]) if isinstance(state, str) else sorted(state[1]),
                       "only": sorted(only) if only is not None else None}
        if label in rows and rows[label].get("fingerprint") == fingerprint:
            print(f"{label:26s} kept from the interrupted run", flush=True)
            return
        if isinstance(state, str):
            spec = spec_without({"library": libraries[state]}, budget, state, set(), COMPONENTS)
        else:                                       # (name, library): an ablated vocabulary
            spec = spec_without({"library": state[1]}, budget, state[0], set(), COMPONENTS)
        started = time.perf_counter()
        result = harness.run(spec, partition_names=partitions, only=only)
        records = {f"{p}/{r['name']}": {"matched": r["term"] is not None, "solved": bool(r["solved"]), "route": r["route"],
                                        "candidates": r["candidates"], "to_solution": r["to_solution"]}
                   for p, rs in result.items() for r in rs}
        rows[label] = {"fingerprint": fingerprint, "budget": budget, "partitions": list(partitions),
                       "counts": summary(result),
                       "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                                    for p, rs in result.items() for r in rs if r["solved"]},
                       "rejected": {f"{p}/{r['name']}": r["program"] for p, rs in result.items() for r in rs
                                    if r["term"] is not None and not r["solved"]},
                       "used": {f"{p}/{r['name']}": r["used"] for p, rs in result.items() for r in rs if r["solved"]},
                       "records": records, "spent": sum(r["candidates"] for r in records.values()),
                       "ceiling": budget * len(records), "seconds": round(time.perf_counter() - started)}
        print(f"{label:26s} budget {budget:>8} {rows[label]['counts']} | spent {rows[label]['spent']} of "
              f"{rows[label]['ceiling']} | {rows[label]['seconds']} s", flush=True)
        save()

    student = deepen.STUDENT
    # the largest runs first: a failure for lack of memory then comes before any FRESH-4 outcome
    for rung in sorted(budgets["heldB"], key=lambda r: -budgets["heldB"][r]):
        measure(f"gen0@{rung}:heldB", "gen0", budgets["heldB"][rung], held)
    for rung in sorted(budgets["fresh4"], key=lambda r: -budgets["fresh4"][r]):
        measure(f"gen0@{rung}:fresh4", "gen0", budgets["fresh4"][rung], ["fresh4"])
    for name, parts in sets.items():
        for state in ("gen0", "new", "old"):
            if name == "fresh3" and state != "new":
                continue                             # FRESH-3: generation 0 and the old state are in the earlier report
            measure(f"{state}@deploy:{name}", state, DEPLOY, parts)
            measure(f"{state}@student:{name}", state, student, parts)
    # criterion R2, outside the loop: what the later teachers found that generation 0 does not find
    # at the same budget on the same tasks, and what the final student loses without the first cycle
    by_run = {t["run"]: t for t in report["timeline"]}
    for cycle in report["cycles"][1:]:
        measure(f"gen0@teacher{cycle['cycle']}:learn", "gen0", cycle["teacher_share"], list(learn),
                only=set(cycle["unsolved"]))
    first_cycle = set(report["cycles"][0]["library"]) if report["cycles"] else set()
    dropped = descendants(report["library"], first_cycle) if first_cycle else set()
    ablated = {name: entry for name, entry in report["library"].items() if name not in dropped}
    if dropped:
        measure("new-without-cycle1@student", ("without-cycle1", ablated), student, list(learn) + held)

    # ---- 4. audit and tests ------------------------------------------------------------------------
    sound = Sound({"fresh4": fourth, "fresh3": third})
    for label, row in rows.items():
        verdicts = {key: sound.verdict(key, value[0]) for key, value in row["programs"].items()}
        row["sound"] = sorted(key for key, (ok, _) in verdicts.items() if ok)
        row["thin_evidence"] = sorted(key for key, (ok, seen) in verdicts.items()
                                      if seen is not None and seen < MIN_EVIDENCE)
        row["sound_counts"] = {p: sum(1 for key in row["sound"] if key.startswith(p + "/")) for p in row["partitions"]}

    def solved(label, measure_="sound"):
        return set(rows[label]["sound"] if measure_ == "sound" else rows[label]["programs"])

    def arms_for(measure_):
        arms = {}
        for name in ("heldB", "fresh4"):
            controls = {"student": solved(f"gen0@student:{name}", measure_),
                        "equal": solved(f"gen0@deploy:{name}", measure_)}
            for rung in budgets[name]:
                controls[rung] = solved(f"gen0@{rung}:{name}", measure_)
            controls["any"] = set().union(*controls.values())
            arms[name] = {"controls": controls,
                          **{f"{state}@{at}": solved(f"{state}@{at}:{name}", measure_)
                             for state in ("new", "old") for at in ("deploy", "student")}}
        return arms

    arms = arms_for("sound")
    comparisons = {}
    for name in ("heldB", "fresh4"):
        for state in ("new", "old"):
            for control, reference in arms[name]["controls"].items():
                comparisons[f"{name}: {state}@deploy vs gen0@{control}"] = paired(arms[name][f"{state}@deploy"], reference)
            comparisons[f"{name}: {state}@student vs gen0@student"] = paired(
                arms[name][f"{state}@student"], arms[name]["controls"]["student"])
            comparisons[f"{name}: {state}@student vs gen0@any"] = paired(
                arms[name][f"{state}@student"], arms[name]["controls"]["any"])
        for at in ("deploy", "student"):
            comparisons[f"{name}: new@{at} vs old@{at}"] = paired(arms[name][f"new@{at}"], arms[name][f"old@{at}"])
    old_own = set().union(*(arms["fresh4"]["controls"][c] for c in ("student", "equal", "C2old")))
    comparisons["fresh4: old@deploy vs gen0 up to its own C2"] = paired(arms["fresh4"]["old@deploy"], old_own)
    # FRESH-3, a development set: the new state against the earlier report's rows (descriptive)
    earlier_any = set().union(*(set(row["sound"]) for label, row in earlier["rows"].items()
                                if label.startswith("gen0@") and "fresh3" in row["partitions"]))
    earlier_any = {key for key in earlier_any if key.startswith("fresh3/")}
    if not tiny:
        comparisons["fresh3 (development set): new@deploy vs gen0@any of Addendum 7"] = paired(
            solved("new@deploy:fresh3"), earlier_any)
        comparisons["fresh3 (development set): new@deploy vs old@deploy of Addendum 7"] = paired(
            solved("new@deploy:fresh3"),
            {key for key in earlier["rows"]["trained@deploy"]["sound"] if key.startswith("fresh3/")})
    out["comparisons"] = comparisons

    # the primary comparison and its breakdowns
    treated, control = arms["fresh4"]["new@deploy"], arms["fresh4"]["controls"]["any"]
    task_of = {f"fresh4/{task.name}": task for task in fourth}
    top_rung = max(budgets["fresh4"], key=lambda r: budgets["fresh4"][r])
    out["kinds"] = {"fresh4: new@deploy vs gen0@any": kinds_of(treated, control, rows["new@deploy:fresh4"],
                                                                rows[f"gen0@{top_rung}:fresh4"])}
    earlier_routine = lambda task: task.modulo or EARLIER_FAMILY in (task.stages[0][0], task.stages[1][0])
    dream_terms = {text for cycle in report["cycles"] for group in cycle["dream_programs"].values()
                   for text, _, _ in group}
    parsed = [parse(text) for text in sorted(dream_terms)]

    def dreamt(task) -> bool:
        examples = list(task.examples) + list(task.hidden)
        for term in parsed:
            for inputs, want in examples:
                got = evaluate(term, tuple(inputs), step_budget=STEPS)
                if not got.ok or got.value != want or type(got.value) is not type(want):
                    break
            else:
                return True
        return False

    dreamt_keys = {key for key, task in task_of.items() if dreamt(task)}
    out["dreamt"] = {"dream_programs": len(parsed), "fresh4_tasks_a_dream_computes": len(dreamt_keys)}

    def stratum(test, t=treated, c=control):
        chosen = {key for key, task in task_of.items() if test(key, task)}
        return dict(paired(t & chosen, c & chosen), tasks=len(chosen))

    out["strata"] = {
        "with a routine of the earlier symbols (slice-k-n or the divisibility family)": stratum(lambda k, t: earlier_routine(t)),
        "without one": stratum(lambda k, t: not earlier_routine(t)),
        "list outputs": stratum(lambda k, t: t.kind == "list"),
        "integer and boolean outputs": stratum(lambda k, t: t.kind != "list"),
        "a dream of the loop computes the task": stratum(lambda k, t: k in dreamt_keys),
        "no dream computes it": stratum(lambda k, t: k not in dreamt_keys)}
    out["strata_new_vs_old"] = {
        "without a routine of the earlier symbols": stratum(lambda k, t: not earlier_routine(t), treated,
                                                           arms["fresh4"]["old@deploy"]),
        "no dream computes it": stratum(lambda k, t: k not in dreamt_keys, treated, arms["fresh4"]["old@deploy"])}
    family = lambda routine: "divisibility family" if routine in fresh3.MODULO else routine
    out["clusters"] = {
        "by first-stage routine": clustered(treated, control, {key: family(task.stages[0][0]) for key, task in task_of.items()}),
        "by second-stage routine": clustered(treated, control, {key: family(task.stages[1][0]) for key, task in task_of.items()})}
    routines = sorted({stage[0] for task in fourth for stage in task.stages})
    without = {}
    for routine in routines:
        kept = {key for key, task in task_of.items() if routine not in (task.stages[0][0], task.stages[1][0])}
        without[routine] = dict(paired(treated & kept, control & kept), tasks=len(kept))
    worst = max(without, key=lambda routine: (without[routine]["p_one_sided"], routine))
    out["leave_one_routine_out"] = {"largest_p": without[worst]["p_one_sided"], "routine": worst, "all": without}
    by_routine = {}
    for key, task in task_of.items():
        for routine in {task.stages[0][0], task.stages[1][0]}:
            entry = by_routine.setdefault(routine, {"tasks": 0, "new": 0, "old": 0, "gen0_any": 0})
            entry["tasks"] += 1
            entry["new"] += key in treated
            entry["old"] += key in arms["fresh4"]["old@deploy"]
            entry["gen0_any"] += key in control
    out["by_routine"] = dict(sorted(by_routine.items()))
    symbols, depth = {}, {name: entry["depth"] for name, entry in report["library"].items()}
    deep_use = 0
    for key in sorted(treated - control):
        used = rows["new@deploy:fresh4"]["used"].get(key) or ["(no learned symbol)"]
        deep_use += any(depth.get(symbol, 1) >= 2 for symbol in used)
        for symbol in used:
            symbols[symbol] = symbols.get(symbol, 0) + 1
    out["new_only_by_symbol"] = dict(sorted(symbols.items(), key=lambda item: -item[1]))
    out["new_only_with_a_symbol_built_on_a_symbol"] = deep_use
    strict = {label: {key for key, value in rows[label]["programs"].items()
                      if key.startswith("fresh4/") and sound.on_pool(key, value[0])}
              for label in rows if rows[label]["partitions"] == ["fresh4"]}
    out["fresh4_on_whole_pool"] = paired(strict["new@deploy:fresh4"], set().union(
        *(keys for label, keys in strict.items() if label.startswith("gen0@"))))
    out["thin_evidence"] = {label: len(row["thin_evidence"]) for label, row in rows.items() if row["thin_evidence"]}

    # ---- the four criteria, on held-out B and the learning set (descriptive) ---------------------------
    reports = [t for t in report["timeline"] if t["label"].startswith("report")]
    trajectory = [{"label": t["label"], "verified": t["held_out"],
                   "sound": sum(1 for key, value in t["programs"].items() if sound.verdict(key, value[0])[0])}
                  for t in reports]
    rises = lambda values: any(a < b < c for a, b, c in zip(values, values[1:], values[2:]))
    needed = {}
    for cycle in report["cycles"][1:]:
        label = f"gen0@teacher{cycle['cycle']}:learn"
        with_symbols = set(by_run[cycle["teacher_run"]]["solved"])
        needed[str(cycle["cycle"])] = {"teacher_solved": len(with_symbols),
                                       "not_by_generation_0_at_that_budget": len(with_symbols - set(rows[label]["programs"]))}
    lost = None
    if dropped:
        final = set(by_run[report["student_last"]]["solved"])
        after_first = set(by_run[report["cycles"][0]["student_run"]]["solved"])
        start = set(by_run[report["student_first"]]["solved"])
        without_first = {key for key in rows["new-without-cycle1@student"]["programs"] if key.split("/", 1)[0] in learn}
        lost = {"dropped_symbols": sorted(dropped), "final_learning_solves": len(final),
                "lost_without_them": len(final - without_first),
                "of_those_first_solved_after_cycle_1": len((final - without_first) - after_first - start)}
    held_any = arms["heldB"]["controls"]["any"]
    out["criteria"] = {
        "R1_held_out_B_by_cycle": trajectory,
        "R1": {"verified": rises([t["verified"] for t in trajectory]), "sound": rises([t["sound"] for t in trajectory])},
        "R2_later_teacher_solves_that_need_symbols": needed,
        "R2_without_first_cycle": lost,
        "R2": any(v["not_by_generation_0_at_that_budget"] > 0 for v in needed.values())
        and bool(lost and lost["of_those_first_solved_after_cycle_1"] > 0),
        "R3_new_student_vs_gen0_any_on_held_out_B": paired(arms["heldB"]["new@student"], held_any),
        "R3": len(arms["heldB"]["new@student"]) > len(held_any),
        "R3_covers_the_cumulative_budget": c1new <= max(budgets["heldB"].values()),
        "R4": True}

    # ---- the outcome class, on sound counts and, beside it, on verified counts -----------------------
    def flags_for(measure_):
        a = arms_for(measure_)
        t, c, o = a["fresh4"]["new@deploy"], a["fresh4"]["controls"]["any"], a["fresh4"]["old@deploy"]
        primary = paired(t, c)
        outside = {key for key, task in task_of.items() if not earlier_routine(task)}
        undreamt = set(task_of) - dreamt_keys
        kinds = kinds_of(t, c, rows["new@deploy:fresh4"], rows[f"gen0@{top_rung}:fresh4"])["budget_bound"]
        expected = {f"gen0@{rung}:fresh4" for rung in budgets["fresh4"]} | {
            f"{state}@{at}:fresh4" for state in ("gen0", "new", "old") for at in ("deploy", "student")}
        return {"missing": "" if expected <= set(rows) else f"runs missing: {sorted(expected - set(rows))}",
                "accepted": bool(report["library"]),
                "lead": primary["trained"] > primary["control"],
                "significant": primary["p_one_sided"] < ALPHA,
                "outside_earlier": graded(paired(t & outside, c & outside)),
                "over_old": graded(paired(t, o)),
                "budget_bound_lead": kinds["trained_only"] > kinds["control_only"],
                "undreamt": graded(paired(t & undreamt, c & undreamt))}

    out["accepted_symbols"] = len(report["library"])
    out["flags"] = flags_for("sound")
    out["outcome"] = outcome_class(out["flags"])
    out["outcome_on_verified_counts"] = outcome_class(flags_for("verified"))
    out["predictions"] = predictions(out, report, comparisons, trajectory)
    save()

    print()
    for label, row in rows.items():
        print(f"{label:28s} verified {row['counts']} sound {row['sound_counts']}")
    for label, c in comparisons.items():
        print(f"{label:62s} sound {c['trained']} against {c['control']}; only first {c['trained_only']}, "
              f"only second {c['control_only']}; one-sided p {c['p_one_sided']}")
    for label, k in out["kinds"].items():
        print(f"{label:44s} only new {k['trained_only']}; only control {k['control_only']}; budget-bound {k['budget_bound']}")
    print("strata:", json.dumps(out["strata"]))
    print("strata, new against old:", json.dumps(out["strata_new_vs_old"]))
    print("clusters:", json.dumps(out["clusters"]))
    print("leave one routine out: largest p", out["leave_one_routine_out"]["largest_p"], "without", worst)
    print("by routine:", json.dumps(out["by_routine"]))
    print("new-only tasks by learned symbol:", json.dumps(out["new_only_by_symbol"]),
          "| with a symbol built on a symbol:", deep_use)
    print("dreamt:", json.dumps(out["dreamt"]), "| thin evidence:", json.dumps(out["thin_evidence"]))
    print("FRESH-4 on the whole input pool:", json.dumps(out["fresh4_on_whole_pool"]))
    print("criteria:", json.dumps(out["criteria"]))
    print("loop: verdicts read", report.get("verdicts_read"), "| seconds in compression and dreaming",
          round(sum(report.get("propose_seconds", [])), 1), "| training ceiling", report["training_ceiling"],
          "spent", report["training_spent"])
    print("predictions:", json.dumps(out["predictions"]))
    print("flags:", json.dumps(out["flags"]))
    print("OUTCOME:", out["outcome"])
    print("on verified counts:", out["outcome_on_verified_counts"])
    harness.close()


def predictions(out, report, comparisons, trajectory) -> dict:
    """The predictions of Addendum 8, scored mechanically (the thresholds are the registered ones)."""
    verdict = lambda ok: "PASS" if ok else "FAIL"
    by_run = {t["run"]: t for t in report["timeline"]}
    last = by_run[report["student_last"]]
    primary = comparisons["fresh4: new@deploy vs gen0@any"]
    over_old = comparisons["fresh4: new@deploy vs old@deploy"]
    old_any = comparisons["fresh4: old@deploy vs gen0@any"]
    student_any = comparisons["fresh4: new@student vs gen0@any"]
    outside = out["strata"]["without one"]
    undreamt = out["strata"]["no dream computes it"]
    criteria = out["criteria"]
    accepted_cycles = sum(1 for cycle in report["cycles"] if cycle["accepted_batches"])
    return {
        "P1": verdict(accepted_cycles >= THRESHOLDS["P1_cycles"] and last["learn"] >= THRESHOLDS["P1_learn"]),
        "P2": verdict(trajectory[-1]["sound"] >= THRESHOLDS["P2_held_sound"]),
        "P3": verdict(criteria["R2"]),
        "P4": verdict(primary["trained"] > primary["control"]),
        "P5": verdict(primary["p_one_sided"] < ALPHA) if primary["trained"] > primary["control"]
        else "not scored (P4 failed)",
        "P6": verdict(over_old["trained"] > over_old["control"] and over_old["p_one_sided"] < ALPHA),
        "P7": verdict(outside["trained"] > outside["control"] and outside["p_one_sided"] < ALPHA),
        "P8": verdict(student_any["trained"] > student_any["control"]),
        "P9": verdict(old_any["trained"] > old_any["control"] and old_any["p_one_sided"] < ALPHA),
        "P10": verdict(undreamt["trained"] > undreamt["control"] and undreamt["p_one_sided"] < ALPHA),
        "P11": verdict(criteria["R3"]),
        "P12": verdict(primary["trained"] >= THRESHOLDS["P12_new_sound"])}


THRESHOLDS = {"P1_cycles": 3, "P1_learn": 150, "P2_held_sound": 38, "P12_new_sound": 300}


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 4, "--tiny" in sys.argv,
         "--resume" in sys.argv)
