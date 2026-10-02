"""Frozen Stage-1 task search and the heuristic input contract.

A logical evaluation is one complete program attempted on a task's search
examples. Failed programs also count. Tree expansions and interpreter steps are
recorded separately; neither substitutes for the candidate-evaluation budget.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from .enumeration import enumerate_programs
from .evaluator import evaluate
from .types import INT, ListOf, arrows

HEURISTIC_TYPE = arrows(ListOf(INT), ListOf(INT), INT, INT, INT)


def flatten(value):
    if isinstance(value, (list, tuple)):
        return [x for item in value for x in flatten(item)]
    return [int(value)] if isinstance(value, (int, bool)) else []


@dataclass
class SearchResult:
    term: object | None
    candidates: int
    log_probability: float | None
    wall_seconds: float
    evaluation_steps: int
    heuristic_calls: int
    exhausted: bool


def solve(examples, request_type, budget, grammar, heuristic=None,
          step_budget=2000, max_size=12, max_expansions=20000):
    """Search sees only supplied examples; verification is a separate operation."""
    # The mandated generation-zero heuristic is constant zero. Keep its
    # traversal and logical evaluation prefix exactly equal to BASE.
    if heuristic is not None:
        body = heuristic
        for _ in range(4):
            if body.tag != "lam":
                break
            body = body.children[0]
        else:
            if body.tag == "int" and body.value == 0:
                heuristic = None
    started = time.perf_counter()
    count = steps = heuristic_calls = 0
    target = flatten([expected for _, expected in examples])
    library = grammar.library
    evaluated = {}
    matches = {}
    priorities = {}

    class Found(Exception):
        def __init__(self, term, probability):
            self.term, self.probability = term, probability

    class Limit(Exception):
        pass

    def attempt(term, probability, select=False):
        nonlocal count, steps
        if term in evaluated:
            if select and term in matches:
                raise Found(term, probability)
            return evaluated[term]
        if count >= budget:
            raise Limit()
        count += 1
        outputs = []
        matched = True
        for inputs, expected in examples:
            result = evaluate(term, inputs, library=library, step_budget=step_budget)
            steps += result.steps
            if not result.ok:
                matched = False
                outputs = []
                break
            outputs.append(result.value)
            if result.value != expected:
                matched = False
                # With no heuristic, remaining outputs are unnecessary.
                if heuristic is None:
                    break
        evaluated[term] = flatten(outputs)
        if matched:
            matches[term] = probability
            if select:
                raise Found(term, probability)
        return evaluated[term]

    def guide(state):
        nonlocal heuristic_calls
        # Complete programs receive output-based scores on their first
        # dequeue. attempt charges the budget and caches each result.
        heuristic_calls += 1
        outputs = attempt(state.term, state.log_probability) if state.complete else []
        result = evaluate(heuristic, (outputs, target, state.min_size, state.depth),
                          library=library, step_budget=step_budget)
        # Scores outside binary64 range cannot be queue priorities. Treat them
        # as a failed heuristic, just like an evaluator budget failure.
        score = (float(result.value) if result.ok and type(result.value) is int
                 and result.value.bit_length() <= 1023 else 0.0)
        if state.complete:
            priorities[state.term] = state.log_probability + score
        return score

    iterator = enumerate_programs(request_type, grammar=grammar, max_size=max_size,
                                  max_expansions=max_expansions,
                                  partial_heuristic=guide if heuristic is not None else None)
    try:
        for candidate in iterator:
            attempt(candidate.term, candidate.log_probability, select=True)
    except Found as found:
        return SearchResult(found.term, count, found.probability,
                            time.perf_counter() - started, steps, heuristic_calls, False)
    except Limit:
        pass
    if matches:
        # Completed states probed for output-based priority already consumed
        # their logical evaluations. Select the highest-priority matching term
        # if the budget ended before it was dequeued.
        best = max(matches, key=lambda term: priorities.get(term, matches[term]))
        return SearchResult(best, count, matches[best], time.perf_counter() - started,
                            steps, heuristic_calls, False)
    return SearchResult(None, count, None, time.perf_counter() - started,
                        steps, heuristic_calls, count < budget)


def verify(term, examples, library=None, step_budget=2000):
    """Called after selecting a solution; hidden examples never guide search."""
    if term is None or not examples:
        return False
    for inputs, expected in examples:
        result = evaluate(term, inputs, library=library, step_budget=step_budget)
        if not result.ok or result.value != expected:
            return False
    return True
