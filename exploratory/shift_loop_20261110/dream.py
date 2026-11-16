"""Dream tasks: new tasks with known answers, composed from the loop's own verified programs.

``g after f`` for two verified programs gives a task whose examples are computed by running
the composition on seeded random lists: 8 public examples for the solver and 8 check examples
that play the verifier's part. Nothing here touches a real task's hidden examples; a dream is
built from programs the loop already holds.
"""
from __future__ import annotations

import random

from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.terms import Lam
from rsi5.dsl.types import INT, ListOf, function_parts, infer
from rsi5.partitions import PublicTask

import hybrid

LIST_INT = ListOf(INT)
SEED = 20261110
PUBLIC, CHECK = 8, 8


def input_lists(seed: int = SEED) -> list:
    rng = random.Random(seed)
    found = [[]]
    while len(found) < PUBLIC + CHECK:
        xs = [rng.randint(0, 10) for _ in range(rng.randint(1, 7))]
        if xs not in found:
            found.append(xs)
    rng.shuffle(found)
    return found


def _outputs(term, inputs):
    values = []
    for xs in inputs:
        result = evaluate(term, (xs,), step_budget=hybrid.STEPS)
        if not result.ok:
            return None
        values.append(result.value)
    return values


def _typed(term):
    try:
        return function_parts(infer(term))
    except Exception:
        return None


def make(programs: dict, count: int, taken: set, round_index: int, seed: int = SEED) -> list:
    """Up to ``count`` new dream tasks from ``programs`` (name -> closed term over one list
    input). ``taken`` holds the output signatures already used and is extended in place.
    Returns [(PublicTask, check examples, ground-truth term)], deterministically."""
    inputs = input_lists(seed)
    typed = {}
    for name in sorted(programs):
        parts = _typed(programs[name])
        if parts is None or len(parts[0]) != 1 or parts[0][0] != LIST_INT:
            continue
        outputs = _outputs(programs[name], inputs)
        if outputs is not None:
            typed[name] = (programs[name], parts[1], outputs)
    inner = [n for n, (_, result, outputs) in typed.items() if result == LIST_INT and outputs != inputs]
    pairs = [(f, g) for f in inner for g in typed if f != g]
    random.Random(f"{seed}:{round_index}").shuffle(pairs)
    made = []
    for f, g in pairs:
        if len(made) >= count:
            break
        f_term, _, f_out = typed[f]
        g_term, _, g_out = typed[g]
        composed = Lam(LIST_INT, hybrid.beta(g_term, [f_term.children[0]]))
        parts = _typed(composed)
        if parts is None:
            continue
        outputs = _outputs(composed, inputs)
        if outputs is None or outputs == f_out or outputs == g_out or outputs == inputs:
            continue
        if all(o == outputs[0] for o in outputs):
            continue
        signature = repr(outputs)
        if signature in taken:
            continue
        taken.add(signature)
        examples = tuple(((xs,), y) for xs, y in zip(inputs, outputs))
        request = infer(composed).to_dict()
        task = PublicTask(f"dream{round_index}::{len(made)}::{g} after {f}", request, examples[:PUBLIC])
        made.append((task, list(examples[PUBLIC:]), composed))
    return made
