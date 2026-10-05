"""Novel, locally scoped own-grammar proposals for the frozen heuristic API.

The four interface lambdas are prescribed binders, not a handwritten heuristic
body. A proxy restricts only those wrapper productions; every body production,
probability and library reference comes from the supplied current Grammar.
Candidate-independent syntax is filtered before the owner evaluates proposals.
This syntactic condition is necessary, not sufficient, for useful scoring.

Each call rebuilds enumeration with global AST novelty across grammar refits.
All replay, filtering, local replacement enumeration and beta normalization is
reported. Four enumeration slots and two seeded mutation slots stay fixed.
No evaluator, task loader, hidden examples or task identifiers are used here.
"""
from __future__ import annotations

import json
import math
import random
import time

from ..enumeration import enumerate_programs
from ..heuristics import (MUTATION_SEED_MULTIPLIER, inline_library,
                          synthesis_grammar, zero_heuristic)
from ..search import HEURISTIC_TYPE
from ..terms import Term, replace_subterm
from ..types import function_parts, infer, library_entries, library_entry, arrows, unify
from .proposals import canonical_term
from .repair_search import beta_normal_form, typed_locations


ENUMERATION_SLOTS = 4
MUTATION_SLOTS = 2
_BODY_PATH = (0, 0, 0, 0)
_CANDIDATE_ARGUMENTS = frozenset((0, 1, 3))  # depth, size, outputs; target is 2.


def candidate_dependencies(term):
    """Return body references to interface arguments, respecting inner binders."""
    parameters, _ = function_parts(HEURISTIC_TYPE)
    body = term
    for parameter in parameters:
        if body.tag != "lam":
            raise ValueError("heuristic proposals require the four interface lambdas")
        unify(body.value, parameter)
        body = body.children[0]
    result = set()

    def visit(node, depth=0):
        if node.tag == "var" and node.value >= depth:
            index = node.value - depth
            if index >= 4:
                raise ValueError("heuristic body has an unbound variable")
            result.add(index)
        for child in node.children:
            visit(child, depth + (node.tag == "lam"))

    visit(body)
    return tuple(sorted(result))


def _key(term):
    return json.dumps(canonical_term(term).to_dict(), sort_keys=True, separators=(",", ":"))


def _library_snapshot(grammar):
    result = {}
    for name, entry in library_entries(grammar.library).items():
        body, declared = library_entry(entry)
        result[name] = {
            "term": None if body is None else canonical_term(body).to_dict(),
            "type": None if declared is None else declared.to_dict(),
        }
    return result


class _Stopped(Exception):
    def __init__(self, reason):
        self.reason = reason


class _WrapperGrammar:
    """Force only a closed wrapper prefix while metering partial frontier pops."""
    def __init__(self, grammar, parameters, charge):
        self.grammar, self.parameters, self.charge = grammar, parameters, charge

    def productions(self, request_type, env=(), substitutions=None, context=("ROOT", 0)):
        self.charge(False)
        choices = self.grammar.productions(request_type, env, substitutions, context)
        if len(env) < len(self.parameters):
            return tuple(choice for choice in choices if choice.is_lambda)
        return choices

    def __getattr__(self, name):
        return getattr(self.grammar, name)


