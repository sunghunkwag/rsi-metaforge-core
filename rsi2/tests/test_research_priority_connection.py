"""Independent causal test of learned priorities in future candidate search."""
import unittest

from rsi2.enumeration import enumerate_programs
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.research.arity_population import solve_arity_population
from rsi2.research.repair_search import RepairSeed
from rsi2.terms import Int
from rsi2.types import INT


class PriorityConnectionTests(unittest.TestCase):
    def test_two_own_fitted_states_change_future_ast_order_with_identical_root(self):
        # Training terms originate in the system's own finite enumeration.
        # No hand-written production weight or DSL scorer supplies the order.
        def grammar():
            return Grammar(primitives={}, constants=(Int(0), Int(1), Int(2)))
        programs = [item.term for item in enumerate_programs(
            INT, grammar(), max_size=1, max_expansions=100)]
        sequences = []
        for preferred in programs[1:]:
            state = grammar()
            state.fit([preferred] * 5)
            same_state = []
            for scorer in (None, zero_heuristic()):
                result = solve_arity_population(
                    (((), 7),), INT, 3, state,
                    accepted_seeds=(RepairSeed(programs[0], 'own-enumerator:0'),),
                    seed_prefix=0, arity_context=False, production_priority=True,
                    heuristic=scorer, max_size=12, max_expansions=20000,
                    max_normalization_steps=20000)
                self.assertEqual(result.seed_candidates, 1)
                self.assertEqual(result.repair_candidates, 2)
                self.assertEqual(result.candidates, 3)
                self.assertEqual(result.trials[0]['term'], programs[0].to_dict())
                self.assertIsNone(result.trials[0]['parent_id'])
                self.assertTrue(all(row['parent_id'] is not None for row in result.trials[1:]))
                same_state.append([row['term'] for row in result.trials])
            self.assertEqual(*same_state)
            self.assertEqual(same_state[0][1], preferred.to_dict())
            sequences.append(same_state[0])
        self.assertNotEqual(*sequences)


if __name__ == '__main__':
    unittest.main()
