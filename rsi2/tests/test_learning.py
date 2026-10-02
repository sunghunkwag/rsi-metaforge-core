"""Synthetic-only integration checks for the wake–sleep training coordinator."""
import random
import unittest
from unittest.mock import patch

from rsi2 import learning
from rsi2.corpus import Task
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.learning import State, dream_pairs, state_summary, wake_sleep
from rsi2.recognition import Recognition
from rsi2.terms import Int, Lam, Prim, Var, apply, subterms
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES


CONFIG = {"B_wake": 64, "dreams": 16,
          "search": {"max_size": 12, "max_expansions": 20000,
                     "step_budget": 2000}}
LIST_REQUEST = Arrow(ListOf(INT), INT)
SUM = Lam(ListOf(INT), apply(Prim("fold"), Prim("add"), Int(0), Var(0)))


class _ForbiddenHidden:
    def __iter__(self):
        raise AssertionError("dream generation inspected hidden examples")

    def __len__(self):
        raise AssertionError("dream generation inspected hidden examples")

    def __bool__(self):
        raise AssertionError("dream generation inspected hidden examples")


def _synthetic_training():
    tasks = []
    for offset in range(6):
        values = [[], [0], [1, -1], [offset + 1, 2, -5], [3, 4],
                  [1, 2, 3], [-2, -5, 1], [9, 8, -4],
                  [offset, 0, 5], [10, -20, 3, 4]]
        examples = tuple(((value,), sum(value)) for value in values)
        hidden = ((([100 + offset, -30, 2],), 72 + offset),)
        tasks.append(Task(f"sum_{offset}", LIST_REQUEST, examples, hidden))
    examples = tuple((([i] * i,), i) for i in range(10))
    tasks.append(Task("length", LIST_REQUEST, examples, ((([15] * 15,), 15),)))
    return tasks


def _seeded_state(train):
    return State(11, solutions={task.name: SUM for task in train[:-1]})


def _without_times(report):
    return {key: value for key, value in report.items()
            if key not in ("wall_seconds", "cpu_seconds")}


