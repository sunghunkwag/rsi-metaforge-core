"""Design "r": a learner whose discovery mechanism is rebuilt, at the start of every acquisition,
from the record of its own earlier discoveries.

Design q (``design_q.py``) searches over its score and pick programs inside acquisition: program
rounds try edited copies of the current programs on the training problems of the category being
learned and switch when a copy wins on two batches. Its edit operators and their probabilities
are fixed. In development that search was starved and noisy (q0 minus o0 about 0).

Design r keeps design q's acquisition and makes the machinery that generates the edits a product
of the learner's own experience, carried from one acquisition to the next through the kernel's
memory channel (``acquire(problems, rng, memory)``): what one category's search discovered
changes how the next category's search generates candidates. Three parts of that machinery
change across acquisitions:

* the prior over the inner edit operators: every variant of every program round is credited to
  the operators that made it with its rank difference from the current programs on the round's
  batch (``d`` in [-1, 1], ``1/k`` to each of its ``k`` operators); at the start of an
  acquisition the prior weight of an operator is ``clip(beta * m / s, -clip, clip)``, where
  ``m = sum(d) / (n + shrink)`` over every recorded variant and ``s`` the pooled spread of ``d``;
* composite operators: the sequence of operators of every confirmed switch (a variant that won on
  two batches) is kept as a composite operator, which a share of later variants applies as a
  whole; a composite is credited like an operator and its weight comes from its own record;
* reusable primitives: the instruction blocks that confirmed switches inserted and that are live
  in the programs the acquisition ended with are kept in a library, which the splice operators
  (absent from design q) insert into later programs.

Nothing in the memory is a score on fresh instances, a reference or a category's name: only the
learner's own totals on training problems (through ``d``), operator sequences and instruction
blocks. With empty memory design r is design q with splice operators that find no block, which
do nothing.

The entry an acquisition adds to the memory is also written into its report (key ``relay``),
which the kernel stores in the run record: a chain of acquisitions can therefore be rebuilt, and
replayed, from the ledger alone.
"""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from rsi6.learner import design_o as O
from rsi6.learner import design_q as Q
from rsi6.open import edits as E

CELLS = list(Q.INNER_CELLS) + [("score", "splice"), ("pick", "splice")]
N_CELLS = len(CELLS)
Q_KEYS = tuple(Q.O_KEYS) + ("inner",)


def default() -> dict:
    """Generation 0 of design r: design q's generation 0 with the relay settings below."""
    out = Q.default()
    out["design"] = "r"
    out["relay"] = {"beta": 1.0, "shrink": 20.0, "clip": 2.0, "composite_share": 0.25, "max_composites": 8,
                    "max_blocks": 16, "max_records": 64}
    return out


def q_part(version: dict) -> dict:
    out = {k: copy.deepcopy(version[k]) for k in Q_KEYS}
    out["design"] = "q"
    return out


def validate(version: dict) -> dict:
    keys = set(Q_KEYS) | {"relay"}
    if set(version) != keys or version.get("design") != "r":
        raise ValueError(f"a version of design r has exactly the parts {sorted(keys)}")
    out = Q.validate(q_part(version))
    out["design"] = "r"
    relay = version["relay"]
    want = {"beta", "shrink", "clip", "composite_share", "max_composites", "max_blocks", "max_records"}
    if set(relay) != want:
        raise ValueError(f"relay: {sorted(want)}")
    beta, shrink, clip = float(relay["beta"]), float(relay["shrink"]), float(relay["clip"])
    share = float(relay["composite_share"])
    mc, mb, mr = int(relay["max_composites"]), int(relay["max_blocks"]), int(relay["max_records"])
    if not (0 <= beta <= 4 and 0 < shrink <= 200 and 0 < clip <= 4 and 0 <= share <= 0.5 and 0 <= mc <= 32
            and 0 <= mb <= 64 and 1 <= mr <= 256):
        raise ValueError("relay settings out of range")
    out["relay"] = {"beta": round(beta, 6), "shrink": round(shrink, 6), "clip": round(clip, 6), "composite_share": round(share, 6),
                    "max_composites": mc, "max_blocks": mb, "max_records": mr}
    return out


