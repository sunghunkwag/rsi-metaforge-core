"""The deepening loop with a two-tier vocabulary (exploratory, in development).

``deepen.py`` is the loop registered in Addendum 8 and is not changed. Its run showed where it
stops: every symbol added to the one vocabulary costs the search of 10^4 candidates a task at
its edge, so the gate rejected symbols that only help compositions (among them every symbol the
earlier loop had for the divisibility routines), and the third cycle accepted nothing.

Here a learned symbol lives in one of two tiers.

  * The *library*: every accepted symbol. Only P of the harness uses it: before its scan,
    representation search enumerates programs made of library symbols, the input and constants
    and nothing else. A program that fits is the answer; a program whose image the outputs are
    an element-wise function or a value filter of is tried as a re-representation. A library
    symbol is in no other search, so it costs the other searches nothing.
  * The *core*: the library symbols that are also in the vocabulary of the list space (the scan
    of representation search and the direct search), where a symbol can be a part of a larger
    program and where each one makes every search wider.

Generation 0 has no symbol. P then has nothing to enumerate and spends nothing, so generation 0
is the machinery of Addendum 8 unchanged.

One cycle:
  1. the teacher, as in ``deepen.py``, on the learning tasks the student does not solve. It
     sees every symbol in the list space: it has the budget for it, and a discovery is a
     program that uses a symbol as a part;
  2. dreams as in ``deepen.py``; compression proposes one symbol per trial, targets first;
  3. a proposal is tried in the library. It is accepted when the family-normalised verified
     score of the student on the learning tasks rises, or stays equal while the student solves
     more of the gate dreams (the rule of ``deepen.py``). If that fails it is tried once more in
     the core as well, by the same rule;
  4. after the trials, each symbol the cycle accepted into the library alone is tried in the
     core and promoted when the learning score rises;
  5. the loop stops after a cycle that accepts nothing, or after MAX_CYCLES.

Every decision reads verifier verdicts on learning tasks and the driver's own dreams, nothing
else. The held-out report runs are recorded and never read.

    python deepen3.py <config A|B> <out.json> [workers] [--max-cycles N] [--p-share N] [--tiny]
"""
from __future__ import annotations

import collections
import json
import sys
import time

import compress
import deepen
from deepen import MAX_CYCLES, REJECTS, Dreamer, family_score, input_pool
from hybrid import ALL, Harness, spec_of, summary
from loop import CONFIGS, serialise
from rsi5 import partitions
from rsi5.dsl.terms import term_from_dict
from rsi5.dsl.vocabulary import VOCABULARIES

COMPONENTS = "SCfRP"
P_SHARE = 20                  # P enumerates at most budget // P_SHARE candidates


def spec_tiers(library: dict, core, label: str, budget: int, role: str = "student", p_share: int = P_SHARE,
               components: str = COMPONENTS, vocabulary: str = "restored") -> dict:
    """The harness spec of a library in two tiers. ``role`` 'teacher' puts every symbol in the
    list space; 'student' only the core. The element space never has a learned symbol."""
    abstractions, constants = serialise(library)
    base = VOCABULARIES[vocabulary]
    integers = list(base.integer_constants) + [c for c in constants if c not in base.integer_constants]
    plain = list(base.primitives) + [f"int:{c}" for c in integers]
    names = [name for name, _, _ in abstractions]
    listed = names if role == "teacher" else [name for name in names if name in core]
    spec = spec_of(label, budget, components, abstractions, constants, vocabulary=vocabulary,
                   keep={"elem": plain, "list": plain + listed, "symbols": plain + names})
    spec["p_share"] = p_share
    return spec


