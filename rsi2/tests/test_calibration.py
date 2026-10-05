"""Calibration selection checks on patched synthetic measurement streams."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rsi2.calibrate import (
    BUDGET_GRID, calibrate, ensure_pre_learning, load_calibration, save_calibration,
    select_budget,
)
from rsi2.search import SearchResult
from rsi2.terms import Int
from rsi2.types import INT


def tasks(count=10):
    return [SimpleNamespace(name=f"task{i:02}", request_type=INT,
                            examples=(((i,), i),), hidden=(((i + 10,), i + 10),))
            for i in range(count)]


class CalibrationTests(unittest.TestCase):
    def measure(self, solution_counts, hidden_fail=()):
        recorded = []

        def fake_solve(examples, requested, budget, grammar, **kwargs):
            index = examples[0][0][0]
            recorded.append((index, budget, kwargs))
            count = solution_counts.get(index)
            return SearchResult(Int(index) if count is not None else None,
                                count if count is not None else budget,
                                -1.0 if count is not None else None, 0.25,
                                7, 0, False)

        def fake_verify(term, hidden, **kwargs):
            return term.value not in hidden_fail

        with patch("rsi2.calibrate.solve", side_effect=fake_solve), \
                patch("rsi2.calibrate.verify", side_effect=fake_verify) as verifier:
            result = calibrate(reversed(tasks()))
        return result, recorded, verifier.call_count

    def test_earliest_eligible_grid_budget_is_frozen_from_one_sweep(self):
        result, recorded, verifications = self.measure({0: 17, 1: 31, 2: 64, 3: 256, 4: 1024})
        self.assertEqual(result["status"], "passed")
        self.assertEqual((result["B_wake"], result["B_eval"]), (32, 32))
        self.assertEqual([row["solved"] for row in result["grid_results"]], [0, 2, 3, 3, 4, 4, 5])
        self.assertEqual([row[0] for row in recorded], list(range(10)))
        self.assertTrue(all(row[1] == 1024 for row in recorded))
        self.assertTrue(all(row[2] == {"max_size": 12, "max_expansions": 20000,
                                      "step_budget": 2000} for row in recorded))
        self.assertEqual(verifications, 5)
        self.assertEqual(result["logical_cost"], 17 + 31 + 64 + 256 + 1024 + 5 * 1024)

    def test_hidden_failure_never_resumes_search_or_counts_as_solved(self):
        result, recorded, verifications = self.measure({0: 1, 1: 20}, hidden_fail=(0,))
        self.assertEqual(result["B_eval"], 32)
        self.assertFalse(result["tasks"][0]["hidden_pass"])
        self.assertEqual(result["tasks"][0]["first_solution_count"], 1)
        self.assertEqual(len(recorded), 10)
        self.assertEqual(verifications, 2)
        self.assertEqual(result["grid_results"][0]["solved"], 0)

    def test_out_of_range_fractions_fail_without_fallback(self):
        for counts in ({}, {index: 1 for index in range(10)}):
            with self.subTest(counts=counts):
                result, _, _ = self.measure(counts)
                self.assertEqual(result["status"], "failed")
                self.assertIsNone(result["B_wake"])
                self.assertIsNone(result["B_eval"])
                self.assertIn("No preregistered budget", result["failure_reason"])

    def test_selection_ignores_unregistered_budgets(self):
        self.assertIsNone(select_budget([{"budget": 7, "solved_fraction": 0.20}]))
        self.assertEqual(select_budget([{"budget": 16, "solved_fraction": 0.10}]), 16)
        self.assertEqual(select_budget([{"budget": 16, "solved_fraction": 0.40}]), 16)

    def test_existing_artifact_is_not_overwritten_and_force_is_pre_learning_only(self):
        result, _, _ = self.measure({0: 20})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "data" / "calibration.json"
            save_calibration(result, path, package_root=root)
            self.assertEqual(load_calibration(path)["B_eval"], 32)
            with self.assertRaises(FileExistsError):
                save_calibration(result, path, package_root=root)
            save_calibration(result, path, force=True, package_root=root)
            (root / "learning.py").write_text("", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                save_calibration(result, path, force=True, package_root=root)
            with self.assertRaises(RuntimeError):
                ensure_pre_learning(root)

    def test_failed_or_inconsistent_artifact_cannot_start_learning(self):
        result, _, _ = self.measure({0: 20})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            for change in ({"status": "failed"}, {"B_eval": 1024}, {"seed": 999}):
                with self.subTest(change=change):
                    path.write_text(json.dumps({**result, **change}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_calibration(path)

    def test_invalid_worker_count_and_empty_validation_are_rejected(self):
        for workers in (0, 6, True):
            with self.assertRaises(ValueError):
                calibrate(tasks(), workers=workers)
        with self.assertRaises(ValueError):
            calibrate([])


if __name__ == "__main__":
    unittest.main()
