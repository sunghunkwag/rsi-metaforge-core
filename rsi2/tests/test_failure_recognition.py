"""Synthetic protocol checks; no corpus, search result or hidden data is loaded."""
from collections import Counter
from dataclasses import dataclass, replace
import json
from types import SimpleNamespace
import unittest

import numpy as np

from rsi2.grammar import Grammar, ROOT_CONTEXT
from rsi2.recognition import FEATURE_DIM, REGULARIZATION, TRAINING_STEPS, task_features
from rsi2.research.failure_recognition import (
    PairwiseRecognition, SharedState, align_state, contrast_rows,
    permuted_labels, preference_objective_gradient, prepare_common_state,
)
from rsi2.terms import Int, Lam
from rsi2.types import Arrow, INT


class PublicTask:
    def __init__(self, value):
        self.examples = (((), value),)
        self.request_type = INT
        self.name = f"synthetic_{value}"
        self.hidden_reads = 0

    @property
    def hidden(self):
        self.hidden_reads += 1
        raise AssertionError("hidden examples are inaccessible")


@dataclass(frozen=True)
class Preference:
    key: tuple
    task_fingerprint: str
    features: tuple
    difference: tuple
    label: int
    lo_decisions: tuple
    hi_decisions: tuple


class Memory:
    def __init__(self, records=()):
        self._records = tuple(records)

    def records(self):
        return self._records


def preference(task, grammar, *, index=0, lo=None, hi=None, label=1, fingerprint=None):
    lo, hi = Int(0) if lo is None else lo, Int(1) if hi is None else hi
    left = tuple(grammar.decisions(lo, request_type=task.request_type))
    right = tuple(grammar.decisions(hi, request_type=task.request_type))
    counts = Counter(right)
    counts.subtract(left)
    difference = tuple((context, production, count)
                       for (context, production), count in sorted(counts.items()) if count)
    fingerprint = task.name if fingerprint is None else fingerprint
    return Preference((fingerprint, f"lo{index}", f"hi{index}"), fingerprint,
                      tuple(task_features(task)), difference, label, left, right)


def fixture():
    grammar = Grammar(primitives={}, constants=(Int(0), Int(1), Int(2)))
    tasks = [PublicTask(0), PublicTask(1)]
    records = [preference(tasks[0], grammar, label=-1),
               preference(tasks[1], grammar, label=1)]
    pairs = [(task, Int(task.examples[0][1])) for task in tasks]
    return grammar, tasks, pairs, Memory(records)


