"""Design "q": the open design with the search for a representation inside acquisition.

What limited the open design (design "o", ``design_o.py``) in its registered experiment and in
its development runs: its acquisition learns only the constants ``theta`` of programs that are
fixed for the whole acquisition, by a learning principle that sees one scalar fitness per
candidate vector; the programs themselves, i.e. which sensors are read and how they are
combined, change only through discovery, which is slow and noisy because every step is judged
on fresh instances of other categories. So the representation could not adapt to the category
being learned, and an edit of the representation had to help across categories to be kept.

This design moves that search into acquisition. A mechanism of design q is a mechanism of
design o (the same programs, constants and learning principle, run by the same code) plus the
*inner* settings that govern a search over the score and pick programs during acquisition, on
the training problems of the category being learned:

``share``     the share of the rounds of acquisition that are program rounds (0 makes the
              design exactly design o: the same random streams, the same constructions, the same
              answers);
``variants``  how many edited programs a program round tries;
``edits``     the weights of one, two and three edits per variant;
``w``         a weight per inner edit cell (the edits of ``rsi6/open/edits.py`` on the score
              and pick programs and on the constants); variants draw their edits with
              probabilities ``softmax(w)``.

A program round takes the current programs with the current state of the learning principle
(its register 0) and ``variants`` edited copies, constructs with each on the round's batch of
training problems, and switches to the best copy when it beats the current programs strictly on
that batch (mean rank over the problems, as the learning principle's fitness). On a switch the
learning principle starts again, by its own ``init`` program, around the constants of the new
programs (an edit can add a constant). Every other round is a round of the learning principle,
exactly as in design o. A constant that an edit adds starts at a random value drawn from the
edit stream (in design o a growth edit adds a constant at the value that makes it a no-op, which
inside acquisition would make every growth variant tie with the current programs). At the end
the learner compares, on held-back training problems, the starting programs with the starting
constants, the current programs with the principle's state, and the programs and constants of
the best candidate of the last round, and keeps the best; on a tie it keeps the start.

The capability is the chosen constants and, when they differ from the mechanism's own, the
chosen programs: what was learned about a category includes its representation. At test time
the answer is a construction with those programs and constants followed by the first design's
local improvement, as in design o.

Compute: every construction is charged by the kernel's meter exactly as in design o (a program
round of ``variants`` copies costs ``variants + 1`` constructions per problem of the batch).
Compiling edited programs is CPU the meter does not count; the experiment compares at measured
CPU.

What is not open here either: the prediction form (the first design's predictor), the local
improvement at test time, the sensors and the instruction set.
"""
from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from rsi6.kernel.problem import BudgetExhausted
from rsi6.learner import design_o as O
from rsi6.learner.learner import _finish_arbitrarily, _key
from rsi6.open import edits as E

INNER_CELLS = [c for c in E.CELLS if c[0] in ("score", "pick") and c[1] != "splice"] + [("theta", "perturb"), ("theta", "grow")]
SHARES = (0.0, 0.25, 0.5, 0.75)
VARIANTS = (2, 4, 6, 8, 12, 16)
O_KEYS = ("design", "score", "pick", "theta", "init", "propose", "update", "pop", "batch", "shortlist", "holdback", "select")


def o_part(version: dict) -> dict:
    """The design-o mechanism inside a design-q mechanism."""
    out = {k: copy.deepcopy(version[k]) for k in O_KEYS if k != "design"}
    out["design"] = "o"
    return out


def default() -> dict:
    """Generation 0 of design q: generation 0 of design o, with half of the rounds program rounds
    of eight variants, mostly single edits, and no preference among the inner edit cells."""
    out = O.default()
    out["design"] = "q"
    out["inner"] = {"share": 0.5, "variants": 8, "edits": [0.6, 0.3, 0.1], "w": [0.0] * len(INNER_CELLS)}
    return out


