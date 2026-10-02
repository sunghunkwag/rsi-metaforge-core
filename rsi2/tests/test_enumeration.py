"""Finite, independently checkable examples of typed probability search."""

import itertools
import math
import unittest

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.terms import Bool, Int, Lam, Prim, Ref, Var, apply
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, infer, unify


class EnumerationTests(unittest.TestCase):
    def test_constant_only_grammar_has_exact_probabilities_and_order(self):
        grammar = Grammar(
            primitives={}, constants=(Int(0), Int(1)),
            weights={"int:0": 1.0, "int:1": 3.0},
        )
        candidates = list(enumerate_programs(INT, grammar=grammar, max_size=1))
        self.assertEqual([candidate.term for candidate in candidates], [Int(1), Int(0)])
        for candidate, probability in zip(candidates, (0.75, 0.25)):
            self.assertAlmostEqual(candidate.log_probability, math.log(probability))
            self.assertAlmostEqual(candidate.score, candidate.log_probability)

    def test_parent_and_argument_context_changes_a_compositional_prior(self):
        grammar = Grammar(
            primitives={"add": PRIMITIVE_TYPES["add"]},
            constants=(Int(0), Int(1)),
            weights={"add": 1.0, "int:0": 2.0, "int:1": 1.0},
            context_weights={("add", 0): {"int:1": 8.0}},
        )
        candidates = list(enumerate_programs(INT, grammar=grammar, max_size=5))
        expected = (
            (Int(0), 2 / 4),
            (Int(1), 1 / 4),
            (apply(Prim("add"), Int(1), Int(0)), (1 / 4) * (8 / 11) * (2 / 4)),
            (apply(Prim("add"), Int(1), Int(1)), (1 / 4) * (8 / 11) * (1 / 4)),
            (apply(Prim("add"), Int(0), Int(0)), (1 / 4) * (2 / 11) * (2 / 4)),
            (apply(Prim("add"), Int(0), Int(1)), (1 / 4) * (2 / 11) * (1 / 4)),
        )
        self.assertEqual([candidate.term for candidate in candidates], [term for term, _ in expected])
        for candidate, (term, probability) in zip(candidates, expected):
            self.assertAlmostEqual(candidate.log_probability, math.log(probability))
            self.assertAlmostEqual(grammar.log_probability(term, request_type=INT), math.log(probability))

    def test_every_returned_program_has_the_requested_type(self):
        requests = (
            (INT, ()),
            (BOOL, ()),
            (ListOf(INT), ()),
            (Arrow(INT, INT), (2,)),
            (Arrow(ListOf(INT), ListOf(INT)), ([0, 1, 2],)),
        )
        grammar = Grammar()
        for requested, inputs in requests:
            with self.subTest(requested=requested):
                candidates = list(itertools.islice(
                    enumerate_programs(requested, grammar=grammar, max_size=9,
                                       max_expansions=4000), 40))
                self.assertTrue(candidates, f"no programs produced for {requested}")
                for candidate in candidates:
                    with self.subTest(term=candidate.term):
                        unify(infer(candidate.term), requested)
                        result = evaluate(candidate.term, inputs=inputs, step_budget=2000)
                        self.assertFalse(result.error and result.error.startswith("type_error"),
                                         result.error)
                        if result.ok:
                            output_type = requested.args[1] if requested.tag == "arrow" else requested
                            if output_type == INT:
                                self.assertIs(type(result.value), int)
                            elif output_type == BOOL:
                                self.assertIs(type(result.value), bool)
                            else:
                                self.assertIs(type(result.value), list)
                                self.assertTrue(all(type(x) is int for x in result.value))

    def test_general_grammar_is_monotone_and_recomputed_scores_agree(self):
        grammar = Grammar()
        candidates = list(itertools.islice(
            enumerate_programs(INT, grammar=grammar, max_size=11,
                               max_expansions=5000), 60))
        self.assertGreaterEqual(len(candidates), 5)
        self.assertEqual(len({candidate.term for candidate in candidates}), len(candidates))
        previous = math.inf
        for candidate in candidates:
            self.assertLessEqual(candidate.log_probability, previous + 1e-12)
            self.assertAlmostEqual(candidate.log_probability,
                                   grammar.log_probability(candidate.term, request_type=INT))
            previous = candidate.log_probability

    def test_search_budget_terminates_even_with_unbounded_size(self):
        grammar = Grammar()
        self.assertEqual(list(enumerate_programs(INT, grammar=grammar, max_size=1000,
                                                max_expansions=0)), [])
        candidates = list(enumerate_programs(INT, grammar=grammar, max_size=1000,
                                            max_expansions=25))
        self.assertLessEqual(len(candidates), 25)
        for candidate in candidates:
            unify(infer(candidate.term), INT)

    def test_library_functions_are_enumerated_in_composed_programs(self):
        increment = Lam(INT, apply(Prim("add"), Var(0), Int(1)))
        twice = Lam(INT, apply(Ref("increment"), apply(Ref("increment"), Var(0))))
        library = {"increment": increment, "twice": (Arrow(INT, INT), twice)}
        grammar = Grammar(library=library, primitives={}, constants=(Int(0),))
        candidates = list(enumerate_programs(INT, grammar=grammar, max_size=5,
                                            max_expansions=1000))
        terms = {candidate.term for candidate in candidates}
        expected = apply(Ref("increment"), apply(Ref("twice"), Int(0)))
        self.assertIn(expected, terms)
        self.assertEqual(infer(expected, library=library), INT)
        result = evaluate(expected, library=library)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, 3)
        for candidate in candidates:
            self.assertEqual(infer(candidate.term, library=library), INT)

    def test_repeating_a_run_has_identical_candidates_and_scores(self):
        grammar = Grammar(
            primitives={"add": PRIMITIVE_TYPES["add"]},
            constants=(Int(0), Int(1), Int(-1)),
        )
        first = list(enumerate_programs(INT, grammar=grammar, max_size=9,
                                       max_expansions=300))
        second = list(enumerate_programs(INT, grammar=grammar, max_size=9,
                                        max_expansions=300))
        self.assertEqual([(c.term, c.log_probability, c.score) for c in first],
                         [(c.term, c.log_probability, c.score) for c in second])

    def test_zero_partial_callback_preserves_baseline_order_including_ties(self):
        grammar = Grammar(primitives={"add": PRIMITIVE_TYPES["add"]},
                          constants=(Int(0), Int(1)))
        baseline = list(enumerate_programs(INT, grammar=grammar, max_size=9,
                                          max_expansions=10000))
        guided = list(enumerate_programs(INT, grammar=grammar, max_size=9,
                                        max_expansions=10000,
                                        partial_heuristic=lambda state: 0.0))
        self.assertEqual([(c.term, c.log_probability, c.score) for c in guided],
                         [(c.term, c.log_probability, c.score) for c in baseline])

    def test_higher_order_map_with_a_library_lambda_is_reachable(self):
        increment = Lam(INT, apply(Prim("add"), Var(0), Int(1)))
        library = {"increment": increment}
        grammar = Grammar(library=library,
                          primitives={"map": PRIMITIVE_TYPES["map"]}, constants=())
        requested = Arrow(ListOf(INT), ListOf(INT))
        expected = Lam(ListOf(INT), apply(Prim("map"), Ref("increment"), Var(0)))
        candidates = list(enumerate_programs(requested, grammar=grammar, max_size=6,
                                            max_expansions=2000))
        self.assertIn(expected, {candidate.term for candidate in candidates})
        self.assertEqual(infer(expected, library=library), requested)
        result = evaluate(expected, inputs=([0, 2, -4],), library=library)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, [1, 3, -3])

    def test_higher_order_fold_with_a_curried_accumulator_is_reachable(self):
        total = Lam(INT, Lam(INT, apply(Prim("add"), Var(1), Var(0))))
        library = {"total": total}
        grammar = Grammar(library=library,
                          primitives={"fold": PRIMITIVE_TYPES["fold"]},
                          constants=(Int(0),))
        requested = Arrow(ListOf(INT), INT)
        expected = Lam(ListOf(INT), apply(Prim("fold"), Ref("total"), Int(0), Var(0)))
        candidates = list(enumerate_programs(requested, grammar=grammar, max_size=8,
                                            max_expansions=4000))
        self.assertIn(expected, {candidate.term for candidate in candidates})
        self.assertEqual(infer(expected, library=library), requested)
        result = evaluate(expected, inputs=([1, 2, -4],), library=library)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, -1)


if __name__ == "__main__":
    unittest.main()
