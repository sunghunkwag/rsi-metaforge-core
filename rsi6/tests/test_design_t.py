"""Tests of design t (the learner of the prediction form) that need no published data.

    python -m rsi6.tests.test_design_t
"""
from __future__ import annotations

import json
import sys

import numpy as np

from rsi6.kernel.problem import Meter, PredictProblem
from rsi6.learner import design_t as T
from rsi6.meta import chain_t


def _problems(rng, n=10, ordered=False, meter=None, train=12.0):
    """A made-up kind: targets that a product of two attributes gives (unordered), or a trend with a period (ordered)."""
    meter = meter or Meter(0.0)
    out = []
    for _ in range(n):
        if ordered:
            t = np.arange(60, dtype=float)
            y = 5.0 + rng.uniform(0.05, 0.3) * t + rng.uniform(0.5, 2.0) * np.sin(2 * np.pi * t / 6) + 0.1 * rng.standard_normal(60)
            out.append(PredictProblem(t[:48, None], y[:48], t[48:, None], True, target=y[48:], meter=meter))
        else:
            X = rng.uniform(1.0, 3.0, size=(90, 3))
            y = X[:, 0] * X[:, 1] + 0.05 * rng.standard_normal(90)
            out.append(PredictProblem(X[:60], y[:60], X[60:], False, target=y[60:], meter=meter))
    meter.limit = train * sum(P.construction_units() for P in out)
    return out


def test_programs():
    rng = np.random.default_rng(0)
    for form, width in (("unordered", 54), ("ordered", 20)):
        for _ in range(200):
            p = T.fresh(form, rng)
            T.check_program(p, form)
            q = T.vary(p, rng)
            T.check_program(q, form)
            row = T.features(q)
            assert len(row) == width and all(0.0 <= x <= 1.0 for x in row), (form, row)
    try:
        T.check_program({"form": "u", "y": "raw", "snap": 0, "stages": []}, "unordered")
    except ValueError:
        pass
    else:
        raise AssertionError("an empty program was accepted")


def test_versions():
    v = T.default()
    assert T.validate(v) == v and len(T.digest(v)) == 64
    assert T.differences(v, v) == {}
    rng = np.random.default_rng(1)
    w = json.loads(json.dumps(v))
    w["library"]["unordered"] = [T.fresh("unordered", rng) for _ in range(3)]
    w["known"]["ordered"] = [[T.fresh("ordered", rng), 0.25, "somewhere"] for _ in range(5)]
    assert set(T.differences(v, w)) == {"library.unordered", "known.ordered"} and T.digest(w) != T.digest(v)
    bad = json.loads(json.dumps(w))
    bad["model"]["ordered"] = {"rule": "select", "programs": [T.fresh("ordered", rng)]}      # a model is made of unordered programs
    for wrong in (bad, dict(v, extra=1), dict(v, library={"unordered": [T.fresh("ordered", rng)], "ordered": []})):
        try:
            T.validate(wrong)
        except ValueError:
            continue
        raise AssertionError("a wrong version was accepted")


def test_acquire_and_apply():
    for ordered in (False, True):
        rng = np.random.default_rng(2)
        problems = _problems(rng, ordered=ordered)
        learner = T.LearnerT(T.default())
        capability, memory, report = learner.acquire(problems, np.random.default_rng(3))
        assert memory == {"entries": []} and report["iterations"] >= 3 and len(report["trace"]) == report["iterations"]
        assert problems[0].meter.used <= problems[0].meter.limit
        assert capability["learned"] and 1 <= len(capability["programs"]), report
        fresh = _problems(np.random.default_rng(4), n=6, ordered=ordered)
        mine, base = [], []
        for P in fresh:
            target, scale = P.qry_y, T.spread(P.ctx_y)
            Q = PredictProblem(P.ctx_x, P.ctx_y, P.qry_x, ordered, meter=Meter(T.PASSES * P.construction_units()))
            mine.append(T.skill(learner.apply(capability, Q), target, scale))            # within the kernel's passes, or this raises
            base.append(T.skill(T.anchor(P.ctx_x, P.ctx_y, P.qry_x, ordered), target, scale))
        assert np.mean(mine) > np.mean(base), (ordered, np.mean(mine), np.mean(base))
        again = T.LearnerT(T.default()).acquire(_problems(np.random.default_rng(2), ordered=ordered), np.random.default_rng(3))
        assert again[0] == capability                                                    # the same seeds, the same capability