def validate(version: dict) -> dict:
    keys = set(O_KEYS) | {"inner"}
    if set(version) != keys or version.get("design") != "q":
        raise ValueError(f"a version of design q has exactly the parts {sorted(keys)}")
    out = O.validate(o_part(version))
    out["design"] = "q"
    inner = version["inner"]
    if set(inner) != {"share", "variants", "edits", "w"}:
        raise ValueError("inner: share, variants, edits, w")
    share, variants = float(inner["share"]), int(inner["variants"])
    if share not in SHARES or variants not in VARIANTS:
        raise ValueError(f"inner: share one of {SHARES}, variants one of {VARIANTS}")
    ed = [float(x) for x in inner["edits"]]
    if len(ed) != 3 or min(ed) < 0 or sum(ed) <= 0 or not all(np.isfinite(ed)):
        raise ValueError("inner: edits are three weights, not negative, not all zero")
    w = [float(x) for x in inner["w"]]
    if len(w) != len(INNER_CELLS) or not all(np.isfinite(w)) or max(abs(x) for x in w) > 8.0:
        raise ValueError(f"inner: w holds {len(INNER_CELLS)} finite weights of size at most 8")
    total = sum(ed)
    out["inner"] = {"share": share, "variants": variants, "edits": [round(x / total, 6) for x in ed], "w": [round(x, 6) for x in w]}
    return out


