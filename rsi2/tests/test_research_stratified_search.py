"""Live synthetic binder-role coverage, typing and resource-accounting checks."""
import unittest
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research import stratified_search as stratified
from rsi2.terms import Int
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, infer, unify


REQUEST = Arrow(INT, INT)
EXAMPLES = (((2,), 0), ((5,), 3))
FIELDS = {"current_performance", "failure_clusters", "bottleneck",
          "previous_attempt_insufficiency", "intervention", "mechanism",
          "verification_plan", "regression_risks", "result", "keep_revert_revise", "updated_rule"}


def _grammar():
    return Grammar(primitives={"sub": PRIMITIVE_TYPES["sub"]},
                   constants=(Int(0), Int(1), Int(2)),
                   weights={"lambda": 0.01, "var": 0.01, "sub": 1})


class StratifiedSearchTests(unittest.TestCase):
    def test_baseline_prefix_is_the_unchanged_enumerator_prefix(self):
        grammar = _grammar()
        expected = []
        for candidate in enumerate_programs(REQUEST, grammar, max_size=12, max_expansions=20000):
            expected.append(candidate.term.to_dict())
            if len(expected) == 16:
                break
        result = stratified.solve_stratified((((2,), 12345),), REQUEST, 16, grammar)
        self.assertEqual([trial["term"] for trial in result.trials], expected)
        self.assertEqual(result.baseline_attempts, 16)
        self.assertEqual(result.stratum_attempts, 0)
        self.assertEqual(result.termination, "candidate_budget")

    def test_round_robin_covers_both_input_roles_and_identity_before_repeating(self):
        result = stratified.solve_stratified(EXAMPLES, REQUEST, 64, _grammar())
        self.assertEqual(result.termination, "public_solution")
        self.assertEqual(result.baseline_attempts, 16)
        roles = [(trial["source"]["head"], trial["source"]["role"])
                 for trial in result.trials[16:]]
        self.assertEqual(roles[:3], [("sub", 0), ("sub", 1), ("var:0", None)])
        self.assertEqual(roles[3:5], [("sub", 0), ("sub", 1)])
        self.assertTrue(result.trials[-1]["matched"])
        self.assertLessEqual(result.term.size, 12)
        for inputs, expected in EXAMPLES:
            self.assertEqual(evaluate(result.term, inputs).value, expected)
        self.assertEqual(result.candidates, result.baseline_attempts + result.stratum_attempts)
        self.assertEqual(result.helper_attempts, 0)
        self.assertEqual(set(result.report), FIELDS)
        self.assertFalse(result.report["updated_rule"]["learned_rule"])

    def test_every_interpreter_call_belongs_to_a_charged_full_root(self):
        calls = []
        def measured(term, inputs, **limits):
            result = evaluate(term, inputs, **limits)
            calls.append((term.to_dict(), result))
            return result
        with patch.object(stratified, "evaluate", side_effect=measured):
            result = stratified.solve_stratified(EXAMPLES, REQUEST, 64, _grammar())
        self.assertEqual(result.candidates, len(result.trials))
        self.assertEqual(result.example_evaluations, len(calls))
        self.assertEqual(result.evaluator_steps, sum(measured.steps for _, measured in calls))
        self.assertEqual(result.example_evaluations, sum(t["example_evaluations"] for t in result.trials))
        self.assertEqual(result.evaluator_steps, sum(t["evaluator_steps"] for t in result.trials))
        roots = [trial["term"] for trial in result.trials]
        self.assertTrue(all(term in roots for term, _ in calls))
        self.assertGreater(result.generated_wrappers, 0)
        self.assertEqual(result.helper_attempts, 0)

    def test_wrapper_constraint_retains_original_probabilities_and_only_fixes_binder(self):
        grammar = _grammar()
        result = stratified.SearchResult()
        meter = stratified._Meter(grammar, result, lambda: None, 100, "argument", force_lambdas=1)
        original = grammar.productions(REQUEST, (), {})
        forced = meter.productions(REQUEST, (), {})
        self.assertTrue(forced)
        self.assertTrue(all(choice.is_lambda for choice in forced))
        self.assertEqual([choice.log_probability for choice in forced],
                         [choice.log_probability for choice in original if choice.is_lambda])
        body = meter.productions(INT, (INT,), {})
        self.assertTrue(any(choice.name == "var:0" for choice in body))
        self.assertTrue(any(choice.name == "sub" for choice in body))

    def test_polymorphic_map_head_threads_list_and_scalar_function_types(self):
        request = Arrow(ListOf(INT), ListOf(INT))
        examples = ((([1, 2],), [-1, -2]), (([3],), [-3]))
        grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("map", "neg")},
                          constants=())
        # Isolate the stratum mechanism; the registered default remains16.
        with patch.object(stratified, "BASELINE_PREFIX", 0):
            result = stratified.solve_stratified(examples, request, 64, grammar)
        self.assertEqual(result.termination, "public_solution")
        self.assertEqual(result.trials[-1]["source"]["head"], "map")
        self.assertEqual(result.trials[-1]["source"]["role"], 1)
        unify(infer(result.term, library=grammar.library), request)
        self.assertTrue(all(evaluate(result.term, inputs).value == expected for inputs, expected in examples))

    def test_polymorphic_if_sibling_roles_keep_condition_boolean_and_branches_integer(self):
        grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("if", "eq")},
                          constants=(Int(0), Int(1)))
        with patch.object(stratified, "BASELINE_PREFIX", 0):
            result = stratified.solve_stratified((((2,), 12345),), REQUEST, 12, grammar)
        roles = [trial["source"]["role"] for trial in result.trials
                 if trial["source"]["head"] == "if"]
        self.assertIn(1, roles)
        self.assertIn(2, roles)
        self.assertNotIn(0, roles)  # int input cannot fill bool condition.
        from rsi2.terms import Term
        for trial in result.trials:
            root = Term.from_dict(trial["term"])
            unify(infer(root, library=grammar.library), REQUEST)
            self.assertNotEqual(trial["failure"], "type_mismatch")

    def test_size_cap_rejects_oversized_identity_and_all_other_roots(self):
        with patch.object(stratified, "BASELINE_PREFIX", 0):
            tiny = stratified.solve_stratified((((2,), 999),), REQUEST, 64, _grammar(), max_size=1)
        self.assertEqual(tiny.candidates, 0)
        self.assertEqual(tiny.termination, "strata_exhausted")
        from rsi2.terms import Term
        for maximum in (2, 5, 12):
            result = stratified.solve_stratified((((2,), 999),), REQUEST, 32,
                                                 _grammar(), max_size=maximum)
            self.assertTrue(all(Term.from_dict(t["term"]).size <= maximum for t in result.trials))

    def test_candidate_and_aggregate_expansion_caps_never_leak_helper_budget(self):
        for budget in (0, 1, 2, 16, 20):
            result = stratified.solve_stratified((((2,), 999),), REQUEST, budget, _grammar())
            self.assertLessEqual(result.candidates, budget)
            self.assertEqual(result.candidates, len(result.trials))
            self.assertEqual(result.helper_attempts, 0)
        for maximum in (0, 1, 2, 8, 40):
            result = stratified.solve_stratified((((2,), 999),), REQUEST, 64,
                                                 _grammar(), max_expansions=maximum)
            self.assertLessEqual(result.expansions, maximum)
            self.assertEqual(result.expansions, sum(result.expansion_counts.values()))
            self.assertIsNone(result.term)

    def test_cpu_deadline_keeps_charges_but_withholds_final_match(self):
        clock = [0.0]
        grammar = Grammar(primitives={"neg": PRIMITIVE_TYPES["neg"]}, constants=())
        def measured(*args, **kwargs):
            result = evaluate(*args, **kwargs)
            clock[0] = 2.0
            return result
        with patch.object(stratified.time, "process_time", side_effect=lambda: clock[0]), \
                patch.object(stratified, "evaluate", side_effect=measured):
            result = stratified.solve_stratified((((2,), -2),), REQUEST, 64,
                                                 grammar, max_cpu_seconds=1)
        self.assertEqual(result.termination, "cpu_budget")
        self.assertIsNone(result.term)
        self.assertEqual(result.candidates, 1)
        self.assertEqual(result.example_evaluations, 1)
        self.assertGreater(result.evaluator_steps, 0)
        self.assertEqual(result.trials[-1]["failure"], "cpu_budget")

    def test_adapter_reads_no_identity_private_examples_and_empty_public_is_not_success(self):
        class Guarded:
            request_type, examples = REQUEST, EXAMPLES
            @property
            def name(self):
                raise AssertionError("task identity read")
            @property
            def hidden(self):
                raise AssertionError("private examples read")
        result = stratified.search(Guarded(), _grammar())
        self.assertEqual(result.termination, "public_solution")
        empty = stratified.solve_stratified((), REQUEST, 64, _grammar())
        self.assertEqual(empty.termination, "no_public_examples")
        self.assertIsNone(empty.term)


if __name__ == "__main__":
    unittest.main()
