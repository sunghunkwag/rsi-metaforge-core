"""Typed population search whose DSL scorer changes future program production.

Roots come from the frozen enumerator or supplied verifier-accepted TRAIN
records. Descendants come from the same enumerator's typed local replacements;
each retains its parent and root provenance. Failed descendants may receive
further edits, but this module never promotes them to verified library labels.

Alternating guided and FIFO turns gives a heuristic a causal role in producing
future candidates while preserving continuing edit opportunities for parents.
The zero scorer and no scorer use the same kernel and candidate sequence.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time

from ..enumeration import enumerate_programs
from ..evaluator import evaluate
from ..search import HEURISTIC_TYPE, flatten
from ..terms import Term, replace_subterm
from ..types import TypeInferenceError, arrows, infer, unify
from .repair_search import (
    RepairResult, RepairSeed, _CountedGrammar, _CpuLimit, _ExpansionLimit,
    _NormalizationLimit, _ReplacementPool, _normalize_beta, typed_locations,
)
from .proposals import canonical_term


@dataclass
class PopulationResult(RepairResult):
    heuristic_calls: int = 0
    heuristic_evaluations: int = 0
    heuristic_steps: int = 0
    heuristic_failures: int = 0
    parent_selections: list = field(default_factory=list)
    parent_records: list = field(default_factory=list)
    seed: int = 11
    force_wrapper_lambdas: bool = True
    canonicalization_enabled: bool = True
    canonicalization_steps: int = 0


@dataclass
class _Parent:
    id: int
    term: Term
    root_id: int
    depth: int
    score: int
    edits: object
    last_turn: int = -1


class _WrapperGrammar(_CountedGrammar):
    """Require an open replacement's binders without refitting probabilities."""

    def __init__(self, grammar, charge, binders):
        super().__init__(grammar, charge)
        self.binders = binders

    def productions(self, *args, **kwargs):
        choices = super().productions(*args, **kwargs)
        env = args[1] if len(args) > 1 else kwargs.get("env", ())
        if len(env) < self.binders:
            return tuple(choice for choice in choices if choice.is_lambda)
        return choices


class _LiveExpansionLimit:
    """Read the shared quota before every pop, including resumed iterators."""

    def __init__(self, result, maximum, check):
        self.result, self.maximum, self.check = result, maximum, check

    def __lt__(self, other):
        return self.maximum < other  # Frozen iterator validates its limit < 0.

    def __gt__(self, _local_count):
        self.check()
        return self.result.expansions < self.maximum


