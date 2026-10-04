"""Causal scorer influence, population provenance, and physical accounting."""
import unittest
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research.population_search import solve_population
from rsi2.research.repair_search import RepairSeed, beta_normal_form
from rsi2.search import HEURISTIC_TYPE, verify
from rsi2.terms import Int, Term, replace_subterm
from rsi2.types import Arrow, INT, PRIMITIVE_TYPES


class PopulationSearchTests(unittest.TestCase):
    def arithmetic_grammar(self):
        return Grammar(primitives={"add": PRIMITIVE_TYPES["add"]},
                       constants=(Int(0), Int(1), Int(2)))

    def own_heuristics(self):
        grammar = Grammar(primitives={}, constants=(Int(0),))
        terms = [candidate.term for candidate in enumerate_programs(
            HEURISTIC_TYPE, grammar, max_size=5, max_expansions=100)]
        # Select actual machine-enumerated programs by their verified behavior.
        zero = next(h for h in terms if evaluate(h, ([], [999], 7, 3)).value == 0)
        size = next(h for h in terms if evaluate(h, ([], [999], 7, 3)).value == 7)
        return zero, size

    def unsuccessful_search(self, heuristic=None, **kwargs):
        return solve_population([((1,), 999), ((2,), 999)], Arrow(INT, INT),
                                20, self.arithmetic_grammar(), seed_prefix=4,
                                beta_normalize=True, heuristic=heuristic, **kwargs)

    def test_no_scorer_and_own_enumerated_zero_have_identical_future_programs(self):
        zero, _ = self.own_heuristics()
        baseline, scored = self.unsuccessful_search(), self.unsuccessful_search(zero)
        self.assertEqual(baseline.trials, scored.trials)
        self.assertEqual(baseline.seed_records, scored.seed_records)
        self.assertEqual(baseline.parent_selections, scored.parent_selections)
        self.assertEqual(baseline.expansions, scored.expansions)
        self.assertEqual(baseline.evaluator_calls, scored.evaluator_calls)
        self.assertEqual(baseline.evaluation_steps, scored.evaluation_steps)
        self.assertEqual(baseline.normalization_steps, scored.normalization_steps)
        self.assertEqual(baseline.heuristic_evaluations, 0)
        self.assertGreater(scored.heuristic_evaluations, 0)
        self.assertGreater(scored.heuristic_steps, 0)

    def test_own_nonzero_scorer_changes_actual_future_candidates(self):
        zero, size = self.own_heuristics()
        baseline, learned = self.unsuccessful_search(zero), self.unsuccessful_search(size)
        prefix = baseline.seed_candidates
        self.assertEqual([t["term"] for t in baseline.trials[:prefix]],
                         [t["term"] for t in learned.trials[:prefix]])
        self.assertNotEqual([t["term"] for t in baseline.trials[prefix:]],
                            [t["term"] for t in learned.trials[prefix:]])
        self.assertNotEqual([p["parent_id"] for p in baseline.parent_selections],
                            [p["parent_id"] for p in learned.parent_selections])
        self.assertEqual(learned.candidates, 20)
        self.assertIsNone(learned.term)  # Causal influence alone is no performance gain.

    def test_descendant_edges_reconstruct_machine_generated_programs(self):
        result = solve_population([((1,), 999), ((2,), 999)], Arrow(INT, INT),
                                  64, self.arithmetic_grammar(), seed_prefix=4,
                                  beta_normalize=True)
        trials = {trial["id"]: trial for trial in result.trials}
        roots = {record["trial_id"] for record in result.seed_records}
        descendant_depths = []
        for trial in result.trials:
            self.assertIn(trial["root_id"], roots)
            if trial["parent_id"] is None:
                self.assertIn(trial["id"], roots)
                continue
            self.assertLess(trial["parent_id"], trial["id"])
            parent = trials[trial["parent_id"]]
            raw = replace_subterm(Term.from_dict(parent["term"]), tuple(trial["path"]),
                                  Term.from_dict(trial["replacement"]))
            normalized = beta_normal_form(raw)
            self.assertTrue(normalized.complete)
            self.assertEqual(normalized.term.to_dict(), trial["term"])
            self.assertEqual(parent["root_id"], trial["root_id"])
            self.assertEqual(parent["depth"] + 1, trial["depth"])
            descendant_depths.append(trial["depth"])
        self.assertGreaterEqual(max(descendant_depths), 2)

    def test_fifo_turns_preserve_edit_opportunities_for_low_score_roots(self):
        _, size = self.own_heuristics()
        result = self.unsuccessful_search(size)
        selected = {s["parent_id"] for s in result.parent_selections}
        roots = {record["trial_id"] for record in result.seed_records}
        self.assertTrue(roots <= selected)
        self.assertTrue(any(s["kind"] == "fifo" for s in result.parent_selections))
        self.assertEqual([s["kind"] for s in result.parent_selections],
                         ["guided" if n % 2 == 0 else "fifo"
                          for n in range(len(result.parent_selections))])

    def test_all_task_and_heuristic_interpreter_calls_and_steps_are_accounted(self):
        zero, _ = self.own_heuristics()
        calls = []

        def recorded(term, inputs, **kwargs):
            result = evaluate(term, inputs, **kwargs)
            calls.append((term == zero, result.steps))
            return result

        with patch("rsi2.research.population_search.evaluate", side_effect=recorded):
            result = self.unsuccessful_search(zero)
        self.assertEqual(sum(not is_h for is_h, _ in calls), result.evaluator_calls)
        self.assertEqual(sum(is_h for is_h, _ in calls), result.heuristic_evaluations)
        self.assertEqual(sum(steps for is_h, steps in calls if not is_h),
                         result.evaluation_steps)
        self.assertEqual(sum(steps for is_h, steps in calls if is_h), result.heuristic_steps)
        self.assertEqual(result.heuristic_calls, result.candidates)
        self.assertLessEqual(result.heuristic_evaluations, result.heuristic_calls)

    def test_runtime_failure_gives_empty_outputs_to_the_scorer(self):
        _, size = self.own_heuristics()
        grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("head", "nil")},
                          constants=(Int(0),))
        heuristic_inputs = []

        def recorded(term, inputs, **kwargs):
            if term == size:
                heuristic_inputs.append(inputs)
            return evaluate(term, inputs, **kwargs)

        with patch("rsi2.research.population_search.evaluate", side_effect=recorded):
            result = solve_population([((), 99)], INT, 2, grammar, heuristic=size,
                                      seed_prefix=2, max_size=3)
        self.assertIsNotNone(result.trials[-1]["runtime_failure"])
        self.assertEqual(result.trials[-1]["outputs"], [])
        self.assertEqual(heuristic_inputs[-1][0], [])
        self.assertEqual(result.candidates, 2)

    def test_public_success_returns_immediately_without_scoring_or_reranking(self):
        _, size = self.own_heuristics()
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        result = solve_population([((), 1)], INT, 2, grammar, heuristic=size,
                                  seed_prefix=2, max_size=1)
        self.assertEqual(result.term, Int(1))
        self.assertEqual(result.heuristic_calls, 1)
        self.assertEqual(result.trials[-1]["heuristic_score"], None)
        self.assertEqual(result.parent_selections, [])
        self.assertEqual(result.termination, "public_match")

    def test_root_bank_provenance_is_preserved_and_its_attempt_counts(self):
        grammar, request = self.arithmetic_grammar(), Arrow(INT, INT)
        original = next(enumerate_programs(request, grammar, max_size=3,
                                           max_expansions=100)).term
        self.assertTrue(verify(original, [((3,), evaluate(original, (3,)).value)]))
        record = RepairSeed(original, "prior-TRAIN-cycle:verified")
        result = solve_population([((1,), 999)], request, 1, grammar,
                                  accepted_seeds=(record,), seed_prefix=16)
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.seed_candidates, 1)
        self.assertEqual(result.repair_candidates, 0)
        self.assertEqual(result.seed_records[0]["source"], "verified_train")
        self.assertEqual(result.seed_records[0]["training_record"], record.training_record)

    def test_expansion_limit_includes_complete_and_partial_root_pops(self):
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        result = solve_population([((), 9)], INT, 64, grammar,
                                  seed_prefix=2, max_size=1, max_expansions=2)
        self.assertEqual(result.expansions, 2)
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.termination, "expansion_budget")
        self.assertFalse(result.exhausted)

    def test_zero_and_cpu_and_normalization_caps_stop_without_unreported_work(self):
        grammar = self.arithmetic_grammar()
        zero = solve_population([((1,), 999)], Arrow(INT, INT), 0, grammar)
        self.assertEqual(zero.candidates, 0)
        self.assertEqual(zero.expansions, 0)
        cpu = solve_population([((1,), 999)], Arrow(INT, INT), 64, grammar,
                               max_cpu_seconds=0)
        self.assertEqual(cpu.termination, "cpu_budget")
        self.assertEqual(cpu.candidates, 0)
        normalized = solve_population([((1,), 999)], Arrow(INT, INT), 64, grammar,
                                      beta_normalize=True, max_normalization_steps=0)
        self.assertEqual(normalized.termination, "normalization_budget")
        self.assertEqual(normalized.candidates, 0)
        self.assertEqual(normalized.emitted_enumerator_terms, 1)

    def test_malformed_heuristic_or_bank_is_rejected_before_search(self):
        with self.assertRaises(TypeError):
            solve_population([((), 1)], INT, 1, self.arithmetic_grammar(),
                             heuristic=lambda _: 0)
        with self.assertRaises(TypeError):
            solve_population([((), 1)], INT, 1, self.arithmetic_grammar(),
                             accepted_seeds=(Int(1),))
        with self.assertRaises(TypeError):
            solve_population([((), 1)], INT, 1, self.arithmetic_grammar(), heuristic=Int(0))

    def test_public_evaluator_overrun_is_charged_and_cannot_accept_a_solution(self):
        now = [0.0]
        grammar = Grammar(primitives={}, constants=(Int(1),))
        expected_steps = evaluate(Int(1)).steps

        def overrun(term, inputs, **kwargs):
            result = evaluate(term, inputs, **kwargs)
            now[0] = 2.0
            return result

        with patch("rsi2.research.population_search.time.process_time",
                   side_effect=lambda: now[0]), patch(
                       "rsi2.research.population_search.evaluate", side_effect=overrun):
            result = solve_population([((), 1)], INT, 1, grammar, max_cpu_seconds=1)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertIsNone(result.term)
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.evaluator_calls, 1)
        self.assertEqual(result.evaluation_steps, expected_steps)
        self.assertEqual(result.cpu_seconds, 2.0)
        self.assertTrue(result.trials[-1]["incomplete"])
        self.assertFalse(result.trials[-1]["public_match"])
        self.assertEqual(result.parent_records, [])

    def test_scorer_overrun_is_charged_and_cannot_enter_the_parent_population(self):
        _, size = self.own_heuristics()
        now = [0.0]
        grammar = Grammar(primitives={}, constants=(Int(0),))
        steps = []

        def overrun(term, inputs, **kwargs):
            result = evaluate(term, inputs, **kwargs)
            if term == size:
                now[0] = 2.0
                steps.append(result.steps)
            return result

        with patch("rsi2.research.population_search.time.process_time",
                   side_effect=lambda: now[0]), patch(
                       "rsi2.research.population_search.evaluate", side_effect=overrun):
            result = solve_population([((), 9)], INT, 2, grammar, heuristic=size,
                                      max_cpu_seconds=1)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertEqual(result.heuristic_calls, 1)
        self.assertEqual(result.heuristic_evaluations, 1)
        self.assertEqual(result.heuristic_steps, sum(steps))
        self.assertTrue(result.trials[-1]["heuristic_incomplete"])
        self.assertIsNone(result.trials[-1]["heuristic_score"])
        self.assertEqual(result.parent_records, [])
        self.assertEqual(result.parent_selections, [])


if __name__ == "__main__":
    unittest.main()
