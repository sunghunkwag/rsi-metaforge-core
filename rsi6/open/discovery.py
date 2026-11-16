"""Discovery of mechanisms of the open design, by a discoverer that the mechanisms change.

A *system* is a mechanism ``M`` (a version of the open design: its representation and its
learning principle are programs) and a discoverer ``D``. ``D`` is not a fixed procedure:

* It draws edits of ``M`` from a distribution over the cells of the edit space (which part of
  ``M`` an edit changes and what kind of edit it is). The distribution is a weight vector, and
  **the weights are learned by M's own learning principle**: ``D`` runs ``M``'s ``init``,
  ``propose`` and ``update`` programs over its weight vector, with the measured values of the
  candidates it proposed as the fitness. When a step adopts a mechanism, ``D``'s learner starts
  again from its current weights on the adopted mechanism's principle: what is discovered
  changes how the next mechanisms are generated.
* It keeps a library of the instruction blocks of accepted edits that are live in the accepted
  mechanism, which the ``splice`` edit inserts elsewhere.

Arms (``mode``): ``recursive`` (as above); ``frozen`` (generation 0's principle always, restarted
at the same moments: the only difference from ``recursive`` is which principle learns);
``uniform`` (no learning); ``shuffled`` (generation 0's principle learning from permuted
values: a control for the learning of the weights, not for the recursion); ``tune`` (edits of
generation 0's constants and numbers only, drawn uniformly: a control that spends the same
compute tuning instead of discovering).

A step, all measured by the kernel (``rsi6.kernel.run.measure`` through ``Cache``) on the
deciding half of the fresh instances (``part`` A) after acquisition at the registered search
budget. The confirming half (``part`` B) is left alone: the experiment uses it to choose between
lineages and to assess the swap test, on instances no acceptance has seen. A seed changes the
relabelling and the learner's random draws, not the instances.

1. *screen*: every candidate on the first discovery seed;
2. *promote*: the candidates that screened above zero, the best half, on the other discovery
   seeds; their value is the mean paired difference from the parent on those seeds only (the
   screen seed, on which they were selected, is left out);
3. *confirm*: the best promoted candidate whose value clears the margin is measured with its
   parent on four seeds used for no other measurement; it is accepted if the mean paired
   difference over the (category, seed) pairs is at least half the margin and its one-sided t
   statistic at least the registered value (pairs on one category share their instances, so
   this is a screening threshold, not a calibrated test), and if its CPU on those runs is within
   the registered ratio of the parent's.

A candidate whose CPU exceeds the registered ratio over generation 0's on the same runs is
refused at screening and on the other discovery seeds. Every lineage is charged, once per run,
the recorded CPU of every run it uses (served from the ledger or not), and the experiment gives
every lineage the same CPU budget. Nothing here reads a reference, and nothing here touches a
category outside the ones it is given.
"""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from rsi6.learner import design_o as O
from rsi6.learner import designs
from rsi6.open import edits

SEARCH_BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 12, "n_fresh": 24, "part": "A"}
ASSESS_BUDGET = dict(SEARCH_BUDGET, part="B")      # the confirming half: selection and the swap assessment only
CPU_RATIO = 1.25            # against generation 0, on the same runs
CPU_STEP = 1.10             # against the parent, on the confirmation runs
SEED_STRIDE = 1000          # confirmation seeds of one lineage: confirm_base + 4k + j, k < SEED_STRIDE / 4
# the tune arm: generation 0's constants and numbers, nothing that adds or changes an instruction
TUNE_CELLS = [k for k, cell in enumerate(edits.CELLS)
              if cell == ("theta", "perturb") or (cell[0] == "scalar" and cell[1] in ("pop", "batch", "shortlist", "holdback"))]


def append_once(ledger, record: dict, identity) -> dict:
    """Append a record unless one with the same identity is already there. A stopped run started
    again replays its steps from the start (every measurement is served from the ledger, every
    random choice repeats), and each replayed record must agree with the one it finds: a resumed
    run checks its own history."""
    for old in reversed(ledger.select(type=record["type"])):
        if all(old.get(k) == record.get(k) for k in identity):
            for k in record:
                if k not in ("idx", "prev", "h") and json.dumps(old.get(k), sort_keys=True) != json.dumps(record[k], sort_keys=True):
                    raise RuntimeError(f"a replayed {record['type']} record differs from the recorded one in {k!r}")
            return old
    return ledger.append(record)


def softmax(x):
    z = np.exp(np.clip(x - np.max(x), -30.0, 0.0))
    return z / z.sum()


def principle(mechanism: dict) -> str:
    """The identity of a learning principle: its three programs, dead instructions removed (they
    are never run: a change that only adds one is not a change of principle)."""
    live = O.live_principle(mechanism)
    text = json.dumps([live[p] for p in ("init", "propose", "update")], separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def jobs(mechanism, envs, seeds, budget, purpose):
    return [{"env": e, "version": mechanism, "seed": s, "budget": budget, "purpose": purpose} for e in envs for s in seeds]


def cpu_of(records) -> float:
    return float(sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in records))


def paired(cand, base) -> np.ndarray:
    """Differences of the acquired score, candidate minus base, one per (category, seed)."""
    b = {(r["env"], r["seed"]): r["acquired"] for r in base}
    return np.array([r["acquired"] - b[(r["env"], r["seed"])] for r in cand])


def score_of(records) -> float:
    """Mean over the categories of the mean over seeds of the acquired score on fresh instances."""
    envs = sorted({r["env"] for r in records})
    return float(np.mean([np.mean([r["acquired"] for r in records if r["env"] == e]) for e in envs]))


