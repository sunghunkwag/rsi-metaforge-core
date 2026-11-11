"""Deepening expert iteration with dream compositions (exploratory, report-only).

``expert.py`` with four changes, each taken from the failure analysis of the replication
(README, "Registered replication"; the loop there never solved 60 of its 214 learning tasks and
its lead stayed inside the routines its nine symbols encode):

  * The teacher's budget goes where the student fails. A teacher run has the ceiling it had
    before (TEACHER candidates for every learning task), but it is spent on the learning tasks
    the current student does not solve, in equal shares of at most CAP candidates each.
  * Reuse is counted on the loop's own compositions. Verified programs of learning tasks are
    composed in pairs, balanced over routine families, into dream programs (``g after f``).
    Compression runs over the real programs together with a sample of dream programs, so a
    routine the loop solved once is proposed as a symbol when its compositions repeat it. Half
    of that sample is built around the *targets*: learning tasks that have a verified program
    (a teacher's) which the student cannot find. The two-family screen of ``expert.py`` is gone.
  * Symbols are tried one at a time, so none rides on another, and those that a target's
    program uses are tried first: only they can turn a teacher's solution into a student's.
  * Real verdicts decide first. A symbol is accepted when the family-normalised verified score
    of the student on the learning tasks rises, or when it stays equal and the student solves
    more tasks of a second, disjoint sample of dreams. No dream gain pays for a real loss.

One cycle:
  1. a teacher run on the unsolved learning tasks with the current vocabulary;
  2. two dream samples from the corpus (gate, corpus); the current vocabulary on the gate sample;
  3. trials. Each trial takes the proposal with the largest description-length gain over the
     real programs and the corpus sample, adds it to the vocabulary and runs the student on the
     learning tasks and the gate sample. First phase: proposals that no target's program uses
     are put off; the phase ends when none is left or REJECTS trials in a row fail. Second
     phase: every remaining proposal in order of gain, until REJECTS trials in a row fail. At
     most MAX_TRIALS trials per cycle. A rejected symbol is never proposed again;
  4. the student on the held-out partitions, recorded and never read.
The loop stops after a cycle that accepts nothing, or after MAX_CYCLES.

A dream is built from verified programs of learning tasks and from public example inputs of
learning tasks. Held-out partitions, and any partition added to the harness later, are never
consulted: no decision of the loop reads a record of theirs.

    python deepen.py <config A|B> <out.json> [workers] [--max-cycles N] [--tiny]
"""
from __future__ import annotations

import collections
from fractions import Fraction
import json
import random
import sys
import time

import compress
import dream
import hybrid
from hybrid import ALL, Harness, spec_of, summary
from loop import CONFIGS, serialise
from rsi5 import partitions
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.terms import Lam, term_from_dict
from rsi5.dsl.types import INT, ListOf, infer

STUDENT, TEACHER, CAP = 10_000, 100_000, 1_000_000
COMPONENTS = "SCfR"
REJECTS, MAX_TRIALS, MAX_CYCLES = 3, 24, 12
DREAMS_GATE, DREAMS_CORPUS, DREAMS_TARGETS = 100, 300, 150
POOL, PUBLIC, CHECK, ROUNDS = 300, 8, 8, 6
VALUE_CAP, LENGTH_CAP = 10 ** 6, 100
SEED = "20261111:deepen"
LIST_INT = ListOf(INT)


def family_score(solved, family_of, sizes) -> Fraction:
    hits = collections.Counter(family_of[key] for key in solved if key in family_of)
    return sum((Fraction(hits[family], size) for family, size in sizes.items()), Fraction(0))


# ---- dream compositions ------------------------------------------------------------------------
def input_pool(harness, learn, size: int = POOL) -> list:
    """A seeded sample of the public example inputs of the learning tasks (lists of integers)."""
    seen = sorted({tuple(example[0][0]) for p in learn for task in harness.public[p]
                   for example in task.examples
                   if len(example[0]) == 1 and isinstance(example[0][0], list)
                   and all(type(v) is int for v in example[0][0])})
    random.Random(f"{SEED}:pool").shuffle(seen)
    return [list(xs) for xs in seen[:size]]


def _usable(value) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, int):
        return abs(value) <= VALUE_CAP
    return isinstance(value, list) and len(value) <= LENGTH_CAP and all(
        type(v) in (int, bool) and abs(v) <= VALUE_CAP for v in value)


def _behaviour(term, pool) -> tuple:
    """The value on every pool input, None where the program fails or leaves the usable range."""
    out = []
    for xs in pool:
        result = evaluate(term, (xs,), step_budget=hybrid.STEPS)
        out.append(result.value if result.ok and _usable(result.value) else None)
    return tuple(out)


