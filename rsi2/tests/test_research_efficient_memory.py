"""Live synthetic counterexamples and equivalence for per-task certified reuse."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.enumeration import enumerate_programs
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.learning import State
from rsi2.recognition import Recognition
from rsi2.research import efficient_memory, memory
from rsi2.search import HEURISTIC_TYPE
from rsi2.terms import Int, Prim
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES


SEARCH = {"max_size": 1, "max_expansions": 20, "step_budget": 2000}


def _grammar(order=("neg", "abs"), **kwargs):
    return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in order},
                   constants=(), **kwargs)


def _task(name="magnitude"):
    return Task(name, Arrow(INT, INT), (((2,), 2),), (((-3,), 3),))


def _logical(report):
    """Keep all original non-timing report fields; remove only reuse attribution."""
    report = copy.deepcopy(report)
    for key in tuple(report):
        if key in ("cache_hit", "wall_seconds") or key.startswith("actual_"):
            report.pop(key)
    for record in report["records"]:
        for key in tuple(record):
            if (key in ("cache_hit", "wall_seconds", "source_budget", "requested_budget", "reuse_kind")
                    or key.startswith(("actual_", "source_"))):
                record.pop(key)
    return report


def _recognizer(grammar):
    model = Recognition(31)
    negative = Task("negative", Arrow(INT, INT), (((2,), -2), ((-4,), 4)), ())
    magnitude = Task("absolute", Arrow(INT, INT), (((2,), 2), ((-4,), 4)), ())
    model.fit([(negative, Prim("neg")), (magnitude, Prim("abs"))], grammar)
    return model


class EfficientMemoryTests(unittest.TestCase):
    def test_live_multitask_decomposition_equals_original_assessment(self):
        state = State(11, grammar=_grammar())
        tasks = [_task(), Task("negative", Arrow(INT, INT), (((2,), -2),), (((-3,), 3),)),
                 Task("unavailable", Arrow(INT, INT), (((2,), 7),), (((-3,), 7),))]
        direct = memory.assess(tasks, state.grammar, None, 2, SEARCH,
                               conditioner=state.condition)
        cache = efficient_memory.EfficientEvaluationMemory()
        with patch.object(efficient_memory, "assess", wraps=memory.assess) as observe:
            first = cache.measure(state, iter(tasks), None, 2, SEARCH)
            second = cache.measure(state, reversed(tasks), None, 2, SEARCH)
        self.assertEqual(_logical(first), _logical(direct))
        self.assertEqual(first["solved"], 2)
        self.assertEqual(first["mean_candidates_to_solution"], 1.5)
        self.assertEqual(first["candidate_evaluations"], 5)
        self.assertEqual(observe.call_count, 3)
        self.assertTrue(all(len(call.args[0]) == 1 for call in observe.call_args_list))
        self.assertEqual([r["name"] for r in second["records"]], [t.name for t in reversed(tasks)])
        self.assertEqual(second["actual_candidate_evaluations"], 0)
        self.assertTrue(second["cache_hit"])
        self.assertEqual(cache.actual_candidate_evaluations, 5)

    def test_shared_cross_arm_exact_hits_have_independent_actual_counters(self):
        store = efficient_memory.SharedStore()
        first_arm = efficient_memory.EfficientEvaluationMemory(store)
        second_arm = efficient_memory.EfficientEvaluationMemory(store)
        state = State(11, grammar=_grammar())
        first = first_arm.measure(state, [_task()], None, 2, SEARCH)
        second = second_arm.measure(memory.restore(memory.snapshot(state)), [_task()], None, 2, SEARCH)
        self.assertEqual(_logical(first), _logical(second))
        self.assertEqual(first_arm.actual_candidate_evaluations, 2)
        self.assertEqual(second_arm.actual_candidate_evaluations, 0)
        self.assertEqual(second["records"][0]["reuse_kind"], "exact")
        self.assertEqual(second["records"][0]["source_budget"], 2)
        self.assertEqual(second_arm.summary()["exact_hits"], 1)
        self.assertEqual(store.summary()["entries"], 1)
        self.assertEqual(sum(m.actual_candidate_evaluations for m in (first_arm, second_arm)), 2)

    def test_budget_hit_cannot_hide_a_solution_at_larger_budget(self):
        cache = efficient_memory.EfficientEvaluationMemory()
        state = State(11, grammar=_grammar())
        first = cache.measure(state, [_task()], None, 1, SEARCH)
        second = cache.measure(state, [_task()], None, 2, SEARCH)
        self.assertFalse(first["records"][0]["public_matched"])
        self.assertEqual(first["records"][0]["candidates"], 1)
        self.assertFalse(first["records"][0]["exhausted"])
        self.assertFalse(second["cache_hit"])
        self.assertTrue(second["records"][0]["solved"])
        self.assertEqual(cache.actual_candidate_evaluations, 3)
        self.assertEqual(cache.summary()["certificate_hits"], 0)

    def test_completed_failed_space_certificate_equals_direct_higher_budget(self):
        state = State(11, grammar=_grammar(("neg",)))
        cache = efficient_memory.EfficientEvaluationMemory()
        first = cache.measure(state, [_task()], None, 2, SEARCH)
        direct = memory.assess([_task()], state.grammar, None, 9, SEARCH)
        with patch.object(efficient_memory, "assess", side_effect=AssertionError("certificate should reuse")):
            higher = cache.measure(state, [_task()], None, 9, SEARCH)
        self.assertFalse(first["records"][0]["public_matched"])
        self.assertTrue(first["records"][0]["exhausted"])
        self.assertEqual(first["candidate_evaluations"], 1)
        self.assertEqual(_logical(higher), _logical(direct))
        self.assertEqual(higher["budget"], 9)
        self.assertEqual(higher["records"][0]["requested_budget"], 9)
        self.assertEqual(higher["records"][0]["source_budget"], 2)
        self.assertEqual(higher["records"][0]["reuse_kind"], "early_termination_certificate")
        self.assertEqual(higher["actual_candidate_evaluations"], 0)
        self.assertEqual(cache.actual_candidate_evaluations, 1)

    def test_expansion_cap_certificate_is_reused_but_changed_cap_misses(self):
        state = State(11, grammar=_grammar())
        cache = efficient_memory.EfficientEvaluationMemory()
        capped = {**SEARCH, "max_expansions": 1}
        first = cache.measure(state, [_task()], None, 2, capped)
        direct = memory.assess([_task()], state.grammar, None, 9, capped)
        higher = cache.measure(state, [_task()], None, 9, capped)
        self.assertEqual(first["candidate_evaluations"], 0)
        self.assertTrue(first["records"][0]["exhausted"])
        self.assertEqual(_logical(higher), _logical(direct))
        self.assertTrue(higher["cache_hit"])
        self.assertEqual(higher["records"][0]["reuse_kind"], "early_termination_certificate")
        changed = cache.measure(state, [_task()], None, 9, SEARCH)
        self.assertFalse(changed["cache_hit"])
        self.assertTrue(changed["records"][0]["solved"])
        self.assertEqual(cache.summary()["task_assessment_calls"], 2)

    def test_zero_candidate_certificate_records_saved_heuristic_work(self):
        synthesis = Grammar(primitives={"add": PRIMITIVE_TYPES["add"]}, constants=())
        heuristic = next(enumerate_programs(HEURISTIC_TYPE, synthesis,
                                           max_size=6, max_expansions=500)).term
        state = State(11, grammar=_grammar())
        cache = efficient_memory.EfficientEvaluationMemory()
        capped = {**SEARCH, "max_expansions": 1}
        first = cache.measure(state, [_task()], heuristic, 2, capped)
        higher = cache.measure(state, [_task()], heuristic, 9, capped)
        self.assertEqual(first["actual_candidate_evaluations"], 0)
        for metric in ("heuristic_calls", "heuristic_evaluations", "heuristic_steps"):
            self.assertGreater(first[f"actual_{metric}"], 0)
            self.assertEqual(higher[f"actual_{metric}"], 0)
            self.assertEqual(first["records"][0][metric], higher["records"][0][metric])
            self.assertEqual(cache.summary()[f"actual_{metric}"], first[f"actual_{metric}"])
        self.assertTrue(higher["cache_hit"])
        self.assertEqual(higher["actual_evaluation_steps"], 0)
        self.assertEqual(higher["actual_verification_steps"], 0)

    def test_partial_hit_and_duplicate_tasks_charge_only_new_task_work(self):
        state = State(11, grammar=_grammar())
        cache = efficient_memory.EfficientEvaluationMemory()
        previous = cache.measure(state, [_task("previous")], None, 2, SEARCH)
        other = _task("new")
        with patch.object(efficient_memory, "assess", wraps=memory.assess) as observe:
            mixed = cache.measure(state, [_task("previous"), other, other], None, 2, SEARCH)
        self.assertEqual(observe.call_count, 1)
        self.assertEqual([r["cache_hit"] for r in mixed["records"]], [True, False, True])
        self.assertFalse(mixed["cache_hit"])
        self.assertEqual(mixed["candidate_evaluations"], 6)
        self.assertEqual(mixed["actual_candidate_evaluations"], 2)
        self.assertEqual(cache.actual_candidate_evaluations, 4)
        for metric in ("evaluation_steps", "verification_steps"):
            self.assertGreater(mixed[f"actual_{metric}"], 0)
            self.assertEqual(mixed[f"actual_{metric}"], mixed["records"][1][metric])
            self.assertEqual(cache.summary()[f"actual_{metric}"],
                             previous[f"actual_{metric}"] + mixed[f"actual_{metric}"])

    def test_hidden_verifier_failure_never_supplies_a_cross_budget_certificate(self):
        task = Task("ambiguous", Arrow(INT, INT), (((0,), 0),), (((3,), 3),))
        state = State(11, grammar=_grammar())
        cache = efficient_memory.EfficientEvaluationMemory()
        first = cache.measure(state, [task], None, 1, SEARCH)
        higher = cache.measure(state, [task], None, 4, SEARCH)
        self.assertTrue(first["records"][0]["public_matched"])
        self.assertFalse(first["solved"])
        self.assertEqual(first["records"][0]["failure"]["stage"], "verification")
        self.assertFalse(higher["cache_hit"])
        self.assertEqual(cache.summary()["certificates"], 0)
        exact = cache.measure(state, [task], None, 1, SEARCH)
        self.assertTrue(exact["cache_hit"])
        self.assertEqual(exact["records"][0]["reuse_kind"], "exact")

    def test_certificate_is_only_reused_upwards_not_at_a_smaller_budget(self):
        state = State(11, grammar=_grammar(("neg",)))
        cache = efficient_memory.EfficientEvaluationMemory()
        cache.measure(state, [_task()], None, 9, SEARCH)
        smaller = cache.measure(state, [_task()], None, 2, SEARCH)
        self.assertFalse(smaller["cache_hit"])
        self.assertEqual(smaller["actual_candidate_evaluations"], 1)

    def test_all_certificate_scope_dependencies_require_new_measurement(self):
        for change in ("max_size", "max_expansions", "step_budget", "public", "hidden",
                       "name", "type", "public_order", "hidden_order", "weights",
                       "context", "primitive_order", "constant_order", "library_order",
                       "library_body", "recognizer", "heuristic"):
            with self.subTest(change=change):
                # Library bodies are produced by the unchanged typed enumerator.
                library = {f"lib_{name}": next(enumerate_programs(Arrow(INT, INT), _grammar((name,)),
                                                                max_size=1, max_expansions=10)).term
                           for name in ("neg", "abs")}
                grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("neg", "abs")},
                                  constants=(Int(0), Int(1)), library=library)
                state = State(11, grammar=grammar)
                task = Task("unavailable", Arrow(INT, INT), (((2,), 7), ((3,), 7)),
                            (((-3,), 7), ((-4,), 7)))
                limits = dict(SEARCH)
                cache = efficient_memory.EfficientEvaluationMemory()
                first = cache.measure(state, [task], None, 20, limits)
                self.assertTrue(first["records"][0]["exhausted"])
                self.assertLess(first["candidate_evaluations"], 20)
                heuristic = None
                if change in SEARCH:
                    limits[change] += 1
                elif change == "public":
                    task = replace(task, examples=(((2,), 8),))
                elif change == "hidden":
                    task = replace(task, hidden=(((-3,), 8),))
                elif change == "name":
                    task = replace(task, name="different")
                elif change == "type":
                    task = replace(task, request_type=INT)
                elif change == "public_order":
                    task = replace(task, examples=tuple(reversed(task.examples)))
                elif change == "hidden_order":
                    task = replace(task, hidden=tuple(reversed(task.hidden)))
                elif change == "weights":
                    state.grammar.weights["abs"] = 2.0
                elif change == "context":
                    state.grammar.context_weights[("ROOT", 0)] = {"abs": 2.0}
                elif change == "primitive_order":
                    state.grammar.primitives = dict(reversed(tuple(state.grammar.primitives.items())))
                elif change == "constant_order":
                    state.grammar.constants = tuple(reversed(state.grammar.constants))
                elif change == "library_order":
                    state.grammar.library = dict(reversed(tuple(state.grammar.library.items())))
                elif change == "library_body":
                    state.grammar.library["lib_neg"] = library["lib_abs"]
                elif change == "recognizer":
                    state.recognition = _recognizer(state.grammar)
                elif change == "heuristic":
                    heuristic = zero_heuristic()
                changed = cache.measure(state, [task], heuristic, 30, limits)
                self.assertFalse(changed["cache_hit"])
                self.assertEqual(cache.summary()["task_assessment_calls"], 2)

    def test_live_primitive_order_change_can_change_success_and_must_miss(self):
        state = State(11, grammar=_grammar())
        cache = efficient_memory.EfficientEvaluationMemory()
        first = cache.measure(state, [_task()], None, 1, SEARCH)
        state.grammar = _grammar(("abs", "neg"))
        second = cache.measure(state, [_task()], None, 1, SEARCH)
        self.assertEqual((first["solved"], second["solved"]), (0, 1))
        self.assertFalse(second["cache_hit"])

    def test_recognizer_parameter_changes_invalidate_exact_scope(self):
        state = State(11, grammar=_grammar())
        state.recognition = _recognizer(state.grammar)
        cache = efficient_memory.EfficientEvaluationMemory()
        cache.measure(state, [_task()], None, 1, SEARCH)
        state.recognition.weights[0, 0, 0] += 0.25
        changed = cache.measure(state, [_task()], None, 1, SEARCH)
        self.assertFalse(changed["cache_hit"])

    def test_public_list_and_tuple_arguments_cannot_share_a_scope(self):
        state = State(11, grammar=_grammar(("head",)))
        task = Task("container-input", Arrow(ListOf(INT), INT),
                    ((([2],), 2),), ((([3],), 3),))
        tuple_task = replace(task, examples=((((2,),), 2),))
        cache = efficient_memory.EfficientEvaluationMemory()
        listed = cache.measure(state, [task], None, 2, SEARCH)
        tupled = cache.measure(state, [tuple_task], None, 2, SEARCH)
        direct = memory.assess([tuple_task], state.grammar, None, 2, SEARCH)
        self.assertTrue(listed["records"][0]["public_matched"])
        self.assertTrue(listed["records"][0]["solved"])
        self.assertFalse(tupled["records"][0]["public_matched"])
        self.assertFalse(tupled["cache_hit"])
        self.assertEqual(_logical(tupled), _logical(direct))

    def test_hidden_list_and_tuple_inputs_and_outputs_cannot_share_scope(self):
        for change in ("input", "output"):
            with self.subTest(change=change):
                operation = "head" if change == "input" else "tail"
                output_type = INT if change == "input" else ListOf(INT)
                public_output = 2 if change == "input" else [4]
                hidden_output = 3 if change == "input" else [5]
                state = State(11, grammar=_grammar((operation,)))
                task = Task("hidden-container", Arrow(ListOf(INT), output_type),
                            ((([2, 4],), public_output),), ((([3, 5],), hidden_output),))
                altered = replace(task, hidden=((((3, 5),), hidden_output),)) if change == "input" else (
                    replace(task, hidden=((([3, 5],), (5,)),)))
                cache = efficient_memory.EfficientEvaluationMemory()
                source = cache.measure(state, [task], None, 2, SEARCH)
                different = cache.measure(state, [altered], None, 2, SEARCH)
                self.assertTrue(source["records"][0]["solved"])
                self.assertFalse(different["records"][0]["solved"])
                self.assertFalse(different["cache_hit"])
                self.assertEqual(different["records"][0]["failure"]["stage"], "verification")

    def test_typed_scope_keys_preserve_nested_containers_and_scalar_types(self):
        for left, right in (([[[2]]], [[(2,)]]), ([True], [1]), ([1], [1.0]),
                            ({"nested": [2]}, {"nested": (2,)})):
            self.assertNotEqual(efficient_memory._key(left), efficient_memory._key(right))
        self.assertEqual(efficient_memory._key({"b": [1], "a": (2,)}),
                         efficient_memory._key({"a": (2,), "b": [1]}))

    def test_shared_store_does_not_expose_mutable_report_aliases(self):
        state = State(11, grammar=_grammar(("neg",)))
        store = efficient_memory.SharedStore()
        first = efficient_memory.EfficientEvaluationMemory(store)
        second = efficient_memory.EfficientEvaluationMemory(store)
        source = first.measure(state, [_task()], None, 2, SEARCH)
        expected = _logical(source)
        source["records"][0]["public_matched"] = True
        source["records"][0]["failure"]["attempted"] = 999
        source["records"].append({"name": "forged"})
        replay = second.measure(state, [_task()], None, 2, SEARCH)
        self.assertEqual(_logical(replay), expected)
        replay["records"][0]["exhausted"] = False
        higher = first.measure(state, [_task()], None, 9, SEARCH)
        self.assertEqual(higher["records"][0]["candidates"], 1)
        self.assertTrue(higher["cache_hit"])
        self.assertEqual(first.actual_candidate_evaluations, 1)
        self.assertEqual(second.actual_candidate_evaluations, 0)

    def test_hit_wall_time_and_actual_counters_do_not_copy_historical_work(self):
        state = State(11, grammar=_grammar())
        cache = efficient_memory.EfficientEvaluationMemory()
        report = memory.assess([_task()], state.grammar, None, 2, SEARCH)
        report["wall_seconds"] = 12345.0
        report["records"][0]["wall_seconds"] = 12345.0
        with patch.object(efficient_memory, "assess", return_value=report):
            first = cache.measure(state, [_task()], None, 2, SEARCH)
        hit = cache.measure(state, [_task()], None, 2, SEARCH)
        self.assertEqual(hit["records"][0]["source_wall_seconds"], 12345.0)
        self.assertLess(hit["wall_seconds"], 1.0)
        self.assertLess(hit["records"][0]["wall_seconds"], 1.0)
        self.assertEqual(hit["actual_candidate_evaluations"], 0)
        for key, value in hit["records"][0].items():
            if key.startswith("actual_") and key != "actual_wall_seconds":
                self.assertEqual(value, 0, key)
        self.assertEqual(_logical(first), _logical(hit))

    def test_empty_measurement_has_defined_zero_counts(self):
        cache = efficient_memory.EfficientEvaluationMemory()
        report = cache.measure(State(11, grammar=_grammar()), [], None, 2, SEARCH)
        self.assertEqual(report["tasks"], 0)
        self.assertEqual(report["solved_fraction"], 0.0)
        self.assertIsNone(report["mean_candidates_to_solution"])
        self.assertEqual(report["candidate_evaluations"], 0)
        self.assertEqual(cache.actual_candidate_evaluations, 0)


if __name__ == "__main__":
    unittest.main()
