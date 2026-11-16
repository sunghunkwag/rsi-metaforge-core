"""Reference functions for the tasks of every exposed partition (report-only audit tool).

The frozen verifier accepts a program that reproduces a task's public and hidden examples.
FRESH tasks have one or two hidden examples, so a wrong program can pass. This module gives,
for each task whose routine is known, a reference function written from the routine's name.
A reference is used only if it reproduces every example of its task (public and hidden);
where a name admits several readings every reading that does so is kept. A verified program
is then run on fresh inputs and compared with the references (``audit_all.py``).

Nothing here is given to the solver: the audit runs after the fact, in the report tool.

    python oracles.py            coverage: tasks with a validated reference, per partition
"""
from __future__ import annotations

import itertools
import random
import re

from rsi3.compose24 import reference_oracle
from rsi5 import partitions

ALL = ("train", "near", "validation", "far", "far2", "fresh1", "fresh2", "compose24")
SEED = 20261110
TRIALS = 200


def _is_prime(n):
    if n < 2:
        return False
    d = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


def _is_square(n):
    if n < 0:
        return False
    r = int(n ** 0.5)
    return any((r + d) ** 2 == n for d in (-1, 0, 1))


def _uniq(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


def _dedup_adjacent(xs):
    out = []
    for x in xs:
        if not out or out[-1] != x:
            out.append(x)
    return out


def _intersperse(xs, k):
    out = []
    for i, x in enumerate(xs):
        if i:
            out.append(k)
        out.append(x)
    return out


def _rotate(xs, k):
    if not xs:
        return []
    k %= len(xs)
    return xs[k:] + xs[:k]


def _rotate_right(xs, k):
    if not xs:
        return []
    k %= len(xs)
    return xs[len(xs) - k:] + xs[:len(xs) - k]


def _fib(n, first):
    if n < 0:
        return None
    a, b = first
    for _ in range(n):
        a, b = b, a + b
    return a


def _need(condition, value):
    return value() if condition else None


def _power(base, exponent):
    if exponent < 0 or abs(base) > 64 or exponent > 64:
        return None
    return base ** exponent


def _all_or_none(values):
    values = list(values)
    return None if any(v is None for v in values) else values


# routine name -> list of readings; a reading maps (value, parameters) to a result, or None
# when the value is outside the routine's domain. The first reading is the expected one.
ROUTINES = {
    "add-k": [lambda xs, p: [x + p[0] for x in xs]],
    "mult-k": [lambda xs, p: [x * p[0] for x in xs]],
    "modulo-k": [lambda xs, p: _need(p[0] != 0, lambda: [x % p[0] for x in xs])],
    "pow-k": [lambda xs, p: _all_or_none(_power(x, p[0]) for x in xs)],
    "pow-base-k": [lambda xs, p: _all_or_none(_power(p[0], x) for x in xs)],
    "prepend-k": [lambda xs, p: [p[0]] + xs],
    "append-k": [lambda xs, p: xs + [p[0]]],
    "has-k": [lambda xs, p: p[0] in xs],
    "count-k": [lambda xs, p: sum(1 for x in xs if x == p[0])],
    "identify-k": [lambda xs, p: [1 if x == p[0] else 0 for x in xs]],
    "identify-geq-k": [lambda xs, p: [1 if x >= p[0] else 0 for x in xs]],
    "identify-is-mod-k": [lambda xs, p: _need(p[0] != 0, lambda: [1 if x % p[0] == 0 else 0 for x in xs])],
    "identify-is-prime": [lambda xs, p: [1 if _is_prime(x) else 0 for x in xs]],
    "bool-identify-k": [lambda xs, p: [x == p[0] for x in xs]],
    "bool-identify-geq-k": [lambda xs, p: [x >= p[0] for x in xs]],
    "bool-identify-is-mod-k": [lambda xs, p: _need(p[0] != 0, lambda: [x % p[0] == 0 for x in xs])],
    "bool-identify-is-prime": [lambda xs, p: [_is_prime(x) for x in xs]],
    "replace-all-k-with-n": [lambda xs, p: [p[1] if x == p[0] else x for x in xs]],
    "replace-index-k-with-n": [lambda xs, p: _need(1 <= p[0] <= len(xs),
                                                 lambda: xs[:p[0] - 1] + [p[1]] + xs[p[0]:])],
    "replace-all-with-index-k": [lambda xs, p: _need(1 <= p[0] <= len(xs), lambda: [xs[p[0] - 1]] * len(xs))],
    "intersperse-k": [lambda xs, p: _intersperse(xs, p[0])],
    "positions": [lambda xs, p: [i for i, x in enumerate(xs) if x != 0]],
    "uniq": [lambda xs, p: _uniq(xs)],
    "dedup": [lambda xs, p: _dedup_adjacent(xs), lambda xs, p: _uniq(xs)],
    "dup": [lambda xs, p: [x for x in xs for _ in (0, 1)], lambda xs, p: xs + xs],
    "rotate-k": [lambda xs, p: _rotate(xs, p[0]), lambda xs, p: _rotate_right(xs, p[0])],
    "reverse": [lambda xs, p: xs[::-1]],
    "sort": [lambda xs, p: sorted(xs)],
    "sum": [lambda xs, p: sum(xs)],
    "product": [lambda xs, p: _product(xs)],
    "len": [lambda xs, p: len(xs)],
    "empty": [lambda xs, p: len(xs) == 0],
    "head": [lambda xs, p: _need(len(xs) > 0, lambda: xs[0])],
    "last": [lambda xs, p: _need(len(xs) > 0, lambda: xs[-1])],
    "min": [lambda xs, p: _need(len(xs) > 0, lambda: min(xs))],
    "max": [lambda xs, p: _need(len(xs) > 0, lambda: max(xs))],
    "is-evens": [lambda xs, p: all(x % 2 == 0 for x in xs)],
    "is-odds": [lambda xs, p: all(x % 2 == 1 for x in xs)],
    "is-primes": [lambda xs, p: all(_is_prime(x) for x in xs)],
    "is-squares": [lambda xs, p: all(_is_square(x) for x in xs)],
    "is-mod-k": [lambda xs, p: _need(p[0] != 0, lambda: all(x % p[0] == 0 for x in xs))],
    "evens": [lambda xs, p: [x for x in xs if x % 2 == 0]],
    "odds": [lambda xs, p: [x for x in xs if x % 2 == 1]],
    "keep-mod-k": [lambda xs, p: _need(p[0] != 0, lambda: [x for x in xs if x % p[0] == 0])],
    "remove-mod-k": [lambda xs, p: _need(p[0] != 0, lambda: [x for x in xs if x % p[0] != 0])],
    "drop-k": [lambda xs, p: _need(0 <= p[0] <= len(xs), lambda: xs[p[0]:])],
    "take-k": [lambda xs, p: _need(0 <= p[0] <= len(xs), lambda: xs[:p[0]])],
    "remove-index-k": [lambda xs, p: _need(1 <= p[0] <= len(xs), lambda: xs[:p[0] - 1] + xs[p[0]:])],
    "index-k": [lambda xs, p: _need(1 <= p[0] <= len(xs), lambda: xs[p[0] - 1])],
    "index-head": [lambda xs, p: _need(len(xs) > 0 and 1 <= xs[0] <= len(xs), lambda: xs[xs[0] - 1]),
                   lambda xs, p: _need(len(xs) > 0 and 0 <= xs[0] < len(xs), lambda: xs[xs[0]]),
                   lambda xs, p: _need(len(xs) > 1 and 1 <= xs[0] < len(xs), lambda: xs[1:][xs[0] - 1])],
    "append-index-k": [lambda xs, p: _need(1 <= p[0] <= len(xs), lambda: xs + [xs[p[0] - 1]])],
    "prepend-index-k": [lambda xs, p: _need(1 <= p[0] <= len(xs), lambda: [xs[p[0] - 1]] + xs)],
    "kth-largest": [lambda xs, p: _need(1 <= p[0] <= len(xs), lambda: sorted(xs, reverse=True)[p[0] - 1])],
    "kth-smallest": [lambda xs, p: _need(1 <= p[0] <= len(xs), lambda: sorted(xs)[p[0] - 1])],
    "repeat-k": [lambda xs, p: _need(p[0] >= 0, lambda: xs * p[0])],
    "caesar-cipher-k-modulo-n": [lambda xs, p: _need(p[1] != 0, lambda: [(x + p[0]) % p[1] for x in xs])],
    "slice-k-n": [lambda xs, p: _need(1 <= p[0] and p[1] <= len(xs), lambda: xs[p[0] - 1:p[1]]),
                  lambda xs, p: _need(1 <= p[0] and p[0] - 1 + p[1] <= len(xs), lambda: xs[p[0] - 1:p[0] - 1 + p[1]]),
                  lambda xs, p: _need(p[1] <= len(xs), lambda: xs[p[0]:p[1]]),
                  lambda xs, p: _need(p[0] + p[1] <= len(xs), lambda: xs[p[0]:p[0] + p[1]])],
    "has-head-in-tail": [lambda xs, p: _need(len(xs) > 0, lambda: xs[0] in xs[1:])],
    "count-head-in-tail": [lambda xs, p: _need(len(xs) > 0, lambda: sum(1 for x in xs[1:] if x == xs[0]))],
    "repeat": [lambda xs, p: _need(len(xs) >= 2 and 0 <= xs[1] <= 64, lambda: [xs[0]] * xs[1]),
               lambda xs, p: _need(len(xs) >= 2 and 0 <= xs[0] <= 64, lambda: [xs[1]] * xs[0])],
    "repeat-many": [lambda xs, p: _need(len(xs) >= 1 and 0 <= xs[0] <= 16, lambda: xs[1:] * xs[0]),
                    lambda xs, p: _need(all(0 <= x <= 16 for x in xs), lambda: [x for x in xs for _ in range(x)]),
                    lambda xs, p: _need(len(xs) >= 1 and 0 <= xs[-1] <= 16, lambda: xs[:-1] * xs[-1])],
    "fibonacci": [lambda n, p: _fib(n, (0, 1)), lambda n, p: _fib(n, (1, 1)), lambda n, p: _fib(n, (1, 2))],
}


def _product(xs):
    out = 1
    for x in xs:
        out *= x
    return out


def _fresh_steps(name):
    """[(routine, parameters)] of a FRESH name such as ((add-k (dyn . 0) (static . 3)) (sum (dyn . 1)))."""
    parts = re.findall(r"\(([a-z0-9-]+)((?: \((?:dyn|static) \. -?\d+\))*)\)", name)
    return [(routine, [int(v) for v in re.findall(r"\(static \. (-?\d+)\)", arguments)]) for routine, arguments in parts]


def _corpus_steps(name):
    """[(routine, parameters)] of a corpus name such as 'slice-k-n with k=3 and n=4'."""
    routine = name.split(" with ")[0]
    return [(routine, [int(v) for v in re.findall(r"=(-?\d+)", name)])]


def _chain(steps, choice):
    def run(xs):
        value = xs
        for (routine, parameters), reading in zip(steps, choice):
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, (list, int)):
                return None
            try:
                value = ROUTINES[routine][reading](value, parameters)
            except (TypeError, IndexError, ZeroDivisionError, OverflowError, ValueError):
                return None
        return value
    return run