def solve_population(examples, request_type, budget, grammar, *,
                     accepted_seeds=(), heuristic=None, seed=11, seed_prefix=16,
                     max_size=12, max_expansions=20000, step_budget=2000,
                     max_cpu_seconds=None, beta_normalize=False,
                     max_normalization_steps=20000, force_wrapper_lambdas=True,
                     edit_provider=None):
    """Produce, evaluate, and recursively edit a budgeted program population.

    Every unique complete program attempted consumes one candidate evaluation.
    All public examples are evaluated for parent scoring; a runtime failure
    supplies empty flattened outputs. A matching candidate terminates before
    heuristic evaluation, so a scorer cannot rerank already charged successes.

    ``seed`` is recorded for controller compatibility. This kernel's choices
    are deterministic; its only learned parent priority comes from the supplied
    DSL heuristic. On alternating turns, highest score wins with least-recent
    turn/id tie breaks, or FIFO selects and rotates a parent. Every selected
    parent contributes at most one generated full program on that turn.

    Enumeration, normalization, evaluator, and heuristic work have independent
    explicit counters. Enumeration and normalization caps are global per task,
    including roots and all parents. The CPU guard preserves completed trials
    and marks any interrupted public-example assessment as incomplete.

    ``force_wrapper_lambdas`` restricts replacement enumeration's declared
    binder prefix to the grammar's existing lambda production. Its original
    normalized log probability is retained. Root enumeration is unrestricted;
    after the required binders, every original production remains available.

    Type-variable alpha names are canonicalized before novelty, typing, and
    scoring. A metered structural prewalk charges each canonicalizer AST/type
    visit to the normalization quota; transformation and metering CPU are both
    included. Raw roots, replacements, and full candidates remain in provenance.
    """
    started, cpu_started = time.perf_counter(), time.process_time()
    for name, value in (("budget", budget), ("seed_prefix", seed_prefix),
                        ("max_expansions", max_expansions),
                        ("max_normalization_steps", max_normalization_steps)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if type(max_size) is not int or max_size < 1:
        raise ValueError("max_size must be a positive integer")
    if type(step_budget) is not int or step_budget < 0:
        raise ValueError("step_budget must be a nonnegative integer")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(beta_normalize) is not bool:
        raise ValueError("beta_normalize must be a bool")
    if type(force_wrapper_lambdas) is not bool:
        raise ValueError("force_wrapper_lambdas must be a bool")
    if edit_provider is not None and not callable(edit_provider):
        raise TypeError("edit_provider must be callable or None")
    if (max_cpu_seconds is not None and
            (type(max_cpu_seconds) not in (int, float) or
             not 0 <= max_cpu_seconds < float("inf"))):
        raise ValueError("max_cpu_seconds must be finite and nonnegative")
    examples, accepted_seeds = tuple(examples), tuple(accepted_seeds)
    if not examples:
        raise ValueError("population search requires public examples")
    if any(not isinstance(record, RepairSeed) for record in accepted_seeds):
        raise TypeError("accepted_seeds must contain RepairSeed TRAIN records")
    if heuristic is not None:
        if not isinstance(heuristic, Term):
            raise TypeError("heuristic must be a DSL Term")
        unify(infer(heuristic, library=grammar.library), HEURISTIC_TYPE)

    result = PopulationResult(seed=seed, force_wrapper_lambdas=force_wrapper_lambdas)
    seen, pools, active, fifo, heuristic_cache = set(), {}, {}, deque(), {}
    target = flatten([expected for _, expected in examples])
    turn = 0

    def check_cpu():
        if (max_cpu_seconds is not None and
                time.process_time() - cpu_started >= max_cpu_seconds):
            raise _CpuLimit

    def charge_expansion():
        if result.expansions >= max_expansions:
            raise _ExpansionLimit
        result.expansions += 1
        # This state has already been popped. Preserve its charge if CPU
        # expires before the following production expansion/materialization.
        check_cpu()

    def charge_normalization():
        check_cpu()
        if result.normalization_steps >= max_normalization_steps:
            raise _NormalizationLimit
        result.normalization_steps += 1

    def contraction():
        result.beta_reductions += 1

    def canonicalize(term):
        pending = [term]
        while pending:
            node = pending.pop()
            charge_normalization()
            result.canonicalization_steps += 1
            pending.extend(node.children)
            if node.tag in ("lam", "hole"):
                types = [node.value]
                while types:
                    annotation = types.pop()
                    charge_normalization()
                    result.canonicalization_steps += 1
                    if not annotation.is_variable:
                        types.extend(annotation.args)
        canonical = canonical_term(term)
        check_cpu()
        return canonical

    def complete_charge(state):
        if state.complete:
            charge_expansion()
        return 0.0

    def stream(type_, size, binders=0):
        counted = _WrapperGrammar(
            grammar, charge_expansion, binders if force_wrapper_lambdas else 0)
        live_limit = _LiveExpansionLimit(result, max_expansions, check_cpu)
        yield from enumerate_programs(
            type_, counted, max_size=size, max_expansions=live_limit,
            partial_heuristic=complete_charge, partial_features_only=True)
        if result.expansions >= max_expansions:
            raise _ExpansionLimit

    def edits(parent_term):
        if edit_provider is not None:
            yield from edit_provider(
                parent_term, request_type=request_type, grammar=grammar, max_size=max_size,
                max_expansions=max_expansions,
                max_normalization_steps=max_normalization_steps,
                charge_expansion=charge_expansion,
                charge_normalization=charge_normalization, check_cpu=check_cpu)
            return
        schedule = deque()
        for location in typed_locations(parent_term, request_type, grammar.library):
            if not location.path:
                continue
            allowance = max_size - (parent_term.size - location.term.size)
            key = (location.type, location.env, allowance)
            if key not in pools:
                closed = arrows(*reversed(location.env), location.type)
                pools[key] = _ReplacementPool(
                    stream(closed, allowance + len(location.env), len(location.env)),
                    location.env, grammar.library, result)
            schedule.append((location, pools[key], 0))
        while schedule:
            check_cpu()
            location, pool, index = schedule.popleft()
            try:
                replacement = pool.get(index)
            except StopIteration:
                continue
            schedule.append((location, pool, index + 1))
            yield (replace_subterm(parent_term, location.path, replacement),
                   location.path, replacement)

    def score_parent(term, outputs):
        if heuristic is None:
            return 0, None
        check_cpu()
        result.heuristic_calls += 1
        flat_outputs = flatten(outputs)
        key = (tuple(flat_outputs), term.size, term.depth)
        if key not in heuristic_cache:
            assessment = evaluate(
                heuristic, (flat_outputs, target, term.size, term.depth),
                library=grammar.library, step_budget=step_budget)
            result.heuristic_evaluations += 1
            result.heuristic_steps += assessment.steps
            check_cpu()
            valid = (assessment.ok and type(assessment.value) is int and
                     assessment.value.bit_length() <= 1023)
            if not valid:
                result.heuristic_failures += 1
            heuristic_cache[key] = (assessment.value if valid else 0,
                                    None if valid else assessment.error or
                                    "heuristic must return a bounded integer")
        return heuristic_cache[key]

    def attempt(raw, source, *, parent=None, path=(), replacement=None, origin=None):
        check_cpu()
        result.generated_full_candidates += 1
        if raw.size > max_size:
            result.invalid_repairs += 1
            return
        term = (_normalize_beta(raw, charge_normalization, contraction)
                if beta_normalize else raw)
        term = canonicalize(term)
        if term in seen:
            result.duplicate_candidates += 1
            return
        try:
            if term.size > max_size:
                raise TypeInferenceError("normalized candidate exceeds AST bound")
            unify(infer(term, library=grammar.library), request_type)
            probability = grammar.log_probability(term, request_type=request_type)
        except (TypeInferenceError, ValueError):
            result.invalid_repairs += 1
            return
        if result.candidates >= budget:
            return
        seen.add(term)
        trial_id = result.candidates
        result.candidates += 1
        if parent is None:
            result.seed_candidates += 1
        else:
            result.repair_candidates += 1
        outputs, matched, failure, interrupted = [], 0, None, False
        try:
            for inputs, expected in examples:
                check_cpu()
                assessment = evaluate(term, inputs, library=grammar.library,
                                      step_budget=step_budget)
                result.evaluator_calls += 1
                result.evaluation_steps += assessment.steps
                if not assessment.ok:
                    failure, outputs = assessment.error, []
                    check_cpu()
                    break
                outputs.append(assessment.value)
                matched += assessment.value == expected
                check_cpu()
        except _CpuLimit:
            interrupted = True
        root_id = trial_id if parent is None else parent.root_id
        trial = {"id": trial_id, "term": term.to_dict(), "raw_term": raw.to_dict(),
                 "source": source,
                 "parent_id": None if parent is None else parent.id,
                 "root_id": root_id, "depth": 0 if parent is None else parent.depth + 1,
                 "path": list(path),
                 "replacement": None if replacement is None else replacement.to_dict(),
                 "matched_examples": matched, "outputs": outputs,
                 "runtime_failure": failure, "incomplete": interrupted,
                 "public_match": not interrupted and matched == len(examples),
                 "log_probability": probability, "heuristic_score": None,
                 "heuristic_failure": None, "heuristic_incomplete": False}
        result.trials.append(trial)
        if parent is not None and origin is not None:
            trial["edit_provenance"] = origin
        if parent is None:
            result.seed_records.append({"trial_id": trial_id, "term": raw.to_dict(),
                                        **origin})
        if interrupted:
            raise _CpuLimit
        if trial["public_match"]:
            result.term, result.log_probability = term, probability
            return
        try:
            score, heuristic_failure = score_parent(term, outputs)
        except _CpuLimit:
            trial["heuristic_incomplete"] = True
            raise
        trial["heuristic_score"], trial["heuristic_failure"] = score, heuristic_failure
        entry = _Parent(trial_id, term, root_id, trial["depth"], score, edits(term))
        active[trial_id] = entry
        fifo.append(trial_id)
        result.parent_records.append({"id": trial_id, "root_id": root_id,
                                      "parent_id": trial["parent_id"],
                                      "depth": trial["depth"], "score": score})

    try:
        if budget == 0:
            result.termination = "candidate_budget"
            return result
        for record in accepted_seeds:
            try:
                unify(infer(record.term, library=grammar.library), request_type)
            except TypeInferenceError:
                result.incompatible_accepted_seeds += 1
                continue
            attempt(record.term, "verified_train_root", origin={
                "source": "verified_train", "training_record": record.training_record})
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
                attempt(candidate.term, "enumerated_root", origin={
                    "source": "frozen_enumerator", "prefix_index": index})
                if result.term is not None or result.candidates >= budget:
                    break
        while active and result.candidates < budget and result.term is None:
            check_cpu()
            guided = turn % 2 == 0
            if guided:
                selected = min(active.values(), key=lambda p: (-p.score, p.last_turn, p.id))
                fifo.remove(selected.id)
            else:
                selected = active[fifo.popleft()]
            selected.last_turn = turn
            selection = {"turn": turn, "kind": "guided" if guided else "fifo",
                         "parent_id": selected.id, "parent_score": selected.score,
                         "child_trial_id": None, "generated": False}
            result.parent_selections.append(selection)
            turn += 1
            try:
                edit = next(selected.edits)
                candidate, path, replacement = edit[:3]
                provenance = edit[3] if len(edit) == 4 else None
            except StopIteration:
                del active[selected.id]
                continue
            selection["generated"] = True
            # Rotation happens before descendant insertion, so later births
            # cannot move ahead of parents already waiting for FIFO turns.
            fifo.append(selected.id)
            previous_count = result.candidates
            attempt(candidate, "descendant", parent=selected,
                    path=path, replacement=replacement, origin=provenance)
            if result.candidates > previous_count:
                selection["child_trial_id"] = result.candidates - 1
        if result.term is not None:
            result.termination = "public_match"
        elif result.candidates >= budget:
            result.termination = "candidate_budget"
        else:
            result.termination, result.exhausted = "population_exhausted", True
    except _ExpansionLimit:
        result.termination = "expansion_budget"
    except _NormalizationLimit:
        result.termination = "normalization_budget"
    except _CpuLimit:
        result.termination = "cpu_budget"
    finally:
        result.wall_seconds = time.perf_counter() - started
        result.cpu_seconds = time.process_time() - cpu_started
    return result
