"""Synthetic validation checks for learned DSL heuristic synthesis and adoption."""
import copy
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from rsi2 import heuristics, search
from rsi2.abstraction import learn_abstractions
from rsi2.corpus import Task
from rsi2.enumeration import Candidate, enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.learning import State, state_summary
from rsi2.recognition import Recognition
from rsi2.search import HEURISTIC_TYPE, solve
from rsi2.terms import Int, Lam, Literal, Prim, Ref, Var, apply, subterms, term_from_dict
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES, TVar, infer, unify


CONFIG = {"B_eval": 64,
          "search": {"max_size": 12, "max_expansions": 20000,
                     "step_budget": 2000}}


def _zero():
    # Generation zero's constant-zero incumbent is part of the frozen contract.
    return Lam(ListOf(INT), Lam(ListOf(INT), Lam(INT, Lam(INT, Int(0)))))


def _state():
    # The library fixture is learned from programs produced by the same typed
    # enumerator, rather than introducing a separately authored library body.
    fragment = {name: PRIMITIVE_TYPES[name] for name in ("neg", "abs")}
    uniform = Grammar(primitives=fragment, constants=(Int(-1), Int(0), Int(1)))
    enumerated = next(enumerate_programs(HEURISTIC_TYPE, uniform,
                                        **{key: value for key, value in CONFIG["search"].items()
                                           if key != "step_budget"})).term
    _, library, records = learn_abstractions(
        {f"synthetic_solution_{i}": enumerated for i in range(6)}, {}, 1)
    if not records:
        raise AssertionError("the repeated enumerated terms did not compress")
    grammar = Grammar(library=library, primitives=fragment,
                      constants=(Int(-1), Int(0), Int(1)))
    state = State(19, grammar=grammar, heuristic=_zero(), generation=1,
                  library_history=records)
    return state


def _validation():
    names = ["zeta", "beta", "epsilon", "alpha", "gamma", "delta"]
    return [Task(name, Arrow(INT, INT),
                 tuple(((i,), abs(i)) for i in range(-5, 5)),
                 (((-12,), 12), ((19,), 19))) for name in names]


def _snapshot(state):
    return copy.deepcopy({
        "summary": state_summary(state), "heuristic": state.heuristic,
        "solutions": state.solutions, "library": state.grammar.library,
        "primitives": state.grammar.primitives, "constants": state.grammar.constants,
        "recognition": state.recognition.to_dict() if state.recognition is not None else None,
    })


def _report(tasks, budget, solved, count_per_task):
    tasks = list(tasks)
    records = [{"name": task.name, "solved": index < solved,
                "candidates": count_per_task,
                "candidates_to_solution": count_per_task if index < solved else None,
                "wall_seconds": 0.0, "evaluation_steps": count_per_task,
                "heuristic_calls": 0, "exhausted": False}
               for index, task in enumerate(tasks)]
    return {"tasks": len(tasks), "solved": solved,
            "solved_fraction": solved / len(tasks) if tasks else 0.0,
            "mean_candidates_to_solution": count_per_task if solved else None,
            "candidate_evaluations": len(tasks) * count_per_task,
            "budget": budget, "wall_seconds": 0.0, "records": records}


