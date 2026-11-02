"""The mapper: a linear alignment of the Breaker's task space and the Builder's program space.

The SwaT analogue (OWNER_DIRECTIVE.md §3): the two agents keep different
codebooks, so a task signature and the program that crossed it are vectors
in unrelated bases. The mapper is kernel ridge regression over the paired
events ``(task signature, crossing program vector)``: with ``X`` the task
vectors and ``Y`` the program vectors of the ``n`` pairs, the task->program
map is ``q -> q Xᵀ (X Xᵀ + λI)⁻¹ Y`` and the program->task map is its
mirror. It is refit from scratch on the full set of pairs at every
consolidation (RSI-3's D1: replay, not anchoring) and accepts only
paired events: ``fit_from_events`` drops any event without both vectors
(``tests/test_latent.py``). ``residual`` is the mean relative training
residual, reported as a field statistic.
"""
from __future__ import annotations

import numpy as np


class Mapper:
    def __init__(self, ridge: float = 1.0):
        self.ridge = float(ridge)
        self.pairs = 0
        self._x = None
        self._y = None
        self._k_inverse = None
        self._k_inverse_y = None
        self.residual = None

    def fit(self, pairs) -> dict:
        """Refit from scratch on paired (task vector, program vector) events."""
        pairs = [(np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)) for a, b in pairs]
        self.pairs = len(pairs)
        if not pairs:
            self._x = self._y = self._k_inverse = self._k_inverse_y = None
            self.residual = None
            return {"pairs": 0, "residual": None}
        self._x = np.stack([a for a, _ in pairs])
        self._y = np.stack([b for _, b in pairs])
        d = self._x.shape[1]
        gram_x = self._x @ self._x.T / d
        gram_y = self._y @ self._y.T / d
        self._k_inverse = np.linalg.inv(gram_x + self.ridge * np.eye(self.pairs))
        self._k_inverse_y = np.linalg.inv(gram_y + self.ridge * np.eye(self.pairs))
        predicted = np.stack([self.task_to_program(a) for a in self._x])
        # Rounded before it is ledgered: the value is a BLAS float and
        # byte-identity of the ledger must not hang on its last digits.
        self.residual = round(float(np.mean(np.linalg.norm(predicted - self._y, axis=1)
                                            / np.maximum(np.linalg.norm(self._y, axis=1), 1e-9))), 6)
        return {"pairs": self.pairs, "residual": self.residual}

    def fit_from_events(self, events) -> dict:
        """Events are dicts; only those with both ``task`` and ``program`` vectors are pairs."""
        pairs = [(e["task"], e["program"]) for e in events
                 if e.get("task") is not None and e.get("program") is not None]
        return self.fit(pairs)

    def task_to_program(self, query: np.ndarray) -> np.ndarray:
        if self._x is None:
            return np.asarray(query, dtype=np.float64)
        weights = self._k_inverse @ (self._x @ np.asarray(query, dtype=np.float64) / self._x.shape[1])
        return weights @ self._y

    def program_to_task(self, query: np.ndarray) -> np.ndarray:
        if self._y is None:
            return np.asarray(query, dtype=np.float64)
        weights = self._k_inverse_y @ (self._y @ np.asarray(query, dtype=np.float64) / self._y.shape[1])
        return weights @ self._x

    @staticmethod
    def sign(vector: np.ndarray) -> np.ndarray:
        return np.where(np.asarray(vector) >= 0, 1, -1).astype(np.int8)
