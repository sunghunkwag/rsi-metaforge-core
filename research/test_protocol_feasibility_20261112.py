"""Tests for the static review only, not for the RSI mechanism."""
import unittest

from research.protocol_feasibility_20261112 import assess, rounds_for


class FeasibilityTests(unittest.TestCase):
    def test_category_threshold(self):
        self.assertEqual([rounds_for(i) for i in range(7, 11)], [0, 1, 1, 2])

    def test_no_early_two_round_claim(self):
        for n in range(10):
            self.assertLess(rounds_for(n), 2)

    def test_all_preregistered_arithmetic_checks(self):
        result = assess()
        self.assertTrue(result["preregistered_checks_passed"])
        self.assertEqual(result["candidate_evaluations"], 0)
        self.assertEqual(result["interpreter_calls"], 0)
        self.assertFalse(result["rsi_success_claim"])

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            rounds_for(7, adoption_per_round=0)


if __name__ == "__main__":
    unittest.main()
