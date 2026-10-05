"""A B16 verifier screen must exercise the scorer's future-generation action."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research.budget_policy import allocate_roots, solve_reserved_population
from rsi2.research.population_search import solve_population
from rsi2.research.proposals import canonical_term
from rsi2.research.repair_search import RepairSeed, beta_normal_form
from rsi2.search import HEURISTIC_TYPE
from rsi2.terms import Int, Term, replace_subterm
from rsi2.types import Arrow, INT, PRIMITIVE_TYPES


class ReservedRootPolicyTests(unittest.TestCase):
    def grammar(self):
        return Grammar(primitives={"add": PRIMITIVE_TYPES["add"]},
                       constants=(Int(0), Int(1), Int(2)))

    def own_heuristics(self):
        grammar = Grammar(primitives={}, constants=(Int(0),))
        terms = [c.term for c in enumerate_programs(
            HEURISTIC_TYPE, grammar, max_size=5, max_expansions=100)]
        zero = next(h for h in terms if evaluate(h, ([], [999], 7, 3)).value == 0)
        size = next(h for h in terms if evaluate(h, ([], [999], 7, 3)).value == 7)
        return zero, size

    def bank(self, count):
        terms = [c.term for c in enumerate_programs(
            Arrow(INT, INT), self.grammar(), max_size=12, max_expansions=500)]
        return tuple(RepairSeed(terms[i % len(terms)], f"proof-{i:03}")
                     for i in range(count))

    def search(self, heuristic=None, *, bank=(), budget=16):
        return solve_reserved_population(
            [((1,), 999), ((2,), 999)], Arrow(INT, INT), budget,
            self.grammar(), accepted_seeds=bank, heuristic=heuristic,
            beta_normalize=True)

    def test_b16_total_roots_remain_bounded_as_verified_bank_grows(self):
        for count in (0, 1, 4, 16, 100):
            allocation = allocate_roots(16, self.bank(count))
            self.assertLessEqual(len(allocation.selected_bank), 4)
            self.assertEqual(allocation.planned_roots, 8)
            self.assertGreaterEqual(allocation.fresh_prefix, 1)
            self.assertEqual(allocation.reserved_descendant_slots, 8)

    def test_b64_cold_prefix_is_preserved_and_bank_cannot_saturate_budget(self):
        cold = allocate_roots(64)
        self.assertEqual(cold.fresh_prefix, 16)
        self.assertEqual(cold.reserved_descendant_slots, 48)
        growing = allocate_roots(64, self.bank(100))
        self.assertEqual(len(growing.selected_bank), 16)
        self.assertEqual(growing.fresh_prefix, 16)
        self.assertEqual(growing.reserved_descendant_slots, 32)

    def test_b64_cold_actual_search_matches_the_original_population_kernel(self):
        examples, request = [((1,), 999), ((2,), 999)], Arrow(INT, INT)
        original = solve_population(examples, request, 64, self.grammar(),
                                    seed_prefix=16, beta_normalize=True)
        revised = self.search(budget=64)
        self.assertEqual(original.trials, revised.trials)
        self.assertEqual(original.seed_records, revised.seed_records)
        self.assertEqual(original.parent_selections, revised.parent_selections)
        self.assertEqual(original.expansions, revised.expansions)
        self.assertEqual(original.evaluator_calls, revised.evaluator_calls)
        self.assertEqual(original.evaluation_steps, revised.evaluation_steps)
        self.assertEqual(original.normalization_steps, revised.normalization_steps)

    def test_bank_allocation_is_stable_under_input_order_and_uses_existing_ids(self):
        bank = self.bank(12)
        left, right = allocate_roots(16, bank), allocate_roots(16, reversed(bank))
        self.assertEqual(left, right)
        self.assertEqual([r.training_record for r in left.selected_bank],
                         ["proof-000", "proof-001", "proof-002", "proof-003"])

    def test_no_scorer_and_own_enumerated_zero_preserve_actual_screen_sequence(self):
        zero, _ = self.own_heuristics()
        plain, scored = self.search(), self.search(zero)
        self.assertEqual(plain.trials, scored.trials)
        self.assertEqual(plain.seed_records, scored.seed_records)
        self.assertEqual(plain.parent_selections, scored.parent_selections)
        self.assertEqual(plain.root_allocation, scored.root_allocation)
        self.assertEqual(plain.candidates, 16)
        self.assertGreaterEqual(plain.repair_candidates, 8)
        self.assertGreater(len(plain.parent_selections), 0)

    def test_own_nonzero_scorer_changes_future_descendants_at_screen_budget(self):
        zero, size = self.own_heuristics()
        baseline, scored = self.search(zero), self.search(size)
        self.assertEqual(baseline.candidates, scored.candidates)
        self.assertEqual(baseline.candidates, 16)
        self.assertEqual(baseline.seed_records, scored.seed_records)
        self.assertEqual(baseline.root_allocation, scored.root_allocation)
        self.assertNotEqual([t["term"] for t in baseline.trials],
                            [t["term"] for t in scored.trials])
        self.assertNotEqual([s["parent_id"] for s in baseline.parent_selections],
                            [s["parent_id"] for s in scored.parent_selections])
        self.assertIsNone(scored.term)  # Causal exposure is not a task gain.

    def test_large_bank_still_leaves_actual_descendants_and_valid_genealogy(self):
        result = self.search(bank=self.bank(100))
        self.assertEqual(result.candidates, 16)
        self.assertLessEqual(result.seed_candidates, 8)
        self.assertGreaterEqual(result.repair_candidates, 8)
        trials = {t["id"]: t for t in result.trials}
        roots = {s["trial_id"] for s in result.seed_records}
        for trial in result.trials:
            self.assertIn(trial["root_id"], roots)
            if trial["parent_id"] is None:
                continue
            parent = trials[trial["parent_id"]]
            raw = replace_subterm(Term.from_dict(parent["term"]), tuple(trial["path"]),
                                  Term.from_dict(trial["replacement"]))
            normalized = beta_normal_form(raw)
            self.assertTrue(normalized.complete)
            self.assertEqual(raw.to_dict(), trial["raw_term"])
            self.assertEqual(canonical_term(normalized.term).to_dict(), trial["term"])

    def test_zero_one_and_two_budgets_are_explicit_and_never_exceed_budget(self):
        for budget, roots, descendants in ((0, 0, 0), (1, 1, 0), (2, 1, 1)):
            allocation = allocate_roots(budget, self.bank(20))
            self.assertEqual(allocation.planned_roots, roots)
            self.assertEqual(allocation.reserved_descendant_slots, descendants)
            result = self.search(bank=self.bank(20), budget=budget)
            self.assertLessEqual(result.candidates, budget)
            self.assertEqual(result.root_allocation, allocation.to_record())

    def test_invalid_limits_and_ambiguous_bank_proofs_fail_closed(self):
        for budget in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                allocate_roots(budget)
        for prefix in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                allocate_roots(16, seed_prefix=prefix)
        with self.assertRaises(TypeError):
            allocate_roots(16, (Int(0),))
        duplicate = self.bank(1)[0]
        with self.assertRaises(ValueError):
            allocate_roots(16, (duplicate, duplicate))

    def test_allocation_cpu_is_deducted_from_the_actual_kernel_allowance(self):
        for times, forwarded, late in (([0, 3, 4, 4], 7, False),
                                       ([0, 12, 12, 12], 0, True)):
            result = SimpleNamespace(term=None, log_probability=None,
                                     termination="candidate_budget", exhausted=False,
                                     trials=[], evaluator_calls=9, evaluation_steps=123)
            with self.subTest(times=times), \
                    patch("rsi2.research.budget_policy.time.process_time", side_effect=times), \
                    patch("rsi2.research.budget_policy.solve_population", return_value=result) as kernel:
                returned = solve_reserved_population([], INT, 16, self.grammar(),
                                                     max_cpu_seconds=10)
            self.assertEqual(kernel.call_args.kwargs["max_cpu_seconds"], forwarded)
            self.assertEqual(returned.root_policy_cpu_seconds, times[1])
            self.assertEqual(returned.cpu_seconds, times[-1])
            self.assertEqual(returned.root_policy_deadline_exceeded, late)
            self.assertEqual((returned.evaluator_calls, returned.evaluation_steps), (9, 123))

    def test_post_kernel_telemetry_deadline_rejects_a_late_matching_program(self):
        term = Int(1)
        result = SimpleNamespace(term=term, log_probability=-1,
                                 termination="public_match", exhausted=False,
                                 trials=[{"term": term.to_dict(), "public_match": True,
                                          "incomplete": False}],
                                 evaluator_calls=1, evaluation_steps=7)
        with patch("rsi2.research.budget_policy.time.process_time", side_effect=[0, 2, 11, 11]), \
                patch("rsi2.research.budget_policy.solve_population", return_value=result) as kernel:
            returned = solve_reserved_population([((), 1)], INT, 16, self.grammar(),
                                                 max_cpu_seconds=10)
        self.assertEqual(kernel.call_args.kwargs["max_cpu_seconds"], 8)
        self.assertIsNone(returned.term)
        self.assertIsNone(returned.log_probability)
        self.assertEqual(returned.termination, "cpu_budget")
        self.assertTrue(returned.trials[0]["incomplete"])
        self.assertFalse(returned.trials[0]["public_match"])
        self.assertTrue(returned.trials[0]["root_policy_deadline_exceeded"])
        self.assertEqual((returned.evaluator_calls, returned.evaluation_steps), (1, 7))


if __name__ == "__main__":
    unittest.main()
