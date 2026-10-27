"""The frozen external verifier: the only RSI-3 module that reads hidden examples.

Every learning component in RSI-3 (memory, value model, controller, pathway
registry, integrator) improves from verdicts this module issues. The verifier
is therefore kept outside every improvement loop: it wraps RSI-2's frozen
``search.verify`` over each task's hidden examples, is constructed once per run,
and is never updated, tuned, or selected by any measured outcome.

Two structural rules make the verdicts usable as a learning signal:

* Receipts. A verdict is a ``Receipt`` recorded at issue time. Memory accepts a
  verified or rejected label only with an authentic receipt for the same task
  and the same program digest, so no pathway can grade its own output.
* Query rate. At most one verification query per task per generation, equal to
  the rate of RSI-2's wake phase. This bounds how much hidden-example
  information can flow back into search.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from rsi2.corpus import Task
from rsi2.search import verify as _frozen_verify
from rsi2.terms import term_to_dict


def term_digest(term) -> str:
    """Stable content digest of a program AST."""
    payload = json.dumps(term_to_dict(term), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def public_view(task: Task) -> Task:
    """Return a search-safe copy of a task with its hidden examples removed."""
    return Task(task.name, task.request_type, task.examples, ())


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
    """Hidden-example verification with authenticated receipts and a query cap."""

    QUERIES_PER_TASK_PER_GENERATION = 1

    def __init__(self, tasks, step_budget: int = 2000):
        self._hidden = {task.name: tuple(task.hidden) for task in tasks}
        if any(not hidden for hidden in self._hidden.values()):
            raise ValueError("every verified task needs hidden examples")
        self._step_budget = int(step_budget)
        self._issued: dict[int, Receipt] = {}
        self._queries: dict[tuple[str, int], int] = {}

    def verify(self, task_name: str, term, library, generation: int) -> Receipt:
        if task_name not in self._hidden:
            raise KeyError(f"unknown task {task_name!r}")
        key = (task_name, int(generation))
        if self._queries.get(key, 0) >= self.QUERIES_PER_TASK_PER_GENERATION:
            raise QueryLimitExceeded(f"{task_name!r} already verified in generation {generation}")
        self._queries[key] = self._queries.get(key, 0) + 1
        verdict = bool(_frozen_verify(term, self._hidden[task_name], library=library,
                                      step_budget=self._step_budget))
        receipt = Receipt(len(self._issued) + 1, task_name, int(generation),
                          term_digest(term), verdict)
        self._issued[receipt.receipt_id] = receipt
        return receipt

    def is_authentic(self, receipt) -> bool:
        return (isinstance(receipt, Receipt)
                and self._issued.get(receipt.receipt_id) == receipt)

    @property
    def queries(self) -> int:
        return sum(self._queries.values())
