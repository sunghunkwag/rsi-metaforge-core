"""Design "v": a learner that searches, and acquires by racing ways to search (development; 2026-11-24).

Where designs a to s stand, a capability constructs an assignment once or twice and stops; what
is acquired is bounded by what the constructing policy can express. A first look
(``rsi6/results/design_t_20261124/README.md``, "What follows") found that spending the
evaluations a fresh problem allows on a plain search lifts the result far above that, and that
which move works depends on the kind.

**What a capability is.** A *search*: after a greedy construction it makes moves until the
meter of the problem ends. A move is one of a few generic operators, the arms: ``exchange`` the
options of two variables; ``shift`` one variable to another option; ``repair``: unassign
``size`` variables and assign them again one by one, each time the variable that would lose
most by waiting, by the exact changes the problem reports. The arms share the units of a search
by *credit*; credit follows what each arm gained per unit it cost (``search``).

**What a way to search is.** Six settings of that search, each one of three (``LEVELS``): which
sizes a repair has, how fast an arm's past is forgotten, how many open variables the
construction looks at, the share every arm keeps whatever its credit, when a move is accepted,
and which arms there are at all. 729 ways.

**What is acquired on a kind.** The way to search that does best on its training problems,
found by a *race* (``race``): some ways near the version's own are tried on a few problems, the
better part is kept and tried on more, and the winner has to beat the version's own way on
problems the race did not use. With it, the credit its searches ended on.

**What a version is.** Its own way to search (what it does on a kind it knows nothing about,
and where its races start), and the settings of its race (how many ways it enters, how far from
its own, how many it keeps, on how many problems at a time, how the winner is checked).

**How a version is modified.** By the same race, run by the version itself
(``rsi6/meta/chain_v.py``): over ways to search, on the training problems of all the kinds it
may use together; and over settings of the race, each tried by letting it acquire. The improver
is the procedure of acquisition, on the same kind of problem.

``install()`` makes the kernel's dispatch know the design (``designs.py`` is pinned).
"""
from __future__ import annotations

import hashlib
import json
import sys

import numpy as np

from rsi6.kernel.problem import BudgetExhausted

LEVELS = {"sizes": ((1, 2, 4), (2, 4, 8, 16), (4, 16, 64)), "decay": (0.7, 0.9, 0.98), "look": (1, 2, 4), "floor": (0.02, 0.05, 0.2),
          "accept": ("better", "not worse", "late"), "focus": ("all", "evaluate", "repair")}
MECH = {"sizes": 1, "decay": 1, "look": 0, "floor": 1, "accept": 1, "focus": 0}
RACE_LEVELS = {"width": (4, 8, 16), "reach": (1, 2, 3), "keep": (0.25, 0.5, 0.75), "batch": (1, 2, 4), "check": (0, 2, 4)}
RACE = {"width": 1, "reach": 0, "keep": 1, "batch": 1, "check": 1}
SLICE = 3.0                                    # of one construction: what a trial on a training problem may spend
START = 0.25                                   # of one construction: the units a starting credit is worth as evidence
LATE = 16                                      # moves back that "late" acceptance compares with
TINY = 1e-12


def default() -> dict:
    """Generation 0."""
    return {"design": "v", "mech": dict(MECH), "race": dict(RACE), "slice": SLICE}


def _levels_ok(values: dict, levels: dict) -> bool:
    return set(values) == set(levels) and all(isinstance(values[k], int) and 0 <= values[k] < len(levels[k]) for k in levels)


def validate(version: dict) -> dict:
    if version.get("design") != "v" or set(version) != {"design", "mech", "race", "slice"}:
        raise ValueError("not a version of design v")
    if not _levels_ok(version["mech"], LEVELS) or not _levels_ok(version["race"], RACE_LEVELS):
        raise ValueError("a setting is the index of one of its levels")
    if not 0.5 <= float(version["slice"]) <= 64.0:
        raise ValueError("slice out of range")
    return version


