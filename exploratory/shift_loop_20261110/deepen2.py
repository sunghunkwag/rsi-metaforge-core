"""The deepening loop with scoped symbols and a pruning pass (exploratory, in development).

``deepen.py`` is the loop registered in Addendum 8 and is not changed. This file is that loop
with two options, each taken from measurements on development sets (three independent analysts,
``results/understand_loop_limits.json``):

  * ``scope="list"``. A learned symbol is visible to the searches in the list space (the scan of
    representation search and the direct search) and not to the searches in the element space
    (the int -> element searches of S and R). Measured on development sets: with the 19 symbols
    of Addendum 8 in the element vocabulary the same element problems cost more than with none;
    without them a run of 10^4 candidates recovers 18 of the 48 tasks that only a run of 10^5
    solved, and on the learning tasks the symbols earn nothing in the element space.
  * ``prune=True``. After the trials of a cycle the symbols accepted in earlier cycles are tried
    for removal, least used by the student's learning programs first. A symbol is removed when
    the family-normalised verified score of the student rises without it, or stays equal while
    the student solves no fewer of the cycle's gate dreams. Measured: every list symbol slows the
    deep solutions of a 10^4 search by 5 to 12%, so a symbol that a later one has made useless
    still costs. A removed symbol is never proposed again.

With ``scope="all"`` and ``prune=False`` this is ``deepen.run``: the same runs in the same
order (compared on a tiny run when this file was written).

The loop stops after a cycle that neither accepts nor removes a symbol, or after MAX_CYCLES.

    python deepen2.py <config A|B> <out.json> [workers] [--scope all|list] [--prune]
                      [--max-cycles N] [--tiny]
"""
from __future__ import annotations

import collections
import json
import sys
import time

import compress
import deepen
from deepen import COMPONENTS, MAX_CYCLES, REJECTS, Dreamer, family_score, input_pool
from hybrid import ALL, Harness, spec_of, summary
from loop import CONFIGS, serialise
from rsi5 import partitions
from rsi5.dsl.terms import term_from_dict
from rsi5.dsl.vocabulary import VOCABULARIES

PRUNES = 8                    # removal trials per cycle, at most
SCOPES = ("all", "list")


def keep_for(scope: str, constants=(), vocabulary: str = "restored"):
    """The per-space restriction of the harness for a scope: None (everything everywhere), or
    the element space cut to the base primitives and the integer constants."""
    if scope == "all":
        return None
    if scope != "list":
        raise ValueError(f"unknown scope {scope!r}")
    base = VOCABULARIES[vocabulary]
    integers = list(base.integer_constants) + [c for c in constants if c not in base.integer_constants]
    return {"elem": list(base.primitives) + [f"int:{c}" for c in integers], "list": None}


def spec_for(library: dict, label: str, budget: int, components: str = COMPONENTS, scope: str = "all") -> dict:
    """The harness spec of a library of ``compress`` abstractions under a scope."""
    abstractions, constants = serialise(library)
    return spec_of(label, budget, components, abstractions, constants, keep=keep_for(scope, constants))


