"""Tests of design r (the discovery machinery rebuilt from the learner's own record), on synthetic
fixtures only.

    OPENBLAS_NUM_THREADS=1 python -m rsi6.tests.test_design_r
"""
from __future__ import annotations

import json
import sys

import numpy as np

from rsi6.kernel.problem import Meter, view
from rsi6.learner import design_r as R
from rsi6.tests.test_kernel import _Fixture, _Parts

FIXTURES = (lambda seed, meter, ordered: _Fixture(8, 5, seed, meter, ordered),
            lambda seed, meter, ordered: _Parts(12, 3, seed, meter))


def _run(version, fixture, ordered, limit, memory=None, seed=3):
    meter = Meter(limit)
    problems = [fixture(s, meter, ordered) for s in range(8)]
    learner = R.LearnerR(version)
    capability, memory_out, report = learner.acquire([view(P) for P in problems], np.random.default_rng(seed), memory)
    assert meter.used <= limit + 1e-9
    test = fixture(99, Meter(400.0), ordered)
    answer = learner.apply(capability, view(test), np.random.default_rng(4))
    assert test.well_formed(answer)
    return capability, memory_out, report, answer.tolist()


def test_design_r_keeps_the_contract_and_repeats():
    for fixture in FIXTURES:
        for ordered in (False, True):
            for limit in (30.0, 2000.0, 60000.0):
                a = _run(R.default(), fixture, ordered, limit)
                b = _run(R.default(), fixture, ordered, limit)
                assert json.dumps([a[0], a[1], a[3]], sort_keys=True) == json.dumps([b[0], b[1], b[3]], sort_keys=True)


def test_the_memory_carries_the_record_and_changes_the_machinery():
    memory = {"entries": []}
    for k in range(4):
        cap, memory, report, _ = _run(R.default(), FIXTURES[k % 2], False, 200000.0, memory, seed=10 + k)
        assert report["relay"] == memory["entries"][-1]
        assert report["relay_in"]["entries"] == k
    m = R.machinery(memory["entries"], R.validate(R.default())["relay"])
    assert m["recorded"] > 0 and np.any(m["prior"] != 0.0)
    assert len(memory["entries"]) == 4
    # the controls' memories keep the amounts and drop or scramble the information
    sh = R.shuffled(memory, 7)
    assert [sum(c[0] for c in e["cells"]) for e in sh["entries"]] == [sum(c[0] for c in e["cells"]) for e in memory["entries"]]
    assert sh["entries"][0]["cells"] != memory["entries"][0]["cells"] or all(c[0] == 0 for c in memory["entries"][0]["cells"])
    pr = R.ablated(memory, "prior")
    assert all(not e["composites"] and not e["blocks"] for e in pr["entries"])
    bl = R.ablated(memory, "blocks")
    assert all(all(c == [0, 0.0, 0.0] for c in e["cells"]) for e in bl["entries"])
    # a run with a memory repeats exactly
    a = _run(R.default(), FIXTURES[0], False, 60000.0, memory, seed=21)
    b = _run(R.default(), FIXTURES[0], False, 60000.0, memory, seed=21)
    assert json.dumps([a[0], a[1], a[3]], sort_keys=True) == json.dumps([b[0], b[1], b[3]], sort_keys=True)


def test_derangement_moves_every_label():
    p = R.derangement(R.N_CELLS, 5)
    assert sorted(p) == list(range(R.N_CELLS)) and all(p[i] != i for i in range(R.N_CELLS))


def test_relay_settings_are_validated():
    good = R.default()
    R.validate(good)
    for broken in ({"beta": -1}, {"shrink": 0}, {"composite_share": 0.9}, {"max_records": 0}):
        bad = json.loads(json.dumps(good))
        bad["relay"].update(broken)
        try:
            R.validate(bad)
            raise AssertionError(f"accepted {broken}")
        except ValueError:
            pass
    assert R.digest(good) != R.digest(dict(good, relay=dict(good["relay"], beta=2.0)))


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
