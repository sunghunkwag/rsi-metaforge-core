"""Independent cache-scope and failure-replay checks using live frozen searches."""
import copy
from dataclasses import replace
import json
import unittest

from rsi2.abstraction import learn_abstractions
from rsi2.corpus import Task
from rsi2.enumeration import enumerate_programs
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.learning import State
from rsi2.recognition import Recognition
from rsi2.research import memory
from rsi2.terms import Int, Prim
from rsi2.types import Arrow, BOOL, INT, PRIMITIVE_TYPES


SEARCH = {"max_size": 1, "max_expansions": 20, "step_budget": 2000}


def _task(name="magnitude"):
    return Task(name, Arrow(INT, INT), (((2,), 2),), (((-3,), 3),))


def _grammar(order=("neg", "abs"), **kwargs):
    return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in order},
                   constants=(), **kwargs)


def _learned_library():
    # Every body originates from the frozen enumerator and its own compressor.
    library = {}
    for generation, operation in enumerate(("neg", "abs"), 1):
        grammar = _grammar((operation,))
        source = next(candidate.term for candidate in enumerate_programs(
            Arrow(INT, INT), grammar, max_size=4, max_expansions=100)
            if candidate.term.tag == "lam" and candidate.term.size >= 4)
        _, library, records = learn_abstractions(
            {f"solution_{i}": source for i in range(6)}, library, generation)
        if not records:
            raise AssertionError("enumerated repeated solutions did not compress")
    return library


def _recognizer(grammar):
    model = Recognition(31)
    negative = Task("negative", Arrow(INT, INT), (((2,), -2), ((-4,), 4)), ())
    magnitude = Task("absolute", Arrow(INT, INT), (((2,), 2), ((-4,), 4)), ())
    model.fit([(negative, Prim("neg")), (magnitude, Prim("abs"))], grammar)
    return model


