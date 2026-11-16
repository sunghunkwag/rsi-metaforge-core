"""test_throughput: the engine evaluates >= 10^4 candidates per second per core on the
standard micro-benchmark example set (``rsi2/benchmark.py``: ``list(range(n))`` for n < 12,
type ``list[int] -> list[int]``), with the restored vocabulary. The measurement is
``rsi5/engine/throughput.py``; ``rsi5.phase1 --throughput`` writes its figure to
``rsi5/results_p1/throughput.json``."""
import unittest

from rsi5.engine.throughput import measure

TARGET = 10_000


class Throughput(unittest.TestCase):
    def test_throughput(self):
        figures = measure()
        print(f"\nthroughput: {figures['candidates_per_second']:.0f} candidates/s "
              f"({figures['candidates']} candidates in {figures['wall_seconds']:.2f} s)")
        self.assertGreaterEqual(figures["candidates_per_second"], TARGET)


if __name__ == "__main__":
    unittest.main()
