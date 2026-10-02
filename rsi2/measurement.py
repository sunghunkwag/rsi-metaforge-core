"""Stateless measurement over explicitly supplied search and hidden examples."""
from __future__ import annotations

import time

from .search import solve, verify


def assess(tasks, grammar, heuristic, budget, searchconfig=None, conditioner=None):
    started = time.perf_counter()
    config = dict(searchconfig or {})
    records = []
    for task in tasks:
        conditional = conditioner(task, grammar) if conditioner is not None else grammar
        result = solve(task.examples, task.request_type, budget, conditional,
                       heuristic=heuristic, **config)
        accepted = verify(result.term, task.hidden, library=grammar.library,
                          step_budget=config.get("step_budget", 2000))
        records.append({"name": task.name, "solved": accepted,
                        "candidates": result.candidates,
                        "candidates_to_solution": result.candidates if accepted else None,
                        "wall_seconds": result.wall_seconds,
                        "evaluation_steps": result.evaluation_steps,
                        "heuristic_calls": result.heuristic_calls,
                        "exhausted": result.exhausted})
    solved = [record for record in records if record["solved"]]
    return {"tasks": len(records), "solved": len(solved),
            "solved_fraction": len(solved) / len(records) if records else 0.0,
            "mean_candidates_to_solution": (sum(r["candidates"] for r in solved) / len(solved)
                                             if solved else None),
            "candidate_evaluations": sum(r["candidates"] for r in records),
            "budget": budget, "wall_seconds": time.perf_counter() - started,
            "records": records}