def run(harness, learn, *, max_cycles=None, p_share=P_SHARE, log=print, checkpoint=None):
    student_budget, teacher_budget, cap = deepen.STUDENT, deepen.TEACHER, deepen.CAP
    max_trials = deepen.MAX_TRIALS
    max_cycles = MAX_CYCLES if max_cycles is None else max_cycles
    held = tuple(p for p in ALL if p not in learn)
    family_of = {f"{p}/{task.name}": partitions.family(task.name) for p in learn for task in harness.public[p]}
    sizes = collections.Counter(family_of.values())
    every = set(family_of)
    pool = input_pool(harness, learn)
    teacher_ceiling = teacher_budget * len(every)
    library, core, tabu, corpus, timeline, cycles = {}, set(), set(), {}, [], []
    born = {}                                  # symbol name -> the cycle that accepted it
    driver_seconds = []                        # compression and dreaming in the driver: in no budget
    trials = 0

    def measure(lib, tier, label, budget, names, only=None, dreams=(), role="student"):
        started = time.perf_counter()
        result = harness.run(spec_tiers(lib, tier, label, budget, role, p_share), partition_names=list(names),
                             dreams=[(task, check) for task, check, _, _ in dreams], only=only)
        real = {p: rows for p, rows in result.items() if p != "dream"}
        programs = {f"{p}/{row['name']}": term_from_dict(row["term"])
                    for p in learn if p in real for row in real[p] if row["solved"]}
        counts = summary(result)
        jobs = sum(len(rows) for rows in result.values())
        score = family_score(programs, family_of, sizes)
        record = {"run": harness.runs, "label": label, "role": role, "budget": budget, "tasks": jobs,
                  "ceiling": budget * jobs,
                  "learning_tasks": sum(len(rows) for p, rows in real.items() if p in learn),
                  "spent": sum(row["candidates"] for rows in result.values() for row in rows),
                  "counts": counts,
                  "learn": sum(counts[p] for p in learn if p in counts) if any(p in counts for p in learn) else None,
                  "held_out": sum(counts[p] for p in held) if held and all(p in counts for p in held) else None,
                  "family_score": round(float(score), 3), "family_score_exact": [score.numerator, score.denominator],
                  "families_with_a_solve": len({family_of[k] for k in programs}),
                  "dream": [sum(1 for row in result["dream"] if row["solved"]), len(result["dream"])]
                  if "dream" in result else None,
                  "library": list(lib), "core": sorted(tier),
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
            f"lib {len(lib)} core {len(tier)} | {record['seconds']} s")
        return record, programs, score

    def absorb(programs):
        for key, term in programs.items():
            if key not in corpus or compress.size(term) < compress.size(corpus[key]):
                corpus[key] = term

    def state(finished: bool) -> dict:
        return {"learn": list(learn), "held_out": list(held), "components": COMPONENTS, "finished": finished,
                "tiers": True, "p_share": p_share,
                "student": student_budget, "teacher": teacher_budget, "cap": cap,
                "timeline": timeline, "cycles": cycles,
                "student_first": timeline[0]["run"], "student_last": last_student,
                "families": len(sizes), "driver_seconds": driver_seconds,
                "training_ceiling": sum(t["ceiling"] for t in timeline),
                "training_spent": sum(t["spent"] for t in timeline),
                "verdicts_read": sum(t["learning_tasks"] for t in timeline),      # learning tasks; the loop reads no other
                "core": sorted(core),
                "library": {n: {"definition": str(a.definition), "witness": str(a.witness), "depth": a.depth,
                                "params": [str(p) for p in a.params], "result": str(a.result), "cycle": born.get(n),
                                "core": n in core}
                            for n, a in library.items()}}

    student, programs, score = measure(library, core, "student0", student_budget, learn)
    absorb(programs)
    solved_now = set(programs)
    measure(library, core, "report0", student_budget, held)              # recorded, never read
    last_student = student["run"]
    for cycle in range(1, max_cycles + 1):
        unsolved = every - solved_now
        if not unsolved:
            log(f"cycle {cycle}: every learning task is solved: stop")
            break
        share = min(cap, teacher_ceiling // len(unsolved))
        harvest, taught, _ = measure(library, core, f"teacher{cycle}", share, learn, only=unsolved, role="teacher")
        absorb(taught)
        started = time.perf_counter()
        dreamer = Dreamer(corpus, family_of, pool)
        gate = dreamer.make(deepen.DREAMS_GATE, f"{cycle}:gate")
        around = dreamer.make(deepen.DREAMS_TARGETS, f"{cycle}:targets", focus=set(corpus) - solved_now)
        extra = around + dreamer.make(deepen.DREAMS_CORPUS - len(around), f"{cycle}:corpus")
        driver_seconds.append(round(time.perf_counter() - started, 1))
        base, _, _ = measure(library, core, f"dreams{cycle}", student_budget, (), dreams=gate)
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
            log(f"     {symbol.name}: {symbol.definition}  gain {symbol.score} tasks {len(symbol.tasks)} targets {support}")
            taken = None
            for tier in ("library", "core"):
                wider = core | {symbol.name} if tier == "core" else core
                new, programs, new_score = measure(candidate, wider, f"student{cycle}.{in_cycle}{tier[0]}",
                                                   student_budget, learn, dreams=gate)
                new["proposed"] = {"name": symbol.name, "definition": str(symbol.definition), "gain": symbol.score,
                                   "tasks": len(symbol.tasks), "real_tasks": sum(1 for t in symbol.tasks if t in family_of),
                                   "support": sorted(t for t in symbol.tasks if t in family_of),
                                   "support_programs": {t: str(full[t]) for t in sorted(symbol.tasks, key=str)
                                                        if t in family_of},
                                   "targets": support, "depth": symbol.depth, "phase": phase, "cycle": cycle,
                                   "tier": tier}
                new["accepted"] = new_score > score or (new_score == score and new["dream"][0] > dream_now)
                tried.append({"trial": trials, "run": new["run"], "phase": phase, "symbol": symbol.name, "tier": tier,
                              "accepted": new["accepted"]})
                if new["accepted"]:
                    log(f"     accepted in the {tier} (phase {phase}): score {float(score):.3f} -> "
                        f"{float(new_score):.3f}, learn {student['learn']} -> {new['learn']}, dream {dream_now} -> "
                        f"{new['dream'][0]}")
                    library, core, student, score, dream_now = candidate, wider, new, new_score, new["dream"][0]
                    absorb(programs)
                    solved_now = set(programs)
                    last_student = new["run"]
                    accepted.append(symbol.name)
                    born[symbol.name] = cycle
                    taken = tier
                    break
                log(f"     not in the {tier} (phase {phase}): score {float(score):.3f} -> {float(new_score):.3f}, "
                    f"dream {dream_now} -> {new['dream'][0]}")
            if taken is not None:
                rejects = 0
            else:
                tabu.add(compress.key(symbol))
                rejects += 1
                if rejects >= REJECTS:
                    if phase == 2:
                        break
                    phase, rejects = 2, 0
        # ---- promotion: a symbol this cycle put in the library alone is tried in the core ----------
        promotions = []
        for name in [n for n in accepted if n not in core]:
            wider = core | {name}
            new, programs, new_score = measure(library, wider, f"promote{cycle}.{len(promotions) + 1}", student_budget,
                                               learn, dreams=gate)
            new["promotion"] = {"name": name, "cycle": cycle}
            new["accepted"] = new_score > score
            promotions.append({"run": new["run"], "symbol": name, "accepted": new["accepted"]})
            if new["accepted"]:
                log(f"     promoted {name}: score {float(score):.3f} -> {float(new_score):.3f}, learn "
                    f"{student['learn']} -> {new['learn']}, dream {dream_now} -> {new['dream'][0]}")
                core, student, score, dream_now = wider, new, new_score, new["dream"][0]
                absorb(programs)
                solved_now = set(programs)
                last_student = new["run"]
            else:
                log(f"     {name} stays in the library alone: in the core score {float(score):.3f} -> "
                    f"{float(new_score):.3f}")
        report = None
        if accepted:
            report, _, _ = measure(library, core, f"report{cycle}", student_budget, held)    # recorded, never read
        cycles.append({"cycle": cycle, "unsolved_before": len(unsolved), "unsolved": sorted(unsolved),
                       "teacher_share": share, "teacher_run": harvest["run"], "taught": len(taught),
                       "dreams": {"gate": len(gate), "targets": len(around), "corpus": len(extra) - len(around)},
                       "dream_programs": {"gate": [[str(term), f, g] for _, _, term, (f, g) in gate],
                                          "corpus": [[str(term), f, g] for _, _, term, (f, g) in extra]},
                       "trials": tried, "accepted": accepted, "promotions": promotions,
                       "student_run": last_student,
                       "report_run": report["run"] if report else None, "library": list(library), "core": sorted(core)})
        if checkpoint is not None:
            checkpoint(state(False))
        if not accepted:
            log(f"cycle {cycle}: nothing accepted: stop")
            break
    return state(True)


if __name__ == "__main__":
    learn = CONFIGS[sys.argv[1]]
    out_path = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 4
    cycles_arg = int(sys.argv[sys.argv.index("--max-cycles") + 1]) if "--max-cycles" in sys.argv else None
    share_arg = int(sys.argv[sys.argv.index("--p-share") + 1]) if "--p-share" in sys.argv else P_SHARE
    if "--tiny" in sys.argv:                      # smoke test only
        deepen.STUDENT, deepen.TEACHER, deepen.CAP = 300, 1500, 5000
        deepen.DREAMS_GATE, deepen.DREAMS_CORPUS, deepen.DREAMS_TARGETS, deepen.MAX_TRIALS = 20, 40, 20, 6
    harness = Harness(workers, ALL)
    report = run(harness, learn, max_cycles=cycles_arg, p_share=share_arg,
                 checkpoint=lambda partial: json.dump(partial, open(out_path, "w"), indent=1))
    json.dump(report, open(out_path, "w"), indent=1)
    by_run = {t["run"]: t for t in report["timeline"]}
    first, last = by_run[report["student_first"]], by_run[report["student_last"]]
    held = [(t["label"], t["held_out"]) for t in report["timeline"] if t["label"].startswith("report")]
    print(f"\ntiers, P share 1/{report['p_share']}; student at {report['student']}: learn {first['learn']} -> "
          f"{last['learn']}, score {first['family_score']} -> {last['family_score']}; held-out by cycle {held}; "
          f"symbols {len(report['library'])}, of them in the core {len(report['core'])}; training ceiling "
          f"{report['training_ceiling']}, spent {report['training_spent']}")
    harness.close()
