"""Acceleration readouts are plain arithmetic over a run record."""
import json
import unittest
from pathlib import Path

from rsi3.acceleration import markdown, readout

RESULTS = Path(__file__).resolve().parents[1] / "results_honest" / "RSI3_META_HONEST_seed11.json"


def _record(solved, library, arm="A", seed=1):
    return {"arm": arm, "seed": seed,
            "generations": [{"generation": i + 1, "train_solved": s,
                             "sleep": {"library_entries": l}}
                            for i, (s, l) in enumerate(zip(solved, library))]}


class AccelerationTests(unittest.TestCase):
    def test_gains_growth_and_plateau(self):
        r = readout(_record([3, 5, 5, 6, 6, 6, 6, 6], [1, 1, 3, 3, 3, 4, 4, 4]))
        self.assertEqual(r["gains"], [3, 2, 0, 1, 0, 0, 0, 0])
        self.assertEqual(r["growth"], [1, 0, 2, 0, 0, 1, 0, 0])
        self.assertEqual(r["plateau"], 4)
        self.assertAlmostEqual(r["slope"]["first_half"], 1.5)
        self.assertAlmostEqual(r["slope"]["second_half"], 0.0)
        self.assertTrue(r["slope"]["decays"])
        self.assertFalse(r["accelerates"])

    def test_growth_then_gain_table(self):
        # Growth in g1 and g3 is followed by a gain in g2 and g4; the flat
        # generations are followed by nothing, so growth raises the next gain.
        r = readout(_record([2, 4, 4, 6, 6, 6], [1, 1, 2, 2, 2, 2]))
        t = r["growth_then_gain"]
        self.assertEqual((t["grew_then_gain"], t["grew_then_none"],
                          t["flat_then_gain"], t["flat_then_none"]), (2, 0, 0, 3))
        self.assertEqual(t["after_growth"], 2.0)
        self.assertEqual(t["after_none"], 0.0)
        self.assertTrue(t["raises"])
        # Held fixed at no gain in g: g3 grew (library 1 -> 2) and g4 gained 2;
        # g5 was flat and g6 gained nothing. Given a gain in g: g1 grew, g2 and g4 did not.
        self.assertEqual(t["given_no_gain"]["pairs"], (1, 1))
        self.assertTrue(t["given_no_gain"]["raises"])
        self.assertEqual(t["given_gain"]["pairs"], (1, 2))

    def test_empty_rows_give_none(self):
        r = readout(_record([1, 2, 3], [1, 2, 3]))
        self.assertIsNone(r["growth_then_gain"]["raises"])
        self.assertIsNone(r["growth_then_gain"]["after_none"])

    def test_markdown_has_one_row_per_run(self):
        rows = markdown([readout(_record([1, 2], [1, 1], seed=1)),
                         readout(_record([1, 1], [1, 1], seed=2))]).strip().split("\n")
        self.assertEqual(len(rows), 4)
        self.assertIn("| A | 2 | 1 0 |", rows[3])

    def test_registered_honest_run_decelerates_to_a_plateau(self):
        r = readout(json.loads(RESULTS.read_text(encoding="utf-8")))
        self.assertEqual(r["solved"][-1], 29)
        self.assertEqual(sum(r["gains"]), 29)
        self.assertTrue(r["slope"]["decays"])
        self.assertGreaterEqual(r["plateau"], 1)


if __name__ == "__main__":
    unittest.main()