class WakeSleepTests(unittest.TestCase):
    def test_wake_retries_solved_and_unsolved_tasks_with_real_budget(self):
        grammar = Grammar(
            primitives={name: PRIMITIVE_TYPES[name] for name in ("neg", "abs")},
            constants=(Int(-1), Int(0), Int(1)))
        solved = Task("negate", Arrow(INT, INT),
                      tuple(((i,), -i) for i in range(1, 11)), (((19,), -19),))
        unsolved = Task("unsolved", Arrow(INT, INT),
                        tuple(((i,), i * i + 10001) for i in range(1, 11)),
                        (((19,), 10362),))
        train, state = [solved, unsolved], State(5, grammar=grammar)
        calls = []
        original_solve = learning.solve

        def observe_solve(examples, requested, budget, current_grammar, **kwargs):
            result = original_solve(examples, requested, budget, current_grammar, **kwargs)
            calls.append((examples, requested, budget, result))
            return result

        with patch.object(learning, "solve", side_effect=observe_solve), \
                patch.object(learning, "verify", wraps=learning.verify) as verify:
            reports = [wake_sleep(state, train, CONFIG, library_learning=False,
                                  recognition_learning=False) for _ in range(2)]

        self.assertEqual(len(calls), 4)
        for index, (examples, requested, budget, result) in enumerate(calls):
            task = train[index % len(train)]
            self.assertIs(examples, task.examples)
            self.assertEqual(requested, task.request_type)
            self.assertEqual(budget, 64)
            self.assertGreater(result.candidates, 0)
            self.assertLessEqual(result.candidates, budget)
            self.assertIs(verify.call_args_list[index].args[1], task.hidden)
        for report in reports:
            self.assertEqual([record["name"] for record in report["wake"]],
                             [task.name for task in train])
            success, failure = report["wake"]
            self.assertTrue(success["hidden_verified"])
            self.assertTrue(success["has_solution"])
            self.assertFalse(failure["hidden_verified"])
            self.assertFalse(failure["has_solution"])
            self.assertEqual(failure["candidates"], 64)
            self.assertEqual(report["wake_candidate_evaluations"],
                             sum(record["candidates"] for record in report["wake"]))
            self.assertEqual(report["dream_candidate_evaluations"], 0)
        self.assertEqual(state.generation, 2)
        self.assertEqual(set(state.solutions), {"negate"})
        self.assertEqual(state.logical_evaluations,
                         sum(result.candidates for *_, result in calls))

    def test_dreams_use_current_library_and_public_inputs_counting_failures(self):
        values = [[], *([i, -i, i + 1] for i in range(1, 10))]
        examples = tuple(((value,), -999999) for value in values)
        # Deliberately incorrect public labels and inaccessible hidden examples
        # make any reuse of reference labels or hidden inputs observable.
        template = Task("public_template", LIST_REQUEST, examples, _ForbiddenHidden())
        grammar = Grammar(
            library={"current_sum": SUM},
            primitives={"head": PRIMITIVE_TYPES["head"]}, constants=(Int(0),),
            weights={"head": 12, "current_sum": 12, "lambda": 1})
        sampled, failures = [], []
        original_sample, original_evaluate = learning.sample_program, learning.evaluate

        def observe_sample(requested, current_grammar, rng, **kwargs):
            self.assertIs(current_grammar, grammar)
            self.assertEqual(requested, LIST_REQUEST)
            term = original_sample(requested, current_grammar, rng, **kwargs)
            sampled.append(term)
            return term

        def observe_evaluate(term, inputs, **kwargs):
            self.assertIs(kwargs["library"], grammar.library)
            self.assertIn(inputs, [inputs for inputs, _ in examples])
            result = original_evaluate(term, inputs, **kwargs)
            if not result.ok:
                failures.append(result.error)
            return result

        with patch.object(learning, "sample_program", side_effect=observe_sample), \
                patch.object(learning, "evaluate", side_effect=observe_evaluate):
            pairs, attempts = dream_pairs([template], grammar, random.Random(3),
                                         count=16, attempts=256, max_size=12,
                                         step_budget=2000)
        self.assertEqual(len(pairs), 16)
        self.assertEqual(attempts, sum(term is not None for term in sampled))
        self.assertGreater(attempts, len(pairs))
        self.assertTrue(failures)
        self.assertEqual(attempts - len(pairs), len(failures))
        self.assertTrue(any(node.tag == "ref" and node.value == "current_sum"
                            for _, term in pairs for _, node in subterms(term)))
        for dreamed, term in pairs:
            self.assertEqual(dreamed.request_type, LIST_REQUEST)
            self.assertEqual(dreamed.hidden, ())
            self.assertEqual(tuple(inputs for inputs, _ in dreamed.examples),
                             tuple(inputs for inputs, _ in examples))
            grammar.decisions(term, LIST_REQUEST)
            for inputs, label in dreamed.examples:
                result = evaluate(term, inputs, library=grammar.library, step_budget=2000)
                self.assertTrue(result.ok)
                self.assertEqual(label, result.value)
                self.assertNotEqual(label, -999999)
        self.assertEqual((pairs, attempts),
                         dream_pairs([template], grammar, random.Random(3), count=16,
                                     attempts=256, max_size=12, step_budget=2000))

    def test_real_abstraction_grammar_and_recognition_share_one_generation(self):
        train = _synthetic_training()
        state = _seeded_state(train)
        fitted = []
        generated = []
        original_fit, original_dream = Recognition.fit, learning.dream_pairs

        def observe_fit(model, pairs, grammar):
            pairs = list(pairs)
            fitted.append((pairs, grammar))
            return original_fit(model, pairs, grammar)

        def observe_dream(*args, **kwargs):
            result = original_dream(*args, **kwargs)
            generated.append(result)
            return result

        with patch.object(Recognition, "fit", observe_fit), \
                patch.object(learning, "dream_pairs", side_effect=observe_dream):
            report = wake_sleep(state, train, CONFIG)

        self.assertEqual(state.generation, 1)
        self.assertEqual(report["training_solutions"], len(train))
        self.assertTrue(report["adopted_library"])
        self.assertEqual(state.library_history, report["adopted_library"])
        self.assertEqual(report["library_entries"], len(state.grammar.library))
        for entry in report["adopted_library"]:
            self.assertLess(entry["cost_after"], entry["cost_before"])
            self.assertEqual(entry["generation"], 1)
            self.assertTrue(set(entry["source_tasks"]).issubset({task.name for task in train}))
        self.assertTrue(any(node.tag == "ref" for term in state.solutions.values()
                            for _, node in subterms(term)))
        for task in train:
            for inputs, expected in task.examples + task.hidden:
                result = evaluate(state.solutions[task.name], inputs,
                                  library=state.grammar.library, step_budget=2000)
                self.assertTrue(result.ok)
                self.assertEqual(result.value, expected)
        self.assertEqual(report["grammar"]["solutions"], len(state.solutions))
        learned_names = set(state.grammar.library)
        self.assertTrue(any(key.rsplit("/", 1)[0] in learned_names
                            for key in report["grammar"]["production_counts"]))
        self.assertEqual(len(fitted), 1)
        pairs, fitted_grammar = fitted[0]
        self.assertIs(fitted_grammar, state.grammar)
        real_pairs = [(task, term) for task, term in pairs if task.name in state.solutions]
        dreamed_pairs = [(task, term) for task, term in pairs if task.name.startswith("dream_")]
        self.assertEqual({task.name for task, _ in real_pairs}, set(state.solutions))
        self.assertTrue(all(any(task is original for original in train)
                            for task, _ in real_pairs))
        self.assertEqual(dreamed_pairs, generated[0][0])
        self.assertEqual(len(dreamed_pairs), 16)
        self.assertEqual(report["recognition"]["examples"], len(real_pairs) + len(dreamed_pairs))
        self.assertLess(report["recognition"]["objective_after"],
                        report["recognition"]["objective_before"])
        self.assertIsInstance(state.recognition, Recognition)
        conditioned = state.condition(train[0])
        self.assertIs(conditioned.library, state.grammar.library)
        self.assertNotEqual(conditioned.context_weights, state.grammar.context_weights)
        self.assertEqual(report["wake_candidate_evaluations"],
                         sum(record["candidates"] for record in report["wake"]))
        self.assertEqual(report["dream_candidate_evaluations"], generated[0][1])
        self.assertGreaterEqual(report["dream_candidate_evaluations"], report["dreams"])
        self.assertEqual(state.logical_evaluations, report["wake_candidate_evaluations"] +
                         report["dream_candidate_evaluations"])

    def test_seed_and_config_reproduce_all_logical_generation_outputs(self):
        train = _synthetic_training()
        left, right = _seeded_state(train), _seeded_state(train)
        first = wake_sleep(left, train, CONFIG)
        second = wake_sleep(right, train, CONFIG)
        self.assertEqual(_without_times(first), _without_times(second))
        self.assertEqual(state_summary(left), state_summary(right))
        self.assertEqual(left.recognition.to_dict(), right.recognition.to_dict())
        for task in train:
            a, b = left.condition(task), right.condition(task)
            self.assertEqual(a.weights, b.weights)
            self.assertEqual(a.context_weights, b.context_weights)


if __name__ == "__main__":
    unittest.main()
