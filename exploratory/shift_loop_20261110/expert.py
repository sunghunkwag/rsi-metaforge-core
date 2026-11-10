"""Expert iteration over the vocabulary (exploratory, report-only).

Three principles are taken from Terminal-RSI (arXiv:2610.22192), none of its code:
  * successes of a stronger harness become supervision after screening and fresh verification
    (their Recursive Self-Rewrite): programs harvested by the same machinery at a teacher
    budget are compressed into symbols, and a symbol is kept only if tasks of at least two
    families support it;
  * a full solve is worth about one in every family (their Family Dense Reward): the gate is
    the sum over learning families of the fraction of the family verified;
  * every failure scores below every success (their Success-Prioritized Reward): only verified
    solves enter the gate, no partial credit.

Cycle k: harvest with the current vocabulary at the teacher budget on the learning partitions;
distil up to three screened symbols; run the candidate vocabulary at the student budget on
every task and accept it only if the family-normalised verified score on the learning
partitions rises. Held-out partitions are recorded and never consulted.

Compounding would show as the harvest itself growing from cycle to cycle.

    python expert.py <config A|B> <out.json> [workers] [--max-cycles N] [--no-screen]
"""
from __future__ import annotations

import collections
import json
import sys
import time

import compress
from hybrid import ALL, Harness, spec_of, summary
from loop import CONFIGS, serialise
from rsi5 import partitions
from rsi5.dsl.terms import term_from_dict

STUDENT, TEACHER = 10_000, 100_000
COMPONENTS = "SCf"
PER_CYCLE, MAX_CYCLES, MIN_FAMILIES, RETRIES = 3, 6, 2, 2


def family_score(solved, family_of, sizes) -> float:
    hits = collections.Counter(family_of[key] for key in solved if key in family_of)
    return sum(hits[family] / size for family, size in sizes.items())


