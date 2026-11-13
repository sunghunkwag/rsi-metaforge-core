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
                                TOP = 1,126,452, the largest budget of Addendum 7
        on held-out B:          every budget generation 0 has been run at there (181,775; 251,479;
                                413,254; 569,881; 1,126,452) and
                                C1new = (T_new + 124 x deployment budget) / 338 when it fits in memory
     Generation 0 runs at the student budget, the deployment budget and every rung; *new* and
     *old* at the student and the deployment budget;
  4. after the loop and outside it, for criterion R2: generation 0 on each later cycle's unsolved
     learning tasks at that cycle's teacher budget, and the final vocabulary without the
     first-cycle symbols and the symbols built on them;
  5. the audit (sound counts); the primary comparison on FRESH-4, *new* at the deployment budget
     against everything generation 0 solves at any budget run; the breakdowns; the outcome class
     by the registered rule; the predictions scored.

    python confirm.py <out.json> [workers] [--tiny] [--resume] [--rehearse <loop report.json>]

``--tiny`` is a smoke test at toy budgets. It never generates a FRESH-4 candidate: FRESH-3 tasks
stand in for both generated sets. ``--rehearse`` is a second smoke test: it takes a finished
development report of the loop instead of running the loop, evaluates at small budgets on the same
stand-in tasks and so walks every analysis path with a real vocabulary; it decides nothing. ``--resume`` continues an interrupted run from its own output
file: the loop report is taken if the loop had finished (otherwise the loop runs again from the
start; it is deterministic) and every evaluation row already there is kept if it was made by
the same vocabulary at the same budget on the same tasks. Results do not depend on the worker
count or on where a run was interrupted.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time

import deepen
from expert_ablate import spec_without
from hybrid import ALL, Harness, summary
from loop import CONFIGS
from replicate import clustered, kinds_of, paired
from rsi5 import partitions
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

COMPONENTS = "SCfR"
DEPLOY = 100_000
TASKS = 338                      # the exposed tasks
STEPS = 2000
ALPHA = 0.05
MIN_EVIDENCE = 20                # fresh in-domain inputs a sound verdict on a generated task needs
MIN_DISCORDANT = 10              # tasks only one arm solves below which a stratum is not read
EXPECTED_LOOP = {"library_digest": "7b8e1ef31a09a95e50643e64530318f68014abd61923a367bfd850837cc0c93e",
                 "training_ceiling": 189_239_903}        # the last development run of the frozen loop
REGISTERED_DIGEST = "6159d55f97e57301"          # the first 16 hex digits; Addendum 8 gives all 64
TOP = 1_126_452                  # the largest budget generation 0 was run at in Addendum 7
HELD_RUNGS = {"r181775": 181_775, "r251479": 251_479, "r413254": 413_254, "r569881": 569_881, "top": TOP}
#                                  every budget above 10^5 generation 0 has been run at on held-out B
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
        """(sound, evidence): evidence is the number of fresh in-domain inputs a program of a
        generated task agreed on when it agreed on all of them, None otherwise (an exposed task, or
        a program that disagreed somewhere)."""
        task = self.tasks.get(key)
        if task is None:
            return bool(self.auditor.sound(key, text)), None
        if (key, text) not in self.cache:
            if key not in self.inputs:
                self.inputs[key] = self.oracles.fresh_inputs(key, task, [task.reference])
            agrees, checked = self._agrees(task, text, self.inputs[key])
            self.cache[(key, text)] = (agrees and checked >= MIN_EVIDENCE, checked if agrees else None)
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
            if name not in found and set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", entry["definition"])) & found:
                found.add(name)
                grew = True
    return found


def outcome_class(flags: dict) -> str:
    """The registered reading (Addendum 8), from values computed by ``main``."""
    if flags["missing"]:
        return "no class: " + flags["missing"]
    scope = flags["scope"] + ": "
    if not flags["accepted"]:
        return scope + "not confirmed: the loop accepted no symbol, so the new state is generation 0"
    if not flags["lead"]:
        return scope + "not confirmed: no lead on FRESH-4 over what generation 0 solves at any budget run"
    if not flags["significant"]:
        return scope + "not established: a lead on FRESH-4 that the sign test does not separate from chance"
    endings = [
        worded(flags["outside_earlier"], {
            "topic": "outside the routines of the earlier symbols",
            "none": "only where a routine of the earlier symbols is present",
            "not separated": "outside the routines of the earlier symbols not separated from chance",
            "significant": "also outside the routines of the earlier symbols"}),
        worded(flags["over_old"], {
            "topic": "against the earlier loop's vocabulary at the same deployment budget",
            "none": "no more than the earlier loop's vocabulary at the same deployment budget",
            "not separated": "not separated from the earlier loop's vocabulary at the same deployment budget",
            "significant": "and more than the earlier loop's vocabulary at the same deployment budget"}),
        worded(flags["budget_bound"], {
            "topic": "reach beyond the budget",
            "none": "as a different first match, not reach beyond the budget",
            "not separated": "reach beyond the budget not separated from chance",
            "significant": "with reach beyond the budget"}),
        worded(flags["undreamt"], {
            "topic": "where no dream computed the task or composed its pair of routines",
            "none": "not where no dream computed the task or composed its pair of routines",
            "not separated": "where no dream computed the task or composed its pair of routines not separated from chance",
            "significant": "also where no dream computed the task or composed its pair of routines"}),
        worded(flags["beyond_learning_tasks"], {
            "topic": "where a stage is not one of its learning tasks",
            "none": "only where both stages are its own learning tasks",
            "not separated": "where a stage is not one of its learning tasks not separated from chance",
            "significant": "also where a stage is not one of its learning tasks"})]
    return scope + "confirmed on FRESH-4 against everything generation 0 solves at any budget run; " + "; ".join(endings)


