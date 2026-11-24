"""Discovery of mechanisms of design q, by a discoverer that the discovered mechanisms change.

A fork of ``discovery.py`` (whose code the open registration pins), for design q
(``rsi6/learner/design_q.py``): the steps, the measurements, the caps, the acceptance rule and
the records are those of ``discovery.py``; what differs is what the discoverer is made of.

The discoverer of design q draws an edit of the parent from a distribution over the cells of the
edit space (the cells of ``edits.py`` and four cells that change the inner settings of design
q: ``share``, ``variants``, ``edits`` and a weight of ``w``). Its log-probabilities are the sum
of two parts:

* weights learned, as in ``discovery.py``, by a mechanism's learning principle (its ``init``,
  ``propose`` and ``update`` programs run over the weight vector, with the candidates' measured
  values as the fitness);
* the inner prior ``w`` of a mechanism, on the eighteen cells that design q's search inside
  acquisition also uses (edits of the score and pick programs and of the constants): what
  makes the search for a representation inside one category productive is used, unchanged, to
  steer the search for mechanisms across categories.

The number of edits of a candidate is drawn with the mechanism's inner ``edits`` weights.

Arms: in the ``recursive`` arm the mechanism that supplies the principle, the prior and the
edit weights is the current parent, rebuilt at every acceptance: a discovered mechanism changes
how the next candidates are generated in three ways. In the ``frozen`` arm it is always
generation 0 (rebuilt at the same moments). ``uniform``: no learning, no prior, the registered
edit weights. ``shuffled``: generation 0's principle learning from permuted values, with
generation 0's prior. ``tune``: the constants and numbers only (theta perturb, pop, batch,
shortlist, holdback and the four inner cells), drawn uniformly.

Record types are ``q_step``, ``q_accept`` and ``q_lineage_done``, apart from the open
experiment's.
"""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from rsi6.learner import design_o as O
from rsi6.learner import design_q as Q
from rsi6.learner import designs
from rsi6.open import edits
from rsi6.open.discovery import (ASSESS_BUDGET, CPU_RATIO, CPU_STEP, SEARCH_BUDGET, SEED_STRIDE, append_once, cpu_of, jobs,
                                 paired, score_of, softmax)

INNER = [("inner", "share"), ("inner", "variants"), ("inner", "edits"), ("inner", "w")]
CELLS = list(edits.CELLS) + INNER
SHARED = [edits.CELLS.index(c) for c in Q.INNER_CELLS]         # the outer cells that the inner prior also weighs
TUNE_CELLS = [k for k, cell in enumerate(CELLS)
              if cell == ("theta", "perturb") or (cell[0] == "scalar" and cell[1] in ("pop", "batch", "shortlist", "holdback"))
              or cell[0] == "inner"]
EDIT_SETS = ([1.0, 0.0, 0.0], [0.6, 0.3, 0.1], [0.4, 0.4, 0.2], [0.2, 0.4, 0.4], [0.0, 0.5, 0.5])


def apply_edit(mechanism: dict, cell, library: list, rng) -> tuple:
    """An edit of a design-q mechanism: the cells of ``edits.py`` act on its design-o part, the
    inner cells on its inner settings."""
    part, kind = cell
    if part != "inner":
        new, info = edits.apply_edit(Q.o_part(mechanism), cell, library, rng)
        if new is None:
            return None, info
        out = dict(new, design="q", inner=copy.deepcopy(mechanism["inner"]))
        return Q.validate(out), info
    g = copy.deepcopy(mechanism)
    inner, info = g["inner"], {"part": "inner", "kind": kind}
    if kind == "share":
        inner["share"] = float(rng.choice([s for s in Q.SHARES if s != inner["share"]]))
    elif kind == "variants":
        inner["variants"] = int(rng.choice([v for v in Q.VARIANTS if v != inner["variants"]]))
    elif kind == "edits":
        others = [e for e in EDIT_SETS if [round(x / sum(e), 6) for x in e] != inner["edits"]]
        inner["edits"] = list(others[int(rng.integers(len(others)))])
    else:
        k = int(rng.integers(len(inner["w"])))
        inner["w"][k] = float(np.clip(inner["w"][k] + rng.choice([-1.0, 1.0]), -8.0, 8.0))
        info["cell"] = k
    try:
        return Q.validate(g), info
    except ValueError as error:
        return None, f"invalid: {error}"


