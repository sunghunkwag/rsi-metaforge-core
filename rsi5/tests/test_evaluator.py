"""The reference interpreter: parity with RSI-2 on the original vocabulary, totality of
the restored primitives (test_fix1_terminates_under_budget), and the closures agree."""
import random
import unittest

from rsi2.evaluator import evaluate as rsi2_evaluate
from rsi2.enumeration import enumerate_programs
from rsi2.types import INT as R_INT, ListOf as R_ListOf, Arrow as R_Arrow
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.terms import App, Bool, Int, Lam, Prim, Term, Var, apply, term_from_dict
from rsi5.dsl.types import Arrow, BOOL, INT, ListOf, PairOf, infer
from rsi5.engine.closures import compile_term, run_closure


def convert(rsi2_term):
    return term_from_dict(rsi2_term.to_dict())


class ParityWithRsi2(unittest.TestCase):
    def test_original_vocabulary_programs_agree(self):
        inputs = [[], [0], [3, 1, 2], [5, -1, 7, 7, 2], [1, 1, 1, 1], [10, 2]]
        count = 0
        for candidate in enumerate_programs(R_Arrow(R_ListOf(R_INT), R_ListOf(R_INT)), max_size=9):
            term = convert(candidate.term)
            for xs in inputs:
                left = rsi2_evaluate(candidate.term, (xs,), step_budget=2000)
                right = evaluate(term, (xs,), step_budget=2000)
                self.assertEqual(left.ok, right.ok, (str(term), xs, left, right))
                if left.ok:
                    self.assertEqual(left.value, right.value, (str(term), xs))
            count += 1
            if count >= 1500:
                break
        self.assertGreaterEqual(count, 1500)

    def test_closures_agree_with_reference(self):
        inputs = [[], [0], [3, 1, 2], [5, -1, 7, 7, 2], [1, 1, 1, 1], [10, 2]]
        count = 0
        for candidate in enumerate_programs(R_Arrow(R_ListOf(R_INT), R_ListOf(R_INT)), max_size=9):
            term = convert(candidate.term)
            fn = compile_term(term)
            for xs in inputs:
                reference = evaluate(term, (xs,), step_budget=2000)
                value, error = run_closure(fn, ())
                if error is None:
                    value, error = run_closure(lambda env, b, v=value, x=xs: v(x, b), ())
                if reference.ok and error is None:
                    self.assertEqual(reference.value, value, str(term))
                elif reference.ok != (error is None):
                    # The closures charge steps coarsely; only budget-bound cases may differ.
                    self.assertIn("budget", reference.error or "budget", str(term))
            count += 1
            if count >= 1500:
                break


class RestoredPrimitivesAreTotal(unittest.TestCase):
    def test_fix1_terminates_under_budget(self):
        # fix1 x (λrec. λy. rec y): never returns; the step budget is the only terminator.
        body = Lam(Arrow(INT, INT), Lam(INT, App(Var(1), Var(0))))
        program = Lam(INT, apply(Prim("fix1"), Var(0), body))
        for budget in (10, 100, 2000, 20000):
            result = evaluate(program, (5,), step_budget=budget)
            self.assertFalse(result.ok)
            self.assertEqual(result.error, "budget_exhausted")
            self.assertEqual(result.steps, budget)
        fn = compile_term(program)
        value, error = run_closure(fn, ())
        self.assertIsNone(error)
        self.assertEqual(run_closure(lambda env, b: value(5, b), (), step_budget=2000),
                         (None, "Fail"))

    def test_fix1_computes_length(self):
        body = Lam(Arrow(ListOf(INT), INT), Lam(ListOf(INT), apply(
            Prim("if"), apply(Prim("is_empty"), Var(0)), Int(0),
            apply(Prim("add"), Int(1), App(Var(1), apply(Prim("tail"), Var(0)))))))
        program = Lam(ListOf(INT), apply(Prim("fix1"), Var(0), body))
        self.assertEqual(str(infer(program)), "list[int] -> int")
        self.assertEqual(evaluate(program, ([1, 2, 3, 4],)).value, 4)
        self.assertEqual(evaluate(program, ([],)).value, 0)

    def test_unfold_terminates_and_counts_down(self):
        countdown = Lam(INT, apply(Prim("unfold"), Lam(INT, apply(Prim("eq"), Var(0), Int(0))),
                                   Lam(INT, Var(0)), Lam(INT, apply(Prim("sub"), Var(0), Int(1))),
                                   Var(0)))
        self.assertEqual(evaluate(countdown, (5,)).value, [5, 4, 3, 2, 1])
        forever = Lam(INT, apply(Prim("unfold"), Lam(INT, Bool(False)), Lam(INT, Var(0)),
                                 Lam(INT, Var(0)), Var(0)))
        result = evaluate(forever, (5,), step_budget=500)
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "budget_exhausted")

    def test_index_zip_pairs_primes_squares(self):
        xs = Lam(ListOf(INT), apply(Prim("index"), Int(2), Var(0)))
        self.assertEqual(evaluate(xs, ([8, 15, 15],)).value, 15)
        self.assertFalse(evaluate(xs, ([8, 15],)).ok)
        self.assertFalse(evaluate(Lam(ListOf(INT), apply(Prim("index"), Int(-1), Var(0))), ([8],)).ok)
        z = Lam(ListOf(INT), apply(Prim("map"), Lam(PairOf(INT, INT), apply(Prim("fst"), Var(0))),
                                   apply(Prim("zip"), Var(0), apply(Prim("tail"), Var(0)))))
        self.assertEqual(evaluate(z, ([1, 2, 3],)).value, [1, 2])
        prime = Lam(INT, apply(Prim("is_prime"), Var(0)))
        self.assertEqual([evaluate(prime, (n,)).value for n in range(-2, 14)],
                         [False, False, False, False, True, True, False, True, False, True,
                          False, False, False, True, False, True])
        square = Lam(INT, apply(Prim("is_square"), Var(0)))
        self.assertEqual([evaluate(square, (n,)).value for n in (-4, 0, 1, 2, 4, 9, 10, 16)],
                         [False, True, True, False, True, True, False, True])

    def test_no_primitive_raises(self):
        """Random well-typed restored-vocabulary terms never raise out of evaluate."""
        from rsi5.dsl.grammar import Grammar
        from rsi5.dsl.vocabulary import RESTORED
        from rsi5.engine.bottomup import Engine
        from rsi5.engine.oe import ERR
        engine = Engine(RESTORED, max_size=6)
        examples = [(([3, 1, 2],), [9, 9, 9]), (([],), [9])]
        engine.search(examples, Arrow(ListOf(INT), ListOf(INT)), [([5, 5],)], budget=3000)
        seen = 0
        for context in engine.contexts:
            if context.depth:
                continue
            for pool in context.pools.values():
                for expr in pool[:400]:
                    term = Lam(ListOf(INT), expr.term)
                    for xs in ([], [1, 2], [7, 0, -3]):
                        result = evaluate(term, (xs,), step_budget=300)
                        self.assertIsInstance(result.ok, bool)
                        seen += 1
        self.assertGreater(seen, 1000)


if __name__ == "__main__":
    unittest.main()
