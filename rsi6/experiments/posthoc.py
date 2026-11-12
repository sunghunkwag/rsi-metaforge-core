"""Post hoc runs on released categories. Not registered; recorded so that nothing is run off the ledger.

    python -m rsi6.experiments.posthoc

After round b1 its gate categories (partitioning, set covering) joined the source pool. The
registered runs of that round measured generation 0 of the second design on them. This
measures generation 0 of the first design on the same fresh instances, with the same budgets
and seeds, so that the two designs can be read side by side on two categories neither was
developed on. The comparison was not registered and decides nothing; the registered comparison
of the designs is the one on the sealed targets.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles, run
from rsi6.learner import designs
from rsi6.meta import rounds

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(os.path.dirname(HERE), "ledger", "main.jsonl")


def main() -> int:
    ledger = ledgers.Ledger(LEDGER)
    reg = ledger.select(type="registration_b")[-1]["registration"]
    envs = sorted(reg["gates"]["1"]["environments"])
    if any(roles.effective_role(e, ledger) != "source" for e in envs):
        raise SystemExit("the categories are not released yet")
    cache = run.Cache(ledger)
    out = {}
    for part, seeds in (("A", reg["seeds"]["gate"]), ("B", reg["seeds"]["confirm"])):
        budget = dict(reg["budgets"]["run"], part=part)
        for design in ("a", "b"):
            rows = cache.get(rounds.jobs_for(designs.default(design), envs, seeds, budget, f"posthoc:{design}:adoption3"))
            for env in envs:
                sel = [r for r in rows if r["env"] == env]
                out.setdefault(env, {}).setdefault(design, {})[part] = {
                    "untrained": float(np.mean([r["untrained"] for r in sel])), "acquired": float(np.mean([r["acquired"] for r in sel])),
                    "gain": float(np.mean([r["gain"] for r in sel])), "cpu_per_run": float(np.mean([r["cpu"]["acquire"] + r["cpu"]["apply"] for r in sel])),
                    "runs": len(sel)}
    for env, by_design in out.items():
        for design, parts in by_design.items():
            for part, v in parts.items():
                print(f"{env:13s} design {design} half {part}: untrained {v['untrained']:.4f} acquired {v['acquired']:.4f} gain {v['gain']:+.4f} "
                      f"cpu/run {v['cpu_per_run']:.0f} ({v['runs']} runs)")
    ledger.append({"type": "posthoc", "what": "generation 0 of both designs on the released gate categories of round b1, same budgets and seeds as the gate and the confirmation; not registered", "table": out})
    return 0


if __name__ == "__main__":
    sys.exit(main())
