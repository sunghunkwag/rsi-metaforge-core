"""One pre-learning budget calibration on the sealed VALIDATION partition.

Every task gets one generation-zero search at the maximum preregistered budget.
The first search-example solution is checked on hidden examples once, after
selection. A hidden failure ends that task; hidden examples never cause search
to continue. Smaller budgets are inferred from the same deterministic prefix.
No eligible budget produces a failed artifact, not a substituted budget.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
from pathlib import Path
import time

from .grammar import Grammar
from .search import solve, verify


SEED = 20261002
BUDGET_GRID = (16, 32, 64, 128, 256, 512, 1024)
MIN_FRACTION = 0.10
MAX_FRACTION = 0.40
MAX_SIZE = 12
MAX_EXPANSIONS = 20000
STEP_BUDGET = 2000
PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PACKAGE_ROOT / "data" / "calibration.json"
LEARNING_MODULES = ("learning.py", "abstraction.py", "recognition.py",
                    "heuristics.py", "experiment.py")


def ensure_pre_learning(package_root=PACKAGE_ROOT):
    """Protect the once-only decision before learning code is introduced."""
    present = [name for name in LEARNING_MODULES if (Path(package_root) / name).exists()]
    if present:
        raise RuntimeError("calibration is frozen after learning code exists: " + ", ".join(present))


def _calibrate_task(task):
    started = time.perf_counter()
    result = solve(task.examples, task.request_type, BUDGET_GRID[-1], Grammar(),
                   max_size=MAX_SIZE, max_expansions=MAX_EXPANSIONS,
                   step_budget=STEP_BUDGET)
    # The verifier sees only a selected program. Its result is never fed back
    # into solve, including when an example-fitting program fails hidden data.
    verification_started = time.perf_counter()
    hidden_pass = bool(verify(result.term, task.hidden, step_budget=STEP_BUDGET)) if result.term is not None else False
    verification_seconds = time.perf_counter() - verification_started
    return {
        "name": task.name,
        "request_type": task.request_type.to_dict(),
        "search_examples": len(task.examples),
        "hidden_examples": len(task.hidden),
        "candidates": result.candidates,
        "logical_cost": result.candidates,
        "first_solution_count": result.candidates if result.term is not None else None,
        "selected_program": result.term.to_dict() if result.term is not None else None,
        "selected_log_probability": result.log_probability,
        "hidden_pass": hidden_pass,
        "exhausted": result.exhausted,
        "evaluation_steps": result.evaluation_steps,
        "search_wall_seconds": result.wall_seconds,
        "hidden_verification_wall_seconds": verification_seconds,
        "wall_seconds": time.perf_counter() - started,
    }


def select_budget(grid_results):
    """Choose the first preregistered budget satisfying the inclusive gate."""
    by_budget = {row["budget"]: row for row in grid_results}
    for budget in BUDGET_GRID:
        row = by_budget.get(budget)
        if row is not None and MIN_FRACTION <= row["solved_fraction"] <= MAX_FRACTION:
            return budget
    return None


def calibrate(tasks=None, *, workers=1):
    """Run a single baseline sweep; injected tasks support synthetic unit tests.

    Production callers omit ``tasks``: only ``corpus.load_validation`` is
    imported and called. No model, library learning, heuristic, or other corpus
    partition participates. Returned task order is deterministic with workers.
    """
    if type(workers) is not int or not 1 <= workers <= 5:
        raise ValueError("workers must be an integer from 1 through 5")
    if tasks is None:
        from .corpus import load_validation
        tasks = load_validation()
    tasks = sorted(tasks, key=lambda task: task.name)
    if not tasks:
        raise ValueError("VALIDATION must contain at least one task")
    if len({task.name for task in tasks}) != len(tasks):
        raise ValueError("VALIDATION task names must be unique")
    started = time.perf_counter()
    if workers == 1:
        measured = [_calibrate_task(task) for task in tasks]
    else:
        context = multiprocessing.get_context("spawn")
        with context.Pool(min(workers, len(tasks))) as pool:
            measured = pool.map(_calibrate_task, tasks)

    grid_results = []
    for budget in BUDGET_GRID:
        solved = sum(row["hidden_pass"] and row["first_solution_count"] <= budget
                     for row in measured)
        logical_cost = sum(min(row["candidates"], budget) for row in measured)
        grid_results.append({
            "budget": budget,
            "solved": solved,
            "total": len(measured),
            "solved_fraction": solved / len(measured),
            "logical_cost": logical_cost,
            "mean_candidates": logical_cost / len(measured),
        })
    chosen = select_budget(grid_results)
    return {
        "schema_version": 1,
        "status": "passed" if chosen is not None else "failed",
        "failure_reason": None if chosen is not None else
            "No preregistered budget yields 10% through 40% hidden-verified VALIDATION success.",
        "seed": SEED,
        "partition": "VALIDATION",
        "baseline": "generation-zero grammar, empty library, no recognition, heuristic zero",
        "budget_grid": list(BUDGET_GRID),
        "gate": {"minimum": MIN_FRACTION, "maximum": MAX_FRACTION,
                 "inclusive": True, "selection": "earliest eligible grid value"},
        "B_wake": chosen,
        "B_eval": chosen,
        "search": {"max_size": MAX_SIZE, "max_expansions": MAX_EXPANSIONS,
                   "step_budget": STEP_BUDGET},
        "workers": workers,
        "grid_results": grid_results,
        "tasks": measured,
        "logical_cost": sum(row["candidates"] for row in measured),
        "search_wall_seconds_sum": sum(row["search_wall_seconds"] for row in measured),
        "wall_seconds": time.perf_counter() - started,
        "method": "One maximum-budget search per task; smaller budgets inferred from its first selected solution. Hidden failures never resume search.",
    }


def save_calibration(result, path=DEFAULT_OUTPUT, *, force=False, package_root=PACKAGE_ROOT):
    """Save the reviewable decision once; explicit force is pre-learning only."""
    ensure_pre_learning(package_root)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if force else "x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_calibration(path=DEFAULT_OUTPUT):
    """Return frozen budgets only from a passed, internally consistent artifact."""
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    if result.get("status") != "passed":
        raise ValueError("calibration gate did not pass; learning must not proceed")
    chosen = select_budget(result.get("grid_results", ()))
    if chosen is None or result.get("B_wake") != chosen or result.get("B_eval") != chosen:
        raise ValueError("calibration artifact does not contain the earliest eligible frozen budget")
    if result.get("seed") != SEED or result.get("budget_grid") != list(BUDGET_GRID):
        raise ValueError("calibration artifact differs from the preregistered seed/grid")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true",
                        help="Overwrite only with explicit Owner/root permission before learning code exists.")
    args = parser.parse_args(argv)
    ensure_pre_learning()
    if args.output.exists() and not args.force:
        raise FileExistsError(f"calibration already exists: {args.output}; it is a once-only measurement")
    result = calibrate(workers=args.workers)
    save_calibration(result, args.output, force=args.force)
    print(json.dumps({"status": result["status"], "B_wake": result["B_wake"],
                      "B_eval": result["B_eval"], "output": str(args.output),
                      "failure_reason": result["failure_reason"]}, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
