import unittest
from unittest.mock import patch

from rsi2.grammar import Grammar
from rsi2 import search
from rsi2.research.bootstrap_run import enumeration_probe
from rsi2.terms import Int
from rsi2.types import INT


class BootstrapInstrumentationTests(unittest.TestCase):
    def test_instrumented_zero_callback_preserves_frozen_results(self):
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        for expected in (0, 1, 2):
            for budget in (0, 1, 2, 3):
                with self.subTest(expected=expected, budget=budget):
                    plain = search.solve([((), expected)], INT, budget, grammar,
                                         max_size=1, max_expansions=20)
                    measured = enumeration_probe([((), expected)], INT, budget, grammar,
                                                 max_size=1, max_expansions=20)
                    for field in ("term", "candidates", "log_probability",
                                  "evaluation_steps", "exhausted"):
                        self.assertEqual(getattr(plain, field), getattr(measured, field))
                    self.assertEqual(measured.evaluator_calls, measured.candidates)
                    self.assertLessEqual(measured.expansions, 20)

    def test_instrumentation_restores_functions_after_exception(self):
        before_enum, before_eval = search.enumerate_programs, search.evaluate
        with patch("rsi2.search.solve", side_effect=RuntimeError("probe")):
            with self.assertRaises(RuntimeError):
                enumeration_probe([((), 0)], INT, 1, Grammar())
        self.assertIs(search.enumerate_programs, before_enum)
        self.assertIs(search.evaluate, before_eval)


if __name__ == "__main__":
    unittest.main()
