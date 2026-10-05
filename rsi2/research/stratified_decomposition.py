"""Public pointwise decomposition with one charged stratified scalar search.

The component search uses the unchanged single-input stratified policy. Head,
component and full-root interpreter attempts share one quota. A scalar public
match requires a separately charged check against every original public case.
No task identity, private examples or held-out data is accessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

from ..enumeration import enumerate_programs
from ..evaluator import evaluate
from ..terms import apply, pretty
from ..types import Arrow
from .decomposition_search import SearchResult as DecompositionResult, _projection
from .stratified_search import solve_stratified


@dataclass
class SearchResult(DecompositionResult):
    scalar_search: dict = field(default_factory=dict)
    expansion_counts: dict = field(default_factory=dict)
    report: dict = field(default_factory=dict)


class _Stopped(Exception):
    def __init__(self, reason):
        self.reason = reason


class _HeadMeter:
    def __init__(self, grammar, result, check, maximum):
        self.grammar, self.result, self.check, self.maximum = grammar, result, check, maximum

    def pop(self):
        self.check()
        if self.result.expansions >= self.maximum:
            raise _Stopped("expansion_budget")
        self.result.expansions += 1
        counts = self.result.expansion_counts
        counts["head"] = counts.get("head", 0) + 1

    def productions(self, *args, **kwargs):
        self.pop()
        choices = self.grammar.productions(*args, **kwargs)
        self.check()
        return choices


def _report(result, budget, limits):
    failures = {}
    for trial in result.trials:
        if trial["failure"] is not None:
            failures[trial["failure"]] = failures.get(trial["failure"], 0) + 1
    return {
        "current_performance": {"public_solution": result.term is not None,
                                "attempts": result.candidates, "independent_verification": "unrun"},
        "failure_clusters": {"observed_failures": failures, "planning_failure": "unknown",
                             "model_failure": "unknown"},
        "bottleneck": "Measure pointwise scalar input-role coverage under one shared interpreter quota",
        "previous_attempt_insufficiency": "A large scalar grammar prefix can contain few input-dependent bodies",
        "intervention": {"kind": "public_pointwise_projection_then_stratified_scalar_search",
                         "scalar_searches": int(bool(result.scalar_search))},
        "mechanism": "Enumerate typed heads; run one scalar binder-role search; separately verify each composed root",
        "verification_plan": "Charge head, scalar and complete-root attempts; caller performs independent verification",
        "regression_risks": "Pointwise hypotheses, finite structural coverage, duplicates and exhausted final-root quota",
        "result": {"termination": result.termination, "candidate_budget": budget, "limits": dict(limits),
                   "head_attempts": result.head_attempts, "component_attempts": result.component_attempts,
                   "root_attempts": result.root_attempts, "expansions": result.expansions,
                   "example_evaluations": result.example_evaluations, "evaluator_steps": result.evaluator_steps},
        "keep_revert_revise": "UNASSESSED: requires matched independently verified TRAIN evidence",
        "updated_rule": {"status": "candidate structural policy", "learned_rule": False,
                         "admission": "A public diagnostic does not establish solver or RSI gain"},
    }


def solve_stratified_decomposition(examples, request_type, budget, grammar, *, max_size=12,
                                   max_expansions=20000, step_budget=2000, max_cpu_seconds=10):
    """Run one scalar search, retaining all head/component/root charges.

    The scalar search receives the quota remaining after head attempts. It
    stops at its first public match. Remaining quota pays full-root checks;
    a match on the last scalar candidate cannot be accepted without that
    check. If every compatible head fails, this adapter stops rather than
    restarting and repeating the scalar prefix. Remaining argument wrappers
    are never interpreted, as specified by ``solve_stratified``.
    """
    started, wall = time.process_time(), time.perf_counter()
    for name, value, minimum in (("budget", budget, 0), ("max_size", max_size, 1),
                                 ("max_expansions", max_expansions, 0), ("step_budget", step_budget, 0)):
        if type(value) is not int or value < minimum:
            raise ValueError(f"{name} requires an integer >= {minimum}")
    if (max_cpu_seconds is not None and (type(max_cpu_seconds) not in (int, float)
            or not math.isfinite(max_cpu_seconds) or max_cpu_seconds < 0)):
        raise ValueError("CPU cap requires a finite nonnegative number or None")
    result, examples = SearchResult(), tuple(examples)

    def check():
        if max_cpu_seconds is not None and time.process_time() - started >= max_cpu_seconds:
            raise _Stopped("cpu_budget")

    def attempt(term, cases, stage):
        check()
        if result.candidates >= budget:
            raise _Stopped("candidate_budget")
        result.candidates += 1
        if stage == "head":
            result.head_attempts += 1
            result.helper_attempts += 1
        else:
            result.root_attempts += 1
        trial = {"index": result.candidates - 1, "stage": stage, "term": term.to_dict(),
                 "readable": pretty(term), "example_evaluations": 0, "evaluator_steps": 0,
                 "matched": False, "complete": False, "failure": None}
        result.trials.append(trial)
        for inputs, expected in cases:
            check()
            evaluated = evaluate(term, inputs, library=grammar.library, step_budget=step_budget)
            result.example_evaluations += 1
            result.evaluator_steps += evaluated.steps
            trial["example_evaluations"] += 1
            trial["evaluator_steps"] += evaluated.steps
            check()
            if not evaluated.ok or (stage != "head" and evaluated.value != expected):
                trial["failure"] = evaluated.error or "public_output_mismatch"
                trial["complete"] = True
                return False
        check()
        trial["matched"] = trial["complete"] = True
        return True

    try:
        check()
        projection, failure = _projection(examples, request_type, check)
        result.decomposition = {"kind": "pointwise_map", "supported": projection is not None,
                                "reason": failure, "public_examples": len(examples)}
        if projection is None:
            return result
        component_type, scalar_examples = projection
        result.decomposition.update({"component_type": str(component_type),
                                     "component_examples": scalar_examples,
                                     "unique_elements": len(scalar_examples)})
        if budget == 0:
            raise _Stopped("candidate_budget")
        meter, heads = _HeadMeter(grammar, result, check, max_expansions), []
        head_stream = enumerate_programs(Arrow(component_type, request_type), meter,
                                         max_size=1, max_expansions=max_expansions)
        for candidate in head_stream:
            meter.pop()
            if attempt(candidate.term, (((), None),), "head"):
                heads.append(candidate.term)
        check()
        if not heads:
            result.termination = ("expansion_budget" if result.expansions >= max_expansions
                                  else "no_compatible_head")
            return result
        if max_size < 3:
            result.termination = "size_budget"
            return result
        if result.candidates >= budget:
            raise _Stopped("candidate_budget")
        remaining_cpu = (None if max_cpu_seconds is None else
                         max(0.0, max_cpu_seconds - (time.process_time() - started)))
        scalar = solve_stratified(scalar_examples, component_type, budget - result.candidates,
                                  grammar, max_size=max_size - 2,
                                  max_expansions=max_expansions - result.expansions,
                                  step_budget=step_budget, max_cpu_seconds=remaining_cpu)
        # Merge before the outer deadline check so all completed scalar work is retained.
        offset = result.candidates
        for trial in scalar.trials:
            result.trials.append({**trial, "index": offset + trial["index"], "stage": "component"})
        result.candidates += scalar.candidates
        result.helper_attempts += scalar.candidates
        result.component_attempts += scalar.candidates
        result.example_evaluations += scalar.example_evaluations
        result.evaluator_steps += scalar.evaluator_steps
        result.expansions += scalar.expansions
        for stage, count in scalar.expansion_counts.items():
            result.expansion_counts["scalar_" + stage] = count
        result.scalar_search = {"termination": scalar.termination,
                                "baseline_attempts": scalar.baseline_attempts,
                                "stratum_attempts": scalar.stratum_attempts,
                                "generated_wrappers": scalar.generated_wrappers,
                                "rejected_compositions": scalar.rejected_compositions,
                                "strata": scalar.strata,
                                "public_match": scalar.term is not None,
                                "cpu_seconds": scalar.cpu_seconds,
                                "wall_seconds": scalar.wall_seconds}
        check()
        if scalar.term is None:
            result.termination = scalar.termination
            return result
        for head in heads:
            root = apply(head, scalar.term)
            if attempt(root, examples, "root"):
                check()
                result.term, result.termination = root, "public_solution"
                return result
        check()
        result.termination = "root_verification_failed"
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
    return solve_stratified_decomposition(task.examples, task.request_type, budget, grammar, **limits)
