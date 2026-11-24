"""Held-out evaluation of open mechanisms: what each acquires on categories discovery never saw.

The functions the experiment's stages and its report use (``runs``, ``raise_until``,
``compare``); the stages are in ``experiment.py`` and the report in ``report.py``.

Arms, all measured by the kernel at the registered run budget on the given categories and
seeds, with empty memory:

  a0           generation 0 of the first design (the strongest human-written baseline here)
  o0           generation 0 of the open design (where discovery started)
  <lineage>    the last mechanism a discovery lineage accepted
  o0@<arm>     o0 with its training budget raised, pair by pair, until its measured CPU
               reaches that of <arm> (the compute-matched control for that arm)

Differences are paired by category and seed; the interval resamples categories and, within
each, seeds (the statistic of the registration: the smaller of the mean change of the
acquired score and of the gain). The development ledger records every run.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import zlib

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6 import environments
from rsi6.experiments import guard
from rsi6.experiments.report import blocked_interval, both_interval
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles
from rsi6.kernel.run import Cache
from rsi6.learner import designs

RUN_BUDGET = {"train": 40.0, "test_c": 2.0, "test_e": 1.0, "n_train": 16, "n_fresh": 24}


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def cpu(r) -> float:
    return r["cpu"]["acquire"] + r["cpu"]["apply"]


def runs(cache, version, envs, seeds, purpose, budget=RUN_BUDGET):
    return cache.get([{"env": e, "version": version, "seed": s, "budget": budget, "purpose": purpose} for e in envs for s in seeds])


def raise_until(cache, version, want: dict, purpose, budget=RUN_BUDGET) -> list:
    """``version`` with its training budget raised, pair by pair, until its measured CPU reaches
    ``want`` (the schedule of amendment 4, reading d, as in ``experiments/targets.py``): doubled
    at first, then by the factor that the measured CPU of the last two levels says is needed with
    a tenth to spare, at least 2 and at most 64 per level, 64 when the CPU did not rise, at most
    twelve levels counting the registered budget as the first. A pair still below its CPU after
    the last level is marked not reached; a comparison with it is void."""
    value = {pair: budget["train"] for pair in want}
    last, seen = {}, {pair: [] for pair in want}
    pending = list(want)
    for _ in range(12):
        if not pending:
            break
        jobs = [{"env": e, "version": version, "seed": s, "budget": dict(budget, train=value[(e, s)]), "purpose": purpose}
                for e, s in pending]
        got = []
        for k in range(0, len(jobs), 4):                   # in small batches, so that a stopped driver loses little
            got += cache.get(jobs[k:k + 4])
        for pair, r in zip(pending, got):
            last[pair] = r
            seen[pair].append((value[pair], cpu(r)))
            factor = 2.0
            if len(seen[pair]) >= 2:
                (v1, c1), (v2, c2) = seen[pair][-2:]
                slope = (c2 - c1) / (v2 - v1)
                factor = 64.0 if slope <= 0 else min(64.0, max(2.0, (v2 + (1.1 * want[pair] - c2) / slope) / v2))
            value[pair] *= factor
        pending = [p for p in pending if cpu(last[p]) < want[p]]
    return [dict(last[p], reached=cpu(last[p]) >= want[p], levels=len(seen[p]), matched_cpu=want[p]) for p in want]


def matched(cache, version, want: dict, purpose, levels=12):
    """The development name of ``raise_until``."""
    return raise_until(cache, version, want, purpose)


def compare(arm, base, rng=None, name="", control=False) -> dict:
    """``arm`` minus ``base``, paired by category and seed: the registered statistic with its
    interval, the acquired score, the untrained score and the gain separately, the sign of every
    category, and the CPU of the pairs. When ``base`` is a control (``control=True``) the
    comparison is ``void`` if the control received less CPU than the arm in any pair or did not
    reach its matched CPU (registration.json, failure conditions): a void comparison is reported
    as such, not as evidence. Between two arms of discovery, which had equal discovery CPU and the
    same cap, the CPU ratio is reported and nothing is voided."""
    rng = rng if rng is not None else np.random.default_rng(zlib.crc32(name.encode()))
    cells = {(r["env"], r["seed"]) for r in base}
    if cells != {(r["env"], r["seed"]) for r in arm} or len(cells) != len(base) or len(cells) != len(arm):
        raise ValueError(f"{name}: the two sides do not hold one run of every category and seed")
    acquired, gain, untrained = {}, {}, {}
    for env in sorted({e for e, _ in cells}):
        b = {r["seed"]: r for r in base if r["env"] == env}
        o = {r["seed"]: r for r in arm if r["env"] == env}
        acquired[env] = np.array([o[s]["acquired"] - b[s]["acquired"] for s in sorted(b)])
        gain[env] = np.array([o[s]["gain"] - b[s]["gain"] for s in sorted(b)])
        untrained[env] = np.array([o[s]["untrained"] - b[s]["untrained"] for s in sorted(b)])
    by = {(r["env"], r["seed"]): r for r in base}
    less = int(sum(cpu(by[(r["env"], r["seed"])]) < cpu(r) for r in arm))
    unreached = int(sum(1 for r in base if r.get("reached") is False))
    return {"min_change": both_interval(acquired, gain, rng), "acquired_change": blocked_interval(acquired, rng),
            "gain_change": blocked_interval(gain, rng), "untrained_change": blocked_interval(untrained, rng),
            "per_env": {e: float(v.mean()) for e, v in acquired.items()},
            "all_categories_positive": bool(all(min(acquired[e].mean(), gain[e].mean()) > 0 for e in acquired)),
            "cpu_ratio": float(sum(cpu(r) for r in arm) / max(sum(cpu(r) for r in base), 1e-9)),
            "pairs_base_with_less_cpu": less, "pairs_unreached": unreached, "control": control,
            "void": bool(control and (less or unreached))}