def graded(comparison: dict) -> str:
    """'significant': more sound solves with p < ALPHA. Otherwise 'not testable' when fewer than
    MIN_DISCORDANT tasks are solved by one arm only (nothing can be read from so few, an absence
    least of all); otherwise 'not separated' (more, p >= ALPHA) or 'none' (no more)."""
    more = comparison["trained"] > comparison["control"]
    if more and comparison["p_one_sided"] < ALPHA:
        return "significant"
    if comparison["trained_only"] + comparison["control_only"] < MIN_DISCORDANT:
        return "not testable"
    return "not separated" if more else "none"


def worded(grade: dict, readings: dict) -> str:
    if grade["reading"] == "not testable":
        return (f"{readings['topic']} not testable ({grade['tasks']} tasks, "
                f"{grade['trained_only'] + grade['control_only']} that only one arm solves)")
    return readings[grade["reading"]]


def main(out_path: str, workers: int, tiny: bool, resume: bool, rehearse: str | None = None) -> None:
    global DEPLOY, TOP, HELD_RUNGS, MIN_EVIDENCE
    stand_in = tiny or bool(rehearse)               # FRESH-3 tasks stand in for both generated sets
    if tiny:
        deepen.STUDENT, deepen.TEACHER, deepen.CAP, deepen.MAX_CYCLES = 300, 1500, 5000, 2
        deepen.DREAMS_GATE, deepen.DREAMS_CORPUS, deepen.DREAMS_TARGETS, deepen.MAX_TRIALS = 20, 40, 20, 5
        DEPLOY, TOP, HELD_RUNGS = 1500, 3000, {"r2000": 2000, "top": 3000}
    elif rehearse:
        DEPLOY, TOP, HELD_RUNGS = 20_000, 60_000, {"r30000": 30_000, "top": 60_000}
    learn = CONFIGS["B"]
    held = [p for p in ALL if p not in learn]
    harness = Harness(workers, ALL)
    import fresh3                                   # loads the FRESH partitions: after the fork
    import fresh4
    third = fresh3.make()
    if not fresh3.digest(third).startswith("4da13e671411da8c"):
        raise SystemExit("fresh3.make() no longer gives the registered FRESH-3 set")
    tally = {}
    if stand_in:                                    # FRESH-3 tasks stand in: no FRESH-4 candidate is made
        fourth, third = third[:60], third[60:100]
    else:
        fourth = fresh4.make(statistics=tally)
    digest = fresh3.digest(fourth)
    if not stand_in and (len(fourth) != fresh4.COUNT or not digest.startswith(REGISTERED_DIGEST)):
        raise SystemExit(f"this is not the registered FRESH-4 set: {len(fourth)} tasks, digest {digest}")
    harness.add_partition("fresh4", fourth, [task.public_view() for task in fourth])
    harness.add_partition("fresh3", third, [task.public_view() for task in third])
    protocol = {"components": COMPONENTS, "student": deepen.STUDENT, "teacher": deepen.TEACHER, "cap": deepen.CAP,
                "rejects": deepen.REJECTS, "max_trials": deepen.MAX_TRIALS, "max_cycles": deepen.MAX_CYCLES,
                "dreams": [deepen.DREAMS_GATE, deepen.DREAMS_CORPUS, deepen.DREAMS_TARGETS],
                "deploy": DEPLOY, "tiny": tiny, "rehearsal": bool(rehearse), "fresh4_digest": digest}
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
    if rehearse:                                    # a development report of the loop, taken as it is
        report = json.load(open(rehearse))
        if not report.get("finished"):
            raise SystemExit("the loop report to rehearse with is not finished")
    elif previous.get("loop", {}).get("finished"):
        report = previous["loop"]
        out["loop_taken_from_interrupted_run"] = True
    else:
        report = deepen.run(harness, learn, components=COMPONENTS)
    out["loop"] = report
    out["library_digest"] = hashlib.sha256(json.dumps(
        sorted((entry["witness"], entry["params"], entry["result"]) for entry in report["library"].values())
    ).encode()).hexdigest()
    save()
    out["loop_as_in_development"] = None if stand_in else (
        out["library_digest"] == EXPECTED_LOOP["library_digest"]
        and report["training_ceiling"] == EXPECTED_LOOP["training_ceiling"])
    print(f"loop: {len(report['library'])} symbols, library digest {out['library_digest'][:16]}, training ceiling "
          f"{report['training_ceiling']}; as in development: {out['loop_as_in_development']}", flush=True)
    earlier = json.load(open(EARLIER))
    libraries = {"gen0": {}, "new": report["library"], "old": earlier["loop"]["library"]}
    training = {"new": report["training_ceiling"], "old": earlier["training_candidates"]}
    if stand_in:                                    # toy ceilings, so that the rungs stay small
        training = {"new": 1_500_000 if rehearse else report["training_ceiling"], "old": 600_000}
    sets = {"heldB": held, "fresh4": ["fresh4"], "fresh3": ["fresh3"]}
    sizes = {name: sum(len(harness.public[p]) for p in parts) for name, parts in sets.items()}
    c2 = lambda which: round((training[which] + sizes["fresh4"] * DEPLOY) / sizes["fresh4"])
    budgets = {"fresh4": {"C2old": c2("old"), "C2new": c2("new"), "top": TOP}, "heldB": dict(HELD_RUNGS)}
    if budgets["fresh4"]["C2new"] > MEMORY_LIMIT:
        raise SystemExit(f"C2new = {budgets['fresh4']['C2new']} does not fit in memory: the registered control cannot be run")
    c1new = round((training["new"] + sizes["heldB"] * DEPLOY) / TASKS)
    if c1new <= MEMORY_LIMIT:
        budgets["heldB"]["C1new"] = c1new
    out["c2new_if_training_were_charged_to_300_tasks"] = round((training["new"] + 300 * DEPLOY) / 300)
    out["top_rung_covers_the_whole_budget"] = {
        "on_these_tasks": TOP >= budgets["fresh4"]["C2new"],
        "if_training_were_charged_to_300_tasks": TOP >= out["c2new_if_training_were_charged_to_300_tasks"]}
    out["training_candidates"], out["set_sizes"], out["control_budgets"] = training, sizes, budgets
    out["c1new_on_held_out_b"] = {"budget": c1new, "run": c1new <= MEMORY_LIMIT}
    print(f"training ceilings {training}; control budgets {budgets}", flush=True)

    # ---- 3. evaluation runs ------------------------------------------------------------------------
    rows = dict(previous.get("rows") or {})
    out["rows"] = rows

    def measure(label, state, budget, partitions, only=None):
        fingerprint = {"state": state if isinstance(state, str) else state[0], "budget": budget,
                       "partitions": list(partitions),
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
    # ---- criterion R2, after the loop and outside it ------------------------------------------------
    # Discovery: a later teacher solves a learning task soundly with a program that uses a learned
    # symbol, and generation 0 at the same budget on the same task finds no public match.
    by_run = {t["run"]: t for t in report["timeline"]}
    sound = Sound({"fresh4": fourth, "fresh3": third})
    discovery, found_by = {}, {}                   # found_by: cycle -> {task: the teacher's program text}
    for cycle in report["cycles"][1:]:
        label = f"gen0@teacher{cycle['cycle']}:learn"
        measure(label, "gen0", cycle["teacher_share"], list(learn), only=set(cycle["unsolved"]))
        teacher, plain = by_run[cycle["teacher_run"]], rows[label]
        with_symbols = {key for key, value in teacher["programs"].items()
                        if teacher["used"].get(key) and sound.verdict(key, value[0])[0]
                        and not plain["records"][key]["matched"]}
        other_way = {key for key, value in plain["programs"].items()
                     if sound.verdict(key, value[0])[0] and key not in teacher["programs"]
                     and key not in teacher["rejected"]}
        if len(with_symbols) > len(other_way):          # the symbols helped that teacher more than they cost
            found_by[cycle["cycle"]] = {key: teacher["programs"][key][0] for key in with_symbols}
        discovery[str(cycle["cycle"])] = {
            "budget": cycle["teacher_share"], "tasks": len(cycle["unsolved"]),
            "teacher_sound_with_a_symbol_where_generation_0_has_no_match": sorted(with_symbols),
            "generation_0_sound_where_the_teacher_has_no_match": sorted(other_way)}
    # Recursive symbols: accepted after the first cycle and distilled from such a program (one of
    # the programs the symbol folded when it was proposed is a discovery made in that cycle or
    # before, text for text); with them go the symbols defined through them.
    trials = {t["proposed"]["name"]: dict(t["proposed"], run=t["run"]) for t in report["timeline"] if t.get("accepted")}
    cycle_of_run = {t["run"]: cycle["cycle"] for cycle in report["cycles"] for t in report["timeline"]
                    if cycle["teacher_run"] <= t["run"] <= max(cycle["student_run"], cycle["teacher_run"])}
    seeds = set()
    for name, info in trials.items():
        info.setdefault("cycle", cycle_of_run.get(info["run"], 1))     # reports made before these fields existed
        folded = info.get("support_programs")
        if folded is None:                                              # (rehearsals only) fall back on use
            folded = {key: found_by.get(info["cycle"], {}).get(key) for key, used in by_run[info["run"]]["used"].items()
                      if name in (used or ())}
        if info["cycle"] >= 2 and any(text is not None and found_by.get(c, {}).get(key) == text
                                      for key, text in folded.items() for c in range(2, info["cycle"] + 1)):
            seeds.add(name)
    recursive = descendants(report["library"], seeds) if seeds else set()
    first_cycle = set(report["cycles"][0]["library"]) if report["cycles"] else set()
    lineage = descendants(report["library"], first_cycle) if first_cycle else set()
    ablations = {"without-recursive": recursive, "without-cycle1-lineage": lineage, "without-cycle1-only": first_cycle}
    for label, names in ablations.items():
        if names:
            kept = {name: entry for name, entry in report["library"].items() if name not in names}
            measure(f"new-{label}@student", (label, kept), student, list(learn) + held)
            measure(f"new-{label}@student:fresh4", (label, kept), student, ["fresh4"])
    # The vocabulary after each accepting cycle on FRESH-4 at the student budget (the last one is
    # the row new@student:fresh4): criterion R1 there.
    stages = [cycle for cycle in report["cycles"] if cycle["accepted"]]
    for cycle in stages[:-1]:
        measure(f"cycle{cycle['cycle']}@student:fresh4",
                (f"cycle{cycle['cycle']}", {name: report["library"][name] for name in cycle["library"]}),
                student, ["fresh4"])

    # ---- 4. audit and tests ------------------------------------------------------------------------
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
    old_own = set().union(arms["fresh4"]["controls"]["student"], arms["fresh4"]["controls"]["equal"],
                          *(arms["fresh4"]["controls"][rung] for rung, budget in budgets["fresh4"].items()
                            if budget <= budgets["fresh4"]["C2old"]))
    comparisons["fresh4: old@deploy vs gen0 up to C2old"] = paired(arms["fresh4"]["old@deploy"], old_own)
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

    # the primary comparison and its breakdowns: list outputs, the scope of the claim
    task_of = {f"fresh4/{task.name}": task for task in fourth}
    scope = {key for key, task in task_of.items() if task.kind == "list"}
    treated, control = arms["fresh4"]["new@deploy"] & scope, arms["fresh4"]["controls"]["any"] & scope
    old_arm = arms["fresh4"]["old@deploy"] & scope
    out["primary"] = dict(paired(treated, control), tasks=len(scope))
    out["new_vs_old"] = dict(paired(treated, old_arm), tasks=len(scope))
    out["old_vs_any"] = dict(paired(old_arm, control), tasks=len(scope))
    out["other_outputs"] = dict(paired(arms["fresh4"]["new@deploy"] - scope, arms["fresh4"]["controls"]["any"] - scope),
                                tasks=len(task_of) - len(scope))
    top_rung = max(budgets["fresh4"], key=lambda r: budgets["fresh4"][r])
    out["kinds"] = {"fresh4, list outputs: new@deploy vs gen0@any": kinds_of(
        treated, control, rows["new@deploy:fresh4"], rows[f"gen0@{top_rung}:fresh4"])}
    earlier_routine = lambda task: task.modulo or EARLIER_FAMILY in (task.stages[0][0], task.stages[1][0])
    # what the loop dreamt: the programs themselves, and the pairs of routine families they compose
    dreams = [entry for cycle in report["cycles"] for group in cycle["dream_programs"].values() for entry in group]
    parsed = [parse(text) for text in sorted({text for text, _, _ in dreams})]
    family_of_key = lambda key: partitions.family(key.split("/", 1)[1])
    dream_pairs = {(family_of_key(f), family_of_key(g)) for _, f, g in dreams}

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

    dreamt_exact = {key for key, task in task_of.items() if dreamt(task)}
    dreamt_pair = {key for key, task in task_of.items() if (task.stages[0][0], task.stages[1][0]) in dream_pairs}
    dreamt_keys = dreamt_exact | dreamt_pair
    solved_families = {family_of_key(key) for t in report["timeline"] for key in t["programs"]
                       if key.split("/", 1)[0] in learn}
    outside_dreams = {key for key, task in task_of.items()
                      if any(routine not in solved_families for routine, _ in task.stages)}
    origin = fresh4.provenance(fourth) if not tiny else {task.name: {"stages": 1, "first": True, "unmet": []}
                                                         for task in fourth}
    origin = {f"fresh4/{name}": value for name, value in origin.items()}
    out["dreamt"] = {"dream_programs": len(parsed), "pairs_of_routine_families_dreamt": len(dream_pairs),
                     "fresh4_tasks_a_dream_computes": len(dreamt_exact),
                     "fresh4_tasks_whose_routine_pair_was_dreamt": len(dreamt_pair),
                     "fresh4_tasks_with_a_routine_the_loop_never_solved_alone": len(outside_dreams)}
    out["provenance"] = {"both stage instances are learning tasks": sum(1 for v in origin.values() if v["stages"] == 2),
                         "one": sum(1 for v in origin.values() if v["stages"] == 1),
                         "none": sum(1 for v in origin.values() if v["stages"] == 0),
                         "with a routine no learning task has": sum(1 for v in origin.values() if v["unmet"])}

    def stratum(test, t=treated, c=control):
        chosen = {key for key in scope if test(key, task_of[key])}
        return dict(paired(t & chosen, c & chosen), tasks=len(chosen), reading=graded(paired(t & chosen, c & chosen)))

    tests = {
        "with a routine of the earlier symbols (slice-k-n or the divisibility family)": lambda k, t: earlier_routine(t),
        "without one": lambda k, t: not earlier_routine(t),
        "a dream computes the task or composes its pair of routines": lambda k, t: k in dreamt_keys,
        "no dream does": lambda k, t: k not in dreamt_keys,
        "a routine the loop never solved alone": lambda k, t: k in outside_dreams,
        "both stage instances are learning tasks": lambda k, t: origin[k]["stages"] == 2,
        "one stage instance is a learning task": lambda k, t: origin[k]["stages"] == 1,
        "no stage instance is a learning task": lambda k, t: origin[k]["stages"] == 0,
        "not both stage instances are learning tasks": lambda k, t: origin[k]["stages"] < 2,
        "a routine no learning task has": lambda k, t: bool(origin[k]["unmet"])}
    out["strata"] = {name: stratum(test) for name, test in tests.items()}
    out["strata_new_vs_old"] = {name: stratum(test, treated, old_arm) for name, test in tests.items()}
    out["more_than_re_pairing_of_trained_instances"] = any(
        out["strata"][name]["reading"] == "significant"
        for name in ("no stage instance is a learning task", "a routine no learning task has"))
    rate = lambda keys, kind: (sum(1 for key in keys if task_of[key].kind == kind)
                               / max(1, sum(1 for task in fourth if task.kind == kind)))
    mix = {"list": 0.71, "int": 0.11, "bool": 0.18}                # FRESH-2's output types
    out["lead_standardised_to_the_mix_of_fresh2_per_100_tasks"] = round(100 * sum(
        share * (rate(arms["fresh4"]["new@deploy"], kind) - rate(arms["fresh4"]["controls"]["any"], kind))
        for kind, share in mix.items()), 1)
    family = lambda routine: "divisibility family" if routine in fresh3.MODULO else routine
    scoped = {key: task for key, task in task_of.items() if key in scope}
    out["clusters"] = {
        "by first-stage routine": clustered(treated, control, {key: family(task.stages[0][0]) for key, task in scoped.items()}),
        "by second-stage routine": clustered(treated, control, {key: family(task.stages[1][0]) for key, task in scoped.items()})}
    routines = sorted({stage[0] for task in fourth for stage in task.stages})
    without = {}
    for routine in routines:
        kept = {key for key, task in scoped.items() if routine not in (task.stages[0][0], task.stages[1][0])}
        without[routine] = dict(paired(treated & kept, control & kept), tasks=len(kept))
    worst = max(without, key=lambda routine: (without[routine]["p_one_sided"], routine))
    out["leave_one_routine_out"] = {"largest_p": without[worst]["p_one_sided"], "routine": worst, "all": without}
    # Removing routines in a fixed order of net lead (computed once), with every task that contains
    # them, until the remaining lead is no longer separated. This loses power as well as lead, so
    # the number of routines is evidence of narrowness only by the rule in ``reading``.
    net = {}
    for key in treated ^ control:
        for routine in {task_of[key].stages[0][0], task_of[key].stages[1][0]}:
            net[routine] = net.get(routine, 0) + (1 if key in treated else -1)
    per_task = lambda keys: round((len(treated & keys) - len(control & keys)) / max(1, len(keys)), 4)
    kept, removed, carried = set(scope), [], None
    if not (out["primary"]["trained"] > out["primary"]["control"] and out["primary"]["p_one_sided"] < ALPHA):
        carried = {"routines_removed": "none: there is no separated lead"}
    else:
        for routine in sorted(net, key=lambda r: (-net[r], r)):
            kept = {key for key in kept if routine not in (task_of[key].stages[0][0], task_of[key].stages[1][0])}
            removed.append(routine)
            left = paired(treated & kept, control & kept)
            if not (left["trained"] > left["control"] and left["p_one_sided"] < ALPHA):
                narrow = left["trained"] <= left["control"] and len(kept) >= 200
                carried = {"routines_removed": list(removed), "tasks_removed": len(scope) - len(kept),
                           "tasks_left": len(kept), "left": left,
                           "lead_per_task_in_the_removed_tasks": per_task(scope - kept),
                           "lead_per_task_in_the_tasks_left": per_task(kept),
                           "reading": "the lead holds over pairs of these routines only" if narrow
                           else "the count of routines is not evidence of narrowness"}
                break
    out["lead_carried_by"] = carried or {"routines_removed": list(removed), "tasks_left": 0,
                                         "reading": "the count of routines is not evidence of narrowness"}
    by_routine = {}
    for key, task in scoped.items():
        for routine in {task.stages[0][0], task.stages[1][0]}:
            entry = by_routine.setdefault(routine, {"tasks": 0, "new": 0, "old": 0, "gen0_any": 0})
            entry["tasks"] += 1
            entry["new"] += key in treated
            entry["old"] += key in old_arm
            entry["gen0_any"] += key in control
    out["by_routine"] = dict(sorted(by_routine.items()))
    accepted, last_score = {}, None
    for t in report["timeline"]:                      # which symbols came in on the dream tie-break
        if t["label"].startswith("student") and "proposed" in t:
            if t.get("accepted"):
                accepted[t["proposed"]["name"]] = {"real_tasks": t["proposed"]["real_tasks"], "depth": t["proposed"]["depth"],
                                                   "cycle": trials[t["proposed"]["name"]]["cycle"],
                                                   "on_the_tie_break": t["family_score_exact"] == last_score}
                last_score = t["family_score_exact"]
        elif t["label"] == "student0":
            last_score = t["family_score_exact"]
    out["accepted_symbols_detail"] = accepted
    symbols, deep_use, dream_only_use = {}, 0, 0
    for key in sorted(treated - control):
        used = rows["new@deploy:fresh4"]["used"].get(key) or ["(no learned symbol)"]
        deep_use += any(accepted.get(symbol, {}).get("depth", 1) >= 2 for symbol in used)
        dream_only_use += any(accepted.get(symbol, {}).get("real_tasks", 1) == 0 for symbol in used)
        for symbol in used:
            symbols[symbol] = symbols.get(symbol, 0) + 1
    out["new_only_by_symbol"] = dict(sorted(symbols.items(), key=lambda item: -item[1]))
    out["new_only_with_a_symbol_built_on_a_symbol"] = deep_use
    out["new_only_with_a_symbol_no_learning_program_uses"] = dream_only_use
    strict = {label: {key for key in rows[label]["sound"]
                      if key in scope and sound.on_pool(key, rows[label]["programs"][key][0])}
              for label in rows if rows[label]["partitions"] == ["fresh4"]}
    out["fresh4_sound_and_on_whole_pool"] = paired(strict["new@deploy:fresh4"], set().union(
        *(keys for label, keys in strict.items() if label.startswith("gen0@"))))
    out["thin_evidence"] = {label: len(row["thin_evidence"]) for label, row in rows.items() if row["thin_evidence"]}

    # ---- the four criteria ------------------------------------------------------------------------
    # R1: sound solves at the student budget rise in two generations running.
    # R2: a task gained after the first cycle whose program uses a recursive symbol and which is
    #     lost when the recursive symbols are taken out of the final vocabulary.
    # R3: the final vocabulary at the student budget has more sound solves than generation 0 at any
    #     budget run. R4: no step is decided by a person.
    rises = lambda values: any(a < b < c for a, b, c in zip(values, values[1:], values[2:]))

    def second(gains, used, without_recursive, without_lineage) -> dict:
        """R2 on one set. ``gains``: the sound solves of the final vocabulary that neither generation 0
        nor the first cycle's vocabulary has. ``used``: task -> the learned symbols its program was
        built with. A gain counts when it was built with a recursive symbol, is lost without the
        recursive symbols and is lost without the first cycle's symbols and those defined through
        them (the symbols of the earlier generation)."""
        uses = {key for key in gains if set(used.get(key) or ()) & recursive}
        lost = uses - solved(without_recursive) if recursive else set()
        both = lost - solved(without_lineage) if lineage else set()
        return {"gains_after_cycle_1": len(gains), "of_those_built_with_a_recursive_symbol": len(uses),
                "of_those_lost_without_the_recursive_symbols": len(lost),
                "of_those_also_lost_without_the_first_cycle_and_what_is_defined_through_it": len(both),
                "holds": len(both) > 0}

    lost_final = {}
    for label, names in ablations.items():
        if names:
            lost_final[label] = {"symbols_removed": sorted(names),
                                 "fresh4_sound_solves_lost": len(solved("new@student:fresh4") - solved(f"new-{label}@student:fresh4")),
                                 "fresh4_sound_solves_gained": len(solved(f"new-{label}@student:fresh4") - solved("new@student:fresh4"))}
    out["recursion"] = {"discovery_by_cycle": discovery, "recursive_symbols": sorted(seeds),
                        "with_the_symbols_defined_through_them": sorted(recursive), "ablations": lost_final}

    # on FRESH-4, which the loop never saw and development never used
    chain = [("generation 0", solved("gen0@student:fresh4"))]
    chain += [(f"cycle {cycle['cycle']}", solved(f"cycle{cycle['cycle']}@student:fresh4")) for cycle in stages[:-1]]
    if stages:
        chain.append((f"cycle {stages[-1]['cycle']}", solved("new@student:fresh4")))
    gains4 = chain[-1][1] - chain[1][1] - chain[0][1] if len(chain) > 2 else set()
    second4 = second(gains4, rows["new@student:fresh4"]["used"], "new-without-recursive@student:fresh4",
                     "new-without-cycle1-lineage@student:fresh4")
    third4 = paired(arms["fresh4"]["new@student"], arms["fresh4"]["controls"]["any"])
    first4 = rises([len(keys) for _, keys in chain])
    out["criteria_on_fresh4"] = {
        "R1_sound_by_generation": [[name, len(keys)] for name, keys in chain], "R1": first4,
        "R2_detail": second4, "R2": second4["holds"],
        "R3_new_student_vs_gen0_any": third4, "R3": third4["trained"] > third4["control"],
        "R3_separated": third4["trained"] > third4["control"] and third4["p_one_sided"] < ALPHA,
        "R4": True,
        "all_four": bool(first4 and second4["holds"] and third4["trained"] > third4["control"])}

    # on held-out B, a development set: descriptive
    reports = [t for t in report["timeline"] if t["label"].startswith("report")]
    by_cycle = [{key for key, value in t["programs"].items() if sound.verdict(key, value[0])[0]} for t in reports]
    trajectory = [{"label": t["label"], "verified": t["held_out"], "sound": len(keys)} for t, keys in zip(reports, by_cycle)]
    held_new = {key for key in solved("new@student:heldB")}
    gains_b = held_new - by_cycle[1] - by_cycle[0] if len(by_cycle) > 2 else set()
    second_b = second(gains_b, rows["new@student:heldB"]["used"], "new-without-recursive@student",
                      "new-without-cycle1-lineage@student")
    held_any = arms["heldB"]["controls"]["any"]
    third_b = paired(arms["heldB"]["new@student"], held_any)
    out["criteria"] = {
        "R1_held_out_B_by_cycle": trajectory,
        "R1": {"verified": rises([t["verified"] for t in trajectory]), "sound": rises([t["sound"] for t in trajectory])},
        "R2_detail": second_b, "R2": second_b["holds"],
        "R3_new_student_vs_gen0_any_on_held_out_B": third_b,
        "R3": third_b["trained"] > third_b["control"] if c1new <= MEMORY_LIMIT
        else "not scored: the cumulative budget does not fit in memory and was not run",
        "R4": True}

    # ---- the outcome class, on sound counts and, beside it, on verified counts -----------------------
    def flags_for(measure_):
        a = arms_for(measure_)
        t, c = a["fresh4"]["new@deploy"] & scope, a["fresh4"]["controls"]["any"] & scope
        o = a["fresh4"]["old@deploy"] & scope

        def grade(comparison, tasks):
            return dict(comparison, tasks=tasks, reading=graded(comparison))

        def within(keys):
            return grade(paired(t & keys, c & keys), len(keys))

        primary = paired(t, c)
        bound = kinds_of(t, c, rows["new@deploy:fresh4"], rows[f"gen0@{top_rung}:fresh4"])["budget_bound"]
        bound = {"trained": bound["trained_only"], "control": bound["control_only"],
                 "trained_only": bound["trained_only"], "control_only": bound["control_only"],
                 "p_one_sided": bound["p_one_sided"]}
        expected = {f"gen0@{rung}:fresh4" for rung in budgets["fresh4"]} | {
            f"{state}@{at}:fresh4" for state in ("gen0", "new", "old") for at in ("deploy", "student")}
        return {"missing": "" if expected <= set(rows) else f"runs missing: {sorted(expected - set(rows))}",
                "scope": f"for list outputs ({len(scope)} of {len(task_of)} tasks)",
                "accepted": bool(report["library"]),
                "lead": primary["trained"] > primary["control"],
                "significant": primary["p_one_sided"] < ALPHA,
                "outside_earlier": within({key for key in scope if not earlier_routine(task_of[key])}),
                "over_old": grade(paired(t, o), len(scope)),
                "budget_bound": grade(bound, len(scope)),
                "undreamt": within(scope - dreamt_keys),
                "beyond_learning_tasks": within({key for key in scope if origin[key]["stages"] < 2})}

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
    print("PRIMARY (list outputs):", json.dumps(out["primary"]), "| other outputs:", json.dumps(out["other_outputs"]))
    print("new against old (list outputs):", json.dumps(out["new_vs_old"]), "| old against generation 0 at any budget:",
          json.dumps(out["old_vs_any"]))
    for label, k in out["kinds"].items():
        print(f"{label:44s} only new {k['trained_only']}; only control {k['control_only']}; budget-bound {k['budget_bound']}")
    print("provenance:", json.dumps(out["provenance"]))
    for name, value in out["strata"].items():
        print(f"  stratum {name}: {json.dumps(value)}")
    for name, value in out["strata_new_vs_old"].items():
        print(f"  new against old, {name}: {json.dumps(value)}")
    print("more than re-pairing of trained instances (a significant lead where no stage is a learning task or a "
          "routine has no learning task):", out["more_than_re_pairing_of_trained_instances"])
    print("routines removed until the lead is not separated:", json.dumps(out["lead_carried_by"]),
          "| standardised to the mix of FRESH-2, per 100 tasks:",
          out["lead_standardised_to_the_mix_of_fresh2_per_100_tasks"])
    print("clusters:", json.dumps(out["clusters"]))
    print("leave one routine out: largest p", out["leave_one_routine_out"]["largest_p"], "without", worst)
    print("by routine:", json.dumps(out["by_routine"]))
    print("new-only tasks by learned symbol:", json.dumps(out["new_only_by_symbol"]),
          "| with a symbol built on a symbol:", deep_use, "| with a symbol no learning program uses:", dream_only_use)
    print("accepted symbols:", json.dumps(out["accepted_symbols_detail"]))
    print("dreamt:", json.dumps(out["dreamt"]), "| thin evidence:", json.dumps(out["thin_evidence"]))
    print("FRESH-4, sound and right on the whole input pool:", json.dumps(out["fresh4_sound_and_on_whole_pool"]))
    print("recursion:", json.dumps(out["recursion"]))
    print("criteria on held-out B (a development set):", json.dumps(out["criteria"]))
    print("criteria on FRESH-4:", json.dumps(out["criteria_on_fresh4"]))
    print("loop: verdicts read", report.get("verdicts_read"), "| seconds in compression and dreaming",
          round(sum(report.get("driver_seconds", [])), 1), "| training ceiling", report["training_ceiling"],
          "spent", report["training_spent"])
    print("predictions:", json.dumps(out["predictions"]))
    print("flags:", json.dumps(out["flags"]))
    print("OUTCOME:", out["outcome"])
    print("on verified counts:", out["outcome_on_verified_counts"])
    harness.close()


def predictions(out, report, comparisons, trajectory) -> dict:
    """The predictions of Addendum 8, scored mechanically (the thresholds are the registered ones)."""
    verdict = lambda ok: "PASS" if ok else "FAIL"
    by_grade = lambda grade: ("not scored (stratum not testable)" if grade["reading"] == "not testable"
                              else verdict(grade["reading"] == "significant"))
    primary, strata, fourth, flags = out["primary"], out["strata"], out["criteria_on_fresh4"], out["flags"]
    unmet = strata["a routine no learning task has"]
    return {
        "D1": verdict(primary["trained"] > primary["control"]),
        "D2": verdict(primary["p_one_sided"] < ALPHA) if primary["trained"] > primary["control"]
        else "not scored (D1 failed)",
        "D3": verdict(primary["trained"] - primary["control"] >= THRESHOLDS["D3_lead"]),
        "D4": by_grade(flags["outside_earlier"]),
        "D5": by_grade(flags["over_old"]),
        "D6": verdict(out["old_vs_any"]["trained"] > out["old_vs_any"]["control"]
                      and out["old_vs_any"]["p_one_sided"] < ALPHA),
        "D7": by_grade(flags["undreamt"]),
        "D8": by_grade(flags["beyond_learning_tasks"]),
        "D9": by_grade(flags["budget_bound"]),
        "D10": "not scored (stratum not testable)" if unmet["reading"] == "not testable"
        else verdict(unmet["trained"] > unmet["control"]),
        "D11": verdict(fourth["R1"]),
        "D12": verdict(fourth["R2"]),
        "D13": verdict(fourth["R3"]),
        "D14": verdict(fourth["all_four"]),
        "thresholds": dict(THRESHOLDS)}


THRESHOLDS = {"D3_lead": 50}


if __name__ == "__main__":
    rehearse_with = sys.argv[sys.argv.index("--rehearse") + 1] if "--rehearse" in sys.argv else None
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 4, "--tiny" in sys.argv,
         "--resume" in sys.argv, rehearse_with)
