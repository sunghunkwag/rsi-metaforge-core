"""Stage-1 evaluator/search throughput; these examples are not benchmark tasks."""
from __future__ import annotations

import argparse
import cProfile
import json
import time

from .enumeration import enumerate_programs
from .evaluator import evaluate
from .types import INT, Arrow, ListOf


def benchmark(candidates: int = 1000, max_size: int = 12) -> dict:
    examples = [list(range(n)) for n in range(12)]
    started = time.perf_counter()
    count = successful_evaluations = steps = 0
    iterator = enumerate_programs(Arrow(ListOf(INT), ListOf(INT)), max_size=max_size)
    for candidate in iterator:
        for xs in examples:
            result = evaluate(candidate.term, (xs,), step_budget=2000)
            successful_evaluations += int(result.ok)
            steps += result.steps
        count += 1
        if count >= candidates:
            break
    elapsed = time.perf_counter() - started
    return {"candidates": count, "max_size": max_size,
            "example_evaluations": count * len(examples),
            "successful_evaluations": successful_evaluations, "steps": steps,
            "wall_seconds": elapsed, "candidates_per_second": count / elapsed,
            "purpose": "Throughput only, independent of external task results"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=1000)
    parser.add_argument("--max-size", type=int, default=12)
    parser.add_argument("--profile", help="cProfile output path")
    args = parser.parse_args()
    if args.profile:
        profiler = cProfile.Profile()
        profiler.enable()
        result = benchmark(args.candidates, args.max_size)
        profiler.disable()
        profiler.dump_stats(args.profile)
    else:
        result = benchmark(args.candidates, args.max_size)
    print(json.dumps(result, indent=2))
