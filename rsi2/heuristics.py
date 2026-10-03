"""The improver is a typed DSL program synthesized by the current searcher.

Each generation has six proposal slots: four current-grammar enumerations and
two seeded subtree mutations. A fixed public development subsample screens
them, the best two are confirmed, and only a strict increase in full validation
solved fraction replaces the incumbent. No outcome changes these parameters.
"""
from __future__ import annotations

from itertools import count
import random
import time

from .enumeration import enumerate_programs
from .grammar import Grammar
from .measurement import assess
from .search import HEURISTIC_TYPE
from .terms import Int, Lam, Term, pretty
from .types import (PRIMITIVE_TYPES, TVar, Type, TypeInferenceError, function_parts,
                    infer, library_entries, library_entry, unify)


N_H = 4
N_M = 2
SCREEN_TASKS = 4
SCREEN_DIVISOR = 4
CONFIRM_CANDIDATES = 2
FIXED_PARAMETERS = {"N_h": N_H, "N_m": N_M, "screen_tasks": SCREEN_TASKS,
                    "screen_budget_divisor": SCREEN_DIVISOR,
                    "confirm_candidates": CONFIRM_CANDIDATES}
MUTATION_SEED_MULTIPLIER = 1000003


def zero_heuristic():
    """The sole initial heuristic; all later candidates come from search."""
    result = Int(0)
    for parameter in reversed(function_parts(HEURISTIC_TYPE)[0]):
        result = Lam(parameter, result)
    return result


def _search_config(config):
    supplied = config.get("heuristics", FIXED_PARAMETERS)
    if supplied != FIXED_PARAMETERS:
        raise ValueError("heuristic synthesis parameters are preregistered and fixed")
    searchconfig = dict(config["search"])
    if (searchconfig.get("max_size") != 12 or searchconfig.get("max_expansions") != 20000
            or searchconfig.get("step_budget") != 2000 or config["B_eval"] != 64):
        raise ValueError("heuristic synthesis requires the frozen size/expansion/step and calibrated budget")
    return searchconfig


def synthesis_grammar(grammar, primitive_only=False):
    """Change only the synthesis vocabulary, preserving every learned weight."""
    return Grammar(library={} if primitive_only else grammar.library,
                   primitives=grammar.primitives, constants=grammar.constants,
                   weights=grammar.weights, context_weights=grammar.context_weights)


def inline_library(term, library):
    """Expand closed library bodies without capture or shared scheme variables."""
    entries = library_entries(library)
    serials = count()
    used = set()

    def collect_type(type_):
        if type_.is_variable:
            used.add(type_.name)
        else:
            for argument in type_.args:
                collect_type(argument)

    def collect(node):
        if node.tag == "lam":
            collect_type(node.value)
        for child in node.children:
            collect(child)

    collect(term)
    for entry in entries.values():
        body, _ = library_entry(entry)
        if body is not None:
            collect(body)

    def fresh_body(body):
        variables = {}

        def annotation(type_):
            if type_.is_variable:
                if type_.name not in variables:
                    name = f"_inline_{next(serials)}"
                    while name in used:
                        name = f"_inline_{next(serials)}"
                    used.add(name)
                    variables[type_.name] = TVar(name)
                return variables[type_.name]
            return Type(type_.tag, tuple(annotation(a) for a in type_.args))

        def visit(node):
            value = annotation(node.value) if node.tag == "lam" else node.value
            return Term(node.tag, value, tuple(visit(c) for c in node.children))

        return visit(body)

    def expand(node, active):
        reference = node.tag == "ref" or (node.tag == "prim" and node.value not in PRIMITIVE_TYPES)
        if reference:
            name = node.value
            if name not in entries or name in active:
                raise TypeInferenceError(f"missing or recursive library reference {name!r}")
            body, _ = library_entry(entries[name])
            if body is None:
                raise TypeInferenceError(f"library entry {name!r} has no inlineable body")
            infer(body, library=library)  # Closedness matters when copying under binders.
            return expand(fresh_body(body), active | {name})
        return Term(node.tag, node.value, tuple(expand(c, active) for c in node.children))

    return expand(term, set())


def _occurrences(term, env=(), path=()):
    yield path, term, env
    for index, child in enumerate(term.children):
        bindings = (term.value,) + env if term.tag == "lam" else env
        yield from _occurrences(child, bindings, path + (index,))


def _replace(term, path, replacement):
    if not path:
        return replacement
    children = list(term.children)
    children[path[0]] = _replace(children[path[0]], path[1:], replacement)
    return Term(term.tag, term.value, tuple(children))


def mutate(incumbent, grammar, rng, searchconfig, *, template_library=None,
           primitive_only=False):
    """Replace a seeded original-incumbent subtree with a closed enumerated term.

    Both vocabulary arms use the same original paths and random seed schedule.
    The primitive arm expands any retained incumbent references after replacing
    the subtree; its resulting candidate contains only base DSL productions.
    """
    template_library = grammar.library if template_library is None else template_library
    occurrences = list(_occurrences(incumbent))
    path, node, env = occurrences[rng.randrange(len(occurrences))]
    try:
        requested = infer(node, env=env, library=template_library)
        replacement_budget = searchconfig["max_size"] - incumbent.size + node.size
        iterator = enumerate_programs(requested, grammar, max_size=replacement_budget,
                                      max_expansions=searchconfig["max_expansions"])
        replacement = next(iterator, None)
        if replacement is None:
            return None, path, "replacement_space_exhausted"
        result = _replace(incumbent, path, replacement.term)
        if primitive_only:
            result = inline_library(result, template_library)
        if result.size > searchconfig["max_size"]:
            return result, path, "candidate_size_bound"
        unify(infer(result, library=grammar.library), HEURISTIC_TYPE)
        return result, path, None
    except (TypeError, ValueError) as exc:
        return None, path, f"invalid_mutation: {exc}"


