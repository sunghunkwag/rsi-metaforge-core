"""The readable program form round-trips through the parser (the audit re-executes
programs from the result files, which keep that form)."""
import unittest

from rsi5.dsl.pretty_parse import parse
from rsi5.dsl.terms import Lam, Prim, Var, apply, pretty
from rsi5.dsl.types import Arrow, INT, ListOf, PairOf, infer


class RoundTrip(unittest.TestCase):
    def test_engine_shapes(self):
        cases = [
            "(lambda x0: list[int]. ((map (lambda x1: int. (((if (is_prime x1)) 1) 0))) x0))",
            "(lambda x0: list[int]. ((cons ((mul 2) 5)) x0))",
            "(lambda x0: list[int]. ((map (lambda x1: int. ((index x1) x0))) (range 3)))",
            "(lambda x0: list[int]. (((fold (lambda x1: bool. (lambda x2: int. (is_prime x2)))) false) x0))",
            "(lambda x0: list[int]. ((map (lambda x1: (int, int). (fst x1))) ((zip x0) (tail x0))))",
            "(lambda x0: list[int]. ((fix1 x0) (lambda x1: list[int] -> int. (lambda x2: list[int]. "
            "(((if (is_empty x2)) 0) ((add 1) (x1 (tail x2))))))))",
        ]
        for text in cases:
            term = parse(text)
            self.assertEqual(pretty(term), text)
            infer(term)

    def test_de_bruijn_indices(self):
        term = parse("(lambda x0: list[int]. ((map (lambda x1: int. ((add x1) (head x0)))) x0))")
        body = term.children[0]
        lam = body.children[0].children[1]
        inner = lam.children[0]
        self.assertEqual(inner.children[0].children[1], Var(0))            # x1
        self.assertEqual(inner.children[1].children[1], Var(1))            # x0 inside the lambda
        self.assertEqual(body.children[1], Var(0))                         # x0 outside

    def test_types(self):
        term = parse("(lambda x0: (int, bool). (snd x0))")
        self.assertEqual(term.value, PairOf(INT, __import__("rsi5.dsl.types", fromlist=["BOOL"]).BOOL))
        term = parse("(lambda x0: (list[int]) -> int. 1)")
        self.assertEqual(term.value, Arrow(ListOf(INT), INT))


if __name__ == "__main__":
    unittest.main()
