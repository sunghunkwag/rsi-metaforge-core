"""Separate per-task evaluation reuse; the running study's memory is unchanged.

This procedure caches supplied development tasks with the original exact scope.
It changes evaluation work, never search, scoring, model labels, or admission.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import time

from .memory import assess, scope


_WORK_FIELDS = ("evaluation_steps", "heuristic_calls", "heuristic_evaluations",
                "heuristic_steps", "verification_examples", "verification_steps")


def _key(value):
    """Preserve host value types which plain JSON erases in evaluator inputs.

    In particular, list/tuple arguments and expected outputs can produce
    different search/verification outcomes. Mapping insertion order is already
    represented by scope's ordered sequences where it affects execution.
    """
    def typed(item):
        kind = type(item)
        if item is None:
            return ["none"]
        if kind is bool:
            return ["bool", item]
        if kind is int:
            return ["int", item]
        if kind is float:
            return ["float", item.hex()]
        if kind is str:
            return ["str", item]
        if kind in (list, tuple):
            return ["list" if kind is list else "tuple", [typed(child) for child in item]]
        if kind is dict:
            pairs = [[typed(key), typed(child)] for key, child in item.items()]
            pairs.sort(key=lambda pair: json.dumps(pair[0], separators=(",", ":")))
            return ["dict", pairs]
        raise TypeError(f"unsupported scope value type: {kind.__name__}")

    return json.dumps(typed(value), separators=(",", ":"))


def _keys(task_scope):
    without_budget = {name: value for name, value in task_scope.items() if name != "budget"}
    return _key(task_scope), _key(without_budget)


def _certified(report):
    """Abstain unless a completed failed search demonstrably avoided Limit.

    Proof: in frozen solve, candidate budget occurs only in attempt's Limit
    guard. A public-no-match result with c < B did not trigger that guard. Raising
    B leaves every preceding transition/evaluation unchanged, so the same
    iterator terminates with the same c and no selected term. Termination may
    be finite-space exhaustion OR the scoped expansion cap; no distinction is
    required. Changed state, limits, I/O or queue order invalidate the key.

    Counterevidence: c == B may stop before a later solution, and a public match
    can be selected on Limit and fail hidden verification. Neither is evidence
    for cross-budget reuse, even if its final task result says solved=False.
    """
    if report.get("tasks") != 1 or len(report.get("records", ())) != 1:
        return False
    record = report["records"][0]
    budget, count = report.get("budget"), record.get("candidates")
    return (type(budget) is int and type(count) is int and 0 <= count < budget
            and record.get("public_matched") is False
            and record.get("exhausted") is True and record.get("solved") is False
            and report.get("candidate_evaluations") == count)


@dataclass(frozen=True)
class _Entry:
    report: dict
    source_budget: int


class SharedStore:
    """Own independent copies of completed single-task measurement evidence.

    Stores may be shared by sequential counterfactual arms in one process.
    Counters belong to each memory client; this store never charges work twice.
    Internal reports are copied on insertion and lookup, so returned artifacts
    cannot change later cache evidence or its certificate.
    """

    def __init__(self):
        self._entries = {}
        self._certificates = {}

    def _lookup(self, task_scope):
        exact_key, certificate_key = _keys(task_scope)
        entry = self._entries.get(exact_key)
        if entry is not None:
            return copy.deepcopy(entry.report), entry.source_budget, "exact"
        budget = task_scope["budget"]
        if type(budget) is int:
            for source_budget, source_key in sorted(self._certificates.get(certificate_key, {}).items()):
                if source_budget < budget:
                    entry = self._entries[source_key]
                    return (copy.deepcopy(entry.report), entry.source_budget,
                            "early_termination_certificate")
        return None

    def _remember(self, task_scope, report):
        # This is reached only after assess returns normally. An interrupted
        # operation never creates an entry or a reusable completion certificate.
        exact_key, certificate_key = _keys(task_scope)
        if (report.get("tasks") != 1 or len(report.get("records", ())) != 1
                or report.get("budget") != task_scope["budget"]):
            raise ValueError("store requires a completed single-task assessment at its scoped budget")
        entry = _Entry(copy.deepcopy(report), task_scope["budget"])
        self._entries[exact_key] = entry
        if _certified(report):
            self._certificates.setdefault(certificate_key, {})[entry.source_budget] = exact_key

    def summary(self):
        return {"entries": len(self._entries),
                "certificates": sum(len(items) for items in self._certificates.values())}


class EfficientEvaluationMemory:
    """Recombine per-task exact evidence with separately charged actual work."""

    def __init__(self, store=None):
        self.store = SharedStore() if store is None else store
        if not isinstance(self.store, SharedStore):
            raise TypeError("store must be a SharedStore")
        self.actual_candidate_evaluations = 0
        self.cache_hits = 0
        self.assessment_calls = 0
        self.task_cache_hits = 0
        self.exact_hits = 0
        self.certificate_hits = 0
        self.task_assessment_calls = 0
        for metric in _WORK_FIELDS:
            setattr(self, f"actual_{metric}", 0)

    def measure(self, state, tasks, heuristic, budget, searchconfig):
        started = time.perf_counter()
        self.assessment_calls += 1
        records = []
        actual = 0
        actual_work = dict.fromkeys(_WORK_FIELDS, 0)
        for task in tasks:
            task_started = time.perf_counter()
            task_scope = scope(state, [task], heuristic, budget, searchconfig)
            cached = self.store._lookup(task_scope)
            if cached is None:
                source = assess([task], state.grammar, heuristic, budget, searchconfig,
                                conditioner=state.condition)
                self.store._remember(task_scope, source)
                source_budget, reuse_kind = budget, "evaluated"
                self.task_assessment_calls += 1
                task_actual = source["candidate_evaluations"]
                self.actual_candidate_evaluations += task_actual
                actual += task_actual
            else:
                source, source_budget, reuse_kind = cached
                self.task_cache_hits += 1
                if reuse_kind == "exact":
                    self.exact_hits += 1
                else:
                    self.certificate_hits += 1
                task_actual = 0
            record = copy.deepcopy(source["records"][0])
            source_wall = record["wall_seconds"]
            wall = time.perf_counter() - task_started
            record.update({"cache_hit": cached is not None, "source_budget": source_budget,
                           "requested_budget": budget, "reuse_kind": reuse_kind,
                           "actual_candidate_evaluations": task_actual,
                           "source_wall_seconds": source_wall, "wall_seconds": wall,
                           "actual_wall_seconds": wall})
            for metric in _WORK_FIELDS:
                value = record[metric] if cached is None else 0
                record[f"actual_{metric}"] = value
                actual_work[metric] += value
                setattr(self, f"actual_{metric}", getattr(self, f"actual_{metric}") + value)
            records.append(record)
        solved = [record for record in records if record["solved"]]
        hit = bool(records) and all(record["cache_hit"] for record in records)
        self.cache_hits += hit
        wall = time.perf_counter() - started
        return {"tasks": len(records), "solved": len(solved),
                "solved_fraction": len(solved) / len(records) if records else 0.0,
                "mean_candidates_to_solution": (sum(r["candidates"] for r in solved) / len(solved)
                                                 if solved else None),
                "candidate_evaluations": sum(r["candidates"] for r in records),
                "budget": budget, "wall_seconds": wall, "actual_wall_seconds": wall,
                "records": records, "cache_hit": hit,
                "actual_candidate_evaluations": actual,
                **{f"actual_{name}": value for name, value in actual_work.items()}}

    def summary(self):
        return {**self.store.summary(), "cache_hits": self.cache_hits,
                "assessment_calls": self.assessment_calls,
                "task_cache_hits": self.task_cache_hits, "exact_hits": self.exact_hits,
                "certificate_hits": self.certificate_hits,
                "task_assessment_calls": self.task_assessment_calls,
                "actual_candidate_evaluations": self.actual_candidate_evaluations,
                **{f"actual_{name}": getattr(self, f"actual_{name}") for name in _WORK_FIELDS}}
