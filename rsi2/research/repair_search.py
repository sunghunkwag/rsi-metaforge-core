"""Budgeted typed single-subterm repair of machine-generated programs.

This prototype changes the search architecture, not the frozen language.
Every replacement is emitted by the frozen enumerator. Open replacements are
enumerated as closed lambda wrappers and unwrapped in the original binder
environment. No target-specific ASTs or task identifiers guide the search.

All enumerators share one expansion cap; all unique complete programs attempted
on public examples share one candidate cap. Cached replacement enumeration is
reported separately from fresh work. Hidden verification belongs to the caller.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from itertools import count
import time

from ..enumeration import enumerate_programs
from ..evaluator import evaluate
from ..terms import Term, replace_subterm
from ..types import (
    Arrow, BOOL, INT, PRIMITIVE_TYPES, TVar, TypeInferenceError,
    arrows, infer, instantiate, substitute, unify,
)


@dataclass(frozen=True)
class RepairSeed:
    """Previously verifier-accepted TRAIN program, with its external provenance.

    The caller must supply the actual acceptance record. This search receives
    public examples only and cannot create or independently validate that record.
    """

    term: Term
    training_record: str

    def __post_init__(self):
        if not isinstance(self.term, Term) or not self.training_record:
            raise ValueError("accepted seeds require a term and a TRAIN record")


@dataclass(frozen=True)
class Location:
    path: tuple[int, ...]
    term: Term
    type: object
    env: tuple


def typed_locations(term, request_type, library=None):
    """Infer subterms jointly, retaining constraints imposed by their context.

    Inferring a subterm alone loses information: ``nil`` may be list[int] in
    its parent, and a lambda annotation may be specialized by an application.
    This traversal mirrors the frozen inference rules, then applies the final
    substitutions to every recorded local type and binder environment.
    """
    serial = count()
    constraints = {}
    renames = {}
    records = []

    def fresh():
        return TVar(f"_repair_{next(serial)}")

    def annotation(type_):
        if type_.is_variable:
            if type_.name not in renames:
                renames[type_.name] = fresh()
            return renames[type_.name]
        return type_ if not type_.args else type(type_)(
            type_.tag, tuple(annotation(a) for a in type_.args))

    def constrain(first, second):
        nonlocal constraints
        constraints = unify(first, second, constraints)

    def visit(node, env, path):
        if node.tag == "int":
            actual = INT
        elif node.tag == "bool":
            actual = BOOL
        elif node.tag == "var":
            if node.value >= len(env):
                raise TypeInferenceError("unbound repair seed variable")
            actual = env[node.value]
        elif node.tag in ("prim", "ref"):
            signature = (PRIMITIVE_TYPES[node.value]
                         if node.tag == "prim" and node.value in PRIMITIVE_TYPES
                         else infer(node, library=library))
            actual = instantiate(signature, "_repair_reference_")
        elif node.tag == "lam":
            parameter = annotation(node.value)
            result = visit(node.children[0], (parameter,) + env, path + (0,))
            actual = Arrow(parameter, result)
        elif node.tag == "app":
            function = visit(node.children[0], env, path + (0,))
            argument = visit(node.children[1], env, path + (1,))
            actual = fresh()
            constrain(function, Arrow(argument, actual))
        else:
            raise TypeInferenceError("repair seeds must be complete programs")
        records.append(Location(path, node, actual, env))
        return actual

    constrain(visit(term, (), ()), request_type)
    return tuple(Location(r.path, r.term, substitute(r.type, constraints),
                          tuple(substitute(t, constraints) for t in r.env))
                 for r in sorted(records, key=lambda r: r.path))


class _ExpansionLimit(Exception):
    pass


class _CpuLimit(Exception):
    pass


class _NormalizationLimit(Exception):
    pass


@dataclass(frozen=True)
class NormalizationResult:
    term: Term | None
    steps: int
    beta_reductions: int
    complete: bool


def _normalize_beta(term, charge, contraction):
    """Strong beta normalization with capture-avoiding de Bruijn substitution."""
    def shift_free(node, amount, cutoff=0):
        charge()
        if node.tag == "var":
            return Term("var", node.value + amount) if node.value >= cutoff else node
        if not node.children:
            return node
        return Term(node.tag, node.value, tuple(
            shift_free(c, amount, cutoff + (node.tag == "lam"))
            for c in node.children))

    def remove_binder(node, argument, depth=0):
        charge()
        if node.tag == "var":
            if node.value == depth:
                return shift_free(argument, depth)
            return Term("var", node.value - 1) if node.value > depth else node
        if not node.children:
            return node
        return Term(node.tag, node.value, tuple(
            remove_binder(c, argument, depth + (node.tag == "lam"))
            for c in node.children))

    def normalize(node):
        charge()
        if node.tag == "app":
            function = normalize(node.children[0])
            if function.tag == "lam":
                reduced = remove_binder(function.children[0], node.children[1])
                contraction()
                return normalize(reduced)
            return Term("app", None, (function, normalize(node.children[1])))
        if node.tag == "lam":
            return Term("lam", node.value, (normalize(node.children[0]),))
        return node

    return normalize(term)


def beta_normal_form(term, max_steps=20000):
    """Return a bounded normalization result; one visited AST node costs a step.

    Visits include normalization, substitution, and free-index shifting. Beta
    contractions are reported separately. This performs no interpreter work.
    A budget failure returns no purported normal form.
    """
    if not isinstance(term, Term):
        raise TypeError("normalization requires a Term")
    if type(max_steps) is not int or max_steps < 0:
        raise ValueError("max_steps must be a nonnegative integer")
    steps = reductions = 0

    def charge():
        nonlocal steps
        if steps >= max_steps:
            raise _NormalizationLimit
        steps += 1

    def contraction():
        nonlocal reductions
        reductions += 1

    try:
        normalized = _normalize_beta(term, charge, contraction)
    except _NormalizationLimit:
        return NormalizationResult(None, steps, reductions, False)
    return NormalizationResult(normalized, steps, reductions, True)


@dataclass
class RepairResult:
    term: Term | None = None
    candidates: int = 0
    log_probability: float | None = None
    evaluation_steps: int = 0
    evaluator_calls: int = 0
    expansions: int = 0
    emitted_enumerator_terms: int = 0
    cached_replacement_terms: int = 0
    generated_full_candidates: int = 0
    duplicate_candidates: int = 0
    invalid_repairs: int = 0
    filtered_wrappers: int = 0
    incompatible_accepted_seeds: int = 0
    normalization_steps: int = 0
    beta_reductions: int = 0
    seed_candidates: int = 0
    repair_candidates: int = 0
    wall_seconds: float = 0.0
    cpu_seconds: float = 0.0
    termination: str = "not_started"
    exhausted: bool = False
    trials: list = field(default_factory=list)
    seed_records: list = field(default_factory=list)


class _CountedGrammar:
    """Charge each noncomplete popped state through its production expansion."""

    def __init__(self, grammar, charge):
        self.grammar, self.charge = grammar, charge

    def productions(self, *args, **kwargs):
        self.charge()
        return self.grammar.productions(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.grammar, name)


class _ReplacementPool:
    def __init__(self, iterator, env, library, result):
        self.iterator, self.env, self.library = iterator, env, library
        self.result = result
        self.cache = []
        self.done = False

    def get(self, index):
        if index < len(self.cache):
            self.result.cached_replacement_terms += 1
            return self.cache[index]
        if self.done:
            raise StopIteration
        for candidate in self.iterator:
            self.result.emitted_enumerator_terms += 1
            term = candidate.term
            for _ in reversed(self.env):
                if term.tag != "lam":
                    break
                term = term.children[0]
            else:
                try:
                    infer(term, env=self.env, library=self.library)
                except TypeInferenceError:
                    self.result.filtered_wrappers += 1
                    continue
                self.cache.append(term)
                return term
            self.result.filtered_wrappers += 1
        self.done = True
        raise StopIteration


def solve_repair(examples, request_type, budget, grammar, *, accepted_seeds=(),
                 seed_prefix=16, max_size=12, max_expansions=20000,
                 step_budget=2000, max_cpu_seconds=None, beta_normalize=False,
                 max_normalization_steps=20000):
    """Try a seed prefix, then fair round-robin single-subterm replacements.

    Seed evaluations count inside ``budget``. Accepted seeds come first, then
    at most ``seed_prefix`` frozen-enumerator terms. Seeds are ordered by their
    number of exact public-example matches, with enumeration order breaking
    ties. All locations get one replacement per round; the whole-program
    location is omitted because it would merely replay baseline enumeration.

    Public-example evaluation continues after a mismatch to obtain the match
    count, and stops at a runtime failure. Every interpreter call and step is
    reported, including that extra ranking work. No hidden examples are read.

    ``beta_normalize=True`` is a separate experimental revision. It normalizes
    generated repairs before the final size/type/grammar checks. Both the raw
    replacement allowance and the normalized candidate must obey ``max_size``.
    All normalization and substitution visits share one explicit task-level
    ``max_normalization_steps`` cap and are reported as search work.
    """
    for name, value in (("budget", budget), ("seed_prefix", seed_prefix),
                        ("max_expansions", max_expansions)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if type(max_size) is not int or max_size < 1:
        raise ValueError("max_size must be a positive integer")
    if type(step_budget) is not int or step_budget < 0:
        raise ValueError("step_budget must be a nonnegative integer")
    if (max_cpu_seconds is not None and
            (type(max_cpu_seconds) not in (int, float) or
             not 0 <= max_cpu_seconds < float("inf"))):
        raise ValueError("max_cpu_seconds must be finite and nonnegative")
    if type(beta_normalize) is not bool:
        raise ValueError("beta_normalize must be a bool")
    if type(max_normalization_steps) is not int or max_normalization_steps < 0:
        raise ValueError("max_normalization_steps must be a nonnegative integer")
    examples = tuple(examples)
    if not examples:
        raise ValueError("search requires public examples")
    accepted_seeds = tuple(accepted_seeds)
    if any(not isinstance(seed, RepairSeed) for seed in accepted_seeds):
        raise TypeError("accepted_seeds must contain RepairSeed provenance records")
    result = RepairResult()
    started, cpu_started = time.perf_counter(), time.process_time()
    seen = set()
    seeds = []

    def check_cpu():
        if (max_cpu_seconds is not None and
                time.process_time() - cpu_started >= max_cpu_seconds):
            raise _CpuLimit

    def charge():
        check_cpu()
        if result.expansions >= max_expansions:
            raise _ExpansionLimit
        result.expansions += 1

    def charge_normalization():
        check_cpu()
        if result.normalization_steps >= max_normalization_steps:
            raise _NormalizationLimit
        result.normalization_steps += 1

    def contraction():
        result.beta_reductions += 1

    counted_grammar = _CountedGrammar(grammar, charge)

    def complete_charge(state):
        if state.complete:
            charge()
        return 0.0

    def stream(type_, size):
        return iter(enumerate_programs(
            type_, counted_grammar, max_size=size, max_expansions=None,
            partial_heuristic=complete_charge, partial_features_only=True))

    def attempt(term, source, path=None, seed_index=None):
        check_cpu()
        result.generated_full_candidates += 1
        if term.size > max_size:
            result.invalid_repairs += 1
            return None
        if beta_normalize:
            term = _normalize_beta(term, charge_normalization, contraction)
        if term in seen:
            result.duplicate_candidates += 1
            return None
        # Failed type/grammar checks cost CPU but no interpreter attempt.
        try:
            if term.size > max_size:
                raise TypeInferenceError("repair exceeds the AST bound")
            unify(infer(term, library=grammar.library), request_type)
            probability = grammar.log_probability(term, request_type=request_type)
        except (TypeInferenceError, ValueError):
            result.invalid_repairs += 1
            return None
        if result.candidates >= budget:
            return None
        seen.add(term)
        result.candidates += 1
        if source == "repair":
            result.repair_candidates += 1
        else:
            result.seed_candidates += 1
        outputs, matched, failure, interrupted = [], 0, None, False
        try:
            for inputs, expected in examples:
                check_cpu()
                assessment = evaluate(term, inputs, library=grammar.library,
                                      step_budget=step_budget)
                result.evaluator_calls += 1
                result.evaluation_steps += assessment.steps
                if not assessment.ok:
                    failure = assessment.error
                    break
                outputs.append(assessment.value)
                matched += assessment.value == expected
        except _CpuLimit:
            interrupted = True
        trial = {"term": term.to_dict(), "source": source,
                 "seed_index": seed_index, "path": list(path) if path else [],
                 "matched_examples": matched, "outputs": outputs,
                 "runtime_failure": failure, "incomplete": interrupted,
                 "public_match": not interrupted and matched == len(examples),
                 "log_probability": probability}
        result.trials.append(trial)
        if interrupted:
            raise _CpuLimit
        if trial["public_match"]:
            result.term, result.log_probability = term, probability
        return trial

    def remember_seed(term, provenance):
        trial = attempt(term, "seed")
        if trial is not None:
            actual = Term.from_dict(trial["term"])
            seeds.append((actual, trial["matched_examples"], len(seeds)))
            result.seed_records.append({"term": term.to_dict(), **provenance})

    try:
        if budget == 0:
            result.termination = "candidate_budget"
            return result
        for seed in accepted_seeds:
            try:
                unify(infer(seed.term, library=grammar.library), request_type)
            except TypeInferenceError:
                result.incompatible_accepted_seeds += 1
                continue
            remember_seed(seed.term, {"source": "verified_train",
                                      "training_record": seed.training_record})
            if result.term is not None or result.candidates >= budget:
                break
        if result.term is None and result.candidates < budget:
            initial = stream(request_type, max_size)
            for index in range(seed_prefix):
                try:
                    candidate = next(initial)
                except StopIteration:
                    break
                result.emitted_enumerator_terms += 1
                remember_seed(candidate.term, {"source": "frozen_enumerator",
                                               "prefix_index": index})
                if result.term is not None or result.candidates >= budget:
                    break
        if result.term is not None:
            result.termination = "public_match"
            return result
        if result.candidates >= budget:
            result.termination = "candidate_budget"
            return result
        pools, schedules = {}, deque()
        for seed, _, seed_index in sorted(seeds, key=lambda s: (-s[1], s[2])):
            for location in typed_locations(seed, request_type, grammar.library):
                if not location.path:
                    continue
                allowance = max_size - (seed.size - location.term.size)
                key = (location.type, location.env, allowance)
                if key not in pools:
                    closed_type = arrows(*reversed(location.env), location.type)
                    pools[key] = _ReplacementPool(
                        stream(closed_type, allowance + len(location.env)),
                        location.env, grammar.library, result)
                schedules.append([seed, seed_index, location, pools[key], 0])
        while schedules and result.candidates < budget and result.term is None:
            check_cpu()
            seed, seed_index, location, pool, index = schedules.popleft()
            try:
                replacement = pool.get(index)
            except StopIteration:
                continue
            candidate = replace_subterm(seed, location.path, replacement)
            attempt(candidate, "repair", location.path, seed_index)
            schedules.append([seed, seed_index, location, pool, index + 1])
        if result.term is not None:
            result.termination = "public_match"
        elif result.candidates >= budget:
            result.termination = "candidate_budget"
        else:
            result.termination = "repair_space_exhausted"
            result.exhausted = True
    except _ExpansionLimit:
        result.termination = "expansion_budget"
    except _CpuLimit:
        result.termination = "cpu_budget"
    except _NormalizationLimit:
        result.termination = "normalization_budget"
    finally:
        result.wall_seconds = time.perf_counter() - started
        result.cpu_seconds = time.process_time() - cpu_started
    return result
