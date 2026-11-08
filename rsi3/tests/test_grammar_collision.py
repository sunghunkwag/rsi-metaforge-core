"""Regression checks for a real, grammar-reachable finite-probe collision.

These tests use only synthetic tasks. No sealed benchmark split is imported.
"""
import unittest

from rsi2.grammar import Grammar
from rsi3.grammar_collision_pilot import (
    MAX_AST_SIZE, MODES, SEEDS, TRIGGERS,
    candidate_pair, make_task, matches, run_arm, study, witness,
)
from rsi3.integrator import BindingIntegrator
from rsi3.verifier import public_view, term_digest


class GrammarCollisionTests(unittest.TestCase):
    def test_default_grammar_reaches_both_asts_within_size(self):
        for trigger in TRIGGERS:
            with self.subTest(trigger=trigger):
                task = make_task(SEEDS[0], trigger)
                bad, good = candidate_pair(trigger)
                grammar = Grammar()
                self.assertLessEqual(bad.size, MAX_AST_SIZE)
                self.assertLessEqual(good.size, MAX_AST_SIZE)
                self.assertIsInstance(grammar.log_probability(bad, task.request_type), float)
                self.assertIsInstance(grammar.log_probability(good, task.request_type), float)
                self.assertNotEqual(term_digest(bad), term_digest(good))

    def test_unmocked_probe_signature_collision(self):
        for trigger in TRIGGERS:
            with self.subTest(trigger=trigger):
                task = make_task(SEEDS[0], trigger)
                bad, good = candidate_pair(trigger)
                integrator = BindingIntegrator([public_view(task)])
                self.assertEqual(
                    integrator.signature(task.name, bad, {}),
                    integrator.signature(task.name, good, {}),
                )
                self.assertTrue(matches(bad, task.examples))
                self.assertTrue(matches(good, task.examples))

    def test_independent_oracle_rejects_only_bad_candidate(self):
        for trigger in TRIGGERS:
            with self.subTest(trigger=trigger):
                task = make_task(SEEDS[0], trigger)
                bad, good = candidate_pair(trigger)
                self.assertFalse(matches(bad, task.hidden))
                self.assertTrue(matches(good, task.hidden))
                self.assertEqual(len(task.hidden), 12)
                witness(SEEDS[0], trigger)

    def test_signature_exact_and_none_controls(self):
        task = make_task(11, 2)
        bad, good = candidate_pair(2)
        results = {mode: run_arm(task, bad, good, mode) for mode in MODES}
        self.assertEqual(results["signature"]["false_suppressions"], 1)
        self.assertEqual(results["signature"]["accepted_correct"], 0)
        self.assertEqual(results["signature"]["verifier_queries"], 1)
        for mode in ("exact", "none"):
            self.assertEqual(results[mode]["false_suppressions"], 0)
            self.assertEqual(results[mode]["accepted_correct"], 1)
            self.assertEqual(results[mode]["verifier_queries"], 2)
        self.assertEqual({r["logical_evaluations"] for r in results.values()}, {2})

    def test_registered_full_matrix_and_budget_accounting(self):
        result = study()
        self.assertEqual(result["case_count"], 12)
        summary = result["summary"]
        self.assertEqual(summary["signature"]["false_suppressions"], 12)
        self.assertEqual(summary["exact"]["false_suppressions"], 0)
        self.assertEqual(summary["none"]["false_suppressions"], 0)
        self.assertEqual(summary["signature"]["accepted_correct"], 0)
        self.assertEqual(summary["exact"]["accepted_correct"], 12)
        self.assertEqual(summary["none"]["accepted_correct"], 12)
        for mode in MODES:
            self.assertEqual(summary[mode]["logical_evaluations"], 24)


if __name__ == "__main__":
    unittest.main()
