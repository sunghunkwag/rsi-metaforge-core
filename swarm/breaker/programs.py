"""The Breaker's program vocabulary: seed witnesses, mutations and compositions in the checker language.

Everything here is a designer-written generator of checker-language
programs, in the sense of Phase K's setter policies: a fixed enumerator
with no channel to the vault, the kernel or the Builder's source. The
Breaker's tasks are functions of one list of ints (or bools) whose outputs
are ints, bools or lists of them, the value domain the Builder's
generation-0 DSL shares; strings and tuples are available to witnesses
and checkers internally but never as task values.

``SEED`` is the bootstrap vocabulary (the archive is empty at generation
0); ``mutate`` and ``compose`` derive new witnesses from existing ones.
Programs are plain JSON, so hashing and ledgering need nothing else.
"""
from __future__ import annotations

import random

X = "x"
V = "v"


def mapped(body):
    return ["map", ["lambda", [V], body], X]


def filtered(test):
    return ["filter", ["lambda", [V], test], X]


SEED = [
    # Stages the checker language has and the generation-0 DSL lacks.
    ["sort", X], ["reverse", X], ["unique", X], ["take", 2, X], ["drop", 2, X],
    ["count", X, 0], ["index-of", X, 1], ["contains", X, 3],
    ["append", X, ["reverse", X]], ["append", ["take", 1, X], ["drop", 2, X]],
    ["sort", ["unique", X]], ["reverse", ["sort", X]], ["take", 3, ["sort", X]], ["drop", 1, ["reverse", X]],
    ["concat", ["list", X, X]], ["append", ["drop", 1, X], ["take", 1, X]],
    # Stages within reach of the generation-0 DSL (map, filter, fold, head, tail, cons, arithmetic),
    # so that mutations and compositions of them sit on the frontier rather than beyond it.
    ["tail", X], ["sum", X], ["len", X], ["last", X], ["head", X], ["empty?", X], ["<", ["len", X], 4],
    mapped(["+", V, 1]), mapped(["*", V, 2]), mapped(["-", V, 1]), mapped(["mod", V, 2]),
    mapped(["neg", V]), mapped(["max", V, 3]), mapped([">", V, 2]), mapped(["=", ["mod", V, 2], 0]),
    mapped(["*", V, V]), mapped(["+", V, V]), mapped(["-", 0, V]), mapped(["mod", V, 3]),
    filtered([">", V, 2]), filtered(["=", ["mod", V, 2], 0]), filtered(["!=", V, 0]), filtered(["<", V, 3]),
    filtered(["=", ["mod", V, 3], 0]), filtered(["<", 1, V]),
    ["fold", "+", 0, X], ["fold", "max", 0, X], ["fold", ["lambda", ["a", "b"], ["cons", "b", "a"]], ["list"], X],
    ["fold", "+", 0, mapped(["*", V, V])], ["fold", "+", 1, X], ["fold", "*", 1, X],
    ["cons", ["head", X], X], ["cons", 0, X], ["cons", ["sum", X], X], ["tail", ["tail", X]],
    ["cons", ["head", X], ["tail", ["tail", X]]], ["len", filtered([">", V, 0])], ["sum", mapped(["+", V, 1])],
    ["sum", filtered(["=", ["mod", V, 2], 0])], ["head", ["tail", X]], ["cons", ["len", X], X],
    mapped(["+", V, ["len", X]]), mapped(["-", V, ["head", X]]), mapped(["*", V, ["sum", X]]),
    filtered(["<", V, ["head", X]]), filtered(["=", V, ["head", X]]), ["=", ["sum", X], 0], ["<", ["head", X], ["last", X]],
    [">", ["len", X], 2], ["contains", X, ["len", X]],
]

UNARY_LIST = [["sort", "_"], ["reverse", "_"], ["unique", "_"], ["tail", "_"], ["take", 2, "_"],
              ["drop", 1, "_"], ["take", 3, "_"], ["drop", 2, "_"], ["append", "_", ["reverse", "_"]],
              ["map", ["lambda", [V], ["+", V, 1]], "_"], ["map", ["lambda", [V], ["*", V, 2]], "_"],
              ["map", ["lambda", [V], ["-", V, 1]], "_"], ["map", ["lambda", [V], ["*", V, V]], "_"],
              ["map", ["lambda", [V], ["mod", V, 2]], "_"], ["map", ["lambda", [V], ["neg", V]], "_"],
              ["filter", ["lambda", [V], [">", V, 1]], "_"], ["filter", ["lambda", [V], ["=", ["mod", V, 2], 0]], "_"],
              ["filter", ["lambda", [V], ["!=", V, 0]], "_"], ["filter", ["lambda", [V], ["<", V, 2]], "_"],
              ["tail", ["tail", "_"]], ["cons", ["head", "_"], "_"], ["cons", 0, "_"], ["cons", ["sum", "_"], "_"]]
