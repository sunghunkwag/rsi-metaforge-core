"""Regression and numerical checks for the pinned Q Labs DUST estimator port."""
import unittest
import numpy as np
from rsi3.dust_value_model import DustValueModel, activation_credit
from rsi3.value_model import DIM, ValueModel

class DustPortTests(unittest.TestCase):
    def test_local_loss_derivative_from_forward_perturbations(self):
        z = np.array([-1.0, 0.2, 1.5])
        y = np.array([0.0, 1.0, 0.0])
        estimated = activation_credit(z, y, rng=np.random.default_rng(23),
                                      sigma=0.08, draws=32768)
        true = 1 / (1 + np.exp(-z)) - y
        np.testing.assert_allclose(estimated, true, atol=0.04)

    def test_draws_are_reproducible(self):
        z = np.array([0., 1.])
        y = np.array([1., 0.])
        a = activation_credit(z, y, rng=np.random.default_rng(7))
        b = activation_credit(z, y, rng=np.random.default_rng(7))
        np.testing.assert_array_equal(a, b)

    def test_model_fits_without_backward_pass(self):
        x = np.zeros((20, DIM))
        x[:, 0] = np.linspace(-2, 2, 20)
        y = (x[:, 0] > 0).astype(float)
        model = DustValueModel(seed=11, draws=32, steps=140)
        info = model.fit(x, y)
        self.assertTrue(info["fitted"])
        self.assertEqual(info["learner"], "qlabs_dust_forward_credit")
        self.assertEqual(info["forward_loss_evaluations"], 20 * 32 * 140)
        probs = model.predict(x)
        self.assertGreater(np.mean((probs > .5) == y), .85)
        other = DustValueModel(seed=11, draws=32, steps=140)
        other.fit(x, y)
        np.testing.assert_array_equal(model.weights, other.weights)

    def test_no_change_in_baseline_model(self):
        self.assertNotIsInstance(ValueModel(), DustValueModel)
        with self.assertRaises(ValueError):
            activation_credit([0], [1], rng=np.random.default_rng(0), draws=1)

if __name__ == "__main__":
    unittest.main()
