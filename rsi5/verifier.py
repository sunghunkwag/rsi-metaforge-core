"""The frozen verifier: the only RSI-5 module outside ``judge/`` that reads hidden examples.

A fork of ``rsi3/verifier.py``'s ``FrozenVerifier`` that checks with RSI-5's reference
interpreter (``dsl/evaluator.py``), because RSI-2's evaluator does not know the restored
vocabulary. Like J's verifier it checks every public *and* hidden example. It is
constructed once per run, never tuned or selected by any measured outcome, and issues
one receipt per task per generation.

* Receipts: every verdict is a ``Receipt`` recorded at issue time; a label is authentic
  only with a receipt for the same task and program digest.
* Query rate: at most one verification per task per generation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .dsl.evaluator import DEFAULT_STEP_BUDGET, evaluate
from .dsl.terms import term_to_dict


def term_digest(term) -> str:
    payload = json.dumps(term_to_dict(term), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class Receipt:
    receipt_id: int
    task: str
    generation: int
    digest: str
    verdict: bool


class QueryLimitExceeded(RuntimeError):
    """Raised when a task is verified more than once in one generation."""


class FrozenVerifier:
    QUERIES_PER_TASK_PER_GENERATION = 1

    def __init__(self, tasks, step_budget: int = DEFAULT_STEP_BUDGET):
        self._examples = {task.name: tuple(task.examples) + tuple(task.hidden) for task in tasks}
        if any(len(task.hidden) == 0 for task in tasks):
            raise ValueError("every verified task needs hidden examples")
        self._step_budget = int(step_budget)
        self._issued: dict[int, Receipt] = {}
        self._queries: dict[tuple[str, int], int] = {}

    def verify(self, task_name: str, term, generation: int = 0) -> Receipt:
        if task_name not in self._examples:
            raise KeyError(f"unknown task {task_name!r}")
        key = (task_name, int(generation))
        if self._queries.get(key, 0) >= self.QUERIES_PER_TASK_PER_GENERATION:
            raise QueryLimitExceeded(f"{task_name!r} already verified in generation {generation}")
        self._queries[key] = self._queries.get(key, 0) + 1
        verdict = term is not None
        if verdict:
            for inputs, expected in self._examples[task_name]:
                result = evaluate(term, tuple(inputs), step_budget=self._step_budget)
                if not result.ok or result.value != expected:
                    verdict = False
                    break
        receipt = Receipt(len(self._issued) + 1, task_name, int(generation),
                          term_digest(term) if term is not None else "", bool(verdict))
        self._issued[receipt.receipt_id] = receipt
        return receipt

    def is_authentic(self, receipt) -> bool:
        return isinstance(receipt, Receipt) and self._issued.get(receipt.receipt_id) == receipt

    @property
    def queries(self) -> int:
        return sum(self._queries.values())
