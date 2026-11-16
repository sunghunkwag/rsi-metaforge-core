"""Features of a task's public examples, for the learned search policy.

A task maps a list of integers to a list, an integer or a boolean. The policy never sees a
task's name, its hidden examples or a reference: only what the search itself receives. A
feature is a relation between an input and its output that can be checked without a search
(lengths, order, membership, element-wise arithmetic). Per-example features are aggregated
over the examples by mean, minimum and maximum, so that "holds for every example" and "holds
for some example" are both visible.

The same featurizer serves every domain whose tasks are integer lists (the typed list language
of rsi5 and the stack machine of the core runtime).
"""
from __future__ import annotations

import numpy as np

SMALL = range(-2, 11)


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def _subsequence(short, long) -> bool:
    it = iter(long)
    return all(any(x == y for y in it) for x in short)


def _sub_multiset(short, long) -> bool:
    pool = list(long)
    for x in short:
        if x in pool:
            pool.remove(x)
        else:
            return False
    return True


def _input_block(xs) -> list:
    n = len(xs)
    return [float(n == 0), min(n, 20) / 20.0, float(any(x < 0 for x in xs)),
            min(max([abs(x) for x in xs] or [0]), 100) / 100.0,
            float(n > 1 and list(xs) == sorted(xs)), float(len(set(xs)) < n)]


def _list_block(xs, y) -> list:
    n, m = len(xs), len(y)
    out = [float(max(-4, min(4, m - n)) == d) for d in range(-4, 5)]
    out += [float(m == 2 * n and n > 0), float(m == 0), float(m <= n), float(m == n), float(m > n)]
    out += [float(list(y) == list(xs)), float(list(y) == list(xs)[::-1]), float(list(y) == sorted(xs)),
            float(list(y) == sorted(xs, reverse=True)), float(_subsequence(y, xs)), float(list(y) == list(xs)[:m]),
            float(m <= n and list(y) == list(xs)[n - m:]), float(_sub_multiset(y, xs)), float(set(y) <= set(xs)),
            float(_subsequence(xs, y)), float(list(y)[:n] == list(xs)), float(m >= n and list(y)[m - n:] == list(xs))]
    same = m == n and n > 0
    if same:
        diffs = {b - a for a, b in zip(xs, y)}
        ratios = {b // a if a != 0 and b % a == 0 else None for a, b in zip(xs, y)}
        equal = sum(1 for a, b in zip(xs, y) if a == b)
        changed = {b for a, b in zip(xs, y) if a != b}
        out += [float(len(diffs) == 1), float(len(ratios) == 1 and None not in ratios), float(set(y) <= {0, 1}),
                float(len(changed) <= 1), equal / n, float(all(b >= a for a, b in zip(xs, y))),
                float(all(b <= a for a, b in zip(xs, y))),
                float(any(all(b == a % k for a, b in zip(xs, y)) for k in range(2, 11))),
                float(all(b == a * a for a, b in zip(xs, y))), float(all(b == abs(a) for a, b in zip(xs, y))),
                float(all(b == -a for a, b in zip(xs, y)))]
    else:
        out += [0.0] * 11
    new = {v for v in y if v not in xs}
    out += [float(m > 1 and len(set(y)) == 1), float(m > 1 and list(y) == sorted(y)), float(all(v >= 0 for v in y)),
            float(set(y) <= {0, 1}), float(m > 0 and all(v % 2 == 0 for v in y)), float(m > 0 and all(v % 2 for v in y)),
            float(m > 0 and all(_is_prime(v) for v in y)),
            float(max([abs(v) for v in y] or [0]) > max([abs(v) for v in xs] or [0])), min(len(new), 5) / 5.0,
            float(m > 0 and all(0 <= v < max(n, 1) for v in y) and list(y) == sorted(set(y))),
            float(len(set(y)) < m), float(m > 0 and n > 0 and y[0] == xs[0]), float(m > 0 and n > 0 and y[-1] == xs[-1]),
            float(m > 0 and n > 0 and y[0] not in xs), float(m > 0 and n > 0 and y[-1] not in xs)]
    out += [float(c in new) for c in SMALL]
    return out


def _int_block(xs, y) -> list:
    n = len(xs)
    product = 1
    for x in xs:
        product *= x
        if abs(product) > 10 ** 9:
            break
    out = [float(y == n), float(y == sum(xs)), float(n > 0 and y == max(xs)), float(n > 0 and y == min(xs)),
           float(n > 0 and y == xs[0]), float(n > 0 and y == xs[-1]), float(y in xs), float(0 <= y <= n),
           float(y == product), float(y == len(set(xs))), float(y < 0),
           float(abs(y) > max([abs(x) for x in xs] or [0])), float(y in (0, 1)),
           float(n > 1 and y == sorted(xs)[-2]), float(n > 1 and y == sorted(xs)[1])]
    out += [float(y == sum(1 for x in xs if x == c)) for c in range(0, 6)]
    return out


def _bool_block(xs, y) -> list:
    n = len(xs)
    truth = bool(y)
    tests = [n == 0, n > 0 and all(x % 2 == 0 for x in xs), any(x < 0 for x in xs), list(xs) == sorted(xs),
             n > 0 and all(_is_prime(x) for x in xs), len(set(xs)) < n, n > 0 and all(x % 2 for x in xs),
             n > 0 and xs[0] in list(xs)[1:]]
    tests += [c in xs for c in range(0, 6)]
    return [float(truth)] + [float(truth == bool(t)) for t in tests]


_LIST = len(_list_block([1], [1]))
_INT = len(_int_block([1], 1))
_BOOL = len(_bool_block([1], True))
_INPUT = len(_input_block([1]))
PER_EXAMPLE = _INPUT + _LIST + _INT + _BOOL
SIZE = 3 * PER_EXAMPLE + 3


def kind_of(value) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    return "list"


def featurize(examples) -> np.ndarray:
    """``examples``: ((inputs, output), ...) with one list input. A vector of SIZE floats."""
    rows = []
    kind = kind_of(examples[0][1])
    for inputs, y in examples:
        xs = list(inputs[0])
        row = _input_block(xs)
        row += _list_block(xs, list(y)) if kind == "list" else [0.0] * _LIST
        row += _int_block(xs, int(y)) if kind == "int" else [0.0] * _INT
        row += _bool_block(xs, y) if kind == "bool" else [0.0] * _BOOL
        rows.append(row)
    table = np.asarray(rows, dtype=np.float32)
    head = np.asarray([float(kind == k) for k in ("list", "int", "bool")], dtype=np.float32)
    return np.concatenate([table.mean(axis=0), table.min(axis=0), table.max(axis=0), head])
