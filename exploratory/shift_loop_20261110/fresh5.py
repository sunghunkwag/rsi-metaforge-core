"""FRESH-5: two-stage tasks with parameter values no task has had (exploratory, driver side only).

FRESH-3 and FRESH-4 re-pair the stage instances of FRESH-1 and FRESH-2: no routine is new and
no parameter value is new. FRESH-5 keeps the routines and changes the parameters.

  * A *stage instance* is a routine with its parameters. The seen instances are those of
    FRESH-3 and FRESH-4: every first stage of a FRESH-1 or FRESH-2 task, every second stage of a
    FRESH-2 task.
  * A *new instance* is a routine of that role with a parameter tuple in which every position
    holds a value the routine has had at that position in no exposed task of any partition
    (and so in no stage instance). The values of a position come from the range the routine has
    used there, widened by 2 on both sides. A routine without parameters has no new instance.
  * The new instances of every (role, routine) are put in one seeded order and dealt out in
    turn: the first to the development set, the second to the registered set, and so on. The
    two sets therefore share no new instance. Each set takes at most PER_ROUTINE of its
    instances per (role, routine).
  * The candidates of a set are all ordered pairs of a first-stage and a second-stage instance
    in which at least one is a new instance of that set, in the order of one seeded shuffle.
    Inputs, the 8 public and 8 hidden examples, the repair of an all-equal public side and the
    skip rules are those of FRESH-4; a candidate is also skipped if it computes on its 16 inputs
    what a FRESH-4 task, a task of the reserve below, or (for the registered set) a development
    task computes.
  * The registered set has a second part, *pairing only*: the reserve of FRESH-4, that is the
    tasks its generator makes from the candidates after its first 800 tasks (seen instances,
    new pairs of routine names, no pipeline a solver has run on). They come first.

``make("development")`` is for development. ``make("registered")`` is run for the first time by
a registered run: no solver runs on one of its pipelines before that, at any budget. Smoke
tests use other sets.

    python fresh5.py [development|registered]     tallies, mix, digest (no solver is run)
"""
from __future__ import annotations

import collections
import itertools
import random
import sys

import fresh3
import fresh4
import oracles
from rsi5 import partitions
from rsi5.dsl.types import BOOL, INT, ListOf, arrows

SPLIT_SEED = "20261111:fresh5:split"
SEEDS = {"development": "20261111:fresh5:development", "registered": "20261111:fresh5:registered"}
COUNTS = {"development": 300, "registered": 800}
PER_ROUTINE = 3
WIDEN = 2
PUBLIC, HIDDEN = fresh3.PUBLIC, fresh3.HIDDEN


def used_values() -> dict:
    """routine -> position -> the values the routine has had there in any exposed task."""
    used = collections.defaultdict(lambda: collections.defaultdict(set))
    for partition in oracles.ALL:
        for task in partitions.load(partition):
            steps = oracles._fresh_steps(task.name) if task.name.startswith("(") else oracles._corpus_steps(task.name)
            for routine, parameters in steps:
                if routine in oracles.ROUTINES:
                    for position, value in enumerate(parameters):
                        used[routine][position].add(value)
    return used


def stage_sets():
    """(reading, first-stage instances, second-stage instances) as FRESH-4 has them."""
    reading, fresh1, fresh2 = fresh4.stage_readings()
    first = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[0]]}
                   | {(r, tuple(p)) for task in fresh1 for r, p in oracles._fresh_steps(task.name)})
    second = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[1]]})
    return reading, [i for i in first if i[0] in reading], [i for i in second if i[0] in reading]


def new_instances(which: str) -> dict:
    """role -> the new instances of the set ``which`` ('development' or 'registered')."""
    reading, first, second = stage_sets()
    used = used_values()
    out = {}
    for role, seen in (("first", first), ("second", second)):
        chosen = []
        for routine in sorted({r for r, _ in seen}):
            arity = len(next(p for r, p in seen if r == routine))
            if arity == 0 or len(used[routine]) < arity:
                continue
            fresh_values = []
            for position in range(arity):
                low, high = min(used[routine][position]) - WIDEN, max(used[routine][position]) + WIDEN
                fresh_values.append([v for v in range(low, high + 1) if v not in used[routine][position]])
            tuples = sorted(itertools.product(*fresh_values))
            random.Random(f"{SPLIT_SEED}:{role}:{routine}").shuffle(tuples)
            mine = tuples[0::2] if which == "development" else tuples[1::2]
            chosen.extend((routine, parameters) for parameters in mine[:PER_ROUTINE])
        out[role] = sorted(chosen)
    return out


def reserve() -> list:
    """The tasks FRESH-4's generator makes after its first 800: seen instances, new pairings."""
    return fresh4.make(count=10 ** 6)[fresh4.COUNT:]


