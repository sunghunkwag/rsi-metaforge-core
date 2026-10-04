"""Generic input-binder role coverage after a charged grammar-order prefix.

Heads, argument roles and closed argument wrappers come from the unchanged
typed grammar/enumerator. Only full root programs are interpreted; every such
attempt shares one quota. Enumeration pops and structural production queries
share one expansion cap. No task identities or private examples are read.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
import math
import time

from ..enumeration import enumerate_programs
from ..evaluator import evaluate
from ..grammar import ROOT_CONTEXT
from ..terms import Lam, Term, Var, apply, pretty
from ..types import (Type, TypeInferenceError, function_parts, infer, instantiate,
                     substitute, unify)


BASELINE_PREFIX = 16


@dataclass
class SearchResult:
    term: object = None
    candidates: int = 0
    baseline_attempts: int = 0
    stratum_attempts: int = 0
    helper_attempts: int = 0
    example_evaluations: int = 0
    evaluator_steps: int = 0
    expansions: int = 0
    expansion_counts: dict = field(default_factory=dict)
    generated_wrappers: int = 0
    rejected_compositions: int = 0
    strata: list = field(default_factory=list)
    trials: list = field(default_factory=list)
    termination: str = "not_started"
    cpu_seconds: float = 0.0
    wall_seconds: float = 0.0
    report: dict = field(default_factory=dict)


class _Stopped(Exception):
    def __init__(self, reason):
        self.reason = reason


class _Meter:
    def __init__(self, grammar, result, check, maximum, stage, force_lambdas=0):
        self.grammar, self.result, self.check = grammar, result, check
        self.maximum, self.stage = maximum, stage
        self.force_lambdas = force_lambdas

    def pop(self):
        self.check()
        if self.result.expansions >= self.maximum:
            raise _Stopped("expansion_budget")
        self.result.expansions += 1
        counts = self.result.expansion_counts
        counts[self.stage] = counts.get(self.stage, 0) + 1

    def productions(self, *args, **kwargs):
        self.pop()
        choices = self.grammar.productions(*args, **kwargs)
        self.check()
        env = args[1] if len(args) > 1 else kwargs.get("env", ())
        if len(env) < self.force_lambdas:
            # Keep the original normalized probabilities and substitutions;
            # only the wrapper's declared input binders are structurally fixed.
            choices = [choice for choice in choices if choice.is_lambda]
        return choices


def _specialize(term, constraints):
    value = substitute(term.value, constraints) if isinstance(term.value, Type) else term.value
    return Term(term.tag, value, tuple(_specialize(child, constraints) for child in term.children))


def _report(result, budget, limits):
    failures = Counter(trial["failure"] for trial in result.trials if trial["failure"] is not None)
    return {
        "current_performance": {"public_solution": result.term is not None,
                                "attempts": result.candidates, "independent_verification": "unrun"},
        "failure_clusters": {"observed_root_failures": dict(failures),
                             "planning_failure": "unknown", "model_failure": "unknown"},
        "bottleneck": "Test input-binder roles which a global grammar prefix may underrepresent",
        "previous_attempt_insufficiency": "Program count alone does not establish coverage of compatible bound-input argument roles",
        "intervention": {"baseline_prefix": BASELINE_PREFIX, "strata": len(result.strata)},
        "mechanism": "Round-robin grammar-derived root/argument roles; enumerate remaining arguments without helper execution",
        "verification_plan": "Charge every complete root and public interpreter call; caller independently verifies the selected root",
        "regression_risks": "Duplicates, restricted wrapper coverage, traversal overhead and finite search caps",
        "result": {"termination": result.termination, "candidate_budget": budget,
                   "limits": dict(limits), "baseline_attempts": result.baseline_attempts,
                   "stratum_attempts": result.stratum_attempts, "helper_attempts": 0,
                   "expansions": result.expansions, "example_evaluations": result.example_evaluations,
                   "evaluator_steps": result.evaluator_steps},
        "keep_revert_revise": "UNASSESSED: structural search requires matched hidden-verified TRAIN evidence",
        "updated_rule": {"status": "candidate structural policy", "learned_rule": False,
                         "admission": "No solver or RSI gain is admitted from this diagnostic alone"},
    }


def solve_stratified(examples, request_type, budget, grammar, *, max_size=12,
                     max_expansions=20000, step_budget=2000, max_cpu_seconds=10):
    """Use the first sixteen baseline programs, then cycle through binder roles.

    A remaining argument is generated as a closed ``input -> argument`` term.
    Its outer lambda is structurally required using the grammar's original
    normalized production probabilities. Removing that lambda places the
    same binder under the root lambda. Shared production type constraints
    are threaded through every argument and checked again on the completed
    root. Helpers are generated, never interpreted.
    """
    started, wall = time.process_time(), time.perf_counter()
    for name, value, minimum in (("budget", budget, 0), ("max_size", max_size, 1),
                                  ("max_expansions", max_expansions, 0),
                                  ("step_budget", step_budget, 0)):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} requires an integer >= {minimum}")
    if (max_cpu_seconds is not None and (type(max_cpu_seconds) not in (int, float)
            or not math.isfinite(max_cpu_seconds) or max_cpu_seconds < 0)):
        raise ValueError("CPU cap requires a finite nonnegative number or None")
    result = SearchResult()
    examples = tuple(examples)
    attempted = set()

    def check():
        if max_cpu_seconds is not None and time.process_time() - started >= max_cpu_seconds:
            raise _Stopped("cpu_budget")

    def generated(type_, size, stage):
        check()
        remaining = max_expansions - result.expansions
        if remaining <= 0:
            raise _Stopped("expansion_budget")
        meter = _Meter(grammar, result, check, max_expansions, stage,
                       force_lambdas=1 if stage == "argument" else 0)
        for candidate in enumerate_programs(type_, meter, max_size=size, max_expansions=remaining):
            meter.pop()  # Partial pops are metered by productions; complete pops here.
            yield candidate.term
        check()

    def attempt(term, source):
        check()
        if result.candidates >= budget:
            raise _Stopped("candidate_budget")
        result.candidates += 1
        if source["stage"] == "baseline":
            result.baseline_attempts += 1
        else:
            result.stratum_attempts += 1
        trial = {"index": result.candidates - 1, "term": term.to_dict(),
                 "readable": pretty(term), "source": source,
                 "duplicate": term in attempted, "complete": False,
                 "matched": False, "failure": None,
                 "example_evaluations": 0, "evaluator_steps": 0}
        result.trials.append(trial)
        attempted.add(term)
        for inputs, expected in examples:
            check()
            measured = evaluate(term, inputs, library=grammar.library, step_budget=step_budget)
            result.example_evaluations += 1
            result.evaluator_steps += measured.steps
            trial["example_evaluations"] += 1
            trial["evaluator_steps"] += measured.steps
            check()  # Keep charges but withhold a matching call after the CPU deadline.
            if not measured.ok or measured.value != expected:
                trial["failure"] = measured.error or "public_output_mismatch"
                trial["complete"] = True
                return False
        check()
        trial["complete"] = trial["matched"] = True
        return True

    def roots(production, fixed, constraints, parameter):
        count = len(production.arguments)
        argument_budget = max_size - 1 - production.head.size - count

        def fill(index, arguments, current):
            check()
            if index == count:
                body = apply(_specialize(production.head, current), *arguments)
                root = Lam(substitute(parameter, current), _specialize(body, current))
                try:
                    unify(instantiate(infer(root, library=grammar.library), "_strat_root_"),
                          request_type)
                except TypeInferenceError:
                    result.rejected_compositions += 1
                    return
                if root.size <= max_size:
                    yield root
                else:
                    result.rejected_compositions += 1
                return
            if index == fixed:
                yield from fill(index + 1, arguments + [Var(0)], current)
                return
            available = argument_budget - sum(argument.size for argument in arguments) - (count - index - 1)
            if available < 1:
                return
            input_type = substitute(parameter, current)
            argument_type = substitute(production.arguments[index], current)
            wrapper_type = Type("arrow", (input_type, argument_type))
            for wrapper in generated(wrapper_type, available + 1, "argument"):
                result.generated_wrappers += 1
                if wrapper.tag != "lam":
                    raise ValueError("argument enumeration omitted its required input binder")
                argument = wrapper.children[0]
                if argument.size > available:
                    result.rejected_compositions += 1
                    continue
                try:
                    signature = instantiate(infer(argument, env=(input_type,), library=grammar.library),
                                            "_strat_argument_")
                    updated = unify(argument_type, signature, current)
                except TypeInferenceError:
                    result.rejected_compositions += 1
                    continue
                yield from fill(index + 1, arguments + [argument], updated)

        yield from fill(0, [], constraints)

    try:
        check()
        if not examples:
            result.termination = "no_public_examples"
            return result
        if budget == 0:
            raise _Stopped("candidate_budget")
        baseline = generated(request_type, max_size, "baseline")
        try:
            for _ in range(min(BASELINE_PREFIX, budget)):
                term = next(baseline, None)
                if term is None:
                    break
                if attempt(term, {"stage": "baseline"}):
                    result.term, result.termination = term, "public_solution"
                    return result
        finally:
            baseline.close()
        if result.candidates >= budget:
            raise _Stopped("candidate_budget")
        arguments, output = function_parts(request_type)
        if len(arguments) != 1:
            result.termination = "request_is_not_single_input"
            return result
        structural = _Meter(grammar, result, check, max_expansions, "structure")
        lambda_choices = structural.productions(request_type, (), {}, ROOT_CONTEXT)
        streams = deque()
        for outer in lambda_choices:
            if not outer.is_lambda:
                continue
            parameter = substitute(outer.parameter, outer.substitutions)
            body_type = substitute(outer.arguments[0], outer.substitutions)
            choices = structural.productions(body_type, (parameter,), outer.substitutions,
                                              (outer.name, 0))
            for production in choices:
                if production.is_lambda:
                    continue
                if production.name == "var:0" and production.arity == 0:
                    direct = Lam(substitute(parameter, production.substitutions), production.head)
                    if direct.size > max_size:
                        continue
                    index = len(result.strata)
                    result.strata.append({"index": index, "head": production.name, "role": None})
                    streams.append((index, iter((direct,))))
                for role, argument_type in enumerate(production.arguments):
                    fixed_choices = structural.productions(argument_type, (parameter,),
                        production.substitutions, (production.name, role))
                    fixed = next((choice for choice in fixed_choices if choice.name == "var:0"
                                  and choice.arity == 0), None)
                    if fixed is None:
                        continue
                    index = len(result.strata)
                    result.strata.append({"index": index, "head": production.name,
                                          "role": role, "arity": production.arity})
                    streams.append((index, roots(production, role, fixed.substitutions, parameter)))
        while streams:
            check()
            if result.candidates >= budget:
                raise _Stopped("candidate_budget")
            index, stream = streams.popleft()
            term = next(stream, None)
            if term is None:
                continue
            source = {"stage": "stratum", **result.strata[index]}
            streams.append((index, stream))
            if attempt(term, source):
                check()
                result.term, result.termination = term, "public_solution"
                return result
        check()
        result.termination = "strata_exhausted"
    except _Stopped as stopped:
        result.termination = stopped.reason
        if result.trials and not result.trials[-1]["complete"]:
            result.trials[-1]["failure"] = stopped.reason
    finally:
        result.cpu_seconds = time.process_time() - started
        result.wall_seconds = time.perf_counter() - wall
        result.report = _report(result, budget, {"max_size": max_size,
            "max_expansions": max_expansions, "step_budget": step_budget,
            "max_cpu_seconds": max_cpu_seconds})
    return result


def search(task, grammar, budget=64, **limits):
    return solve_stratified(task.examples, task.request_type, budget, grammar, **limits)
