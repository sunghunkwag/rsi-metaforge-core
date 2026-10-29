"""Behavioural search: sound vectors, deduction, witnesses, accounting, resumption."""
import pickle
import random
import unittest

from rsi2.evaluator import evaluate
from rsi2.types import BOOL, INT, Arrow, ListOf

from rsi3.behave import (BehaviouralSearch, frozen, hole_problem, problems_for, whole_problem,
                         witnesses)
from rsi3.decompose import skeletons_for

LIST = ListOf(INT)


def _lists(seed, n=10, lo=4, hi=9):
    rng = random.Random(seed)
    return [[rng.randrange(0, 17) for _ in range(rng.randrange(lo, hi))] for _ in range(n)]


def _task(function, seed=0, **kw):
    return [((xs,), function(xs)) for xs in _lists(seed, **kw)]


class VectorSoundnessTests(unittest.TestCase):
    def test_every_pool_vector_is_what_the_evaluator_computes(self):
        examples = _task(lambda xs: xs[1], seed=3)
        problem = whole_problem(examples, Arrow(LIST, INT))
        search = BehaviouralSearch(problem, {}, examples, known=set(), witnesses=True)
        checked = 0
        for tag, term, vector, kind in search._events:
            program = problem.wrap(term)
            for (inputs, _), value in zip(examples, vector):
                result = evaluate(program, inputs, step_budget=2000)
                self.assertTrue(result.ok, (term, result.error))
                self.assertEqual(frozen(result.value), value, term)
            checked += 1
            if checked >= 400:
                break
        self.assertGreaterEqual(checked, 400)


class DeductionTests(unittest.TestCase):
    def test_cons_deduction_builds_a_fixed_length_output(self):
        examples = _task(lambda xs: [xs[2], xs[0]], seed=4)
        problem = whole_problem(examples, Arrow(LIST, LIST))
        result = BehaviouralSearch(problem, {}, examples, known=set()).run(500)
        self.assertIsNotNone(result.term)
        for inputs, expected in examples:
            self.assertEqual(evaluate(result.term, inputs, step_budget=2000).value, expected)

    def test_eq_witness_finds_a_filter_predicate(self):
        examples = _task(lambda xs: [x for x in xs if x % 2 == 0], seed=5)
        sk = next(s for s in skeletons_for(examples) if s.name == "filter")
        problem = hole_problem(sk, examples)
        result = BehaviouralSearch(problem, {}, examples, known=set()).run(64)
        self.assertIsNotNone(result.term)
        self.assertLessEqual(result.evaluated, 64)
        for inputs, expected in examples:
            self.assertEqual(evaluate(result.term, inputs, step_budget=2000).value, expected)

    def test_without_witnesses_the_same_filter_costs_more(self):
        examples = _task(lambda xs: [x for x in xs if x % 2 == 0], seed=5)
        sk = next(s for s in skeletons_for(examples) if s.name == "filter")
        problem = hole_problem(sk, examples)
        with_w = BehaviouralSearch(problem, {}, examples, known=set()).run(2000)
        without = BehaviouralSearch(problem, {}, examples, known=set(), witnesses=False).run(2000)
        self.assertIsNotNone(with_w.term)
        self.assertGreater(without.evaluated, with_w.evaluated)

    def test_quantifier_witness_for_all(self):
        rng = random.Random(6)
        examples = []
        for i in range(12):
            xs = [rng.randrange(0, 6) * 2 for _ in range(rng.randrange(1, 5))]
            if i % 2:
                xs[rng.randrange(len(xs))] += 1
            examples.append(((xs,), all(x % 2 == 0 for x in xs)))
        sk = next(s for s in skeletons_for(examples) if s.name == "all")
        problem = hole_problem(sk, examples)
        result = BehaviouralSearch(problem, {}, examples, known=set()).run(200)
        self.assertIsNotNone(result.term)
        for inputs, expected in examples:
            self.assertEqual(evaluate(result.term, inputs, step_budget=2000).value, expected)

    def test_int_witness_inverts_add_and_mod(self):
        a = (3, 7, 10, 12)
        constants = {-1: None, 0: None, 1: None, 2: None, 3: None}
        problem = type("P", (), {})()
        problem.targets = {("i", tuple((x + 2) for x in a)): [("R", 0)],
                           ("i", tuple(x % 3 for x in a)): [("R", 0)]}
        problem.has_predicate = False
        found = witnesses(problem, a, constants)
        self.assertIn(("i", "add", 2, False), found)
        self.assertIn(("i", "mod", 3, False), found)


class AccountingTests(unittest.TestCase):
    def test_known_behaviours_are_free_on_a_rebuild(self):
        examples = _task(lambda xs: xs[3], seed=7)
        problem = whole_problem(examples, Arrow(LIST, INT))
        known = set()
        first = BehaviouralSearch(problem, {}, examples, known=known)
        first.run(30)
        again = BehaviouralSearch(problem, {}, examples, known=known)
        result = again.run(30)
        self.assertEqual(again.skipped_known, first.evaluated - _programs(first))
        self.assertLessEqual(result.evaluated, 30)

    def test_relevance_pruning_keeps_booleans_out_of_an_int_problem(self):
        examples = _task(lambda xs: xs[1] + xs[2], seed=8)
        problem = whole_problem(examples, Arrow(LIST, INT))
        search = BehaviouralSearch(problem, {}, examples, known=set())
        tags = {tag for _, (tag, *_rest) in zip(range(300), search._events)}
        self.assertNotIn("b", tags)
        self.assertNotIn("lb", tags)


def _programs(search) -> int:
    """Assembled-program checks a search has charged (none for these targets)."""
    return 0


class ResumptionTests(unittest.TestCase):
    def test_windows_and_fast_forward_equal_one_search(self):
        examples = _task(lambda xs: [xs[3], xs[1], xs[0]], seed=9)
        problem = whole_problem(examples, Arrow(LIST, LIST))
        one = BehaviouralSearch(problem, {}, examples).run(400)
        self.assertIsNotNone(one.term)
        a = BehaviouralSearch(problem, {}, examples)
        result = a.run(one.evaluated // 2)
        self.assertIsNone(result.term)
        b = BehaviouralSearch(problem, {}, examples)
        b.fast_forward(a.position, a.evaluated, a.skipped_known, a.evaluation_steps)
        rest = b.run(400)
        self.assertEqual(rest.term, one.term)
        self.assertEqual(b.evaluated, one.evaluated)

    def test_problems_pickle(self):
        examples = _task(lambda xs: [x for x in xs if x > 5], seed=10)
        problems = problems_for(examples, Arrow(LIST, LIST), skeletons_for(examples))
        self.assertIn("whole", problems)
        self.assertIn("filter", problems)
        restored = pickle.loads(pickle.dumps(problems))
        self.assertEqual(sorted(restored), sorted(problems))


if __name__ == "__main__":
    unittest.main()
