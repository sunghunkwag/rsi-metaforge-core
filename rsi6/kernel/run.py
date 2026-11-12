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
from rsi6.kernel.problem import Meter
from rsi6.learner import version as versions
from rsi6.learner.learner import Learner

BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 16}


def _seed(*parts) -> int:
    return zlib.crc32("|".join(str(p) for p in parts).encode())


def _test_limit(P, budget: dict) -> float:
    if P.kind == "predict":
        return 4.0 * P.construction_units()
    return budget["test_c"] * P.construction_units() + budget["test_e"] * P.n_vars * P.n_vars


def measure(job: dict) -> dict:
    """One run. ``job``: env, version, seed, budget, purpose, and optionally memory."""
    env = environments.load(job["env"])
    budget, seed = job["budget"], int(job["seed"])
    train_ids, fresh_ids = split(env.instance_ids(), env.name, budget["n_train"], budget["n_fresh"])
    learner = Learner(job["version"])
    relabel_seed = _seed(seed, env.name, "relabel")
    meter = Meter(0.0)
    problems = [env.problem(i, meter, relabel_seed, True)[0] for i in train_ids]
    meter.limit = budget["train"] * sum(P.construction_units() for P in problems)
    started = time.process_time()
    capability, memory, report = learner.acquire(problems, np.random.default_rng(_seed(seed, env.name, "acquire")),
                                                 job.get("memory"))
    cpu_acquire = time.process_time() - started

    def scores(ids, cap):
        out, used = [], 0.0
        for i in ids:
            P, decode = env.problem(i, Meter(0.0), relabel_seed, False)
            P.meter.limit = _test_limit(P, budget)
            answer = learner.apply(cap, P, np.random.default_rng(_seed(seed, env.name, i, "apply")))
            out.append(env.score(i, decode(answer)))
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
        "n_train": len(train_ids), "n_fresh": len(fresh_ids), "threshold": env.threshold,
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
        ledger.append(result["record"])
    return results
