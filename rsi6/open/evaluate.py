"""Held-out evaluation of open mechanisms: what each acquires on categories discovery never saw.

    python -m rsi6.open.evaluate --ledger PATH --envs a,b,c --seeds 1,2,3,4 [--from LEDGER_OF_DISCOVERY ...]

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


def matched(cache, version, want: dict, purpose, levels=8):
    """``version`` with its training budget raised, pair by pair, until its CPU reaches ``want``."""
    value, last = {pair: RUN_BUDGET["train"] for pair in want}, {}
    pending = list(want)
    for _ in range(levels):
        if not pending:
            break
        got = cache.get([{"env": e, "version": version, "seed": s, "budget": dict(RUN_BUDGET, train=value[(e, s)]), "purpose": purpose}
                         for e, s in pending])
        for pair, r in zip(pending, got):
            last[pair] = r
            value[pair] *= 2.0
        pending = [p for p in pending if cpu(last[p]) < want[p]]
    return [dict(last[p], reached=cpu(last[p]) >= want[p]) for p in want]


def compare(arm, base, rng) -> dict:
    acquired, gain = {}, {}
    for env in sorted({r["env"] for r in base}):
        b = {r["seed"]: r for r in base if r["env"] == env}
        o = {r["seed"]: r for r in arm if r["env"] == env}
        acquired[env] = np.array([o[s]["acquired"] - b[s]["acquired"] for s in sorted(b)])
        gain[env] = np.array([o[s]["gain"] - b[s]["gain"] for s in sorted(b)])
    return {"min_change": both_interval(acquired, gain, rng), "acquired_change": blocked_interval(acquired, rng),
            "per_env": {e: float(v.mean()) for e, v in acquired.items()}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--envs", required=True)
    parser.add_argument("--seeds", default="1,2,3,4")
    parser.add_argument("--discovery", nargs="*", default=[], help="ledgers of discovery runs whose last accepted mechanisms are arms")
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-match", action="store_true")
    args = parser.parse_args()
    if guard.is_registered(args.ledger):
        raise SystemExit("development evaluations use a scratch ledger")
    envs, seeds = args.envs.split(","), [int(x) for x in args.seeds.split(",")]
    registered = ledgers.Ledger(guard.MAIN)
    for e in envs:
        if roles.effective_role(environments.load(e).category, registered) != "source":
            raise SystemExit(f"{e} is not a source category")
    if not os.path.exists(args.ledger):
        shutil.copy(guard.MAIN, args.ledger)
    guard.single_writer(args.ledger)
    ledger = ledgers.Ledger(args.ledger)
    cache = Cache(ledger)
    arms = {"a0": designs.default("a"), "o0": designs.default("o")}
    for path in args.discovery:
        for r in ledgers.Ledger(path).select(type="o_accept"):
            arms[f"{os.path.basename(path).split('.')[0]}:{r['lineage']}"] = r["mechanism"]          # the last one of a lineage wins
    results = {}
    for name, version in arms.items():
        results[name] = runs(cache, version, envs, seeds, f"open-eval:{name}")
        say(f"{name:28s} acquired {np.mean([r['acquired'] for r in results[name]]):.4f} gain {np.mean([r['gain'] for r in results[name]]):+.4f}"
            f" cpu/run {np.mean([cpu(r) for r in results[name]]):.1f}")
    rng = np.random.default_rng(0)
    table = {}
    for name in arms:
        if name == "o0":
            continue
        table[f"{name} minus o0"] = compare(results[name], results["o0"], rng)
        if name not in ("a0",):
            table[f"{name} minus a0"] = compare(results[name], results["a0"], rng)
            if not args.no_match:
                want = {(r["env"], r["seed"]): cpu(r) for r in results[name]}
                control = matched(cache, arms["o0"], want, f"open-eval:o0@{name}")
                table[f"{name} minus o0@{name}"] = dict(compare(results[name], control, rng),
                                                        reached=int(sum(r["reached"] for r in control)), of=len(control))
    for name, c in table.items():
        say(f"{name:40s} min-change {c['min_change'][0]:+.4f} [{c['min_change'][1]:+.4f}, {c['min_change'][2]:+.4f}] per category",
            {e: round(v, 4) for e, v in c["per_env"].items()}, "" if "reached" not in c else f"matched {c['reached']}/{c['of']}")
    if args.out:
        json.dump({"envs": envs, "seeds": seeds, "table": table,
                   "arms": {k: {"acquired": float(np.mean([r["acquired"] for r in v])), "cpu": float(np.mean([cpu(r) for r in v]))}
                            for k, v in results.items()}}, open(args.out, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
