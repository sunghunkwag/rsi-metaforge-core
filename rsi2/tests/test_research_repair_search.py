"""Scope preservation, honest limits, and semantic repair-search checks."""
from itertools import islice
import unittest
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research.repair_search import (
    RepairSeed, beta_normal_form, solve_repair, typed_locations,
)
from rsi2.search import verify
from rsi2.terms import App, Int, Lam, Prim, Var, apply
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES, TVar, arrows, infer


class RepairSearchTests(unittest.TestCase):
    def constant_grammar(self):
        return Grammar(primitives={}, constants=(Int(0), Int(1)))

    def arithmetic_grammar(self):
        return Grammar(primitives={"add": PRIMITIVE_TYPES["add"]},
                       constants=(Int(0), Int(1), Int(2)))

    def enumerated_seed(self, request, grammar, term_size, select):
        return next(c.term for c in enumerate_programs(
            request, grammar, max_size=term_size, max_expansions=1000)
                    if select(c.term))

    def test_context_specializes_polymorphic_subterms_and_binders(self):
        term = Lam(TVar("a"), apply(Prim("cons"), Int(1), Prim("nil")))
        request = Arrow(INT, ListOf(INT))
        locations = {location.path: location for location in typed_locations(term, request)}
        self.assertEqual(locations[(0, 1)].type, ListOf(INT))
        self.assertEqual(locations[(0, 1)].env, (INT,))
        self.assertEqual(locations[()].type, request)
        self.assertEqual(locations[(0, 0, 1)].type, INT)

    def test_nested_binder_indices_remain_distinct(self):
        term = Lam(INT, Lam(INT, apply(Prim("add"), Var(1), Var(0))))
        locations = {location.path: location for location in typed_locations(
            term, arrows(INT, INT, INT))}
        self.assertEqual(locations[(0, 0, 0, 1)].env, (INT, INT))
        self.assertEqual(locations[(0, 0, 0, 1)].term, Var(1))
        self.assertEqual(locations[(0, 0, 1)].term, Var(0))

    def test_zero_candidate_budget_does_no_generation_or_interpretation(self):
        with patch("rsi2.research.repair_search.evaluate", wraps=evaluate) as interpreter:
            result = solve_repair([((), 1)], INT, 0, self.constant_grammar())
        interpreter.assert_not_called()
        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.expansions, 0)
        self.assertEqual(result.emitted_enumerator_terms, 0)
        self.assertEqual(result.termination, "candidate_budget")

    def test_expansion_cap_charges_partial_and_complete_pops_exactly(self):
        limited = solve_repair([((), 1)], INT, 2, self.constant_grammar(),
                               seed_prefix=2, max_size=1, max_expansions=2)
        self.assertEqual(limited.expansions, 2)  # Initial hole, first literal.
        self.assertEqual(limited.candidates, 1)
        self.assertEqual(limited.termination, "expansion_budget")
        successful = solve_repair([((), 1)], INT, 2, self.constant_grammar(),
                                  seed_prefix=2, max_size=1, max_expansions=3)
        self.assertEqual(successful.expansions, 3)
        self.assertEqual(successful.candidates, 2)
        self.assertEqual(successful.term, Int(1))

    def test_all_public_ranking_work_is_counted_and_hidden_data_is_absent(self):
        examples = [((), 9), ((), 9), ((), 9)]
        with patch("rsi2.research.repair_search.evaluate", wraps=evaluate) as interpreter:
            result = solve_repair(examples, INT, 2, self.constant_grammar(),
                                  seed_prefix=2, max_size=1)
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.evaluator_calls, 6)
        self.assertEqual(len(interpreter.call_args_list), 6)
        expected_steps = sum(evaluate(Int(value), ()).steps
                             for value in (0, 1) for _ in range(3))
        self.assertEqual(result.evaluation_steps, expected_steps)
        self.assertEqual(len(result.trials), result.candidates)

    def test_machine_seed_can_be_repaired_to_a_new_semantic_function(self):
        request, grammar = Arrow(INT, INT), self.arithmetic_grammar()
        seed = self.enumerated_seed(request, grammar, 2,
                                    lambda t: t.tag == "lam" and t.children[0] == Var(0))
        # This seed was independently accepted on a separate TRAIN identity task.
        self.assertTrue(verify(seed, [((7,), 7)], library=grammar.library))
        examples = [((0,), 2), ((4,), 6), ((-3,), -1)]
        result = solve_repair(examples, request, 64, grammar, seed_prefix=0,
                              accepted_seeds=(RepairSeed(seed, "identity:verifier-pass"),))
        self.assertEqual(result.termination, "public_match")
        self.assertTrue(verify(result.term, [((100,), 102), ((-50,), -48)],
                               library=grammar.library))
        self.assertEqual(infer(result.term), request)
        self.assertLessEqual(result.term.size, 12)
        self.assertGreater(result.repair_candidates, 0)
        self.assertEqual(result.seed_records[0]["source"], "verified_train")
        self.assertEqual(result.trials[-1]["source"], "repair")

    def test_repair_can_use_an_outer_binding_without_capture(self):
        grammar, request = self.constant_grammar(), arrows(INT, INT, INT)
        seed = self.enumerated_seed(request, grammar, 3,
                                    lambda t: t.tag == "lam" and
                                    t.children[0].tag == "lam" and
                                    t.children[0].children[0] == Int(0))
        self.assertTrue(verify(seed, [((9, 8), 0)], library=grammar.library))
        result = solve_repair([((3, 8), 3), ((5, 2), 5)], request, 16, grammar,
                              accepted_seeds=(RepairSeed(seed, "zero:verifier-pass"),),
                              seed_prefix=0, max_size=3)
        self.assertEqual(result.termination, "public_match")
        self.assertTrue(verify(result.term, [((17, -4), 17)], library=grammar.library))
        self.assertEqual(result.term.children[0].children[0], Var(1))
        self.assertLessEqual(result.expansions, 20000)

    def test_no_repair_can_exceed_the_candidate_cap(self):
        grammar, request = self.arithmetic_grammar(), Arrow(INT, INT)
        for budget in (1, 4, 7):
            with self.subTest(budget=budget):
                result = solve_repair([((1,), 999)], request, budget, grammar)
                self.assertEqual(result.candidates, budget)
                self.assertEqual(len(result.trials), budget)
                self.assertEqual(result.termination, "candidate_budget")

    def test_fresh_seed_provenance_is_the_actual_frozen_enumerator_prefix(self):
        grammar, request = self.arithmetic_grammar(), Arrow(INT, INT)
        expected = [c.term.to_dict() for c in islice(enumerate_programs(
            request, grammar, max_size=12, max_expansions=20000), 4)]
        result = solve_repair([((2,), 999)], request, 4, grammar, seed_prefix=4)
        self.assertEqual([r["term"] for r in result.seed_records], expected)
        self.assertEqual([r["prefix_index"] for r in result.seed_records], list(range(4)))
        self.assertEqual(result.seed_candidates, 4)
        self.assertEqual(result.repair_candidates, 0)

    def test_incompatible_accepted_programs_are_not_evaluated(self):
        seed = self.enumerated_seed(Arrow(INT, INT), self.constant_grammar(), 2,
                                    lambda t: t.tag == "lam")
        self.assertTrue(verify(seed, [((1,), evaluate(seed, (1,)).value)]))
        result = solve_repair([((), 1)], INT, 2, self.constant_grammar(),
                              accepted_seeds=(RepairSeed(seed, "function:verifier-pass"),),
                              max_size=1)
        self.assertEqual(result.incompatible_accepted_seeds, 1)
        self.assertEqual(result.term, Int(1))
        self.assertEqual(result.candidates, 2)

    def test_cpu_guard_preserves_counters_and_does_not_claim_exhaustion(self):
        result = solve_repair([((), 9)], INT, 64, self.constant_grammar(),
                              max_cpu_seconds=0)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.expansions, 0)
        self.assertFalse(result.exhausted)

    def test_malformed_budgets_and_missing_provenance_are_rejected(self):
        for key, value in (("budget", -1), ("seed_prefix", True),
                           ("max_cpu_seconds", float("nan"))):
            kwargs = {"budget": 2, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                solve_repair([((), 1)], INT, grammar=self.constant_grammar(), **kwargs)
        with self.assertRaises(TypeError):
            solve_repair([((), 1)], INT, 2, self.constant_grammar(), accepted_seeds=(Int(1),))
        with self.assertRaises(ValueError):
            RepairSeed(Int(1), "")

    def test_beta_normalization_preserves_nested_free_and_shadowed_binders(self):
        examples = (
            # The substituted outer variable must stay free under the inner lambda.
            (Lam(INT, App(Lam(INT, Lam(INT, Var(1))), Var(0))),
             (17, -4), 17, Lam(INT, Lam(INT, Var(1)))),
            # Removing the application binder decrements the surrounding free index.
            (Lam(INT, App(Lam(INT, Var(1)), Int(0))),
             (23,), 23, Lam(INT, Var(0))),
            # An inner binding shadows the removed binding and remains unchanged.
            (App(Lam(INT, Lam(INT, Var(0))), Int(7)),
             (-9,), -9, Lam(INT, Var(0))),
        )
        for raw, inputs, expected, normal in examples:
            with self.subTest(raw=str(raw)):
                result = beta_normal_form(raw)
                self.assertTrue(result.complete)
                self.assertEqual(result.term, normal)
                self.assertEqual(infer(raw), infer(result.term))
                self.assertEqual(evaluate(raw, inputs).value, expected)
                self.assertEqual(evaluate(result.term, inputs).value, expected)
                self.assertGreater(result.steps, raw.size)
                self.assertEqual(result.beta_reductions, 1)

    def test_normalization_budget_does_not_return_a_partial_normal_form(self):
        raw = App(Lam(INT, Var(0)), Int(1))
        result = beta_normal_form(raw, max_steps=1)
        self.assertFalse(result.complete)
        self.assertIsNone(result.term)
        self.assertEqual(result.steps, 1)
        self.assertEqual(result.beta_reductions, 0)

    def test_normalization_is_opt_in_and_has_a_separate_honest_work_cap(self):
        ordinary = solve_repair([((), 9)], INT, 2, self.constant_grammar())
        self.assertEqual(ordinary.normalization_steps, 0)
        self.assertEqual(ordinary.beta_reductions, 0)
        limited = solve_repair([((), 9)], INT, 2, self.constant_grammar(),
                               beta_normalize=True, max_normalization_steps=0)
        self.assertEqual(limited.termination, "normalization_budget")
        self.assertEqual(limited.normalization_steps, 0)
        self.assertEqual(limited.candidates, 0)
        self.assertEqual(limited.emitted_enumerator_terms, 1)
        self.assertFalse(limited.exhausted)

    def test_beta_normalization_unlocks_an_actual_enumerator_generated_repair(self):
        grammar, request = self.arithmetic_grammar(), Arrow(INT, INT)
        seed = self.enumerated_seed(request, grammar, 3,
                                    lambda t: t == apply(Prim("add"), Int(0)))
        self.assertTrue(verify(seed, [((9,), 9)], library=grammar.library))
        kwargs = {"accepted_seeds": (RepairSeed(seed, "identity:verifier-pass"),),
                  "seed_prefix": 0, "max_size": 5}
        examples = [((1,), 2), ((5,), 2), ((-7,), 2)]
        previous = solve_repair(examples, request, 64, grammar, **kwargs)
        revised = solve_repair(examples, request, 64, grammar, beta_normalize=True, **kwargs)
        self.assertIsNone(previous.term)
        self.assertEqual(previous.termination, "repair_space_exhausted")
        self.assertGreater(previous.invalid_repairs, 0)
        self.assertEqual(revised.termination, "public_match")
        self.assertTrue(verify(revised.term, [((100,), 2), ((-50,), 2)],
                               library=grammar.library))
        self.assertGreater(revised.beta_reductions, 0)
        self.assertGreater(revised.normalization_steps, 0)
        self.assertEqual(revised.trials[-1]["source"], "repair")

    def test_normalized_candidate_must_still_fit_the_ast_bound(self):
        argument = apply(Prim("add"), Int(1), Int(2))
        raw = App(Lam(INT, apply(Prim("add"), Var(0), Var(0))), argument)
        normalized = beta_normal_form(raw)
        self.assertEqual(raw.size, 12)
        self.assertEqual(normalized.term.size, 13)
        self.assertEqual(evaluate(raw).value, evaluate(normalized.term).value)
        # This accepted fixture exercises only admission; its normalized form
        # must be rejected before any candidate interpreter call at size12.
        self.assertTrue(verify(raw, [((), 6)]))
        result = solve_repair([((), 99)], INT, 1, self.arithmetic_grammar(),
                              accepted_seeds=(RepairSeed(raw, "six:verifier-pass"),),
                              seed_prefix=0, beta_normalize=True, max_size=12)
        self.assertEqual(result.invalid_repairs, 1)
        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.evaluator_calls, 0)
        self.assertGreater(result.normalization_steps, 0)


if __name__ == "__main__":
    unittest.main()
