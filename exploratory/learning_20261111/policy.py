"""The learned search policy: a small network whose weights change as the system works.

A two-hidden-layer perceptron (NumPy; no attention, no transformer) maps the features of a
task's public examples to one logit per vocabulary item: how likely the item is to occur in a
program that solves the task. The search uses the logits to choose the vocabulary it tries
first. The network is trained on (features, items of a verified program) pairs: programs the
system verified on real tasks, and programs it ran on its own inputs (dreams), for which the
answer is known by construction.

Weights are updated online: ``Policy.learn`` takes a few Adam steps on a batch drawn from a
replay buffer whenever new experience arrives. The output layer grows when the vocabulary
does (a new learned symbol gets a new unit; nothing else moves). A policy is a plain
dictionary of arrays, so a snapshot can be stored, compared and rolled back.
"""
from __future__ import annotations

import numpy as np

HIDDEN = 128


class Policy:
    def __init__(self, size: int, items, seed: int = 0, hidden: int = HIDDEN):
        rng = np.random.default_rng(seed)
        self.items = list(items)
        self.index = {name: i for i, name in enumerate(self.items)}
        scale = lambda fan: np.sqrt(2.0 / fan)
        self.w = {"w1": (rng.standard_normal((size, hidden)) * scale(size)).astype(np.float32),
                  "b1": np.zeros(hidden, np.float32),
                  "w2": (rng.standard_normal((hidden, hidden)) * scale(hidden)).astype(np.float32),
                  "b2": np.zeros(hidden, np.float32),
                  "w3": (rng.standard_normal((hidden, len(self.items))) * 0.01).astype(np.float32),
                  "b3": np.zeros(len(self.items), np.float32)}
        self.m = {k: np.zeros_like(v) for k, v in self.w.items()}
        self.v = {k: np.zeros_like(v) for k, v in self.w.items()}
        self.steps = 0
        self.seed = seed

    # -- inference --
    def logits(self, x: np.ndarray) -> np.ndarray:
        h1 = np.maximum(x @ self.w["w1"] + self.w["b1"], 0.0)
        h2 = np.maximum(h1 @ self.w["w2"] + self.w["b2"], 0.0)
        return h2 @ self.w["w3"] + self.w["b3"]

    def probabilities(self, x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-self.logits(x)))

    def ranked(self, x: np.ndarray) -> list:
        """Vocabulary items, most likely first."""
        order = np.argsort(-self.logits(x), kind="stable")
        return [self.items[i] for i in order]

    # -- learning --
    def grow(self, name: str) -> None:
        """A new vocabulary item: one more output unit, at the prior of a rare item."""
        if name in self.index:
            return
        self.index[name] = len(self.items)
        self.items.append(name)
        for key, fill in (("w3", 0.0), ("b3", -2.0)):
            for store in (self.w, self.m, self.v):
                old = store[key]
                column = np.full((old.shape[0], 1) if old.ndim == 2 else (1,), fill if store is self.w else 0.0,
                                 np.float32)
                store[key] = np.concatenate([old, column], axis=-1)

    def target(self, names) -> np.ndarray:
        y = np.zeros(len(self.items), np.float32)
        for name in names:
            if name in self.index:
                y[self.index[name]] = 1.0
        return y

    def step(self, x: np.ndarray, y: np.ndarray, rate: float = 1e-3, weight=None) -> float:
        """One Adam step on a batch (binary cross-entropy). Returns the loss before the step.
        ``y`` may have fewer columns than the policy has items (targets made before a growth)."""
        if y.shape[1] < len(self.items):
            y = np.concatenate([y, np.zeros((y.shape[0], len(self.items) - y.shape[1]), np.float32)], axis=1)
        h1 = np.maximum(x @ self.w["w1"] + self.w["b1"], 0.0)
        h2 = np.maximum(h1 @ self.w["w2"] + self.w["b2"], 0.0)
        z = h2 @ self.w["w3"] + self.w["b3"]
        p = 1.0 / (1.0 + np.exp(-z))
        eps = 1e-7
        loss = -(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps))
        d3 = (p - y) / len(x)
        if weight is not None:
            d3 = d3 * weight[:, None]
            loss = loss * weight[:, None]
        grads = {"w3": h2.T @ d3, "b3": d3.sum(axis=0)}
        d2 = (d3 @ self.w["w3"].T) * (h2 > 0)
        grads["w2"], grads["b2"] = h1.T @ d2, d2.sum(axis=0)
        d1 = (d2 @ self.w["w2"].T) * (h1 > 0)
        grads["w1"], grads["b1"] = x.T @ d1, d1.sum(axis=0)
        self.steps += 1
        b1, b2 = 0.9, 0.999
        for key, g in grads.items():
            self.m[key] = b1 * self.m[key] + (1 - b1) * g
            self.v[key] = b2 * self.v[key] + (1 - b2) * g * g
            mhat = self.m[key] / (1 - b1 ** self.steps)
            vhat = self.v[key] / (1 - b2 ** self.steps)
            self.w[key] = (self.w[key] - rate * mhat / (np.sqrt(vhat) + 1e-8)).astype(np.float32)
        return float(loss.sum(axis=1).mean())

    # -- snapshots --
    def snapshot(self) -> dict:
        return {"items": list(self.items), "seed": self.seed, "steps": self.steps,
                "w": {k: v.copy() for k, v in self.w.items()}}

    @classmethod
    def restore(cls, shot: dict) -> "Policy":
        policy = cls(shot["w"]["w1"].shape[0], shot["items"], shot.get("seed", 0), shot["w"]["w1"].shape[1])
        policy.w = {k: np.asarray(v, np.float32).copy() for k, v in shot["w"].items()}
        policy.m = {k: np.zeros_like(v) for k, v in policy.w.items()}
        policy.v = {k: np.zeros_like(v) for k, v in policy.w.items()}
        policy.steps = 0
        return policy

    def to_json(self) -> dict:
        return {"items": list(self.items), "seed": self.seed, "steps": self.steps,
                "w": {k: v.tolist() for k, v in self.w.items()}}

    @classmethod
    def from_json(cls, data: dict) -> "Policy":
        return cls.restore({"items": data["items"], "seed": data.get("seed", 0),
                            "w": {k: np.asarray(v, np.float32) for k, v in data["w"].items()}})