def run(harness, learn, max_cycles=MAX_CYCLES, screen=True, log=print):
    held = tuple(p for p in ALL if p not in learn)
    family_of = {f"{p}/{task.name}": partitions.family(task.name) for p in learn for task in harness.public[p]}
    sizes = collections.Counter(family_of.values())
    library, tabu, corpus, timeline, screened_out = {}, set(), {}, [], []
    executions = {"student": 0, "teacher": 0}

    def measure(lib, label, budget, names):
        abstractions, constants = serialise(lib)
        started = time.perf_counter()
        result = harness.run(spec_of(label, budget, COMPONENTS, abstractions, constants), partition_names=list(names))
        programs = {f"{p}/{row['name']}": term_from_dict(row["term"])
                    for p in learn if p in result for row in result[p] if row["solved"]}
        counts = summary(result)
        record = {"run": harness.runs, "label": label, "budget": budget, "counts": counts,
                  "learn": sum(counts[p] for p in learn),
                  "held_out": sum(counts[p] for p in held if p in counts) if set(held) <= set(counts) else None,
                  "family_score": round(family_score(programs, family_of, sizes), 3),
                  "families_with_a_solve": len({family_of[k] for k in programs}),
                  "library": list(lib),
                  "solved": sorted(f"{p}/{r['name']}" for p, rows in result.items() for r in rows if r["solved"]),
                  "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                               for p, rows in result.items() for r in rows if r["solved"]},
                  "seconds": round(time.perf_counter() - started)}
        timeline.append(record)
        log(f"run {harness.runs:2d} {label:14s} budget {budget:>6} learn {record['learn']:3d} "
            f"families {record['families_with_a_solve']:2d}/{len(sizes)} score {record['family_score']:6.2f} "
            f"held-out {record['held_out']} {counts} lib {len(lib)} | {record['seconds']} s")
        return record, programs

    def absorb(programs):
        for key, term in programs.items():
            if key not in corpus or compress.size(term) < compress.size(corpus[key]):
                corpus[key] = term

    def propose(lib, cycle):
        kept, trial, banned = [], dict(lib), set(tabu)
        for _ in range(60):
            if len(kept) >= PER_CYCLE:
                break
            found = compress.propose(corpus, trial, tabu=frozenset(banned), max_new=1, name_prefix=f"c{cycle}_")
            if not found:
                break
            a = found[0]
            families = sorted({family_of[t] for t in a.tasks if t in family_of})
            if screen and len(families) < MIN_FAMILIES:
                banned.add(compress.key(a))
                tabu.add(compress.key(a))
                screened_out.append({"cycle": cycle, "definition": str(a.definition), "score": a.score,
                                     "tasks": len(a.tasks), "families": families})
                continue
            log(f"     symbol {a.name}: {a.definition}  score {a.score} tasks {len(a.tasks)} families {len(families)}")
            kept.append(a)
            trial[a.name] = a
        return kept

    current, programs = measure(library, "student0", STUDENT, ALL)
    executions["student"] += 1
    absorb(programs)
    harvests = []
    for cycle in range(1, max_cycles + 1):
        harvest, taught = measure(library, f"teacher{cycle - 1}", TEACHER, learn)
        executions["teacher"] += 1
        harvests.append(harvest)
        absorb(taught)
        accepted = False
        for attempt in range(1, RETRIES + 1):
            proposals = propose(library, cycle)
            if not proposals:
                break
            candidate = dict(library)
            candidate.update({a.name: a for a in proposals})
            new, programs = measure(candidate, f"student{cycle}.{attempt}", STUDENT, ALL)
            executions["student"] += 1
            new["proposed"] = [{"name": a.name, "definition": str(a.definition), "score": a.score,
                                "tasks": len(a.tasks), "depth": a.depth} for a in proposals]
            new["accepted"] = new["family_score"] > current["family_score"]
            if new["accepted"]:
                log(f"     accepted: score {current['family_score']} -> {new['family_score']}, learn {current['learn']} -> "
                    f"{new['learn']}, held-out {current['held_out']} -> {new['held_out']}")
                library, current, accepted = candidate, new, True
                absorb(programs)
                break
            tabu.update(compress.key(a) for a in proposals)
        if not accepted:
            log(f"cycle {cycle}: nothing accepted: stop")
            break
    final, _ = measure(library, "teacher_final", TEACHER, learn)
    executions["teacher"] += 1
    harvests.append(final)
    learn_tasks = sum(len(harness.public[p]) for p in learn)
    cumulative = (executions["student"] * 338 * STUDENT + executions["teacher"] * learn_tasks * TEACHER) / 338
    return {"learn": list(learn), "held_out": list(held), "screen": screen, "timeline": timeline,
            "student_first": timeline[0]["run"], "student_last": current["run"],
            "harvest_learn": [h["learn"] for h in harvests],
            "harvest_families": [h["families_with_a_solve"] for h in harvests],
            "harvest_family_score": [h["family_score"] for h in harvests],
            "families": len(sizes), "screened_out": screened_out, "executions": executions,
            "equal_budget_per_real_task": round(cumulative),
            "library": {n: {"definition": str(a.definition), "witness": str(a.witness), "depth": a.depth,
                            "params": [str(p) for p in a.params], "result": str(a.result)} for n, a in library.items()}}


if __name__ == "__main__":
    learn = CONFIGS[sys.argv[1]]
    out_path = sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 4
    max_cycles = int(sys.argv[sys.argv.index("--max-cycles") + 1]) if "--max-cycles" in sys.argv else MAX_CYCLES
    if "--tiny" in sys.argv:                      # smoke test only
        STUDENT, TEACHER = 300, 1500
    harness = Harness(workers, ALL)
    report = run(harness, learn, max_cycles=max_cycles, screen="--no-screen" not in sys.argv)
    json.dump(report, open(out_path, "w"), indent=1)
    by_run = {t["run"]: t for t in report["timeline"]}
    first, last = by_run[report["student_first"]], by_run[report["student_last"]]
    print(f"\nstudent at {STUDENT}: learn {first['learn']} -> {last['learn']}, families {first['families_with_a_solve']} -> "
          f"{last['families_with_a_solve']} of {report['families']}, score {first['family_score']} -> {last['family_score']}, "
          f"held-out {first['held_out']} -> {last['held_out']}")
    print(f"teacher at {TEACHER}: learn {report['harvest_learn']}, families {report['harvest_families']}; "
          f"screened out {len(report['screened_out'])}; equal budget per real task {report['equal_budget_per_real_task']}")
    harness.close()
