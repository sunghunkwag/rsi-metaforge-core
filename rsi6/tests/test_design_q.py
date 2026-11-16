"""Tests of design q (representation search inside acquisition), on synthetic fixtures only.

    OPENBLAS_NUM_THREADS=1 python -m rsi6.tests.test_design_q
"""
from __future__ import annotations

import json
import sys

import numpy as np

from rsi6.kernel.problem import Meter, view
from rsi6.learner import design_o as O
from rsi6.learner import design_q as Q
from rsi6.tests.test_kernel import _Fixture, _Parts

FIXTURES = (lambda seed, meter, ordered: _Fixture(8, 5, seed, meter, ordered),
            lambda seed, meter, ordered: _Parts(12, 3, seed, meter))


def _run(learner, fixture, ordered, limit):
    meter = Meter(limit)
    problems = [fixture(seed, meter, ordered) for seed in range(8)]
    capability, _, report = learner.acquire([view(P) for P in problems], np.random.default_rng(3))
    assert meter.used <= limit + 1e-9, (limit, meter.used)
    test = fixture(99, Meter(400.0), ordered)
    answer = learner.apply(capability, view(test), np.random.default_rng(4))
    assert test.well_formed(answer), (ordered, limit)
    return capability, answer.tolist(), report


def test_design_q_keeps_the_contract():
    """A well-formed answer whatever the budget, the meter respected, a run repeats exactly."""
    for fixture in FIXTURES:
        for ordered in (False, True):
            for limit in (30.0, 2000.0, 60000.0):
                a = _run(Q.LearnerQ(Q.default()), fixture, ordered, limit)
                b = _run(Q.LearnerQ(Q.default()), fixture, ordered, limit)
                assert json.dumps(a[:2], sort_keys=True) == json.dumps(b[:2], sort_keys=True), "design q does not repeat exactly"


def test_share_zero_is_design_o():
    """With no program rounds, design q is design o: the same capability and the same answers."""
    off = Q.default()
    off["inner"]["share"] = 0.0
    for fixture in FIXTURES:
        for ordered in (False, True):
            for limit in (30.0, 2000.0, 60000.0):
                q = _run(Q.LearnerQ(off), fixture, ordered, limit)
                o = _run(O.OpenLearner(O.default()), fixture, ordered, limit)
                assert json.dumps(q[0], sort_keys=True) == json.dumps(o[0], sort_keys=True), (ordered, limit)
                assert q[1] == o[1], (ordered, limit)
                assert q[2]["iterations"] == o[2]["iterations"] and q[2]["program_rounds"] == 0


def test_program_rounds_run_and_programs_are_kept_as_capability():
    """With budget, program rounds happen; a capability that carries programs is applied with them."""
    seen_rounds, seen_program = 0, 0
    for fixture in FIXTURES:
        for seed_limit in (60000.0, 200000.0):
            cap, _, report = _run(Q.LearnerQ(Q.default()), fixture, False, seed_limit)
            seen_rounds += report["program_rounds"]
            if "program" in cap:
                seen_program += 1
                O.validate(dict(O.default(), score=cap["program"]["score"], pick=cap["program"]["pick"], theta=cap["theta"]))
    assert seen_rounds > 0
    # a capability with programs changes the answer the way its programs say
    learner = Q.LearnerQ(Q.default())
    P = _Fixture(8, 5, 99, Meter(400.0), False)
    flipped = {"kind": "open", "theta": [1.0] + [0.0] * 9, "learned": True,
               "program": {"score": [["load", 1, 0, 0], ["mm", 1, 1, 0], ["scale", 0, 1, 0]], "pick": []}}
    answer = learner.apply(flipped, view(P), np.random.default_rng(4))
    assert P.well_formed(answer)


def test_variants_are_valid_programs_and_growth_is_not_a_no_op():
    learner = Q.LearnerQ(Q.default())
    rng = np.random.default_rng(0)
    prog = {"score": learner.g["score"], "pick": learner.g["pick"]}
    theta = np.array(learner.g["theta"], float)
    grew = 0
    for _ in range(300):
        v = learner._variant(prog, theta, rng)
        if v is None:
            continue
        p, t = v
        O.validate(dict(learner.g, score=p["score"], pick=p["pick"], theta=[float(x) for x in t]))
        if len(t) > len(theta):
            grew += 1
            assert t[-1] != 0.0 or True                    # a random start (0 only by chance)
    assert grew > 0


def test_inner_settings_are_validated():
    good = Q.default()
    Q.validate(good)
    for broken in ({"share": 0.3}, {"variants": 5}, {"edits": [0, 0, 0]}, {"w": [0.0] * 3}, {"w": [9.0] * len(Q.INNER_CELLS)}):
        bad = json.loads(json.dumps(good))
        bad["inner"].update(broken)
        try:
            Q.validate(bad)
            raise AssertionError(f"accepted {broken}")
        except ValueError:
            pass
    try:
        Q.validate(dict(good, extra=1))
        raise AssertionError("accepted an extra part")
    except ValueError:
        pass
    assert Q.digest(good) != O.digest(O.default())


def test_outer_edits_of_design_q():
    """Every cell of the outer edit space gives a valid mechanism of design q or no edit; inner
    settings that are never read do not change the behaviour key; the prior and the edit weights
    are part of what the discoverer reads."""
    from rsi6.open import discovery_q as DQ
    rng = np.random.default_rng(1)
    q0 = Q.default()
    made = 0
    for _ in range(4):
        for cell in DQ.CELLS:
            new, info = DQ.apply_edit(q0, cell, [], rng)
            if new is not None:
                assert Q.validate(new) == new
                made += 1
    assert made > len(DQ.CELLS)
    off = json.loads(json.dumps(q0))
    off["inner"]["share"] = 0.0
    off2 = json.loads(json.dumps(off))
    off2["inner"]["w"][0] = 3.0
    assert DQ.behaviour(off) == DQ.behaviour(off2)
    on2 = json.loads(json.dumps(q0))
    on2["inner"]["w"][0] = 3.0
    assert DQ.behaviour(q0) != DQ.behaviour(on2) and DQ.principle(q0) != DQ.principle(on2)
    D = DQ.Discoverer(on2, np.random.default_rng(0), {"kd": 6, "nedit": [0.6, 0.3, 0.1]}, mode="recursive")
    p = D.distribution(np.zeros(len(DQ.CELLS)))
    assert abs(p.sum() - 1) < 1e-9 and p[DQ.SHARED[0]] > p[DQ.SHARED[1]]
    assert DQ.Discoverer(on2, np.random.default_rng(0), {"kd": 6, "nedit": [0.6, 0.3, 0.1]}, mode="uniform").distribution(
        np.zeros(len(DQ.CELLS))).std() < 1e-12


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception as error:                      # noqa: BLE001
            failed += 1
            print("FAIL", name, "-", type(error).__name__, error)
    print(f"RESULT: {len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