def candidates(partition: str, name: str) -> list:
    """Every reading of the task's name as a function, before validation."""
    if partition == "compose24":
        family = name.split("::")[1]
        k = int(name.split("::p")[1])
        return [lambda xs: reference_oracle(family, k, xs)]
    steps = _fresh_steps(name) if partition in ("fresh1", "fresh2") else _corpus_steps(name)
    if not steps or any(routine not in ROUTINES for routine, _ in steps):
        return []
    return [_chain(steps, choice)
            for choice in itertools.product(*[range(len(ROUTINES[routine])) for routine, _ in steps])]


def validated(partition: str, task) -> list:
    """The readings that reproduce every example of the task, public and hidden."""
    examples = list(task.examples) + list(task.hidden)
    kept = []
    for function in candidates(partition, task.name):
        try:
            if all(function(list(inputs[0])) == output and type(function(list(inputs[0]))) is type(output)
                   for inputs, output in examples):
                kept.append(function)
        except Exception:
            continue
    return kept


_CACHE: dict = {}


def references() -> dict:
    """'partition/task name' -> (task, [validated readings]) for every exposed task."""
    if not _CACHE:
        for partition in ALL:
            for task in partitions.load(partition):
                _CACHE[f"{partition}/{task.name}"] = (task, validated(partition, task))
    return _CACHE


