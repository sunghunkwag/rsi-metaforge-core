"""Residual decomposition: a stage from the system's programs, the residual by behavioural search."""
import unittest

from rsi2.grammar import Grammar
from rsi2.terms import App, Int, Lam, Prim, Var, pretty
from rsi2.types import INT, Arrow, ListOf

from rsi3.chain import ChainSearch, relevance, stage_candidates
from rsi3.verifier import FrozenVerifier

LIST = ListOf(INT)
REQUEST = Arrow(LIST, LIST)
INPUTS = [[3, 1, 4, 1, 5], [9, 2, 6], [5, 3, 5, 8, 9, 7], [2, 7, 1, 8], [0, 4, 4, 2, 1],
          [6, 6, 1], [8, 0, 3, 3, 4, 1, 2], [1, 5, 9, 2]]
SETTINGS = {"max_size": 10, "max_unroll": 6}


def examples_of(function):
    return tuple(((x,), function(x)) for x in INPUTS)


class ChainTests(unittest.TestCase):
    def test_a_stage_then_a_pointwise_residual(self):
        # drop one, then add 2: tail is a stage; the residual is map (add 2).
        examples = examples_of(lambda x: [v + 2 for v in x[1:]])
        stages = {"prim:tail": Prim("tail")}
        search = ChainSearch(examples, REQUEST, stages, {}, behave_settings=SETTINGS)
        result = search.run(64)
        self.assertIsNotNone(result.term)
        self.assertEqual(search.found_from[0], "prim:tail")
        hidden = (((list(range(7)),), [v + 2 for v in range(1, 7)]),)
        task = type("T", (), {"name": "t", "hidden": hidden})()
        self.assertTrue(FrozenVerifier([task]).verify("t", result.term, {}, 1).verdict)

    def test_a_stage_that_already_fits_costs_one_unit(self):
        examples = examples_of(lambda x: x[1:])
        result = ChainSearch(examples, REQUEST, {"prim:tail": Prim("tail")}, {},
                             behave_settings=SETTINGS).run(16)
        self.assertEqual(result.evaluated, 1)
        self.assertEqual(pretty(result.term), "tail")

    def test_duplicate_and_identity_stages_are_free(self):
        examples = examples_of(lambda x: [v + 2 for v in x[1:]])
        identity = Lam(LIST, Var(0))
        stages = {"id": identity, "a": Prim("tail"), "b": Lam(LIST, App(Prim("tail"), Var(0)))}
        search = ChainSearch(examples, REQUEST, stages, {}, behave_settings=SETTINGS)
        search.run(1)
        self.assertEqual([r[2] for r in search._ranked], ["a"])

    def test_windows_resume_exactly(self):
        examples = examples_of(lambda x: [v + 2 for v in x[2:]])
        stages = {"prim:tail": Prim("tail"), "two": Lam(LIST, App(Prim("tail"),
                                                                 App(Prim("tail"), Var(0))))}
        whole = ChainSearch(examples, REQUEST, stages, {}, behave_settings=SETTINGS).run(40)
        self.assertIsNotNone(whole.term)
        first = ChainSearch(examples, REQUEST, stages, {}, behave_settings=SETTINGS)
        a = first.run(9)
        rebuilt = ChainSearch(examples, REQUEST, stages, {}, behave_settings=SETTINGS)
        rebuilt.fast_forward(first.position, first.evaluated, first.skipped_known,
                             first.evaluation_steps)
        b = rebuilt.run(40 - a.evaluated)
        self.assertEqual(None if whole.term is None else pretty(whole.term),
                         None if b.term is None else pretty(b.term))
        self.assertEqual(a.evaluated + b.evaluated, whole.evaluated)

    def test_relevance_prefers_a_shape_the_residual_can_take(self):
        examples = examples_of(lambda x: [v + 1 for v in x[1:]])
        tail = [x[1:] for x in INPUTS]
        self.assertGreater(relevance(tail, examples), relevance(INPUTS, examples))

    def test_stage_candidates_are_list_programs_in_order(self):
        library = {"c2": Lam(LIST, App(Prim("tail"), App(Prim("tail"), Var(0)))),
                   "h": Lam(LIST, App(Prim("head"), Var(0)))}
        solutions = {"s": Lam(LIST, Var(0))}
        stages = stage_candidates(solutions, {"s": REQUEST}, library)
        self.assertEqual(list(stages), ["concept:c2", "prim:tail", "solution:s"])


class Compose24Tests(unittest.TestCase):
    def test_the_copied_suite_matches_its_commitment(self):
        from rsi3.compose24 import load_frozen_tasks, suite_sha256
        self.assertEqual(suite_sha256(),
                         "c871c3a3c0ca4da576c48f2f84b742a67a39725c701ae9d3a291794d23d7edc5")
        self.assertEqual(len(load_frozen_tasks()), 24)


if __name__ == "__main__":
    unittest.main()
