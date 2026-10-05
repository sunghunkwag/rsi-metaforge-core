"""TRAIN development prototype: learn proposal counts from public near misses.

This is a human-designed alternative search kernel, not a synthesized heuristic
or accepted RSI improvement. It opens no partitions. A complete sampled program
costs one logical attempt, including runtime failures; all public executions,
draws, duplicates and typed expansion requests are recorded separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import random
import time
import math

from ..evaluator import evaluate
from ..grammar import Grammar
from ..sampling import sample_program


class ExpansionLimit(Exception):
    pass


class CpuLimit(Exception):
    pass


class CountedGrammar:
    def __init__(self, grammar, limit):
        self.grammar, self.limit, self.expansions = grammar, limit, 0

    def productions(self, *args, **kwargs):
        if self.expansions >= self.limit:
            raise ExpansionLimit
        self.expansions += 1
        return self.grammar.productions(*args, **kwargs)


def distance(actual, expected):
    """Bounded generic value loss; no task names or DSL-specific semantics."""
    if type(actual) is not type(expected):
        return 1.0
    if type(expected) in (int, bool):
        if actual == expected:
            return 0.0
        if type(expected) is bool:
            return 1.0
        # Bounded integer arithmetic avoids binary64 overflow on DSL integers.
        numerator = abs(actual - expected)
        denominator = 1 + abs(actual) + abs(expected)
        return numerator / denominator
    if type(expected) is list:
        width = max(len(actual), len(expected), 1)
        return (abs(len(actual) - len(expected)) +
                sum(distance(a, b) for a, b in zip(actual, expected))) / width
    raise TypeError("unsupported example value")


@dataclass
class SamplingResult:
    term: object | None = None
    candidates: int = 0
    evaluator_calls: int = 0
    evaluation_steps: int = 0
    expansions: int = 0
    draws: int = 0
    duplicate_draws: int = 0
    failed_draws: int = 0
    updates: int = 0
    cpu_seconds: float = 0.0
    wall_seconds: float = 0.0
    stop_reason: str = "candidate_budget"
    trials: list = field(default_factory=list)


def solve_sampling(examples, request_type, budget, grammar, *, seed=11,
                   adaptive=False, batch=16, elite=4, max_size=12,
                   max_expansions=20000, step_budget=2000, max_cpu_seconds=10):
    """Uniform/current-prior sampling or alternating prior/near-miss sampling.

    Hidden examples are absent from this interface. Only full public matches
    can return a solution; near misses influence local proposals but never
    become verified library/recognition training labels here.
    """
    for name, value in (("budget", budget), ("batch", batch), ("elite", elite),
                        ("max_size", max_size), ("max_expansions", max_expansions),
                        ("step_budget", step_budget)):
        if type(value) is not int or value < (0 if name == "budget" else 1):
            raise ValueError(f"invalid {name}")
    if not examples:
        raise ValueError("public examples required")
    if type(max_cpu_seconds) not in (int, float) or not math.isfinite(max_cpu_seconds) or max_cpu_seconds < 0:
        raise ValueError("invalid CPU limit")
    result = SamplingResult()
    wall, cpu = time.perf_counter(), time.process_time()
    rng, seen, history = random.Random(seed), set(), []
    proposal = grammar
    counted = CountedGrammar(grammar, max_expansions)

    def check_cpu():
        if time.process_time() - cpu >= max_cpu_seconds:
            raise CpuLimit

    try:
        while result.candidates < budget:
            check_cpu()
            # Alternating the original prior and learned proposal prevents an
            # elite's common but uninformative output from removing exploration.
            counted.grammar = proposal if adaptive and result.draws % 2 else grammar
            result.draws += 1
            term = sample_program(request_type, counted, rng, max_size=max_size,
                                  max_attempts=1)
            if term is None:
                result.failed_draws += 1
                continue
            if term in seen:
                result.duplicate_draws += 1
                continue
            seen.add(term)
            result.candidates += 1
            matches, losses, valid = 0, [], True
            row = {"term": term.to_dict(), "complete": False}
            result.trials.append(row)
            for inputs, expected in examples:
                check_cpu()
                evaluated = evaluate(term, inputs, library=grammar.library,
                                     step_budget=step_budget)
                result.evaluator_calls += 1
                result.evaluation_steps += evaluated.steps
                check_cpu()
                if not evaluated.ok:
                    valid = False
                    losses.append(1.0)
                else:
                    matches += evaluated.value == expected
                    losses.append(distance(evaluated.value, expected))
            loss = sum(losses) / len(losses)
            row.update(valid=valid, matches=matches, loss=loss, complete=True)
            if valid:
                history.append(((-matches, loss, term.size, result.candidates), term))
            if valid and matches == len(examples):
                result.term, result.stop_reason = term, "public_match"
                break
            if adaptive and result.candidates % batch == 0 and history:
                chosen = [term for _, term in sorted(history)[:elite]]
                proposal = Grammar(library=grammar.library,
                                   primitives=grammar.primitives,
                                   constants=grammar.constants)
                proposal.fit([(term, request_type) for term in chosen])
                result.updates += 1
    except ExpansionLimit:
        result.stop_reason = "expansion_budget"
    except CpuLimit:
        result.stop_reason = "cpu_budget"
    result.expansions = counted.expansions
    result.cpu_seconds = time.process_time() - cpu
    result.wall_seconds = time.perf_counter() - wall
    return result
