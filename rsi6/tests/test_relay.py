"""Tests of the relay driver's plan and raise, and of the relay report on synthetic ledgers (no
learner runs; test T11 of the relay experiment's specification, and the parts of the driver that
need no learner).

    OPENBLAS_NUM_THREADS=1 python -m rsi6.tests.test_relay
"""
from __future__ import annotations

import math
import os
import sys
import tempfile

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.learner import design_r
from rsi6.open import evaluate, relay, relay_report

CATS = ["c1", "c2", "c3", "c4"]


def test_t_functions_match_tables():
    for p, df, want in ((0.01, 63, 2.387), (0.01, 31, 2.453), (0.05, 31, 1.696), (0.01, 7, 2.998), (0.05, 1, 6.314),
                        (0.025, 15, 2.131), (0.3, 5, 0.559)):
        assert abs(relay_report.t_quantile(p, df) - want) < 1e-3, (p, df)
    assert abs(relay_report.t_sf(0.0, 10) - 0.5) < 1e-12
    assert abs(relay_report.t_sf(1e-20, 10) - 0.5) < 1e-12              # the case that failed in the dry run
    assert abs(relay_report.t_sf(-1.0, 63) + relay_report.t_sf(1.0, 63) - 1.0) < 1e-12
    assert relay_report.t_sf(math.inf, 5) == 0.0 and relay_report.t_sf(math.nan, 5) == 1.0


def test_spearman_uses_average_ranks():
    assert relay_report.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert relay_report.spearman([1, 1, 1], [1, 2, 3]) is None
    r = relay_report.spearman([1, 2, 2, 3], [1, 2, 3, 4])
    assert abs(r - 0.9486832980505138) < 1e-12, r                      # ties take the average rank


class _FakeCache:
    """CPU proportional to the training budget; a record per distinct job."""

    def __init__(self):
        self.by_key, self.requests = {}, []

    def get(self, jobs, workers=4):
        out = []
        for job in jobs:
            key = (job["env"], job["seed"], job["budget"]["train"], repr(job.get("memory")))
            self.requests.append(key)
            if key not in self.by_key:
                self.by_key[key] = {"key": str(key), "env": job["env"], "seed": job["seed"], "budget": job["budget"],
                                    "cpu": {"acquire": min(0.05 * job["budget"]["train"] * (1 + job["seed"] % 3), 500.0), "apply": 0.0},
                                    "purpose": job["purpose"]}
            out.append(self.by_key[key])
        return out


def test_raise_with_memory_is_raise_until_without_memory():
    want = {("c1", 1): 30.0, ("c1", 2): 55.0, ("c2", 3): 9.0, ("c2", 4): 1e9}
    a, b = _FakeCache(), _FakeCache()
    budget = {"train": 100.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}
    ra = evaluate.raise_until(a, {"design": "x"}, want, "p", budget)
    rb = relay.raise_with_memory(b, {"design": "x"}, want, "p", budget)
    assert a.requests == b.requests
    assert [(r["key"], r["reached"], r["levels"]) for r in ra] == [(r["key"], r["reached"], r["levels"]) for r in rb]
    assert [r["reached"] for r in rb] == [True, True, True, False]
    c = _FakeCache()
    rc = relay.raise_with_memory(c, {"design": "x"}, want, "p", budget, memory_of=lambda pair: {"entries": [{"m": pair[1]}]})
    assert [r["levels"] for r in rc] == [r["levels"] for r in rb] and all("{'entries'" in k[3] for k in c.requests)


def _H(**over):
    H = {"cpu_model": {"o0": {"a": 0.0, "b": 1.0, "d": 0.0}, "r0_over_o0": 1.25}, "train_grid": [200, 160, 120, 80, 40],
         "max_cpu_per_run": 60.0, "machine_factor": 1.15, "matched_levels": 2, "ceiling_cost": 3.8}
    H.update(over)
    return H


def test_plan_drops_items_from_the_end_and_lowers_the_costliest_category():
    U = {c: {"train": u, "test": 0.0} for c, u in zip(CATS, (0.1, 0.2, 0.25, 0.3))}   # o0 CPU = T * u
    big = relay.plan_of(_H(), CATS, U, 64, 2, 32, 16, 1e12)
    assert big["kept"] == list(range(1, 13)) and big["train"] == {"c1": 200, "c2": 200, "c3": 200, "c4": 200}
    cost = {int(k): v for k, v in big["cost"].items()}
    cap = 1.15 * sum(cost[n] for n in range(1, 8)) + 1.0
    mid = relay.plan_of(_H(), CATS, U, 64, 2, 32, 16, cap)
    assert mid["kept"] == list(range(1, 8)) and mid["projection"] <= cap
    tight = relay.plan_of(_H(), CATS, U, 64, 2, 32, 16, 1.15 * (cost[1] + cost[2]) * 0.9)
    assert tight["kept"] == [1, 2]
    assert tight["train"]["c4"] < 200 and tight["train"]["c1"] == 200         # the costliest category is lowered first
    capped = relay.plan_of(_H(max_cpu_per_run=50.0), CATS, U, 64, 2, 32, 16, 1e12)
    assert capped["train"] == {"c1": 200, "c2": 200, "c3": 200, "c4": 160}     # the size rule: o0 at most 50 s per run


