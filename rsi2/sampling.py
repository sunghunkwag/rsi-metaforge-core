"""Seeded stochastic expansion from the current typed contextual grammar.

Sampling draws a production at each hole; it does not enumerate a prefix and
choose one of its members. Within a subtree size budget, locally impossible
productions are excluded and the remaining grammar probabilities renormalized.
Failed type-constrained branches restart the draw, up to ``max_attempts``.
"""
from __future__ import annotations

import math

from .grammar import ROOT_CONTEXT
from .terms import Term
from .types import TVar, Type, substitute


def _draw(productions, rng):
    maximum = max(p.log_probability for p in productions)
    weights = [math.exp(p.log_probability - maximum) for p in productions]
    threshold = float(rng.random()) * math.fsum(weights)
    cumulative = 0.0
    for production, weight in zip(productions, weights):
        cumulative += weight
        if threshold < cumulative:
            return production
    return productions[-1]


def _resolve_annotations(term, constraints):
    # Alpha-normalize unresolved annotation variables. Global fresh inference
    # counters must not leak into the serialization of a seeded random draw.
    variables = {}

    def canonical(type_):
        if type_.is_variable:
            if type_.name not in variables:
                variables[type_.name] = TVar(f"sample_type_{len(variables)}")
            return variables[type_.name]
        return Type(type_.tag, tuple(canonical(a) for a in type_.args))

    def visit(node):
        value = canonical(substitute(node.value, constraints)) if node.tag == "lam" else node.value
        return Term(node.tag, value, tuple(visit(c) for c in node.children))

    return visit(term)


def sample_program(request_type, grammar, rng, max_size=12, max_attempts=100):
    """Draw a typed program or return ``None`` after bounded unsuccessful draws.

    ``rng`` supplies ``random()`` and is seeded by the caller. Type substitutions
    are threaded through siblings and lambda binders, preserving polymorphic
    argument relationships. A failed draw is never evaluated by this function.
    """
    if not isinstance(request_type, Type):
        raise TypeError("request_type must be a Type")
    if type(max_size) is not int or type(max_attempts) is not int:
        raise TypeError("sampling bounds must be integers")
    if max_attempts < 0:
        raise ValueError("max_attempts must be nonnegative")
    if max_size < 1:
        return None

    def build(target, env, constraints, context, budget):
        choices = tuple(p for p in grammar.productions(target, env, constraints, context)
                        if (2 if p.is_lambda else 1 + 2 * p.arity) <= budget)
        if not choices:
            return None
        selected = _draw(choices, rng)
        updated = selected.substitutions
        if selected.is_lambda:
            child = build(selected.arguments[0], (selected.parameter,) + env,
                          updated, (selected.name, 0), budget - 1)
            if child is None:
                return None
            body, updated, size = child
            return Term("lam", selected.parameter, (body,)), updated, size + 1
        term = selected.head
        # One head and one application node per argument are already reserved.
        remaining = budget - 1 - selected.arity
        size = 1 + selected.arity
        for index, child_type in enumerate(selected.arguments):
            reserved = selected.arity - index - 1
            child = build(child_type, env, updated, (selected.name, index), remaining - reserved)
            if child is None:
                return None
            argument, updated, child_size = child
            term = Term("app", None, (term, argument))
            remaining -= child_size
            size += child_size
        return term, updated, size

    for _ in range(max_attempts):
        result = build(request_type, (), {}, ROOT_CONTEXT, max_size)
        if result is not None:
            term, constraints, _ = result
            return _resolve_annotations(term, constraints)
    return None
