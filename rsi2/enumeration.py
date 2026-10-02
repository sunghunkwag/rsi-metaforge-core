"""Typed top-down best-first enumeration of beta-normal functional programs.

Without a heuristic, accumulated log probability is an admissible upper bound:
every future production adds a nonpositive log probability. Complete programs
are therefore yielded in decreasing probability, without generating every
program first. A finite AST-size bound makes the search space finite.

A partial heuristic changes the frontier priority to grammar log probability
plus its score. Unless that score is an admissible completion upper bound, this
is heuristic search and does not claim global probability/score ordering. A
complete-only heuristic instead reranks a bounded lookahead buffer; arbitrary
unbounded scores cannot establish a global order without exhaustive traversal.
The zero heuristic preserves the exact baseline traversal in both modes.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from itertools import count
import math

from .terms import Term
from .grammar import Grammar, ROOT_CONTEXT
from .types import Type, substitute


@dataclass(frozen=True)
class Candidate:
    term: Term
    log_probability: float
    score: float | None = None

    def __post_init__(self):
        if self.score is None:
            object.__setattr__(self, "score", self.log_probability)


@dataclass(frozen=True)
class PartialProgram:
    """Read-only frontier features; holes have ``Term('hole', expected_type)``."""

    term: Term
    log_probability: float
    min_size: int
    depth: int
    complete: bool


@dataclass(frozen=True)
class _Hole:
    type: Type
    env: tuple[Type, ...]
    context: tuple[str, int]


@dataclass(frozen=True)
class _Node:
    tag: str
    value: object = None
    children: tuple = ()


def _first_hole(tree, path=()):
    if isinstance(tree, _Hole):
        return path, tree
    for index, child in enumerate(tree.children):
        result = _first_hole(child, path + (index,))
        if result is not None:
            return result
    return None


def _replace(tree, path, replacement):
    if not path:
        return replacement
    children = list(tree.children)
    children[path[0]] = _replace(children[path[0]], path[1:], replacement)
    return _Node(tree.tag, tree.value, tuple(children))


def _features(tree):
    if isinstance(tree, _Hole):
        return 1, 1
    features = [_features(child) for child in tree.children]
    return 1 + sum(size for size, _ in features), 1 + max(
        (depth for _, depth in features), default=0)


def _materialize(tree, substitutions):
    if isinstance(tree, _Hole):
        return Term("hole", substitute(tree.type, substitutions))
    value = substitute(tree.value, substitutions) if tree.tag == "lam" else tree.value
    return Term(tree.tag, value, tuple(_materialize(c, substitutions) for c in tree.children))


def _expand(production, hole):
    if production.is_lambda:
        body = _Hole(production.arguments[0], (production.parameter,) + hole.env,
                     (production.name, 0))
        return _Node("lam", production.parameter, (body,))
    term = _Node(production.head.tag, production.head.value)
    for index, type_ in enumerate(production.arguments):
        child = _Hole(type_, hole.env, (production.name, index))
        term = _Node("app", None, (term, child))
    return term


def _finite_score(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("heuristic scores must be finite")
    return value


def _frontier(request_type, grammar, max_size, max_depth, max_expansions,
              partial_heuristic, heuristic):
    serials = count()
    initial = _Hole(request_type, (), ROOT_CONTEXT)
    heap = []

    def push(tree, constraints, log_probability):
        size, depth = _features(tree)
        if size > max_size or (max_depth is not None and depth > max_depth):
            return
        pending = _first_hole(tree)
        complete = pending is None
        score = log_probability
        term = None
        if partial_heuristic is not None and not complete:
            term = _materialize(tree, constraints)
        if partial_heuristic is not None and not complete:
            score += _finite_score(partial_heuristic(
                PartialProgram(term, log_probability, size, depth, False)))
        heapq.heappush(heap, (-score, next(serials), tree, constraints,
                              log_probability, pending, term, False))

    push(initial, {}, 0.0)
    expansions = 0
    while heap and (max_expansions is None or expansions < max_expansions):
        priority, _, tree, constraints, log_probability, pending, cached_term, scored = heapq.heappop(heap)
        expansions += 1
        if pending is None:
            term = cached_term if cached_term is not None else _materialize(tree, constraints)
            if not scored and (heuristic is not None or partial_heuristic is not None):
                if heuristic is not None:
                    bonus = _finite_score(heuristic(term))
                else:
                    size, depth = _features(tree)
                    bonus = _finite_score(partial_heuristic(
                        PartialProgram(term, log_probability, size, depth, True)))
                # Probe only a dequeued complete program. Semantic zero must
                # preserve both grammar order and the evaluated prefix under
                # a logical candidate budget, including ties.
                if bonus != 0.0:
                    heapq.heappush(heap, (-(log_probability + bonus), next(serials),
                                          tree, constraints, log_probability,
                                          None, term, True))
                    continue
            yield Candidate(term, log_probability, -priority)
            continue
        path, hole = pending
        for production in grammar.productions(hole.type, hole.env, constraints, hole.context):
            expanded = _replace(tree, path, _expand(production, hole))
            push(expanded, production.substitutions, log_probability + production.log_probability)


def enumerate_programs(request_type, grammar=None, max_size=14, heuristic=None, *,
                       partial_heuristic=None, max_expansions=None, max_depth=None,
                       lookahead=32):
    """Yield well-typed programs, with explicit size and expansion budgets.

    A ``heuristic(term)`` callback supplies complete-program scores. With no
    partial callback, the best grammar-first candidates in a rolling buffer of
    ``lookahead`` are ranked by their actual ``log_probability + heuristic``.
    A ``partial_heuristic(PartialProgram)`` callback instead directs expansion
    of the frontier itself. Complete states use ``heuristic`` when supplied,
    otherwise the partial callback with ``complete=True``. One popped frontier
    state, including a completed program, consumes one expansion budget unit.
    Complete callbacks run only on first dequeue. A nonzero complete score
    reinserts the program with its adjusted priority without calling the scorer
    again; a zero score yields directly, preserving baseline evaluation order.

    Neither score callback changes typing or probabilities. They never inspect
    a task or examples unless the caller explicitly captures that information.
    """
    if not isinstance(request_type, Type):
        raise TypeError("request_type must be a Type")
    if max_size < 1:
        return
    if max_depth is not None and max_depth < 1:
        return
    if max_expansions is not None and max_expansions < 0:
        raise ValueError("max_expansions must be nonnegative")
    if lookahead < 1:
        raise ValueError("lookahead must be positive")
    grammar = Grammar() if grammar is None else grammar
    if heuristic is None or partial_heuristic is not None:
        yield from _frontier(request_type, grammar, max_size, max_depth,
                             max_expansions, partial_heuristic, heuristic)
        return

    baseline = iter(_frontier(request_type, grammar, max_size, max_depth,
                              max_expansions, None, None))
    buffer = []
    serial = count()
    exhausted = False
    while not exhausted or buffer:
        while not exhausted and len(buffer) < lookahead:
            try:
                candidate = next(baseline)
            except StopIteration:
                exhausted = True
                break
            score = candidate.log_probability + _finite_score(heuristic(candidate.term))
            heapq.heappush(buffer, (-score, next(serial), candidate))
        if buffer:
            negative_score, _, candidate = heapq.heappop(buffer)
            yield Candidate(candidate.term, candidate.log_probability, -negative_score)
