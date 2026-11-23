"""Tests of design s: the learner, the list of mechanisms, and the chains on tables.

    python -m rsi6.tests.test_design_s

The first group runs the learner on published instances (it fetches quadassign, pmedian and
jobshop); the second builds small tables with a known landscape in a temporary directory.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6.kernel.run import BUDGET, measure
from rsi6.learner import design_s, designs
from rsi6.learner.learner import Learner
from rsi6.meta import chain_s
from rsi6.meta.rounds import RULES

SEED = 9741001                                                    # no measurement uses this range


def run(category: str, version: dict, seed: int, train: float = 40.0) -> dict:
    return measure({"env": category, "version": version, "seed": seed, "budget": dict(BUDGET, train=train), "purpose": "test"})["record"]


def test_dispatch():
    design_s.install()
    design_s.install()                                            # twice is once
    s0 = design_s.default()
    assert designs.design_of(s0) == "s" and type(designs.make(s0)) is design_s.LearnerS
    assert type(designs.make(designs.default("a"))) is Learner    # the first design goes where it went
    assert designs.digest(s0) == design_s.digest(s0) != designs.digest(designs.default("a"))
    assert designs.validate(s0) == s0 and designs.schema(s0) is design_s.SCHEMA
    for bad in (dict(s0, **{"model.variant": "es"}), dict(s0, **{"adapt.spread": "fast"}), dict(s0, **{"adapt.race": 2}),
                {k: v for k, v in s0.items() if k != "adapt.race"}, dict(s0, design="a")):
        try:
            design_s.validate(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad}")
    assert designs.differences(s0, dict(s0, **{"adapt.race": 1})) == {"adapt.race": {"from": 0, "to": 1, "function": "explore"}}
    print("dispatch: design s is known after install(); the other designs are untouched")


def test_list():
    versions = design_s.mechanisms()
    assert len(versions) == 324 and len({design_s.digest(v) for v in versions}) == 324
    assert len({design_s.behaviour(v) for v in versions}) == 288   # a population of 8 keeps 2 at 0.1 and at 0.25
    tables_shape = tuple(len(design_s.LEVELS[f]) for f in design_s.MECHANISM)
    for k, v in enumerate(versions):
        assert int(np.ravel_multi_index(design_s.index_of(v), tables_shape)) == k
        assert design_s.a_part(v) == designs.validate(dict(designs.default("a"), **{f: v[f] for f in design_s.MECHANISM[:4]}))
    assert design_s.default() in versions
    assert design_s.race_plan(16, 4, 8) == [16, 8, 4, 4, 4, 4, 4, 4] and design_s.race_plan(8, 2, 2) == [8, 4]
    assert design_s.race_plan(32, 16, 4) == [32, 16, 16, 16] and design_s.race_plan(16, 2, 4) == [16, 8, 4, 2]
    print("list: 324 versions, 288 different searches, numbered as the tables number them")


def test_same_as_first_design():
    """With both new procedures off, design s is the first design: same scores, same capability,
    same report, same counted units, on unordered and ordered categories."""
    design_s.install()
    cases = [("quadassign", {}, SEED), ("quadassign", {"model.batch": 2}, SEED + 1),
             ("quadassign", {"model.batch": 2, "model.pop": 8, "model.elite": 0.5, "model.sigma": 0.2}, SEED),
             ("pmedian", {"model.batch": 2}, SEED), ("jobshop", {"model.batch": 2, "model.pop": 32}, SEED)]
    for category, change, seed in cases:
        a = run(category, designs.validate(dict(designs.default("a"), **change)), seed)
        s = run(category, design_s.validate(dict(design_s.default(), **change)), seed)
        for name in ("untrained", "acquired", "gain", "capability", "fresh_acquired", "train_acquired", "units", "report"):
            assert a[name] == s[name], (category, change, name)
        assert a["version"] != s["version"]
    print(f"same as the first design: {len(cases)} runs identical in scores, capability, report and units")


def test_adaptive_steps():
    design_s.install()
    base = design_s.validate(dict(design_s.default(), **{"model.batch": 4}))
    plain = run("quadassign", base, SEED)
    raced = run("quadassign", dict(base, **{"adapt.race": 1}), SEED)
    selfa = run("quadassign", dict(base, **{"adapt.spread": "self"}), SEED)
    both = run("quadassign", dict(base, **{"adapt.spread": "self", "adapt.race": 1, "model.batch": 8}), SEED)
    for r in (plain, raced, selfa, both):
        assert r["units"]["train_used"] <= r["units"]["train_limit"] and 0.0 <= r["acquired"] <= 1.0
        assert r["report"]["iterations"] >= 1
    # a raced round of 16 candidates keeping 4 on a batch of 4 costs 16 + 8 + 4 + 4 constructions, a plain one 64
    assert plain["report"]["constructions"] == 64 * plain["report"]["iterations"]
    assert raced["report"]["constructions"] == 32 * raced["report"]["iterations"]
    assert raced["report"]["iterations"] > plain["report"]["iterations"]
    assert both["report"]["constructions"] == 48 * both["report"]["iterations"]
    assert "spread" not in plain["report"] and len(selfa["report"]["spread"]) == selfa["report"]["iterations"]
    schedule = [round(0.9 ** (k + 1), 4) for k in range(selfa["report"]["iterations"])]
    assert selfa["report"]["spread"] != schedule                 # the spread followed the candidates that were kept, not the schedule alone
    again = run("quadassign", dict(base, **{"adapt.spread": "self", "adapt.race": 1, "model.batch": 8}), SEED)
    assert again["capability"] == both["capability"] and again["acquired"] == both["acquired"]
    print("adaptive steps: inside the budget, a raced round costs what the plan says, runs repeat exactly")


# ---- chains on tables with a known landscape ---------------------------------------------------
def landscape(index, kind: int) -> float:
    """A score with one best mechanism: small batch, middle population, the two procedures on."""
    batch, pop, elite, sigma, spread, race = index
    return 0.5 - 0.04 * batch - 0.03 * abs(pop - 1) - 0.01 * elite + 0.02 * spread + 0.03 * race + 0.01 * kind * (sigma == 1)


def write_tables(directory: str, noise: float = 0.01, seeds: int = 8):
    versions = design_s.mechanisms()
    rng = np.random.default_rng(5)
    for kind, category in enumerate(("d1", "d2", "d3", "d4", "g1", "g2", "t1", "t2")):
        base = np.array([landscape(design_s.index_of(v), kind % 3) for v in versions])
        table = {}
        for name in chain_s.NAMES:
            if name.startswith("acquired"):
                table[name] = (base[None, :] + noise * rng.standard_normal((seeds, len(versions)))).tolist()
            elif name.startswith("untrained"):
                table[name] = np.full((seeds, len(versions)), 0.2).tolist()
            elif name == "cpu":
                table[name] = np.full((seeds, len(versions)), 1.0 + kind).tolist()
            else:
                table[name] = np.ones((seeds, len(versions))).tolist()
        for half in range(2):                                      # two files per category, as two jobs would write them
            rows = slice(0, seeds // 2) if half == 0 else slice(seeds // 2, seeds)
            out = {"category": category, "seeds": list(range(100 + rows.start, 100 + rows.stop)), "smoke": False,
                   "fields": list(design_s.MECHANISM), "versions": [design_s.digest(v) for v in versions],
                   "table": {name: table[name][rows] for name in chain_s.NAMES}}
            json.dump(out, open(os.path.join(directory, f"grid_{category}_{100 + rows.start}.json"), "w"))


def test_chains():
    with tempfile.TemporaryDirectory() as directory:
        write_tables(directory)
        tables = chain_s.Tables(directory)
        discovery, gates, test = ["d1", "d2", "d3", "d4"], ["g1", "g2"], ["t1", "t2"]
        assert sorted(tables.cats) == sorted(discovery + gates + test) and tables.cats["d1"]["acquired"].shape == (8, 324)
        assert tables.cats["d1"]["seeds"] == list(range(100, 108))
        for k in (0, 17, 323):
            assert tables.number(tables.point(k)) == k
        # the improver's task: 16 problems, the budget of an acquisition, never overspent
        rng = np.random.default_rng(1)
        task = chain_s.VersionTask(tables, discovery, 200, rng)
        assert task.n == 16 and task.dim == 6 and abs(task.limit - 40.0 * sum(task.costs)) < 1e-9
        assert sorted({c for c, _ in task.problems}) == discovery
        for improver in (0, 107, 215, 323):
            nominee, report = chain_s.improve(tables, discovery, improver, 200, np.random.default_rng(2))
            assert report["iterations"] >= 1 and (nominee is None or 0 <= nominee < 324 and nominee != 200)
        task = chain_s.VersionTask(tables, discovery, 200, np.random.default_rng(3))
        design_s.search(task, tables.versions[0], np.random.default_rng(3), {})
        assert 0.0 < task.used <= task.limit
        # the gate is the registered rule, computed directly here
        gate = chain_s.Gate(tables, gates)
        worst, best = int(np.argmin(tables.mean(gates))), int(np.argmax(tables.mean(gates)))
        assert gate.decide(worst, best)["adopted"] and not gate.decide(best, worst)["adopted"] and not gate.decide(best, best)["adopted"]
        d = gate.decide(worst, best)
        a = [tables.cats[c]["acquired_a"][:4, best] - tables.cats[c]["acquired_a"][:4, worst] for c in gates]
        assert abs(d["mean_min"] - np.mean([x.mean() for x in a])) < 1e-12
        rng = np.random.default_rng(700)
        means = []
        for _ in range(RULES["bootstrap"]):
            means.append(np.mean([x[rng.choice(len(x), size=len(x))].mean() for x in a]))
        assert abs(d["gain_lower_bound"] - float(np.quantile(means, 1.0 - RULES["level"]))) < 1e-12
        b = [tables.cats[c]["acquired_b"][4:, best] - tables.cats[c]["acquired_b"][4:, worst] for c in gates]
        assert abs(d["confirmation"] - np.mean([x.mean() for x in b])) < 1e-12 and abs(d["cpu_ratio"] - 1.0) < 1e-12
        # chains: repeatable; the recursive and the frozen arm are one chain until their improvers differ
        starts = [0, 107, 200, 215, 323]
        one = chain_s.simulate(tables, discovery, gates, starts, reps=6, generations=3, seed=4)
        two = chain_s.simulate(tables, discovery, gates, starts, reps=6, generations=3, seed=4)
        assert json.dumps(one) == json.dumps(two)
        rec, frz = np.array(one["arms"]["recursive"]["paths"]), np.array(one["arms"]["frozen"]["paths"])
        assert rec.shape == (5, 6, 4) and (rec[:, :, 0] == np.array(starts)[:, None]).all()
        assert (rec[:, :, 1] == frz[:, :, 1]).all()
        same_improver = rec[:, :, 1] == rec[:, :, 0]               # nothing adopted in generation 1: the improvers are still the same
        assert (rec[:, :, 2][same_improver] == frz[:, :, 2][same_improver]).all()
        # on this landscape (clear, little noise) a chain must end above where it started, on categories it did not read
        reading = chain_s.read(tables, [{"result": one, "test": test}], boot=200)
        stats = reading["statistics"]
        assert stats["recursive"]["mean"][0] == 0.0 and stats["recursive"]["mean"][-1] > 0.01 and stats["recursive"]["q05"][-1] > 0.0
        assert stats["random"]["mean"][-1] >= 0.0                  # the gate lets nothing worse through here
        assert len(stats["recursive-frozen"]["mean"]) == 4 and stats["recursive-frozen"]["mean"][1] == 0.0
        assert set(reading["per_fold"][0]["adopted_per_generation"]) == set(chain_s.ARMS)
        try:
            chain_s.read(tables, [{"result": one, "test": ["d1", "t1"]}], boot=10)
        except ValueError:
            pass
        else:
            raise AssertionError("a category the chains read was accepted as a test category")
        swapped = chain_s.simulate(tables, ["d1", "d2", "t1", "t2"], ["d3", "d4"], starts, reps=6, generations=3, seed=4)
        two_folds = chain_s.read(tables, [{"result": one, "test": test}, {"result": swapped, "test": gates}], boot=100)
        mean_of_folds = np.mean([f["statistics"]["recursive"]["mean"] for f in two_folds["per_fold"]], axis=0)
        assert np.allclose(two_folds["statistics"]["recursive"]["mean"], mean_of_folds, atol=2e-5)
        # every improver from the same incumbents
        after = chain_s.quality(tables, discovery, gates, [107, 200], reps=2, seed=5)
        assert after.shape == (324, 2, 2) and after.min() >= 0 and after.max() < 324
        with_quality = chain_s.read(tables, [{"result": one, "test": test, "after": after, "incumbents": [107, 200]}], boot=50)
        assert -1.0 <= with_quality["statistics"]["alignment"]["mean"][0] <= 1.0
    print("chains: tables load, the task has the budget of an acquisition, the gate is the registered rule, chains repeat, "
          "recursive and frozen agree until an adoption")


def main() -> int:
    test_dispatch()
    test_list()
    test_chains()
    test_same_as_first_design()
    test_adaptive_steps()
    print("all tests of design s passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
