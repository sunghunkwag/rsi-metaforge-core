"""Candidate accounting and the separation between search and verification."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.search import HEURISTIC_TYPE, solve, verify
from rsi2.terms import Int, Lam, Prim, Var, apply
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES, infer


class SearchTests(unittest.TestCase):
    def constant_grammar(self):
        return Grammar(primitives={}, constants=(Int(0), Int(1)),
                       weights={"int:0": 2.0, "int:1": 1.0})

    def test_budget_counts_candidates_instead_of_examples(self):
        examples = [((), 1), ((), 1), ((), 1)]
        one = solve(examples, INT, 1, self.constant_grammar(), max_size=1)
        self.assertIsNone(one.term)
        self.assertEqual(one.candidates, 1)
        two = solve(examples, INT, 2, self.constant_grammar(), max_size=1)
        self.assertEqual(two.term, Int(1))
        self.assertEqual(two.candidates, 2)
        self.assertGreater(two.evaluation_steps, one.evaluation_steps)
        self.assertTrue(verify(two.term, examples))

    def test_zero_budget_does_not_evaluate_a_task_candidate(self):
        with patch("rsi2.search.evaluate", wraps=evaluate) as interpreter:
            result = solve([((), 1)], INT, 0, self.constant_grammar(), max_size=1)
        self.assertIsNone(result.term)
        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.evaluation_steps, 0)
        interpreter.assert_not_called()

    def test_zero_dsl_heuristic_preserves_baseline_solution_and_budget_prefix(self):
        zero = Lam(ListOf(INT), Lam(ListOf(INT), Lam(INT, Lam(INT, Int(0)))))
        self.assertEqual(infer(zero), HEURISTIC_TYPE)
        for expected in (0, 1, 2):
            for budget in (0, 1, 2):
                with self.subTest(expected=expected, budget=budget):
                    baseline = solve([((), expected)], INT, budget,
                                     self.constant_grammar(), max_size=1)
                    guided = solve([((), expected)], INT, budget,
                                   self.constant_grammar(), heuristic=zero, max_size=1)
                    self.assertEqual(guided.term, baseline.term)
                    self.assertEqual(guided.candidates, baseline.candidates)
                    self.assertEqual(guided.log_probability, baseline.log_probability)
                    self.assertEqual(guided.evaluation_steps, baseline.evaluation_steps)
                    self.assertEqual(guided.exhausted, baseline.exhausted)

    def test_computed_zero_heuristic_cannot_preview_candidates_outside_baseline_prefix(self):
        computed_zero = Lam(ListOf(INT), Lam(ListOf(INT),
                            Lam(INT, Lam(INT, apply(Prim("add"), Int(0), Int(0))))))
        self.assertEqual(infer(computed_zero), HEURISTIC_TYPE)
        grammar = Grammar(
            primitives={"add": PRIMITIVE_TYPES["add"]},
            constants=(Int(0), Int(1)),
            weights={"add": 30.0, "int:0": 67.0, "int:1": 3.0},
        )
        for budget in (1, 2, 3):
            with self.subTest(budget=budget):
                baseline = solve([((), 1)], INT, budget, grammar,
                                 max_size=5, max_expansions=10000)
                guided = solve([((), 1)], INT, budget, grammar,
                               heuristic=computed_zero, max_size=5, max_expansions=10000)
                self.assertEqual(guided.term, baseline.term)
                self.assertEqual(guided.candidates, baseline.candidates)
                self.assertEqual(guided.log_probability, baseline.log_probability)
                self.assertEqual(guided.evaluation_steps, baseline.evaluation_steps)
                self.assertEqual(baseline.term, Int(1) if budget == 3 else None)

    def test_permitted_large_integer_heuristic_score_cannot_escape_or_exceed_budget(self):
        large_value = 1 << 2000
        huge = Lam(ListOf(INT), Lam(ListOf(INT), Lam(INT, Lam(INT, Int(large_value)))))
        self.assertEqual(infer(huge), HEURISTIC_TYPE)
        direct = evaluate(huge, inputs=([], [1], 1, 1))
        self.assertTrue(direct.ok, direct.error)
        self.assertEqual(direct.value, large_value)
        for budget in (0, 1, 2):
            with self.subTest(budget=budget):
                result = solve([((), 1)], INT, budget, self.constant_grammar(),
                               heuristic=huge, max_size=1)
                self.assertEqual(result.candidates, budget)
                self.assertEqual(result.term, Int(1) if budget == 2 else None)

    def test_failed_programs_consume_the_same_logical_budget(self):
        invalid = apply(Prim("div"), Int(1), Int(0))
        stream = (
            SimpleNamespace(term=invalid, log_probability=-1.0),
            SimpleNamespace(term=Int(1), log_probability=-2.0),
        )
        with patch("rsi2.search.enumerate_programs", return_value=iter(stream)):
            result = solve([((), 1)], INT, 1, self.constant_grammar())
        self.assertIsNone(result.term)
        self.assertEqual(result.candidates, 1)
        with patch("rsi2.search.enumerate_programs", return_value=iter(stream)):
            result = solve([((), 1)], INT, 2, self.constant_grammar())
        self.assertEqual(result.term, Int(1))
        self.assertEqual(result.candidates, 2)

    def test_hidden_examples_are_only_used_after_solution_selection(self):
        grammar = Grammar(primitives={}, constants=(Int(1),))
        requested = Arrow(INT, INT)
        with patch("rsi2.search.evaluate", wraps=evaluate) as interpreter:
            result = solve([((0,), 1)], requested, 20, grammar, max_size=2)
        self.assertIsNotNone(result.term)
        self.assertTrue(all(call.args[1] == (0,) for call in interpreter.call_args_list))
        count_before_verification = result.candidates
        self.assertTrue(verify(result.term, [((0,), 1)]))
        self.assertFalse(verify(result.term, [((5,), 6)]))
        # The separate hidden check does not alter the selected program or count.
        self.assertEqual(result.candidates, count_before_verification)
        self.assertEqual(infer(result.term), requested)

    def test_complete_heuristic_receives_outputs_without_double_charging(self):
        outputs_length = Lam(ListOf(INT), Lam(ListOf(INT),
                              Lam(INT, Lam(INT, apply(Prim("length"), Var(3))))))
        self.assertEqual(infer(outputs_length), HEURISTIC_TYPE)
        examples = [((), 2), ((), 3)]
        with patch("rsi2.search.evaluate", wraps=evaluate) as interpreter:
            result = solve(examples, INT, 2, self.constant_grammar(),
                           heuristic=outputs_length, max_size=1)
        self.assertIsNone(result.term)
        self.assertEqual(result.candidates, 2)
        task_calls = [call for call in interpreter.call_args_list
                      if call.args[0] != outputs_length]
        self.assertEqual(len(task_calls), 4)
        self.assertEqual([call.args[0] for call in task_calls].count(Int(0)), 2)
        self.assertEqual([call.args[0] for call in task_calls].count(Int(1)), 2)
        heuristic_inputs = [call.args[1] for call in interpreter.call_args_list
                            if call.args[0] == outputs_length]
        self.assertEqual(len(heuristic_inputs), result.heuristic_calls)
        self.assertTrue(any(values[0] == [] for values in heuristic_inputs))
        self.assertIn(([0, 0], [2, 3], 1, 1), heuristic_inputs)
        self.assertIn(([1, 1], [2, 3], 1, 1), heuristic_inputs)

    def test_unsuccessful_evaluations_supply_empty_output_features(self):
        outputs_length = Lam(ListOf(INT), Lam(ListOf(INT),
                              Lam(INT, Lam(INT, apply(Prim("length"), Var(3))))))
        invalid = apply(Prim("div"), Int(1), Int(0))

        def partial_stream(*args, **kwargs):
            state = SimpleNamespace(term=invalid, log_probability=-1.0,
                                    min_size=invalid.size, depth=invalid.depth, complete=True)
            kwargs["partial_heuristic"](state)
            yield SimpleNamespace(term=invalid, log_probability=-1.0)

        with patch("rsi2.search.enumerate_programs", side_effect=partial_stream):
            with patch("rsi2.search.evaluate", wraps=evaluate) as interpreter:
                result = solve([((), 1)], INT, 1, self.constant_grammar(),
                               heuristic=outputs_length)
        self.assertEqual(result.candidates, 1)
        heuristic_inputs = [call.args[1] for call in interpreter.call_args_list
                            if call.args[0] == outputs_length]
        self.assertEqual(heuristic_inputs, [([], [1], invalid.size, invalid.depth)])


if __name__ == "__main__":
    unittest.main()