def make(which: str = "development", count: int | None = None, statistics: dict | None = None) -> list:
    """The tasks of the set ``which`` (``fresh3.Task`` records; ``stages`` hold the instances)."""
    if which not in SEEDS:
        raise ValueError(f"unknown set {which!r}")
    count = COUNTS[which] if count is None else count
    seed = SEEDS[which]
    reading, first, second = stage_sets()
    fresh = new_instances(which)
    pool = fresh3.input_pool()
    exposed = [(key, functions[0]) for key, (_, functions) in sorted(oracles.references().items()) if functions]
    third, fourth, held = fresh3.make(), fresh4.make(), reserve()
    if not fresh4.fresh3.digest(fourth).startswith("6159d55f97e57301"):
        raise RuntimeError("fresh4.make() no longer gives the registered FRESH-4 set")
    before = list(third) + list(fourth) + list(held)
    if which == "registered":
        before += make("development")
    made = list(held) if which == "registered" else []
    new_first, new_second = set(fresh["first"]), set(fresh["second"])
    candidates = [(a, b) for a in sorted(set(first) | new_first) for b in sorted(set(second) | new_second)
                  if a in new_first or b in new_second]
    random.Random(seed).shuffle(candidates)
    tally = {"new first-stage instances": len(new_first), "new second-stage instances": len(new_second),
             "candidates": len(candidates), "examined": 0, "pairing only (the reserve of FRESH-4)": len(made),
             "too few inputs": 0, "mixed output types": 0, "constant": 0, "identity": 0,
             "same function as an exposed task": 0, "same function as an earlier generated task": 0,
             "same function as an earlier task of this set": 0, "public outputs repaired": 0}
    for first_stage, second_stage in candidates:
        if len(made) >= count:
            break
        tally["examined"] += 1
        steps = [(first_stage[0], list(first_stage[1])), (second_stage[0], list(second_stage[1]))]
        reference = oracles._chain(steps, (reading[first_stage[0]], reading[second_stage[0]]))
        head = oracles._chain(steps[:1], (reading[first_stage[0]],))
        usable = []
        for xs, weight in pool.items():
            if fresh3._kind(head(list(xs))) != "list":
                continue
            value = reference(list(xs))
            if fresh3._kind(value) is not None:
                usable.append((list(xs), value, weight))
        if len(usable) < PUBLIC + HIDDEN:
            tally["too few inputs"] += 1
            continue
        if len({repr(value) for _, value, _ in usable}) < 2:
            tally["constant"] += 1
            continue
        name = f"fresh5::{fresh3._name(first_stage, second_stage)}"
        rng = random.Random(f"{seed}:{name}")
        keyed = [(rng.random() ** (1.0 / weight), xs, value) for xs, value, weight in usable]
        order = sorted(keyed, key=lambda item: item[0], reverse=True)
        chosen = [(xs, value) for _, xs, value in order[:PUBLIC + HIDDEN]]
        if len({repr(value) for _, value in chosen[:PUBLIC]}) < 2:
            shown = repr(chosen[0][1])
            position = next(i for i in range(PUBLIC, len(order)) if repr(order[i][2]) != shown)
            if position < PUBLIC + HIDDEN:
                chosen[PUBLIC - 1], chosen[position] = chosen[position], chosen[PUBLIC - 1]
            else:
                chosen[PUBLIC - 1] = (order[position][1], order[position][2])
            tally["public outputs repaired"] += 1
        kinds = {fresh3._kind(value) for _, value in chosen}
        if len(kinds) != 1:
            tally["mixed output types"] += 1
            continue
        kind = kinds.pop()
        if all(value == xs for xs, value in chosen):
            tally["identity"] += 1
            continue
        if any(fresh3._same(other, chosen) for _, other in exposed):
            tally["same function as an exposed task"] += 1
            continue
        if any(fresh3._same(task.reference, chosen) for task in before):
            tally["same function as an earlier generated task"] += 1
            continue
        if any(fresh3._same(task.reference, chosen) for task in made):
            tally["same function as an earlier task of this set"] += 1
            continue
        output = {"list": ListOf(INT), "int": INT, "bool": BOOL}[kind]
        examples = tuple(((xs,), value) for xs, value in chosen)
        made.append(fresh3.Task(name, arrows(ListOf(INT), output), examples[:PUBLIC], examples[PUBLIC:], reference,
                                (first_stage, second_stage), kind))
    tally["made"] = len(made)
    tally["by output type"] = dict(collections.Counter(task.kind for task in made))
    if statistics is not None:
        statistics.update(tally)
    return made


def novelty(tasks, which: str) -> dict:
    """task name -> how many of its two stage instances are new instances of the set (0, 1, 2)."""
    fresh = new_instances(which)
    new_first, new_second = set(fresh["first"]), set(fresh["second"])
    return {task.name: int(task.stages[0] in new_first) + int(task.stages[1] in new_second) for task in tasks}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "development"
    statistics = {}
    tasks = make(which, statistics=statistics)
    print(f"FRESH-5 ({which}): {len(tasks)} tasks, digest {fresh3.digest(tasks)}")
    for key, value in statistics.items():
        print(f"  {key}: {value}")
    print("  " + str(fresh3.describe(tasks)))
    print("  new stage instances per task: " + str(dict(collections.Counter(novelty(tasks, which).values()))))
    fresh = new_instances(which)
    for role in ("first", "second"):
        print(f"  new {role}-stage instances: " + ", ".join(f"{r} {list(p)}" for r, p in fresh[role]))