def digest(version: dict) -> str:
    return hashlib.sha256(json.dumps(validate(version), separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    out = O.differences(o_part(a), o_part(b))
    for k in ("share", "variants", "edits", "w"):
        if a["inner"][k] != b["inner"][k]:
            out[f"inner.{k}"] = {"from": a["inner"][k] if k != "w" else "weights", "to": b["inner"][k] if k != "w" else "weights",
                                 "function": "explore"}
    return out


SCHEMA = {}


def softmax(x):
    z = np.exp(np.asarray(x, float) - np.max(x))
    return z / z.sum()


def program_rounds(iteration: int, share: float) -> bool:
    """Whether round ``iteration`` (0, 1, ...) is a program round: spread evenly at the share."""
    return share > 0 and int(np.floor((iteration + 1) * share + 1e-9)) > int(np.floor(iteration * share + 1e-9))


class LearnerQ(O.OpenLearner):
    """The learner of design q. ``self.g`` is the design-o part (its programs are the starting
    programs of every acquisition), ``self.inner`` the inner settings."""

    def __init__(self, version: dict):
        full = validate(version)
        super().__init__(o_part(full))
        self.inner = full["inner"]
        self._sensor_cache = {}

    # ---- constructions with given programs --------------------------------------------------
    def _genome(self, prog) -> dict:
        return dict(self.g, score=prog["score"], pick=prog["pick"])

    def _sensors(self, P, prog, index):
        key = (index, json.dumps(O.live(prog["score"])), json.dumps(O.live(prog["pick"])))
        if key not in self._sensor_cache:
            self._sensor_cache[key] = O.Sensors(P, self._genome(prog))
        return self._sensor_cache[key]

    def _rollouts_q(self, problems, indices, cands, rng, meter):
        need = sum(self._cost(P, self.g["shortlist"]) for P in problems) * len(cands)
        if meter.left() < need:
            return None
        keys = np.zeros((len(cands), len(problems), 2))
        for c, (prog, theta) in enumerate(cands):
            compiled = (O.compile_vector_program(prog["score"], theta), O.compile_vector_program(prog["pick"], theta, O.N_PREG))
            genome = self._genome(prog)
            for i, (P, index) in enumerate(zip(problems, indices)):
                try:
                    totals, _ = O.construct(P, self._sensors(P, prog, index), genome, theta, rng, self.g["shortlist"], compiled=compiled)
                    keys[c, i] = _key(totals, P)
                except O.Infeasible:
                    keys[c, i] = (np.inf, np.inf)
        return keys

    # ---- the inner edits ----------------------------------------------------------------------
    def _variant(self, prog, theta, rng):
        """An edited copy of ``prog`` with ``theta``: one to three edits drawn by the inner prior.
        A constant an edit adds starts at a random value of the edit stream."""
        p = softmax(self.inner["w"])
        ed = np.asarray(self.inner["edits"], float)
        n = 1 + int(rng.choice(3, p=ed / ed.sum()))
        g = dict(self.g, score=copy.deepcopy(prog["score"]), pick=copy.deepcopy(prog["pick"]),
                 theta=[float(np.clip(x, -100.0, 100.0)) for x in theta])
        done = 0
        for _ in range(n):
            for _ in range(12):
                cell = INNER_CELLS[int(rng.choice(len(INNER_CELLS), p=p))]
                new, info = E.apply_edit(g, cell, [], rng)
                if new is None:
                    continue
                if len(new["theta"]) > len(g["theta"]):          # a new constant: a random start, not a no-op
                    base = 1.0 if (info.get("block") and info["block"][-1][0] == "scale" and cell[0] == "theta") else 0.0
                    new["theta"][-1] = round(float(np.clip(base + rng.normal(0.0, 1.0), -50.0, 50.0)), 6)
                g = new
                done += 1
                break
        if done == 0:
            return None
        return {"score": g["score"], "pick": g["pick"]}, np.array(g["theta"], dtype=float)

    # ---- acquisition ---------------------------------------------------------------------------
    def _acquire_open(self, problems, rng):
        g, inner = self.g, self.inner
        meter = problems[0].meter
        n = len(problems)
        rng_order, rng_acq, rng_con = (np.random.default_rng(int(x)) for x in rng.integers(0, 2 ** 63, size=3))
        rng_edit = np.random.default_rng(int(rng.integers(0, 2 ** 63)))   # drawn after design o's three: those stay as they were
        order = rng_order.permutation(n)
        n_check = (min(max(1, int(round(g["holdback"] * n))), n - 1) if n > 1 else 0) if g["select"] == "best_of_3" else 0
        check, fit = order[:n_check], order[n_check:]
        start = np.array(g["theta"], dtype=float)
        start_prog = {"score": g["score"], "pick": g["pick"]}
        prog = start_prog
        report = {"form": "assign", "design": "q", "fit": len(fit), "held_back": len(check), "iterations": 0,
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
                if program_rounds(it, inner["share"]):
                    if meter.left() - reserve < (inner["variants"] + 1) * fit_cost[chosen].sum():
                        break
                    here = acq.A[0].copy()
                    variants = [self._variant(prog, here, rng_edit) for _ in range(inner["variants"])]
                    cands = [(prog, here)] + [v for v in variants if v is not None]
                    keys = self._rollouts_q([problems[i] for i in idx], idx, cands, rng_con, meter)
                    if keys is None:
                        break
                    F = O._fitness(keys)
                    best = int(np.argmax(F))
                    if best > 0 and F[best] > F[0]:
                        prog, theta = cands[best]
                        acq = O.Acquirer(g, theta, rng_acq)          # the principle starts again around the new constants
                        last_best = (prog, theta.copy())
                        report["switches"] += 1
                    report["program_rounds"] += 1
                    report["constructions"] += len(cands) * batch
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
        except BudgetExhausted:
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
            except BudgetExhausted:
                report["failed"] = "decide: the budget ended inside the held-back check"
        report["learned"] = learned
        capability = {"kind": "open", "theta": [float(x) for x in chosen_theta], "learned": learned}
        if chosen_prog is not start_prog and (chosen_prog["score"] != start_prog["score"] or chosen_prog["pick"] != start_prog["pick"]):
            capability["program"] = {"score": chosen_prog["score"], "pick": chosen_prog["pick"]}
            report["program_size"] = [len(O.live(chosen_prog["score"])), len(O.live(chosen_prog["pick"]))]
        return capability, report

    def _apply_open(self, capability, P, rng):
        if not (capability and capability.get("kind") == "open" and capability.get("program")):
            return super()._apply_open(capability, P, rng)
        if P.start_answer is not None:
            return super()._apply_open(capability, P, rng)
        prog = capability["program"]
        genome = self._genome(prog)
        theta = np.array(capability["theta"], dtype=float)
        shortlist = self.g["shortlist"]
        if not P.ordered:
            while shortlist > 1 and self._cost(P, shortlist) > P.meter.left():
                shortlist //= 2
        hold = []
        try:
            totals, answer = O.construct(P, O.Sensors(P, genome), genome, theta, rng, shortlist, hold=hold)
        except (BudgetExhausted, O.Infeasible):
            try:
                return _finish_arbitrarily(P, hold[0] if hold else None)
            except IndexError:
                return np.zeros(P.n_vars, dtype=np.int64)
        return self._improve(None, P, rng, answer, _key(totals, P))
