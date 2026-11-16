"""Tests of design r (the discovery machinery rebuilt from the learner's own record), on synthetic
fixtures only (tests T1 to T9 of the relay experiment's specification, and the acceptance rule
``hard_first`` that development added).

    OPENBLAS_NUM_THREADS=1 python -m rsi6.tests.test_design_r
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

import numpy as np

from rsi6.kernel.problem import AssignProblem, Meter, view
from rsi6.learner import design_o as O
from rsi6.learner import design_q as Q
from rsi6.learner import design_r as R
from rsi6.tests.test_kernel import _Fixture, _Parts

FIXTURES = (lambda seed, meter, ordered: _Fixture(8, 5, seed, meter, ordered),
            lambda seed, meter, ordered: _Parts(12, 3, seed, meter))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RANK = lambda: dict(R.default(), accept="rank")              # design q's acceptance rule


class _ForbiddenParts(AssignProblem):
    """Plumbing fixture with a hard group: a made-up graph whose vertices go into parts of limited size,
    some (vertex, part) pairs forbidden; the soft cost is the number of edges between parts."""

    def __init__(self, n, k, seed, meter):
        rng = np.random.default_rng(seed)
        upper = np.triu((rng.random((n, n)) < 0.25).astype(float), 1)
        self.w = upper + upper.T
        self.bad = (rng.random((n, k)) < 0.3).astype(float)
        super().__init__(n, k, hard=[True, False], ordered=False, capacity=np.full(k, n // k), var_var=(self.w,), var_opt=(self.bad,),
                         meter=meter)

    def partial_totals(self, a):
        placed = a >= 0
        idx = np.flatnonzero(placed)
        cut = self.w * placed[:, None] * placed[None, :] * (a[:, None] != a[None, :])
        return np.array([self.bad[idx, a[idx]].sum(), cut.sum() / 2.0])


def _run(learner, fixture, ordered, limit, memory=None, seed=3):
    meter = Meter(limit)
    problems = [fixture(s, meter, ordered) for s in range(8)]
    capability, memory_out, report = learner.acquire([view(P) for P in problems], np.random.default_rng(seed), memory)
    assert meter.used <= limit + 1e-9, (limit, meter.used)
    test = fixture(99, Meter(400.0), ordered)
    answer = learner.apply(capability, view(test), np.random.default_rng(4))
    assert test.well_formed(answer)
    return capability, memory_out, report, answer.tolist()


def _chain(n=4, limit=200000.0):
    memory = None
    for k in range(n):
        _, memory, report, _ = _run(R.LearnerR(R.default()), FIXTURES[k % 2], False, limit, memory, seed=10 + k)
    return memory


def test_T1_empty_memory_is_design_q_and_foreign_entries_pass():
    for fixture in FIXTURES:
        for ordered in (False, True):
            for limit in (30.0, 2000.0, 60000.0, 200000.0):
                cq, _, rq, aq = _run(Q.LearnerQ(Q.default()), fixture, ordered, limit)
                for memory in (None, {"entries": []}, {"entries": [{"kind": "other", "x": 1}]}):
                    cr, mr, rr, ar = _run(R.LearnerR(RANK()), fixture, ordered, limit, memory)
                    assert json.dumps(cq, sort_keys=True) == json.dumps(cr, sort_keys=True), (ordered, limit)
                    assert aq == ar
                    for k in ("iterations", "program_rounds", "switches", "constructions", "learned"):
                        assert rq[k] == rr[k], (k, rq[k], rr[k])
                    if memory and memory["entries"]:
                        assert mr["entries"][0] == {"kind": "other", "x": 1}


def test_T2_meter_and_exact_repetition_with_a_memory():
    memory = _chain(3)
    a = _run(R.LearnerR(R.default()), FIXTURES[0], False, 60000.0, memory, seed=21)
    b = _run(R.LearnerR(R.default()), FIXTURES[0], False, 60000.0, memory, seed=21)
    assert json.dumps([a[0], a[1], a[3]], sort_keys=True) == json.dumps([b[0], b[1], b[3]], sort_keys=True)


def _planted(U, N, UE=(0, 0, 0), NE=(0, 0, 0)):
    z = [0.0] * R.N_CELLS
    return {"kind": R.KIND_STATS, "v": 1, "N": list(N), "U": list(U), "S": z, "Q": z, "W": z, "SW": z,
            "NE": list(NE), "UE": list(UE), "SE": [0.0] * 3, "QE": [0.0] * 3}


def test_T3_prior_recovers_planted_statistics():
    relay = R.validate(R.default())["relay"]
    N = [100.0] * R.N_CELLS
    U = [5.0] * R.N_CELLS
    U[0], U[1] = 20.0, 0.0
    pr = R.prior_from([_planted(U, N, (30, 10, 0), (100, 100, 100))], relay)
    ubar = sum(U) / sum(N)
    m0 = (20.0 + 20 * ubar) / (100 + 20)
    assert abs(pr["w"][0] - round(min(2.0, np.log(m0 / ubar)), 6)) < 1e-6
    assert pr["w"][1] < 0 and pr["w"][0] > 0 and abs(pr["w"][2] - pr["w"][3]) < 1e-9
    assert pr["wE"][0] > pr["wE"][1] > pr["wE"][2]
    big = [1e6 if c == 0 else 1.0 for c in range(R.N_CELLS)]
    assert R.prior_from([_planted(big, N)], relay)["w"][0] == 2.0           # the cap
    assert R.prior_from([], relay) is None and R.prior_from([{"kind": "x"}], relay) is None
    dm = dict(relay, rule="dmean")
    e = _planted(U, N)
    e["S"] = [1.0 if c == 0 else -1.0 for c in range(R.N_CELLS)]
    e["Q"] = [1.0] * R.N_CELLS
    assert R.prior_from([e], dm)["w"][0] > 0 > R.prior_from([e], dm)["w"][1]


def test_T4_credit_ties_carry_none_and_shares_are_fractional():
    L = R.LearnerR(R.default())
    L._reset_log()
    keys = np.zeros((4, 2, 2))
    keys[2] = 1.0                                                  # variant 2 differs from the incumbent; variants 1 and 3 tie
    F = np.array([1.0, 1.0, 3.0, 1.0])
    logs = [{"cells": [0], "k": 1, "infos": []}, {"cells": [2, 5], "k": 2, "infos": []}, {"cells": [7], "k": 1, "infos": []}]
    L._credit(logs, keys, F, switched=2)
    assert L._counts["variants"] == 3 and L._counts["informative"] == 1 and L._counts["switches"] == 1
    d = (3.0 - 1.0) / 3
    assert abs(L._stats["N"].sum() - 1.0) < 1e-12 and abs(L._stats["U"].sum() - d) < 1e-12
    assert L._stats["N"][2] == 0.5 and L._stats["N"][5] == 0.5 and L._stats["N"][0] == 0 and L._stats["N"][7] == 0
    assert L._sizes["NE"][1] == 1.0 and L._stats["SW"][2] == 0.5


def test_T5_splice_relocates_and_appends_terms():
    g = O.validate(O.default())
    rng = np.random.default_rng(0)
    term = {"part": "score", "block": [["load", 3, 1, 0], ["mm", 3, 3, 0], ["scale", 3, 3, -1], ["add", 0, 0, 3]], "fresh": 1, "term": True}
    new, info = R.splice(g, "score", [term], rng)
    assert new is not None and len(new["theta"]) == len(g["theta"]) + 1
    assert new["score"][-4:] == [["load", 3, 1, 0], ["mm", 3, 3, 0], ["scale", 3, 3, len(g["theta"])], ["add", 0, 0, 3]]
    base = {"part": "pick", "block": [["scale", 1, 1, 7]], "fresh": 0, "term": False}
    new2, _ = R.splice(g, "pick", [base], rng)
    assert ["scale", 1, 1, 7] in new2["pick"] and len(new2["theta"]) == len(g["theta"])
    assert R.splice(g, "pick", [term], rng)[0] is None                    # no block of that part
    full = dict(g, theta=[0.0] * 32)
    assert R.splice(O.validate(full), "score", [term], rng)[0] is None    # no room for a constant
    ins, fresh, is_term = R.relocate([["load", 3, 1, 0], ["scale", 3, 3, 12], ["shift", 2, 2, 12], ["scale", 2, 2, 4], ["add", 0, 0, 3]])
    assert ins == [["load", 3, 1, 0], ["scale", 3, 3, -1], ["shift", 2, 2, -1], ["scale", 2, 2, 4], ["add", 0, 0, 3]]
    assert fresh == 1 and is_term


def test_T6_library_extraction_is_live_limited_and_relocated():
    memory = _chain(6, 400000.0)
    libs = [e for e in memory["entries"] if e["kind"] == R.KIND_LIB]
    for e in libs:
        assert 1 <= len(e["blocks"]) <= R.RELAY0["lib_per_run"]
        for b in e["blocks"]:
            assert b["part"] in ("score", "pick")
            assert all(not (ins[0] in R.PARAMLIKE and ins[3] >= R.BASE_THETA) for ins in b["block"])
            assert b["fresh"] == len({ins[3] for ins in b["block"] if ins[0] in R.PARAMLIKE and ins[3] < 0})


def test_T7_memory_transforms_keep_amounts_and_structure():
    memory = _chain(4)
    sh = R.shuffled(memory, 3)
    for a, b in zip(memory["entries"], sh["entries"]):
        assert a["kind"] == b["kind"]
        if a["kind"] == R.KIND_STATS:
            for k in R.STAT_KEYS + R.SIZE_KEYS:
                assert sorted(a[k]) == sorted(b[k])
        if a["kind"] == R.KIND_LIB:
            for x, y in zip(a["blocks"], b["blocks"]):
                assert (x["part"], len(x["block"]), x["term"]) == (y["part"], len(y["block"]), y["term"])
    assert R.shuffled(memory, 3) == sh and R.shuffled(memory, 4) != sh or all(e["kind"] != R.KIND_STATS for e in memory["entries"])
    assert all(e["kind"] != R.KIND_LIB for e in (R.without(memory, R.KIND_LIB) or {"entries": []})["entries"])
    assert all(e["kind"] != R.KIND_STATS for e in (R.without(memory, R.KIND_STATS) or {"entries": []})["entries"])
    assert R.mem([]) is None


def test_T8_dispatch_leaves_the_other_designs_alone():
    from rsi6.learner import designs, dispatch_extra
    pinned = json.load(open(os.path.join(ROOT, "rsi6", "registry", "registration_o.json")))["generation_0"]["files"]["rsi6/learner/designs.py"]
    assert hashlib.sha256(open(os.path.join(ROOT, "rsi6", "learner", "designs.py"), "rb").read()).hexdigest() == pinned
    before = [designs.digest(designs.default(d)) for d in ("a", "b", "o")]
    dispatch_extra.install()
    after = [designs.digest(designs.default(d)) for d in ("a", "b", "o")]
    assert before == after
    assert type(designs.make(R.default())) is R.LearnerR and type(designs.make(Q.default())) is Q.LearnerQ
    assert designs.digest(R.default()) == R.digest(R.default())


def test_T9_the_memory_holds_no_score_answer_or_reference():
    memory = _chain(3)
    allowed_stats = {"kind", "v", *R.STAT_KEYS, *R.SIZE_KEYS, "rounds", "variants", "informative", "switches", "kept", "kept_splice", "layout"}
    for e in memory["entries"]:
        if e["kind"] == R.KIND_STATS:
            assert set(e) == allowed_stats, set(e) ^ allowed_stats
        else:
            assert set(e) == {"kind", "v", "blocks"} and all(set(b) == {"part", "block", "fresh", "term"} for b in e["blocks"])


def test_hard_first_fitness_is_lexicographic_over_the_batch():
    # three candidates, four problems; keys are (hard, soft). Candidate 1 is best on three problems and
    # breaks a hard constraint on the fourth; candidate 2 is never best and never breaks one.
    keys = np.array([[(0, 5.0), (0, 5.0), (0, 5.0), (0, 5.0)],
                     [(0, 1.0), (0, 1.0), (0, 1.0), (2, 0.0)],
                     [(0, 6.0), (0, 6.0), (0, 6.0), (0, 4.0)]], dtype=float)
    rank, hard = O._fitness(keys), R.fitness_hard_first(keys)
    assert int(np.argmax(rank)) == 1                                   # the mean rank takes the fragile candidate
    assert hard[1] < hard[0] and hard[1] < hard[2] and int(np.argmax(hard)) == 0
    assert hard[0] == rank[0] and hard[2] == rank[2]                   # the clean candidates keep their mean rank
    clean = keys.copy()
    clean[1, 3] = (0, 0.0)
    assert np.array_equal(R.fitness_hard_first(clean), O._fitness(clean))   # nothing broken: design o's fitness exactly
    inf = keys.copy()
    inf[1, 3] = (np.inf, np.inf)                                       # a construction that could not be completed
    assert int(np.argmax(R.fitness_hard_first(inf))) == 0
    everyone = keys.copy()
    everyone[:, 3, 0] = (3, 1, 2)                                      # all break it there: the rank of the keys decides
    assert np.array_equal(R.fitness_hard_first(everyone), O._fitness(everyone))


def test_hard_first_tests_a_switch_on_every_other_problem():
    learner = R.LearnerR(R.default())
    calls = []

    def fake(problems, indices, cands, rng, meter):
        calls.append(list(indices))
        keys = np.zeros((2, len(indices), 2))
        keys[1, 0, 0] = planted                                        # the second candidate's hard total on the first problem
        return keys

    learner._rollouts_q = fake
    report = {"constructions": 0, "vetoes": 0}
    planted = 1.0
    assert learner._clean_everywhere(list(range(9)), [3, 5, 7], [None, None], None, None, report) is False
    assert report == {"constructions": 6, "vetoes": 1} and calls == [[3, 5, 7]]
    planted = 0.0
    assert learner._clean_everywhere(list(range(9)), [3, 5, 7], [None, None], None, None, report) is True
    assert learner._clean_everywhere(list(range(9)), [], [None, None], None, None, report) is True and len(calls) == 2
    rank = R.LearnerR(RANK())
    rank._rollouts_q = fake
    planted = 1.0
    assert rank._clean_everywhere(list(range(9)), [3, 5, 7], [None, None], None, None, report) is True and len(calls) == 2


def test_hard_first_on_a_fixture_with_a_hard_group():
    """Within the meter, repeatable, the tests on every problem are exercised (some switch is refused), and
    a capability refused at the end is the starting one. (That a refused candidate breaks more problems
    than the one it would replace is the unit test above: this fixture's constructions depend on the
    random stream, so a second construction cannot check it.)"""
    vetoes, end_refusals = 0, 0
    for seed in range(8):
        out = []
        for _ in range(2 if seed == 0 else 1):
            learner = R.LearnerR(R.default())
            meter = Meter(250000.0)
            problems = [_ForbiddenParts(12, 3, 100 * seed + s, meter) for s in range(8)]
            capability, memory, report = learner.acquire([view(P) for P in problems], np.random.default_rng(seed), None)
            assert meter.used <= meter.limit + 1e-9 and "vetoes" in report
            out.append(json.dumps([capability, memory, report["vetoes"]], sort_keys=True))
        assert len(set(out)) == 1
        vetoes += report["vetoes"]
        if report["failed"] and "breaks hard constraints" in report["failed"]:
            end_refusals += 1
            assert capability["learned"] is False and "program" not in capability
            assert capability["theta"] == [float(x) for x in learner.g["theta"]]
    assert vetoes >= 3 and end_refusals >= 1, (vetoes, end_refusals)
    rank = R.LearnerR(RANK())
    meter = Meter(250000.0)
    _, _, report = rank.acquire([view(_ForbiddenParts(12, 3, s, meter)) for s in range(8)], np.random.default_rng(0), None)
    assert "vetoes" not in report


def test_relay_settings_are_validated():
    good = R.default()
    R.validate(good)
    try:
        R.validate(dict(good, accept="other"))
        raise AssertionError("accepted an unknown acceptance rule")
    except ValueError:
        pass
    assert R.digest(good) != R.digest(dict(good, accept="rank")) and R.differences(good, dict(good, accept="rank"))["accept"]["to"] == "rank"
    for broken in ({"beta": 0.0}, {"kappa": 0}, {"cap": 9}, {"lib_max": 65}, {"rule": "other"}):
        bad = json.loads(json.dumps(good))
        bad["relay"].update(broken)
        try:
            R.validate(bad)
            raise AssertionError(f"accepted {broken}")
        except ValueError:
            pass


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
