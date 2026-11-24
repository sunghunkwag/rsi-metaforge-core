"""Rounds of self-modification: a search for a better version on the source pool, and a gate
on environments that no earlier round has used.

Everything here is kernel code. It decides nothing by judgement: the numbers in ``RULES`` are
registered before the first round and the decisions follow from the ledger.
"""
from __future__ import annotations

import numpy as np

from rsi6 import environments
from rsi6.kernel import roles
from rsi6.kernel.problem import BudgetExhausted, Meter, view
from rsi6.kernel.run import Cache
from rsi6.learner import designs
from rsi6.meta import space

RULES = {
    "margin": 0.005,            # a nominee must improve acquired and gain by this much, on average
    "cpu_ratio": 1.15,          # and may not use more measured CPU than this multiple of the incumbent's
    "search_cpu_ratio": 1.25,   # versions above this multiple are refused during the search already
    "bootstrap": 2000,
    "level": 0.90,
}


def cpu_of(records) -> float:
    return float(sum(r["cpu"]["acquire"] + r["cpu"]["apply"] for r in records))


def changes(base, other) -> tuple:
    """Mean change of the acquired score and of the gain: over seeds within an environment, then
    over environments."""
    envs = sorted({r["env"] for r in base})
    acquired = [np.mean([o["acquired"] - b["acquired"] for b, o in zip(base, other) if b["env"] == e]) for e in envs]
    gain = [np.mean([o["gain"] - b["gain"] for b, o in zip(base, other) if b["env"] == e]) for e in envs]
    return float(np.mean(acquired)), float(np.mean(gain))


def improvement(base, other) -> float:
    """The smaller of the two mean changes. A version that only lowers its untrained score, or
    only searches better untrained, gets nothing. (The means are taken first: the mean of
    per-run minima would be pulled down by noise alone.)"""
    return min(changes(base, other))


def breadth(base, other) -> float:
    """The improvement of a version as the continued process counts it (amendment 2). The change
    in each environment is cut to [breadth_floor, breadth_cap] before the mean over environments
    is taken, for the acquired score and for the gain, and the smaller of the two means is
    returned. A gain in one environment cannot make up for none in the others (the nominees of
    the first two rounds were carried by one category and failed their gates), and a loss
    weighs up to three times as much as a gain."""
    envs = sorted({r["env"] for r in base})
    low, high = RULES.get("breadth_floor", -0.03), RULES.get("breadth_cap", 0.01)
    acquired = [np.mean([o["acquired"] - b["acquired"] for b, o in zip(base, other) if b["env"] == e]) for e in envs]
    gain = [np.mean([o["gain"] - b["gain"] for b, o in zip(base, other) if b["env"] == e]) for e in envs]
    return float(min(np.mean(np.clip(acquired, low, high)), np.mean(np.clip(gain, low, high))))


def pool(ledger) -> list:
    """Environments whose category is in the source pool now."""
    return sorted(name for name in environments.REGISTRY
                  if roles.effective_role(environments.load(name).category, ledger) == "source")


def jobs_for(version: dict, envs, seeds, budget: dict, purpose: str) -> list:
    return [{"env": e, "version": version, "seed": s, "budget": budget, "purpose": purpose} for e in envs for s in seeds]


def search(improver: str, improver_version, start: dict, envs, seeds, budget: dict, cpu_limit: float, cache: Cache,
           tag: str, seed: int, edit_stats=None, objective=None) -> dict:
    """One improver looks for a better version than ``start`` on the source pool, within
    ``cpu_limit`` measured CPU-seconds. ``improver`` is "learner" (a version of L working on the
    space of versions) or "random" (single-field changes of the start, no use of feedback)."""
    base = cache.get(jobs_for(start, envs, seeds, budget, tag + ":start"))
    base_cpu = cpu_of(base)

    def cost(version: dict):
        records = cache.get(jobs_for(version, envs, seeds, budget, tag))
        cpu = cpu_of(records)
        if cpu > RULES["search_cpu_ratio"] * base_cpu:
            return 1.0, cpu
        return -(objective or improvement)(base, records), cpu

    meter = Meter(cpu_limit)
    problem = space.VersionProblem(start, cost, meter)
    rng = np.random.default_rng(seed)
    trace = {}
    if improver == "learner":
        learner = designs.make(improver_version)
        capability = {"kind": "assign", "weights": {}, "edit_stats": edit_stats} if edit_stats else None
        learner.apply(capability, view(problem), rng)
        trace = learner.trace
    else:
        first = problem.start_answer
        try:
            while True:
                answer = first.copy()
                k = int(rng.integers(problem.n_vars))
                choices = np.flatnonzero(problem.domain[k])
                choices = choices[choices != first[k]]
                answer[k] = int(choices[int(rng.integers(len(choices)))])
                problem.evaluate(answer)
        except BudgetExhausted:
            pass
    history = problem.history
    best = min(history, key=lambda h: h["cost"]) if history else None
    nominee = best["version"] if best is not None and best["cost"] < 0.0 else None
    expected = trace.get("expected", [])
    return {
        "type": "search", "tag": tag, "improver": improver,
        "improver_version": designs.digest(improver_version) if improver_version else None,
        "start": designs.digest(start), "envs": list(envs), "seeds": list(seeds), "cpu_limit": cpu_limit,
        "cpu_used": float(sum(h["cpu"] for h in history)), "evaluated": len(history),
        "improving": int(sum(1 for h in history if h["cost"] < 0.0)),
        "best_cost": None if best is None else best["cost"],
        "nominee": None if nominee is None else designs.digest(nominee),
        "nominee_version": nominee,
        "nominee_changes": None if nominee is None else designs.differences(start, nominee),
        "costs": [round(h["cost"], 6) for h in history],
        "expected": expected,
        "brier": None if not expected else float(np.mean([(p - y) ** 2 for p, y in expected])),
        "edit_stats": {k: trace.get(k) for k in ("kinds", "vars")} if trace else None,
    }


