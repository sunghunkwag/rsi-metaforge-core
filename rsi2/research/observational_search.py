"""A bounded, typed bottom-up alternative to the frozen probability queue.

This is a research search procedure, not a replacement for the frozen search.
It constructs beta-normal primitive/library spines and lambda bodies by AST
size. Polymorphic signatures are instantiated over a stated finite ground
type fragment. Function-valued components retain their syntax. Ground-valued
components are pruned only when their values agree in *every* observed binding
environment of their own scope: either a closed component, or the complete
outer task-input scope. Nested lambda scopes are never sampled or pruned.

The procedure is incomplete: the type fragment is finite, observational
equivalence is limited to public inputs, and resource-limited interpretations
do not establish whole-language completeness. Any returned solution must still
pass the existing task-specific hidden verifier. Runtime failures are retained
rather than treated as interchangeable, because the interpreter is lazy.

``budget`` bounds complete-program attempts PLUS auxiliary component probes.
Both count, including failed probes. ``evaluator_calls`` and interpreter steps
include every example evaluation. This makes unmetered semantic helper work
impossible when comparing this procedure with a 64- or 640-candidate baseline.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math
import time

from ..evaluator import evaluate
from ..grammar import Grammar
from ..terms import Lam, Ref, Term, Var, apply
from ..types import BOOL, INT, ListOf, function_parts, infer, library_entries, substitute


@dataclass
class ObservationalSearchResult:
    """Counters cover actual work, not unique mathematical expressions.

    ``retained_components`` and ``constructed_terms`` count DP entries; one AST
    may occur in both a root and an auxiliary construction bucket. Interpreter
    observations of the same closed AST and input scope are cached and counted
    once, including failed observations.
    """
    term: Term | None
    complete_candidates: int
    auxiliary_candidates: int
    evaluator_calls: int
    evaluation_steps: int
    expansions: int
    constructed_terms: int
    semantic_pruned: int
    runtime_failures: int
    retained_components: int
    cpu_seconds: float
    wall_seconds: float
    termination: str
    fragment_ground_types: tuple[str, ...]
    language_complete: bool = False
    log_probability: float | None = None

    @property
    def logical_evaluations(self):
        return self.complete_candidates + self.auxiliary_candidates

    def to_dict(self):
        result = dict(vars(self))
        result["term"] = self.term.to_dict() if self.term is not None else None
        result["fragment_ground_types"] = list(self.fragment_ground_types)
        result["logical_evaluations"] = self.logical_evaluations
        return result


def _variables(type_):
    if type_.is_variable:
        return {type_.name}
    return set().union(*(_variables(arg) for arg in type_.args)) if type_.args else set()


def _ground_fragment(request_type):
    """A task-independent scalar basis plus the task's observed type shapes."""
    values = {INT, BOOL, ListOf(INT), ListOf(BOOL)}

    def visit(type_):
        if type_.is_variable:
            raise ValueError("the observational prototype requires a ground request type")
        if type_.tag != "arrow":
            values.add(type_)
        for child in type_.args:
            visit(child)

    visit(request_type)
    return tuple(sorted(values, key=str))


def _monomorphic(type_, ground_types):
    names = sorted(_variables(type_))
    for choices in product(ground_types, repeat=len(names)):
        yield substitute(type_, dict(zip(names, choices)))


def _partitions(total, count):
    if count == 0:
        if total == 0:
            yield ()
        return
    if total < count:
        return
    if count == 1:
        yield (total,)
        return
    for first in range(1, total - count + 2):
        for rest in _partitions(total - first, count - 1):
            yield (first,) + rest


def _value_key(value):
    """Preserve bool/int and list shapes in equivalence partitions."""
    if type(value) in (bool, int):
        return (type(value).__name__, value)
    if type(value) is list:
        return ("list", tuple(_value_key(item) for item in value))
    raise TypeError("a ground DSL value must be bool, int, or a homogeneous list")


class _Stopped(Exception):
    def __init__(self, reason):
        self.reason = reason


class _Found(Exception):
    def __init__(self, term):
        self.term = term


