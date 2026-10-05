"""Reserve causal descendant search within every complete-candidate budget.

The diagnosed B16 screen exhausted its entire allowance on initial roots,
before a scorer could select a parent. This adapter limits the combined bank
and enumeration root prefix. It does not change population edits, evaluation,
scorers, primitive productions, or acceptance. Root selection treats prior
verification record IDs as opaque ordering keys. The allocation policy
receives neither public examples nor Task objects.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from .population_search import solve_population
from .repair_search import RepairSeed


POLICY_NAME = "combined_roots_half_budget_bank_quarter_v1"


@dataclass(frozen=True)
class RootAllocation:
    budget: int
    maximum_roots: int
    maximum_bank_roots: int
    selected_bank: tuple[RepairSeed, ...]
    fresh_prefix: int
    supplied_bank_records: int

    @property
    def planned_roots(self):
        return len(self.selected_bank) + self.fresh_prefix

    @property
    def reserved_descendant_slots(self):
        return self.budget - self.planned_roots

    def to_record(self):
        return {
            "name": POLICY_NAME,
            "budget": self.budget,
            "maximum_roots": self.maximum_roots,
            "maximum_bank_roots": self.maximum_bank_roots,
            "selected_bank_records": [r.training_record for r in self.selected_bank],
            "supplied_bank_records": self.supplied_bank_records,
            "fresh_prefix": self.fresh_prefix,
            "planned_roots": self.planned_roots,
            "reserved_descendant_slots": self.reserved_descendant_slots,
            "bank_fairness": "fixed proof-ID prefix; later IDs may remain unselected across generations",
            "scope": "candidate slots reserved; early success or other caps may stop before edits",
        }


def allocate_roots(budget, accepted_seeds=(), *, seed_prefix=16):
    """Use at most floor(B/2) roots and floor(B/4) bank roots.

    A nonzero budget retains at least one fresh enumerator draw. Budgets zero
    and one cannot contain both a root and a descendant and are explicit edge
    cases. The bank is a deterministic prefix sorted by existing proof ID;
    its size or order cannot consume the reserved descendant slots.
    This bounded prefix does not ensure bank fairness across generations.
    """
    if type(budget) is not int or budget < 0:
        raise ValueError("budget must be a nonnegative integer")
    if type(seed_prefix) is not int or seed_prefix < 1:
        raise ValueError("seed_prefix must be a positive integer")
    bank = tuple(accepted_seeds)
    if any(not isinstance(record, RepairSeed) for record in bank):
        raise TypeError("accepted_seeds must contain RepairSeed TRAIN records")
    if any(not isinstance(record.training_record, str) for record in bank):
        raise TypeError("bank verification record IDs must be strings")
    if len({record.training_record for record in bank}) != len(bank):
        raise ValueError("bank verification record IDs must be unique")
    maximum_roots = max(1, budget // 2) if budget else 0
    maximum_bank_roots = min(budget // 4, max(0, maximum_roots - 1))
    selected = tuple(sorted(bank, key=lambda r: r.training_record)[:maximum_bank_roots])
    fresh = min(seed_prefix, maximum_roots - len(selected))
    return RootAllocation(budget, maximum_roots, maximum_bank_roots,
                          selected, fresh, len(bank))


def solve_reserved_population(examples, request_type, budget, grammar, *,
                              accepted_seeds=(), seed_prefix=16, **limits):
    """Apply the same allocation for every scorer, arm, and task budget."""
    started, wall_started = time.process_time(), time.perf_counter()
    maximum_cpu = limits.get("max_cpu_seconds")
    if (maximum_cpu is not None and
            (type(maximum_cpu) not in (int, float) or
             not 0 <= maximum_cpu < float("inf"))):
        raise ValueError("max_cpu_seconds must be finite and nonnegative")
    allocation = allocate_roots(budget, accepted_seeds, seed_prefix=seed_prefix)
    policy_cpu = time.process_time() - started
    if maximum_cpu is not None:
        limits["max_cpu_seconds"] = max(0.0, maximum_cpu - policy_cpu)
    result = solve_population(examples, request_type, budget, grammar,
                              accepted_seeds=allocation.selected_bank,
                              seed_prefix=allocation.fresh_prefix, **limits)
    result.root_allocation = allocation.to_record()
    result.root_policy_cpu_seconds = policy_cpu
    elapsed = time.process_time() - started
    deadline_exceeded = maximum_cpu is not None and elapsed >= maximum_cpu
    result.root_policy_deadline_exceeded = deadline_exceeded
    if deadline_exceeded:
        # The scorer-visible solution cannot be admitted after the complete
        # adapter call's deadline. Preserve all interpreter/structural charges
        # and outputs while marking a late public match as incomplete.
        if result.term is not None:
            for trial in result.trials:
                if trial["public_match"]:
                    trial.update(public_match=False, incomplete=True,
                                 root_policy_deadline_exceeded=True)
            result.term, result.log_probability = None, None
        result.termination, result.exhausted = "cpu_budget", False
    # The underlying kernel's timer starts after bank allocation. Report the
    # complete adapter call rather than dropping selection/telemetry CPU.
    result.cpu_seconds = time.process_time() - started
    result.wall_seconds = time.perf_counter() - wall_started
    return result
