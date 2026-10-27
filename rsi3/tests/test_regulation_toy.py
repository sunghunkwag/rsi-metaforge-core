import unittest

import numpy as np

from rsi3.studies import regulation_toy as toy


class RegulationToyTests(unittest.TestCase):
    def test_gradients_match_finite_differences(self):
        rng = np.random.default_rng(0)
        p = toy.init_params(rng, 7)
        X, Y = toy.make_batch(rng, 1, 16)
        analytic = toy.grad(p, X, Y)
        eps, worst = 1e-6, 0.0
        for key, array in p.items():
            for index in np.ndindex(array.shape):
                old = array[index]
                array[index] = old + eps
                plus = toy.loss(p, X, Y)
                array[index] = old - eps
                minus = toy.loss(p, X, Y)
                array[index] = old
                numeric = (plus - minus) / (2 * eps)
                denominator = max(1e-8, abs(numeric) + abs(analytic[key][index]))
                worst = max(worst, abs(numeric - analytic[key][index]) / denominator)
        self.assertLess(worst, 1e-6)

    def test_dormant_units_preserve_function_and_wake_through_output_weights(self):
        rng = np.random.default_rng(1)
        p = toy.init_params(rng, 5)
        X, Y = toy.make_batch(rng, 0, 32)
        state, opt = toy.new_state(None), toy.Momentum(p, 0.02)
        before = toy.loss(p, X, Y)
        toy.grow_units(p, opt, state, 3, rng)
        self.assertAlmostEqual(before, toy.loss(p, X, Y), places=12)
        g = toy.grad(p, X, Y)
        self.assertEqual(float(np.linalg.norm(g["W1"][:, -3:])), 0.0)
        self.assertGreater(float(np.linalg.norm(g["W2"][-3:])), 0.0)
        self.assertEqual(opt.v["W2"].shape, p["W2"].shape)


if __name__ == "__main__":
    unittest.main()
