"""FRESH-3: two-stage tasks no run of this study has seen (exploratory, driver side only).

FRESH-2 is 100 pipelines of two list routines. FRESH-3 is 300 more, drawn by a fixed seeded
rule from the same routines, generated only after the mechanism under test was frozen. No loop
decision and no design decision has read a FRESH-3 outcome at a real budget.

The rule (registered in PREDICTIONS.md, Addendum 7):
  * stage-1 instances: every (routine, parameters) that is the first stage of a FRESH-2 task or
    a FRESH-1 task; stage-2 instances: every second stage of a FRESH-2 task;
  * a routine is used with the one reading of its name that reproduces every FRESH task it
    occurs in (``oracles.py``); a routine with no such single reading is left out;
  * candidates are all ordered pairs that are not a FRESH-2 task, in the order of one seeded
    shuffle; a candidate is taken unless it fails one of the tests in ``make``;
  * inputs are public example inputs of FRESH-1 and FRESH-2 tasks (never a hidden one), 16 per
    task by a seeded draw among those the pipeline is defined on: 8 public, 8 hidden.

The reference function of a task is kept in the driver for the audit. A worker receives the
public examples only, like any other task.

    python fresh3.py            the generated set: counts by output type and by rejection reason
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
import json
import random

import oracles
from rsi5 import partitions
from rsi5.dsl.types import BOOL, INT, ListOf, arrows

SEED = "20261110:fresh3"
COUNT = 300
PUBLIC, HIDDEN = 8, 8
VALUE_CAP = 10 ** 6
LENGTH_CAP = 100


@dataclass(frozen=True)
class Task:
    name: str
    request: object          # an rsi5 Type
    examples: tuple          # public: ((inputs, output), ...)
    hidden: tuple
    reference: object        # the generating function; never sent to a worker
    stages: tuple            # ((routine, parameters), (routine, parameters))

    def public_view(self):
        return partitions.PublicTask(self.name, self.request.to_dict(), self.examples)


def _name(first, second) -> str:
    def stage(position, routine, parameters):
        return "(" + " ".join([routine, f"(dyn . {position})"] + [f"(static . {p})" for p in parameters]) + ")"
    return "(" + stage(0, *first) + " " + stage(1, *second) + ")"


def _readings(fresh_tasks) -> dict:
    """routine -> the index of the one reading valid in every FRESH task that uses it (absent
    when no single reading is)."""
    valid = {}
    for task in fresh_tasks:
        steps = oracles._fresh_steps(task.name)
        examples = list(task.examples) + list(task.hidden)
        choices = []
        for choice in itertools.product(*[range(len(oracles.ROUTINES[routine])) for routine, _ in steps]):
            function = oracles._chain(steps, choice)
            try:
                if all(function(list(i[0])) == o and type(function(list(i[0]))) is type(o) for i, o in examples):
                    choices.append(choice)
            except Exception:
                continue
        for position, (routine, _) in enumerate(steps):
            valid.setdefault(routine, []).append({choice[position] for choice in choices})
    single = {}
    for routine, sets in valid.items():
        common = set.intersection(*sets)
        if len(common) == 1:
            single[routine] = common.pop()
    return single


def _kind(value):
    """'list', 'int' or 'bool' for a usable output, else None."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int" if abs(value) <= VALUE_CAP else None
    if isinstance(value, list) and len(value) <= LENGTH_CAP and \
            all(type(v) is int and abs(v) <= VALUE_CAP for v in value):
        return "list"
    return None


def _same(function, examples) -> bool:
    """True when ``function`` gives every output of ``examples`` (it may be undefined elsewhere)."""
    try:
        return all(function(list(xs)) == value and type(function(list(xs))) is type(value) for xs, value in examples)
    except Exception:
        return False


def make(count: int = COUNT, statistics: dict | None = None) -> list:
    """The FRESH-3 tasks, deterministically. ``statistics`` (a dict) receives the tallies."""
    fresh1, fresh2 = partitions.load("fresh1"), partitions.load("fresh2")
    reading = _readings(fresh1 + fresh2)
    first_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[0]]}
                          | {(r, tuple(p)) for task in fresh1 for r, p in oracles._fresh_steps(task.name)})
    second_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[1]]})
    existing = {tuple((r, tuple(p)) for r, p in oracles._fresh_steps(task.name)) for task in fresh2}
    pool = sorted({tuple(example[0][0]) for task in fresh1 + fresh2 for example in task.examples})
    exposed = [(key, functions[0]) for key, (_, functions) in sorted(oracles.references().items()) if functions]
    candidates = [(a, b) for a in first_stages for b in second_stages
                  if (a, b) not in existing and a[0] in reading and b[0] in reading]
    random.Random(SEED).shuffle(candidates)
    tally = {"candidates": len(candidates), "examined": 0, "too few inputs": 0, "mixed output types": 0,
             "constant": 0, "identity": 0, "same function as an exposed task": 0, "same function as an earlier FRESH-3 task": 0}
    made = []
    for first, second in candidates:
        if len(made) >= count:
            break
        tally["examined"] += 1
        steps = [(first[0], list(first[1])), (second[0], list(second[1]))]
        reference = oracles._chain(steps, (reading[first[0]], reading[second[0]]))
        head = oracles._chain(steps[:1], (reading[first[0]],))
        usable = []
        for xs in pool:
            middle = head(list(xs))
            if _kind(middle) != "list":
                continue
            value = reference(list(xs))
            if _kind(value) is not None:
                usable.append((list(xs), value))
        if len(usable) < PUBLIC + HIDDEN:
            tally["too few inputs"] += 1
            continue
        name = "fresh3::" + _name(first, second)
        chosen = random.Random(f"{SEED}:{name}").sample(usable, PUBLIC + HIDDEN)
        kinds = {_kind(value) for _, value in chosen}
        if len(kinds) != 1:
            tally["mixed output types"] += 1
            continue
        if len({repr(value) for _, value in chosen[:PUBLIC]}) < 2:
            tally["constant"] += 1
            continue
        if all(value == xs for xs, value in chosen):
            tally["identity"] += 1
            continue
        if any(_same(other, chosen) for _, other in exposed):
            tally["same function as an exposed task"] += 1
            continue
        if any(_same(earlier.reference, chosen) for earlier in made):
            tally["same function as an earlier FRESH-3 task"] += 1
            continue
        output = {"list": ListOf(INT), "int": INT, "bool": BOOL}[kinds.pop()]
        examples = tuple(((xs,), value) for xs, value in chosen)
        made.append(Task(name, arrows(ListOf(INT), output), examples[:PUBLIC], examples[PUBLIC:], reference,
                         (first, second)))
    tally["made"] = len(made)
    if statistics is not None:
        statistics.update(tally)
    return made


def digest(tasks) -> str:
    """SHA-256 over names and every example, so a report can show which set it ran on."""
    payload = [[task.name, str(task.request), task.examples, task.hidden] for task in tasks]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=list).encode()).hexdigest()


if __name__ == "__main__":
    tally = {}
    tasks = make(statistics=tally)
    print(json.dumps(tally))
    kinds = {}
    for task in tasks:
        kinds[str(task.request)] = kinds.get(str(task.request), 0) + 1
    print("tasks", len(tasks), "by request type", kinds, "digest", digest(tasks)[:16])
    again = make()
    print("deterministic:", digest(again) == digest(tasks))
    for task in tasks[:8]:
        print("  ", task.name, "|", task.examples[0])