def _stats(rng, n=20):
    N = rng.uniform(1, 30, design_r.N_CELLS)
    U = N * rng.uniform(0.0, 0.05, design_r.N_CELLS)
    e = {"kind": design_r.KIND_STATS, "v": design_r.ENTRY_V, "N": N.tolist(), "U": U.tolist(), "S": U.tolist(), "Q": U.tolist(),
         "W": N.tolist(), "SW": (N * 0.1).tolist(), "NE": [1.0, 1.0, 1.0], "UE": [0.1, 0.1, 0.1], "SE": [0.1, 0.1, 0.1],
         "QE": [0.1, 0.1, 0.1], "rounds": n, "variants": 10 * n, "informative": 7 * n, "switches": 2, "kept": True, "kept_splice": False,
         "layout": {}}
    return e


def _synthetic_ledger(effect, chains_measured=64, seed=5):
    rng = np.random.default_rng(seed)
    path = os.path.join(tempfile.mkdtemp(prefix="relay-test-"), "ledger.jsonl")
    L = ledgers.Ledger(path)
    base = 260000
    arms = {"relay": [], "frozen": []}
    for j in range(64):
        tau = rng.normal(0.0, 0.008)
        for c in CATS:
            for s in range(2):
                seed_ = base + 10 * j + s
                f = float(rng.uniform(0.5, 0.9))
                r = float(f + effect + tau + rng.normal(0.0, 0.03))
                for name, acq in (("frozen", f), ("relay", r)):
                    if name == "relay" and j >= chains_measured:
                        continue
                    if name == "frozen" and j >= chains_measured:
                        continue
                    rec = L.append({"type": "run", "key": f"{name}-{j}-{c}-{s}", "env": c, "seed": seed_, "acquired": acq, "gain": acq - 0.4,
                                    "untrained": 0.4, "threshold": 0.7, "cpu": {"acquire": 10.0, "apply": 1.0}, "units": {"train_used": 5.0},
                                    "budget": {"train": 200.0}, "report": {"program_rounds": 20, "switches": 4, "constructions": 99,
                                                                           "relay": {"new_entries": [_stats(rng)]}}})
                    arms[name].append(rec["key"])
    L.append({"type": "r_stage_done", "stage": "heldout", "categories": CATS, "train": {c: 200 for c in CATS}, "arms": arms})
    reg = {"what": "test", "version": design_r.default(), "heldout": {"seed_base": base, "alpha": {"primary": 0.01}, "secondary_chains": 32,
                                                                     "depths": [8, 4]},
           "meta": {"chains": 64, "order": ["c9"] * 12, "retention": {"chains": 0, "plan": {}}},
           "predictions": [{"id": "PX", "text": "relay minus frozen in [0.005, 0.02]",
                            "checks": [{"quantity": "endpoints / E-R1 relay minus frozen / mean", "lo": 0.005, "hi": 0.02, "expected": 0.01}]},
                           {"id": "PY", "text": "E-R1 met with probability 0.25",
                            "events": [{"quantity": "gate / E-R1", "probability": 0.25}]}]}
    return L, reg


def test_T11_the_report_rejects_a_planted_effect_and_not_the_null():
    L, reg = _synthetic_ledger(0.01)
    out = relay_report.build(L, reg)
    e = out["endpoints"]["E-R1 relay minus frozen"]
    assert e["met"] and e["complete"] and abs(e["mean"] - 0.01) < 0.004 and e["chains"] == 64, e
    assert e["bootstraps"]["chains and seeds"][0] < e["mean"] < e["bootstraps"]["chains and seeds"][1]
    assert out["gate"]["E-R1"] and not out["gate"]["E-R2"] and not out["tiers"]["T1"]   # E-R2's arm was not measured
    scored = {p["id"]: p for p in out["predictions"]}
    assert scored["PX"]["met"] is True and scored["PY"]["events"][0]["occurred"] is True
    L0, reg0 = _synthetic_ledger(0.0)
    out0 = relay_report.build(L0, reg0)
    assert not out0["endpoints"]["E-R1 relay minus frozen"]["met"]
    assert {p["id"]: p for p in out0["predictions"]}["PX"]["met"] is False
    assert out0["predictions"][0]["id"] == "PX"                                          # misses first


def test_an_endpoint_on_fewer_chains_than_registered_is_not_met():
    L, reg = _synthetic_ledger(0.02, chains_measured=32)
    e = relay_report.build(L, reg)["endpoints"]["E-R1 relay minus frozen"]
    assert e["t"] > e["critical_t"] and not e["complete"] and not e["met"], e


def test_l4_and_l6_on_planted_statistics():
    rng = np.random.default_rng(3)
    shared = rng.uniform(0.0, 0.05, design_r.N_CELLS)
    groups = {}
    for c in CATS:
        es = []
        for _ in range(3):
            N = np.full(design_r.N_CELLS, 40.0)
            es.append({"N": N.tolist(), "U": (N * (shared + rng.normal(0.0, 0.002, design_r.N_CELLS)).clip(0)).tolist()})
        groups[c] = es
    assert relay_report.l4(groups, 20.0)["mean_pairwise_spearman"] > 0.8
    noise = {c: [{"N": [40.0] * design_r.N_CELLS, "U": (40.0 * rng.uniform(0.0, 0.05, design_r.N_CELLS)).tolist()}] for c in CATS}
    assert abs(relay_report.l4(noise, 20.0)["mean_pairwise_spearman"]) < 0.4


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
