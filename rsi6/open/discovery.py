"""Discovery of mechanisms of the open design, by a discoverer that the mechanisms change.

A *system* is a mechanism ``M`` (a version of the open design: its representation and its
learning principle are programs) and a discoverer ``D``. ``D`` is not a fixed procedure:

* It draws edits of ``M`` from a distribution over the cells of the edit space (which part of
  ``M`` an edit changes and what kind of edit it is). The distribution is a weight vector, and
  **the weights are learned by M's own learning principle**: ``D`` runs ``M``'s ``init``,
  ``propose`` and ``update`` programs over its weight vector, with the measured values of the
  candidates it proposed as the fitness. When a step adopts a mechanism whose learning
  principle differs, ``D`` is rebuilt on the new principle: what is discovered changes how the
  next mechanisms are generated. (The *frozen-principle* arm keeps generation 0's principle in
  ``D`` instead; that is the comparison that tests whether this recursion matters.)
* It keeps a library of the instruction blocks of accepted edits, which the ``splice`` edit
  inserts elsewhere: what was found becomes material for what is proposed.
* Its own numbers (candidates per step, edits per candidate, the margin a candidate must clear)
  differ between lineages and are inherited, perturbed, when a lineage replaces another.

A candidate is measured by the kernel (``rsi6.kernel.run.measure`` through ``Cache``): fresh
instances of the discovery categories after acquisition, at the registered search budget, on
the discovery seeds. A candidate whose measured CPU exceeds the registered ratio over the
mechanism the lineage started from is refused, so that a gain cannot come from more compute.
The best candidate of a step is accepted only if its gain over the parent clears the margin on
the discovery seeds and again, with the same sign, on confirmation seeds it was not selected
on. Nothing here reads a reference, and nothing here touches a category outside the ones it is
given.
"""
from __future__ import annotations

import copy
import time

import numpy as np

from rsi6.learner import design_o as O
from rsi6.learner import designs
from rsi6.open import edits

SEARCH_BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 12, "n_fresh": 24, "part": "A"}
CPU_RATIO = 1.25


def softmax(x):
    z = np.exp(np.clip(x - np.max(x), -30.0, 0.0))
    return z / z.sum()


def jobs(mechanism, envs, seeds, purpose):
    return [{"env": e, "version": mechanism, "seed": s, "budget": SEARCH_BUDGET, "purpose": purpose} for e in envs for s in seeds]


def score_of(records) -> float:
    """Mean over the categories of the mean over seeds of the acquired score on fresh instances."""
    envs = sorted({r["env"] for r in records})
    return float(np.mean([np.mean([r["acquired"] for r in records if r["env"] == e]) for e in envs]))


def cpu_of(records) -> float:
    return float(sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in records))


class Discoverer:
    """The edit distribution (learned by a mechanism's learning principle), the library, the knobs."""

    def __init__(self, principle_source: dict, rng, knobs=None, weights=None, library=None, mode="recursive"):
        self.knobs = dict(knobs or {"kd": 4, "nedit": [0.6, 0.3, 0.1], "margin": 0.002})
        self.library = list(library or [])
        self.mode = mode                                    # "recursive", "frozen", "uniform", "shuffled"
        self.rng = rng
        self.rebuild(principle_source, np.zeros(len(edits.CELLS)) if weights is None else np.asarray(weights, float))

    def rebuild(self, principle_source: dict, start) -> None:
        """Take the learning principle of ``principle_source`` to learn the weights from now on."""
        self.source = edits.behaviour(principle_source)
        self.principle = O.Acquirer(principle_source, np.asarray(start, float), self.rng, pop=self.knobs["kd"])

    def weights(self) -> np.ndarray:
        return self.principle.A[0].copy()

    def propose(self) -> np.ndarray:
        if self.mode == "uniform":
            return np.zeros((self.knobs["kd"], len(edits.CELLS)))
        return self.principle.propose()[: self.knobs["kd"]]

    def learn(self, values) -> None:
        if self.mode == "uniform":
            return
        values = np.asarray(values, float)
        if self.mode == "shuffled":                         # negative control: the feedback carries no information
            values = self.rng.permutation(values)
        self.principle.update(values)


