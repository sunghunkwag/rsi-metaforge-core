"""Memory-feedback value model: P(verified solve in the next window | public context).

A logistic regression refit *from scratch* every generation on episodes
replayed from memory. There is deliberately no parameter anchor, no
consolidation gate, and no rollback on the model itself. The regulation study
(``studies/regulation_toy.py``, REGULATION_TOY_RESULTS.md) measured the
alternatives on a continual-learning problem: pulling parameters toward a
fixed or gated reference destroyed both the old and the new capability while
experience kept arriving, and experience replay alone retained beneficial
changes and repaired harmful ones. The ``latest`` mode (fit on the most recent
generation only) is the matching ablation.

Inputs are public only: RSI-2's 32 task features of the public examples
(standardized over TRAIN), the pathway kind, the similarity of an analog
pathway's source task, the depth already searched, and the window size.
Labels are verifier receipts relayed through memory.
"""
from __future__ import annotations

import math

import numpy as np

from .pathways import KINDS

STEPS = 300
L2 = 1e-2
EXTRA = ("similarity", "log_depth", "log_window")
DIM = 32 + len(KINDS) + len(EXTRA)


def slot_features(task_features, kind: str, similarity: float, start: int, window: int):
    onehot = [1.0 if kind == k else 0.0 for k in KINDS]
    extra = [float(similarity), math.log1p(start) / 8.0, math.log1p(window) / 8.0]
    vector = np.concatenate([np.asarray(task_features, dtype=np.float64), onehot, extra])
    if vector.shape != (DIM,):
        raise ValueError("slot feature width mismatch")
    return vector


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))


class ValueModel:
    def __init__(self):
        self.weights = None
        self.mean = np.zeros(DIM)
        self.scale = np.ones(DIM)
        self.prior = 0.5
        self.last_fit: dict = {"examples": 0, "positives": 0, "fitted": False}

    def fit(self, features, labels) -> dict:
        X = np.asarray(features, dtype=np.float64).reshape(-1, DIM)
        y = np.asarray(labels, dtype=np.float64)
        n, positives = len(y), int(y.sum())
        self.prior = (positives + 1.0) / (n + 2.0)
        self.weights = None
        self.last_fit = {"examples": n, "positives": positives, "fitted": False,
                         "prior": self.prior}
        if n == 0 or positives in (0, n):
            return self.last_fit
        self.mean = X.mean(axis=0)
        self.scale = X.std(axis=0)
        self.scale[self.scale < 1e-8] = 1.0
        design = self._design(X)
        # Fixed step from the logistic loss's Lipschitz bound; no tuned rate.
        curvature = 0.25 * float(np.linalg.eigvalsh(design.T @ design / n).max())
        rate = 1.0 / (curvature + L2)
        w = np.zeros(design.shape[1])
        for _ in range(STEPS):
            p = _sigmoid(design @ w)
            w -= rate * (design.T @ (p - y) / n + L2 * w)
        self.weights = w
        p = _sigmoid(design @ w)
        loss = float(-np.mean(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)))
        self.last_fit.update({"fitted": True, "log_loss": loss})
        return self.last_fit

    def _design(self, X):
        scaled = np.clip((X - self.mean) / self.scale, -10.0, 10.0)
        return np.concatenate([scaled, np.ones((len(scaled), 1))], axis=1)

    def predict(self, features):
        X = np.asarray(features, dtype=np.float64).reshape(-1, DIM)
        if self.weights is None:
            return np.full(len(X), self.prior)
        return _sigmoid(self._design(X) @ self.weights)
