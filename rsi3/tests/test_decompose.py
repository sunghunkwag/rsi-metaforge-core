"""Decomposition skeletons: shapes from public examples, beta-normal composites,
and a hole search that solves a task the plain prior search does not at the same budget."""
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.search import solve
from rsi2.terms import pretty

from rsi3.decompose import skeletons_for
from rsi3.resumable import ResumableSearch
from rsi3.verifier import FrozenVerifier

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}


class DecomposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = {t.name: t for t in load_train()}

    def test_skeletons_follow_the_public_shape(self):
        names = lambda task: [s.name for s in skeletons_for(self.train[task].examples)]
        self.assertIn("filter", names("keep-mod-k with k=2"))
        self.assertIn("any", names("has-k with k=3"))
        self.assertIn("prepend_of", names("prepend-index-k with k=2"))
        self.assertIn("map_const", names("replace-all-with-index-k with k=1"))
        self.assertEqual(names("index-k with k=3"), [])     # int output: no list skeleton

    def test_composites_are_beta_normal_and_score_in_the_grammar(self):
        task = self.train["prepend-index-k with k=2"]
        skeleton = skeletons_for(task.examples)[0]
        result = ResumableSearch(task.examples, skeleton.hole_type, Grammar(),
                                 compose=skeleton.compose, **SEARCH).run(300)
        self.assertIsNotNone(result.term)
        self.assertNotIn("((lambda", pretty(result.term))
        grammar = Grammar()
        grammar.fit([(result.term, task.request_type)])   # what RSI-2's sleep does
        verdict = FrozenVerifier([task]).verify(task.name, result.term, {}, 1).verdict
        self.assertTrue(verdict)
        # The plain prior search does not reach it at the same budget.
        self.assertIsNone(solve(task.examples, task.request_type, 300, Grammar(),
                                **SEARCH).term)


if __name__ == "__main__":
    unittest.main()


class FoldSkeletonTests(unittest.TestCase):
    def test_fold_skeletons_are_opt_in_and_reach_reverse(self):
        train = {t.name: t for t in load_train()}
        task = train["reverse"]
        self.assertNotIn("fold_nil", [s.name for s in skeletons_for(task.examples)])
        fold = {s.name: s for s in skeletons_for(task.examples, fold=True)}["fold_nil"]
        result = ResumableSearch(task.examples, fold.hole_type, Grammar(), compose=fold.compose,
                                 **SEARCH).run(300)
        self.assertIsNotNone(result.term)
        self.assertTrue(FrozenVerifier([task]).verify(task.name, result.term, {}, 1).verdict)
        self.assertIsNone(solve(task.examples, task.request_type, 300, Grammar(), **SEARCH).term)
