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


# ---- the held-out stage on a deterministic fake cache: replay, the plan's re-projection, the futility look -----
class _Stop(Exception):
    pass


class _LedgerCache:
    """Stands in for the kernel's cache: a run is a deterministic function of its job, written to the
    ledger when its submission is done. ``stop_at``: the submission during which the stage is stopped
    (its runs are lost, as a killed driver's are)."""

    def __init__(self, ledger, stop_at=None):
        from rsi6.kernel.run import key_of
        self.key_of, self.ledger, self.stop_at, self.calls = key_of, ledger, stop_at, 0
        self.by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run"}

    def record(self, job):
        key = self.key_of(job)
        h = int(key[:12], 16)
        u = lambda k: ((h >> (4 * k)) % 1000) / 1000.0
        memory = job.get("memory")
        design = job["version"].get("design", "a")
        cpu = {"c1": 20.0, "c2": 30.0, "c3": 12.0}[job["env"]] * job["budget"]["train"] / 200.0 * (0.95 + 0.1 * u(0))
        if design == "r" and memory is not None and job["env"] == "c2":
            cpu *= 1.3                                         # relay's CPU is above frozen's on c2: the CPU rule applies there
        untrained = 0.4 if design != "a" else 0.35
        acquired = 0.5 + 0.2 * u(1) + (0.01 if memory is not None else 0.0)
        return {"type": "run", "key": key, "env": job["env"], "seed": job["seed"], "budget": job["budget"], "purpose": job["purpose"],
                "acquired": acquired, "untrained": untrained, "gain": acquired - untrained, "threshold": 0.6,
                "cpu": {"acquire": round(cpu, 3), "apply": 1.0}, "units": {"train_used": 5.0},
                "report": {"program_rounds": 20, "switches": 4, "constructions": 99,
                           "relay": {"new_entries": [_stats(np.random.default_rng(h % 2 ** 32))]}}}

    def get(self, jobs, workers=4):
        self.calls += 1
        if self.stop_at is not None and self.calls == self.stop_at:
            raise _Stop()
        out = []
        for job in jobs:
            key = self.key_of(job)
            if key not in self.by_key:
                self.by_key[key] = self.ledger.append(self.record(job))
            out.append(self.by_key[key])
        return out


def _heldout_reg(J=6, **heldout):
    from rsi6.learner import dispatch_extra
    dispatch_extra.install()
    H = {"categories": [], "role": "fresh", "seed_base": 700000, "seeds": 2, "secondary_chains": 4, "depths": [2, 1], "reference_chains": 2,
         "cpu_model": {"o0": {"a": 0.0, "b": 1.0, "d": 0.0}, "r0_over_o0": 1.2}, "train_grid": [200, 160, 120, 80, 40], "max_cpu_per_run": 60.0,
         "machine_factor": 1.15, "cpu_total": 1e9, "cpu_development": 0.0, "cpu_reserve": 0.0, "matched_levels": 2, "ceiling_cost": 3.8,
         "cpu_tolerance": 1.10, "futility_t": -99.0, "ceiling_factor": 4, "alpha": {"primary": 0.01}}
    H.update(heldout)
    return {"what": "test", "version": design_r.default(), "dev_heldout": ["c1", "c2", "c3"], "heldout": H,
            "budgets": {"heldout": {"train": 200.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}},
            "meta": {"chains": J, "order": ["s1", "s2", "s3"], "retention": {"chains": 0, "plan": {}}}}


def _memories(J):
    lib = {"kind": design_r.KIND_LIB, "v": 1, "blocks": [{"part": "score", "block": [["scale", 3, 3, -1]], "fresh": 1, "term": False},
                                                          {"part": "pick", "block": [["load", 2, 1, 0], ["add", 0, 0, 2]], "fresh": 0, "term": True}]}
    on = {}
    for j in range(J):
        rng = np.random.default_rng(1000 + j)
        entries = []
        on[j] = {0: None}
        for d in (1, 2, 3):
            entries = entries + [_stats(rng), lib]
            on[j][d] = design_r.mem(entries)
    return {"on": on, "off": {j: design_r.mem([_stats(np.random.default_rng(2000 + j))]) for j in range(J)}}


def _run_stage(reg, path, stop_at=None):
    class Args:
        dev = True
    units, load = relay.units, relay.environments.load
    relay.units = lambda env: {"train": {"c1": 0.1, "c2": 0.15, "c3": 0.06}[env], "test": 0.0, "all_fresh_have_start_answers": False}
    relay.environments.load = lambda c: c
    quiet, relay.say = relay.say, lambda *a: None
    try:
        ledger = ledgers.Ledger(path)
        cache = _LedgerCache(ledger, stop_at)
        relay.run_heldout(reg, cache, ledger, _memories(reg["meta"]["chains"]), Args())
        return cache.calls
    finally:
        relay.units, relay.environments.load, relay.say = units, load, quiet


