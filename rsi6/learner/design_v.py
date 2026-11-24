"""Design "v": a learner that searches (first sketch, development; 2026-11-25).

Where designs a to s stand, a capability constructs an assignment once or twice and stops; what
is acquired is bounded by what the constructing policy can express. A first look
(``rsi6/results/design_t_20261124/README.md``, "What follows") found that spending the
evaluations a fresh problem allows on a plain search lifts the result far above that, and that
which move works depends on the kind.

A capability of design v is therefore a *search*: after a greedy construction it makes moves
until the meter of the problem ends, keeping an assignment when it is not worse. A move is one
of a few generic operators (``exchange`` the options of two variables; ``shift`` one variable
to another option; ``repair``: unassign ``size`` variables and assign them again one by one,
each time the variable that would lose most by waiting, by the exact changes the problem
reports). What is acquired on a kind is which operators to use there: every arm is tried on the
training problems under the share of the budget one fresh problem gets, the worse half is
dropped, and so on (``acquire``).

This file is a sketch for development measurements: it has no version space yet and its only
setting is the list of arms. ``install()`` makes the kernel's dispatch know it.
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np

from rsi6.kernel.problem import BudgetExhausted

ARMS = (("exchange", 0), ("shift", 0), ("repair", 2), ("repair", 4), ("repair", 8), ("repair", 16))
SLICE = 3.0                                    # of one construction: what a trial on a training problem may spend


def default() -> dict:
    return {"design": "v", "arms": [list(a) for a in ARMS], "slice": SLICE}


def validate(version: dict) -> dict:
    if version.get("design") != "v" or set(version) != {"design", "arms", "slice"} or not version["arms"]:
        raise ValueError("not a version of design v")
    for name, size in version["arms"]:
        if name not in ("exchange", "shift", "repair") or not 0 <= int(size) <= 64:
            raise ValueError("unknown arm")
    return version


def digest(version: dict) -> str:
    return hashlib.sha256(json.dumps(validate(version), separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    return {} if a == b else {"arms": {"from": a["arms"], "to": b["arms"], "function": "decide"}}


FIELDS = ("arms", "slice")
SCHEMA = {}


def install() -> None:
    from rsi6.learner import designs
    if getattr(designs, "_v_installed", False):
        return
    make, module = designs.make, designs._module
    here = sys.modules[__name__]
    designs.make = lambda version: LearnerV(version) if version.get("design") == "v" else make(version)
    designs._module = lambda version: here if version.get("design") == "v" else module(version)
    designs._v_installed = True


def cost(P, totals) -> tuple:
    """Hard totals first, then what the published objective sums."""
    soft = ~P.hard & ~P.detail
    return float(totals[P.hard].sum()), float(totals[soft].sum())


def _key(P, rows):
    soft = ~P.hard & ~P.detail
    return rows[..., P.hard].sum(axis=-1) * 1e9 + rows[..., soft].sum(axis=-1) + rows[..., P.detail].sum(axis=-1) * 1e-3


def _fill(P, s, left, regret=True):
    """Assign the variables in ``left`` one by one, each to its best option by the exact changes the problem
    reports. With ``regret`` (and free order) the next variable is the one that would lose most by waiting,
    which looks at every open variable each time; without, the variables are taken in the order given, which
    costs one construction for all of them. ``False`` when a variable is left without an option."""
    left = sorted(left) if P.ordered else list(left)
    while left:
        look = left if regret and not P.ordered else left[:1]
        rows = P.candidates(s, look)
        k = _key(P, rows)
        ok = np.broadcast_to(P.allowed(s), k.shape).copy()
        if P.domain is not None:
            ok &= P.domain[look]
        k = np.where(ok, k, np.inf)
        if not np.isfinite(k).any(axis=1).all():
            return False
        if len(k) > 1 and k.shape[1] > 1:
            two = np.partition(k, 1, axis=1)[:, :2]
            i = int(np.argmax(np.where(np.isfinite(two[:, 1]), two[:, 1] - two[:, 0], np.inf)))
        else:
            i = 0
        P.assign(s, left[i], int(np.argmin(k[i])))
        left.pop(i)
    return True


def construct(P):
    s = P.start()
    if not _fill(P, s, range(P.n_vars), regret=False):
        return None, None
    return P.assignment(s), cost(P, P.totals(s))


def search(P, arms, rng, spend=None):
    """A greedy construction, then moves of the given arms (drawn evenly) until ``spend`` units are used or the
    meter ends. Returns ``(assignment or None, cost)``."""
    meter = P.meter
    until = meter.used + spend if spend is not None else float("inf")
    best = c_best = None
    try:
        best, c_best = construct(P)
        if best is None:
            return None, None
        while arms and meter.used < until:
            name, size = arms[int(rng.integers(len(arms)))]
            b = best.copy()
            if name == "exchange":
                i, j = rng.choice(P.n_vars, size=2, replace=False)
                if b[i] == b[j]:
                    meter.charge(1)
                    continue
                b[i], b[j] = b[j], b[i]
                if not P.well_formed(b):
                    meter.charge(1)
                    continue
                c = cost(P, P.evaluate(b))
            elif name == "shift":
                i, o = int(rng.integers(P.n_vars)), int(rng.integers(P.n_opts))
                b[i] = o
                if o == best[i] or not P.well_formed(b):
                    meter.charge(1)
                    continue
                c = cost(P, P.evaluate(b))
            else:
                if P.ordered:
                    out = set(range(max(P.n_vars - int(size), 0), P.n_vars))   # ordered problems: only a tail can be redone
                else:
                    out = set(int(v) for v in rng.choice(P.n_vars, size=min(int(size), P.n_vars), replace=False))
                s = P.start()
                for v in range(P.n_vars):
                    if v not in out:
                        P.assign(s, v, int(best[v]))
                if not _fill(P, s, sorted(out)):
                    continue
                b, c = P.assignment(s), cost(P, P.totals(s))
            if c <= c_best:
                best, c_best = b, c
    except BudgetExhausted:
        pass
    return best, c_best


class LearnerV:
    def __init__(self, version: dict):
        self.v = validate(version)

    def acquire(self, problems, rng, memory=None):
        memory = {"entries": list((memory or {}).get("entries", []))}
        if not problems or problems[0].kind != "assign":
            return None, memory, {"form": "predict", "failed": "design v acquires in the assignment form only", "learned": False, "iterations": 0}
        meter = problems[0].meter
        arms = [tuple(a) for a in self.v["arms"]]
        alive, scores, trials = list(range(len(arms))), {i: [] for i in range(len(arms))}, 0
        order = [int(i) for i in rng.permutation(len(problems))]
        at = 0
        try:
            while len(alive) > 1:
                batch = [order[(at + k) % len(order)] for k in range(2)]
                at += 2
                for j in batch:
                    P = problems[j]
                    spend = self.v["slice"] * P.construction_units()
                    row = {}
                    for i in alive:
                        if meter.left() < spend:
                            raise BudgetExhausted()
                        _, c = search(P, [arms[i]], rng, spend)
                        row[i] = c if c is not None else (float("inf"), float("inf"))
                        trials += 1
                    ranked = sorted(row, key=lambda i: row[i])
                    for place, i in enumerate(ranked):
                        scores[i].append(place / max(len(ranked) - 1, 1))
                alive = sorted(alive, key=lambda i: np.mean(scores[i][-2:]))[:max(1, (len(alive) + 1) // 2)]
        except BudgetExhausted:
            pass
        best = min(alive, key=lambda i: np.mean(scores[i]) if scores[i] else 1.0)
        tried = [i for i in range(len(arms)) if scores[i]]
        capability = {"kind": "assign", "design": "v", "arms": [list(arms[best])], "learned": bool(tried)}
        report = {"form": "assign", "iterations": trials, "failed": None, "learned": bool(tried), "arm": list(arms[best]),
                  "mean_place": {str(list(arms[i])): round(float(np.mean(scores[i])), 4) for i in tried}}
        return capability, memory, report

    def apply(self, capability, P, rng=None):
        rng = rng if rng is not None else np.random.default_rng(0)
        arms = [tuple(a) for a in capability["arms"]] if capability and capability.get("learned") else []
        best, _ = search(P, arms, rng)
        return best if best is not None else np.zeros(P.n_vars, dtype=np.int64)
