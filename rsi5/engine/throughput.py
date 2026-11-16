"""The throughput micro-benchmark of OWNER_DIRECTIVE.md §3.2: candidates evaluated per
second on one core, on the standard example set (``rsi2/benchmark.py``: ``list(range(n))``
for n < 12, type ``list[int] -> list[int]``) with a target no program reaches, so the whole
budget is spent. ``rsi5/tests/test_throughput.py`` asserts the floor; ``rsi5.phase1
--throughput`` records the figure. It measures the engine only: no task, no verdict.
"""
from __future__ import annotations

import time

from ..dsl.types import Arrow, INT, ListOf
from ..dsl.vocabulary import RESTORED
from .bottomup import Engine


def measure(candidates: int = 40_000, vocabulary=RESTORED) -> dict:
    examples = [((list(range(n)),), [-999]) for n in range(12)]     # unreachable target
    engine = Engine(vocabulary)
    started = time.perf_counter()
    result = engine.search(examples, Arrow(ListOf(INT), ListOf(INT)), [], budget=candidates)
    elapsed = time.perf_counter() - started
    return {"candidates": result.candidates, "wall_seconds": elapsed,
            "candidates_per_second": result.candidates / elapsed, "vocabulary": vocabulary.name,
            "completed_size": result.completed_size, "pool_size": result.pool_size,
            "purpose": "Throughput only, independent of external task results"}
