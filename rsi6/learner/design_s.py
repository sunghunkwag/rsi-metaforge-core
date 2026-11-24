"""Design "s": one search procedure, used at two levels.

What the first design could not show, and why (``rsi6/results/dev_landscape_20261122/G1.md``,
``rsi6/results/dev_recursion_20261122/``): its learner acquires by a search over the weights of
a policy, but as an improver of versions it only edits a known version with its ``edit.*``
fields. A change of how it acquires therefore leaves the improver exactly as it was, and the
second half of the hypothesis has nothing to act on. And a setting that helps one category
hurts another: what is left to gain needs a procedure that adapts inside an acquisition, not
another value of a field.

This design changes two things and nothing else.

* **The search is one function** (``search`` below), written against a *task*: a starting
  point, a number of training problems, the cost of one evaluation on each, and the evaluation
  of a set of candidate points on some of the problems. The learner's acquisition calls it on
  the weights of its policy (``LearnerS._acquire_assign``); the improver calls the same function
  on the space of versions (``rsi6/meta/chain_s.py``), with the fields of the version that is
  doing the improving. With the two new fields at their defaults the function is the first
  design's acquisition, operation for operation and random draw for random draw
  (``rsi6/tests/test_design_s.py`` compares them run by run).

* **Two procedures that adapt inside one search**, each a field with the first design's
  behaviour as its default:

  ``adapt.spread``  ``"schedule"``: the spread of the candidates follows ``model.sigma`` and
                    ``model.decay`` only. ``"self"``: every candidate draws its own multiplier
                    of the spread, ``exp(TAU * z)`` with ``z`` standard normal, and after a round
                    the spread is multiplied by the geometric mean of the multipliers of the
                    candidates that were kept (then by ``model.decay`` as before). If small
                    steps win on this category the spread shrinks, if large ones win it grows.
  ``adapt.race``    ``0``: every candidate of a round is evaluated on every problem of the
                    round's batch. ``1``: the candidates are evaluated on the problems one at
                    a time and after each problem the worse half is dropped (never below the
                    number that is kept at the end), so how many evaluations a candidate gets
                    depends on how it is doing, and the round costs less.

Neither procedure is known to help. They are generic steps of a population search; whether a
version that uses them acquires more, and whether it is a better improver, is what is measured.

A version of this design is a version of the first design (its 38 fields, with
``model.variant`` ``"cem"``) plus the two fields above and ``design: "s"``.

``rsi6/learner/designs.py`` is pinned by hash by earlier registrations and does not name this
design. A driver that measures it calls ``install()`` first, as the drivers of designs q and r
call ``dispatch_extra.install()``.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import sys

import numpy as np

from rsi6.kernel.problem import BudgetExhausted
from rsi6.learner import version as A
from rsi6.learner.learner import Layout, Learner

SPREADS = ("schedule", "self")
TAU = 0.7                                               # spread of the log-multipliers under adapt.spread "self"
EXTRA = {"adapt.spread": ("choice", SPREADS, "schedule"), "adapt.race": ("choice", (0, 1), 0)}
SCHEMA = dict(A.SCHEMA, **EXTRA)
FIELDS = tuple(SCHEMA)
FUNCTION_OF = dict(A.FUNCTION_OF, adapt="explore")

# The list of mechanisms a chain of this design moves in: every combination of these values of the
# six fields the search reads, every other field as in generation 0 of the first design.
LEVELS = {
    "model.batch": (2, 4, 8),
    "model.pop": (8, 16, 32),
    "model.elite": (0.1, 0.25, 0.5),
    "model.sigma": (0.2, 1.0, 2.0),
    "adapt.spread": SPREADS,
    "adapt.race": (0, 1),
}
MECHANISM = tuple(LEVELS)


def default() -> dict:
    """Generation 0 of the first design, in this design: both new procedures off."""
    version = {name: spec[-1] for name, spec in SCHEMA.items()}
    version["design"] = "s"
    return version


def a_part(version: dict) -> dict:
    """The first design's record inside a version of this design."""
    return {name: version[name] for name in A.FIELDS}


def validate(version: dict) -> dict:
    if version.get("design") != "s":
        raise ValueError("not a version of design s")
    if set(version) != set(SCHEMA) | {"design"}:
        raise ValueError(f"version fields differ from the schema: {sorted(set(version) ^ (set(SCHEMA) | {'design'}))}")
    out = A.validate(a_part(version))
    if out["model.variant"] != "cem":
        raise ValueError("design s has one search procedure: model.variant must be 'cem'")
    for name, spec in EXTRA.items():
        if version[name] not in spec[1]:
            raise ValueError(f"{name}={version[name]!r} not one of {spec[1]}")
        out[name] = version[name]
    out["design"] = "s"
    return out


