"""Design "r": a learner whose discovery machinery is rebuilt, at the start of every acquisition,
from its own record of earlier discoveries, carried across categories in the kernel's memory.

Design q (``design_q.py``) searches over its score and pick programs inside acquisition: a program
round tries edited copies of the current programs on a batch of training problems and switches
when the best copy also wins on a second batch. Its edit operators and their probabilities are
fixed; in development the search gained nothing (rsi6/results/dev_20261116).

Design r keeps design q's acquisition, rounds, rules and checks, and makes three parts of the
machinery that generates the edits a product of the learner's own record, which the kernel hands
from one acquisition to the next (``acquire(problems, rng, memory)``):

* the prior over the 20 inner edit operators (design q's 18 and two splice operators);
* the prior over edit sizes (one, two or three edits per variant);
* a library of instruction blocks taken from kept switches, which the splice operators insert
  again, with the constants they added relocated to new constants.

The record of an acquisition (an ``r_stats`` entry) credits every informative variant of every
program round to the operators that made it: ``d`` is its fitness margin over the current
programs on the round's batch (mean rank, scaled to [-1, 1]); a variant whose constructions
equal the current programs' on every problem of the batch is a tie and carries no credit (an
edit that changes nothing would otherwise look harmless and be preferred); credit is shared
``1/k`` among a variant's ``k`` operators. At the start of an acquisition the weight of an
operator is ``clip(beta * ln(m / ubar), -cap, cap)``, where ``m = (U + kappa * ubar) / (N + kappa)``
is its shrunk mean positive margin and ``ubar`` the mean over all operators (probability matching
on the positive margin; rule ``dplus``). The edit sizes are weighted the same way.

Design r also changes how the inner search judges a candidate (``accept``). Design o's batch
fitness is the mean rank over the batch's problems: a construction that breaks a hard constraint
is last on its problem and no worse, so a copy of the programs that wins narrowly on most
problems and breaks a hard constraint on the others is taken. In development such programs were
taken (4.6% of one acquisition's constructions broke a hard constraint; the programs it kept
broke one on 3 of its 10 training problems and on 3 of 10 fresh instances, which the category
scores 0; rsi6/results/dev_r_20261116). With ``accept: "hard_first"`` every comparison within a
batch is lexicographic, as the cost of one problem already is: first the number of the batch's
problems constructed without a hard violation, then the mean rank; a switch of programs, after
its second batch, is constructed once on every other problem it learns from and is taken only
if it breaks no more of them than the programs it replaces; and the capability kept at the end
passes the same test against the starting programs. ``accept: "rank"`` is design q's rule.

Nothing in the memory is a score on fresh instances, an answer, a reference or a category's
name: only the learner's own ranks on training problems, operator counts and instruction
blocks. With no entry of either kind and ``accept: "rank"``, design r is design q's generation
0 draw for draw. The
entries an acquisition adds are also written into its report (``report["relay"]["new_entries"]``),
which the kernel keeps in the run record: a chain of acquisitions is rebuilt, and replayed, from
the ledger alone.
"""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from rsi6.learner import design_o as O
from rsi6.learner import design_q as Q
from rsi6.open import edits as E

BASE_CELLS = list(Q.INNER_CELLS)
SPLICE_CELLS = [("score", "splice"), ("pick", "splice")]
CELLS = BASE_CELLS + SPLICE_CELLS
N_CELLS = len(CELLS)
BASE_THETA = 10                                     # generation 0's constants; an index at or above it was added by an edit
PARAMLIKE = ("scale", "shift", "const")              # score and pick ops whose field b is a constant's index
KIND_STATS, KIND_LIB, ENTRY_V = "r_stats", "r_lib", 1
RELAY0 = {"beta": 1.0, "kappa": 20.0, "cap": 2.0, "lib_max": 32, "lib_per_run": 4, "rule": "dplus"}
Q_KEYS = tuple(Q.O_KEYS) + ("inner",)
STAT_KEYS = ("N", "U", "S", "Q", "W", "SW")
SIZE_KEYS = ("NE", "UE", "SE", "QE")
ACCEPT = ("hard_first", "rank")                     # the first is generation 0's rule; "rank" is design q's


