"""Experience the system makes for itself: programs it runs on its own inputs.

The engine enumerates programs over a set of input lists and keeps, for every behaviour, one
program with its outputs. Each of them is a task whose answer is known by construction: the
outputs are the examples and the program is a solution. Two programs of one run compose into
a deeper task (``g after f``), evaluated by the reference interpreter. Nothing here reads a
task's hidden examples or a held-out task: the inputs are public example inputs of the
learning partitions.

A dream is ``(examples, items)``: examples in the form the search receives them, and the
vocabulary items of the program that made them.
"""
from __future__ import annotations

import random
import re

from hybrid import LAMBDA_DEPTH, LIST_INT, MAX_SIZE, STEPS, bu, probes
from rsi5 import partitions
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.terms import Lam
from rsi5.dsl.types import BOOL, INT, arrows
from rsi5.engine.oe import ERR

WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
IMPOSSIBLE = 10 ** 9 + 7


def input_pool(partition_names) -> list:
    """Every distinct public example input of the named partitions."""
    seen = {}
    for name in partition_names:
        for task in partitions.load(name):
            for inputs, _ in task.examples:
                seen[tuple(inputs[0])] = None
    return [list(xs) for xs in seen]


def items_of(text: str, names) -> set:
    """The vocabulary items (primitive or symbol names) that occur in a program text."""
    return {word for word in WORD.findall(text) if word in names}


def _usable(outputs, inputs) -> bool:
    if any(o is ERR for o in outputs):
        return False
    if len({repr(o) for o in outputs}) < 2:
        return False
    if all(isinstance(o, list) and o == xs for o, xs in zip(outputs, inputs)):
        return False
    return True


def run(vocabulary, inputs, budget: int, rng: random.Random, singles: int, pairs: int, names, state=None) -> list:
    """Dreams from one enumeration over ``inputs``: up to ``singles`` pool programs, larger
    ones more often, and up to ``pairs`` compositions of two of them."""
    examples = [((list(xs),), [IMPOSSIBLE + i]) for i, xs in enumerate(inputs)]
    engine = bu.Engine(vocabulary, max_size=MAX_SIZE, step_budget=STEPS, max_lambda_depth=LAMBDA_DEPTH)
    stored = state if state is not None else probes.load()
    engine.search(examples, arrows(LIST_INT, LIST_INT), probes.inputs_for((LIST_INT,), stored), budget)
    n = len(inputs)
    usable = {}
    for type_ in (LIST_INT, INT, BOOL):
        for expr in engine.top.pools.get(type_, ()):
            if expr.kind in ("var", "const"):
                continue
            outputs = list(expr.outputs[:n])
            if _usable(outputs, inputs):
                usable.setdefault(type_, []).append((expr, outputs))
    out = []
    everything = [entry for entries in usable.values() for entry in entries]
    if not everything:
        return out
    weights = [entry[0].size ** 2 for entry in everything]
    for expr, outputs in rng.choices(everything, weights=weights, k=min(singles, len(everything))):
        text = str(expr.term)
        out.append(([((list(xs),), o) for xs, o in zip(inputs, outputs)], sorted(items_of(text, names)), text))
    lists = usable.get(LIST_INT, [])
    tried = 0
    while lists and len(out) < singles + pairs and tried < 6 * pairs:
        tried += 1
        (f, mids), (g, _) = rng.choice(lists), rng.choice(everything)
        if any(not isinstance(mid, list) for mid in mids):
            continue
        outer = Lam(LIST_INT, g.term)
        outputs = []
        for mid in mids:
            got = evaluate(outer, (list(mid),), step_budget=STEPS)
            if not got.ok:
                break
            outputs.append(got.value)
        if len(outputs) != n or not _usable(outputs, inputs):
            continue
        text = f"{g.term} after {f.term}"
        out.append(([((list(xs),), o) for xs, o in zip(inputs, outputs)], sorted(items_of(text, names)), text))
    return out


