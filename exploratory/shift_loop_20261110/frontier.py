"""Deployment frontier of a loop's best state (exploratory, report-only).

Three vocabularies at the same per-task budget on the held-out partitions of a loop report:
  gen0     no learned symbol, full vocabulary (the machinery the loop started from)
  best     the best state: its learned symbols and its kept symbol sets
  symbols  the learned symbols with the full vocabulary (the cut lifted)
A learned vocabulary that only finds the same programs earlier is caught up by budget; one
that reaches programs generation 0 does not reach stays ahead at every budget.

    python frontier.py <loop report.json> <out.json> <budget> [<budget> ...] [--states gen0,best,symbols]
"""
from __future__ import annotations

import json
import sys
import time

from hybrid import ALL, Harness, summary
from state_run import state_spec

STATES = {"gen0": {"keep": False, "library": False},
          "best": {"keep": True, "library": True},
          "symbols": {"keep": False, "library": True}}


if __name__ == "__main__":
    report = json.load(open(sys.argv[1]))
    out_path = sys.argv[2]
    budgets = [int(a) for a in sys.argv[3:] if a.isdigit()]
    states = sys.argv[sys.argv.index("--states") + 1].split(",") if "--states" in sys.argv else list(STATES)
    held = [p for p in ALL if p not in report["learn"]]
    harness = Harness(4, ALL)
    out = {"report": sys.argv[1], "held_out": held, "rows": []}
    for budget in budgets:
        for state in states:
            started = time.perf_counter()
            result = harness.run(state_spec(report, budget, f"{state}@{budget}", **STATES[state]), partition_names=held)
            counts = summary(result)
            row = {"state": state, "budget": budget, "counts": counts, "held_out": sum(counts.values()),
                   "solved": sorted(f"{p}/{r['name']}" for p, rows in result.items() for r in rows if r["solved"]),
                   "programs": {f"{p}/{r['name']}": [r["program"], r["route"], r["to_solution"]]
                                for p, rows in result.items() for r in rows if r["solved"]},
                   "seconds": round(time.perf_counter() - started)}
            out["rows"].append(row)
            print(f"{state:8s} budget {budget:>7} held-out {row['held_out']:3d} {counts} | {row['seconds']} s", flush=True)
            json.dump(out, open(out_path, "w"), indent=1)
    harness.close()