class Lineage:
    """One line of descent: a parent mechanism, its discoverer, and what it has measured."""

    def __init__(self, name, mechanism, envs, seeds, confirm_seeds, cache, ledger, rng, mode="recursive", knobs=None,
                 reference_cpu=None, memo=None):
        self.name, self.envs, self.seeds, self.confirm_seeds = name, list(envs), list(seeds), list(confirm_seeds)
        self.cache, self.ledger, self.rng = cache, ledger, rng
        self.parent = O.validate(mechanism)
        self.start = self.parent
        self.memo = memo if memo is not None else {}       # behaviour -> (score, cpu) on the discovery seeds
        self.D = Discoverer(self.parent, rng, knobs=knobs, mode=mode)
        self.steps, self.accepted = 0, []
        self.parent_score, self.parent_cpu = self.measure(self.parent, "start")
        self.reference_cpu = reference_cpu if reference_cpu is not None else self.parent_cpu
        self.seen = {edits.behaviour(self.parent)}

    def measure(self, mechanism, tag, seeds=None):
        key = (edits.behaviour(mechanism), tuple(seeds or self.seeds))
        if key not in self.memo:
            records = self.cache.get(jobs(mechanism, self.envs, seeds or self.seeds, f"open:{self.name}:{tag}"))
            self.memo[key] = (score_of(records), cpu_of(records))
        return self.memo[key]

    def _candidate(self, w):
        p = softmax(w)
        nedit = np.asarray(self.D.knobs["nedit"], float)
        for _ in range(8):
            n = 1 + int(self.rng.choice(len(nedit), p=nedit / nedit.sum()))
            m, desc, cells = self.parent, [], []
            for _ in range(n):
                for _ in range(12):
                    c = int(self.rng.choice(len(edits.CELLS), p=p))
                    new, info = edits.apply_edit(m, edits.CELLS[c], self.D.library, self.rng)
                    if new is not None:
                        m, cells = new, cells + [c]
                        desc.append(info)
                        break
            key = edits.behaviour(m)
            if key not in self.seen:
                return m, desc, cells, key
        return None, [], [], None

    def step(self) -> dict:
        """One step: propose, measure, learn, and accept the best candidate if it holds up."""
        before = self.parent_score
        W = self.D.propose()
        cands = [self._candidate(w) for w in W]
        fresh = [c for c in cands if c[0] is not None]
        for m, _, _, key in fresh:
            self.seen.add(key)
        # one batch for every fresh candidate on the discovery seeds
        need = [m for m, _, _, key in fresh if (key, tuple(self.seeds)) not in self.memo]
        if need:
            all_jobs = [j for m in need for j in jobs(m, self.envs, self.seeds, f"open:{self.name}:step{self.steps}")]
            self.cache.get(all_jobs)
        values, rows = [], []
        for m, desc, cells, key in cands:
            if m is None:
                values.append(None)
                rows.append({"key": None})
                continue
            s, cpu = self.measure(m, f"step{self.steps}")
            ok = cpu <= CPU_RATIO * self.reference_cpu
            values.append((s - self.parent_score) if ok else None)
            rows.append({"key": key[:16], "edits": desc, "cells": cells, "score": s, "cpu": cpu, "cpu_ok": ok})
        measured = [v for v in values if v is not None]
        floor = (min(measured) if measured else 0.0) - 0.01
        F = np.array([floor if v is None else v for v in values])
        self.D.learn(F)
        accepted = None
        best = int(np.argmax(F)) if len(F) else None
        if best is not None and values[best] is not None and values[best] >= self.D.knobs["margin"]:
            m = cands[best][0]
            # confirmation on seeds used once: a candidate is never confirmed on seeds an earlier selection has seen
            fresh_seeds = [s + 2 * self.steps for s in self.confirm_seeds]
            s2, cpu2 = self.measure(m, f"confirm{self.steps}", seeds=fresh_seeds)
            p2, _ = self.measure(self.parent, f"confirm{self.steps}", seeds=fresh_seeds)
            rows[best]["confirmation"] = s2 - p2
            if s2 - p2 > 0.0 and cpu2 <= CPU_RATIO * self.reference_cpu * len(self.confirm_seeds) / len(self.seeds):
                accepted = self.accept(m, cands[best][1], values[best], s2 - p2)
        record = {"type": "o_step", "lineage": self.name, "step": self.steps, "mode": self.D.mode, "parent": edits.behaviour(self.parent)[:16],
                  "parent_score": before, "parent_score_after": self.parent_score, "candidates": rows, "accepted": accepted,
                  "knobs": self.D.knobs,
                  "principle_of": self.D.source[:16], "weights": [round(float(x), 4) for x in self.D.weights()],
                  "library": len(self.D.library)}
        self.ledger.append(record)
        self.steps += 1
        return record

    def accept(self, mechanism, desc, value, confirmation) -> str:
        key = edits.behaviour(mechanism)
        self.parent = mechanism
        self.parent_score, _ = self.measure(mechanism, "accepted")
        for info in desc:                                  # what an accepted edit inserted becomes material for later edits
            if info.get("block") and info["part"] in edits.PROGRAMS:
                self.D.library.append({"part": info["part"], "block": copy.deepcopy(info["block"])})
            elif info.get("block") and info.get("target"):
                self.D.library.append({"part": info["target"], "block": copy.deepcopy(info["block"])})
        self.D.library = self.D.library[-32:]
        if self.D.mode == "recursive":                     # the adopted learning principle learns the discoverer's weights from now on
            self.D.rebuild(mechanism, self.D.weights())
        self.accepted.append({"step": self.steps, "key": key[:16], "value": value, "confirmation": confirmation})
        self.ledger.append({"type": "o_accept", "lineage": self.name, "step": self.steps, "key": key, "mechanism": mechanism,
                            "digest": designs.digest(mechanism), "value": value, "confirmation": confirmation,
                            "edits": desc, "differences": designs.differences(self.start, mechanism)})
        return key[:16]


