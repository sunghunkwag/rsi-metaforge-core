"""Measured runs: one version of the learner, one environment, one seed.

A run builds the training problems of the environment with one shared meter, calls ``acquire``,
then answers the environment's fresh instances twice within the same small test-time budget:
once with no capability (*untrained*) and once with the acquired one (*acquired*). The answers
are scored against the external reference by the environment, which is the only place the
reference is read. Scores on the training instances are measured too and kept apart: they are
never the evidence of acquisition.

Compute is enforced in counted units and measured in CPU-seconds of the worker process.
"""
from __future__ import annotations

import multiprocessing
import os
import time
import zlib

import numpy as np

from rsi6 import environments
from rsi6.kernel import roles
from rsi6.kernel.environment import split
from rsi6.kernel.ledger import digest
from rsi6.kernel.environment import _order
from rsi6.kernel.problem import Meter, view
from rsi6.learner import version as versions
from rsi6.learner.learner import Learner

BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}


def _seed(*parts) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode())


def _test_limit(P, budget: dict) -> float:
    if P.kind == "predict":
        return 4.0 * P.construction_units()
    return budget["test_c"] * P.construction_units() + budget["test_e"] * P.n_vars * P.n_vars


def halves(env, fresh_ids):
    """The deciding and the confirming half of the fresh instances. Whole published groups go to
    one half, so that instances that share data (a matrix, a generator) are not split across
    the decision and its confirmation."""
    groups = {}
    for i in fresh_ids:
        groups.setdefault(env.group(i), []).append(i)
    if len(groups) < 2:
        return list(fresh_ids[0::2]), list(fresh_ids[1::2])
    a, b = [], []
    for name in sorted(_order(groups, env.name + "|parts"), key=lambda g: -len(groups[g])):
        (a if len(a) <= len(b) else b).extend(groups[name])
    return a, b


def layout(P) -> tuple:
    """The generic layout of a problem: what must be the same for every instance of an environment."""
    if P.kind == "predict":
        return ("predict", bool(P.ordered), P.ctx_x.shape[1], P.qry_x.shape[1])
    return ("assign", bool(P.ordered), P.capacity is None, tuple(P.hard.tolist()), tuple(P.detail.tolist()),
            P.var_attr.shape[1], P.opt_attr.shape[1], len(P.var_var), len(P.opt_opt), len(P.var_opt), len(P.occ_attr),
            P.domain is None, P.start_answer is None)


def _valid(P, answer) -> bool:
    """A learner's answer is scored only if it is a well-formed answer of the problem."""
    if not isinstance(answer, np.ndarray):
        return False
    if P.kind == "predict":
        return answer.dtype.kind == "f" and answer.shape == (P.n_queries,) and bool(np.all(np.isfinite(answer)))
    return answer.dtype.kind in "iu" and bool(P.well_formed(answer))


