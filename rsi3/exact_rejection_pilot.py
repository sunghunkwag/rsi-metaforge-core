"""Development-only matched TRAIN study: finite-probe vs exact rejection.

The seeds, budgets and outcome metrics were frozen in
PREDICTIONS_EXACT_REJECTION_PILOT.md before running this script.
Never read VALIDATION, TEST, or J's sealed pools.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from rsi2.corpus import load_train
from rsi3.experiment import ARMS
from rsi3.loop import Runtime


def study(seeds=(11, 22), generations=2):
    config = {
        "B_wake": 16,
        "B_eval": 16,
        "dreams": 4,
        "search": {"max_size": 12, "max_expansions": 20000, "step_budget": 2000},
        "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2},
    }
    train = sorted(load_train(), key=lambda task: task.name)
    rows = []
    for seed in seeds:
        for mode in ("signature", "exact"):
            runtime = Runtime(seed, train, ARMS["RSI3_UNIFORM_FM"],
                              dict(config, binding_skip_mode=mode))
            started = time.process_time()
            for generation in range(1, generations + 1):
                before_queries = runtime.verifier.queries
                before_skips = runtime.integrator.skipped_equivalent
                record = runtime.generation()
                rows.append({
                    "seed": seed,
                    "mode": mode,
                    "generation": generation,
                    "train_solved": record["train_solved"],
                    "new_verifier_queries": runtime.verifier.queries - before_queries,
                    "total_verifier_queries": runtime.verifier.queries,
                    "new_skips": runtime.integrator.skipped_equivalent - before_skips,
                    "total_skips": runtime.integrator.skipped_equivalent,
                    "rejected_receipts": sum(
                        item.outcome == "rejected" for item in runtime.memory.episodes),
                    "logical_evaluations": runtime.state.logical_evaluations,
                    "cpu_seconds_cumulative": round(time.process_time() - started, 3),
                })
            # Code invariant: never more than one actual verify per TRAIN task/gen.
            assert runtime.verifier.queries <= len(train) * generations
    return {
        "status": "development_train_only",
        "seeds": list(seeds),
        "generations": generations,
        "train_count": len(train),
        "config": config,
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = study()
    result = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    print(result, end="")


if __name__ == "__main__":
    main()