def migrate(lineages, rng, ledger) -> None:
    """The lineage whose parent scores lowest takes over the best one's mechanism, library and
    weights, and inherits its discoverer's numbers, perturbed: discoverers are selected by what
    their lineages find."""
    order = sorted(lineages, key=lambda L: L.parent_score)
    worst, best = order[0], order[-1]
    if worst is best or best.parent_score <= worst.parent_score:
        return
    knobs = copy.deepcopy(best.D.knobs)
    knobs["kd"] = int(np.clip(knobs["kd"] + rng.choice([-1, 0, 1]), 2, 8))
    knobs["margin"] = float(np.clip(knobs["margin"] * float(np.exp(rng.normal(0.0, 0.3))), 0.0005, 0.02))
    nedit = np.clip(np.asarray(knobs["nedit"], float) * np.exp(rng.normal(0.0, 0.3, len(knobs["nedit"]))), 0.02, None)
    knobs["nedit"] = [round(float(x), 4) for x in nedit / nedit.sum()]
    worst.parent, worst.parent_score = best.parent, best.parent_score
    worst.D = Discoverer(best.parent if best.D.mode == "recursive" else worst.start, rng, knobs=knobs, weights=best.D.weights(),
                         library=best.D.library, mode=best.D.mode)
    worst.seen |= best.seen
    ledger.append({"type": "o_migrate", "from": best.name, "to": worst.name, "knobs": knobs, "score": best.parent_score})
