"""Synthetic checks for learned, public-example-conditioned grammar weights."""

import json
import math
from types import SimpleNamespace
import unittest

import numpy as np

from rsi2.grammar import Grammar, ROOT_CONTEXT
from rsi2.recognition import Recognition, task_features
from rsi2.terms import Bool, Int, Lam, Var
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES


def constant_task(value, name="synthetic"):
    return SimpleNamespace(
        name=name,
        request_type=INT,
        examples=tuple(((), value) for _ in range(4)),
    )


def constant_training():
    grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
    tasks = [constant_task(value, f"synthetic_{value}_{index}")
             for value in (0, 1) for index in range(6)]
    return grammar, [(task, Int(task.examples[0][1])) for task in tasks]


class PublicTask:
    """Accessing held-out examples fails even if the caller catches the error."""

    def __init__(self, value):
        self.name = "synthetic_public_only"
        self.request_type = INT
        self.examples = (((), value),)
        self.hidden_reads = 0

    @property
    def hidden(self):
        self.hidden_reads += 1
        raise AssertionError("recognition must use only public task examples")


class RecognitionTests(unittest.TestCase):
    def test_feature_vector_is_fixed_and_finite_for_supported_examples(self):
        cases = (
            (),
            (((), 0),),
            (((-8, 13), 5), ((0, -2), -2)),
            (((True,), False), ((False,), True)),
            ((([],), []),),
            ((([1, -2, 3],), [2, -1, 4]), (([0],), [1])),
            ((([True, False],), [False, True]),),
            (((10**1000, -(10**1000)), 10**999),),
        )
        shape = None
        for examples in cases:
            with self.subTest(examples=examples):
                # No name, requested type, split, or hidden data is provided.
                features = task_features(SimpleNamespace(examples=examples))
                self.assertIsInstance(features, np.ndarray)
                self.assertEqual(features.ndim, 1)
                self.assertGreater(features.size, 0)
                self.assertTrue(np.isfinite(features).all())
                if shape is None:
                    shape = features.shape
                self.assertEqual(features.shape, shape)
                np.testing.assert_array_equal(
                    features, task_features(SimpleNamespace(examples=examples)),
                )

    def test_features_do_not_depend_on_names_types_or_hidden_metadata(self):
        first = constant_task(1, "different_first_name")
        second = constant_task(1, "different_second_name")
        first.hidden = (((99,), -100),)
        second.hidden = (((-99,), 100),)
        first.split = "arbitrary_metadata_a"
        second.split = "arbitrary_metadata_b"
        second.request_type = Arrow(ListOf(BOOL), BOOL)
        np.testing.assert_array_equal(task_features(first), task_features(second))

    def test_feature_training_and_prediction_never_access_hidden_examples(self):
        tasks = (PublicTask(0), PublicTask(1))
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        model = Recognition(seed=3)
        for task in tasks:
            self.assertTrue(np.isfinite(task_features(task)).all())
        model.fit([(task, Int(task.examples[0][1])) for task in tasks], grammar)
        for task in tasks:
            predicted = model.grammar_for(task, grammar)
            self.assertTrue(math.isfinite(predicted.log_probability(Int(0), INT)))
            self.assertEqual(task.hidden_reads, 0)

    def test_training_reduces_objective_and_labeled_program_surprisal(self):
        grammar, pairs = constant_training()
        model = Recognition(seed=11)
        metrics = model.fit(pairs, grammar)
        self.assertEqual(metrics["examples"], len(pairs))
        self.assertEqual(metrics["decisions"], len(pairs))
        self.assertTrue(math.isfinite(metrics["objective_before"]))
        self.assertTrue(math.isfinite(metrics["objective_after"]))
        self.assertLess(metrics["objective_after"], metrics["objective_before"])
        before = -sum(grammar.log_probability(term, task.request_type)
                      for task, term in pairs) / len(pairs)
        after = -sum(model.grammar_for(task, grammar).log_probability(
            term, task.request_type) for task, term in pairs) / len(pairs)
        self.assertLess(after, before)

    def test_same_seed_and_training_pairs_reproduce_parameters_and_predictions(self):
        grammar, pairs = constant_training()
        first, second = Recognition(seed=17), Recognition(seed=17)
        first_metrics, second_metrics = first.fit(pairs, grammar), second.fit(pairs, grammar)
        self.assertEqual(first_metrics, second_metrics)
        self.assertEqual(first.to_dict(), second.to_dict())
        for task, _ in pairs:
            left, right = first.grammar_for(task, grammar), second.grammar_for(task, grammar)
            for term in grammar.constants:
                self.assertEqual(left.log_probability(term, INT),
                                 right.log_probability(term, INT))

    def test_task_conditioning_favors_the_corresponding_program_label(self):
        grammar, pairs = constant_training()
        model = Recognition(seed=19)
        model.fit(pairs, grammar)
        for label in (0, 1):
            with self.subTest(label=label):
                # New task names prevent an identifier lookup from satisfying this check.
                predicted = model.grammar_for(constant_task(label, "new_public_task"), grammar)
                self.assertGreater(predicted.log_probability(Int(label), INT),
                                   predicted.log_probability(Int(1 - label), INT))
        zero = model.grammar_for(constant_task(0), grammar)
        one = model.grammar_for(constant_task(1), grammar)
        self.assertNotEqual(zero.log_probability(Int(0), INT),
                            one.log_probability(Int(0), INT))

    def test_json_round_trip_preserves_conditioned_grammar_scores(self):
        grammar, pairs = constant_training()
        model = Recognition(seed=23)
        model.fit(pairs, grammar)
        saved = json.loads(json.dumps(model.to_dict(), allow_nan=False))
        restored = Recognition.from_dict(saved)
        probes = [constant_task(0), constant_task(1), SimpleNamespace(
            name="new_mixed_examples", request_type=INT,
            examples=(((), 0), ((), 1)),
        )]
        for task in probes:
            original = model.grammar_for(task, grammar)
            loaded = restored.grammar_for(task, grammar)
            for term in grammar.constants:
                self.assertEqual(original.log_probability(term, INT),
                                 loaded.log_probability(term, INT))

    def test_prediction_preserves_language_and_base_grammar_and_normalizes_choices(self):
        library = {"identity": Lam(INT, Var(0))}
        grammar = Grammar(
            library=library,
            primitives={"add": PRIMITIVE_TYPES["add"]},
            constants=(Int(0), Int(1), Bool(False)),
            weights={"add": 2.0, "identity": 3.0, "var": 1.5},
            context_weights={ROOT_CONTEXT: {"int:0": 1.2},
                             ("add", 0): {"int:1": 2.5}},
        )
        original_weights = dict(grammar.weights)
        original_contexts = {key: dict(value)
                             for key, value in grammar.context_weights.items()}
        model = Recognition(seed=29)
        model.fit([(constant_task(0), Int(0)), (constant_task(1), Int(1))], grammar)
        predicted = model.grammar_for(constant_task(1), grammar)
        self.assertIsNot(predicted, grammar)
        self.assertEqual(predicted.primitives, grammar.primitives)
        self.assertEqual(predicted.constants, grammar.constants)
        self.assertEqual(predicted.library, library)
        self.assertEqual(grammar.weights, original_weights)
        self.assertEqual(grammar.context_weights, original_contexts)
        for request_type, env, context in (
            (INT, (), ROOT_CONTEXT),
            (INT, (INT,), ("add", 0)),
            (Arrow(INT, INT), (), ROOT_CONTEXT),
            (BOOL, (), ROOT_CONTEXT),
        ):
            with self.subTest(request_type=request_type, context=context):
                choices = predicted.productions(request_type, env, context=context)
                baseline = grammar.productions(request_type, env, context=context)
                self.assertEqual([(p.name, p.arity) for p in choices],
                                 [(p.name, p.arity) for p in baseline])
                self.assertTrue(all(math.isfinite(p.log_probability) for p in choices))
                self.assertAlmostEqual(sum(math.exp(p.log_probability) for p in choices),
                                       1.0, places=12)


if __name__ == "__main__":
    unittest.main()
