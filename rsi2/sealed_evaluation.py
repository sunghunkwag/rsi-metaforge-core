"""Separate evaluation capability: the only module that loads held-out TEST.

This module imports task parsing and frozen search, never a learner. Its report
is an output artifact for measurement and must not enter an adoption decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from .corpus import parse_task
from .search import solve, verify


def load_test():
    path = Path(__file__).resolve().parent / "data" / "test.json"
    return [parse_task(record) for record in json.loads(path.read_text(encoding="utf-8"))]


def report(testtasks, grammar, heuristic, budget, searchconfig=None):
    """Return hidden-verified measurements without updating any search state."""
    started = time.perf_counter()
    searchconfig = dict(searchconfig or {})
    records = []
    for task in testtasks:
        result = solve(task.examples, task.request_type, budget, grammar,
                       heuristic=heuristic, **searchconfig)
        accepted = verify(result.term, task.hidden, library=grammar.library,
                          step_budget=searchconfig.get("step_budget", 2000))
        records.append({"name": task.name, "solved": accepted,
                        "candidates": result.candidates,
                        "candidates_to_solution": result.candidates if accepted else None,
                        "wall_seconds": result.wall_seconds})
    solved = [r for r in records if r["solved"]]
    return {"tasks": len(records), "solved": len(solved),
            "solved_fraction": len(solved) / len(records) if records else 0.0,
            "mean_candidates_to_solution": (sum(r["candidates"] for r in solved) / len(solved)
                                             if solved else None),
            "budget": budget, "wall_seconds": time.perf_counter() - started,
            "records": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-only", action="store_true",
                        help="inspect partition size without attempting any task")
    args = parser.parse_args()
    if not args.metadata_only:
        parser.error("experiment orchestration supplies frozen search state; use --metadata-only here")
    print(json.dumps({"partition": "TEST", "tasks": len(load_test())}))
