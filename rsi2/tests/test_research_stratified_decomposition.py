"""Synthetic shared-quota and full-root checks for scalar stratified projection."""
import unittest
from unittest.mock import patch

from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research import stratified_decomposition as decomposition
from rsi2.research import stratified_search as stratified
from rsi2.terms import Int, Lam, Prim, Term
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES, infer, unify


REQUEST = Arrow(ListOf(INT), ListOf(INT))
EXAMPLES = ((([1, 2],), [-1, -2]), (([3],), [-3]))
FIELDS = {"current_performance", "failure_clusters", "bottleneck",
          "previous_attempt_insufficiency", "intervention", "mechanism",
          "verification_plan", "regression_risks", "result", "keep_revert_revise", "updated_rule"}


def _grammar():
    return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("map", "neg")}, constants=())


class StratifiedDecompositionTests(unittest.TestCase):
    def test_live_projection_is_typed_and_full_root_verified(self):
        result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64, _grammar())
        self.assertEqual(result.termination, "public_solution")
        self.assertEqual((result.head_attempts, result.component_attempts, result.root_attempts), (1, 1, 1))
        self.assertEqual(result.candidates, 3)
        self.assertEqual(result.helper_attempts, 2)
        self.assertEqual(result.example_evaluations, 1 + 3 + 2)
        self.assertEqual(result.expansions, sum(result.expansion_counts.values()))
        self.assertLessEqual(result.term.size, 12)
        unify(infer(result.term), REQUEST)
        for inputs, expected in EXAMPLES:
            self.assertEqual(evaluate(result.term, inputs).value, expected)
        self.assertEqual(set(result.report), FIELDS)
        self.assertFalse(result.report["updated_rule"]["learned_rule"])

    def test_input_roles_are_used_by_the_live_scalar_search(self):
        grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("map", "sub")},
                          constants=(Int(0), Int(1), Int(2)),
                          weights={"lambda": 0.01, "var": 0.01, "sub": 1})
        examples = ((([2, 5],), [0, 3]), (([7],), [5]))
        result = decomposition.solve_stratified_decomposition(examples, REQUEST, 64, grammar)
        self.assertEqual(result.termination, "public_solution")
        self.assertEqual(result.scalar_search["baseline_attempts"], 16)
        self.assertGreater(result.scalar_search["stratum_attempts"], 0)
        self.assertGreater(result.scalar_search["generated_wrappers"], 0)
        scalar_trials = [trial for trial in result.trials if trial["stage"] == "component"]
        self.assertEqual(len(scalar_trials), result.component_attempts)
        self.assertTrue(any(trial["source"]["stage"] == "stratum" for trial in scalar_trials))

    def test_last_scalar_candidate_match_cannot_skip_root_charge(self):
        short = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 2, _grammar())
        self.assertEqual(short.termination, "candidate_budget")
        self.assertIsNone(short.term)
        self.assertTrue(short.scalar_search["public_match"])
        self.assertEqual(short.candidates, 2)
        self.assertEqual(short.root_attempts, 0)
        enough = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 3, _grammar())
        self.assertEqual(enough.termination, "public_solution")
        self.assertEqual(enough.candidates, 3)

    def test_type_compatible_operator_failure_requires_full_public_check_without_scalar_restart(self):
        # A compatible callable need not obey the hypothesized pointwise relation.
        ignores_component = Lam(Arrow(INT, INT), Lam(ListOf(INT), Prim("nil")))
        grammar = Grammar(library={"ignore_component": ignores_component},
                          primitives={"neg": PRIMITIVE_TYPES["neg"]}, constants=())
        result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64, grammar)
        self.assertEqual(result.termination, "root_verification_failed")
        self.assertIsNone(result.term)
        self.assertTrue(result.scalar_search["public_match"])
        self.assertEqual((result.head_attempts, result.component_attempts, result.root_attempts), (1, 1, 1))
        self.assertEqual(result.trials[-1]["failure"], "public_output_mismatch")

    def test_every_call_is_charged_to_head_component_or_root_and_no_wrapper_is_executed(self):
        calls = []
        def measured(term, inputs, **limits):
            result = evaluate(term, inputs, **limits)
            calls.append((term.to_dict(), result.steps))
            return result
        with patch.object(decomposition, "evaluate", side_effect=measured), \
                patch.object(stratified, "evaluate", side_effect=measured):
            result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64, _grammar())
        self.assertEqual(result.candidates, len(result.trials))
        self.assertEqual(result.candidates, result.head_attempts + result.component_attempts + result.root_attempts)
        self.assertEqual(result.example_evaluations, len(calls))
        self.assertEqual(result.evaluator_steps, sum(steps for _, steps in calls))
        self.assertEqual(result.evaluator_steps, sum(trial["evaluator_steps"] for trial in result.trials))
        charged_terms = [trial["term"] for trial in result.trials]
        self.assertTrue(all(term in charged_terms for term, _ in calls))
        self.assertEqual([trial["index"] for trial in result.trials], list(range(result.candidates)))

    def test_shared_caps_and_component_size_reservation(self):
        for budget in (0, 1, 2, 3):
            result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, budget, _grammar())
            self.assertLessEqual(result.candidates, budget)
        for maximum in (0, 1, 2, 3, 8):
            result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64,
                                                                  _grammar(), max_expansions=maximum)
            self.assertLessEqual(result.expansions, maximum)
            self.assertEqual(result.expansions, sum(result.expansion_counts.values()))
        small = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64,
                                                              _grammar(), max_size=2)
        self.assertEqual(small.termination, "size_budget")
        self.assertEqual(small.component_attempts, 0)
        for maximum in (3, 4, 8):
            result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64,
                                                                  _grammar(), max_size=maximum)
            for trial in result.trials:
                size = Term.from_dict(trial["term"]).size
                self.assertLessEqual(size, maximum - 2 if trial["stage"] == "component" else maximum)

    def test_cpu_deadline_after_scalar_call_retains_merged_work_and_prevents_root(self):
        clock = [0.0]
        def measured(*args, **kwargs):
            result = evaluate(*args, **kwargs)
            clock[0] = 2.0
            return result
        with patch.object(decomposition.time, "process_time", side_effect=lambda: clock[0]), \
                patch.object(stratified, "evaluate", side_effect=measured):
            result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64,
                                                                  _grammar(), max_cpu_seconds=1)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertIsNone(result.term)
        self.assertEqual((result.head_attempts, result.component_attempts, result.root_attempts), (1, 1, 0))
        self.assertEqual(result.example_evaluations, 2)
        self.assertGreater(result.evaluator_steps, 0)
        self.assertEqual(result.trials[-1]["failure"], "cpu_budget")

    def test_cpu_deadline_after_final_root_match_retains_charge_and_withholds_solution(self):
        clock = [0.0]
        def measured(term, inputs, **limits):
            result = evaluate(term, inputs, **limits)
            if inputs:
                clock[0] = 2.0
            return result
        with patch.object(decomposition.time, "process_time", side_effect=lambda: clock[0]), \
                patch.object(decomposition, "evaluate", side_effect=measured):
            result = decomposition.solve_stratified_decomposition(EXAMPLES, REQUEST, 64,
                                                                  _grammar(), max_cpu_seconds=1)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertIsNone(result.term)
        self.assertEqual(result.candidates, 3)
        self.assertEqual(result.root_attempts, 1)
        self.assertEqual(result.trials[-1]["example_evaluations"], 1)
        self.assertEqual(result.trials[-1]["failure"], "cpu_budget")

    def test_inconsistent_projection_and_private_task_access_are_rejected_without_measurement(self):
        inconsistent = ((([1],), [2]), (([1],), [3]))
        result = decomposition.solve_stratified_decomposition(inconsistent, REQUEST, 64, _grammar())
        self.assertEqual(result.decomposition["reason"], "inconsistent_pointwise_relation")
        self.assertEqual(result.candidates, 0)
        class Guarded:
            examples, request_type = EXAMPLES, REQUEST
            @property
            def name(self):
                raise AssertionError("identity access")
            @property
            def hidden(self):
                raise AssertionError("private access")
        self.assertEqual(decomposition.search(Guarded(), _grammar()).termination, "public_solution")


if __name__ == "__main__":
    unittest.main()