def effective(mechanism: dict) -> dict:
    g = dict(edits.effective(Q.o_part(mechanism)), design="q", inner=copy.deepcopy(mechanism["inner"]))
    if g["inner"]["share"] == 0.0:                   # no program round: the other inner settings are never read
        g["inner"] = {"share": 0.0}
    return g


def behaviour(mechanism: dict) -> str:
    return hashlib.sha256(json.dumps(effective(mechanism), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def principle(mechanism: dict) -> str:
    """What of a mechanism the discoverer reads: its live learning programs, its inner prior and
    its inner edit weights."""
    live = O.live_principle(mechanism)
    text = json.dumps([[live[p] for p in ("init", "propose", "update")], mechanism["inner"]["w"], mechanism["inner"]["edits"]],
                      separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


class Discoverer:
    def __init__(self, source: dict, rng, knobs: dict, weights=None, library=None, mode="recursive"):
        self.knobs = dict(knobs)
        self.library = list(library or [])
        self.mode = mode
        self.rng = rng
        self.rebuild(source, np.zeros(len(CELLS)) if weights is None else np.asarray(weights, float))

    def rebuild(self, source: dict, start) -> None:
        self.source = principle(source)
        self.prior = np.zeros(len(CELLS))
        self.prior[SHARED] = np.asarray(source["inner"]["w"], float)
        self.nedit = np.asarray(source["inner"]["edits"], float)
        self.learner = O.Acquirer(source, np.asarray(start, float), self.rng, pop=self.knobs["kd"])

    def weights(self) -> np.ndarray:
        return self.learner.A[0].copy()

    def propose(self) -> np.ndarray:
        if self.mode in ("uniform", "tune"):
            return np.zeros((self.knobs["kd"], len(CELLS)))
        return self.learner.propose()[: self.knobs["kd"]]

    def distribution(self, w) -> np.ndarray:
        if self.mode == "tune":
            p = np.zeros(len(CELLS))
            p[TUNE_CELLS] = 1.0 / len(TUNE_CELLS)
            return p
        if self.mode == "uniform":
            return softmax(np.zeros(len(CELLS)))
        return softmax(np.asarray(w, float) + self.prior)

    def edit_weights(self) -> np.ndarray:
        return np.asarray(self.knobs["nedit"], float) if self.mode in ("uniform", "tune") else self.nedit

    def learn(self, values) -> list:
        values = np.asarray(values, float)
        if self.mode in ("uniform", "tune"):
            return values.tolist()
        if self.mode == "shuffled":
            values = self.rng.permutation(values)
        self.learner.update(values)
        return values.tolist()


class Lineage:
    """One line of descent of design q (see ``discovery.Lineage``, of which this is a fork)."""

    def __init__(self, name, mechanism, envs, seeds, confirm_base, cache, ledger, rng, knobs, mode="recursive", memo=None,
                 reference=None, principle_source=None):
        self.name, self.envs, self.seeds = name, list(envs), list(seeds)
        self.confirm_base = int(confirm_base)
        self.cache, self.ledger, self.rng, self.knobs = cache, ledger, rng, dict(knobs)
        self.parent = Q.validate(mechanism)
        self.start = self.parent
        self.memo = memo if memo is not None else {}
        self.principle_source = principle_source if principle_source is not None else self.start
        self.D = Discoverer(self.principle_source, rng, self.knobs, mode=mode)
        self.steps, self.accepted, self.confirmations, self.spent = 0, [], 0, 0.0
        self.charged = set()
        self.seen = {behaviour(self.parent)}
        self.reference = reference if reference is not None else self.parent
        self.parent_records = self.records(self.parent, self.seeds, SEARCH_BUDGET, "start")
        self.parent_score = score_of(self.parent_records)

    def records(self, mechanism, seeds, budget, tag):
        key = (behaviour(mechanism), tuple(self.envs), tuple(seeds), budget.get("part"))
        if key not in self.memo:
            self.memo[key] = self.cache.get(jobs(mechanism, self.envs, seeds, budget, f"q:{self.name}:{tag}"))
        for r in self.memo[key]:
            if r["key"] not in self.charged:
                self.charged.add(r["key"])
                self.spent += r["cpu"]["acquire"] + r["cpu"]["apply"]
        return self.memo[key]

    def batch(self, mechanisms, seeds, budget, tag) -> None:
        todo = [m for m in mechanisms if (behaviour(m), tuple(self.envs), tuple(seeds), budget.get("part")) not in self.memo]
        if todo:
            self.cache.get([j for m in todo for j in jobs(m, self.envs, seeds, budget, f"q:{self.name}:{tag}")])

    def _candidate(self, w):
        p = self.D.distribution(w)
        nedit = self.D.edit_weights()
        for _ in range(8):
            n = 1 + int(self.rng.choice(len(nedit), p=nedit / nedit.sum()))
            m, desc, cells = self.parent, [], []
            for _ in range(n):
                for _ in range(12):
                    c = int(self.rng.choice(len(CELLS), p=p))
                    new, info = apply_edit(m, CELLS[c], self.D.library, self.rng)
                    if new is not None:
                        m, cells = new, cells + [c]
                        desc.append(info)
                        break
            key = behaviour(m)
            if key not in self.seen:
                return m, desc, cells, key
        return None, [], [], None

    def step(self) -> dict:
        knobs = self.knobs
        before, parent_digest, used_principle = self.parent_score, designs.digest(self.parent), self.D.source
        W = self.D.propose()
        cands = [self._candidate(w) for w in W]
        for c in cands:
            if c[0] is not None:
                self.seen.add(c[3])
        screen, rest = self.seeds[:1], self.seeds[1:]
        live = [c for c in cands if c[0] is not None]
        self.batch([c[0] for c in live], screen, SEARCH_BUDGET, f"screen{self.steps}")
        parent_screen = self.records(self.parent, screen, SEARCH_BUDGET, "screen")
        ref_screen = cpu_of(self.records(self.reference, screen, SEARCH_BUDGET, "reference"))
        ref_rest = cpu_of(self.records(self.reference, rest, SEARCH_BUDGET, "reference")) if rest else 0.0
        values, rows = [], []
        for m, desc, cells, key in cands:
            if m is None:
                values.append(None)
                rows.append({"digest": None, "reason": "no new candidate"})
                continue
            got = self.records(m, screen, SEARCH_BUDGET, f"screen{self.steps}")
            ok = cpu_of(got) <= CPU_RATIO * ref_screen
            v = float(paired(got, parent_screen).mean())
            values.append(v if ok else None)
            rows.append({"digest": designs.digest(m), "behaviour": key[:16], "edits": desc, "cells": cells, "screen": v,
                         "cpu_screen": cpu_of(got), "runs_screen": [r["key"] for r in got],
                         "reason": None if ok else "cpu above the cap at screening"})
        alive = sorted((k for k, v in enumerate(values) if v is not None and v > 0.0), key=lambda k: -values[k])
        promoted = alive[: max(1, int(round(knobs["promote"] * len(cands))))] if alive else []
        if rest and promoted:
            self.batch([cands[k][0] for k in promoted], rest, SEARCH_BUDGET, f"promote{self.steps}")
        parent_rest = self.records(self.parent, rest, SEARCH_BUDGET, "promote") if rest else []
        for k in promoted:
            got = self.records(cands[k][0], rest, SEARCH_BUDGET, f"promote{self.steps}")
            ok = cpu_of(got) <= CPU_RATIO * ref_rest
            values[k] = float(paired(got, parent_rest).mean()) if ok else None
            rows[k].update({"promoted": values[k], "cpu_promote": cpu_of(got), "runs_promote": [r["key"] for r in got],
                            "reason": None if ok else "cpu above the cap on the other discovery seeds"})
        measured = [v for v in values if v is not None]
        floor = (min(measured) if measured else 0.0) - 0.01
        F = [floor if v is None else (v - knobs["neutral"] if v == 0.0 else v) for v in values]
        given = self.D.learn(F)
        accepted = None
        ready = [k for k in promoted if values[k] is not None and values[k] >= knobs["margin"]]
        if ready:
            best = max(ready, key=lambda k: values[k])
            m = cands[best][0]
            if 4 * (self.confirmations + 1) > SEED_STRIDE:
                raise RuntimeError(f"{self.name}: more confirmations than its window of seeds holds")
            seeds = [self.confirm_base + 4 * self.confirmations + j for j in range(4)]
            self.confirmations += 1
            self.batch([m, self.parent], seeds, SEARCH_BUDGET, f"confirm{self.steps}")
            got = self.records(m, seeds, SEARCH_BUDGET, f"confirm{self.steps}")
            base = self.records(self.parent, seeds, SEARCH_BUDGET, f"confirm{self.steps}")
            d = paired(got, base)
            sd = float(d.std(ddof=1)) if len(d) > 1 else 0.0
            tstat = float(d.mean() / (sd / np.sqrt(len(d)))) if sd > 0 else (np.inf if d.mean() > 0 else 0.0)
            ratio_parent = cpu_of(got) / max(cpu_of(base), 1e-9)
            passed = bool(d.mean() >= 0.5 * knobs["margin"] and tstat >= knobs["t"] and ratio_parent <= CPU_STEP)
            confirmation = {"seeds": seeds, "part": "A", "mean": float(d.mean()), "sd": sd, "t": tstat, "n": len(d),
                            "cpu_ratio_to_parent": ratio_parent, "passed": passed,
                            "runs": [r["key"] for r in got], "parent_runs": [r["key"] for r in base]}
            rows[best]["confirmation"] = confirmation
            if passed:
                accepted = self.accept(m, cands[best][1], values[best], confirmation)
        record = {"type": "q_step", "lineage": self.name, "step": self.steps, "mode": self.D.mode, "parent": parent_digest,
                  "parent_score": before, "parent_score_after": self.parent_score, "seeds": {"screen": screen, "promote": rest},
                  "candidates": rows, "promoted": promoted, "learner_input": given, "accepted": accepted, "knobs": knobs,
                  "principle_used": used_principle, "principle_now": self.D.source,
                  "weights": [round(float(x), 4) for x in self.D.weights()], "library": len(self.D.library),
                  "spent": round(self.spent, 3)}
        append_once(self.ledger, record, ("lineage", "step"))
        self.steps += 1
        return record

    def accept(self, mechanism, desc, value, confirmation) -> str:
        previous = self.parent
        self.parent = mechanism
        self.parent_records = self.records(mechanism, self.seeds, SEARCH_BUDGET, "accepted")
        self.parent_score = score_of(self.parent_records)
        live = {part: {json.dumps(ins) for ins in (O.live(mechanism[part]) if part in ("score", "pick") else mechanism[part])}
                for part in edits.PROGRAMS}
        for info in desc:
            if not isinstance(info, dict):
                continue
            part = info.get("target") or info["part"]
            block = info.get("block")
            if block and part in edits.PROGRAMS and all(json.dumps(ins) in live[part] for ins in block):
                self.D.library.append({"part": part, "block": copy.deepcopy(block)})
        self.D.library = self.D.library[-32:]
        if self.D.mode == "recursive":
            self.D.rebuild(mechanism, self.D.weights())
        elif self.D.mode in ("frozen", "shuffled"):
            self.D.rebuild(self.principle_source, self.D.weights())
        digest = designs.digest(mechanism)
        changed = principle(mechanism) != principle(self.start)
        self.accepted.append({"step": self.steps, "digest": digest, "value": value, "confirmation": confirmation["mean"],
                              "principle_changed": changed})
        append_once(self.ledger, {"type": "q_accept", "lineage": self.name, "step": self.steps, "mode": self.D.mode,
                                  "parent": designs.digest(previous), "digest": digest, "mechanism": mechanism, "value": value,
                                  "confirmation": confirmation, "edits": desc, "principle_changed": changed,
                                  "differences": designs.differences(self.start, mechanism)}, ("lineage", "step"))
        return digest
