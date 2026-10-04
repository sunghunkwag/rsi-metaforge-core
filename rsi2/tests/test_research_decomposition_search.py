"""Synthetic accounting and applicability checks for enumerated map decomposition."""
import unittest
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research import decomposition_search as decomposition
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES


REQUEST = Arrow(ListOf(INT), ListOf(INT))
EXAMPLES = ((([1, 2],), [-1, -2]), (([3],), [-3]))


def _grammar():
    return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("map", "neg")}, constants=())


class DecompositionTests(unittest.TestCase):
    def test_enumerated_operator_and_component_compose_verified_public_root(self):
        result = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, _grammar())
        self.assertEqual(result.termination, "public_solution")
        self.assertIsNotNone(result.term)
        self.assertEqual([trial["stage"] for trial in result.trials], ["head", "component", "root"])
        self.assertEqual(result.head_attempts, 1)
        self.assertEqual(result.component_attempts, 1)
        self.assertEqual(result.root_attempts, 1)
        self.assertEqual(result.candidates, result.helper_attempts + result.root_attempts)
        self.assertTrue(all(trial["complete"] and trial["matched"] for trial in result.trials))
        self.assertEqual(result.term.children[0].to_dict(), result.trials[0]["term"])
        self.assertEqual(result.term.children[1].to_dict(), result.trials[1]["term"])
        for inputs, expected in EXAMPLES:
            self.assertEqual(evaluate(result.term, inputs).value, expected)

    def test_all_helper_example_evaluations_and_steps_are_exactly_charged(self):
        calls = []
        def measured(*args, **kwargs):
            result = evaluate(*args, **kwargs)
            calls.append(result)
            return result
        with patch.object(decomposition, "evaluate", side_effect=measured):
            result = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, _grammar())
        self.assertEqual(result.example_evaluations, len(calls))
        self.assertEqual(result.evaluator_steps, sum(call.steps for call in calls))
        self.assertEqual(result.example_evaluations, sum(t["example_evaluations"] for t in result.trials))
        self.assertEqual(result.evaluator_steps, sum(t["evaluator_steps"] for t in result.trials))
        self.assertEqual(result.example_evaluations, 6)
        self.assertGreater(result.evaluator_steps, 0)

    def test_matching_component_still_needs_budget_for_full_root_verification(self):
        result = decomposition.solve_decomposition(EXAMPLES, REQUEST, 2, _grammar())
        self.assertIsNone(result.term)
        self.assertEqual(result.termination, "candidate_budget")
        self.assertEqual(result.candidates, 2)
        self.assertEqual(result.helper_attempts, 2)
        self.assertEqual(result.root_attempts, 0)
        self.assertTrue(result.trials[-1]["matched"])

    def test_pointwise_detection_checks_every_public_example_and_rejects_conflicts(self):
        conflicting = ((([1],), [-1]), (([1],), [1]))
        result = decomposition.solve_decomposition(conflicting, REQUEST, 64, _grammar())
        self.assertEqual(result.candidates, 0)
        self.assertEqual(result.decomposition["reason"], "inconsistent_pointwise_relation")
        self.assertEqual(result.termination, "not_applicable")
        self.assertEqual(result.example_evaluations, 0)

    def test_length_change_non_list_request_and_empty_relation_are_not_map_evidence(self):
        cases = (( ((([1, 2],), [-1]),), REQUEST, "length_mismatch"),
                 ( ((([1],), 1),), Arrow(ListOf(INT), INT), "request_is_not_single_list_to_list"),
                 ( ((([],), []),), REQUEST, "no_observed_elements"))
        for examples, request, reason in cases:
            with self.subTest(reason=reason):
                result = decomposition.solve_decomposition(examples, request, 64, _grammar())
                self.assertEqual(result.decomposition["reason"], reason)
                self.assertEqual(result.candidates, 0)

    def test_aggregate_expansion_and_cpu_guards_preserve_partial_accounting(self):
        for cap in (0, 1, 2):
            with self.subTest(cap=cap):
                result = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, _grammar(), max_expansions=cap)
                self.assertEqual(result.termination, "expansion_budget")
                self.assertLessEqual(result.expansions, cap)
                self.assertIsNone(result.term)
        cpu = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, _grammar(), max_cpu_seconds=0)
        self.assertEqual(cpu.termination, "cpu_budget")
        self.assertEqual(cpu.candidates, 0)
        self.assertEqual(cpu.evaluator_steps, 0)
        ticks = 0
        def clock():
            nonlocal ticks
            ticks += 1
            return 0.0 if ticks < 20 else 100.0
        with patch.object(decomposition.time, "process_time", side_effect=clock):
            partial = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, _grammar(), max_cpu_seconds=1)
        self.assertEqual(partial.termination, "cpu_budget")
        self.assertEqual(partial.candidates, len(partial.trials))
        self.assertEqual(partial.example_evaluations, sum(t["example_evaluations"] for t in partial.trials))
        self.assertEqual(partial.evaluator_steps, sum(t["evaluator_steps"] for t in partial.trials))

    def test_current_library_operator_is_itself_sourced_by_enumeration(self):
        operator_type = Arrow(Arrow(INT, INT), REQUEST)
        source = Grammar(primitives={"map": PRIMITIVE_TYPES["map"]}, constants=())
        operator = next(enumerate_programs(operator_type, source, max_size=1, max_expansions=10)).term
        grammar = Grammar(primitives={"neg": PRIMITIVE_TYPES["neg"]}, constants=(),
                          library={"own_operator": operator})
        result = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, grammar)
        self.assertEqual(result.termination, "public_solution")
        self.assertEqual(result.trials[0]["term"]["tag"], "ref")

    def test_task_adapter_cannot_read_identity_or_private_examples(self):
        class Guarded:
            request_type = REQUEST
            examples = EXAMPLES
            @property
            def hidden(self):
                raise AssertionError("private access")
            @property
            def name(self):
                raise AssertionError("identity access")
        result = decomposition.search(Guarded(), _grammar(), 64)
        self.assertEqual(result.termination, "public_solution")

    def test_final_matching_call_crossing_cpu_guard_is_charged_and_rejected(self):
        elapsed, calls = 0.0, []
        def interpreter(*args, **kwargs):
            nonlocal elapsed
            measured = evaluate(*args, **kwargs)
            calls.append(measured)
            if len(calls) == 6:
                elapsed = 1.01
            return measured
        with patch.object(decomposition.time, "process_time", side_effect=lambda: elapsed), \
             patch.object(decomposition, "evaluate", side_effect=interpreter):
            result = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, _grammar(),
                                                      max_cpu_seconds=1)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertIsNone(result.term)
        self.assertEqual(result.root_attempts, 1)
        self.assertEqual(result.example_evaluations, 6)
        self.assertEqual(result.evaluator_steps, sum(call.steps for call in calls))
        self.assertFalse(result.trials[-1]["complete"])
        self.assertEqual(result.trials[-1]["failure"], "cpu_budget")

    def test_final_production_call_crossing_cpu_guard_is_not_normal_exhaustion(self):
        elapsed = 0.0
        class EmptyGrammar:
            library = {}
            def productions(self, *args, **kwargs):
                nonlocal elapsed
                elapsed = 1.01
                return ()
        with patch.object(decomposition.time, "process_time", side_effect=lambda: elapsed):
            result = decomposition.solve_decomposition(EXAMPLES, REQUEST, 64, EmptyGrammar(),
                                                      max_cpu_seconds=1)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertEqual(result.expansions, 1)
        self.assertEqual(result.candidates, 0)


if __name__ == "__main__":
    unittest.main()
