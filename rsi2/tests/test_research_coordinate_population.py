"""Integration: a coordinate generator shares the original causal controller."""
import heapq
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research.coordinate_population import solve_coordinate_population
from rsi2.research.derivation_neighborhood import reconstruct_neighbor
from rsi2.research.population_search import solve_population
from rsi2.research.proposals import canonical_term
from rsi2.research.repair_search import beta_normal_form
from rsi2.search import HEURISTIC_TYPE
from rsi2.terms import Int, Term
from rsi2.types import Arrow, INT, PRIMITIVE_TYPES


class CoordinatePopulationTests(unittest.TestCase):
    def grammar(self):
        return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("add", "sub", "neg")},
                       constants=(Int(0), Int(1), Int(2)))

    def own_heuristics(self):
        grammar = Grammar(primitives={}, constants=(Int(0),))
        own = [candidate.term for candidate in enumerate_programs(
            HEURISTIC_TYPE, grammar, max_size=5, max_expansions=100)]
        zero = next(term for term in own if evaluate(term, ([], [999], 7, 3)).value == 0)
        size = next(term for term in own if evaluate(term, ([], [999], 7, 3)).value == 7)
        return zero, size

    def run_search(self, heuristic=None, **kwargs):
        return solve_coordinate_population(
            [((1,), 999), ((2,), 999)], Arrow(INT, INT), 30, self.grammar(),
            seed_prefix=4, beta_normalize=True, heuristic=heuristic, **kwargs)

    def test_generic_hook_default_preserves_original_behavior_and_result_schema(self):
        arguments = ([((1,), 999)], Arrow(INT, INT), 12, self.grammar())
        plain = solve_population(*arguments, seed_prefix=4, beta_normalize=True)
        explicit = solve_population(*arguments, seed_prefix=4, beta_normalize=True,
                                    edit_provider=None)
        plain_values = {key: value for key, value in vars(plain).items()
                        if key not in ("cpu_seconds", "wall_seconds")}
        explicit_values = {key: value for key, value in vars(explicit).items()
                           if key not in ("cpu_seconds", "wall_seconds")}
        self.assertEqual(plain_values, explicit_values)
        self.assertNotIn("neighborhood_work", plain_values)
        self.assertFalse(any("edit_provenance" in trial for trial in plain.trials))

    def test_same_cold_prefix_precedes_the_different_candidate_generator(self):
        arguments = ([((1,), 999)], Arrow(INT, INT), 64, self.grammar())
        original = solve_population(*arguments, seed_prefix=16, beta_normalize=True)
        changed = solve_coordinate_population(*arguments, seed_prefix=16, beta_normalize=True)
        self.assertEqual(original.trials[:16], changed.trials[:16])
        self.assertEqual(original.seed_records, changed.seed_records)
        self.assertEqual(changed.seed_candidates, 16)
        self.assertTrue(changed.neighborhood_work["generated"] > 0)

    def test_own_zero_scorer_preserves_coordinate_sequence_and_parent_selection(self):
        zero, _ = self.own_heuristics()
        plain, scored = self.run_search(), self.run_search(zero)
        self.assertEqual(plain.trials, scored.trials)
        self.assertEqual(plain.parent_selections, scored.parent_selections)
        self.assertEqual(plain.neighborhood_work, scored.neighborhood_work)
        self.assertEqual(plain.expansions, scored.expansions)
        self.assertEqual(plain.normalization_steps, scored.normalization_steps)
        self.assertGreater(scored.heuristic_evaluations, 0)

    def test_own_nonzero_scorer_changes_future_coordinate_candidates(self):
        zero, size = self.own_heuristics()
        plain, scored = self.run_search(zero), self.run_search(size)
        self.assertEqual([trial["term"] for trial in plain.trials[:4]],
                         [trial["term"] for trial in scored.trials[:4]])
        self.assertNotEqual([trial["term"] for trial in plain.trials[4:]],
                            [trial["term"] for trial in scored.trials[4:]])
        self.assertNotEqual([turn["parent_id"] for turn in plain.parent_selections],
                            [turn["parent_id"] for turn in scored.parent_selections])
        self.assertIsNone(scored.term)  # Causal wiring does not establish capability gain.

    def test_coordinate_genealogy_reconstructs_raw_then_normalized_alpha_ast(self):
        result = self.run_search()
        trials = {trial["id"]: trial for trial in result.trials}
        roots = {record["trial_id"] for record in result.seed_records}
        descendants = [trial for trial in result.trials if trial["parent_id"] is not None]
        self.assertTrue(descendants)
        for trial in descendants:
            parent = trials[trial["parent_id"]]
            raw = reconstruct_neighbor(Term.from_dict(parent["term"]), Arrow(INT, INT),
                                       self.grammar(), trial["edit_provenance"])
            self.assertEqual(raw.to_dict(), trial["raw_term"])
            normalized = beta_normal_form(raw)
            self.assertTrue(normalized.complete)
            self.assertEqual(canonical_term(normalized.term).to_dict(), trial["term"])
            self.assertEqual(parent["root_id"], trial["root_id"])
            self.assertIn(trial["root_id"], roots)

    def test_all_root_heap_pops_and_coordinate_states_share_the_expansion_counter(self):
        observed = []
        original_pop = heapq.heappop

        def recorded_pop(heap):
            observed.append(1)
            return original_pop(heap)

        with patch("heapq.heappop", side_effect=recorded_pop):
            result = self.run_search(max_expansions=80)
        self.assertEqual(result.expansions, 80)
        self.assertEqual(result.termination, "expansion_budget")
        self.assertEqual(result.expansions,
                         len(observed) + result.neighborhood_work["structural_states"])
        self.assertGreater(result.neighborhood_work["structural_states"], 0)

    def test_coordinate_compiler_and_root_normalization_share_one_live_cap(self):
        result = self.run_search(max_normalization_steps=300)
        self.assertEqual(result.termination, "normalization_budget")
        self.assertEqual(result.normalization_steps, 300)
        self.assertGreater(result.neighborhood_work["compiler_steps"], 0)
        self.assertLessEqual(result.neighborhood_work["compiler_steps"], result.normalization_steps)

    def test_provider_adds_no_semantic_evaluations_and_controller_accounts_all_calls(self):
        zero, _ = self.own_heuristics()
        calls = []

        def recorded(term, inputs, **kwargs):
            assessment = evaluate(term, inputs, **kwargs)
            calls.append((term == zero, assessment.steps))
            return assessment

        with patch("rsi2.research.population_search.evaluate", side_effect=recorded):
            result = self.run_search(zero)
        self.assertEqual(result.evaluator_calls, sum(not heuristic for heuristic, _ in calls))
        self.assertEqual(result.heuristic_evaluations, sum(heuristic for heuristic, _ in calls))
        self.assertEqual(result.evaluation_steps,
                         sum(steps for heuristic, steps in calls if not heuristic))
        self.assertEqual(result.heuristic_steps,
                         sum(steps for heuristic, steps in calls if heuristic))
        self.assertEqual(result.neighborhood_work["semantic_evaluator_calls"], 0)
        self.assertLessEqual(result.candidates, 30)

    def test_zero_budget_and_zero_cpu_stop_before_coordinate_setup(self):
        arguments = ([((1,), 999)], Arrow(INT, INT), self.grammar())
        zero = solve_coordinate_population(arguments[0], arguments[1], 0, arguments[2])
        cpu = self.run_search(max_cpu_seconds=0)
        self.assertEqual(zero.candidates, 0)
        self.assertEqual(cpu.candidates, 0)
        self.assertEqual(cpu.termination, "cpu_budget")
        self.assertEqual(zero.neighborhood_work["compiler_steps"], 0)
        self.assertEqual(cpu.neighborhood_work["structural_states"], 0)

    def test_adapter_setup_cpu_is_deducted_from_the_kernel_allowance(self):
        for times, allowance, late in (([0, 3, 4, 4], 7, False),
                                       ([0, 12, 12, 12], 0, True)):
            result = SimpleNamespace(term=None, log_probability=None,
                                     termination="candidate_budget", exhausted=False,
                                     trials=[], evaluator_calls=9, evaluation_steps=123)
            with self.subTest(times=times), \
                    patch("rsi2.research.coordinate_population.time.process_time", side_effect=times), \
                    patch("rsi2.research.coordinate_population.solve_population", return_value=result) as kernel:
                returned = solve_coordinate_population([], INT, 16, self.grammar(),
                                                       max_cpu_seconds=10)
            self.assertEqual(kernel.call_args.kwargs["max_cpu_seconds"], allowance)
            self.assertEqual(returned.coordinate_setup_cpu_seconds, times[1])
            self.assertEqual(returned.cpu_seconds, times[-1])
            self.assertEqual(returned.coordinate_adapter_deadline_exceeded, late)
            self.assertEqual((returned.evaluator_calls, returned.evaluation_steps), (9, 123))

    def test_adapter_post_metadata_overrun_vetoes_late_success_without_erasing_work(self):
        term = Int(1)
        result = SimpleNamespace(term=term, log_probability=-1,
                                 termination="public_match", exhausted=False,
                                 trials=[{"public_match": True, "incomplete": False}],
                                 evaluator_calls=1, evaluation_steps=7)
        with patch("rsi2.research.coordinate_population.time.process_time", side_effect=[0, 2, 11, 11]), \
                patch("rsi2.research.coordinate_population.solve_population", return_value=result) as kernel:
            returned = solve_coordinate_population([((), 1)], INT, 16, self.grammar(),
                                                   max_cpu_seconds=10)
        self.assertEqual(kernel.call_args.kwargs["max_cpu_seconds"], 8)
        self.assertIsNone(returned.term)
        self.assertIsNone(returned.log_probability)
        self.assertEqual(returned.termination, "cpu_budget")
        self.assertTrue(returned.trials[0]["incomplete"])
        self.assertFalse(returned.trials[0]["public_match"])
        self.assertTrue(returned.trials[0]["coordinate_adapter_deadline_exceeded"])
        self.assertEqual((returned.evaluator_calls, returned.evaluation_steps), (1, 7))


if __name__ == "__main__":
    unittest.main()
