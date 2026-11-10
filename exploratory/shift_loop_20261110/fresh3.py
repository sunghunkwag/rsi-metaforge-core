"""FRESH-3: two-stage tasks no run of this study has seen (exploratory, driver side only).

FRESH-2 is 100 pipelines of two list routines. FRESH-3 is 300 more, drawn by a fixed seeded
rule from the same stage instances, generated only after the mechanism under test was frozen.
The registered set (``SEED``) is run for the first time by the registered run; smoke tests use
``SMOKE_SEED`` and so never touch it.

The rule (registered in PREDICTIONS.md, Addendum 7):
  * stage-1 instances: every (routine, parameters) that is the first stage of a FRESH-2 task or
    a FRESH-1 task; stage-2 instances: every second stage of a FRESH-2 task. No new routine and
    no new parameter value;
  * a routine is used with the one reading of its name that reproduces every FRESH task it
    occurs in (``oracles.py``); a routine with no such single reading is left out;
  * candidates are all ordered pairs whose pair of routine names is not the pair of a FRESH-2
    task, in the order of one seeded shuffle;
  * inputs are public example inputs of FRESH-1 and FRESH-2 tasks (never a hidden one), drawn
    with the frequency they have there, 16 distinct lists per task among those the pipeline is
    defined on: 8 public, 8 hidden. If the 8 public outputs are all equal although the
    pipeline is not constant, the last public example is exchanged for one with another output;
  * a candidate is skipped if fewer than 16 inputs are usable, if it is constant on every
    usable input, if it is the identity on its examples, or if it computes on its 16 inputs
    what an exposed task's reference or an earlier FRESH-3 task computes;
  * quotas by output type in FRESH-2's proportions (71 list, 11 integer, 18 boolean per 100):
    a passing candidate is skipped once its type is full.

The reference function of a task is kept in the driver for the audit. A worker receives the
public examples only, like any other task.

    python fresh3.py [--smoke]     the generated set: tallies, mix, digest (no solver is run)
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import itertools
import json
import random
import sys

import oracles
from rsi5 import partitions
from rsi5.dsl.types import BOOL, INT, ListOf, arrows

SEED = "20261110:fresh3:registered"
SMOKE_SEED = "20261110:fresh3:smoke"
COUNT = 300
PUBLIC, HIDDEN = 8, 8
VALUE_CAP = 10 ** 6
LENGTH_CAP = 100
SHARES = (("list", 0.71), ("int", 0.11))           # the rest is boolean: FRESH-2's 71 / 11 / 18
MODULO = frozenset({"modulo-k", "is-mod-k", "keep-mod-k", "remove-mod-k", "identify-is-mod-k",
                    "is-evens", "is-odds", "evens", "odds"})


@dataclass(frozen=True)
class Task:
    name: str
    request: object          # an rsi5 Type
    examples: tuple          # public: ((inputs, output), ...)
    hidden: tuple
    reference: object        # the generating function; never sent to a worker
    stages: tuple            # ((routine, parameters), (routine, parameters))
    kind: str                # 'list', 'int' or 'bool'

    def public_view(self):
        return partitions.PublicTask(self.name, self.request.to_dict(), self.examples)

    @property
    def modulo(self) -> bool:
        """True when a stage is a routine of the modulo family (divisibility tests and filters)."""
        return any(routine in MODULO for routine, _ in self.stages)


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


def input_pool() -> dict:
    """Every public example input of FRESH-1 and FRESH-2 with the number of tasks it occurs in."""
    fresh = partitions.load("fresh1") + partitions.load("fresh2")
    pool = {}
    for task in fresh:
        for xs in {tuple(example[0][0]) for example in task.examples}:
            pool[xs] = pool.get(xs, 0) + 1
    return dict(sorted(pool.items()))


def quotas(count: int) -> dict:
    out = {kind: round(count * share) for kind, share in SHARES}
    out["bool"] = count - sum(out.values())
    return out


def make(count: int = COUNT, seed: str = SEED, statistics: dict | None = None) -> list:
    """The FRESH-3 tasks for ``seed``, deterministically. ``statistics`` receives the tallies."""
    fresh1, fresh2 = partitions.load("fresh1"), partitions.load("fresh2")
    reading = _readings(fresh1 + fresh2)
    first_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[0]]}
                          | {(r, tuple(p)) for task in fresh1 for r, p in oracles._fresh_steps(task.name)})
    second_stages = sorted({(r, tuple(p)) for task in fresh2 for r, p in [oracles._fresh_steps(task.name)[1]]})
    used_pairs = {tuple(r for r, _ in oracles._fresh_steps(task.name)) for task in fresh2}
    pool = input_pool()
    exposed = [(key, functions[0]) for key, (_, functions) in sorted(oracles.references().items()) if functions]
    candidates = [(a, b) for a in first_stages for b in second_stages
                  if (a[0], b[0]) not in used_pairs and a[0] in reading and b[0] in reading]
    random.Random(seed).shuffle(candidates)
    quota = quotas(count)
    tally = {"candidates": len(candidates), "examined": 0, "too few inputs": 0, "mixed output types": 0,
             "constant": 0, "identity": 0, "same function as an exposed task": 0,
             "same function as an earlier FRESH-3 task": 0, "quota full": 0, "public outputs repaired": 0}
    made, filled = [], {kind: 0 for kind in quota}
    for first, second in candidates:
        if len(made) >= count:
            break
        tally["examined"] += 1
        steps = [(first[0], list(first[1])), (second[0], list(second[1]))]
        reference = oracles._chain(steps, (reading[first[0]], reading[second[0]]))
        head = oracles._chain(steps[:1], (reading[first[0]],))
        usable = []
        for xs, weight in pool.items():
            if _kind(head(list(xs))) != "list":
                continue
            value = reference(list(xs))
            if _kind(value) is not None:
                usable.append((list(xs), value, weight))
        if len(usable) < PUBLIC + HIDDEN:
            tally["too few inputs"] += 1
            continue
        if len({repr(value) for _, value, _ in usable}) < 2:
            tally["constant"] += 1
            continue
        name = "fresh3::" + _name(first, second)
        rng = random.Random(f"{seed}:{name}")
        # a weighted draw without replacement: the largest keys u ** (1 / weight)
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
        kinds = {_kind(value) for _, value in chosen}
        if len(kinds) != 1:
            tally["mixed output types"] += 1
            continue
        kind = kinds.pop()
        if all(value == xs for xs, value in chosen):
            tally["identity"] += 1
            continue
        if any(_same(other, chosen) for _, other in exposed):
            tally["same function as an exposed task"] += 1
            continue
        if any(_same(earlier.reference, chosen) for earlier in made):
            tally["same function as an earlier FRESH-3 task"] += 1
            continue
        if filled[kind] >= quota[kind]:
            tally["quota full"] += 1
            continue
        filled[kind] += 1
        output = {"list": ListOf(INT), "int": INT, "bool": BOOL}[kind]
        examples = tuple(((xs,), value) for xs, value in chosen)
        made.append(Task(name, arrows(ListOf(INT), output), examples[:PUBLIC], examples[PUBLIC:], reference,
                         (first, second), kind))
    tally["made"] = len(made)
    tally["by output type"] = filled
    if statistics is not None:
        statistics.update(tally)
    return made


def digest(tasks) -> str:
    """SHA-256 over names and every example, so a report can show which set it ran on."""
    payload = [[task.name, str(task.request), task.examples, task.hidden] for task in tasks]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=list).encode()).hexdigest()


def describe(tasks) -> dict:
    """What the registration states about a set of tasks: its input statistics."""
    longest = sorted(max(len(example[0][0]) for example in task.examples) for task in tasks)
    return {"tasks": len(tasks),
            "with an empty public input": sum(1 for t in tasks if any(not e[0][0] for e in t.examples)),
            "with a negative public input value": sum(1 for t in tasks if any(v < 0 for e in t.examples for v in e[0][0])),
            "median longest public input": longest[len(longest) // 2]}


if __name__ == "__main__":
    smoke = "--smoke" in sys.argv
    count, seed = (60, SMOKE_SEED) if smoke else (COUNT, SEED)
    tally = {}
    tasks = make(count, seed, tally)
    print(json.dumps(tally))
    print("digest", digest(tasks)[:16], "| deterministic:", digest(make(count, seed)) == digest(tasks))
    print("FRESH-3:", json.dumps(describe(tasks)), "| with a modulo-family stage:", sum(1 for t in tasks if t.modulo),
          "| first-stage routines:", len({t.stages[0][0] for t in tasks}),
          "| second-stage routines:", len({t.stages[1][0] for t in tasks}),
          "| distinct routine pairs:", len({(t.stages[0][0], t.stages[1][0]) for t in tasks}))
    print("FRESH-2:", json.dumps(describe(partitions.load("fresh2"))))