class FailureRecognitionTests(unittest.TestCase):
    def test_pairwise_gradient_matches_independent_finite_differences(self):
        rng = np.random.default_rng(4)
        design = rng.normal(size=(4, 3))
        difference = rng.normal(size=(4, 2, 3))
        difference /= np.linalg.norm(difference, axis=(1, 2))[:, None, None]
        weights = rng.normal(0, .1, size=(3, 2, 3))
        labels = np.array([-1., 1., 1., -1.])
        alpha = np.array([1 / 6, 1 / 6, 1 / 6, 1 / 2])
        _, gradient = preference_objective_gradient(weights, design, difference, labels, alpha)

        def independent_loss(value):
            score = np.array([sum(design[n, d] * value[d, c, p] * difference[n, c, p]
                                  for d in range(3) for c in range(2) for p in range(3))
                              for n in range(4)])
            return (alpha * np.logaddexp(0, -labels * score)).sum() + REGULARIZATION * (value ** 2).sum() / 2

        finite = np.zeros_like(weights)
        for index in np.ndindex(weights.shape):
            upper, lower = weights.copy(), weights.copy()
            upper[index] += 1e-6
            lower[index] -= 1e-6
            finite[index] = (independent_loss(upper) - independent_loss(lower)) / 2e-6
        np.testing.assert_allclose(gradient, finite, rtol=1e-6, atol=1e-9)

    def test_pair_rows_are_task_balanced_and_rate_uses_their_covariance(self):
        grammar, tasks, _, memory = fixture()
        memory = Memory(memory.records() + (preference(tasks[0], grammar, index=1, label=-1),))
        state, _ = prepare_common_state([], grammar, memory, fitting_tasks=tasks, seed=3)
        records, design, difference, labels, alpha = contrast_rows(memory, state)
        expected = np.array([.25 if r.task_fingerprint == tasks[0].name else .5 for r in records])
        np.testing.assert_array_equal(alpha, expected)
        np.testing.assert_allclose(np.linalg.norm(difference, axis=(1, 2)), 1)
        covariance = sum(a * np.outer(x, x) for a, x in zip(alpha, design))
        eigmax = np.linalg.eigvalsh(covariance).max()
        model = PairwiseRecognition()
        metrics = model.fit_preferences(memory, state)
        self.assertAlmostEqual(metrics["learning_rate"], 1 / (eigmax + REGULARIZATION))
        self.assertAlmostEqual(metrics["hessian_bound"], .25 * eigmax + REGULARIZATION)
        self.assertLess(metrics["objective_after"], metrics["objective_before"])
        self.assertEqual(metrics["steps"], TRAINING_STEPS)
        self.assertEqual(metrics["matrix_shapes"]["difference"], list(difference.shape))
        self.assertEqual(metrics["matrix_shapes"]["covariance"], [33, 33])
        self.assertGreaterEqual(metrics["training_cpu_seconds"], 0)
        self.assertEqual(metrics["semantic_evaluator_calls"], 0)

    def test_shared_union_includes_decisions_cancelled_by_the_contrast(self):
        grammar, _, _, _ = fixture()
        task = SimpleNamespace(name="synthetic_function", request_type=Arrow(INT, INT),
                               examples=(((0,), 1),))
        record = preference(task, grammar, lo=Lam(INT, Int(0)), hi=Lam(INT, Int(1)))
        self.assertFalse(any(c == ROOT_CONTEXT for c, _, _ in record.difference))
        state, metrics = prepare_common_state([], grammar, Memory([record]),
                                              fitting_tasks=[task], seed=17)
        self.assertIn(ROOT_CONTEXT, state.contexts)
        self.assertIn("lambda/1", state.productions)
        expected = np.random.default_rng(17).normal(0, .01, state.weights.shape)
        np.testing.assert_array_equal(state.weights, expected)
        self.assertEqual(metrics["steps"], 0)
        self.assertEqual(metrics["preference_decision_visits"], 4)

    def test_common_base_and_matched_arms_share_transform_and_initial_state(self):
        grammar, tasks, pairs, memory = fixture()
        state, base = prepare_common_state(pairs, grammar, memory, fitting_tasks=tasks, seed=5)
        original = state.to_dict()
        positive, contrast = PairwiseRecognition(), PairwiseRecognition()
        positive_metrics = positive.fit_positive_extra(pairs, grammar, state)
        contrast_metrics = contrast.fit_preferences(memory, state)
        self.assertEqual(base["steps"], 80)
        self.assertEqual(positive_metrics["steps"], contrast_metrics["steps"])
        self.assertEqual(positive_metrics["steps"], 80)
        self.assertEqual(original, state.to_dict())
        self.assertFalse(state.weights.flags.writeable)
        for model in (positive, contrast):
            np.testing.assert_array_equal(model.mean, state.mean)
            np.testing.assert_array_equal(model.scale, state.scale)
            self.assertEqual(model.contexts, state.contexts)
            self.assertEqual(model.productions, state.productions)
            self.assertFalse(np.shares_memory(model.weights, state.weights))
        self.assertLess(positive_metrics["objective_after"], positive_metrics["objective_before"])

    def test_seeded_fits_and_predictions_reproduce(self):
        grammar, tasks, pairs, memory = fixture()
        state_a, _ = prepare_common_state(pairs, grammar, memory, fitting_tasks=tasks, seed=31)
        state_b, _ = prepare_common_state(pairs, grammar, memory, fitting_tasks=tasks, seed=31)
        self.assertEqual(state_a.to_dict(), state_b.to_dict())
        models = [PairwiseRecognition(), PairwiseRecognition()]
        for model, state in zip(models, (state_a, state_b)):
            model.fit_preferences(memory, state)
        self.assertEqual(models[0].to_dict(), models[1].to_dict())
        for task in tasks:
            probabilities = [model.grammar_for(task, grammar).log_probability(Int(1), INT)
                             for model in models]
            self.assertEqual(*probabilities)

    def test_retained_prior_preserves_transform_and_existing_offsets_with_new_zero_keys(self):
        grammar, tasks, pairs, memory = fixture()
        old, _ = prepare_common_state(pairs, grammar, memory, fitting_tasks=tasks, seed=7)
        record = preference(tasks[0], grammar, hi=Int(2))
        new_task = PublicTask(999)
        aligned, metrics = prepare_common_state([], grammar, Memory([record]),
                                                fitting_tasks=[new_task], seed=888, prior=old)
        self.assertEqual(metrics["transform_source"], "retained_prior")
        self.assertEqual(metrics["new_key_initialization"], "zero")
        np.testing.assert_array_equal(aligned.mean, old.mean)
        np.testing.assert_array_equal(aligned.scale, old.scale)
        for c, context in enumerate(old.contexts):
            for p, production in enumerate(old.productions):
                np.testing.assert_array_equal(old.weights[:, c, p], aligned.weights[
                    :, aligned.contexts.index(context), aligned.productions.index(production)])
        self.assertTrue((aligned.weights[:, :, aligned.productions.index("int:2/0")] == 0).all())
        self.assertEqual(align_state(old, aligned).to_dict(), aligned.to_dict())
        changed = SharedState(old.seed, aligned.contexts, aligned.productions,
                              old.mean + 1, old.scale, aligned.weights)
        with self.assertRaisesRegex(ValueError, "same frozen feature transform"):
            align_state(old, changed)

    def test_missing_frozen_keys_are_rejected_instead_of_changing_axes(self):
        grammar, tasks, pairs, memory = fixture()
        state, _ = prepare_common_state(pairs, grammar, memory, fitting_tasks=tasks)
        model = PairwiseRecognition()
        with self.assertRaisesRegex(ValueError, "positive key absent"):
            model.fit_positive_extra([(tasks[0], Int(2))], grammar, state)
        with self.assertRaisesRegex(ValueError, "preference key absent"):
            model.fit_preferences(Memory([preference(tasks[0], grammar, hi=Int(2))]), state)

    def test_permutation_is_sorted_fixed_and_reports_uninformative_cases(self):
        grammar, tasks, _, memory = fixture()
        records = memory.records() + tuple(preference(tasks[i % 2], grammar, index=i,
                                                     label=(-1 if i % 2 else 1))
                                          for i in range(1, 7))
        first, report_a = permuted_labels(Memory(records), 41)
        second, report_b = permuted_labels(Memory(reversed(records)), 41)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(report_a, report_b)
        sorted_records = sorted(records, key=lambda r: r.key)
        self.assertEqual(report_a["canonical_pair_keys"], [list(r.key) for r in sorted_records])
        expected = [sorted_records[i].label for i in report_a["source_row_mapping"]]
        self.assertEqual(first.tolist(), expected)
        self.assertEqual(report_a["status"], "informative")
        for rows in ([], [replace(r, label=1) for r in records]):
            _, report = permuted_labels(Memory(rows), 41)
            self.assertEqual(report["status"], "uninformative")
        # Seed zero leaves this two-element mixed-label sequence unchanged.
        _, report = permuted_labels(memory, 0)
        self.assertEqual(report["changed_labels"], 0)
        self.assertEqual(report["status"], "uninformative")

    def test_serialization_and_public_only_predictions_preserve_grammar(self):
        grammar, tasks, pairs, memory = fixture()
        state, _ = prepare_common_state(pairs, grammar, memory, fitting_tasks=tasks)
        self.assertEqual(SharedState.from_dict(json.loads(json.dumps(state.to_dict()))).to_dict(),
                         state.to_dict())
        model = PairwiseRecognition()
        model.fit_preferences(memory, state)
        restored = PairwiseRecognition.from_dict(json.loads(json.dumps(model.to_dict(), allow_nan=False)))
        original_contexts = dict(grammar.context_weights)
        for task in tasks:
            predicted = model.grammar_for(task, grammar)
            loaded = restored.grammar_for(task, grammar)
            self.assertEqual(predicted.constants, grammar.constants)
            self.assertEqual(predicted.primitives, grammar.primitives)
            self.assertEqual(predicted.library, grammar.library)
            for term in grammar.constants:
                self.assertEqual(predicted.log_probability(term, INT), loaded.log_probability(term, INT))
            favored = Int(task.examples[0][1])
            rejected = Int(1 - task.examples[0][1])
            self.assertGreater(predicted.log_probability(favored, INT), predicted.log_probability(rejected, INT))
            self.assertEqual(task.hidden_reads, 0)
        self.assertEqual(grammar.context_weights, original_contexts)
        self.assertEqual(model.prediction_metrics["calls"], 2)
        self.assertGreaterEqual(model.prediction_metrics["cpu_seconds"], 0)
        self.assertEqual(model.prediction_metrics["semantic_evaluator_calls"], 0)

    def test_empty_corpus_preserves_state_and_invalid_labels_or_duplicates_fail(self):
        grammar, tasks, pairs, memory = fixture()
        empty, _ = prepare_common_state([], grammar, Memory(), fitting_tasks=[])
        self.assertEqual(empty.weights.shape, (FEATURE_DIM + 1, 0, 0))
        self.assertEqual(SharedState.from_dict(empty.to_dict()).to_dict(), empty.to_dict())
        model = PairwiseRecognition()
        self.assertEqual(model.fit_preferences(Memory(), empty)["steps"], 0)
        self.assertEqual(model.fit_positive_extra([], grammar, empty)["steps"], 0)
        state, _ = prepare_common_state(pairs, grammar, memory, fitting_tasks=tasks)
        for labels in ([1], [1, 0], [1, float("nan")]):
            with self.assertRaises(ValueError):
                contrast_rows(memory, state, labels_override=labels)
        record = memory.records()[0]
        with self.assertRaisesRegex(ValueError, "deduplicate"):
            contrast_rows(Memory([record, record]), state)
        with self.assertRaisesRegex(ValueError, "nonzero"):
            contrast_rows(Memory([replace(record, difference=())]), state)


if __name__ == "__main__":
    unittest.main()