def default() -> dict:
    out = Q.default()
    out["design"] = "r"
    out["relay"] = dict(RELAY0)
    out["accept"] = ACCEPT[0]
    return out


def q_part(version: dict) -> dict:
    out = {k: copy.deepcopy(version[k]) for k in Q_KEYS}
    out["design"] = "q"
    return out


def validate(version: dict) -> dict:
    keys = set(Q_KEYS) | {"relay", "accept"}
    if set(version) != keys or version.get("design") != "r":
        raise ValueError(f"a version of design r has exactly the parts {sorted(keys)}")
    if version["accept"] not in ACCEPT:
        raise ValueError(f"accept: one of {ACCEPT}")
    out = Q.validate(q_part(version))
    out["design"] = "r"
    r = version["relay"]
    if set(r) != set(RELAY0):
        raise ValueError(f"relay: {sorted(RELAY0)}")
    beta, kappa, cap = float(r["beta"]), float(r["kappa"]), float(r["cap"])
    lib_max, lib_per_run, rule = int(r["lib_max"]), int(r["lib_per_run"]), r["rule"]
    if not (0.1 <= beta <= 4 and 1 <= kappa <= 1000 and 0 < cap <= 8 and 0 <= lib_max <= 64 and 0 <= lib_per_run <= 8
            and rule in ("dplus", "dmean")):
        raise ValueError("relay settings out of range")
    out["relay"] = {"beta": round(beta, 6), "kappa": round(kappa, 6), "cap": round(cap, 6), "lib_max": lib_max,
                    "lib_per_run": lib_per_run, "rule": rule}
    out["accept"] = version["accept"]
    return out


