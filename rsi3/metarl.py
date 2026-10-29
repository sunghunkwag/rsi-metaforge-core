"""Meta-reinforcement learning of the search process, carried across tasks and generations.

What is learned. Inside each task's share of the wake budget, the system
spends chunks of candidates on ACTIONS:

- the prior pathway;
- the invented-concept pathway;
- each decomposition skeleton that the task's public examples fit.

The reward of a chunk is 1 if it produced a program the frozen verifier
accepted, and 0 otherwise. A policy chooses the next chunk's action from the
task's public SHAPE (the decomposition preconditions and its output type) and
from what the task has already cost it: how many chunks it has spent on this
action, and on all actions, without a solve.

Why this is meta-RL and not plain RL. The policy is fitted across all tasks.
It is not a per-task table, so what it learns from one task's reward applies
on its first chunk to a task it has never acted on. That includes VALIDATION
tasks, which it is never trained on. This is the meta-RL setting of the
owner's ``MetaRL-Agent-Framework`` (learn across a task distribution, adapt
fast on a new task) without gradients through a network. The within-task
adaptation is RL^2-style: the history features change the choice as a task's
chunks fail, and the across-task learning is the refit.

Continual. Every chunk episode is kept, and the policy is refit from scratch
each generation on the full replay. ``wipe=True`` refits on the current
generation only. That is the matched control of the owner's
``gated-self-improvement`` v3, where the identical learner with its memory
wiped between problems was the comparator that persistent process memory
beat (+1.52 tasks, p = 0.0011). The regulation study (D1) is why it is
replay, and not a parameter anchor.

Inputs are public only, and the labels are verifier receipts.
"""
from __future__ import annotations

import math

import numpy as np

from .decompose import (_bool_of_list, _constant_per_example, _elementwise_function,
                        _filter_consistent, _is_filter, _prepends_one, _same_length)

STEPS = 300
L2 = 1e-1


def shape_features(examples) -> np.ndarray:
    """Public shape of a task: decomposition preconditions and output type."""
    outputs = [out for _, out in examples]
    is_list = all(isinstance(o, (list, tuple)) for o in outputs)
    is_bool = all(type(o) is bool for o in outputs)
    is_int = all(type(o) is int for o in outputs)
    bool_list = is_list and any(o and type(o[0]) is bool for o in outputs)
    same = _same_length(examples)
    flags = [
        is_list and not bool_list, bool_list, is_int, is_bool,
        same, same and _elementwise_function(examples),
        _constant_per_example(examples) if same else False,
        _is_filter(examples), _is_filter(examples) and _filter_consistent(examples),
        _prepends_one(examples), _bool_of_list(examples),
    ]
    return np.asarray([1.0 if f else 0.0 for f in flags])


SHAPE_DIM = 11


def context(shape: np.ndarray, spent_action: int, spent_task: int) -> np.ndarray:
    return np.concatenate([[1.0], shape, [math.log1p(spent_action) / 3.0,
                                          math.log1p(spent_task) / 3.0]])


DIM = 1 + SHAPE_DIM + 2


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -60.0, 60.0)))


class MetaPolicy:
    """One logistic model per action identity, fitted on replayed chunk episodes."""

    def __init__(self, *, exploration: float = 0.3, wipe: bool = False):
        self.exploration = float(exploration)
        self.wipe = bool(wipe)
        self.episodes: list[tuple] = []        # (generation, action, context, reward)
        self.models: dict[str, tuple] = {}     # action -> (weights | None, prior)
        self.base_rate = 0.5
        self.last_fit: dict = {}

    # ---- learning --------------------------------------------------------
    def record(self, generation: int, action: str, x: np.ndarray, reward: int) -> None:
        self.episodes.append((generation, action, x, int(reward)))

    def fit(self, generation: int) -> dict:
        replay = [e for e in self.episodes if not self.wipe or e[0] == generation]
        by_action: dict[str, list] = {}
        for _, action, x, r in replay:
            by_action.setdefault(action, []).append((x, r))
        self.models = {}
        summary = {}
        rewards = sum(r for _, _, _, r in replay)
        # An action never tried starts at the overall reward rate, not at an
        # optimistic 0.5 (which made a newly available action take every chunk
        # of a generation); the exploration bonus is what gets it tried.
        self.base_rate = (rewards + 1.0) / (len(replay) + 2.0)
        for action, rows in sorted(by_action.items()):
            X = np.stack([x for x, _ in rows])
            y = np.asarray([r for _, r in rows], dtype=np.float64)
            n, positives = len(y), int(y.sum())
            prior = (positives + 1.0) / (n + 2.0)
            weights = None
            if 0 < positives < n:
                curvature = 0.25 * float(np.linalg.eigvalsh(X.T @ X / n).max())
                rate = 1.0 / (curvature + L2)
                w = np.zeros(DIM)
                for _ in range(STEPS):
                    w -= rate * (X.T @ (_sigmoid(X @ w) - y) / n + L2 * w)
                weights = w
            self.models[action] = (weights, prior)
            summary[action] = {"episodes": n, "rewards": positives}
        self.last_fit = {"replayed": len(replay), "actions": summary}
        return self.last_fit

    def probability(self, action: str, x: np.ndarray) -> float:
        weights, prior = self.models.get(action, (None, self.base_rate))
        if weights is None:
            return prior
        return float(_sigmoid(x @ weights))

    # ---- acting ----------------------------------------------------------
    def choose(self, actions: list[str], shape: np.ndarray, spent: dict, total: int) -> str:
        """Highest probability plus a within-task exploration bonus; ties by name."""
        log_term = math.log(1.0 + total)
        best, best_score = None, None
        for action in sorted(actions):
            x = context(shape, spent.get(action, 0), total)
            score = self.probability(action, x) + self.exploration * math.sqrt(
                log_term / (1.0 + spent.get(action, 0)))
            if best_score is None or score > best_score + 1e-12:
                best, best_score = action, score
        return best
