"""FRESH-4: the two-stage tasks FRESH-3 left unused (exploratory, driver side only).

FRESH-3 took 300 of the 3,710 candidate pipelines its rule allows (``fresh3.py``). FRESH-4 is
drawn from the other 3,410 by the same construction under a new seed:

  * the candidates are FRESH-3's (every ordered pair of a first-stage and a second-stage instance
    whose pair of routine names no FRESH-2 task has, each routine with its one validated
    reading), without the pairs that became FRESH-3 tasks, in the order of one seeded shuffle;
  * inputs, the 8 public and 8 hidden examples and the repair of an all-equal public side are
    made exactly as for FRESH-3 (``fresh3.py``), with the task's own seeded generator;
  * a candidate is skipped if fewer than 16 inputs are usable, if it is constant on every usable
    input, if it is the identity on its examples, or if it computes on its 16 inputs what an
    exposed task's reference, a FRESH-3 task or an earlier FRESH-4 task computes;
  * no quota by output type: FRESH-3's quotas used up almost every pipeline with an integer or
    boolean output, so what is left is list outputs with a few others (the registration gives
    the mix);
  * the first COUNT candidates that pass are FRESH-4. The candidates after them are a reserve
    that this module never generates.

The registered set (``SEED``) is run for the first time by the registered run. Smoke tests do
not touch FRESH-4 candidates at all: they use FRESH-3 tasks, which have been run.

    python fresh4.py            the generated set: tallies, mix, digest (no solver is run)
"""
from __future__ import annotations

import json
import random

import fresh3
import oracles
from rsi5 import partitions
from rsi5.dsl.types import BOOL, INT, ListOf, arrows

SEED = "20261111:fresh4:registered"
COUNT = 1000
PUBLIC, HIDDEN = fresh3.PUBLIC, fresh3.HIDDEN


def make(count: int = COUNT, seed: str = SEED, statistics: dict | None = None) -> list:
    """The FRESH-4 tasks for ``seed``, deterministically (``fresh3.Task`` records)."""
    fresh1, fresh2 = partitions.load("fresh1"), partitions.load("fresh2")
    reading = fresh3._readings(fresh1 + fresh2)
    first_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[0]]}
                          | {(r, tuple(p)) for task in fresh1 for r, p in oracles._fresh_steps(task.name)})
    second_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[1]]})
    used_pairs = {tuple(r for r, _ in oracles._fresh_steps(task.name)) for task in fresh2}
    pool = fresh3.input_pool()
    exposed = [(key, functions[0]) for key, (_, functions) in sorted(oracles.references().items()) if functions]
    earlier = fresh3.make()
    if not fresh3.digest(earlier).startswith("4da13e671411da8c"):
        raise RuntimeError("fresh3.make() no longer gives the registered FRESH-3 set")
    taken = {task.name for task in earlier}
    candidates = [(a, b) for a in first_stages for b in second_stages
                  if (a[0], b[0]) not in used_pairs and a[0] in reading and b[0] in reading
                  and "fresh3::" + fresh3._name(a, b) not in taken]
    random.Random(seed).shuffle(candidates)
    tally = {"candidates": len(candidates), "examined": 0, "too few inputs": 0, "mixed output types": 0,
             "constant": 0, "identity": 0, "same function as an exposed task": 0,
             "same function as a FRESH-3 task": 0, "same function as an earlier FRESH-4 task": 0,
             "public outputs repaired": 0}
    made, filled = [], {"list": 0, "int": 0, "bool": 0}
    for first, second in candidates:
        if len(made) >= count:
            break
        tally["examined"] += 1
        steps = [(first[0], list(first[1])), (second[0], list(second[1]))]
        reference = oracles._chain(steps, (reading[first[0]], reading[second[0]]))
        head = oracles._chain(steps[:1], (reading[first[0]],))
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
        name = "fresh4::" + fresh3._name(first, second)
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
        if any(fresh3._same(task.reference, chosen) for task in earlier):
            tally["same function as a FRESH-3 task"] += 1
            continue
        if any(fresh3._same(task.reference, chosen) for task in made):
            tally["same function as an earlier FRESH-4 task"] += 1
            continue
        filled[kind] += 1
        output = {"list": ListOf(INT), "int": INT, "bool": BOOL}[kind]
        examples = tuple(((xs,), value) for xs, value in chosen)
        made.append(fresh3.Task(name, arrows(ListOf(INT), output), examples[:PUBLIC], examples[PUBLIC:], reference,
                                (first, second), kind))
    tally["made"] = len(made)
    tally["by output type"] = filled
    if statistics is not None:
        statistics.update(tally)
    return made


if __name__ == "__main__":
    tally = {}
    tasks = make(statistics=tally)
    print(json.dumps(tally))
    print("digest", fresh3.digest(tasks))
    print("FRESH-4:", json.dumps(fresh3.describe(tasks)), "| with a divisibility-family stage:",
          sum(1 for t in tasks if t.modulo), "| with slice-k-n:", sum(1 for t in tasks if t.stages[0][0] == "slice-k-n"),
          "| first-stage routines:", len({t.stages[0][0] for t in tasks}),
          "| second-stage routines:", len({t.stages[1][0] for t in tasks}),
          "| distinct routine pairs:", len({(t.stages[0][0], t.stages[1][0]) for t in tasks}))