def digest(version: dict) -> str:
    text = json.dumps(validate(version), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def differences(a: dict, b: dict) -> dict:
    return {name: {"from": a[name], "to": b[name], "function": FUNCTION_OF[name.split(".")[0]]}
            for name in FIELDS if a[name] != b[name]}


def mechanisms() -> list:
    """The list, in a fixed order: index ``k`` of field ``f`` moves slowest for the first field."""
    out = []
    for values in itertools.product(*(LEVELS[f] for f in MECHANISM)):
        out.append(validate(dict(default(), **dict(zip(MECHANISM, values)))))
    return out


def index_of(version: dict) -> tuple:
    """The position of a version in the list, as one index per mechanism field."""
    return tuple(LEVELS[f].index(version[f]) for f in MECHANISM)


def behaviour(version: dict) -> tuple:
    """What a search under this version does: two versions with the same value here run the same
    acquisition (``model.elite`` enters only through the number of candidates kept)."""
    pop = int(version["model.pop"])
    return (int(version["model.batch"]), pop, max(2, int(round(version["model.elite"] * pop))), float(version["model.sigma"]),
            version["adapt.spread"], int(version["adapt.race"]))


def install() -> None:
    """Make the kernel's dispatch know design s in this process (and the workers it forks)."""
    from rsi6.learner import designs
    if getattr(designs, "_s_installed", False):
        return
    make, module = designs.make, designs._module
    here = sys.modules[__name__]

    def make_s(version):
        return LearnerS(version) if version.get("design") == "s" else make(version)

    def module_s(version):
        return here if version.get("design") == "s" else module(version)

    designs.make = make_s
    designs._module = module_s
    designs._s_installed = True


# ---- the search ---------------------------------------------------------------------------------
def race_plan(pop: int, n_elite: int, batch: int) -> list:
    """How many candidates are evaluated on each problem of a round under ``adapt.race``."""
    plan, k = [], pop
    for _ in range(batch):
        plan.append(k)
        k = max(n_elite, (k + 1) // 2)
    return plan


def search(task, v: dict, rng, report: dict):
    """The acquisition of the first design as a procedure on a task, with the two adaptive steps.

    ``task`` has ``n`` (training problems), ``dim``, ``start`` (a point), ``cost(i)`` (units one
    evaluation of one candidate on problem ``i`` costs), ``left()`` (units left), ``project(points)``
    (the points the candidates stand for: themselves, or the nearest points of a grid) and
    ``evaluate(points, problems, rng)``, which returns the keys ``(hard, soft)`` of every point on
    every problem, lower is better, or ``None`` if the budget does not allow it.

    Returns ``(point, learned)``: the point the search ends on if it beat the start on the
    held-back problems (or if ``assess.strict`` is off), otherwise the start.
    """
    fitness = Learner._fitness
    n = task.n
    order = rng.permutation(n)
    n_check = min(max(1, int(round(v["assess.holdback"] * n))), n - 1) if n > 1 else 0
    check, fit = order[:n_check], order[n_check:]
    report.update({"fit": len(fit), "held_back": len(check), "iterations": 0, "constructions": 0, "failed": None})
    start = task.start
    check_cost = sum(task.cost(i) for i in check)
    reserve = 3.0 * check_cost
    d = task.dim
    mu, sigma = start.copy(), np.full(d, float(v["model.sigma"]))
    pop, batch = int(v["model.pop"]), min(int(v["model.batch"]), len(fit))
    n_elite = max(2, int(round(v["model.elite"] * pop)))
    self_adapt, race = v.get("adapt.spread", "schedule") == "self", bool(v.get("adapt.race", 0))
    plan = race_plan(pop, n_elite, batch) if race else None
    best, spreads = start.copy(), []
    fit_cost = np.array([task.cost(i) for i in fit])
    try:
        while d > 0 and len(fit) > 0:
            chosen = rng.choice(len(fit), size=batch, replace=False)
            need = float(np.dot(plan, fit_cost[chosen])) if race else pop * fit_cost[chosen].sum()
            if task.left() - reserve < need:
                break
            noise = rng.standard_normal((pop, d))
            if self_adapt:
                z = rng.standard_normal(pop)
                if v["model.keep_best"]:
                    z[0] = 0.0
                cands = mu + sigma * np.exp(TAU * z)[:, None] * noise
            else:
                cands = mu + sigma * noise
            if v["model.keep_best"]:
                cands[0] = mu
            cands = task.project(cands)
            problems = [fit[i] for i in chosen]
            if race:
                alive, keys = np.arange(pop), np.zeros((pop, 0, 2))
                for j, problem in enumerate(problems):
                    alive, keys = alive[:plan[j]], keys[:plan[j]]
                    new = task.evaluate(cands[alive], [problem], rng)
                    if new is None:
                        keys = None
                        break
                    keys = np.concatenate([keys, new], axis=1)
                    report["constructions"] += len(alive)
                    rank = np.argsort(-fitness(keys), kind="stable")           # best first, on the problems seen so far
                    alive, keys = alive[rank], keys[rank]
                if keys is None:
                    break
                top = alive[:n_elite]
            else:
                keys = task.evaluate(cands, problems, rng)
                if keys is None:
                    break
                top = np.argsort(-fitness(keys), kind="stable")[:n_elite]
                report["constructions"] += len(cands) * len(problems)
            mu = cands[top].mean(axis=0)
            if self_adapt:
                sigma = sigma * float(np.exp(TAU * z[top].mean()))
            sigma = np.maximum(sigma * v["model.decay"], 0.02)
            report["iterations"] += 1
            spreads.append(float(sigma.mean()))
            best = mu.copy()
    except BudgetExhausted:
        report["failed"] = "decide: the budget ended inside a construction"
    if self_adapt:
        report["spread"] = [round(x, 4) for x in spreads]
    # self-assessment on the held-back problems: where the search ended against where it started
    chosen_point, learned = start, False
    best = task.project(best[None, :])[0]
    if report["iterations"] == 0:
        report["failed"] = report["failed"] or "decide: the budget did not allow one round of learning"
    elif n_check == 0:
        chosen_point, learned = best, True
    else:
        try:
            keys = task.evaluate(np.stack([start, best]), list(check), rng)
            if keys is None:
                report["failed"] = "decide: no budget left for the held-back check"
            else:
                f = fitness(keys)
                report["held_back_start"] = keys[0].mean(axis=0).tolist()
                report["held_back_learned"] = keys[1].mean(axis=0).tolist()
                if f[1] > f[0] or not v["assess.strict"]:
                    chosen_point, learned = best, True
                else:
                    report["failed"] = ("model: the learned weights did not beat the starting weights on the "
                                        "held-back problems")
        except BudgetExhausted:
            report["failed"] = "decide: the budget ended inside the held-back check"
    report["learned"] = learned
    return chosen_point, learned


class _WeightTask:
    """The learner's own task: the weights of its policy on the training problems of one category."""

    def __init__(self, learner, problems, layouts, start, shortlist):
        self.learner, self.problems, self.layouts, self.shortlist = learner, problems, layouts, shortlist
        self.meter = problems[0].meter
        self.n, self.dim, self.start = len(problems), layouts[0].size, start

    def cost(self, i) -> float:
        return self.learner._cost(self.problems[i], self.shortlist)

    def left(self) -> float:
        return self.meter.left()

    @staticmethod
    def project(points):
        return points

    def evaluate(self, points, problems, rng):
        return self.learner._rollouts([self.problems[i] for i in problems], [self.layouts[i] for i in problems], points, rng,
                                      self.shortlist, self.meter)


class LearnerS(Learner):
    """The first design's learner with its acquisition of the assignment form run by ``search``."""

    def __init__(self, version: dict):
        self.v = validate(version)
        self.trace = {}

    def _acquire_assign(self, problems, rng, memory):
        v = self.v
        layouts = [Layout(P, v) for P in problems]
        lay0 = layouts[0]
        start = lay0.prior(v)
        recalled = self._recall(problems[0], memory) if (v["transfer.on"] and memory.get("entries")) else None
        if recalled is not None:
            start = (1.0 - v["transfer.blend"]) * start + v["transfer.blend"] * lay0.vector(recalled)
        report = {"form": "assign", "descriptors": lay0.names, "fit": 0, "held_back": 0, "iterations": 0, "constructions": 0,
                  "transferred": recalled is not None, "failed": None}
        task = _WeightTask(self, problems, layouts, start, int(v["shortlist"]))
        theta, learned = search(task, v, rng, report)
        capability = {"kind": "assign", "weights": lay0.weights(theta), "learned": learned}
        return capability, report