class Discoverer:
    """The edit distribution (learned by a mechanism's learning principle) and the library."""

    def __init__(self, principle_source: dict, rng, knobs: dict, weights=None, library=None, mode="recursive"):
        self.knobs = dict(knobs)
        self.library = list(library or [])
        self.mode = mode
        self.rng = rng
        self.rebuild(principle_source, np.zeros(len(edits.CELLS)) if weights is None else np.asarray(weights, float))

    def rebuild(self, principle_source: dict, start) -> None:
        """Learn the weights with the principle of ``principle_source`` from now on."""
        self.source = principle(principle_source)
        self.learner = O.Acquirer(principle_source, np.asarray(start, float), self.rng, pop=self.knobs["kd"])

    def weights(self) -> np.ndarray:
        return self.learner.A[0].copy()

    def propose(self) -> np.ndarray:
        if self.mode in ("uniform", "tune"):
            return np.zeros((self.knobs["kd"], len(edits.CELLS)))
        return self.learner.propose()[: self.knobs["kd"]]

    def distribution(self, w) -> np.ndarray:
        if self.mode == "tune":
            p = np.zeros(len(edits.CELLS))
            p[TUNE_CELLS] = 1.0 / len(TUNE_CELLS)
            return p
        return softmax(w)

    def learn(self, values) -> list:
        """Learn from the candidates' values; returns what the learner was given."""
        values = np.asarray(values, float)
        if self.mode in ("uniform", "tune"):
            return values.tolist()
        if self.mode == "shuffled":                         # the feedback carries no information
            values = self.rng.permutation(values)
        self.learner.update(values)
        return values.tolist()


class Lineage:
    """One line of descent: a parent mechanism, its discoverer, what it has measured and spent."""

    def __init__(self, name, mechanism, envs, seeds, confirm_base, cache, ledger, rng, knobs, mode="recursive", memo=None,
                 reference=None, principle_source=None):
        self.name, self.envs, self.seeds = name, list(envs), list(seeds)
        self.confirm_base = int(confirm_base)               # confirmation k of this lineage uses confirm_base + 4k + (0..3)
        self.cache, self.ledger, self.rng, self.knobs = cache, ledger, rng, dict(knobs)
        self.parent = O.validate(mechanism)
        self.start = self.parent
        self.memo = memo if memo is not None else {}
        # whose learning principle learns the weights in the frozen and shuffled arms (generation 0's unless the
        # experiment assigns another, as the swap test does); the recursive arm always takes the current parent's
        self.principle_source = principle_source if principle_source is not None else self.start
        self.D = Discoverer(self.principle_source, rng, self.knobs, mode=mode)
        self.steps, self.accepted, self.confirmations, self.spent = 0, [], 0, 0.0
        self.charged = set()                                 # run keys this lineage has paid for
        self.seen = {edits.behaviour(self.parent)}
        self.reference = reference if reference is not None else self.parent   # generation 0, for the CPU cap
        self.parent_records = self.records(self.parent, self.seeds, SEARCH_BUDGET, "start")
        self.parent_score = score_of(self.parent_records)

    def records(self, mechanism, seeds, budget, tag):
        """The kernel's records of ``mechanism`` on the lineage's categories and these seeds; the
        lineage is charged their CPU the first time it uses them."""
        key = (edits.behaviour(mechanism), tuple(self.envs), tuple(seeds), budget.get("part"))
        if key not in self.memo:
            self.memo[key] = self.cache.get(jobs(mechanism, self.envs, seeds, budget, f"open:{self.name}:{tag}"))
        for r in self.memo[key]:
            if r["key"] not in self.charged:
                self.charged.add(r["key"])
                self.spent += r["cpu"]["acquire"] + r["cpu"]["apply"]
        return self.memo[key]

    def batch(self, mechanisms, seeds, budget, tag) -> None:
        """Measure several mechanisms in one parallel batch (what is in the ledger is not run again)."""
        todo = [m for m in mechanisms if (edits.behaviour(m), tuple(self.envs), tuple(seeds), budget.get("part")) not in self.memo]
        if todo:
            self.cache.get([j for m in todo for j in jobs(m, self.envs, seeds, budget, f"open:{self.name}:{tag}")])

    def _candidate(self, w):
        p = self.D.distribution(w)
        nedit = np.asarray(self.knobs["nedit"], float)
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
        # a candidate that changed nothing it was measured on wasted its measurement: a little below nothing
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
        record = {"type": "o_step", "lineage": self.name, "step": self.steps, "mode": self.D.mode, "parent": parent_digest,
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
        for info in desc:                                  # what an accepted edit inserted, if still live in the accepted mechanism
            part = info.get("target") or info["part"]
            block = info.get("block")
            if block and part in edits.PROGRAMS and all(json.dumps(ins) in live[part] for ins in block):
                self.D.library.append({"part": part, "block": copy.deepcopy(block)})
        self.D.library = self.D.library[-32:]
        if self.D.mode == "recursive":                     # the adopted principle learns the discoverer's weights from now on
            self.D.rebuild(mechanism, self.D.weights())
        elif self.D.mode in ("frozen", "shuffled"):        # the assigned principle, restarted at the same moment
            self.D.rebuild(self.principle_source, self.D.weights())
        digest = designs.digest(mechanism)
        changed = principle(mechanism) != principle(self.start)
        self.accepted.append({"step": self.steps, "digest": digest, "value": value, "confirmation": confirmation["mean"],
                              "principle_changed": changed})
        append_once(self.ledger, {"type": "o_accept", "lineage": self.name, "step": self.steps, "mode": self.D.mode,
                                  "parent": designs.digest(previous), "digest": digest, "mechanism": mechanism, "value": value,
                                  "confirmation": confirmation, "edits": desc, "principle_changed": changed,
                                  "differences": designs.differences(self.start, mechanism)}, ("lineage", "step"))
        return digest