def make(vocabulary, pool, runs: int, seed: int, *, budget: int = 6000, singles: int = 60, pairs: int = 60,
         examples: int = 8, names=None) -> list:
    """``runs`` enumerations, each over ``examples`` inputs drawn from ``pool``."""
    rng = random.Random(seed)
    names = set(names if names is not None else vocabulary.primitives)
    stored = probes.load()
    out = []
    for _ in range(runs):
        inputs = rng.sample(pool, examples)
        out.extend(run(vocabulary, inputs, budget, rng, singles, pairs, names, stored))
    return out


def lifted(vocabulary, inputs, budget: int, rng: random.Random, count: int, names, state=None) -> list:
    """Dreams of the element-wise kind: an ``int -> int`` function mapped over the input, or
    an ``int -> bool`` predicate filtering it, optionally after a list program of ``prefix``
    (so that the search's own routes, a map or a filter over a re-representation, are covered).
    The element functions are enumerated over the values that occur in ``inputs``."""
    values = sorted({x for xs in inputs for x in xs})
    if len(values) < 3:
        return []
    examples = [((v,), IMPOSSIBLE + i) for i, v in enumerate(values)]
    engine = bu.Engine(vocabulary, max_size=MAX_SIZE, step_budget=STEPS, max_lambda_depth=LAMBDA_DEPTH)
    stored = state if state is not None else probes.load()
    engine.search(examples, arrows(INT, INT), probes.inputs_for((INT,), stored), budget)
    n = len(values)
    candidates = []
    for type_ in (INT, BOOL):
        for expr in engine.top.pools.get(type_, ()):
            if expr.kind in ("var", "const"):
                continue
            outputs = list(expr.outputs[:n])
            if any(o is ERR for o in outputs) or len({repr(o) for o in outputs}) < 2:
                continue
            candidates.append((expr, dict(zip(values, outputs)), type_))
    out = []
    if not candidates:
        return out
    weights = [entry[0].size ** 2 for entry in candidates]
    for expr, table, type_ in rng.choices(candidates, weights=weights, k=min(count, len(candidates))):
        if type_ == INT:
            outputs = [[table[x] for x in xs] for xs in inputs]
            text = f"(map (lambda x: int. {expr.term})) $0"
        else:
            outputs = [[x for x in xs if table[x]] for xs in inputs]
            text = f"(filter (lambda x: int. {expr.term})) $0"
        if _usable(outputs, inputs):
            out.append(([((list(xs),), o) for xs, o in zip(inputs, outputs)], sorted(items_of(text, names)), text))
    return out


def composed_programs(programs: dict, pool, rng: random.Random, count: int, names, examples: int = 8) -> list:
    """Dreams ``g after f`` of verified programs (key -> closed term over one list input),
    on inputs drawn from ``pool``. ``f`` must return a list on every input used."""
    keys = sorted(programs)
    out, tried = [], 0
    while keys and len(out) < count and tried < 20 * count:
        tried += 1
        f_key, g_key = rng.choice(keys), rng.choice(keys)
        f, g = programs[f_key], programs[g_key]
        chosen, rows = rng.sample(pool, min(len(pool), 4 * examples)), []
        for xs in chosen:
            mid = evaluate(f, (list(xs),), step_budget=STEPS)
            if not mid.ok or not isinstance(mid.value, list) or isinstance(mid.value, bool):
                continue
            if any(isinstance(v, bool) or not isinstance(v, int) for v in mid.value):
                continue
            got = evaluate(g, (list(mid.value),), step_budget=STEPS)
            if got.ok:
                rows.append((xs, got.value))
            if len(rows) == examples:
                break
        if len(rows) < examples:
            continue
        inputs, outputs = [r[0] for r in rows], [r[1] for r in rows]
        if any(isinstance(o, list) and any(isinstance(v, bool) for v in o) for o in outputs):
            continue
        if not _usable(outputs, inputs):
            continue
        text = f"{g} after {f}"
        out.append(([((list(xs),), o) for xs, o in zip(inputs, outputs)], sorted(items_of(text, names)), text))
    return out