class Dreamer:
    """Dream compositions ``g after f`` of the verified programs in ``programs`` (key -> closed
    term over one list input), balanced over pairs of routine families.

    One round visits each pair (family of f, family of g) once, in a seeded order, and draws
    one program from each family. With ``focus`` (a set of keys) every pair of a round has a
    focus program on one side: f from a focus family with any g, and any f with g from a focus
    family. A composition is kept when it is defined on at least PUBLIC + CHECK pool inputs, is
    not constant there, differs from f, from g and from the identity on its examples, and
    behaves on the pool like no corpus program and no earlier dream of this Dreamer."""

    def __init__(self, programs: dict, family_of: dict, pool: list):
        self.programs, self.pool = programs, pool
        self.result, self.behaviour = {}, {}
        for key in sorted(programs):
            parts = dream._typed(programs[key])
            if parts is None or len(parts[0]) != 1 or parts[0][0] != LIST_INT:
                continue
            self.result[key] = parts[1]
            self.behaviour[key] = _behaviour(programs[key], pool)
        self.taken = {repr(values) for values in self.behaviour.values()}
        self.inner, self.outer = collections.defaultdict(list), collections.defaultdict(list)
        for key, result in self.result.items():
            self.outer[family_of[key]].append(key)
            if result == LIST_INT:
                self.inner[family_of[key]].append(key)

    def _round(self, rng, focus):
        if focus is None:
            pairs = [(a, b) for a in sorted(self.inner) for b in sorted(self.outer)]
            rng.shuffle(pairs)
            for a, b in pairs:
                yield rng.choice(self.inner[a]), rng.choice(self.outer[b])
            return
        inner = {a: [k for k in keys if k in focus] for a, keys in self.inner.items()}
        outer = {b: [k for k in keys if k in focus] for b, keys in self.outer.items()}
        pairs = [("f", a, b) for a in sorted(inner) if inner[a] for b in sorted(self.outer)]
        pairs += [("g", a, b) for a in sorted(self.inner) for b in sorted(outer) if outer[b]]
        rng.shuffle(pairs)
        for side, a, b in pairs:
            if side == "f":
                yield rng.choice(inner[a]), rng.choice(self.outer[b])
            else:
                yield rng.choice(self.inner[a]), rng.choice(outer[b])

    def make(self, count: int, tag: str, focus=None) -> list:
        """Up to ``count`` new dreams: [(public task, check examples, term, (f key, g key))]."""
        rng = random.Random(f"{SEED}:{tag}")
        pool, made = self.pool, []
        for _ in range(ROUNDS):
            for f, g in self._round(rng, focus):
                if len(made) >= count:
                    return made
                if f == g:
                    continue
                term = Lam(LIST_INT, hybrid.beta(self.programs[g], [self.programs[f].children[0]]))
                if dream._typed(term) is None:
                    continue
                values = _behaviour(term, pool)
                signature = repr(values)
                if signature in self.taken:
                    continue
                usable = [i for i, value in enumerate(values) if value is not None]
                if len(usable) < PUBLIC + CHECK or len({repr(values[i]) for i in usable}) < 2:
                    continue
                chosen = None
                for _attempt in range(4):
                    draw = rng.sample(usable, PUBLIC + CHECK)
                    if len({repr(values[i]) for i in draw[:PUBLIC]}) >= 2:
                        chosen = draw
                        break
                if chosen is None:
                    continue
                if all(values[i] == pool[i] for i in chosen) \
                        or all(values[i] == self.behaviour[f][i] for i in chosen) \
                        or all(values[i] == self.behaviour[g][i] for i in chosen):
                    continue
                self.taken.add(signature)
                examples = tuple(((list(pool[i]),), values[i]) for i in chosen)
                task = partitions.PublicTask(f"dream:{tag}:{len(made)}", infer(term).to_dict(), examples[:PUBLIC])
                made.append((task, list(examples[PUBLIC:]), term, (f, g)))
        return made