def gate(incumbent: dict, nominee: dict, envs, seeds, budget: dict, cache: Cache, tag: str, seed: int = 0) -> dict:
    """The adoption decision, on the half of the fresh instances reserved for it."""
    part = dict(budget, part="A")
    base = cache.get(jobs_for(incumbent, envs, seeds, part, tag + ":incumbent"))
    other = cache.get(jobs_for(nominee, envs, seeds, part, tag + ":nominee"))
    both = improvement(base, other)
    d_gain = np.array([o["gain"] - b["gain"] for b, o in zip(base, other)])
    d_acq = np.array([o["acquired"] - b["acquired"] for b, o in zip(base, other)])
    rng = np.random.default_rng(seed)
    # resample runs within each environment, then average over environments (environment as block)
    by_env = {}
    for k, record in enumerate(base):
        by_env.setdefault(record["env"], []).append(k)
    means = []
    for _ in range(RULES["bootstrap"]):
        means.append(np.mean([d_gain[rng.choice(idx, size=len(idx))].mean() for idx in by_env.values()]))
    low = float(np.quantile(means, 1.0 - RULES["level"]))
    ratio = cpu_of(other) / max(cpu_of(base), 1e-9)
    conditions = {"improvement": bool(both >= RULES["margin"]), "gain_interval": bool(low > 0.0),
                  "cpu": bool(ratio <= RULES["cpu_ratio"])}
    return {
        "type": "gate", "tag": tag, "incumbent": designs.digest(incumbent), "nominee": designs.digest(nominee),
        "envs": list(envs), "seeds": list(seeds), "mean_min": float(both), "mean_gain_change": float(d_gain.mean()),
        "mean_acquired_change": float(d_acq.mean()), "gain_lower_bound": low, "cpu_ratio": float(ratio),
        "per_env": {e: {"gain_change": float(d_gain[idx].mean()), "acquired_change": float(d_acq[idx].mean())}
                    for e, idx in by_env.items()},
        "conditions": conditions, "adopted": bool(all(conditions.values())),
        "cpu": {"incumbent": cpu_of(base), "nominee": cpu_of(other)},
    }


def confirm(incumbent: dict, nominee: dict, envs, seeds, budget: dict, cache: Cache, tag: str) -> dict:
    """After the decision: the same comparison on the other half of the fresh instances, with
    seeds the gate did not use. It decides nothing; it is the measurement the decision did not
    select on."""
    part = dict(budget, part="B")
    base = cache.get(jobs_for(incumbent, envs, seeds, part, tag + ":incumbent"))
    other = cache.get(jobs_for(nominee, envs, seeds, part, tag + ":nominee"))
    d_gain = np.array([o["gain"] - b["gain"] for b, o in zip(base, other)])
    d_acq = np.array([o["acquired"] - b["acquired"] for b, o in zip(base, other)])
    return {"type": "confirm", "tag": tag, "incumbent": designs.digest(incumbent), "nominee": designs.digest(nominee),
            "envs": list(envs), "seeds": list(seeds), "mean_gain_change": float(d_gain.mean()),
            "mean_acquired_change": float(d_acq.mean()), "mean_min": improvement(base, other),
            "runs": len(base), "cpu": {"incumbent": cpu_of(base), "nominee": cpu_of(other)}}