def candidate_attempts(state, config, *, primitive_only=False):
    """Produce all six logged slots, including unavailable or invalid draws."""
    searchconfig = _search_config(config)
    grammar = synthesis_grammar(state.grammar, primitive_only)
    incumbent = state.heuristic if state.heuristic is not None else zero_heuristic()
    iterator = iter(enumerate_programs(HEURISTIC_TYPE, grammar,
                                       max_size=searchconfig["max_size"],
                                       max_expansions=searchconfig["max_expansions"]))
    records = []
    for _ in range(N_H):
        candidate = next(iterator, None)
        records.append({"origin": "enumeration", "term": candidate.term if candidate else None,
                        "mutation_path": None,
                        "rejection": None if candidate else "enumerator_exhausted"})
    rng = random.Random(state.seed * MUTATION_SEED_MULTIPLIER + state.generation)
    for _ in range(N_M):
        term, path, rejection = mutate(incumbent, grammar, rng, searchconfig,
                                       template_library=state.grammar.library,
                                       primitive_only=primitive_only)
        records.append({"origin": "mutation", "term": term,
                        "mutation_path": list(path), "rejection": rejection})
    for index, record in enumerate(records):
        record.update({"index": index, "generation": state.generation,
                       "screen": None, "full": None, "adopted": False,
                       "duplicate": False})
    return records


def improve_heuristic(state, validation, config, *, primitive_only=False, update_state=True):
    """Screen, confirm, and optionally adopt a strictly better DSL heuristic.

    Counterfactual callers use ``primitive_only=True, update_state=False``.
    Their task measurements still use the same current task grammar, library,
    recognition conditioner, and incumbent. Reports account for every proposal
    slot and every complete program attempted in all inner task searches.
    """
    searchconfig = _search_config(config)
    validation = sorted(validation, key=lambda task: task.name)
    if not validation:
        raise ValueError("heuristic improvement requires validation tasks")
    started, cpu_started = time.perf_counter(), time.process_time()
    incumbent = state.heuristic if state.heuristic is not None else zero_heuristic()
    synthesis = synthesis_grammar(state.grammar, primitive_only)
    incumbent_full = assess(validation, state.grammar, state.heuristic, config["B_eval"],
                            searchconfig, conditioner=state.condition)
    inner_evaluations = incumbent_full["candidate_evaluations"]
    records = candidate_attempts(state, config, primitive_only=primitive_only)
    seen = {inline_library(incumbent, state.grammar.library) if primitive_only else incumbent}
    screened = []
    subsample = validation[:SCREEN_TASKS]
    screen_budget = config["B_eval"] // SCREEN_DIVISOR
    for record in records:
        term = record["term"]
        if record["rejection"] is not None or term is None:
            continue
        try:
            unify(infer(term, library=synthesis.library), HEURISTIC_TYPE)
        except (TypeError, ValueError) as exc:
            record["rejection"] = f"invalid_type: {exc}"
            continue
        record["duplicate"] = term in seen
        seen.add(term)
        screen = assess(subsample, state.grammar, term, screen_budget, searchconfig,
                        conditioner=state.condition)
        record["screen"] = screen
        inner_evaluations += screen["candidate_evaluations"]
        screened.append(record)

    # Screen solved fraction ranks candidates; fixed proposal order breaks
    # ties. Candidate cost is recorded but never changes an adoption decision.
    screened.sort(key=lambda record: (-record["screen"]["solved_fraction"], record["index"]))
    confirmed = screened[:CONFIRM_CANDIDATES]
    for record in screened[CONFIRM_CANDIDATES:]:
        record["rejection"] = "not_confirmed"
    best_term = inline_library(incumbent, state.grammar.library) if primitive_only else incumbent
    best_fraction = incumbent_full["solved_fraction"]
    adopted_index = None
    for record in confirmed:
        full = assess(validation, state.grammar, record["term"], config["B_eval"],
                      searchconfig, conditioner=state.condition)
        record["full"] = full
        inner_evaluations += full["candidate_evaluations"]
        if full["solved_fraction"] > best_fraction:
            best_term, best_fraction = record["term"], full["solved_fraction"]
            adopted_index = record["index"]
    for record in confirmed:
        record["adopted"] = record["index"] == adopted_index
        if not record["adopted"]:
            record["rejection"] = "no_strict_improvement" if record["full"]["solved_fraction"] <= incumbent_full["solved_fraction"] else "better_candidate_selected"

    report = {"generation": state.generation, "seed": state.seed,
              "primitive_only": primitive_only, "update_state": update_state,
              "parameters": dict(FIXED_PARAMETERS), "screen_budget": screen_budget,
              "screen_task_names": [task.name for task in subsample],
              "incumbent": incumbent.to_dict(), "incumbent_full": incumbent_full,
              "best_full_fraction": best_fraction, "best_term": best_term.to_dict(),
              "adopted": adopted_index is not None, "adopted_index": adopted_index,
              "synthesis_candidate_evaluations": N_H + N_M,
              "inner_candidate_evaluations": inner_evaluations,
              "candidate_evaluations": inner_evaluations + N_H + N_M,
              "wall_seconds": time.perf_counter() - started,
              "cpu_seconds": time.process_time() - cpu_started,
              "candidates": [{**record,
                              "term": record["term"].to_dict() if record["term"] is not None else None,
                              "readable": pretty(record["term"]) if record["term"] is not None else None}
                             for record in records]}
    if update_state:
        if adopted_index is not None:
            state.heuristic = best_term
        state.heuristic_history.append(report)
        state.logical_evaluations += report["candidate_evaluations"]
    return report