class ResearchMemoryTests(unittest.TestCase):
    def test_public_match_hidden_mismatch_logs_replayable_counterexample(self):
        task = Task("ambiguous", Arrow(INT, INT), (((0,), 0),), (((-3,), -3),))
        report = memory.assess([task], _grammar(), None, 1, SEARCH)
        record = report["records"][0]
        self.assertTrue(record["public_matched"])
        self.assertFalse(record["solved"])
        self.assertEqual(report["solved"], 0)
        self.assertEqual(report["candidate_evaluations"], 1)
        self.assertIsNone(record["candidates_to_solution"])
        # neg wins the public tie, then fails this independent hidden example.
        self.assertEqual(record["failure"], {"stage": "verification", "inputs": (-3,),
                                             "expected": -3, "actual": 3,
                                             "error": None})

    def test_verification_failure_distinguishes_observed_expected_and_actual(self):
        task = Task("ambiguous", Arrow(INT, INT), (((0,), 0),), (((3,), 3),))
        report = memory.assess([task], _grammar(), None, 1, SEARCH)
        record = report["records"][0]
        self.assertTrue(record["public_matched"])
        self.assertFalse(record["solved"])
        self.assertEqual(record["failure"]["stage"], "verification")
        self.assertEqual(record["failure"]["inputs"], (3,))
        self.assertEqual(record["failure"]["expected"], 3)
        self.assertEqual(record["failure"]["actual"], -3)
        self.assertIsNone(record["failure"]["error"])
        self.assertEqual(record["verification_examples"], 1)
        self.assertGreater(record["verification_steps"], 0)

    def test_search_failure_distinguishes_candidate_budget_from_exhausted_space(self):
        budget = memory.assess([_task()], _grammar(), None, 1, SEARCH)["records"][0]
        exhausted = memory.assess([_task()], _grammar(("neg",)), None, 2,
                                  SEARCH)["records"][0]
        self.assertFalse(budget["public_matched"])
        self.assertEqual(budget["failure"], {"stage": "search", "kind": "candidate_budget",
                                             "attempted": 1})
        self.assertTrue(exhausted["exhausted"])
        self.assertEqual(exhausted["failure"], {"stage": "search", "kind": "space_exhausted",
                                                "attempted": 1})
        self.assertEqual(exhausted["verification_examples"], 0)

    def test_exact_scope_hit_preserves_report_without_new_actual_candidate_cost(self):
        state = State(11, grammar=_grammar())
        cache = memory.EvaluationMemory()
        first = cache.measure(state, [_task()], None, 1, SEARCH)
        second = cache.measure(state, iter([_task()]), None, 1, dict(SEARCH))
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertEqual(first["candidate_evaluations"], 1)
        self.assertEqual(first["actual_candidate_evaluations"], 1)
        self.assertEqual(second["candidate_evaluations"], 1)
        self.assertEqual(second["actual_candidate_evaluations"], 0)
        self.assertEqual(first["records"], second["records"])
        self.assertEqual(cache.summary(), {"entries": 1, "cache_hits": 1,
                                           "assessment_calls": 2,
                                           "actual_candidate_evaluations": 1})

    def test_primitive_insertion_order_is_a_live_search_dependency(self):
        state = State(11, grammar=_grammar())
        cache = memory.EvaluationMemory()
        first = cache.measure(state, [_task()], None, 1, SEARCH)
        state.grammar = _grammar(("abs", "neg"))
        second = cache.measure(state, [_task()], None, 1, SEARCH)
        self.assertFalse(first["records"][0]["public_matched"])
        self.assertTrue(second["records"][0]["public_matched"])
        self.assertEqual((first["solved"], second["solved"]), (0, 1))
        self.assertFalse(second["cache_hit"])
        self.assertEqual(cache.actual_candidate_evaluations, 2)
        self.assertEqual(len(cache.entries), 2)

    def test_learned_library_insertion_order_is_a_live_search_dependency(self):
        library = _learned_library()
        state = State(11, grammar=Grammar(library=library, primitives={}, constants=()))
        cache = memory.EvaluationMemory()
        first = cache.measure(state, [_task()], None, 1, SEARCH)
        state.grammar = Grammar(library=dict(reversed(list(library.items()))),
                                primitives={}, constants=())
        second = cache.measure(state, [_task()], None, 1, SEARCH)
        self.assertEqual((first["solved"], second["solved"]), (0, 1))
        self.assertFalse(second["cache_hit"])
        self.assertEqual(cache.actual_candidate_evaluations, 2)

    def test_every_task_search_and_grammar_dependency_invalidates_scope(self):
        cases = (
            "public_examples", "hidden_examples", "task_name", "task_type", "task_order",
            "budget", "max_size", "max_expansions", "step_budget", "grammar_weights",
            "context_weights", "primitive_membership", "library_bodies", "constant_order",
            "recognizer_added", "heuristic",
        )
        for change in cases:
            with self.subTest(change=change):
                state = State(11, grammar=_grammar(library=_learned_library()))
                if change == "constant_order":
                    state.grammar = Grammar(library=state.grammar.library,
                                            primitives=state.grammar.primitives,
                                            constants=(Int(0), Int(1)))
                tasks = [_task(), _task("second")]
                searchconfig, budget, heuristic = dict(SEARCH), 1, None
                cache = memory.EvaluationMemory()
                first = cache.measure(state, tasks, heuristic, budget, searchconfig)
                if change == "public_examples":
                    tasks[0] = replace(tasks[0], examples=(((-2,), 2),))
                elif change == "hidden_examples":
                    tasks[0] = replace(tasks[0], hidden=(((7,), -7),))
                elif change == "task_name":
                    tasks[0] = replace(tasks[0], name="new-identity")
                elif change == "task_type":
                    tasks[0] = replace(tasks[0], request_type=Arrow(INT, BOOL))
                elif change == "task_order":
                    tasks.reverse()
                elif change == "budget":
                    budget = 2
                elif change in SEARCH:
                    searchconfig[change] += 1
                elif change == "grammar_weights":
                    state.grammar.weights["abs"] = 2
                elif change == "context_weights":
                    state.grammar.context_weights[("ROOT", 0)] = {"abs": 2}
                elif change == "primitive_membership":
                    state.grammar = _grammar(("neg",), library=state.grammar.library)
                elif change == "library_bodies":
                    library = dict(state.grammar.library)
                    name = next(iter(library))
                    library[name] = library[next(reversed(library))]
                    state.grammar = _grammar(library=library)
                elif change == "constant_order":
                    state.grammar = Grammar(library=state.grammar.library,
                                            primitives=state.grammar.primitives,
                                            constants=(Int(1), Int(0)))
                elif change == "recognizer_added":
                    state.recognition = _recognizer(state.grammar)
                elif change == "heuristic":
                    heuristic = zero_heuristic()
                second = cache.measure(state, tasks, heuristic, budget, searchconfig)
                self.assertGreater(first["actual_candidate_evaluations"], 0)
                self.assertFalse(second["cache_hit"])
                self.assertEqual(len(cache.entries), 2)
                self.assertEqual(cache.cache_hits, 0)
                self.assertEqual(cache.actual_candidate_evaluations,
                                 first["candidate_evaluations"] + second["candidate_evaluations"])

    def test_fitted_recognizer_parameter_change_misses_same_scope_cache(self):
        state = State(11, grammar=_grammar())
        state.recognition = _recognizer(state.grammar)
        cache = memory.EvaluationMemory()
        cache.measure(state, [_task()], None, 1, SEARCH)
        state.recognition.weights[0, 0, 0] += 0.25
        changed = cache.measure(state, [_task()], None, 1, SEARCH)
        self.assertFalse(changed["cache_hit"])
        self.assertEqual(changed["actual_candidate_evaluations"], 1)
        self.assertEqual(cache.actual_candidate_evaluations, 2)

    def test_returned_cache_reports_are_deep_copies(self):
        task = Task("ambiguous", Arrow(INT, INT), (((0,), 0),), (((3,), 3),))
        state = State(11, grammar=_grammar())
        cache = memory.EvaluationMemory()
        first = cache.measure(state, [task], None, 1, SEARCH)
        expected = copy.deepcopy(first["records"])
        first["records"][0]["failure"]["expected"] = 999
        first["records"].append({"name": "forged", "solved": True})
        first["solved"] = 10
        second = cache.measure(state, [task], None, 1, SEARCH)
        self.assertEqual(second["records"], expected)
        self.assertEqual(second["solved"], 0)
        second["records"][0]["failure"]["actual"] = 999
        third = cache.measure(state, [task], None, 1, SEARCH)
        self.assertEqual(third["records"], expected)
        self.assertEqual(cache.actual_candidate_evaluations, 1)

    def test_state_snapshot_json_replay_preserves_order_recognition_and_scope(self):
        library = dict(reversed(list(_learned_library().items())))
        grammar = Grammar(library=library,
                          primitives={name: PRIMITIVE_TYPES[name] for name in ("neg", "abs")},
                          constants=(Int(1), Int(-1)), weights={"neg": 2, "abs": 3},
                          context_weights={("ROOT", 0): {"abs": 4}, ("neg", 0): {"var": 2}})
        state = State(31, grammar=grammar, generation=7, heuristic=zero_heuristic(),
                      solutions={"training-solution": Prim("abs")})
        state.recognition = _recognizer(grammar)
        record = memory.snapshot(state)
        # Ordinary JSON serialization retains order; replay must retain it too.
        restored = memory.restore(json.loads(json.dumps(record)))
        self.assertEqual(memory.snapshot(restored), record)
        self.assertEqual(tuple(restored.grammar.primitives), tuple(grammar.primitives))
        self.assertEqual(tuple(restored.grammar.library), tuple(grammar.library))
        self.assertEqual(restored.grammar.constants, grammar.constants)
        self.assertEqual(restored.recognition.to_dict(), state.recognition.to_dict())
        expected_conditional = state.condition(_task())
        replayed_conditional = restored.condition(_task())
        self.assertEqual(replayed_conditional.context_weights, expected_conditional.context_weights)
        self.assertEqual(memory.scope(restored, [_task()], restored.heuristic, 1, SEARCH),
                         memory.scope(state, [_task()], state.heuristic, 1, SEARCH))
        original = memory.assess([_task()], grammar, state.heuristic, 1, SEARCH,
                                 conditioner=state.condition)
        replayed = memory.assess([_task()], restored.grammar, restored.heuristic, 1, SEARCH,
                                 conditioner=restored.condition)
        for report in (original, replayed):
            report.pop("wall_seconds")
            for item in report["records"]:
                item.pop("wall_seconds")
        self.assertEqual(replayed, original)

    def test_snapshot_and_restored_state_are_mutationally_independent(self):
        state = State(11, grammar=_grammar(weights={"abs": 3},
                                          context_weights={("ROOT", 0): {"abs": 4}}))
        state.recognition = _recognizer(state.grammar)
        saved = memory.snapshot(state)
        original = copy.deepcopy(saved)
        restored = memory.restore(saved)
        restored.grammar.weights["abs"] = 99
        restored.grammar.context_weights[("ROOT", 0)]["abs"] = 99
        restored.recognition.weights[0, 0, 0] += 1
        self.assertEqual(memory.snapshot(state), original)
        self.assertEqual(saved, original)
        saved["grammar"]["weights"]["abs"] = 88
        saved["recognition"]["weights"][0][0][0] = 88
        self.assertEqual(memory.snapshot(state), original)
        self.assertEqual(restored.grammar.weights["abs"], 99)


if __name__ == "__main__":
    unittest.main()