class HeuristicProposalProvider:
    """Use a fresh provider per arm/seed; preserve it across all generations.

    Old library definitions must survive unchanged when the library grows.
    Novelty is global, including filtered draws, so a grammar weight refit cannot
    reset proposal discovery to the same four syntax trees. Rebuilding work is
    charged again rather than attributed to free continuation.
    """
    def __init__(self):
        self._seen = {}
        self._library = {}
        self.last_report = None

    def propose(self, incumbent, grammar, seed, generation, limits):
        """Return ``{records: six attempts, work: metered construction, ...}``."""
        cpu, wall = time.process_time(), time.perf_counter()
        max_size = limits.get("max_size", 12)
        max_expansions = limits.get("max_expansions", 20000)
        normalization_limit = limits.get("max_normalization_steps", 20000)
        max_cpu = limits.get("max_cpu_seconds")
        for name, value, ceiling in (("max_size", max_size, 12),
                                     ("max_expansions", max_expansions, 20000),
                                     ("max_normalization_steps", normalization_limit, 20000),
                                     ("step_budget", limits.get("step_budget", 2000), 2000)):
            if type(value) is not int or value < 0 or value > ceiling:
                raise ValueError(f"invalid {name}")
        if (max_cpu is not None and
                (type(max_cpu) not in (int, float) or not math.isfinite(max_cpu) or max_cpu < 0)):
            raise ValueError("max_cpu_seconds must be finite and nonnegative")
        if type(seed) is not int or type(generation) is not int or generation < 0:
            raise ValueError("seed and nonnegative generation must be integers")
        current_library = _library_snapshot(grammar)
        if any(current_library.get(name) != entry for name, entry in self._library.items()):
            raise ValueError("old library definitions must remain available and unchanged")
        self._library = current_library
        incumbent = zero_heuristic() if incumbent is None else incumbent
        unify(infer(incumbent, library=grammar.library), HEURISTIC_TYPE)
        candidate_dependencies(incumbent)
        incumbent_key = _key(incumbent)
        work = {"partial_frontier_pops": 0, "complete_frontier_pops": 0,
                "frontier_pops": 0, "enumerator_terms": 0,
                "enumeration_terms": 0, "mutation_wrapper_terms": 0,
                "generated_full_candidates": 0, "normalized_mutation_candidates": 0,
                "replayed_ast_draws": 0,
                "filtered_ast_draws": 0, "normalization_steps": 0,
                "beta_reductions": 0, "typing_checks": 0,
                "incumbent_typing_checks": 1, "joint_location_inference_calls": 0,
                "raw_draws": []}
        records = []
        termination = None

        def check_cpu():
            if max_cpu is not None and time.process_time() - cpu >= max_cpu:
                raise _Stopped("cpu_budget")

        def charge(complete):
            if work["frontier_pops"] >= max_expansions:
                raise _Stopped("expansion_budget")
            work["frontier_pops"] += 1
            work["complete_frontier_pops" if complete else "partial_frontier_pops"] += 1
            check_cpu()

        def stream(request, parameters, size):
            def complete(state):
                if state.complete:
                    charge(True)
                return 0.0
            return iter(enumerate_programs(
                request, _WrapperGrammar(grammar, parameters, charge),
                max_size=size, max_expansions=max_expansions - work["frontier_pops"],
                partial_heuristic=complete, partial_features_only=True))

        def inspect(term, origin, slot, raw):
            term = canonical_term(term)
            key = _key(term)
            rejection = None
            if term.size > max_size:
                rejection = "candidate_size_bound"
            else:
                work["typing_checks"] += 1
                try:
                    unify(infer(term, library=grammar.library), HEURISTIC_TYPE)
                    dependencies = candidate_dependencies(term)
                    raw["dependencies"] = list(dependencies)
                except (TypeError, ValueError) as exc:
                    rejection = f"invalid_candidate: {exc}"
                else:
                    if key in self._seen:
                        rejection = "replayed_ast"
                        raw["first_generation"] = self._seen[key]["generation"]
                        work["replayed_ast_draws"] += 1
                    elif key == incumbent_key:
                        rejection = "incumbent_ast"
                    elif not _CANDIDATE_ARGUMENTS.intersection(dependencies):
                        rejection = "candidate_independent"
            self._seen.setdefault(key, {"generation": generation, "origin": origin})
            raw.update({"candidate": term.to_dict(), "rejection": rejection})
            work["raw_draws"].append(raw)
            if rejection is not None:
                work["filtered_ast_draws"] += 1
                check_cpu()
                return None
            check_cpu()
            return {"index": slot, "generation": generation, "origin": origin,
                    "term": term, "mutation_path": raw.get("mutation_path"),
                    "rejection": None}

        def unavailable(index, origin, reason, path=None):
            return {"index": index, "generation": generation, "origin": origin,
                    "term": None, "mutation_path": path, "rejection": reason}

        parameters, _ = function_parts(HEURISTIC_TYPE)
        enumeration = stream(HEURISTIC_TYPE, parameters, max_size)
        enumeration_done = False
        for slot in range(ENUMERATION_SLOTS):
            record = None
            if termination is None and not enumeration_done:
                try:
                    while record is None:
                        check_cpu()
                        candidate = next(enumeration, None)
                        if candidate is None:
                            if work["frontier_pops"] >= max_expansions:
                                raise _Stopped("expansion_budget")
                            enumeration_done = True
                            break
                        work["enumerator_terms"] += 1
                        work["enumeration_terms"] += 1
                        work["generated_full_candidates"] += 1
                        record = inspect(candidate.term, "enumeration", slot,
                                         {"origin": "enumeration", "slot": slot,
                                          "enumerated_term": candidate.term.to_dict()})
                except _Stopped as stopped:
                    termination = stopped.reason
            records.append(record if record is not None else unavailable(
                slot, "enumeration", termination or "enumerator_exhausted"))

        rng = random.Random(seed * MUTATION_SEED_MULTIPLIER + generation)
        locations = []
        if termination is None:
            try:
                check_cpu()
                work["joint_location_inference_calls"] += 1
                locations = [location for location in typed_locations(incumbent, HEURISTIC_TYPE,
                                                                       grammar.library)
                             if location.path[:4] == _BODY_PATH]
                check_cpu()
            except _Stopped as stopped:
                termination = stopped.reason
        for slot in range(ENUMERATION_SLOTS, ENUMERATION_SLOTS + MUTATION_SLOTS):
            record, path = None, None
            if termination is None:
                location = locations[rng.randrange(len(locations))]
                path = list(location.path)
                allowance = max_size - incumbent.size + location.term.size
                wrapper_parameters = tuple(reversed(location.env))
                request = arrows(*wrapper_parameters, location.type)
                replacements = stream(request, wrapper_parameters,
                                      min(max_size, allowance + len(wrapper_parameters)))
                try:
                    while record is None:
                        check_cpu()
                        candidate = next(replacements, None)
                        if candidate is None:
                            if work["frontier_pops"] >= max_expansions:
                                raise _Stopped("expansion_budget")
                            break
                        work["enumerator_terms"] += 1
                        work["mutation_wrapper_terms"] += 1
                        replacement = candidate.term
                        for _ in wrapper_parameters:
                            if replacement.tag != "lam":
                                raise ValueError("local enumeration lost its prescribed wrapper")
                            replacement = replacement.children[0]
                        raw_candidate = replace_subterm(incumbent, location.path, replacement)
                        work["generated_full_candidates"] += 1
                        remaining = normalization_limit - work["normalization_steps"]
                        normalized = beta_normal_form(raw_candidate, max_steps=remaining)
                        work["normalization_steps"] += normalized.steps
                        work["beta_reductions"] += normalized.beta_reductions
                        raw = {"origin": "mutation", "slot": slot, "mutation_path": path,
                               "enumerated_term": candidate.term.to_dict(),
                               "raw_candidate": raw_candidate.to_dict(),
                               "normalization_steps": normalized.steps,
                               "beta_reductions": normalized.beta_reductions}
                        if not normalized.complete:
                            raw["rejection"] = "normalization_budget"
                            work["raw_draws"].append(raw)
                            work["filtered_ast_draws"] += 1
                            raise _Stopped("normalization_budget")
                        work["normalized_mutation_candidates"] += 1
                        try:
                            check_cpu()
                        except _Stopped:
                            raw["rejection"] = "cpu_budget"
                            work["raw_draws"].append(raw)
                            work["filtered_ast_draws"] += 1
                            raise
                        record = inspect(normalized.term, "mutation", slot, raw)
                except _Stopped as stopped:
                    termination = stopped.reason
            records.append(record if record is not None else unavailable(
                slot, "mutation", termination or "replacement_space_exhausted", path))

        try:
            check_cpu()
        except _Stopped as stopped:
            termination = stopped.reason
        report = {"records": records, "work": work, "seed": seed, "generation": generation,
                  "enumeration_slots": ENUMERATION_SLOTS, "mutation_slots": MUTATION_SLOTS,
                  "termination": termination or "completed_slots",
                  "novelty_scope": "global_ast_across_immutable_library_extensions_and_weight_refits",
                  "expansion_budget_scope": "entire_call_including_replay_and_mutation",
                  "normalization_budget_scope": "both_mutation_slots",
                  "seen_ast_count": len(self._seen), "cpu_seconds": time.process_time() - cpu,
                  "wall_seconds": time.perf_counter() - wall,
                  "heuristic_evaluations": 0, "heuristic_evaluation_steps": 0}
        self.last_report = report
        return report

    def draw(self, state, config, *, primitive_only=False):
        """Controller adapter; detailed construction telemetry is ``last_report``."""
        cpu, wall = time.process_time(), time.perf_counter()
        grammar = synthesis_grammar(state.grammar, primitive_only)
        incumbent = state.heuristic
        inline_cpu = 0.0
        inline_input_size = inline_output_size = 0
        if primitive_only and incumbent is not None:
            inline_started = time.process_time()
            inline_input_size = incumbent.size
            incumbent = inline_library(incumbent, state.grammar.library)
            inline_output_size = incumbent.size
            inline_cpu = time.process_time() - inline_started
        limits = dict(config["search"])
        if limits.get("max_cpu_seconds") is not None:
            limits["max_cpu_seconds"] = max(0.0, limits["max_cpu_seconds"] - (time.process_time() - cpu))
        report = self.propose(incumbent, grammar, state.seed, state.generation, limits)
        report["primitive_only"] = primitive_only
        report["work"].update({"incumbent_inline_calls": int(primitive_only and state.heuristic is not None),
                               "incumbent_inline_input_size": inline_input_size,
                               "incumbent_inline_output_size": inline_output_size,
                               "incumbent_inline_cpu_seconds": inline_cpu})
        report["cpu_seconds"] = time.process_time() - cpu
        report["wall_seconds"] = time.perf_counter() - wall
        return report["records"]
