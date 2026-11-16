"""FRESH-4: two-stage tasks on routine pairs no earlier set has (exploratory, driver side only).

FRESH-3 took 300 of the 3,710 candidate pipelines its rule allows (``fresh3.py``) and has since
been used for development. FRESH-4 is drawn from the others by the same construction under a
new seed, and keeps its distance from everything that has been run:

  * the candidates are FRESH-3's (every ordered pair of a first-stage and a second-stage instance,
    each routine with its one validated reading) without
      - every pair whose two routine names are the routine names of a FRESH-2 task or of a
        FRESH-3 task (FRESH-3 excluded FRESH-2's pairs; this set excludes both);
      - every pipeline a solver has run on at any budget: the registered FRESH-3 tasks, the
        60-task smoke set of Addendum 7 and the 300 pipelines of its discarded draft set
        (``fresh3_draft_pipelines.json``);
    in the order of one seeded shuffle;
  * inputs, the 8 public and 8 hidden examples and the repair of an all-equal public side are
    made exactly as for FRESH-3, with the task's own seeded generator;
  * a candidate is skipped if fewer than 16 inputs are usable, if it is constant on every usable
    input, if it is the identity on its examples, or if it computes on its 16 inputs what an
    exposed task's reference, a FRESH-3 task or an earlier FRESH-4 task computes;
  * no quota by output type: FRESH-3's quotas used up almost every pipeline with an integer or
    boolean output, so what is left is list outputs with a few others (the registration gives
    the mix);
  * the first COUNT candidates that pass are FRESH-4. The candidates after them are a reserve
    that this module never generates.

The registered set (``SEED``) is run for the first time by the registered run. Smoke tests do
not touch a FRESH-4 candidate: they use FRESH-3 tasks, which have been run.

    python fresh4.py            the generated set: tallies, mix, digest (no solver is run)
"""
from __future__ import annotations

import json
import os
import random

import fresh3
import oracles
from rsi5 import partitions
from rsi5.dsl.types import BOOL, INT, ListOf, arrows

SEED = "20261111:fresh4:registered-2"
COUNT = 800
PUBLIC, HIDDEN = fresh3.PUBLIC, fresh3.HIDDEN
DRAFT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fresh3_draft_pipelines.json")


def stage_readings():
    """(the one validated reading of every routine, FRESH-1 tasks, FRESH-2 tasks)."""
    fresh1, fresh2 = partitions.load("fresh1"), partitions.load("fresh2")
    return fresh3._readings(fresh1 + fresh2), fresh1, fresh2


def make(count: int = COUNT, seed: str = SEED, statistics: dict | None = None) -> list:
    """The FRESH-4 tasks for ``seed``, deterministically (``fresh3.Task`` records)."""
    reading, fresh1, fresh2 = stage_readings()
    first_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[0]]}
                          | {(r, tuple(p)) for task in fresh1 for r, p in oracles._fresh_steps(task.name)})
    second_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[1]]})
    pool = fresh3.input_pool()
    exposed = [(key, functions[0]) for key, (_, functions) in sorted(oracles.references().items()) if functions]
    earlier = fresh3.make()
    if not fresh3.digest(earlier).startswith("4da13e671411da8c"):
        raise RuntimeError("fresh3.make() no longer gives the registered FRESH-3 set")
    used_pairs = {tuple(r for r, _ in oracles._fresh_steps(task.name)) for task in fresh2}
    used_pairs |= {(task.stages[0][0], task.stages[1][0]) for task in earlier}
    run_before = {task.name.split("::", 1)[1] for task in earlier}
    run_before |= {task.name.split("::", 1)[1] for task in fresh3.make(60, fresh3.SMOKE_SEED)}
    run_before |= set(json.load(open(DRAFT))["pipelines"])
    everything = [(a, b) for a in first_stages for b in second_stages if a[0] in reading and b[0] in reading]
    candidates = [(a, b) for a, b in everything
                  if (a[0], b[0]) not in used_pairs and fresh3._name(a, b) not in run_before]
    random.Random(seed).shuffle(candidates)
    tally = {"pairs of stage instances": len(everything), "candidates": len(candidates), "examined": 0,
             "too few inputs": 0, "mixed output types": 0, "constant": 0, "identity": 0,
             "same function as an exposed task": 0, "same function as a FRESH-3 task": 0,
             "same function as an earlier FRESH-4 task": 0, "public outputs repaired": 0}
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


def provenance(tasks) -> dict:
    """What each task shares with the learning tasks of configuration B, from references alone.

    A stage instance *is a learning task* when its function under the validated reading equals
    the validated reference of a learning task on every input of the FRESH input pool. A routine
    *has a learning task* when some learning task is of its family. Returns, per task name,
    ``{"stages": how many of its two stage instances are learning tasks (0, 1 or 2),
       "first": is the first one, "unmet": the stage routines no learning task has}``."""
    from loop import CONFIGS
    learn = CONFIGS["B"]
    reading, _, _ = stage_readings()
    pool = [list(xs) for xs in fresh3.input_pool()]

    def behaviour(function):
        out = []
        for xs in pool:
            try:
                value = function(list(xs))
            except Exception:
                value = None
            out.append(repr(value) if value is not None and fresh3._kind(value) is not None else None)
        return tuple(out)

    learnt, families = set(), set()
    for key, (_, functions) in sorted(oracles.references().items()):
        partition, name = key.split("/", 1)
        if partition in learn:
            families.add(partitions.family(name))
            learnt.update(behaviour(function) for function in functions)
    cache, table = {}, {}
    for task in tasks:
        flags = []
        for routine, parameters in task.stages:
            instance = (routine, tuple(parameters))
            if instance not in cache:
                cache[instance] = behaviour(oracles._chain([(routine, list(parameters))], (reading[routine],))) in learnt
            flags.append(cache[instance])
        table[task.name] = {"stages": sum(flags), "first": flags[0],
                            "unmet": sorted({routine for routine, _ in task.stages if routine not in families})}
    return table


if __name__ == "__main__":
    tally = {}
    tasks = make(statistics=tally)
    print(json.dumps(tally))
    print("digest", fresh3.digest(tasks))
    table = provenance(tasks)
    print("FRESH-4:", json.dumps(fresh3.describe(tasks)), "| with a divisibility-family stage:",
          sum(1 for t in tasks if t.modulo), "| with slice-k-n:", sum(1 for t in tasks if t.stages[0][0] == "slice-k-n"),
          "| first-stage routines:", len({t.stages[0][0] for t in tasks}),
          "| second-stage routines:", len({t.stages[1][0] for t in tasks}),
          "| distinct routine pairs:", len({(t.stages[0][0], t.stages[1][0]) for t in tasks}))
    print("stage instances that are learning tasks: both", sum(1 for v in table.values() if v["stages"] == 2),
          "| one", sum(1 for v in table.values() if v["stages"] == 1),
          "| none", sum(1 for v in table.values() if v["stages"] == 0),
          "| first stage is one:", sum(1 for v in table.values() if v["first"]),
          "| with a routine no learning task has:", sum(1 for v in table.values() if v["unmet"]),
          sorted({r for v in table.values() for r in v["unmet"]}))
    print("list outputs by provenance:", {n: sum(1 for t in tasks if t.kind == "list" and table[t.name]["stages"] == n)
                                           for n in (2, 1, 0)})
