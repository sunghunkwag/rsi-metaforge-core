"""Tests of design v (the learner that searches) that need no published data.

    python -m rsi6.tests.test_design_v
"""
from __future__ import annotations

import sys

import numpy as np

from rsi6.kernel.problem import AssignProblem, BudgetExhausted, Meter, view
from rsi6.learner import design_v as V


class Toy(AssignProblem):
    """Variables take options at a cost per pair; pairs of variables on one option cost extra; one hard group
    counts variables on option 0 beyond two."""

    def __init__(self, n, m, rng, capacity=None, ordered=False):
        self.w = rng.uniform(0.0, 1.0, size=(n, m))
        self.q = rng.uniform(0.0, 0.3, size=(n, n))
        self.q = (self.q + self.q.T) / 2.0
        super().__init__(n, m, hard=[False, True], ordered=ordered, capacity=capacity, var_opt=(self.w,), var_var=(self.q,))

    def partial_totals(self, a):
        on = a >= 0
        soft = float(self.w[np.flatnonzero(on), a[on]].sum())
        same = (a[:, None] == a[None, :]) & on[:, None] & on[None, :]
        soft += float(np.triu(self.q * same, 1).sum())
        return np.array([soft, float(max(int((a == 0).sum()) - 2, 0))])


def _toy(seed, n=14, m=5, capacity=None, ordered=False, limit=float("inf")):
    P = Toy(n, m, np.random.default_rng(seed), capacity, ordered)
    P.meter = Meter(limit)
    return P


def test_versions_and_ways():
    v = V.default()
    assert V.validate(v) == v and len(V.digest(v)) == 64 and V.differences(v, v) == {}
    ways = V.ways()
    assert len(ways) == 729 and len({tuple(sorted(w.items())) for w in ways}) == 729 and V.MECH in ways
    w = dict(v, mech=dict(v["mech"], focus=1), race=dict(v["race"], width=2))
    assert set(V.differences(v, w)) == {"mech.focus", "race.width"} and V.digest(w) != V.digest(v)
    for wrong in (dict(v, mech=dict(v["mech"], focus=3)), dict(v, extra=1), dict(v, slice=0.1), dict(v, race={})):
        try:
            V.validate(wrong)
        except ValueError:
            continue
        raise AssertionError("a wrong version was accepted")
    assert V.arms_of(dict(V.MECH, focus=1)) == [("exchange", 0), ("shift", 0)]
    assert all(name == "repair" for name, _ in V.arms_of(dict(V.MECH, focus=2)))


def test_search_stays_inside_the_meter_and_improves():
    for accept in range(3):
        for focus in range(3):
            for capacity, ordered in ((None, False), (np.full(5, 3), False), (None, True)):
                mech = dict(V.MECH, accept=accept, focus=focus, look=accept)
                P = _toy(3, capacity=capacity, ordered=ordered)
                P.meter = Meter(6.0 * P.construction_units())
                best, c, share = V.search(view(P), mech, np.random.default_rng(1))
                assert best is not None and P.well_formed(best) and P.meter.used <= P.meter.limit + P.n_vars * (P.n_opts + 1) * 9, (accept, focus)
                Q = _toy(3, capacity=capacity, ordered=ordered)
                first, c0 = V.construct(view(Q), 1)
                assert c <= c0 and abs(share.sum() - 1.0) < 1e-9 and V.cost(Q, Q.partial_totals(best)) == c
    P = _toy(4)
    P.meter = Meter(0.5 * P.construction_units())                    # not even one construction
    assert V.search(view(P), V.MECH, np.random.default_rng(1))[0] is None
    a = V.search(view(_toy(5, limit=4000.0)), V.MECH, np.random.default_rng(7))
    b = V.search(view(_toy(5, limit=4000.0)), V.MECH, np.random.default_rng(7))
    assert np.array_equal(a[0], b[0]) and a[1] == b[1]                # the same seeds, the same search


def test_improvement():
    assert V.improvement((0.0, 10.0), (0.0, 5.0)) > V.improvement((0.0, 10.0), (0.0, 9.0)) > 0.0
    assert V.improvement((2.0, 10.0), (1.0, 50.0)) > 1.0 and V.improvement((0.0, 10.0), (1.0, 1.0)) == 0.0
    assert V.improvement((0.0, 10.0), (0.0, 10.0)) == 0.0 and V.improvement((0.0, -4.0), (0.0, -5.0)) > 0.0


def test_learner():
    meter = Meter(0.0)
    problems = []
    for seed in range(6):
        P = _toy(10 + seed)
        P.meter = meter
        problems.append(view(P))
    meter.limit = 40.0 * sum(P.construction_units() for P in problems)
    learner = V.LearnerV(V.default())
    capability, memory, report = learner.acquire(problems, np.random.default_rng(2))
    assert memory == {"entries": []} and capability["learned"] and report["iterations"] > 6 and meter.used <= meter.limit
    assert abs(sum(capability["credit"]) - 1.0) < 1e-4 and capability["mech"] == V.MECH
    for cap in (capability, None):
        P = _toy(99)
        P.meter = Meter(2.0 * P.construction_units() + P.n_vars * P.n_vars)
        answer = learner.apply(cap, view(P), np.random.default_rng(3))
        assert answer.dtype.kind in "iu" and P.well_formed(answer)
    P = _toy(99)
    P.meter = Meter(1.0)
    assert learner.apply(None, view(P), np.random.default_rng(3)).shape == (P.n_vars,)       # no budget: an answer of the right shape


def main() -> int:
    tests = [test_versions_and_ways, test_search_stays_inside_the_meter_and_improves, test_improvement, test_learner]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
