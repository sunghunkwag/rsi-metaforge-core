"""test_throughput: the engine evaluates >= 10^4 candidates per second per core on the
standard micro-benchmark example set (``rsi2/benchmark.py``: ``list(range(n))`` for n < 12,
type ``list[int] -> list[int]``), with the restored vocabulary. The measured figure is
printed and written to ``rsi5/results_p1/throughput.json`` by ``rsi5.phase1``."""
import time
import unittest

from rsi5.dsl.types import Arrow, INT, ListOf
from rsi5.dsl.vocabulary import RESTORED
from rsi5.engine.bottomup import Engine

TARGET = 10_000


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


class Throughput(unittest.TestCase):
    def test_throughput(self):
        figures = measure()
        print(f"\nthroughput: {figures['candidates_per_second']:.0f} candidates/s "
              f"({figures['candidates']} candidates in {figures['wall_seconds']:.2f} s)")
        self.assertGreaterEqual(figures["candidates_per_second"], TARGET)


if __name__ == "__main__":
    unittest.main()
