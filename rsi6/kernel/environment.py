"""The kernel's side of one external benchmark.

An environment turns published instance files into the learner's generic problem form and
scores answers against the external reference. The learner never receives an ``Environment``:
it receives the problem objects ``problem()`` returns, which carry no name and no reference.
The reference values are read by ``score`` only, after an answer has been produced.

An adapter may do four things: parse the published files, state the form of an answer, expose
the instance as plain arrays, and evaluate. It must not search, rank or hint.
"""
from __future__ import annotations

import hashlib
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")


class Environment:
    name = ""                 # kernel only
    category = ""             # kernel only
    form = "assign"           # "assign" or "predict"
    threshold = 0.9           # score on fresh instances at which the capability counts as held
    anchor = ""               # where the threshold comes from (an external fact)

    def instance_ids(self) -> list:
        """Usable instances, in a fixed order."""
        raise NotImplementedError

    def problem(self, instance_id: str, meter, seed: int, training: bool):
        """``(problem, decode)``. ``seed`` relabels the instance's entities; ``decode`` maps an
        answer given in the relabelled problem back to the instance's own labels."""
        raise NotImplementedError

    def score(self, instance_id: str, answer) -> float:
        """Score in [0, 1] of an answer in the instance's own labels, against the external
        reference. An invalid answer scores 0."""
        raise NotImplementedError

    def reference(self, instance_id: str):
        """The external reference value of an instance (for reports and audits)."""
        raise NotImplementedError


def split(ids, key: str, n_train: int, n_fresh: int):
    """A fixed, seeded split of an environment's instances into training and fresh ones.
    The split depends on the environment's name only, so every version and every seed is
    scored on the same fresh instances, and no fresh instance is ever a training instance."""
    order = sorted(ids, key=lambda i: hashlib.sha256(f"{key}|{i}".encode()).hexdigest())
    n_train = min(n_train, len(order) // 2)
    n_fresh = min(n_fresh, len(order) - n_train)
    return order[:n_train], order[n_train:n_train + n_fresh]


def relabel(rng, n: int):
    """A random relabelling of ``n`` entities: ``perm[new] = old`` and its inverse."""
    perm = rng.permutation(n)
    inverse = np.empty(n, dtype=np.int64)
    inverse[perm] = np.arange(n)
    return perm, inverse


def data_path(*parts) -> str:
    return os.path.join(DATA, *parts)