def _body(path):
    return [{k: v for k, v in r.items() if k not in ("idx", "prev", "h")} for r in ledgers.Ledger(path).records]


def _replays(reg, tag):
    """The stage run whole, and stopped during each of its submissions in turn and started again: the same ledger."""
    base = tempfile.mkdtemp(prefix=f"relay-{tag}-")
    whole = os.path.join(base, "whole.jsonl")
    calls = _run_stage(reg, whole)
    want = _body(whole)
    for stop_at in range(1, calls + 1):
        path = os.path.join(base, f"stop{stop_at}.jsonl")
        try:
            _run_stage(reg, path, stop_at)
            raise AssertionError("the stage was not stopped")
        except _Stop:
            pass
        _run_stage(reg, path)
        assert _body(path) == want, (tag, stop_at)
    return ledgers.Ledger(whole), calls


def test_T10_a_stopped_stage_replays_and_agrees_plain():
    reg = _heldout_reg()
    L, calls = _replays(reg, "plain")
    types = [r["type"] for r in L.records if r["type"].startswith("r_")]
    done = {r["item"]: r["done"] for r in L.select(type="r_item")}
    assert all(done[n] for n in range(1, 13)) and calls > 20, (done, calls)
    rule = {(r["arm"], r["part"]): r for r in L.select(type="r_cpu_rule")}
    assert rule[("frozen", "a")]["matched_categories"] == ["c2"] and rule[("shuffled", None)]["matched_categories"] == []
    matched = {(m["arm"], m["part"]) for m in L.select(type="r_matched")}
    assert {("frozen@relay", "a"), ("frozen@relay", "b"), ("o0@relay", None), ("a0@relay", None)} <= matched, matched
    arms = L.select(type="r_stage_done", stage="heldout")[0]["arms"]
    assert len(arms["relay"]) == len(arms["frozen"]) == 6 * 3 * 2 and len(arms["frozen@relay"]) == 6 * 2      # c2 only, both halves
    assert len(arms["o0"]) == len(arms["o0@relay"]) == 4 * 3 * 2 and len(arms["a0"]) == len(arms["a0@relay"]) == 2 * 3
    # relay and frozen are submitted side by side: within a submission the two arms alternate
    first = [r["purpose"].split(":")[1] for r in L.records if r["type"] == "run"][:8]
    assert first == ["relay", "frozen"] * 4, first
    out = relay_report.build(L, reg)
    e = out["endpoints"]["E-R1 relay minus frozen"]
    assert e["comparator raised to relay's CPU on"] == ["c2"] and "against the comparator at the registered budget" in e
    # the CPU of the pairs that enter, and nothing else: the raised comparator has more CPU than relay, the plain one less
    assert e["cpu_ratio"] < 1.0 < e["against the comparator at the registered budget"]["cpu_ratio"] < 1.2
    assert 0.9 < out["endpoints"]["E-R2 relay minus shuffled"]["cpu_ratio"] < 1.1
    assert out["m_net"]["complete"] and out["m_net"]["value"] is not None and out["diagnostics"]["L8 depth curve"]["slope"] is not None
    assert out["diagnostics"]["untrained answers identical across the arms of designs r and o"] is True


def test_T10_replay_with_a_futility_stop_on_fewer_primary_chains_than_secondaries():
    reg = _heldout_reg(futility_t=99.0)
    L, _ = _replays(reg, "futility")
    done = {r["item"]: (r["done"], r.get("why")) for r in L.select(type="r_item")}
    assert [n for n in done if done[n][0]] == [1, 4, 7, 11, 12] and all("futility" in done[n][1] for n in relay.FUTILE)
    arms = L.select(type="r_stage_done", stage="heldout")[0]["arms"]
    assert len(arms["relay"]) == 3 * 3 * 2                                   # chains 0, 1, 2 only
    assert len(arms["o0@relay"]) == 3 * 3 * 2 and len(arms["frozen@ceiling"]) == 3 * 3      # the items that still run cover those chains
    out = relay_report.build(L, reg)
    e = out["endpoints"]["E-R1 relay minus frozen"]
    assert e["complete"] is False and e["met"] is False and out["m_net"]["value"] is None and out["m_net"]["complete"] is False
    assert out["diagnostics"]["L8 depth curve"]["slope"] is None
    assert out["futility look"]["stop"] is True


