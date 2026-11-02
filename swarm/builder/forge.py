"""The primitive forge (OWNER_DIRECTIVE.md §5; original core §16's discipline, re-implemented).

The original core's self-forge synthesized fold programs in a tiny
designer-provided combinator language and registered them as native
primitives. Here the generative substrate is the kernel's checker
language: the forge enumerates small checker-language bodies over a
template vocabulary (list stages, pointwise maps and filters with small
constants, folds, reductions), depth two at most, and keeps the first
body that reproduces every public example of a residue task. The body
becomes a candidate primitive (its DSL type read off the examples) that
the self-edit protocol submits to the kernel; the Builder sets its own
forge criteria (which tasks are residues, how many candidates). The forge
never sees hidden instances: it reads public examples only, and the
kernel decides adoption by archive crossings.
"""
from __future__ import annotations

import json

V, X = "v", "x"
STAGES = [["sort", "_"], ["reverse", "_"], ["unique", "_"], ["tail", "_"],
          ["take", 1, "_"], ["take", 2, "_"], ["take", 3, "_"], ["drop", 1, "_"], ["drop", 2, "_"], ["drop", 3, "_"],
          ["append", "_", ["reverse", "_"]], ["append", ["drop", 1, "_"], ["take", 1, "_"]],
          ["append", ["reverse", "_"], "_"], ["concat", ["list", "_", "_"]]]
POINTWISE = [["+", V, k] for k in (1, 2, 3, -1, -2)] + [["*", V, k] for k in (2, 3, -1)] + \
            [["-", k, V] for k in (0, 10)] + [["mod", V, k] for k in (2, 3)] + [["*", V, V], ["abs", V], ["max", V, 0]]
PREDICATES = [[">", V, k] for k in (0, 1, 2, 3)] + [["<", V, k] for k in (2, 3, 5)] + \
             [["=", ["mod", V, 2], 0], ["!=", ["mod", V, 2], 0], ["=", V, 0], ["!=", V, 0]]
REDUCTIONS = [["sum", "_"], ["len", "_"], ["head", "_"], ["last", "_"], ["fold", "max", 0, "_"],
              ["fold", "min", 0, "_"], ["count", "_", 0], ["count", "_", 1]] + \
             [["index-of", "_", k] for k in (0, 1, 2)]
BOOLS = [["empty?", "_"], ["contains", "_", 0], ["contains", "_", 1], ["<", ["len", "_"], 3],
         ["=", ["len", "_"], 2], ["=", "_", ["sort", "_"]], ["=", "_", ["reverse", "_"]]]


def _sub(template, inner):
    if template == "_":
        return inner
    if isinstance(template, list):
        return [_sub(t, inner) for t in template]
    return template


def candidates(output_kind: str):
    """Bodies over x, by increasing size, for a task whose outputs are of ``output_kind``."""
    lists = [_sub(s, X) for s in STAGES]
    lists += [["map", ["lambda", [V], p], X] for p in POINTWISE]
    lists += [["filter", ["lambda", [V], p], X] for p in PREDICATES]
    if output_kind == "list[int]":
        yield from lists
        for outer in STAGES:
            for inner in lists:
                yield _sub(outer, inner)
        for p in POINTWISE:
            for inner in lists:
                yield ["map", ["lambda", [V], p], inner]
        for p in PREDICATES:
            for inner in lists:
                yield ["filter", ["lambda", [V], p], inner]
    elif output_kind == "int":
        for r in REDUCTIONS:
            yield _sub(r, X)
        for r in REDUCTIONS:
            for inner in lists:
                yield _sub(r, inner)
        for p in POINTWISE:
            for r in REDUCTIONS:
                yield _apply_int(p, _sub(r, X))
    elif output_kind == "bool":
        for b in BOOLS:
            yield _sub(b, X)
        for b in BOOLS:
            for inner in lists:
                yield _sub(b, inner)
        for p in PREDICATES:
            for r in REDUCTIONS:
                yield _apply_int(p, _sub(r, X))
    elif output_kind == "list[bool]":
        for p in PREDICATES:
            yield ["map", ["lambda", [V], p], X]
            for inner in lists:
                yield ["map", ["lambda", [V], p], inner]


def _apply_int(pointwise, inner):
    """A pointwise template over v applied to an int-valued body."""
    return _sub_v(pointwise, inner)


def _sub_v(template, inner):
    if template == V:
        return inner
    if isinstance(template, list):
        return [_sub_v(t, inner) for t in template]
    return template


def output_kind(examples) -> str | None:
    kinds = set()
    for item in examples:
        y = item["output"]
        if type(y) is bool:
            kinds.add("bool")
        elif type(y) is int:
            kinds.add("int")
        elif type(y) is list:
            kinds.add("list[bool]" if y and all(type(v) is bool for v in y) else "list[int]")
        else:
            return None
    if kinds == {"list[int]", "list[bool]"}:
        return "list[int]"
    return kinds.pop() if len(kinds) == 1 else None


def forge(examples, batch_runner, limit: int = 4000, batch: int = 64) -> dict | None:
    """The first enumerated body reproducing every public example, or None.

    ``batch_runner(programs, inputs)`` runs checker-language programs on
    inputs (the metered runner the loop hands the Builder) and returns, per
    program, the outputs or None. Returns {"body": checker-language lambda,
    "type": DSL type text, "tried": n}. Public inputs only.
    """
    kind = output_kind(examples)
    if kind is None:
        return None
    inputs = [item["inputs"][0] for item in examples]
    outputs = [item["output"] for item in examples]
    tried = 0
    pending = []
    for body in candidates(kind):
        pending.append(body)
        if len(pending) < batch and tried + len(pending) < limit:
            continue
        found = _run_batch(pending, inputs, outputs, batch_runner)
        tried += len(pending)
        if found is not None:
            return {"body": ["lambda", [X], found], "type": f"list[int] -> {kind}",
                    "tried": tried - len(pending) + pending.index(found) + 1, "text": json.dumps(found)}
        pending = []
        if tried >= limit:
            return None
    if pending:
        found = _run_batch(pending, inputs, outputs, batch_runner)
        if found is not None:
            return {"body": ["lambda", [X], found], "type": f"list[int] -> {kind}",
                    "tried": tried + pending.index(found) + 1, "text": json.dumps(found)}
    return None


def _run_batch(bodies, inputs, outputs, batch_runner):
    results = batch_runner([["lambda", [X], body] for body in bodies], inputs)
    for body, got in zip(bodies, results):
        if got is not None and all(o == y for o, y in zip(got, outputs)):
            return body
    return None
