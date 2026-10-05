import unittest

from rsi2.grammar import Grammar
from rsi2.research.adaptive_sampling import distance, solve_sampling
from rsi2.terms import Int
from rsi2.types import INT


class AdaptiveSamplingTests(unittest.TestCase):
    def test_solution_requires_all_public_examples(self):
        result = solve_sampling([((), 1), ((), 0)], INT, 2,
                                Grammar(primitives={}, constants=(Int(0), Int(1))),
                                max_size=1)
        self.assertIsNone(result.term)
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.evaluator_calls, 4)
        self.assertGreater(result.evaluation_steps, 0)

    def test_no_habitable_program_respects_global_expansion_budget(self):
        from rsi2.types import BOOL
        result = solve_sampling([((), True)], BOOL, 64,
                                Grammar(primitives={}, constants=(Int(0),)),
                                max_expansions=7)
        self.assertEqual(result.expansions, 7)
        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.failed_draws, 7)
        self.assertEqual(result.stop_reason, "expansion_budget")

    def test_elite_learning_never_labels_near_miss_a_solution(self):
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        result = solve_sampling([((), 2)], INT, 2, grammar, adaptive=True,
                                batch=1, elite=1, max_size=1)
        self.assertIsNone(result.term)
        self.assertEqual(result.updates, 2)
        self.assertEqual(grammar.weights, {})
        self.assertEqual(len(grammar.library), 0)

    def test_seed_replays_candidate_history(self):
        grammar = Grammar()
        a = solve_sampling([((), 987)], INT, 8, grammar, adaptive=True)
        b = solve_sampling([((), 987)], INT, 8, grammar, adaptive=True)
        self.assertEqual(a.trials, b.trials)
        self.assertEqual(a.expansions, b.expansions)
        self.assertEqual(a.evaluator_calls, b.evaluator_calls)

    def test_budget_zero_does_no_generation_or_evaluation(self):
        result = solve_sampling([((), 1)], INT, 0, Grammar())
        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.evaluator_calls, 0)
        self.assertEqual(result.expansions, 0)

    def test_value_loss_preserves_bool_and_integer_type_distinction(self):
        self.assertEqual(distance(True, 1), 1)
        self.assertEqual(distance([1, 2], [1, 2]), 0)
        self.assertGreater(distance([1], [1, 2]), 0)
        self.assertLess(distance(1 << 4000, 1 << 3999), 1)


if __name__ == "__main__":
    unittest.main()
