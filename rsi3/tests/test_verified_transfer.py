"""Typed donor-mutation tests; no benchmark hidden/test data used."""
import unittest
from types import SimpleNamespace

from rsi2.grammar import Grammar
from rsi2.terms import App, Int, Lam, Prim, Var, apply
from rsi2.types import INT, ListOf, Arrow, infer, unify
from rsi2.evaluator import evaluate
from rsi3.verified_transfer import integer_replacements, verified_program_mutations
from rsi3.resumable import ResumableSearch

LIST = ListOf(INT)
def donor():
    return Lam(LIST, apply(Prim("cons"), Int(0), Var(0)))

class VerifiedTransferTests(unittest.TestCase):
    def test_no_new_integer_literals(self):
        grammar = Grammar()
        replacements = integer_replacements(grammar)
        self.assertTrue(any(evaluate(term).ok and evaluate(term).value == 4
                            for term in replacements))
        legal_constants = set(grammar.constants)
        for term in replacements:
            def check(node):
                if node.tag == "int":
                    self.assertIn(node, legal_constants)
                for child in node.children:
                    check(child)
            check(term)

    def test_publicly_correct_program_is_generated_and_charged(self):
        grammar = Grammar()
        task = SimpleNamespace(request_type=Arrow(LIST, LIST),
             examples=tuple(((n,), [4] + n) for n in ([1], [2,3], [], [0,5], [9])))
        variants = verified_program_mutations(
            task, [donor()], grammar, max_size=12, max_proposals=48)
        self.assertTrue(variants)
        self.assertTrue(any(
            all((r := evaluate(term, inputs, step_budget=2000)).ok and
                r.value == expected for inputs, expected in task.examples)
            for term in variants))
        search = ResumableSearch(task.examples, task.request_type, grammar,
                                max_size=12, max_expansions=20000, known_failures=set())
        search.prepend_proposals(variants, grammar)
        record = search.run(len(variants))
        self.assertIsNotNone(record.term)
        self.assertLessEqual(record.evaluated, len(variants))
        self.assertEqual(search.evaluated, record.evaluated)

    def test_type_filter_and_size_cap(self):
        task = SimpleNamespace(request_type=Arrow(LIST, LIST), examples=())
        result = verified_program_mutations(task, [Int(0), donor()], Grammar(),
                                            max_size=12, max_proposals=48)
        self.assertTrue(all(term.size <= 12 for term in result))
        self.assertTrue(all(unify(infer(term), task.request_type) == {}
                            for term in result))

if __name__ == "__main__":
    unittest.main()
