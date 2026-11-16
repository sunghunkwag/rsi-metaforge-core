"""A stricter measure of a solve for generated tasks: *right*.

The audit of Addendum 7 and 8 calls a verified program *sound* when it agrees with the task's
generating function on up to 200 fresh inputs inside the range of the task's own examples. The
verification of Addendum 8 showed what that lets through: programs that patch a sentinel
constant (right while the constant cannot occur in the input), programs that are right only
for non-negative values, and programs that run out of evaluation steps on larger inputs of the
range. Twenty percent of the sound programs of FRESH-4 fail on wider inputs.

A verified program of a generated task is *right* when it returns the generating function's
output, within the evaluator's step budget, on every input of three sets on which the function
is defined:

  1. the audit's fresh inputs (at least ``confirm.MIN_EVIDENCE`` of them), so right implies sound;
  2. the FRESH input pool (every public example input of FRESH-1 and FRESH-2), as in the
     "whole pool" reading of Addenda 7 and 8;
  3. a wide draw, seeded by the task's name: WIDE lists of length 0 to the longest example plus
     4, with values between minus and plus the largest absolute example value plus 5 (at least
     10), together with the empty list and every list of one element from -3 to 3.

Running out of steps on a test input is a failure there, for every program and every arm. The
rule is the same for all states compared, and no search reads it.

For an exposed task the measure is the audit's (``audit_all``): no wider test is defined there.
"""
from __future__ import annotations

import random

import confirm
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.pretty_parse import parse

WIDE = 200
STEPS = confirm.STEPS


def same(a, b) -> bool:
    """Equality with element types compared: [True] is not [1]."""
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


class Right:
    def __init__(self, generated: dict):
        self.sound = confirm.Sound(generated)
        self.tasks = self.sound.tasks
        self.wide, self.cache = {}, {}

    def wide_inputs(self, key: str) -> list:
        if key not in self.wide:
            task = self.tasks[key]
            inputs = [list(example[0][0]) for example in list(task.examples) + list(task.hidden)]
            longest = max(len(xs) for xs in inputs) + 4
            bound = max(10, max([abs(x) for xs in inputs for x in xs] or [0]) + 5)
            rng = random.Random(f"wide:{key}")
            drawn = [[]] + [[v] for v in range(-3, 4)]
            drawn += [[rng.randint(-bound, bound) for _ in range(rng.randint(0, longest))] for _ in range(WIDE)]
            self.wide[key] = drawn
        return self.wide[key]

    def _agrees(self, task, term, inputs) -> bool:
        for xs in inputs:
            want = task.reference(list(xs))
            if want is None or self.sound.kind(want) is None:
                continue
            got = evaluate(term, (list(xs),), step_budget=STEPS)
            if not got.ok or not same(got.value, want):
                return False
        return True

    def verdict(self, key: str, text: str) -> dict:
        """{'sound', 'pool', 'wide', 'right'} for a verified program (an exposed task: the audit only)."""
        if (key, text) not in self.cache:
            sound = bool(self.sound.verdict(key, text)[0])
            if key not in self.tasks:
                self.cache[(key, text)] = {"sound": sound, "pool": None, "wide": None, "right": sound}
            else:
                pool = sound and bool(self.sound.on_pool(key, text))
                wide = self._agrees(self.tasks[key], parse(text), self.wide_inputs(key))
                self.cache[(key, text)] = {"sound": sound, "pool": pool, "wide": wide, "right": sound and pool and wide}
        return self.cache[(key, text)]

    def right(self, key: str, text: str) -> bool:
        return self.verdict(key, text)["right"]
