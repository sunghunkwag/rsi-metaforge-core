"""Binding integrator: binds new matches to remembered behaviour by observation.

A program that matches a task's public examples is an *explanation* of them;
different explanations can agree on the public examples and disagree
elsewhere. The integrator gives each public match a behavioural signature:
its outputs on deterministic probe inputs derived from the public inputs alone
(reverse a list, drop its first element, increment an int, negate a bool).
Hidden examples are never used.

Binding has two effects:

* Before verification. If a new match's signature equals the signature of a
  program the frozen verifier already rejected for that task, the match is
  bound to that rejected behaviour and is not submitted. The search continues
  in the same window. This keeps the one-query-per-task-per-generation cap
  from being spent on a behavioural duplicate of a known failure.
* After verification. A verified solution is bound with its provenance
  (pathway, kind, origin, generation, receipt) and its signature, so the record
  of which pathway produced which capability is explicit.

Probe evaluations are interpreter calls, not logical candidate evaluations;
they are counted separately and reported.
"""
from __future__ import annotations

import json

from rsi2.evaluator import evaluate


def _probe_value(value, mode: str):
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is list:
        return list(reversed(value)) if mode == "reverse" else value[1:]
    return value


def probe_inputs(examples) -> list[tuple]:
    probes, seen = [], set()
    for inputs, _ in examples:
        for mode in ("reverse", "drop"):
            probe = tuple(_probe_value(value, mode) for value in inputs)
            key = json.dumps(probe, sort_keys=True)
            if key not in seen:
                seen.add(key)
                probes.append(probe)
    return probes


class BindingIntegrator:
    def __init__(self, tasks, step_budget: int = 2000):
        self.probes = {task.name: probe_inputs(task.examples) for task in tasks}
        self.step_budget = int(step_budget)
        self.probe_evaluations = 0
        self.skipped_equivalent = 0
        self.bound_rejected = 0
        self.provenance: dict[str, dict] = {}

    def signature(self, task: str, term, library) -> str:
        outputs = []
        for probe in self.probes[task]:
            self.probe_evaluations += 1
            result = evaluate(term, probe, library=library, step_budget=self.step_budget)
            outputs.append(result.value if result.ok else "!error")
        return json.dumps(outputs, sort_keys=True, default=str)

    def skip_callback(self, task: str, library, memory):
        if not memory.rejected_signatures.get(task):
            return None

        def skip(term) -> bool:
            if memory.is_rejected_behaviour(task, self.signature(task, term, library)):
                self.skipped_equivalent += 1
                return True
            return False
        return skip

    def bind_rejected(self, task: str, term, library, receipt, memory) -> None:
        memory.reject_signature(task, self.signature(task, term, library), receipt)
        self.bound_rejected += 1

    def bind_verified(self, task: str, term, library, record) -> None:
        self.provenance[task] = {
            "pathway": record.pathway, "kind": record.kind, "origin": record.origin,
            "generation": record.generation, "receipt_id": record.receipt_id,
            "digest": record.digest, "signature": self.signature(task, term, library),
        }

    def stats(self) -> dict:
        return {"probe_evaluations": self.probe_evaluations,
                "skipped_equivalent": self.skipped_equivalent,
                "bound_rejected": self.bound_rejected}