def run(harness, learn, *, scope="all", prune=False, max_cycles=None, components=COMPONENTS, log=print,
        checkpoint=None):
    if scope not in SCOPES:
        raise ValueError(f"unknown scope {scope!r}")
    student_budget, teacher_budget, cap = deepen.STUDENT, deepen.TEACHER, deepen.CAP
    max_trials = deepen.MAX_TRIALS
    max_cycles = MAX_CYCLES if max_cycles is None else max_cycles
    held = tuple(p for p in ALL if p not in learn)
    family_of = {f"{p}/{task.name}": partitions.family(task.name) for p in learn for task in harness.public[p]}
    sizes = collections.Counter(family_of.values())
    every = set(family_of)
    pool = input_pool(harness, learn)
    teacher_ceiling = teacher_budget * len(every)
    library, tabu, corpus, timeline, cycles = {}, set(), {}, [], []
    born = {}                                  # symbol name -> the cycle that accepted it
    driver_seconds = []                        # compression and dreaming in the driver: in no budget
    trials = 0

    def measure(lib, label, budget, names, only=None, dreams=()):
        started = time.perf_counter()
        result = harness.run(spec_for(lib, label, budget, components, scope),
                             partition_names=list(names), dreams=[(task, check) for task, check, _, _ in dreams],
                             only=only)
        real = {p: rows for p, rows in result.items() if p != "dream"}
        programs = {f"{p}/{row['name']}": term_from_dict(row["term"])
                    for p in learn if p in real for row in real[p] if row["solved"]}
        counts = summary(result)
        jobs = sum(len(rows) for rows in result.values())
        score = family_score(programs, family_of, sizes)
        record = {"run": harness.runs, "label": label, "budget": budget, "tasks": jobs, "ceiling": budget * jobs,
                  "learning_tasks": sum(len(rows) for p, rows in real.items() if p in learn),
                  "spent": sum(row["candidates"] for rows in result.values() for row in rows),
                  "counts": counts,
                  "learn": sum(counts[p] for p in learn if p in counts) if any(p in counts for p in learn) else None,
                  "held_out": sum(counts[p] for p in held) if held and all(p in counts for p in held) else None,
                  "family_score": round(float(score), 3), "family_score_exact": [score.numerator, score.denominator],
                  "families_with_a_solve": len({family_of[k] for k in programs}),
                  "dream": [sum(1 for row in result["dream"] if row["solved"]), len(result["dream"])]
                  if "dream" in result else None,
                  "library": list(lib),
                  "solved": sorted(f"{p}/{r['name']}" for p, rows in real.items() for r in rows if r["solved"]),
                  "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                               for p, rows in real.items() for r in rows if r["solved"]},
                  "rejected": {f"{p}/{r['name']}": [r["program"], r["route"]]     # public match, verifier said no
                               for p, rows in real.items() for r in rows if r["term"] is not None and not r["solved"]},
                  "used": {f"{p}/{r['name']}": r["used"] for p, rows in real.items() for r in rows if r["solved"]},
                  "seconds": round(time.perf_counter() - started)}
        timeline.append(record)
        log(f"run {harness.runs:3d} {label:14s} budget {budget:>7} tasks {jobs:3d} learn {record['learn']} "
            f"score {record['family_score']:6.2f} dream {record['dream']} held-out {record['held_out']} "
            f"lib {len(lib)} | {record['seconds']} s")
        return record, programs, score

    def absorb(programs):
        for key, term in programs.items():
            if key not in corpus or compress.size(term) < compress.size(corpus[key]):
                corpus[key] = term

    def state(finished: bool) -> dict:
        return {"learn": list(learn), "held_out": list(held), "components": components, "finished": finished,
                "scope": scope, "prune": prune,
                "student": student_budget, "teacher": teacher_budget, "cap": cap,
                "timeline": timeline, "cycles": cycles,
                "student_first": timeline[0]["run"], "student_last": last_student,
                "families": len(sizes), "driver_seconds": driver_seconds,
                "training_ceiling": sum(t["ceiling"] for t in timeline),
                "training_spent": sum(t["spent"] for t in timeline),
                "verdicts_read": sum(t["learning_tasks"] for t in timeline),      # learning tasks; the loop reads no other
                "library": {n: {"definition": str(a.definition), "witness": str(a.witness), "depth": a.depth,
                                "params": [str(p) for p in a.params], "result": str(a.result), "cycle": born.get(n)}
                            for n, a in library.items()}}

    student, programs, score = measure(library, "student0", student_budget, learn)
    absorb(programs)
    solved_now = set(programs)
    measure(library, "report0", student_budget, held)                    # recorded, never read
    last_student = student["run"]
    for cycle in range(1, max_cycles + 1):
        unsolved = every - solved_now
        if not unsolved:
            log(f"cycle {cycle}: every learning task is solved: stop")
            break
        share = min(cap, teacher_ceiling // len(unsolved))
        harvest, taught, _ = measure(library, f"teacher{cycle}", share, learn, only=unsolved)
        absorb(taught)
        started = time.perf_counter()
        dreamer = Dreamer(corpus, family_of, pool)
        gate = dreamer.make(deepen.DREAMS_GATE, f"{cycle}:gate")
        around = dreamer.make(deepen.DREAMS_TARGETS, f"{cycle}:targets", focus=set(corpus) - solved_now)
        extra = around + dreamer.make(deepen.DREAMS_CORPUS - len(around), f"{cycle}:corpus")
        driver_seconds.append(round(time.perf_counter() - started, 1))
        base, _, _ = measure(library, f"dreams{cycle}", student_budget, (), dreams=gate)
        dream_now = base["dream"][0]
        full = dict(corpus)
        full.update({task.name: term for task, _, term, _ in extra})
        accepted, tried, put_off = [], [], set()
        phase, rejects, in_cycle = 1, 0, 0
        while in_cycle < max_trials:
            started = time.perf_counter()
            full.update(corpus)                                   # programs the accepted students added
            banned = tabu | put_off if phase == 1 else tabu
            found = compress.propose(full, library, tabu=frozenset(banned), max_new=1, name_prefix=f"s{trials + 1}_")
            driver_seconds.append(round(time.perf_counter() - started, 1))
            if not found:
                if phase == 1:
                    phase, rejects = 2, 0
                    continue
                break
            symbol = found[0]
            targets = set(corpus) - solved_now
            support = sum(1 for task in symbol.tasks if task in targets)
            if phase == 1 and not support:
                put_off.add(compress.key(symbol))
                continue
            trials += 1
            in_cycle += 1
            candidate = dict(library)
            candidate[symbol.name] = symbol
            new, programs, new_score = measure(candidate, f"student{cycle}.{in_cycle}", student_budget, learn, dreams=gate)
            new["proposed"] = {"name": symbol.name, "definition": str(symbol.definition), "gain": symbol.score,
                               "tasks": len(symbol.tasks), "real_tasks": sum(1 for t in symbol.tasks if t in family_of),
                               "support": sorted(t for t in symbol.tasks if t in family_of),   # learning tasks it folds
                               "support_programs": {t: str(full[t]) for t in sorted(symbol.tasks, key=str)
                                                    if t in family_of},                       # and their programs then
                               "targets": support, "depth": symbol.depth, "phase": phase, "cycle": cycle}
            new["accepted"] = new_score > score or (new_score == score and new["dream"][0] > dream_now)
            tried.append({"trial": trials, "run": new["run"], "phase": phase, "symbol": symbol.name,
                          "accepted": new["accepted"]})
            log(f"     {symbol.name}: {symbol.definition}  gain {symbol.score} tasks {len(symbol.tasks)} targets {support}")
            if new["accepted"]:
                log(f"     accepted (phase {phase}): score {float(score):.3f} -> {float(new_score):.3f}, learn "
                    f"{student['learn']} -> {new['learn']}, dream {dream_now} -> {new['dream'][0]}")
                library, student, score, dream_now = candidate, new, new_score, new["dream"][0]
                absorb(programs)
                solved_now = set(programs)
                last_student = new["run"]
                accepted.append(symbol.name)
                born[symbol.name] = cycle
                rejects = 0
            else:
                log(f"     rejected (phase {phase}): score {float(score):.3f} -> {float(new_score):.3f}, dream "
                    f"{dream_now} -> {new['dream'][0]}")
                tabu.add(compress.key(symbol))
                rejects += 1
                if rejects >= REJECTS:
                    if phase == 2:
                        break
                    phase, rejects = 2, 0
        # ---- the pruning pass: symbols of earlier cycles, least used first -------------------------
        removed, removals = [], []
        if prune:
            fails = 0
            while len(removals) < PRUNES and fails < REJECTS:
                uses = collections.Counter(name for used in student["used"].values() for name in (used or ()))
                waiting = sorted((name for name in library if born.get(name, cycle) < cycle
                                  and name not in {r["symbol"] for r in removals}),
                                 key=lambda name: (uses[name], name))
                if not waiting:
                    break
                name = waiting[0]
                candidate = {n: a for n, a in library.items() if n != name}
                new, programs, new_score = measure(candidate, f"prune{cycle}.{len(removals) + 1}", student_budget, learn,
                                                   dreams=gate)
                new["pruned"] = {"name": name, "uses": uses[name], "cycle": cycle}
                new["accepted"] = new_score > score or (new_score == score and new["dream"][0] >= dream_now)
                removals.append({"run": new["run"], "symbol": name, "uses": uses[name], "accepted": new["accepted"]})
                if new["accepted"]:
                    log(f"     removed {name} (used by {uses[name]} learning programs): score {float(score):.3f} -> "
                        f"{float(new_score):.3f}, learn {student['learn']} -> {new['learn']}, dream {dream_now} -> "
                        f"{new['dream'][0]}")
                    tabu.add(compress.key(library[name]))
                    library, student, score, dream_now = candidate, new, new_score, new["dream"][0]
                    absorb(programs)
                    solved_now = set(programs)
                    last_student = new["run"]
                    removed.append(name)
                    fails = 0
                else:
                    log(f"     kept {name} (used by {uses[name]}): without it score {float(score):.3f} -> "
                        f"{float(new_score):.3f}, dream {dream_now} -> {new['dream'][0]}")
                    fails += 1
        report = None
        if accepted or removed:
            report, _, _ = measure(library, f"report{cycle}", student_budget, held)      # recorded, never read
        cycles.append({"cycle": cycle, "unsolved_before": len(unsolved), "unsolved": sorted(unsolved),
                       "teacher_share": share, "teacher_run": harvest["run"], "taught": len(taught),
                       "dreams": {"gate": len(gate), "targets": len(around), "corpus": len(extra) - len(around)},
                       "dream_programs": {"gate": [[str(term), f, g] for _, _, term, (f, g) in gate],
                                          "corpus": [[str(term), f, g] for _, _, term, (f, g) in extra]},
                       "trials": tried, "accepted": accepted, "removals": removals, "removed": removed,
                       "student_run": last_student,
                       "report_run": report["run"] if report else None, "library": list(library)})
        if checkpoint is not None:
            checkpoint(state(False))
        if not accepted and not removed:
            log(f"cycle {cycle}: nothing accepted and nothing removed: stop")
            break
    return state(True)


if __name__ == "__main__":
    learn = CONFIGS[sys.argv[1]]
    out_path = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 4
    cycles_arg = int(sys.argv[sys.argv.index("--max-cycles") + 1]) if "--max-cycles" in sys.argv else None
    scope_arg = sys.argv[sys.argv.index("--scope") + 1] if "--scope" in sys.argv else "all"
    if "--tiny" in sys.argv:                      # smoke test only
        deepen.STUDENT, deepen.TEACHER, deepen.CAP = 300, 1500, 5000
        deepen.DREAMS_GATE, deepen.DREAMS_CORPUS, deepen.DREAMS_TARGETS, deepen.MAX_TRIALS = 20, 40, 20, 6
    harness = Harness(workers, ALL)
    report = run(harness, learn, scope=scope_arg, prune="--prune" in sys.argv, max_cycles=cycles_arg,
                 checkpoint=lambda partial: json.dump(partial, open(out_path, "w"), indent=1))
    json.dump(report, open(out_path, "w"), indent=1)
    by_run = {t["run"]: t for t in report["timeline"]}
    first, last = by_run[report["student_first"]], by_run[report["student_last"]]
    held = [(t["label"], t["held_out"]) for t in report["timeline"] if t["label"].startswith("report")]
    print(f"\nscope {report['scope']}, prune {report['prune']}; student at {report['student']}: learn {first['learn']} -> "
          f"{last['learn']}, score {first['family_score']} -> {last['family_score']}; held-out by cycle {held}; "
          f"symbols {len(report['library'])}; training ceiling {report['training_ceiling']}, spent "
          f"{report['training_spent']}")
    harness.close()