def measure(job: dict) -> dict:
    """One run. ``job``: env, version, seed, budget, purpose, and optionally memory."""
    env = environments.load(job["env"])
    budget, seed = job["budget"], int(job["seed"])
    train_ids, fresh_ids = split(env, budget["n_train"], budget["n_fresh"])
    if budget.get("part") in ("A", "B"):          # one half of the fresh instances decides, the other confirms afterwards
        fresh_ids = halves(env, fresh_ids)[0 if budget["part"] == "A" else 1]
    learner = Learner(job["version"])
    relabel = lambda i: _seed(seed, env.name, i, "relabel")      # every instance has its own relabelling
    meter = Meter(0.0)
    problems = [env.problem(i, meter, relabel(i), True)[0] for i in train_ids]
    shape = layout(problems[0])
    if any(layout(P) != shape for P in problems):
        raise RuntimeError(f"{env.name}: instances of one environment must have the same generic layout")
    meter.limit = budget["train"] * sum(P.construction_units() for P in problems)
    started = time.process_time()
    capability, memory, report = learner.acquire([view(P) for P in problems],
                                                 np.random.default_rng(_seed(seed, env.name, "acquire")), job.get("memory"))
    cpu_acquire = time.process_time() - started

    def scores(ids, cap):
        out, used = [], 0.0
        for i in ids:
            P, decode = env.problem(i, Meter(0.0), relabel(i), False)
            if layout(P) != shape:
                raise RuntimeError(f"{env.name}: instances of one environment must have the same generic layout")
            P.meter.limit = _test_limit(P, budget)
            answer = learner.apply(cap, view(P), np.random.default_rng(_seed(seed, env.name, i, "apply")))
            try:                                         # a malformed answer scores 0; it is never repaired
                out.append(float(env.score(i, decode(answer))) if _valid(P, answer) else 0.0)
            except Exception:                            # noqa: BLE001
                out.append(0.0)
            used += P.meter.used
        return out, used

    started = time.process_time()
    fresh_u, units_u = scores(fresh_ids, None)
    fresh_a, units_a = scores(fresh_ids, capability)
    cpu_apply = time.process_time() - started
    train_u, _ = scores(train_ids, None)
    train_a, _ = scores(train_ids, capability)
    record = {
        "type": "run", "purpose": job.get("purpose", ""), "env": env.name, "category": env.category,
        "version": versions.digest(job["version"]), "seed": seed, "budget": budget,
        "n_train": len(train_ids), "n_fresh": len(fresh_ids), "threshold": float(env.threshold_for(fresh_ids)),
        "fresh_ids": list(fresh_ids), "fresh_groups": sorted({env.group(i) for i in fresh_ids}),
        "train_groups": sorted({env.group(i) for i in train_ids}),
        "untrained": float(np.mean(fresh_u)), "acquired": float(np.mean(fresh_a)),
        "gain": float(np.mean(fresh_a) - np.mean(fresh_u)),
        "train_untrained": float(np.mean(train_u)), "train_acquired": float(np.mean(train_a)),
        "fresh_untrained": [round(x, 6) for x in fresh_u], "fresh_acquired": [round(x, 6) for x in fresh_a],
        "units": {"train_limit": meter.limit, "train_used": meter.used, "test_untrained": units_u, "test_acquired": units_a},
        "cpu": {"acquire": round(cpu_acquire, 3), "apply": round(cpu_apply, 3)},
        "memory_in": len((job.get("memory") or {}).get("entries", [])),
        "report": report, "capability": digest(capability),
    }
    if job.get("return_memory"):
        return {"record": record, "memory": memory}
    return {"record": record}


def key_of(job: dict) -> str:
    """What identifies a run: the same key always gives the same record apart from measured cost."""
    return digest({"env": job["env"], "version": versions.digest(job["version"]), "seed": int(job["seed"]),
                   "budget": job["budget"], "memory": digest(job.get("memory"))})


class Cache:
    """Runs already in the ledger, by key. A repeated request is served from the ledger, so a
    driver that is started again repeats nothing and reads the same numbers."""

    def __init__(self, ledger):
        self.ledger = ledger
        self.by_key = {r["key"]: r for r in ledger.records if r.get("type") == "run" and "key" in r}

    def get(self, jobs, workers: int = 4) -> list:
        missing = [job for job in jobs if key_of(job) not in self.by_key]
        seen, todo = set(), []
        for job in missing:
            k = key_of(job)
            if k not in seen:
                seen.add(k)
                todo.append(job)
        for result in run(todo, self.ledger, workers):
            self.by_key[result["record"]["key"]] = result["record"]
        return [self.by_key[key_of(job)] for job in jobs]


def run(jobs, ledger, workers: int = 4) -> list:
    """Run the jobs (role lock first), append their records to the ledger in job order, and
    return the results."""
    if os.environ.get("OPENBLAS_NUM_THREADS") != "1":
        raise RuntimeError("set OPENBLAS_NUM_THREADS=1 before starting, so that CPU-seconds are comparable")
    for job in jobs:
        job["role"] = roles.check(environments.load(job["env"]).category, ledger)
    if workers > 1 and len(jobs) > 1:
        with multiprocessing.get_context("fork").Pool(workers) as pool:
            results = pool.map(measure, jobs, chunksize=1)
    else:
        results = [measure(job) for job in jobs]
    for job, result in zip(jobs, results):
        result["record"]["role"] = job["role"]
        result["record"]["key"] = key_of(job)
        result["record"] = ledger.append(result["record"])
    return results
