"""Numerical and integration tests for the Q Labs DUST meta-policy port.

The analytic logistic derivative is used ONLY as a test oracle; the DUST
learner itself never calls backward/autograd or analytic BCE gradients.
"""
import dataclasses
import unittest

import numpy as np

from rsi3.dust_metapolicy import DustMetaPolicy, local_logit_credit
from rsi3.experiment import ARMS
from rsi3.metarl import MetaPolicy, context
from rsi3.loop import Runtime
from rsi2.corpus import load_train


class DustLocalCreditTests(unittest.TestCase):
    def test_centered_forward_credit_approaches_reference_derivative(self):
        z = np.array([-1.5, 0.0, 1.25])
        y = np.array([0., 1., 0.])
        estimate = local_logit_credit(
            z, y, rng=np.random.default_rng(71), draws=32768, sigma=0.08)
        reference = 1.0 / (1.0 + np.exp(-z)) - y
        np.testing.assert_allclose(estimate, reference, atol=0.035)

    def test_zero_rows_and_reproducibility(self):
        z = np.array([0.1, -0.7, 1.3, 0.0])
        y = np.array([1., 0., 0., 1.])
        a = local_logit_credit(z, y, rng=np.random.default_rng(5), draws=64)
        b = local_logit_credit(z, y, rng=np.random.default_rng(5), draws=64)
        np.testing.assert_array_equal(a, b)
        self.assertEqual(
            len(local_logit_credit([], [], rng=np.random.default_rng(0))), 0)

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            local_logit_credit([float("nan")], [1], rng=np.random.default_rng(1))
        with self.assertRaises(ValueError):
            local_logit_credit([1], [0, 1], rng=np.random.default_rng(1))
        with self.assertRaises(ValueError):
            local_logit_credit([0], [1], rng=np.random.default_rng(1), draws=1)


class DustMetaPolicyTests(unittest.TestCase):
    def _make_policy(self):
        policy = DustMetaPolicy(seed=11, exploration=0.0, steps=80, draws=16)
        first = np.zeros(11)
        first[0] = 1.
        second = np.zeros(11)
        second[3] = 1.
        for generation in (1, 2):
            for _ in range(14):
                policy.record(generation, "behave:map", context(first, 0, 0), 1)
                policy.record(generation, "behave:map", context(second, 0, 0), 0)
                policy.record(generation, "behave:any", context(second, 0, 0), 1)
                policy.record(generation, "behave:any", context(first, 0, 0), 0)
        return policy, first, second

    def test_action_credit_learns_across_public_contexts(self):
        policy, first, second = self._make_policy()
        metrics = policy.fit(2)
        self.assertEqual(metrics["learner"], "qlabs_dust_local_logit_credit")
        self.assertGreater(metrics["forward_loss_evaluations"], 0)
        self.assertEqual(policy.choose(["behave:map", "behave:any"], first, {}, 0),
                         "behave:map")
        self.assertEqual(policy.choose(["behave:map", "behave:any"], second, {}, 0),
                         "behave:any")

    def test_repeated_fit_is_byte_deterministic(self):
        policy, _, _ = self._make_policy()
        policy.fit(2)
        first = {k: (v[0].copy(), v[1]) for k, v in policy.models.items()}
        policy.fit(2)
        for action, (weights, prior) in first.items():
            np.testing.assert_array_equal(policy.models[action][0], weights)
            self.assertEqual(policy.models[action][1], prior)

    def test_matched_arms_differ_only_by_credit_learner(self):
        for base_name, dust_name in (
            ("RSI3_META_HONEST", "RSI3_META_HONEST_DUST"),
            ("RSI3_META_PORTFOLIO", "RSI3_META_PORTFOLIO_DUST"),
        ):
            base = dataclasses.asdict(ARMS[base_name])
            dust = dataclasses.asdict(ARMS[dust_name])
            self.assertFalse(base.pop("meta_dust"))
            self.assertTrue(dust.pop("meta_dust"))
            base.pop("name")
            dust.pop("name")
            self.assertEqual(base, dust)

    def test_runtime_switch_keeps_baseline_unchanged(self):
        config = {
            "B_wake": 4, "B_eval": 4, "dreams": 0,
            "search": {"step_budget": 200, "max_size": 5,
                       "max_expansions": 128},
            "controller": {"chunk": 4, "exploration": 0.3,
                           "analog_neighbors": 1},
            "meta": {"chunk": 4, "selfplay": 0},
            "compact_searches": True,
        }
        tasks = load_train()[:2]
        base = Runtime(11, tasks, ARMS["RSI3_META_HONEST"], config)
        dust = Runtime(11, tasks, ARMS["RSI3_META_HONEST_DUST"], config)
        self.assertIsInstance(base.metapolicy, MetaPolicy)
        self.assertNotIsInstance(base.metapolicy, DustMetaPolicy)
        self.assertIsInstance(dust.metapolicy, DustMetaPolicy)


if __name__ == "__main__":
    unittest.main()