class Replay:
    """Experience for the policy: (features, item names) pairs with a tag that says where the
    pair came from. A fixed capacity; the oldest pair of the largest tag goes first, so a new
    domain cannot push an old one out entirely."""

    def __init__(self, capacity: int = 200_000, seed: int = 0):
        self.capacity, self.rng = capacity, np.random.default_rng(seed)
        self.by_tag: dict = {}

    def add(self, features: np.ndarray, names, tag: str = "dream") -> None:
        self.by_tag.setdefault(tag, []).append((features, tuple(names)))
        total = sum(len(v) for v in self.by_tag.values())
        if total > self.capacity:
            largest = max(self.by_tag, key=lambda t: len(self.by_tag[t]))
            self.by_tag[largest].pop(0)

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_tag.values())

    def batch(self, policy: Policy, size: int = 256, mix: dict | None = None):
        """A batch drawn evenly over tags (or by ``mix``: tag -> share)."""
        tags = [t for t in self.by_tag if self.by_tag[t]]
        shares = np.asarray([(mix or {}).get(t, 1.0) for t in tags], float)
        shares = shares / shares.sum()
        xs, ys = [], []
        for tag in self.rng.choice(len(tags), size=size, p=shares):
            rows = self.by_tag[tags[tag]]
            features, names = rows[int(self.rng.integers(len(rows)))]
            xs.append(features)
            ys.append(policy.target(names))
        return np.stack(xs), np.stack(ys)


def learn(policy: Policy, replay: Replay, steps: int, size: int = 256, rate: float = 1e-3, mix=None) -> float:
    """``steps`` online updates from the replay buffer. Returns the mean loss."""
    losses = []
    for _ in range(steps):
        x, y = replay.batch(policy, size, mix)
        losses.append(policy.step(x, y, rate))
    return float(np.mean(losses)) if losses else 0.0
