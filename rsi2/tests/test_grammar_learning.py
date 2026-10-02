"""Grammar estimation from actual typed solution decisions."""
import unittest

from rsi2.enumeration import enumerate_programs
from rsi2.grammar import Grammar, ROOT_CONTEXT
from rsi2.terms import Int, Lam, Prim, Ref, Var, apply
from rsi2.types import Arrow, INT, PRIMITIVE_TYPES


class GrammarLearningTests(unittest.TestCase):
    def grammar(self):
        return Grammar(primitives={"add": PRIMITIVE_TYPES["add"]},
                       constants=(Int(0), Int(1)))

    def test_decisions_match_parent_arguments_and_variable_bindings(self):
        term = Lam(INT, apply(Prim("add"), Var(0), Int(1)))
        self.assertEqual(self.grammar().decisions(term, Arrow(INT, INT)), [
            (ROOT_CONTEXT, "lambda/1"), (("lambda", 0), "add/2"),
            (("add", 0), "var:0/0"), (("add", 1), "int:1/0"),
        ])

    def test_fit_counts_contexts_with_frozen_pseudocount_one(self):
        grammar = self.grammar()
        term = apply(Prim("add"), Int(1), Int(0))
        metrics = grammar.fit([(term, INT), (term, INT), Int(0)])
        self.assertEqual(metrics["pseudocount"], 1)
        self.assertEqual(metrics["solutions"], 3)
        self.assertEqual(metrics["decisions"], 7)
        self.assertEqual(grammar.weights["int:0/0"], 4)
        self.assertEqual(grammar.weights["int:1/0"], 3)
        self.assertEqual(grammar.context_weights[("add", 0)]["int:1/0"], 3)
        self.assertEqual(grammar.context_weights[("add", 0)]["int:0/0"], 1)
        self.assertEqual(grammar.context_weights[("add", 1)]["int:0/0"], 3)
        self.assertEqual(grammar.context_weights[("add", 1)]["int:1/0"], 1)
        self.assertGreater(metrics["log_likelihood_after"], metrics["log_likelihood_before"])

    def test_fit_changes_search_prior_and_preserves_unseen_productions(self):
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        grammar.fit([Int(1)] * 4)
        candidates = list(enumerate_programs(INT, grammar, max_size=1))
        self.assertEqual([c.term for c in candidates], [Int(1), Int(0)])
        self.assertAlmostEqual(candidates[0].log_probability, __import__("math").log(5 / 6))
        self.assertEqual(grammar.weights["int:0/0"], 1)
        self.assertEqual(Grammar(primitives={}, constants=(Int(0), Int(1))).weights, {})

    def test_fitting_library_head_and_resetting_have_identical_rules(self):
        library = {"learned": Lam(INT, apply(Prim("add"), Var(0), Int(1)))}
        grammar = Grammar(library=library, primitives={}, constants=(Int(0),))
        grammar.fit([apply(Ref("learned"), Int(0))] * 3)
        self.assertEqual(grammar.context_weights[ROOT_CONTEXT]["learned/1"], 4)
        self.assertEqual(grammar.context_weights[("learned", 0)]["int:0/0"], 4)
        grammar.fit([])
        self.assertTrue(all(value == 1 for value in grammar.weights.values()))
        self.assertEqual(grammar.context_weights, {})

    def test_invalid_solution_is_rejected_without_partial_weight_update(self):
        grammar = self.grammar()
        with self.assertRaises(TypeError):
            grammar.fit([Int(0), (Int(1), "int")])
        self.assertEqual(grammar.weights, {})
        with self.assertRaises(TypeError):
            grammar.fit([Var(0)])
        self.assertEqual(grammar.weights, {})


if __name__ == "__main__":
    unittest.main()