def fresh_inputs(key: str, task, functions, trials: int = TRIALS) -> list:
    """``trials`` inputs inside the task's own input range, spread over the reference's outputs
    (so a boolean task gets both answers and a counting task several counts). Lengths stay
    between the shortest and the longest example input; values stay between the smallest and
    the largest example value of the task."""
    rng = random.Random(f"{SEED}:{key}")
    inputs = [list(example[0][0]) for example in list(task.examples) + list(task.hidden)]
    lengths = [len(xs) for xs in inputs]
    values = [x for xs in inputs for x in xs] or [0]
    low, high, shortest, longest = min(values), max(values), min(lengths), max(lengths)
    pool = []

    def add(xs):
        if shortest <= len(xs) <= longest and all(low <= x <= high for x in xs):
            pool.append(list(xs))
    for _ in range(1500):
        add([rng.randint(low, high) for _ in range(rng.randint(shortest, longest))])
    for _ in range(1500):                                   # near the task's own inputs
        xs = list(inputs[rng.randrange(len(inputs))])
        for _ in range(rng.randint(1, 2)):
            move = rng.randrange(5)
            if move == 0 and xs:
                xs[rng.randrange(len(xs))] = rng.randint(low, high)
            elif move == 1 and xs:
                del xs[rng.randrange(len(xs))]
            elif move == 2:
                xs.insert(rng.randint(0, len(xs)), xs[rng.randrange(len(xs))] if xs and rng.random() < 0.5
                          else rng.randint(low, high))
            elif move == 3 and len(xs) > 1:
                i, j = rng.randrange(len(xs)), rng.randrange(len(xs))
                xs[i], xs[j] = xs[j], xs[i]
            elif move == 4 and xs:
                xs = [xs[rng.randrange(len(xs))]] * len(xs) if rng.random() < 0.3 else xs
        add(xs)
    span = list(range(low, high + 1))[:24]
    for n in range(shortest, min(longest, 2) + 1):          # every short list over the first values
        for xs in itertools.product(span, repeat=n):
            add(list(xs))
    groups, seen = {}, set(tuple(xs) for xs in inputs)      # the examples themselves are not fresh
    for xs in pool:
        key_ = tuple(xs)
        if key_ in seen:
            continue
        seen.add(key_)
        expected = functions[0](list(xs))
        if expected is None:
            continue
        groups.setdefault(repr(expected), []).append(xs)
    order = sorted(groups, key=lambda g: (len(groups[g]), g))
    chosen = []
    while len(chosen) < trials and any(groups[g] for g in order):
        for g in order:
            if groups[g] and len(chosen) < trials:
                chosen.append(groups[g].pop(0))
    return chosen


if __name__ == "__main__":
    table = references()
    for partition in ALL:
        keys = [k for k in table if k.startswith(partition + "/")]
        with_reference = [k for k in keys if table[k][1]]
        several = [k for k in with_reference if len(table[k][1]) > 1]
        print(f"{partition:10s} tasks {len(keys):3d}  with a validated reference {len(with_reference):3d}  "
              f"of which several readings fit {len(several)}")
        for k in keys:
            if not table[k][1]:
                print("    no reference:", k)
