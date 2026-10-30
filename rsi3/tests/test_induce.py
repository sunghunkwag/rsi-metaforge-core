"""Procedure induction: anti-unification gives typed one-hole templates that rebuild their sources."""
import unittest

from rsi2.evaluator import evaluate
from rsi2.terms import App, Lam, Term, Var
from rsi2.types import INT, Arrow, ListOf

from rsi3.induce import anti_unify, induce_skeletons, matches

LIST = ListOf(INT)


def P(name):
    return Term("prim", name)


def ap(f, *args):
    for a in args:
        f = App(f, a)
    return f


def mod_map(k):
    return ap(P("map"), Lam(INT, ap(P("mod"), Var(0), Term("int", k))))


class InduceTests(unittest.TestCase):
    def test_constant_difference_gives_an_int_hole(self):
        sk = anti_unify(mod_map(2), mod_map(1), str(Arrow(LIST, LIST)))
        self.assertIsNotNone(sk)
        self.assertEqual(sk.hole_type, INT)
        program = sk.compose(Term("int", 2))
        self.assertEqual(evaluate(program, ([5, 6, 7],)).value, [1, 0, 1])

    def test_differences_using_a_bound_variable_are_lambda_lifted(self):
        first = Lam(LIST, ap(P("cons"), ap(P("head"), ap(P("tail"), Var(0))), Var(0)))
        second = Lam(LIST, ap(P("cons"), ap(P("head"), Var(0)), Var(0)))
        sk = anti_unify(first, second, str(Arrow(LIST, LIST)))
        self.assertIsNotNone(sk)
        self.assertEqual(sk.lifted, (0,))
        self.assertEqual(sk.hole_type, Arrow(LIST, LIST))       # the hole is "tail l" vs "l"
        hole = Lam(LIST, ap(P("tail"), ap(P("tail"), Var(0))))
        self.assertEqual(evaluate(sk.compose(hole), ([4, 5, 6],)).value, [6, 4, 5, 6])

    def test_identical_programs_and_root_differences_give_nothing(self):
        self.assertIsNone(anti_unify(mod_map(2), mod_map(2), "t"))
        self.assertIsNone(anti_unify(mod_map(2), P("nil"), "t"))

    def test_support_counts_instances_and_ranks_them(self):
        sols = {"a": mod_map(2), "b": mod_map(3), "c": mod_map(1)}
        types = {n: "t" for n in sols}
        found = induce_skeletons(sols, types)
        self.assertEqual(found[0].support, 3)
        self.assertTrue(all(matches(found[0].template, p) for p in sols.values()))


if __name__ == "__main__":
    unittest.main()