def digest(version: dict) -> str:
    return hashlib.sha256(json.dumps(validate(version), separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    out = Q.differences(q_part(a), q_part(b))
    for k in a["relay"]:
        if a["relay"][k] != b["relay"][k]:
            out[f"relay.{k}"] = {"from": a["relay"][k], "to": b["relay"][k], "function": "explore"}
    return out


SCHEMA = {}


# =============================================================================================
# what the memory holds, and what is rebuilt from it
# =============================================================================================
def _empty_entry() -> dict:
    return {"cells": [[0, 0.0, 0.0] for _ in range(N_CELLS)], "composites": [], "blocks": [], "rejected_blocks": [],
            "variants": 0, "rounds": 0, "switches": 0}


def machinery(entries: list, relay: dict) -> dict:
    """The discovery machinery an acquisition starts with, rebuilt from the memory's entries:
    the prior over the operators, the composite operators with their weights, the library."""
    n = np.zeros(N_CELLS)
    s = np.zeros(N_CELLS)
    ss = np.zeros(N_CELLS)
    composites, blocks = {}, []
    for entry in entries:
        for c, (cn, cs, css) in enumerate(entry["cells"]):
            n[c] += cn
            s[c] += cs
            ss[c] += css
        for comp in entry["composites"]:
            key = json.dumps(comp["cells"])
            got = composites.setdefault(key, {"cells": list(comp["cells"]), "n": 0, "s": 0.0, "ss": 0.0})
            got["n"] += comp["n"]
            got["s"] += comp["s"]
            got["ss"] += comp["ss"]
        for b in entry["blocks"]:
            if b not in blocks:
                blocks.append(b)
    total_n = n.sum()
    if total_n > 1:
        mean = s.sum() / total_n
        spread = float(np.sqrt(max(ss.sum() / total_n - mean ** 2, 1e-6)))
    else:
        spread = 1.0
    m = s / (n + relay["shrink"])
    prior = np.clip(relay["beta"] * m / spread, -relay["clip"], relay["clip"])
    comps = sorted(composites.values(), key=lambda c: -(c["s"] / (c["n"] + relay["shrink"])))[: relay["max_composites"]]
    for c in comps:
        c["weight"] = float(np.clip(relay["beta"] * (c["s"] / (c["n"] + relay["shrink"])) / spread, -relay["clip"], relay["clip"]))
    return {"prior": prior, "composites": comps, "blocks": blocks[-relay["max_blocks"]:], "spread": spread,
            "recorded": int(total_n)}


class LearnerR(Q.LearnerQ):
    """The learner of design r."""

    def __init__(self, version: dict):
        full = validate(version)
        super().__init__(q_part(full))
        self.relay = full["relay"]
        self.m = machinery([], self.relay)
        self.entry = _empty_entry()

    def acquire(self, problems, rng, memory=None):
        entries = list((memory or {}).get("entries", []))
        self.m = machinery(entries[-self.relay["max_records"]:], self.relay)
        self.entry = _empty_entry()
        self._sensor_cache = {}
        if problems[0].kind == "predict":
            capability, report = self._acquire_predict(problems, rng)
            return capability, {"entries": entries}, report
        capability, report = self._acquire_open(problems, rng)
        report["design"] = "r"
        report["relay_in"] = {"entries": len(entries), "recorded": self.m["recorded"], "composites": len(self.m["composites"]),
                              "blocks": len(self.m["blocks"]), "prior": [round(float(x), 4) for x in self.m["prior"]]}
        report["relay"] = self.entry
        return capability, {"entries": entries + [self.entry]}, report

    # ---- the variants, now drawn by the rebuilt machinery, and credited -----------------------
    def _variant(self, prog, theta, rng):
        """An edited copy of ``prog``. Without composites and without a library this is design
        q's ``_variant`` draw for draw (the splice operators are not offered while the library is
        empty), with the rebuilt prior added to the inner weights."""
        library = [{"part": b["part"], "block": b["block"]} for b in self.m["blocks"]]
        active = list(range(len(Q.INNER_CELLS))) + ([len(Q.INNER_CELLS), len(Q.INNER_CELLS) + 1] if library else [])
        weights = np.concatenate([np.asarray(self.inner["w"], float), np.zeros(N_CELLS - len(Q.INNER_CELLS))]) + self.m["prior"]
        p = Q.softmax(weights[active])
        comps = self.m["composites"]
        use_comp = bool(comps) and rng.random() < self.relay["composite_share"]
        g = dict(self.g, score=copy.deepcopy(prog["score"]), pick=copy.deepcopy(prog["pick"]),
                 theta=[float(np.clip(x, -100.0, 100.0)) for x in theta])
        used, inserted, composite = [], [], None

        def take(cell, new, info):
            if len(new["theta"]) > len(g["theta"]):          # a new constant: a random start, not a no-op
                base = 1.0 if (info.get("block") and info["block"][-1][0] == "scale" and cell[0] == "theta") else 0.0
                new["theta"][-1] = round(float(np.clip(base + rng.normal(0.0, 1.0), -50.0, 50.0)), 6)
            if info.get("block") and info["part"] in ("score", "pick") and info["kind"] in ("insert", "term", "cross"):
                inserted.append({"part": info["part"], "block": copy.deepcopy(info["block"])})
            return new

        if use_comp:                                          # a composite operator: its operators in order, once each
            comp = comps[int(rng.choice(len(comps), p=Q.softmax([c["weight"] for c in comps])))]
            composite = [list(c) for c in comp["cells"]]
            for c in comp["cells"]:
                cell = tuple(c)
                new, info = E.apply_edit(g, cell, library, rng)
                if new is not None:
                    g = take(cell, new, info)
                    used.append(CELLS.index(cell))
        else:
            ed = np.asarray(self.inner["edits"], float)
            n = 1 + int(rng.choice(3, p=ed / ed.sum()))
            for _ in range(n):
                for _ in range(12):
                    c = active[int(rng.choice(len(active), p=p))]
                    cell = CELLS[c]
                    new, info = E.apply_edit(g, cell, library, rng)
                    if new is None:
                        continue
                    g = take(cell, new, info)
                    used.append(c)
                    break
        if not used:
            return None
        self._last_plan = {"cells": used, "composite": composite, "inserted": inserted}
        return {"score": g["score"], "pick": g["pick"]}, np.array(g["theta"], dtype=float)

    def _credit(self, plans, F, switched_to):
        """Credit every variant of a program round to the operators that made it."""
        K = len(F)
        if K < 2:
            return
        self.entry["rounds"] += 1
        for j, plan in enumerate(plans, start=1):
            if plan is None:
                continue
            d = float((F[j] - F[0]) / (K - 1))
            share = 1.0 / len(plan["cells"])
            for c in plan["cells"]:
                cell = self.entry["cells"][c]
                cell[0] += share
                cell[1] += share * d
                cell[2] += share * d * d
            self.entry["variants"] += 1
            if plan["composite"] is not None:
                key = plan["composite"]
                for comp in self.entry["composites"]:
                    if comp["cells"] == key:
                        break
                else:
                    comp = {"cells": key, "n": 0, "s": 0.0, "ss": 0.0}
                    self.entry["composites"].append(comp)
                comp["n"] += 1
                comp["s"] += d
                comp["ss"] += d * d
            if j == switched_to:
                self.entry["switches"] += 1
                if len(plan["cells"]) >= 2 and plan["composite"] is None:
                    self.entry["composites"].append({"cells": [list(CELLS[c]) for c in plan["cells"]], "n": 1, "s": d, "ss": d * d})
                self._pending_blocks.extend(plan["inserted"])
            elif len(self.entry["rejected_blocks"]) < 32:
                self.entry["rejected_blocks"].extend(plan["inserted"][:1])

    def _acquire_open(self, problems, rng):
        self._pending_blocks = []
        capability, report = self._acquire_open_r(problems, rng)
        final = capability.get("program") or {"score": self.g["score"], "pick": self.g["pick"]}
        live = {part: {json.dumps(ins) for ins in O.live(final[part])} for part in ("score", "pick")}
        for b in self._pending_blocks:
            if all(json.dumps(ins) in live[b["part"]] for ins in b["block"]) and b not in self.entry["blocks"]:
                self.entry["blocks"].append(b)
        return capability, report

    def _acquire_open_r(self, problems, rng):
        """Design q's acquisition (``design_q.LearnerQ._acquire_open``), with the variants of every
        program round credited. The rounds, streams, rules and checks are design q's."""
        g, inner = self.g, self.inner
        meter = problems[0].meter
        n = len(problems)
        rng_order, rng_acq, rng_con = (np.random.default_rng(int(x)) for x in rng.integers(0, 2 ** 63, size=3))
        rng_edit = np.random.default_rng(int(rng.integers(0, 2 ** 63)))
        order = rng_order.permutation(n)
        n_check = (min(max(1, int(round(g["holdback"] * n))), n - 1) if n > 1 else 0) if g["select"] == "best_of_3" else 0
        check, fit = order[:n_check], order[n_check:]
        start = np.array(g["theta"], dtype=float)
        start_prog = {"score": g["score"], "pick": g["pick"]}
        prog = start_prog
        report = {"form": "assign", "design": "r", "fit": len(fit), "held_back": len(check), "iterations": 0,
                  "constructions": 0, "failed": None, "program_rounds": 0, "switches": 0, "program_size": None}
        reserve = 3.0 * sum(self._cost(problems[i], g["shortlist"]) for i in check)
        fit_cost = np.array([self._cost(problems[i], g["shortlist"]) for i in fit])
        acq = O.Acquirer(g, start, rng_acq)
        last_best = (prog, start.copy())
        it = 0
        try:
            while len(fit) > 0:
                batch = min(g["batch"], len(fit))
                chosen = rng_order.choice(len(fit), size=batch, replace=False)
                idx = [int(fit[i]) for i in chosen]
                if Q.program_rounds(it, inner["share"]):
                    second = rng_order.choice(len(fit), size=batch, replace=False)
                    idx2 = [int(fit[i]) for i in second]
                    if meter.left() - reserve < (inner["variants"] + 1) * fit_cost[chosen].sum() + 2 * fit_cost[second].sum():
                        break
                    here = acq.A[0].copy()
                    cands, plans = [(prog, here)], []
                    for _ in range(inner["variants"]):
                        self._last_plan = None
                        v = self._variant(prog, here, rng_edit)
                        if v is not None:
                            cands.append(v)
                            plans.append(self._last_plan)
                    keys = self._rollouts_q([problems[i] for i in idx], idx, cands, rng_con, meter)
                    if keys is None:
                        break
                    F = O._fitness(keys)
                    best = int(np.argmax(F))
                    report["program_rounds"] += 1
                    report["constructions"] += len(cands) * batch
                    switched = None
                    if best > 0 and F[best] > F[0]:
                        pair = [cands[0], cands[best]]
                        keys2 = self._rollouts_q([problems[i] for i in idx2], idx2, pair, rng_con, meter)
                        if keys2 is None:
                            self._credit(plans, F, None)
                            break
                        report["constructions"] += 2 * batch
                        F2 = O._fitness(keys2)
                        if F2[1] > F2[0]:
                            prog, theta = cands[best]
                            acq = O.Acquirer(g, theta, rng_acq)
                            last_best = (prog, theta.copy())
                            report["switches"] += 1
                            switched = best
                    self._credit(plans, F, switched)
                else:
                    if meter.left() - reserve < acq.K * fit_cost[chosen].sum():
                        break
                    thetas = acq.propose()
                    keys = self._rollouts_q([problems[i] for i in idx], idx, [(prog, t) for t in thetas], rng_con, meter)
                    if keys is None:
                        break
                    F = O._fitness(keys)
                    last_best = (prog, thetas[int(np.argmax(F))].copy())
                    acq.update(F)
                    report["constructions"] += len(thetas) * batch
                report["iterations"] += 1
                it += 1
        except Q.BudgetExhausted:
            report["failed"] = "decide: the budget ended inside a construction"
        options = {"start": (start_prog, start), "state": (prog, acq.A[0].copy()), "last_best": last_best}
        chosen_prog, chosen_theta, learned = start_prog, start, False
        if report["iterations"] == 0:
            report["failed"] = report["failed"] or "decide: the budget did not allow one round of learning"
        elif n_check == 0:
            name = g["select"] if g["select"] != "best_of_3" else "state"
            (chosen_prog, chosen_theta), learned = options[name], True
            report["held_back"] = 0
        else:
            names = ["start", "state", "last_best"]
            try:
                keys = self._rollouts_q([problems[i] for i in check], [int(i) for i in check], [options[k] for k in names], rng_con, meter)
                if keys is None:
                    report["failed"] = "decide: no budget left for the held-back check"
                else:
                    f = O._fitness(keys)
                    report["held_back"] = {k: float(f[j]) for j, k in enumerate(names)}
                    best = int(np.argmax(f))
                    if f[best] > f[0]:
                        (chosen_prog, chosen_theta), learned = options[names[best]], True
                    else:
                        report["failed"] = "self-assess: nothing learned beat the starting constants on held-back problems"
            except Q.BudgetExhausted:
                report["failed"] = "decide: the budget ended inside the held-back check"
        report["learned"] = learned
        capability = {"kind": "open", "theta": [float(x) for x in chosen_theta], "learned": learned}
        if chosen_prog is not start_prog and (chosen_prog["score"] != start_prog["score"] or chosen_prog["pick"] != start_prog["pick"]):
            capability["program"] = {"score": chosen_prog["score"], "pick": chosen_prog["pick"]}
            report["program_size"] = [len(O.live(chosen_prog["score"])), len(O.live(chosen_prog["pick"]))]
        return capability, report


# =============================================================================================
# the controls' memories, made from relayed ones (registered transformations)
# =============================================================================================
def derangement(n: int, seed: int) -> list:
    """A fixed permutation of ``n`` labels that moves every label."""
    rng = np.random.default_rng(seed)
    while True:
        p = rng.permutation(n)
        if all(p[i] != i for i in range(n)):
            return [int(x) for x in p]


def permutation(n: int, seed: int) -> list:
    """A uniformly random permutation of ``n`` labels (fixed points allowed)."""
    return [int(x) for x in np.random.default_rng(seed).permutation(n)]


def shuffled(memory: dict, seed: int) -> dict:
    """The memory with the same amounts and no information about which operator did what: the
    operator labels permuted uniformly at random in the cell records and in the composites, and
    the library replaced by blocks of variants that were not kept (as many as there were kept
    blocks, from the same entries). The permutation is uniform, not a derangement: a derangement
    would move the strongly negative records of the few destructive operators onto other
    operators every time and so make the placebo misinformed rather than uninformed; under a
    uniform permutation every operator's record is, in expectation, the mean record."""
    perm = permutation(N_CELLS, seed)
    out = []
    for e in memory.get("entries", []):
        cells = [None] * N_CELLS
        for c in range(N_CELLS):
            cells[perm[c]] = list(e["cells"][c])
        comps = [{"cells": [list(CELLS[perm[CELLS.index(tuple(x))]]) for x in comp["cells"]], "n": comp["n"], "s": comp["s"], "ss": comp["ss"]}
                 for comp in e["composites"]]
        blocks = list(e.get("rejected_blocks", []))[: len(e["blocks"])]
        out.append(dict(e, cells=cells, composites=comps, blocks=blocks))
    return {"entries": out}


def ablated(memory: dict, keep: str) -> dict:
    """``keep='prior'``: the operator records only (no composites, no library); ``keep='blocks'``:
    the library only (no operator records, no composites)."""
    out = []
    for e in memory.get("entries", []):
        if keep == "prior":
            out.append(dict(e, composites=[], blocks=[]))
        else:
            out.append(dict(e, cells=[[0, 0.0, 0.0] for _ in range(N_CELLS)], composites=[]))
    return {"entries": out}
