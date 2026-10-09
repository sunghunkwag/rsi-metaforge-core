"""Prospective population adapter with independent context and priority factors."""
from __future__ import annotations

import time

from .arity_neighborhood import arity_neighbors
from .coordinate_population import _COUNTERS
from .derivation_neighborhood import NeighborhoodLimit, NeighborhoodMeter
from .population_search import solve_population
from .repair_search import _CpuLimit, _ExpansionLimit, _NormalizationLimit


class ArityEditProvider:
    def __init__(self, *, arity_context=False, production_priority=False, eta_exposure=True):
        if any(type(flag) is not bool for flag in (arity_context, production_priority, eta_exposure)):
            raise TypeError("neighborhood switches must be bools")
        self.arity_context = arity_context
        self.production_priority = production_priority
        self.eta_exposure = eta_exposure
        self.meter = None

    def __call__(self, parent, *, request_type, grammar, max_size, max_expansions,
                 max_normalization_steps, charge_expansion, charge_normalization, check_cpu):
        if self.meter is None:
            self.meter = NeighborhoodMeter(
                structural_limit=max_expansions, compiler_limit=max_normalization_steps,
                structural_callback=charge_expansion, compiler_callback=charge_normalization,
                check_callback=check_cpu)
        try:
            for neighbor in arity_neighbors(parent, request_type, grammar, max_size=max_size,
                    meter=self.meter, eta_exposure=self.eta_exposure,
                    arity_context=self.arity_context, production_priority=self.production_priority):
                yield neighbor.term, neighbor.path, neighbor.replacement, neighbor.metadata
        except NeighborhoodLimit as error:
            translated = {"expansion_budget": _ExpansionLimit,
                          "normalization_budget": _NormalizationLimit,
                          "cpu_budget": _CpuLimit}[error.reason]
            raise translated from error

    def snapshot(self):
        return {
            "schema_version": 1, "eta_exposure": self.eta_exposure,
            "arity_context": self.arity_context, "production_priority": self.production_priority,
            "structural_unit": "examined grammar choices/permutations/removals/eta views and context frontier pops",
            "compiler_unit": "reconstruction/shift/traversal AST and type visits plus compiler/query/sort invocations",
            "all_compiler_and_grammar_cpu_in_search_guard": True,
            "semantic_evaluator_calls": 0,
            **{name: getattr(self.meter, name, 0) for name in _COUNTERS},
        }


def solve_arity_population(examples, request_type, budget, grammar, *,
                           arity_context=False, production_priority=False,
                           eta_exposure=True, **kwargs):
    """Use the unchanged controller with independently registered edit factors."""
    started, wall = time.process_time(), time.perf_counter()
    if "edit_provider" in kwargs:
        raise ValueError("the arity adapter owns its edit provider")
    maximum_cpu = kwargs.get("max_cpu_seconds")
    if (maximum_cpu is not None and (type(maximum_cpu) not in (int, float)
            or not 0 <= maximum_cpu < float("inf"))):
        raise ValueError("max_cpu_seconds must be finite and nonnegative")
    provider = ArityEditProvider(arity_context=arity_context,
                                production_priority=production_priority,
                                eta_exposure=eta_exposure)
    setup_cpu = time.process_time() - started
    if maximum_cpu is not None:
        kwargs["max_cpu_seconds"] = max(0.0, maximum_cpu - setup_cpu)
    result = solve_population(examples, request_type, budget, grammar,
                              edit_provider=provider, **kwargs)
    result.edit_mode = "arity_coordinates"
    result.neighborhood_work = provider.snapshot()
    result.coordinate_setup_cpu_seconds = setup_cpu
    elapsed = time.process_time() - started
    exceeded = maximum_cpu is not None and elapsed >= maximum_cpu
    result.coordinate_adapter_deadline_exceeded = exceeded
    if exceeded:
        if result.term is not None:
            for trial in result.trials:
                if trial["public_match"]:
                    trial.update(public_match=False, incomplete=True,
                                 coordinate_adapter_deadline_exceeded=True)
            result.term, result.log_probability = None, None
        result.termination, result.exhausted = "cpu_budget", False
    result.cpu_seconds = time.process_time() - started
    result.wall_seconds = time.perf_counter() - wall
    return result


def arity_kernel_factory(*, arity_context=False, production_priority=False):
    def call(examples, request_type, budget, grammar, *, bank, heuristic, seed, limits):
        return solve_arity_population(examples, request_type, budget, grammar,
            accepted_seeds=bank, heuristic=heuristic, seed=seed, **limits,
            arity_context=arity_context, production_priority=production_priority)
    return call