def digest(version: dict) -> str:
    return hashlib.sha256(json.dumps(validate(version), separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    out = {f"mech.{k}": {"from": a["mech"][k], "to": b["mech"][k], "function": "decide"} for k in LEVELS if a["mech"][k] != b["mech"][k]}
    out.update({f"race.{k}": {"from": a["race"][k], "to": b["race"][k], "function": "explore"} for k in RACE_LEVELS if a["race"][k] != b["race"][k]})
    return out


FIELDS = ("mech", "race", "slice")
SCHEMA = {**{f"mech.{k}": list(range(len(v))) for k, v in LEVELS.items()}, **{f"race.{k}": list(range(len(v))) for k, v in RACE_LEVELS.items()}}


def install() -> None:
    from rsi6.learner import designs
    if getattr(designs, "_v_installed", False):
        return
    make, module = designs.make, designs._module
    here = sys.modules[__name__]
    designs.make = lambda version: LearnerV(version) if version.get("design") == "v" else make(version)
    designs._module = lambda version: here if version.get("design") == "v" else module(version)
    designs._v_installed = True


def ways() -> list:
    """Every way to search, in a fixed order."""
    names = list(LEVELS)
    out = [{}]
    for name in names:
        out = [dict(w, **{name: i}) for w in out for i in range(len(LEVELS[name]))]
    return out


def arms_of(mech: dict) -> list:
    focus = LEVELS["focus"][mech["focus"]]
    arms = [] if focus == "repair" else [("exchange", 0), ("shift", 0)]
    if focus != "evaluate":
        arms += [("repair", int(r)) for r in LEVELS["sizes"][mech["sizes"]]]
    return arms


# ---- the search -----------------------------------------------------------------------------------
def cost(P, totals) -> tuple:
    """Hard totals first, then what the published objective sums."""
    soft = ~P.hard & ~P.detail
    return float(totals[P.hard].sum()), float(totals[soft].sum())


def improvement(old: tuple, new: tuple) -> float:
    """How much better ``new`` is: any progress on the hard totals counts above 1, progress on the objective as
    its share of the two values, anything else 0."""
    if new[0] < old[0]:
        return 1.0 + (old[0] - new[0]) / (abs(old[0]) + TINY)
    if new[0] > old[0]:
        return 0.0
    return max(0.0, (old[1] - new[1]) / (abs(old[1]) + abs(new[1]) + TINY))


def _key(P, rows):
    soft = ~P.hard & ~P.detail
    return rows[..., P.hard].sum(axis=-1) * 1e9 + rows[..., soft].sum(axis=-1) + rows[..., P.detail].sum(axis=-1) * 1e-3


def _fill(P, s, left, look=0):
    """Assign the variables in ``left`` one by one, each to its best option by the exact changes the problem
    reports. Of the first ``look`` variables still open (all of them when ``look`` is 0) the next is the one
    that would lose most by waiting; an ordered problem takes them in order. ``False`` when a variable is left
    without an option."""
    left = sorted(left) if P.ordered else list(left)
    while left:
        seen = left[:1] if P.ordered else (left if look == 0 else left[:look])
        rows = P.candidates(s, seen)
        k = _key(P, rows)
        ok = np.broadcast_to(P.allowed(s), k.shape).copy()
        if P.domain is not None:
            ok &= P.domain[seen]
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


def construct(P, look=1, rng=None):
    """A greedy construction. ``look`` 1: the variables in index order (one construction's units); more: in a
    random order, the one of the next ``look`` that would lose most by waiting first (``look`` times the units,
    and only when half of what the meter has left covers it)."""
    if look > 1 and not P.ordered and rng is not None and look * P.construction_units() <= 0.5 * P.meter.left():
        order = [int(v) for v in rng.permutation(P.n_vars)]
    else:
        order, look = list(range(P.n_vars)), 1
    s = P.start()
    if not _fill(P, s, order, look):
        return None, None
    return P.assignment(s), cost(P, P.totals(s))


def _guess(P, arm) -> float:
    """The units one move of an arm costs, before any has been made."""
    name, size = arm
    if name != "repair":
        return float(P.n_vars)
    r = min(int(size), P.n_vars)
    return float(P.n_vars + P.n_opts * (r if P.ordered else r * (r + 1) / 2.0))


def search(P, mech, rng, spend=None, start=None):
    """A greedy construction, then moves until ``spend`` units are used or the meter ends. Each arm has an
    estimate of what it gains per unit: its improvements over the units it used (older moves counting less),
    with the starting credit ``start`` counted as ``START`` constructions of evidence at the rate of all arms
    together. The units are shared by those estimates (every arm keeps a small share). Returns
    ``(best assignment or None, its cost, the shares the search ended on)``."""
    meter = P.meter
    until = meter.used + spend if spend is not None else float("inf")
    arms = arms_of(mech)
    n = len(arms)
    decay, floor, accept = LEVELS["decay"][mech["decay"]], LEVELS["floor"][mech["floor"]], LEVELS["accept"][mech["accept"]]
    share = np.ones(n) / n if start is None or len(start) != n else np.asarray(start, dtype=float) / np.sum(start)
    best = c_best = None
    try:
        best, c_best = construct(P, LEVELS["look"][mech["look"]], rng)
        if best is None:
            return None, None, share
        cur, c_cur = best, c_best
        past, turn = [c_best] * LATE, 0
        gained, used, typical = np.zeros(n), np.zeros(n), np.array([_guess(P, a) for a in arms])
        evidence, first = START * P.construction_units(), share.copy()
        while meter.used < until:
            rate = (gained.sum() + TINY) / (used.sum() + TINY)
            estimate = (evidence * first * n * rate + gained) / (evidence + used)
            share = estimate / estimate.sum()
            moves = (floor / n + (1.0 - floor) * share) / typical
            a = int(rng.choice(n, p=moves / moves.sum()))
            name, size = arms[a]
            before = meter.used
            b, c = cur.copy(), None
            if name == "exchange":
                i, j = rng.choice(P.n_vars, size=2, replace=False)
                b[i], b[j] = b[j], b[i]
                if cur[i] == cur[j] or not P.well_formed(b):
                    meter.charge(1)
                else:
                    c = cost(P, P.evaluate(b))
            elif name == "shift":
                i, o = int(rng.integers(P.n_vars)), int(rng.integers(P.n_opts))
                b[i] = o
                if o == cur[i] or not P.well_formed(b):
                    meter.charge(1)
                else:
                    c = cost(P, P.evaluate(b))
            else:
                if P.ordered:
                    out = set(range(max(P.n_vars - int(size), 0), P.n_vars))   # ordered problems: only a tail can be redone
                else:
                    out = set(int(v) for v in rng.choice(P.n_vars, size=min(int(size), P.n_vars), replace=False))
                s = P.start()
                for v in range(P.n_vars):
                    if v not in out:
                        P.assign(s, v, int(cur[v]))
                if _fill(P, s, sorted(out)):
                    b, c = P.assignment(s), cost(P, P.totals(s))
            spent = max(meter.used - before, 1.0)
            won = improvement(c_cur, c) if c is not None else 0.0
            if c is not None:
                if accept == "better":
                    take = c < c_cur
                elif accept == "not worse":
                    take = c <= c_cur
                else:
                    take = c <= c_cur or c <= past[turn % LATE]
                    past[turn % LATE] = c_cur
                    turn += 1
                if take:
                    cur, c_cur = b, c
                    if c < c_best:
                        best, c_best = b, c
            gained[a] = decay * gained[a] + won
            used[a] = decay * used[a] + spent
            typical[a] = 0.8 * typical[a] + 0.2 * spent
    except BudgetExhausted:
        pass
    return best, c_best, share


class LearnerV:
    def __init__(self, version: dict):
        self.v = validate(version)

    def acquire(self, problems, rng, memory=None):
        """For now: the version's own way to search, and the credit its searches on the training problems end
        on. (The race over ways to search is added after the tables of ``experiments/dev_ways.py`` are read.)"""
        memory = {"entries": list((memory or {}).get("entries", []))}
        if not problems or problems[0].kind != "assign":
            return None, memory, {"form": "predict", "failed": "design v acquires in the assignment form only", "learned": False, "iterations": 0}
        meter = problems[0].meter
        mech = dict(self.v["mech"])
        credit, trials, ends = None, 0, []
        try:
            while True:
                for j in rng.permutation(len(problems)):
                    P = problems[int(j)]
                    spend = self.v["slice"] * P.construction_units()
                    if meter.left() < spend:
                        raise BudgetExhausted()
                    _, _, end = search(P, mech, rng, spend, credit)
                    ends.append(end)
                    credit = np.mean(ends[-len(problems):], axis=0)           # what the last round of searches ended on
                    trials += 1
        except BudgetExhausted:
            pass
        capability = {"kind": "assign", "design": "v", "mech": mech, "credit": None if credit is None else [round(float(x), 6) for x in credit],
                      "learned": trials > 0}
        report = {"form": "assign", "iterations": trials, "failed": None, "learned": trials > 0, "mech": mech, "credit": capability["credit"]}
        return capability, memory, report

    def apply(self, capability, P, rng=None):
        """With a capability: its way to search, starting from the credit acquired on the kind. Without: the
        version's own way, from an even share."""
        rng = rng if rng is not None else np.random.default_rng(0)
        learned = bool(capability and capability.get("learned"))
        best, _, _ = search(P, capability["mech"] if learned else self.v["mech"], rng, None, capability["credit"] if learned else None)
        return best if best is not None else np.zeros(P.n_vars, dtype=np.int64)