# ---- the loop ---------------------------------------------------------------------------------
def run(harness, learn, *, max_cycles=None, components=COMPONENTS, log=print, checkpoint=None):
    max_cycles = MAX_CYCLES if max_cycles is None else max_cycles
    held = tuple(p for p in ALL if p not in learn)
    family_of = {f"{p}/{task.name}": partitions.family(task.name) for p in learn for task in harness.public[p]}
    sizes = collections.Counter(family_of.values())
    every = set(family_of)
    pool = input_pool(harness, learn)
    teacher_ceiling = TEACHER * len(every)
    library, tabu, corpus, timeline, cycles = {}, set(), {}, [], []
    driver_seconds = []                        # compression and dreaming in the driver: in no budget
    trials = 0

    def measure(lib, label, budget, names, only=None, dreams=()):
        abstractions, constants = serialise(lib)
        started = time.perf_counter()
        result = harness.run(spec_of(label, budget, components, abstractions, constants),
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
                "student": STUDENT, "teacher": TEACHER, "cap": CAP,
                "timeline": timeline, "cycles": cycles,
                "student_first": timeline[0]["run"], "student_last": last_student,
                "families": len(sizes), "driver_seconds": driver_seconds,
                "training_ceiling": sum(t["ceiling"] for t in timeline),
                "training_spent": sum(t["spent"] for t in timeline),
                "verdicts_read": sum(t["learning_tasks"] for t in timeline),      # learning tasks; the loop reads no other
                "library": {n: {"definition": str(a.definition), "witness": str(a.witness), "depth": a.depth,
                                "params": [str(p) for p in a.params], "result": str(a.result)}
                            for n, a in library.items()}}

    student, programs, score = measure(library, "student0", STUDENT, learn)
    absorb(programs)
    solved_now = set(programs)
    measure(library, "report0", STUDENT, held)                    # recorded, never read
    last_student = student["run"]
    for cycle in range(1, max_cycles + 1):
        unsolved = every - solved_now
        if not unsolved:
            log(f"cycle {cycle}: every learning task is solved: stop")
            break
        share = min(CAP, teacher_ceiling // len(unsolved))
        harvest, taught, _ = measure(library, f"teacher{cycle}", share, learn, only=unsolved)
        absorb(taught)
        started = time.perf_counter()
        dreamer = Dreamer(corpus, family_of, pool)
        gate = dreamer.make(DREAMS_GATE, f"{cycle}:gate")
        around = dreamer.make(DREAMS_TARGETS, f"{cycle}:targets", focus=set(corpus) - solved_now)
        extra = around + dreamer.make(DREAMS_CORPUS - len(around), f"{cycle}:corpus")
        driver_seconds.append(round(time.perf_counter() - started, 1))
        base, _, _ = measure(library, f"dreams{cycle}", STUDENT, (), dreams=gate)
        dream_now = base["dream"][0]
        full = dict(corpus)
        full.update({task.name: term for task, _, term, _ in extra})
        accepted, tried, put_off = [], [], set()
        phase, rejects, in_cycle = 1, 0, 0
        while in_cycle < MAX_TRIALS:
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
            new, programs, new_score = measure(candidate, f"student{cycle}.{in_cycle}", STUDENT, learn, dreams=gate)
            new["proposed"] = {"name": symbol.name, "definition": str(symbol.definition), "gain": symbol.score,
                               "tasks": len(symbol.tasks), "real_tasks": sum(1 for t in symbol.tasks if t in family_of),
                               "support": sorted(t for t in symbol.tasks if t in family_of),   # learning tasks it folds
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
        report = None
        if accepted:
            report, _, _ = measure(library, f"report{cycle}", STUDENT, held)      # recorded, never read
        cycles.append({"cycle": cycle, "unsolved_before": len(unsolved), "unsolved": sorted(unsolved),
                       "teacher_share": share, "teacher_run": harvest["run"], "taught": len(taught),
                       "dreams": {"gate": len(gate), "targets": len(around), "corpus": len(extra) - len(around)},
                       "dream_programs": {"gate": [[str(term), f, g] for _, _, term, (f, g) in gate],
                                          "corpus": [[str(term), f, g] for _, _, term, (f, g) in extra]},
                       "trials": tried, "accepted": accepted, "student_run": last_student,
                       "report_run": report["run"] if report else None, "library": list(library)})
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
    if "--tiny" in sys.argv:                      # smoke test only
        STUDENT, TEACHER, CAP, DREAMS_GATE, DREAMS_CORPUS, DREAMS_TARGETS, MAX_TRIALS = 300, 1500, 5000, 20, 40, 20, 6
    harness = Harness(workers, ALL)
    report = run(harness, learn, max_cycles=cycles_arg,
                 checkpoint=lambda partial: json.dump(partial, open(out_path, "w"), indent=1))
    json.dump(report, open(out_path, "w"), indent=1)
    by_run = {t["run"]: t for t in report["timeline"]}
    first, last = by_run[report["student_first"]], by_run[report["student_last"]]
    held = [(t["label"], t["held_out"]) for t in report["timeline"] if t["label"].startswith("report")]
    print(f"\nstudent at {STUDENT}: learn {first['learn']} -> {last['learn']}, score {first['family_score']} -> "
          f"{last['family_score']}; held-out by cycle {held}; symbols {len(report['library'])}; "
          f"training ceiling {report['training_ceiling']}, spent {report['training_spent']}")
    harness.close()