class HeuristicLearningTests(unittest.TestCase):
    def test_current_library_and_seeded_typed_mutations_share_six_slots(self):
        state = _state()
        before = _snapshot(state)
        calls = []
        original_enumerate = heuristics.enumerate_programs

        def observe_enumerate(requested, grammar=None, **kwargs):
            calls.append((requested, grammar))
            yield from original_enumerate(requested, grammar, **kwargs)

        with patch.object(heuristics, "enumerate_programs", side_effect=observe_enumerate):
            first = heuristics.candidate_attempts(state, CONFIG)
        second = heuristics.candidate_attempts(state, CONFIG)
        primitive = heuristics.candidate_attempts(state, CONFIG, primitive_only=True)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual(len(primitive), 6)
        self.assertEqual(sum(record["origin"] == "enumeration" for record in first), 4)
        self.assertEqual(sum(record["origin"] == "mutation" for record in first), 2)
        self.assertEqual(calls[0][0], HEURISTIC_TYPE)
        self.assertEqual(calls[0][1].library, state.grammar.library)
        self.assertTrue(any(node.tag == "ref" for record in first if record["term"] is not None
                            for _, node in subterms(record["term"])))
        self.assertFalse(any(node.tag == "ref" for record in primitive if record["term"] is not None
                             for _, node in subterms(record["term"])))
        for records, library in ((first, state.grammar.library), (primitive, {})):
            self.assertTrue(all(record["term"] is not None for record in records))
            for record in records:
                unify(infer(record["term"], library=library), HEURISTIC_TYPE)
                result = evaluate(record["term"], ([], [1, -2], 3, 2),
                                  library=library, step_budget=2000)
                self.assertTrue(result.ok, result.error)
                self.assertIs(type(result.value), int)
        self.assertEqual(_snapshot(state), before)

    def _decision_run(self, strictly_better):
        state, validation = _state(), _validation()
        attempts = heuristics.candidate_attempts(state, CONFIG)
        leaders = []
        for record in attempts:
            term = record["term"]
            if term is not None and term != state.heuristic and term not in leaders:
                leaders.append(term)
            if len(leaders) == 2:
                break
        self.assertEqual(len(leaders), 2)
        calls = []

        def assessment(tasks, grammar, heuristic, budget, searchconfig=None, conditioner=None):
            tasks = list(tasks)
            self.assertIs(grammar, state.grammar)
            self.assertIs(conditioner.__self__, state)
            self.assertEqual(searchconfig, CONFIG["search"])
            if heuristic == state.heuristic:
                solved, count = 2, budget
            elif budget == 16:
                solved = 4 if heuristic == leaders[0] else 3 if heuristic == leaders[1] else 0
                count = budget
            elif heuristic == leaders[0]:
                # A tie with far fewer candidate evaluations must still lose.
                solved, count = (3 if strictly_better else 2), 2
            else:
                solved, count = 1, budget
            report = _report(tasks, budget, solved, count)
            calls.append((tasks, heuristic, budget, report))
            return report

        before_cost = state.logical_evaluations
        incumbent = state.heuristic
        with patch.object(heuristics, "assess", side_effect=assessment):
            report = heuristics.improve_heuristic(state, validation, CONFIG)
        return state, validation, report, calls, leaders, incumbent, before_cost

    def test_screening_improvement_and_faster_ties_cannot_replace_incumbent(self):
        state, validation, report, calls, leaders, incumbent, before_cost = self._decision_run(False)
        self.assertFalse(report["adopted"])
        self.assertEqual(state.heuristic, incumbent)
        screen_calls = [call for call in calls if call[2] == 16]
        self.assertTrue(screen_calls)
        expected = sorted(task.name for task in validation)[:4]
        self.assertTrue(all([task.name for task in call[0]] == expected for call in screen_calls))
        full_calls = [call for call in calls if call[2] == 64]
        self.assertEqual(len(full_calls), 3)  # Incumbent plus the two screened leaders.
        self.assertTrue(all({task.name for task in call[0]} == {task.name for task in validation}
                            for call in full_calls))
        self.assertEqual({call[1] for call in full_calls[1:]}, set(leaders))
        self.assertEqual(len(report["candidates"]), 6)
        self.assertTrue(all(not candidate["adopted"] for candidate in report["candidates"]))
        self.assertEqual(report["synthesis_candidate_evaluations"], 6)
        inner = sum(call[3]["candidate_evaluations"] for call in calls)
        self.assertEqual(report["inner_candidate_evaluations"], inner)
        self.assertEqual(report["candidate_evaluations"], inner + 6)
        self.assertEqual(state.logical_evaluations - before_cost, inner + 6)
        self.assertTrue(any(call[3]["solved"] == 0 for call in screen_calls))

    def test_only_full_validation_strict_improvement_is_adopted(self):
        state, validation, report, calls, leaders, _, _ = self._decision_run(True)
        self.assertTrue(report["adopted"])
        self.assertEqual(state.heuristic, leaders[0])
        self.assertEqual(sum(candidate["adopted"] for candidate in report["candidates"]), 1)
        adopted = next(candidate for candidate in report["candidates"] if candidate["adopted"])
        self.assertEqual(term_from_dict(adopted["term"]), state.heuristic)
        self.assertEqual(adopted["full"]["tasks"], len(validation))
        self.assertEqual(adopted["full"]["budget"], 64)
        self.assertGreater(adopted["full"]["solved_fraction"],
                           report["incumbent_full"]["solved_fraction"])
        self.assertTrue(state.heuristic_history)

    def test_primitive_counterfactual_preserves_task_grammar_recognition_and_state(self):
        state, validation = _state(), _validation()
        model = Recognition(19)
        model.fit([(validation[0], Prim("abs")), (validation[1], Prim("abs"))], state.grammar)
        state.recognition = model
        before = _snapshot(state)
        calls = []

        def assessment(tasks, grammar, heuristic, budget, searchconfig=None, conditioner=None):
            tasks = list(tasks)
            self.assertIs(grammar, state.grammar)
            self.assertIs(conditioner.__self__, state)
            conditional = conditioner(tasks[0], grammar)
            self.assertEqual(conditional.library, before["library"])
            self.assertEqual(conditional.context_weights,
                             model.grammar_for(tasks[0], state.grammar).context_weights)
            calls.append((grammar, conditioner, heuristic, budget))
            return _report(tasks, budget, 1, budget)

        with patch.object(heuristics, "assess", side_effect=assessment):
            full = heuristics.improve_heuristic(state, validation, CONFIG, update_state=False)
            primitive = heuristics.improve_heuristic(
                state, validation, CONFIG, primitive_only=True, update_state=False)
        self.assertTrue(calls)
        self.assertEqual(full["synthesis_candidate_evaluations"], 6)
        self.assertEqual(primitive["synthesis_candidate_evaluations"], 6)
        self.assertEqual(len(full["candidates"]), len(primitive["candidates"]))
        self.assertFalse(any(node.tag == "ref" for candidate in primitive["candidates"]
                             if candidate["term"] is not None
                             for _, node in subterms(term_from_dict(candidate["term"]))))
        self.assertIs(state.recognition, model)
        self.assertEqual(_snapshot(state), before)

    def test_registered_config_screens_and_charges_every_valid_duplicate_slot(self):
        config = json.loads((Path(__file__).parents[1] / "experiment_config.json").read_text())
        self.assertEqual(config["heuristics"], heuristics.FIXED_PARAMETERS)
        state, validation = _state(), _validation()
        attempts = heuristics.candidate_attempts(state, config)
        distinct = [attempts[0]["term"], attempts[1]["term"]]
        terms = [state.heuristic, state.heuristic, distinct[0], distinct[0],
                 distinct[1], distinct[1]]
        slots = [{**record, "term": term} for record, term in zip(attempts, terms)]
        calls = []

        def assessment(tasks, grammar, heuristic, budget, searchconfig=None, conditioner=None):
            self.assertIs(grammar, state.grammar)
            self.assertIs(conditioner.__self__, state)
            self.assertEqual(searchconfig, config["search"])
            tasks = list(tasks)
            report = _report(tasks, budget, 1, budget)
            calls.append((tasks, heuristic, budget, report))
            return report

        before_cost = state.logical_evaluations
        with patch.object(heuristics, "candidate_attempts", return_value=slots) as proposals:
            with patch.object(heuristics, "assess", side_effect=assessment):
                report = heuristics.improve_heuristic(state, validation, config)
        proposals.assert_called_once_with(state, config, primitive_only=False)
        screens = [call for call in calls if call[2] == 16]
        self.assertEqual(len(screens), 6)
        self.assertEqual([call[1] for call in screens], terms)
        self.assertEqual(report["screen_budget"], 16)
        expected_names = sorted(task.name for task in validation)[:4]
        self.assertEqual(report["screen_task_names"], expected_names)
        for candidate, call in zip(report["candidates"], screens):
            self.assertIs(candidate["screen"], call[3])
            self.assertEqual([task.name for task in call[0]], expected_names)
            self.assertEqual(candidate["screen"]["candidate_evaluations"], 4 * 16)
        self.assertEqual([candidate["duplicate"] for candidate in report["candidates"]],
                         [True, True, False, True, False, True])
        self.assertEqual(len({id(call[3]) for call in screens}), 6)
        self.assertEqual(len([call for call in calls if call[2] == 64]), 3)
        self.assertEqual(report["synthesis_candidate_evaluations"], 6)
        inner = 6 * 4 * 16 + 3 * len(validation) * 64
        self.assertEqual(report["inner_candidate_evaluations"], inner)
        self.assertEqual(report["candidate_evaluations"], inner + 6)
        self.assertEqual(state.logical_evaluations - before_cost, inner + 6)
        self.assertFalse(report["adopted"])

    def test_semantic_zero_preserves_base_prefix_and_memoizes_actual_scores(self):
        # This evaluates to zero, but does not match the constant-zero shortcut.
        computed_zero = Lam(ListOf(INT), Lam(ListOf(INT), Lam(INT, Lam(
            INT, apply(Prim("sub"), Var(0), Var(0))))))
        grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("neg", "abs")},
                          constants=(Int(-1), Int(0), Int(1)))
        examples = [((2,), 999999)]
        baseline_attempts, guided_attempts, score_inputs = [], [], []
        observed_outputs, guide_states, successful_keys = {}, [], []
        original_enumerate = search.enumerate_programs

        def base_evaluate(term, inputs=(), **kwargs):
            baseline_attempts.append(term)
            return evaluate(term, inputs, **kwargs)

        def guided_evaluate(term, inputs=(), **kwargs):
            result = evaluate(term, inputs, **kwargs)
            if term == computed_zero:
                score_inputs.append(inputs)
                self.assertTrue(result.ok, result.error)
                self.assertEqual(result.value, 0)
            else:
                guided_attempts.append(term)
                observed_outputs[term] = [result.value] if result.ok else []
            return result

        def observed_enumerate(*args, **kwargs):
            guide = kwargs["partial_heuristic"]

            def observed_guide(state):
                guide_states.append(state)
                score = guide(state)
                outputs = observed_outputs[state.term] if state.complete else []
                successful_keys.append((tuple(outputs), state.min_size, state.depth))
                self.assertEqual(score, 0)
                return score

            kwargs["partial_heuristic"] = observed_guide
            yield from original_enumerate(*args, **kwargs)

        with patch.object(search, "evaluate", side_effect=base_evaluate):
            baseline = solve(examples, Arrow(INT, INT), 16, grammar,
                             max_size=8, max_expansions=5000)
        with patch.object(search, "evaluate", side_effect=guided_evaluate):
            with patch.object(search, "enumerate_programs", side_effect=observed_enumerate):
                guided = solve(examples, Arrow(INT, INT), 16, grammar, computed_zero,
                               max_size=8, max_expansions=5000)
        self.assertEqual(guided_attempts, baseline_attempts)
        self.assertEqual(guided.candidates, baseline.candidates)
        self.assertEqual(guided.candidates, 16)
        self.assertEqual(guided.evaluation_steps, baseline.evaluation_steps)
        self.assertIsNone(guided.term)
        self.assertEqual(guided.heuristic_calls, len(guide_states))
        self.assertEqual(guided.heuristic_evaluations, len(score_inputs))
        self.assertLess(guided.heuristic_evaluations, guided.heuristic_calls)
        partial_keys = [((), state.min_size, state.depth)
                        for state in guide_states if not state.complete]
        self.assertGreater(len(partial_keys), len(set(partial_keys)))
        score_keys = [(tuple(inputs[0]), inputs[2], inputs[3]) for inputs in score_inputs]
        self.assertEqual(len(score_keys), len(set(score_keys)))
        self.assertEqual(set(score_keys), set(successful_keys))
        self.assertEqual(score_keys.count(((), 1, 1)), 1)
        self.assertTrue(all(inputs[1] == [999999] for inputs in score_inputs))
        self.assertTrue(any(inputs[0] for inputs in score_inputs))

    def test_primitive_mutation_inlines_retained_library_under_original_scope(self):
        state = _state()
        name = next(iter(state.grammar.library))
        # nil supplies a closed replacement for the outer list variable. The
        # library function remains in place and must be expanded after mutation.
        grammar = Grammar(library=state.grammar.library,
                          primitives={**state.grammar.primitives, "nil": PRIMITIVE_TYPES["nil"]},
                          constants=state.grammar.constants)
        primitive = heuristics.synthesis_grammar(grammar, primitive_only=True)
        before = copy.deepcopy(grammar.library)
        for reference in (Ref(name), Prim(name)):
            with self.subTest(reference=reference.tag):
                incumbent = Lam(ListOf(INT), apply(reference, Var(0)))
                candidate, path, rejection = heuristics.mutate(
                    incumbent, primitive, random.Random(0), CONFIG["search"],
                    template_library=grammar.library, primitive_only=True)
                self.assertEqual(path, (0, 1))
                self.assertIsNone(rejection)
                self.assertTrue(any(node.tag == "ref" or
                                    (node.tag == "prim" and node.value == name)
                                    for _, node in subterms(incumbent)))
                self.assertFalse(any(node.tag == "ref" or
                                     (node.tag == "prim" and node.value not in PRIMITIVE_TYPES)
                                     for _, node in subterms(candidate)))
                unify(infer(candidate), HEURISTIC_TYPE)
                result = evaluate(candidate, ([7], [-2], 3, 4), step_budget=2000)
                self.assertTrue(result.ok, result.error)
                self.assertEqual(result.value, -4)
        self.assertEqual(grammar.library, before)

    def test_inlined_polymorphic_references_and_prim_aliases_get_fresh_annotations(self):
        requested = Arrow(ListOf(TVar("a")), ListOf(TVar("a")))
        grammar = Grammar(primitives={"tail": PRIMITIVE_TYPES["tail"]}, constants=())
        source = next(candidate.term for candidate in enumerate_programs(
            requested, grammar, max_size=8, max_expansions=1000)
            if candidate.term.tag == "lam" and candidate.term.size >= 6)
        _, library, records = learn_abstractions(
            {f"polymorphic_solution_{i}": source for i in range(6)}, {}, 2)
        self.assertTrue(records)
        name = records[0]["name"]
        before = copy.deepcopy(library)
        # One learned scheme is independently instantiated at list[int] and
        # list[bool]. The outer variable must also retain its binder.
        term = Lam(INT, apply(
            Prim("add"),
            apply(Prim("length"), apply(Ref(name), Literal([1, 2, 3]))),
            apply(Prim("add"), Var(0),
                  apply(Prim("length"), apply(Prim(name), Literal([True, False, True]))))))
        unify(infer(term, library=library), Arrow(INT, INT))
        inlined = heuristics.inline_library(term, library)
        unify(infer(inlined), Arrow(INT, INT))
        self.assertFalse(any(node.tag == "ref" or
                             (node.tag == "prim" and node.value not in PRIMITIVE_TYPES)
                             for _, node in subterms(inlined)))
        annotations = [node.value.args[0].name for _, node in subterms(inlined)
                       if node.tag == "lam" and node.value.tag == "list"]
        self.assertEqual(len(annotations), 2)
        self.assertEqual(len(set(annotations)), 2)
        original = evaluate(term, (17,), library=library, step_budget=2000)
        expanded = evaluate(inlined, (17,), step_budget=2000)
        self.assertTrue(original.ok, original.error)
        self.assertTrue(expanded.ok, expanded.error)
        self.assertEqual(original.value, 19)
        self.assertEqual(expanded.value, original.value)
        self.assertEqual(library, before)


if __name__ == "__main__":
    unittest.main()