def test_library_has_a_share():
    rng = np.random.default_rng(5)
    v = T.default()
    v["library"]["unordered"] = [T.fresh("unordered", rng) for _ in range(6)]
    _, _, report = T.LearnerT(v).acquire(_problems(np.random.default_rng(6)), np.random.default_rng(7))
    origins = [row[2] for row in report["trace"]]
    assert origins[0] == "library" and "library" not in origins[origins.index(next(o for o in origins if o != "library")):]
    spent = sum(T.passes(row[0]) for row in report["trace"] if row[2] == "library")
    total = sum(T.passes(row[0]) for row in report["trace"])
    assert spent <= T.SHARE * total + 3, (spent, total)                                  # at most its share (one program of slack)


def test_model_of_own_programs():
    rng = np.random.default_rng(8)
    known = []
    for place, shift in (("a", 0.0), ("b", 0.1), ("c", -0.1)):
        for _ in range(60):
            p = T.fresh("unordered", rng)
            value = 0.6 * (p["y"] == "log") + 0.3 * (p["stages"][0]["model"] == "krr") - 0.2 * len(p["stages"]) + shift
            known.append([p, float(np.clip(value + 0.05 * rng.standard_normal(), -1, 1)), place])
    values = T.values(known)
    assert values.min() == 0.0 and values.max() == 1.0 and len(values) == len(known)
    problems = T.landscape(known, np.random.default_rng(9), Meter(float("inf")))
    assert len(problems) == 12 and all(P.has_feedback() and not P.ordered for P in problems)
    model, report = T.self_model(T.default(), known, np.random.default_rng(10))
    assert model is not None and model["rule"] in ("select", "mean") and report["used"] > 0
    v = T.default()
    v["known"]["unordered"], v["model"]["unordered"] = known, model
    v = T.validate(v)
    meter = Meter(1e9)
    proposed = T.LearnerT(v).propose("unordered", np.random.default_rng(11), meter)
    assert len(proposed) == v["search"]["take"] and meter.used > 0
    drawn = [T.fresh("unordered", np.random.default_rng(12 + i)) for i in range(200)]
    share = lambda programs: float(np.mean([p["y"] == "log" for p in programs]))
    assert share(proposed) > share(drawn) + 0.2, (share(proposed), share(drawn))        # the model found what makes a program good here
    assert T.LearnerT(T.default()).propose("unordered", np.random.default_rng(11), Meter(1e9)) == []
    assert T.LearnerT(v).propose("unordered", np.random.default_rng(11), Meter(10.0)) == []   # no budget: no proposal, nothing charged
    _, _, report = T.LearnerT(v).acquire(_problems(np.random.default_rng(13)), np.random.default_rng(14))
    assert report["modelled"] == v["search"]["take"] and any(row[2] == "proposed" for row in report["trace"])
    assert T.self_model(T.default(), known[:10], np.random.default_rng(10))[0] is None


def test_improver_parts():
    scores = np.array([[0.9, 0.1, 0.1], [0.8, 0.8, 0.1], [0.1, 0.2, 0.9], [0.5, 0.5, 0.5]])
    assert chain_t.cover(scores, 2) == [1, 2] and chain_t.cover(scores, 0) == [] and len(chain_t.cover(scores, 9)) == 4
    rng = np.random.default_rng(15)
    trace = [[T.fresh("unordered", rng), s, "fresh"] for s in (0.1, 0.7, 0.4, 0.9)]
    assert chain_t.offered(trace) == [trace[3][0], trace[1][0]]
    assert len(chain_t.offered(trace, np.random.default_rng(0))) == 2
    records = [{"env": "x", "report": {"trace": trace}}, {"env": "x", "report": {"trace": trace[:2]}}, {"env": "y", "report": {"trace": trace[2:]}}]
    rows = chain_t.remembered(records, "unordered")
    assert len(rows) == 6 and {r[2] for r in rows} == {"x", "y"} and chain_t.remembered(records, "ordered") == []


def main() -> int:
    tests = [test_programs, test_versions, test_acquire_and_apply, test_library_has_a_share, test_model_of_own_programs, test_improver_parts]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