def solve_observational(examples, request_type, budget, grammar=None, *,
                        step_budget=2000, max_size=12, max_expansions=20000,
                        max_cpu_seconds=10):
    """Construct programs from supplied public examples with honest probe costs.

    No corpus loader is called. Grammar production weights do not determine the
    size-first construction order; learned library entries remain available as
    ordinary typed heads. A combined budget is deliberately stricter than the
    frozen solver's complete-program-only budget. Limits may be reduced for
    diagnostics but cannot exceed the frozen structural/interpreter caps.
    """
    for name, value, ceiling in (("budget", budget, None),
                                 ("step_budget", step_budget, 2000),
                                 ("max_size", max_size, 12),
                                 ("max_expansions", max_expansions, 20000)):
        if type(value) is not int or value < 0 or (ceiling is not None and value > ceiling):
            raise ValueError(f"invalid {name}: {value!r}")
    if max_cpu_seconds is not None and (not math.isfinite(max_cpu_seconds) or max_cpu_seconds <= 0):
        raise ValueError("max_cpu_seconds must be positive")
    examples = tuple((tuple(inputs), expected) for inputs, expected in examples)
    if not examples:
        raise ValueError("search requires supplied public examples")
    inputs_type, output_type = function_parts(request_type)
    if any(len(inputs) != len(inputs_type) for inputs, _ in examples):
        raise ValueError("example arity disagrees with the request type")
    grammar = Grammar() if grammar is None else grammar
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    complete = auxiliary = calls = steps = expansions = constructed = pruned = failures = retained = 0
    fragment = _ground_fragment(request_type)
    outer_scope = tuple(reversed(range(len(inputs_type))))
    memo, seen_semantics, observed = {}, {}, {}
    term = None
    termination = "finite_fragment_exhausted"

    def check_cpu():
        if max_cpu_seconds is not None and time.process_time() - cpu_start >= max_cpu_seconds:
            raise _Stopped("cpu_budget")

    def tick():
        nonlocal expansions
        check_cpu()
        if expansions >= max_expansions:
            raise _Stopped("expansion_budget")
        expansions += 1

    def wrap(body):
        for type_ in reversed(inputs_type):
            body = Lam(type_, body)
        return body

    def observe(node, goal, env, scope, task_prefix):
        """Return a successful ground signature, or None without pruning errors."""
        nonlocal complete, auxiliary, calls, steps, failures
        # Function values are not compared using arbitrary finite probes.
        if goal.tag == "arrow":
            if env or goal != request_type or not task_prefix:
                return None
            executable, supplied, is_complete = node, examples, True
        elif scope == outer_scope:
            executable, supplied = wrap(node), examples
            is_complete = goal == output_type
        elif not env:
            executable, supplied = node, (((), None),)
            is_complete = not inputs_type and goal == request_type
            if is_complete:
                supplied = examples
        else:
            return None
        key = (executable, bool(supplied is examples))
        if key in observed:
            return observed[key]
        check_cpu()
        if complete + auxiliary >= budget:
            raise _Stopped("evaluation_budget")
        if is_complete:
            complete += 1
        else:
            auxiliary += 1
        values = []
        matched = is_complete
        for inputs, expected in supplied:
            check_cpu()
            result = evaluate(executable, inputs, library=grammar.library,
                              step_budget=step_budget)
            calls += 1
            steps += result.steps
            if not result.ok:
                failures += 1
                observed[key] = None
                return None
            values.append(_value_key(result.value))
            matched = matched and result.value == expected
        signature = tuple(values)
        observed[key] = signature
        if matched:
            raise _Found(executable)
        return signature if goal.tag != "arrow" else None

    heads = [(Term("prim", name), signature) for name, signature in grammar.primitives.items()]
    heads.extend((Ref(name), infer(Ref(name), library=grammar.library))
                 for name in library_entries(grammar.library))
    heads.extend((constant, infer(constant)) for constant in grammar.constants)
    mono_heads = tuple((head, actual) for head, signature in heads
                       for actual in _monomorphic(signature, fragment))
    choice_cache = {}

    def choices(goal, env):
        key = (goal, env)
        if key not in choice_cache:
            result = []
            available = mono_heads + tuple((Var(index), type_) for index, type_ in enumerate(env))
            for head, signature in available:
                arguments, residual = function_parts(signature)
                residual = signature
                for arity in range(len(arguments) + 1):
                    if residual == goal:
                        result.append((head, arguments[:arity]))
                    if residual.tag == "arrow":
                        residual = residual.args[1]
            choice_cache[key] = tuple(result)
        return choice_cache[key]

    def components(goal, env, size, scope=(), task_prefix=False):
        nonlocal constructed, pruned, retained
        # Binding *origins*, rather than just their types, matter. An internal
        # fold accumulator can have the same type as a public task input while
        # taking values absent from the task's observed input environments.
        key = (goal, env, scope, task_prefix, size)
        if key in memo:
            return memo[key]
        result = []
        distinct = set()

        def accept(node):
            nonlocal constructed, pruned, retained
            if node in distinct:
                return
            distinct.add(node)
            tick()
            constructed += 1
            signature = observe(node, goal, env, scope, task_prefix)
            if signature is not None:
                semantic_key = (goal, env, scope, signature)
                previous = seen_semantics.get(semantic_key)
                if previous is not None and previous != node and previous.size <= node.size:
                    pruned += 1
                    return
                seen_semantics[semantic_key] = node
            result.append(node)
            retained += 1

        if size <= 0:
            return ()
        if goal.tag == "arrow" and size >= 2:
            tick()
            argument, returned = goal.args
            binding_origin = len(scope) if task_prefix else None
            inner_scope = (binding_origin,) + scope
            for body in components(returned, (argument,) + env, size - 1,
                                   inner_scope, task_prefix):
                accept(Lam(argument, body))
        for head, arguments in choices(goal, env):
            tick()
            remaining = size - 1 - len(arguments)
            for sizes in _partitions(remaining, len(arguments)):
                pools = [components(type_, env, amount, scope)
                         for type_, amount in zip(arguments, sizes)]
                if any(not pool for pool in pools):
                    continue
                for children in product(*pools):
                    accept(apply(head, *children))
        memo[key] = tuple(result)
        return memo[key]

    try:
        if budget == 0:
            raise _Stopped("evaluation_budget")
        for size in range(1, max_size + 1):
            components(request_type, (), size, task_prefix=True)
    except _Found as found:
        term, termination = found.term, "solution"
    except _Stopped as stopped:
        termination = stopped.reason
    probability = (grammar.log_probability(term, request_type=request_type)
                   if term is not None else None)
    return ObservationalSearchResult(
        term, complete, auxiliary, calls, steps, expansions, constructed,
        pruned, failures, retained, time.process_time() - cpu_start,
        time.perf_counter() - wall_start, termination, tuple(map(str, fragment)),
        log_probability=probability,
    )
