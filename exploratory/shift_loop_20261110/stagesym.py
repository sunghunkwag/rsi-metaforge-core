"""Which stages of a two-stage task are a learned symbol (driver side, analysis only).

The verification of Addendum 8 found, after the run, that the lead of the learned vocabulary
sat in the tasks one of whose stages computes the same function as a symbol of the library
(``reverse``, ``append-k``, ...). This module decides that mechanically, so that a later
registration can fix the stratum before its run.

A stage instance (a routine with its parameters) *is a symbol application* when some symbol
of the library, given integer constants from -RANGE to RANGE for its integer parameters and
the input list for its one list parameter, returns the stage's output on every test input on
which the stage is defined: the FRESH input pool and a seeded wide draw. A symbol with no list
parameter, with more than one, or with more than two integer parameters is not considered.

    python stagesym.py <loop report.json> [fresh4|fresh5dev]     counts for a development set
"""
from __future__ import annotations

import itertools
import json
import random
import sys

import fresh3
import fresh4
import oracles
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

RANGE = 12
STEPS = 2000
WIDE = 120


def test_inputs() -> list:
    """The FRESH input pool and a seeded wide draw (the same for every stage)."""
    pool = [list(xs) for xs in fresh3.input_pool()]
    rng = random.Random("stagesym:wide")
    wide = [[]] + [[v] for v in range(-3, 4)]
    wide += [[rng.randint(-15, 15) for _ in range(rng.randint(0, 12))] for _ in range(WIDE)]
    return pool + wide


def same(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def symbol_applications(library: dict, instances) -> dict:
    """stage instance -> [(symbol name, constants)] for the instances that are a symbol
    application. ``library`` is the 'library' of a loop report; ``instances`` are
    (routine, parameters) pairs."""
    reading, _, _ = fresh4.stage_readings()
    inputs = test_inputs()
    symbols = []
    for name, entry in library.items():
        params = entry["params"]
        lists = [i for i, p in enumerate(params) if p == "list[int]"]
        ints = [i for i, p in enumerate(params) if p == "int"]
        if len(lists) != 1 or len(lists) + len(ints) != len(params) or len(ints) > 2:
            continue
        symbols.append((name, parse(entry["witness"]), params, lists[0], ints))
    out = {}
    for routine, parameters in sorted(set((r, tuple(p)) for r, p in instances)):
        if routine not in reading:
            continue
        function = oracles._chain([(routine, list(parameters))], (reading[routine],))
        table = []
        for xs in inputs:
            want = function(list(xs))
            if want is not None and fresh3._kind(want) is not None:
                table.append((xs, want))
        if len(table) < 16:
            continue
        found = []
        for name, term, params, where, ints in symbols:
            for constants in itertools.product(range(-RANGE, RANGE + 1), repeat=len(ints)):
                arguments = [None] * len(params)
                for position, value in zip(ints, constants):
                    arguments[position] = value
                for xs, want in table:
                    arguments[where] = list(xs)
                    got = evaluate(term, tuple(arguments), step_budget=STEPS)
                    if not got.ok or not same(got.value, want):
                        break
                else:
                    found.append((name, list(constants)))
                    break
        if found:
            out[(routine, parameters)] = found
    return out


def stratum(library: dict, tasks) -> dict:
    """task name -> the symbols a stage of the task is an application of ([] when none)."""
    instances = [stage for task in tasks for stage in task.stages]
    table = symbol_applications(library, instances)
    return {task.name: sorted({name for stage in task.stages
                               for name, _ in table.get((stage[0], tuple(stage[1])), [])}) for task in tasks}


if __name__ == "__main__":
    report = json.load(open(sys.argv[1]))
    library = report["loop"]["library"] if "loop" in report else report["library"]
    which = sys.argv[2] if len(sys.argv) > 2 else "fresh4"
    if which == "fresh4":
        tasks = fresh4.make()
    elif which == "fresh5dev":
        import fresh5
        tasks = fresh5.make("development")
    else:
        raise SystemExit("fresh4 or fresh5dev")
    table = symbol_applications(library, [stage for task in tasks for stage in task.stages])
    for (routine, parameters), found in sorted(table.items()):
        print(f"  {routine} {list(parameters)} = " + ", ".join(f"{name} {constants}" for name, constants in found))
    members = stratum(library, tasks)
    listed = [task for task in tasks if task.kind == "list"]
    print(f"{which}: {sum(1 for task in listed if members[task.name])} of {len(listed)} list tasks have a stage that "
          f"is a symbol application ({sum(1 for task in tasks if members[task.name])} of {len(tasks)} tasks)")