LIST_TO_INT = [["sum", "_"], ["len", "_"], ["head", "_"], ["last", "_"], ["fold", "max", 0, "_"],
               ["count", "_", 1], ["index-of", "_", 2], ["fold", "+", 1, "_"], ["head", ["tail", "_"]]]
INT_TO_INT = [["+", "_", 1], ["*", "_", 2], ["-", "_", 3], ["mod", "_", 3], ["neg", "_"], ["abs", "_"],
              ["*", "_", "_"], ["-", 0, "_"], ["+", "_", "_"]]
INT_TO_BOOL = [[">", "_", 2], ["=", "_", 0], ["<", "_", 5], ["=", ["mod", "_", 2], 0]]
SWAPS = {"+": ["-", "*", "max", "min"], "-": ["+", "*", "min"], "*": ["+", "-", "max"],
         "<": ["<=", ">", ">="], ">": [">=", "<", "<="], "=": ["!=", "<", ">"], "!=": ["="],
         "sort": ["reverse", "unique"], "reverse": ["sort"], "take": ["drop"], "drop": ["take"],
         "sum": ["len"], "head": ["last"], "last": ["head"], "max": ["min"], "min": ["max"]}
CONSTANT_RANGE = (-3, 6)


def substitute(template, inner):
    """Replace the placeholder "_" in a template by ``inner``."""
    if template == "_":
        return inner
    if isinstance(template, list):
        return [substitute(t, inner) for t in template]
    return template


def witness(body) -> list:
    return ["lambda", [X], body]


def equality_checker(body) -> list:
    """The default checker: the output equals the witness's output."""
    return ["lambda", [X, "y"], ["=", "y", body]]


def _paths(program, path=()):
    yield path, program
    if isinstance(program, list):
        for index, child in enumerate(program):
            if not (index == 0 and isinstance(child, str) and child in ("lambda", "rec", "let", "str")):
                yield from _paths(child, path + (index,))


def _replace(program, path, value):
    if not path:
        return value
    out = list(program)
    out[path[0]] = _replace(out[path[0]], path[1:], value)
    return out


def mutate(body, rng: random.Random) -> list:
    """One random edit of a witness body: a constant, a primitive swap, or a wrapping stage."""
    choice = rng.random()
    nodes = list(_paths(body))
    constants = [(p, n) for p, n in nodes if type(n) is int and p]
    primitives = [(p, n) for p, n in nodes if isinstance(n, str) and n in SWAPS and p and p[-1] == 0]
    if choice < 0.35 and constants:
        path, value = constants[rng.randrange(len(constants))]
        delta = rng.choice([-2, -1, 1, 2, 3])
        new = max(CONSTANT_RANGE[0], min(CONSTANT_RANGE[1], value + delta))
        return _replace(body, path, new if new != value else value + 1)
    if choice < 0.6 and primitives:
        path, name = primitives[rng.randrange(len(primitives))]
        return _replace(body, path, rng.choice(SWAPS[name]))
    kind = output_kind_hint(body)
    if kind == "list":
        return substitute(rng.choice(UNARY_LIST), body) if rng.random() < 0.5 else rng.choice(
            [substitute(rng.choice(LIST_TO_INT), body), substitute(rng.choice(UNARY_LIST), ["sort", body])])
    if kind == "int":
        return substitute(rng.choice(INT_TO_INT + INT_TO_BOOL), body)
    return ["not", body] if rng.random() < 0.3 else substitute(rng.choice(UNARY_LIST), X)


def output_kind_hint(body) -> str:
    """A syntactic guess of a body's result kind (list / int / bool), used to pick mutations."""
    head = body[0] if isinstance(body, list) and body else None
    if head in ("sort", "reverse", "unique", "tail", "take", "drop", "append", "map", "filter", "concat", "list", "cons"):
        return "list"
    if head in ("sum", "len", "head", "last", "count", "index-of", "+", "-", "*", "mod", "div", "neg", "abs", "max", "min"):
        return "int"
    if head == "fold":
        return "list" if isinstance(body[2], list) else "int"
    if head in ("<", ">", "<=", ">=", "=", "!=", "empty?", "contains", "not", "and", "or"):
        return "bool"
    return "list"


def compose(outer_body, inner_body) -> list:
    """``outer(inner(x))``: the inner body replaces ``x`` in the outer body."""
    return substitute_x(outer_body, inner_body)


def substitute_x(program, inner):
    if program == X:
        return inner
    if isinstance(program, list):
        if program and program[0] in ("lambda", "rec") and X in (program[1] if program[0] == "lambda" else program[2]):
            return program
        return [substitute_x(p, inner) for p in program]
    return program


def size(program) -> int:
    if isinstance(program, list):
        return 1 + sum(size(p) for p in program)
    return 1
