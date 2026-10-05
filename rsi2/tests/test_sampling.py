"""Direct random typed expansion, not selection from an enumerated prefix."""
import random
import unittest

from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.sampling import sample_program
from rsi2.terms import Int, Lam, Prim, Ref, Var, apply
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, infer, unify


class SamplingTests(unittest.TestCase):
    def test_seeded_runs_have_identical_programs(self):
        grammar = Grammar(primitives={"add": PRIMITIVE_TYPES["add"]},
                          constants=(Int(0), Int(1)))
        left, right = random.Random(19), random.Random(19)
        a = [sample_program(Arrow(INT, INT), grammar, left) for _ in range(50)]
        b = [sample_program(Arrow(INT, INT), grammar, right) for _ in range(50)]
        self.assertEqual(a, b)

    def test_sampled_programs_share_polymorphic_constraints_and_are_size_bounded(self):
        grammar = Grammar()
        rng = random.Random(20261002)
        for requested, inputs in ((INT, ()), (BOOL, ()), (ListOf(INT), ()),
                                  (Arrow(INT, INT), (2,)),
                                  (Arrow(ListOf(INT), ListOf(INT)), ([0, 2, -1],))):
            drawn = [sample_program(requested, grammar, rng, max_size=10) for _ in range(20)]
            self.assertTrue(all(term is not None for term in drawn))
            for term in drawn:
                self.assertLessEqual(term.size, 10)
                unify(infer(term), requested)
                result = evaluate(term, inputs, step_budget=2000)
                self.assertFalse(result.error and result.error.startswith("type_error"))

    def test_draws_follow_current_learned_grammar_instead_of_uniform_atoms(self):
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        grammar.fit([Int(1)] * 9)
        rng = random.Random(5)
        terms = [sample_program(INT, grammar, rng, max_size=1) for _ in range(400)]
        self.assertGreater(terms.count(Int(1)), 330)
        self.assertGreater(terms.count(Int(0)), 0)

    def test_context_and_library_productions_participate_in_sampling(self):
        entry = Lam(INT, apply(Prim("add"), Var(0), Int(1)))
        library = {"learned": entry}
        grammar = Grammar(library=library, primitives={}, constants=(Int(0),))
        solution = apply(Ref("learned"), Int(0))
        grammar.fit([solution] * 5)
        rng = random.Random(37)
        drawn = [sample_program(INT, grammar, rng, max_size=3) for _ in range(50)]
        self.assertIn(solution, drawn)
        for term in drawn:
            self.assertEqual(infer(term, library=library), INT)
            self.assertTrue(evaluate(term, library=library).ok)

    def test_uninhabited_fragment_terminates_under_attempt_bound(self):
        grammar = Grammar(primitives={}, constants=(Int(0),))
        self.assertIsNone(sample_program(BOOL, grammar, random.Random(1), max_attempts=3))
        self.assertIsNone(sample_program(INT, grammar, random.Random(1), max_attempts=0))
        self.assertIsNone(sample_program(INT, grammar, random.Random(1), max_size=0))


if __name__ == "__main__":
    unittest.main()