def test_T10_replay_with_the_cap_dropping_items_and_stopping_the_stage():
    whole = _heldout_reg()
    path = os.path.join(tempfile.mkdtemp(prefix="relay-cost-"), "l.jsonl")
    _run_stage(whole, path)
    L = ledgers.Ledger(path)
    spent = lambda upto: sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in L.records[:upto] if r["type"] == "run")
    at = {r["item"]: r["idx"] for r in L.select(type="r_item")}
    # a total that lets the stage run through item 5 or so, then drop from the end, then stop
    total = 1.15 * spent(at[5]) * 1.25
    reg = _heldout_reg(cpu_total=total)
    L2, _ = _replays(reg, "cap")
    done = {r["item"]: (r["done"], r.get("why")) for r in L2.select(type="r_item")}
    drops, caps = L2.select(type="r_drop"), L2.select(type="r_cap")
    assert drops or caps or any(why and "CPU plan" in why for _, why in done.values()), (done, drops, caps)
    ran = [n for n in sorted(done) if done[n][0]]
    assert ran[:2] == [1, 2] and len(ran) < 12, ran
    stage = L2.select(type="r_stage_done", stage="heldout")
    assert len(stage) == 1
    out = relay_report.build(L2, reg)                                        # the report runs on what was measured
    assert "endpoints" in out and out["tiers"]["T3"] is False


def test_the_comparator_is_not_weakened_by_being_given_more_cpu():
    """E-R1 must hold against frozen raised to relay's CPU and against frozen at the registered budget."""
    L, reg = _synthetic_ledger(0.012)
    arms = L.select(type="r_stage_done", stage="heldout")[0]["arms"]
    by_key = {r["key"]: r for r in L.records if r["type"] == "run"}
    raised = []
    for k in arms["frozen"]:
        r = by_key[k]
        if r["env"] == "c1":                                   # the raised copy of frozen on c1 does much worse
            rec = L.append(dict({x: r[x] for x in r if x not in ("idx", "prev", "h")}, key=k + "-raised", acquired=r["acquired"] - 0.2,
                                gain=r["gain"] - 0.2))
            raised.append(rec["key"])
    L.append({"type": "r_cpu_rule", "arm": "frozen", "part": "a", "ratios": {"c1": 1.2}, "matched_categories": ["c1"]})
    arms2 = dict(arms, **{"frozen@relay": raised})
    L.append({"type": "r_stage_done", "stage": "heldout", "categories": CATS, "train": {c: 200 for c in CATS}, "arms": arms2})
    out = relay_report.build(L, reg)
    e = out["endpoints"]["E-R1 relay minus frozen"]
    raw = e["against the comparator at the registered budget"]
    assert e["mean"] > raw["mean"] + 0.03 and raw["single_test"] and e["single_test"] and e["met"]      # both hold here
    # with no true effect the weakened comparator alone would pass; the registered budget's test stops it
    L0, reg0 = _synthetic_ledger(0.0)
    arms = L0.select(type="r_stage_done", stage="heldout")[0]["arms"]
    by_key = {r["key"]: r for r in L0.records if r["type"] == "run"}
    raised = [L0.append(dict({x: by_key[k][x] for x in by_key[k] if x not in ("idx", "prev", "h")}, key=k + "-raised",
                             acquired=by_key[k]["acquired"] - 0.2, gain=by_key[k]["gain"] - 0.2))["key"] for k in arms["frozen"] if by_key[k]["env"] == "c1"]
    L0.append({"type": "r_cpu_rule", "arm": "frozen", "part": "a", "ratios": {"c1": 1.2}, "matched_categories": ["c1"]})
    L0.append({"type": "r_stage_done", "stage": "heldout", "categories": CATS, "train": {c: 200 for c in CATS}, "arms": dict(arms, **{"frozen@relay": raised})})
    e0 = relay_report.build(L0, reg0)["endpoints"]["E-R1 relay minus frozen"]
    assert e0["t"] > e0["critical_t"] and not e0["against the comparator at the registered budget"]["single_test"] and not e0["single_test"] and not e0["met"]


def test_the_sign_flip_test_agrees_with_t_on_a_planted_effect_and_on_the_null():
    for effect, want in ((0.012, True), (0.0, False)):
        L, reg = _synthetic_ledger(effect)
        reg["heldout"]["test"] = "signflip"
        e = relay_report.build(L, reg)["endpoints"]["E-R1 relay minus frozen"]
        assert e["test"] == "signflip" and e["single_test"] is want and (e["p"] <= 0.01) is want, (effect, e["p"])
    rng = np.random.default_rng(1)
    x = rng.normal(0.0, 1.0, 64)
    rows_a = [{"env": "c", "seed": 10 * j, "acquired": float(v), "gain": float(v), "cpu": {"acquire": 1.0, "apply": 0.0}} for j, v in enumerate(x)]
    rows_b = [{"env": "c", "seed": 10 * j, "acquired": 0.0, "gain": 0.0, "cpu": {"acquire": 1.0, "apply": 0.0}} for j in range(64)]
    e_t = relay_report.endpoint("x", rows_a, rows_b, lambda s: s // 10, 0.05, "t")
    e_s = relay_report.endpoint("x", rows_a, rows_b, lambda s: s // 10, 0.05, "signflip")
    assert abs(e_t["p"] - e_s["p"]) < 0.03, (e_t["p"], e_s["p"])                    # the two tests agree closely on normal data


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
