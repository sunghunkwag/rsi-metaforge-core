"""Typed bottom-up construction, conservative equivalence and honest budgets."""
import unittest
from unittest.mock import patch

from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research.observational_search import solve_observational
from rsi2.search import verify
from rsi2.terms import Bool, Int, Lam, Prim, Var, apply, subterms
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, TVar, infer, unify


class ObservationalSearchTests(unittest.TestCase):
    def grammar(self, names=(), constants=(Int(0), Int(1))):
        return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in names},
                       constants=constants)

    def test_zero_combined_budget_calls_no_interpreter(self):
        with patch("rsi2.research.observational_search.evaluate", wraps=evaluate) as interpreter:
            result = solve_observational([((), 9)], INT, 0, self.grammar())
        interpreter.assert_not_called()
        self.assertEqual(result.logical_evaluations, 0)
        self.assertEqual(result.evaluation_steps, 0)
        self.assertEqual(result.termination, "evaluation_budget")

    def test_exact_candidate_and_example_accounting(self):
        examples = [((), 1), ((), 1), ((), 1)]
        with patch("rsi2.research.observational_search.evaluate", wraps=evaluate) as interpreter:
            result = solve_observational(examples, INT, 2, self.grammar(), max_size=1)
        self.assertEqual(result.term, Int(1))
        self.assertEqual(result.complete_candidates, 2)
        self.assertEqual(result.auxiliary_candidates, 0)
        self.assertEqual(result.evaluator_calls, interpreter.call_count)
        self.assertEqual(result.evaluator_calls, 6)
        independently_counted = sum(evaluate(*call.args, **call.kwargs).steps
                                    for call in interpreter.call_args_list)
        self.assertEqual(result.evaluation_steps, independently_counted)
        self.assertEqual(result.termination, "solution")

    def test_combined_budget_charges_auxiliary_components(self):
        requested = Arrow(ListOf(INT), ListOf(INT))
        examples = [(([3, 5],), [999]), (([-2],), [999])]
        with patch("rsi2.research.observational_search.evaluate", wraps=evaluate) as interpreter:
            result = solve_observational(examples, requested, 5,
                                         self.grammar(("cons",)), max_size=9)
        self.assertIsNone(result.term)
        self.assertGreater(result.auxiliary_candidates, 0)
        self.assertEqual(result.logical_evaluations, 5)
        self.assertEqual(result.termination, "evaluation_budget")
        self.assertEqual(result.evaluator_calls, interpreter.call_count)
        self.assertTrue(all(call.args[1] in [(), *[inputs for inputs, _ in examples]]
                            for call in interpreter.call_args_list))

    def test_equivalent_components_are_pruned_after_paying_for_the_probe(self):
        result = solve_observational([((), 99)], INT, 100,
                                     self.grammar(("add",)), max_size=5)
        self.assertGreater(result.semantic_pruned, 0)
        self.assertGreater(result.complete_candidates, result.retained_components)
        self.assertEqual(result.evaluator_calls, result.complete_candidates)
        self.assertEqual(result.termination, "finite_fragment_exhausted")
        self.assertFalse(result.language_complete)

    def test_runtime_failures_count_and_are_not_equivalence_pruned(self):
        grammar = self.grammar(("div",), constants=(Int(0),))
        result = solve_observational([((), 99)], INT, 20, grammar, max_size=5)
        self.assertEqual(result.complete_candidates, 2)
        self.assertEqual(result.runtime_failures, 1)
        self.assertEqual(result.semantic_pruned, 0)
        # Literal 0 occupies root and auxiliary DP buckets, while div(0,0)
        # occupies its root bucket. Their two distinct observations are cached.
        self.assertEqual(result.retained_components, 3)

    def test_primitive_partial_application_is_constructed(self):
        examples = [((3,), 4), ((-2,), -1)]
        requested = Arrow(INT, INT)
        result = solve_observational(examples, requested, 100,
                                     self.grammar(("add",)), max_size=6)
        self.assertIsNotNone(result.term)
        unify(infer(result.term), requested)
        self.assertTrue(verify(result.term, examples))
        self.assertEqual(result.term, apply(Prim("add"), Int(1)))

    def test_map_constructs_higher_order_lambda_without_sampling_its_binder(self):
        examples = [(([-2, 1],), [-3, 0]), (([0, 3],), [-1, 2])]
        requested = Arrow(ListOf(INT), ListOf(INT))
        with patch("rsi2.research.observational_search.evaluate", wraps=evaluate) as interpreter:
            result = solve_observational(examples, requested, 640,
                                         self.grammar(("map", "sub"), constants=(Int(1),)),
                                         max_size=8)
        self.assertIsNotNone(result.term, result.to_dict())
        self.assertTrue(any(node.tag == "lam" and node.value == INT
                            for _, node in subterms(result.term)))
        unify(infer(result.term), requested)
        self.assertTrue(verify(result.term, examples))
        self.assertTrue(verify(result.term, [(([8, -7],), [7, -8])]))
        # No invented scalar input is used to compare nested lambda bodies.
        self.assertTrue(all(call.args[1] in [(), *[inputs for inputs, _ in examples]]
                            for call in interpreter.call_args_list))

    def test_fold_constructs_curried_higher_order_primitive(self):
        examples = [(([2, 3],), 5), (([-4, 1],), -3), (([],), 0)]
        requested = Arrow(ListOf(INT), INT)
        result = solve_observational(examples, requested, 640,
                                     self.grammar(("fold", "add"), constants=(Int(0),)),
                                     max_size=5)
        self.assertIsNotNone(result.term, result.to_dict())
        self.assertTrue(verify(result.term, examples))
        self.assertTrue(verify(result.term, [(([9, -2, 5],), 12)]))
        self.assertIn(Prim("add"), {node for _, node in subterms(result.term)})

    def test_fold_lambdas_keep_accumulator_scope_distinct_from_same_typed_input(self):
        examples = [(([1, 9],), [9, 1]), (([1, 5, -2],), [-2, 5, 1])]
        requested = Arrow(ListOf(INT), ListOf(INT))
        result = solve_observational(examples, requested, 640,
                                     self.grammar(("fold", "cons", "nil"), constants=()),
                                     max_size=11)
        self.assertIsNotNone(result.term, result.to_dict())
        self.assertTrue(verify(result.term, examples))
        self.assertTrue(verify(result.term, [(([8, 2, -7],), [-7, 2, 8]), (([],), [])]))
        # The fold accumulator has list[int] type like the public input, but it
        # also takes values (initially []) absent from these public inputs.
        binders = [node.value for _, node in subterms(result.term) if node.tag == "lam"]
        self.assertIn(ListOf(INT), binders)
        self.assertIn(INT, binders)

    def test_library_heads_are_composed_without_new_primitives(self):
        library = {"own_increment": Lam(INT, apply(Prim("add"), Var(0), Int(1)))}
        grammar = Grammar(library=library, primitives={"map": PRIMITIVE_TYPES["map"]},
                          constants=())
        examples = [(([0, 3],), [1, 4]), (([-2],), [-1])]
        requested = Arrow(ListOf(INT), ListOf(INT))
        result = solve_observational(examples, requested, 100, grammar, max_size=3)
        self.assertIsNotNone(result.term, result.to_dict())
        self.assertTrue(verify(result.term, examples, library))
        self.assertTrue(any(node.tag == "ref" and node.value == "own_increment"
                            for _, node in subterms(result.term)))

    def test_public_inputs_do_not_leak_from_external_loaders(self):
        examples = [((0,), 1)]
        with patch("rsi2.corpus.load_train", side_effect=AssertionError("loader called")), \
                patch("rsi2.corpus.load_validation", side_effect=AssertionError("loader called")):
            result = solve_observational(examples, Arrow(INT, INT), 30,
                                         self.grammar(), max_size=2)
        self.assertIsNotNone(result.term)
        self.assertTrue(verify(result.term, examples))
        # A hidden counterexample changes verification, never search selection.
        self.assertFalse(verify(result.term, [((8,), 9)]))

    def test_expansion_and_cpu_limits_have_distinct_partial_results(self):
        result = solve_observational([((), 99)], INT, 20, self.grammar(), max_expansions=0)
        self.assertEqual(result.termination, "expansion_budget")
        self.assertEqual(result.expansions, 0)
        self.assertEqual(result.evaluator_calls, 0)
        result = solve_observational([((), 99)], INT, 20, self.grammar(), max_cpu_seconds=1e-12)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertEqual(result.evaluator_calls, 0)

    def test_frozen_caps_and_ground_fragment_are_explicit(self):
        for keyword in ({"max_size": 13}, {"max_expansions": 20001},
                        {"step_budget": 2001}, {"budget": -1},
                        {"max_cpu_seconds": float("nan")}):
            with self.subTest(keyword=keyword), self.assertRaises(ValueError):
                options = {"budget": 20, **keyword}
                solve_observational([((), 1)], INT, grammar=self.grammar(), **options)
        with self.assertRaises(ValueError):
            solve_observational([((), 1)], TVar("unspecified"), 20, self.grammar())
        with self.assertRaises(ValueError):
            solve_observational([((1,), 1)], INT, 20, self.grammar())


if __name__ == "__main__":
    unittest.main()
