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
    threshold = 0.9           # mean score on fresh instances at which the capability counts as held
    anchor = ""               # what the threshold is, said plainly; most are operating points, not external facts

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

    def threshold_for(self, instance_ids) -> float:
        """The threshold for the mean score over exactly these instances."""
        return self.threshold

    def group(self, instance_id: str) -> str:
        """The published group an instance belongs to (its family, generator class or size
        class). Training and fresh instances are taken from different groups."""
        return ""


def _order(items, key: str) -> list:
    return sorted(items, key=lambda i: hashlib.sha256(f"{key}|{i}".encode()).hexdigest())


def split(env, n_train: int, n_fresh: int):
    """A fixed, seeded split of an environment's instances into training and fresh ones.

    It depends on the environment only, so every version and every seed is scored on the same
    fresh instances, and no fresh instance is ever a training instance. When the benchmark's
    instances come in published groups, whole groups go to one side: the fresh instances are
    then not siblings of the training ones. Groups are taken for the fresh side, in a seeded
    order, until it holds ``n_fresh`` instances or half of all instances; the training side is
    drawn from the rest."""
    ids = list(env.instance_ids())
    groups = {}
    for i in ids:
        groups.setdefault(env.group(i), []).append(i)
    if len(groups) < 2:
        order = _order(ids, env.name)
        n_train = min(n_train, len(order) // 2)
        return order[:n_train], order[n_train:n_train + min(n_fresh, len(order) - n_train)]
    names = _order(groups, env.name + "|groups")
    fresh, k = [], 0
    while k < len(names) - 1 and len(fresh) < n_fresh and 2 * len(fresh) < len(ids):
        fresh += groups[names[k]]
        k += 1
    train = [i for name in names[k:] for i in groups[name]]
    return _order(train, env.name)[:n_train], _order(fresh, env.name)[:n_fresh]


def relabel(rng, n: int):
    """A random relabelling of ``n`` entities: ``perm[new] = old`` and its inverse."""
    perm = rng.permutation(n)
    inverse = np.empty(n, dtype=np.int64)
    inverse[perm] = np.arange(n)
    return perm, inverse


def data_path(*parts) -> str:
    return os.path.join(DATA, *parts)