def digest(version: dict) -> str:
    return hashlib.sha256(json.dumps(validate(version), separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    out = Q.differences(q_part(a), q_part(b))
    for k in a["relay"]:
        if a["relay"][k] != b["relay"][k]:
            out[f"relay.{k}"] = {"from": a["relay"][k], "to": b["relay"][k], "function": "explore"}
    if a["accept"] != b["accept"]:
        out["accept"] = {"from": a["accept"], "to": b["accept"], "function": "explore"}
    return out


SCHEMA = {}


def fitness_hard_first(keys: np.ndarray) -> np.ndarray:
    """The batch fitness of rule ``hard_first``: first the number of the batch's problems on which
    the candidate's construction has no hard violation, then design o's mean rank. The candidates
    with the largest such number keep their mean rank exactly (so a batch on which nothing breaks
    a hard constraint is judged as design o judges it); a candidate with fewer is below them all."""
    F = O._fitness(keys)
    clean = (keys[:, :, 0] == 0).sum(axis=1)
    return F - len(F) * (clean.max() - clean)


def _canon(x) -> str:
    return json.dumps(x, separators=(",", ":"), sort_keys=True)


def prior_from(entries, relay: dict):
    """The machinery an acquisition starts with, from the memory's entries (a pure function).
    ``None`` when the memory holds no entry of either kind."""
    stats = [e for e in entries if e.get("kind") == KIND_STATS and e.get("v") == ENTRY_V]
    libs = [e for e in entries if e.get("kind") == KIND_LIB and e.get("v") == ENTRY_V]
    if not stats and not libs:
        return None
    A = {k: np.zeros(N_CELLS) for k in STAT_KEYS}
    B = {k: np.zeros(3) for k in SIZE_KEYS}
    for e in stats:
        for k in STAT_KEYS:
            A[k] += np.asarray(e[k], float)
        for k in SIZE_KEYS:
            B[k] += np.asarray(e[k], float)
    n = float(A["N"].sum())
    beta, kappa, cap = relay["beta"], relay["kappa"], relay["cap"]
    w, wE = np.zeros(N_CELLS), np.zeros(3)
    if relay["rule"] == "dplus":
        if n >= 1 and A["U"].sum() > 0:
            ubar = A["U"].sum() / n
            m = (A["U"] + kappa * ubar) / (A["N"] + kappa)
            w = np.clip(beta * np.log(m / ubar), -cap, cap)
            mE = (B["UE"] + kappa * ubar) / (B["NE"] + kappa)
            wE = np.clip(beta * np.log(mE / ubar), -cap, cap)
    elif n >= 1:                                                # dmean, the pre-written alternative
        dbar = A["S"].sum() / n
        s = np.sqrt(max(A["Q"].sum() / n - dbar ** 2, 1e-6))
        m = (A["S"] + kappa * dbar) / (A["N"] + kappa)
        w = np.clip(beta * (m - dbar) / s, -cap, cap)
        nE = max(B["NE"].sum(), 1.0)
        dbarE = B["SE"].sum() / nE
        mE = (B["SE"] + kappa * dbarE) / (B["NE"] + kappa)
        wE = np.clip(beta * (mE - dbarE) / s, -cap, cap)
    seen, order = {}, []                                        # unique by canonical form, in the order of last occurrence
    for e in libs:
        for b in e["blocks"]:
            key = _canon(b)
            seen[key] = b
            if key in order:
                order.remove(key)
            order.append(key)
    library = [seen[k] for k in order][-relay["lib_max"]:] if relay["lib_max"] > 0 else []
    return {"w": [round(float(x), 6) for x in w], "wE": [round(float(x), 6) for x in wE], "library": library,
            "n": round(n, 6), "entries": len(entries)}


def splice(g: dict, part: str, library: list, rng):
    """Insert a library block into program ``part`` of the design-o mechanism ``g``: the constants
    the block added when it was found are appended as new constants (random starts) and its
    placeholders remapped to them; a term block goes to the end of the program."""
    blocks = [b for b in library if b["part"] == part]
    if not blocks:
        return None, "no block"
    blk = blocks[int(rng.integers(len(blocks)))]
    out = copy.deepcopy(g)
    n0 = len(out["theta"])
    prog = out[part]
    if n0 + blk["fresh"] > O.LIMITS["theta"] or len(prog) + len(blk["block"]) > O.LIMITS[part]:
        return None, "full"
    for _ in range(blk["fresh"]):
        out["theta"].append(round(float(np.clip(rng.normal(0.0, 1.0), -50.0, 50.0)), 6))
    ins = []
    for op, dst, a, b in blk["block"]:
        if op in PARAMLIKE and b < 0:
            b = n0 + (-1 - b)
        ins.append([op, dst, a, b])
    pos = len(prog) if blk["term"] else int(rng.integers(len(prog) + 1))
    prog[pos:pos] = ins
    try:
        out = O.validate(out)
    except ValueError as error:
        return None, f"invalid: {error}"
    return out, {"part": part, "kind": "splice", "block": ins}


def relocate(block: list):
    """A block found in a kept program, its added constants turned into placeholders -1, -2, ..."""
    remap, out = {}, []
    for op, dst, a, b in block:
        if op in PARAMLIKE and b >= BASE_THETA:
            if b not in remap:
                remap[b] = -1 - len(remap)
            b = remap[b]
        out.append([op, dst, a, b])
    term = bool(out) and out[-1][0] == "add" and out[-1][1] == 0 and out[-1][2] == 0 and out[-1][3] != 0
    return out, len(remap), term


class LearnerR(Q.LearnerQ):
    """The learner of design r."""

    def __init__(self, version: dict):
        full = validate(version)
        super().__init__(q_part(full))
        self.relay = full["relay"]
        self.accept = full["accept"]
        self._prior = None

    def acquire(self, problems, rng, memory=None):
        entries = list((memory or {}).get("entries", []))
        if problems[0].kind == "predict":
            capability, report = self._acquire_predict(problems, rng)
            return capability, {"entries": entries}, report
        self._prior = prior_from(entries, self.relay)
        self._sensor_cache = {}
        self._reset_log()
        capability, report = self._acquire_open(problems, rng)
        new = self._new_entries(capability, problems[0])
        report["design"] = "r"
        report["relay"] = {"prior": None if self._prior is None else
                           {"w": [round(x, 4) for x in self._prior["w"]], "wE": [round(x, 4) for x in self._prior["wE"]],
                            "library": len(self._prior["library"]), "n": self._prior["n"], "entries": self._prior["entries"]},
                           "new_entries": new}
        return capability, {"entries": entries + new}, report

    # ---- the log of one acquisition -----------------------------------------------------------
    def _reset_log(self):
        self._stats = {k: np.zeros(N_CELLS) for k in STAT_KEYS}
        self._sizes = {k: np.zeros(3) for k in SIZE_KEYS}
        self._counts = {"rounds": 0, "variants": 0, "informative": 0, "switches": 0}
        self._switches = []
        self._vlog = []

    def _variant(self, prog, theta, rng):
        """With no prior, design q's ``_variant`` draw for draw; with one, the operators, the edit
        sizes and the library it was rebuilt with. Every call logs what it applied."""
        pr = self._prior
        ed = np.asarray(self.inner["edits"], float)
        if pr is None:
            cells_idx = list(range(len(BASE_CELLS)))
            p = Q.softmax(self.inner["w"])
            library = []
        else:
            library = pr["library"]
            cells_idx = list(range(len(BASE_CELLS))) + [len(BASE_CELLS) + i for i, (part, _) in enumerate(SPLICE_CELLS)
                                                         if any(b["part"] == part for b in library)]
            logits = np.concatenate([np.asarray(self.inner["w"], float), np.zeros(len(SPLICE_CELLS))]) + np.asarray(pr["w"], float)
            p = Q.softmax(logits[cells_idx])
            ed = ed * np.exp(np.asarray(pr["wE"], float))
        n = 1 + int(rng.choice(3, p=ed / ed.sum()))
        g = dict(self.g, score=copy.deepcopy(prog["score"]), pick=copy.deepcopy(prog["pick"]),
                 theta=[float(np.clip(x, -100.0, 100.0)) for x in theta])
        applied, infos = [], []
        for _ in range(n):
            for _ in range(12):
                c = cells_idx[int(rng.choice(len(cells_idx), p=p))]
                cell = CELLS[c]
                if cell[1] == "splice":
                    new, info = splice(g, cell[0], library, rng)
                else:
                    new, info = E.apply_edit(g, cell, [], rng)
                if new is None:
                    continue
                if cell[1] != "splice" and len(new["theta"]) > len(g["theta"]):     # design q's random start of a new constant
                    base = 1.0 if (info.get("block") and info["block"][-1][0] == "scale" and cell[0] == "theta") else 0.0
                    new["theta"][-1] = round(float(np.clip(base + rng.normal(0.0, 1.0), -50.0, 50.0)), 6)
                g = new
                applied.append(c)
                infos.append(info)
                break
        if not applied:
            self._vlog.append(None)
            return None
        self._vlog.append({"cells": applied, "k": len(applied), "infos": infos})
        return {"score": g["score"], "pick": g["pick"]}, np.array(g["theta"], dtype=float)

    def _credit(self, logs, keys, F, switched):
        """Credit the informative variants of one program round; ties carry no credit."""
        self._counts["rounds"] += 1
        K = len(F)
        for i, log in enumerate(logs, start=1):
            self._counts["variants"] += 1
            if np.array_equal(keys[i], keys[0]):
                continue                                         # a tie: the variant changed nothing the batch measures
            self._counts["informative"] += 1
            d = float(np.clip((F[i] - F[0]) / (K - 1), -1.0, 1.0))   # under hard_first a lost problem is the worst margin
            k = log["k"]
            for c in log["cells"]:
                self._stats["N"][c] += 1.0 / k
                self._stats["U"][c] += max(d, 0.0) / k
                self._stats["S"][c] += d / k
                self._stats["Q"][c] += d * d / k
                self._stats["W"][c] += (1.0 if d > 0 else 0.0) / k
            self._sizes["NE"][k - 1] += 1.0
            self._sizes["UE"][k - 1] += max(d, 0.0)
            self._sizes["SE"][k - 1] += d
            self._sizes["QE"][k - 1] += d * d
            if i == switched:
                for c in log["cells"]:
                    self._stats["SW"][c] += 1.0 / k
                self._switches.append(log)
                self._counts["switches"] += 1

    def _new_entries(self, capability, P0) -> list:
        r6 = lambda a: [round(float(x), 6) for x in a]
        kept = "program" in capability
        kept_splice = bool(kept and any(CELLS[c][1] == "splice" for log in self._switches for c in log["cells"]))
        stats = {"kind": KIND_STATS, "v": ENTRY_V, **{k: r6(self._stats[k]) for k in STAT_KEYS},
                 **{k: r6(self._sizes[k]) for k in SIZE_KEYS}, **self._counts, "kept": kept, "kept_splice": kept_splice,
                 "layout": {"ordered": bool(P0.ordered), "binary": bool(P0.n_opts == 2), "capacity": P0.capacity is not None}}
        out = [stats]
        if kept and self.relay["lib_per_run"] > 0:
            final = capability["program"]
            live = {part: {_canon(ins) for ins in O.live(final[part])} for part in ("score", "pick")}
            blocks, keys = [], set()
            for log in reversed(self._switches):
                for info in log["infos"]:
                    part = info.get("target") or info.get("part")
                    blk = info.get("block")
                    if not blk or part not in ("score", "pick") or not all(_canon(ins) in live[part] for ins in blk):
                        continue
                    ins, fresh, term = relocate(blk)
                    b = {"part": part, "block": ins, "fresh": fresh, "term": term}
                    if _canon(b) not in keys:
                        keys.add(_canon(b))
                        blocks.append(b)
            blocks = blocks[: self.relay["lib_per_run"]]
            if blocks:
                out.append({"kind": KIND_LIB, "v": ENTRY_V, "blocks": blocks})
        return out

    def _clean_everywhere(self, problems, rest, pair, rng, meter, report) -> bool:
        """Rule ``hard_first``: the second of ``pair`` (programs and constants) is constructed once, with
        the first, on the problems ``rest``; it passes if it breaks hard constraints on no more of
        them than the first does. Rule ``rank`` has no such test."""
        if self.accept != "hard_first" or not rest:
            return True
        keys = self._rollouts_q([problems[i] for i in rest], rest, pair, rng, meter)
        if keys is None:
            report["vetoes"] += 1
            return False
        report["constructions"] += 2 * len(rest)
        clean = (keys[:, :, 0] == 0).sum(axis=1)
        if clean[1] < clean[0]:
            report["vetoes"] += 1
            return False
        return True

    def _acquire_open(self, problems, rng):
        """Design q's ``_acquire_open`` with the log of a program round's variants, their credit after
        the round's fitness, the log entry of a confirmed switch, and, under ``accept: "hard_first"``,
        the lexicographic batch fitness and the two tests on every problem the learner learns from."""
        g, inner = self.g, self.inner
        hard_first = self.accept == "hard_first"
        fitness = fitness_hard_first if hard_first else O._fitness
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
        everywhere = 2.0 * float(fit_cost.sum()) if hard_first else 0.0     # two programs once on every fit problem
        reserve += everywhere                                                # kept for the test of the capability at the end
        if hard_first:
            report["vetoes"] = 0
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
                    if meter.left() - reserve < (inner["variants"] + 1) * fit_cost[chosen].sum() + 2 * fit_cost[second].sum() + everywhere:
                        break
                    here = acq.A[0].copy()
                    self._vlog = []
                    variants = [self._variant(prog, here, rng_edit) for _ in range(inner["variants"])]
                    logs = [log for log in self._vlog if log is not None]
                    cands = [(prog, here)] + [v for v in variants if v is not None]
                    keys = self._rollouts_q([problems[i] for i in idx], idx, cands, rng_con, meter)
                    if keys is None:
                        break
                    F = fitness(keys)
                    best = int(np.argmax(F))
                    report["program_rounds"] += 1
                    report["constructions"] += len(cands) * batch
                    switched = None
                    if best > 0 and F[best] > F[0]:
                        pair = [cands[0], cands[best]]
                        keys2 = self._rollouts_q([problems[i] for i in idx2], idx2, pair, rng_con, meter)
                        if keys2 is None:
                            self._credit(logs, keys, F, None)
                            break
                        report["constructions"] += 2 * batch
                        F2 = fitness(keys2)
                        rest = [int(i) for i in fit if int(i) not in idx and int(i) not in idx2]
                        if F2[1] > F2[0] and self._clean_everywhere(problems, rest, pair, rng_con, meter, report):
                            prog, theta = cands[best]
                            acq = O.Acquirer(g, theta, rng_acq)
                            last_best = (prog, theta.copy())
                            report["switches"] += 1
                            switched = best
                    self._credit(logs, keys, F, switched)
                else:
                    if meter.left() - reserve < acq.K * fit_cost[chosen].sum():
                        break
                    thetas = acq.propose()
                    keys = self._rollouts_q([problems[i] for i in idx], idx, [(prog, t) for t in thetas], rng_con, meter)
                    if keys is None:
                        break
                    F = fitness(keys)
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
                    f = fitness(keys)
                    report["held_back"] = {k: float(f[j]) for j, k in enumerate(names)}
                    best = int(np.argmax(f))
                    if f[best] <= f[0]:
                        report["failed"] = "self-assess: nothing learned beat the starting constants on held-back problems"
                    elif self._clean_everywhere(problems, [int(i) for i in fit], [options["start"], options[names[best]]], rng_con, meter, report):
                        (chosen_prog, chosen_theta), learned = options[names[best]], True
                    else:
                        report["failed"] = "self-assess: what was learned breaks hard constraints that the starting programs keep on the training problems"
            except Q.BudgetExhausted:
                report["failed"] = "decide: the budget ended inside the held-back check"
        report["learned"] = learned
        capability = {"kind": "open", "theta": [float(x) for x in chosen_theta], "learned": learned}
        if chosen_prog is not start_prog and (chosen_prog["score"] != start_prog["score"] or chosen_prog["pick"] != start_prog["pick"]):
            capability["program"] = {"score": chosen_prog["score"], "pick": chosen_prog["pick"]}
            report["program_size"] = [len(O.live(chosen_prog["score"])), len(O.live(chosen_prog["pick"]))]
        return capability, report


# =============================================================================================
# the arms' memories, made from the relayed ones (registered transformations)
# =============================================================================================
def mem(entries) -> dict | None:
    return {"entries": list(entries)} if entries else None


def without(memory, kind) -> dict | None:
    return mem([e for e in (memory or {}).get("entries", []) if e.get("kind") != kind])


def _random_block(blk, rng):
    """A random block with the same part, length, number of new constants and term flag."""
    part, L = blk["part"], len(blk["block"])
    nreg = O.N_REG if part == "score" else O.N_PREG
    sensors = O.SCORE_SENSORS if part == "score" else O.PICK_SENSORS
    quiet = [k for k, name in enumerate(sensors) if name != "noise"]
    if blk["term"]:
        r = int(rng.integers(1, nreg))
        r2 = 1 + (r % (nreg - 1))
        body = [["load", r, int(rng.choice(quiet)), int(rng.integers(O.SENSOR_ARGS))]]
        if L >= 6:
            body += [["load", r2, int(rng.choice(quiet)), int(rng.integers(O.SENSOR_ARGS))], ["mul", r, r, r2]]
        body += [[str(rng.choice(["mm", "rank", "z"])), r, r, 0], ["scale", r, r, -1], ["add", 0, 0, r]]
        fresh = 1
    else:                                                        # as many new constants as the original, then random instructions
        fresh = blk["fresh"]
        body = [[str(rng.choice(["scale", "shift"])), (r := int(rng.integers(nreg))), r, -1 - i] for i in range(min(fresh, L))]
        while len(body) < L:
            body.append(E.random_instruction(part, BASE_THETA, rng))
        fresh = min(fresh, L)
    return {"part": part, "block": body, "fresh": fresh, "term": blk["term"]}


def shuffled(memory, j: int) -> dict | None:
    """Chain j's memory with no information about which operator or which edit size did what:
    every 20-array of every stats entry permuted by one uniformly random permutation of the
    operators, every 3-array by one of the edit sizes (fixed points allowed: a derangement would
    always move the destructive operators' records onto other operators and so misinform), and
    every library block replaced by a random block of the same part, length, constants and form."""
    import zlib
    rng = np.random.default_rng([29, zlib.crc32(b"shuffle"), j])
    pi, sigma = rng.permutation(N_CELLS), rng.permutation(3)
    rng2 = np.random.default_rng([29, zlib.crc32(b"shuffle-lib"), j])
    out = []
    for e in (memory or {}).get("entries", []):
        if e.get("kind") == KIND_STATS:
            e = dict(e, **{k: [e[k][int(pi[c])] for c in range(N_CELLS)] for k in STAT_KEYS},
                     **{k: [e[k][int(sigma[i])] for i in range(3)] for k in SIZE_KEYS})
        elif e.get("kind") == KIND_LIB:
            e = dict(e, blocks=[_random_block(b, rng2) for b in e["blocks"]])
        out.append(e)
    return mem(out)
