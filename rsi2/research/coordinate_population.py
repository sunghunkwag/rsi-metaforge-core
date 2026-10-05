"""The common population controller with generic derivation-coordinate edits.

This adapter changes candidate construction only. It preserves the controller's
own root prefix, verified bank, scorer, public evaluations and acceptance path.
A new provider and meter are created per search, then shared by every parent.
No semantic evaluator or task loader is added by the edit provider.
"""
from __future__ import annotations

import time

from .derivation_neighborhood import NeighborhoodLimit, NeighborhoodMeter, derivation_neighbors
from .population_search import solve_population
from .repair_search import _CpuLimit, _ExpansionLimit, _NormalizationLimit


_COUNTERS = (
    "structural_states", "compiler_steps", "grammar_queries", "production_choices_created",
    "type_checks", "generated", "duplicates", "oversized", "ill_typed", "eta_views",
)


class CoordinateEditProvider:
    """An injectable edit iterator, using the enclosing search's live budgets."""

    def __init__(self, *, eta_exposure=True):
        if type(eta_exposure) is not bool:
            raise TypeError("eta_exposure must be a bool")
        self.eta_exposure = eta_exposure
        self.meter = None

    def __call__(self, parent, *, request_type, grammar, max_size, max_expansions,
                 max_normalization_steps, charge_expansion, charge_normalization, check_cpu):
        if self.meter is None:
            self.meter = NeighborhoodMeter(
                structural_limit=max_expansions, compiler_limit=max_normalization_steps,
                structural_callback=charge_expansion, compiler_callback=charge_normalization,
                check_callback=check_cpu,
            )
        try:
            for neighbor in derivation_neighbors(
                    parent, request_type, grammar, max_size=max_size, meter=self.meter,
                    eta_exposure=self.eta_exposure):
                yield neighbor.term, neighbor.path, neighbor.replacement, neighbor.metadata
        except NeighborhoodLimit as error:
            translated = {"expansion_budget": _ExpansionLimit,
                          "normalization_budget": _NormalizationLimit,
                          "cpu_budget": _CpuLimit}[error.reason]
            raise translated from error

    def snapshot(self):
        return {
            "schema_version": 1, "eta_exposure": self.eta_exposure,
            "structural_unit": "examined grammar choices/permutations/removals and eta views",
            "compiler_unit": "reconstruction/shift/prewalk AST and type visits plus compiler invocations",
            "all_compiler_and_grammar_cpu_in_search_guard": True,
            "semantic_evaluator_calls": 0,
            **{name: getattr(self.meter, name, 0) for name in _COUNTERS},
        }


def solve_coordinate_population(examples, request_type, budget, grammar, *,
                                eta_exposure=True, **kwargs):
    """Use the unchanged controller with a fresh coordinate-neighborhood provider."""
    started, wall_started = time.process_time(), time.perf_counter()
    if "edit_provider" in kwargs:
        raise ValueError("the coordinate adapter owns its edit provider")
    maximum_cpu = kwargs.get("max_cpu_seconds")
    if (maximum_cpu is not None and
            (type(maximum_cpu) not in (int, float) or
             not 0 <= maximum_cpu < float("inf"))):
        raise ValueError("max_cpu_seconds must be finite and nonnegative")
    provider = CoordinateEditProvider(eta_exposure=eta_exposure)
    setup_cpu = time.process_time() - started
    if maximum_cpu is not None:
        kwargs["max_cpu_seconds"] = max(0.0, maximum_cpu - setup_cpu)
    result = solve_population(examples, request_type, budget, grammar,
                              edit_provider=provider, **kwargs)
    result.edit_mode = "coordinates"
    result.neighborhood_work = provider.snapshot()
    result.coordinate_setup_cpu_seconds = setup_cpu
    elapsed = time.process_time() - started
    deadline_exceeded = maximum_cpu is not None and elapsed >= maximum_cpu
    result.coordinate_adapter_deadline_exceeded = deadline_exceeded
    if deadline_exceeded:
        if result.term is not None:
            for trial in result.trials:
                if trial["public_match"]:
                    trial.update(public_match=False, incomplete=True,
                                 coordinate_adapter_deadline_exceeded=True)
            result.term, result.log_probability = None, None
        result.termination, result.exhausted = "cpu_budget", False
    result.cpu_seconds = time.process_time() - started
    result.wall_seconds = time.perf_counter() - wall_started
    return result


def coordinate_kernel_factory():
    """A fresh adapter satisfying recursive_bootstrap's existing kernel interface."""
    def call(examples, request_type, budget, grammar, *, bank, heuristic, seed, limits):
        return solve_coordinate_population(
            examples, request_type, budget, grammar, accepted_seeds=bank,
            heuristic=heuristic, seed=seed, **limits)
    return call
