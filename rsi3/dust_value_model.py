"""CPU adaptation of Q Labs' forward-only DUST credit estimator.

Upstream source (vendored unchanged):
    rsi3/third_party/qlabs_noise/dust_reference.py
    Q Labs Noise commit f6dc47543bf62aa4926808f6aad19e88d2e1daf2
    Original functions: DUST.direct_errors, DUST.reassemble, DUST.step
    Original license: MIT (rsi3/third_party/qlabs_noise/LICENSE)

This module ports the *actual activation-perturbation credit calculation*
from DUST to the RSI-3 value learner, which has a single linear logit map.
It is deliberately NOT a port of the speedrun's fused multi-GPU kernels,
attention-internal estimators, or large transformer training procedure.

DUST source: reward = clean_loss - perturbed_loss; center reward over
noise draws; estimated local loss derivative = -mean(reward * noise)/sigma;
linear weight credit = input outer product with estimated derivative.
All outputs/losses below come exclusively from verifier-receipted
TRAIN episodes. No backward pass or analytic data-loss gradient is used.
"""
from __future__ import annotations

import numpy as np

from .value_model import DIM, EXTRA, KINDS, L2, ValueModel, _sigmoid


def activation_credit(logits, targets, *, rng, sigma=0.3, draws=32):
    """Port of DUST.direct_errors for a linear-logit activation site.

    Each draw jitters the logit for each row. Every perturbed loss is
    recomputed in a forward pass. The score-function estimator has the
    same reward sign and centering as upstream DUST.direct_errors.
    The local gradient error is not an analytic sigmoid derivative.
    """
    if sigma <= 0 or draws < 2:
        raise ValueError("sigma must be positive and draws must be >= 2")
    z = np.asarray(logits, dtype=np.float64).reshape(-1)
    y = np.asarray(targets, dtype=np.float64).reshape(-1)
    if len(z) != len(y):
        raise ValueError("logits/targets length mismatch")
    if len(z) == 0:
        return np.zeros(0, dtype=np.float64)
    if not np.all(np.isfinite(z)) or np.any((y < 0) | (y > 1)):
        raise ValueError("invalid logits or targets")
    # DUST: draws n x batch x activation-width, with loss drops centered
    # across each draw chunk. Here activation-width is exactly 1 (logit).
    noise = rng.standard_normal((draws, len(z)))
    clean_loss = np.logaddexp(0.0, z) - y * z
    perturbed_logits = z[None, :] + sigma * noise
    perturbed_loss = np.logaddexp(0.0, perturbed_logits) - y[None, :] * perturbed_logits
    reward = clean_loss[None, :] - perturbed_loss
    reward -= reward.mean(axis=0, keepdims=True)
    # DUST: errors -= einsum(reward, noise) / sigma; divide by draws.
    return -np.mean(reward * noise, axis=0) / sigma


class DustValueModel(ValueModel):
    """RSI-3 logistic value model learned with Q Labs DUST local credit.

    The frozen evaluator, feature vector, training labels, and predictions
    are exactly the baseline ValueModel's. Only the parameter-update rule
    changes. Adam is a local optimizer on the estimated weight gradient.
    """

    def __init__(self, *, seed=0, draws=32, sigma=0.3, steps=120,
                 learning_rate=0.05):
        super().__init__()
        self.seed = int(seed)
        self.draws = int(draws)
        self.sigma = float(sigma)
        self.steps = int(steps)
        self.learning_rate = float(learning_rate)
        if self.draws < 2 or self.sigma <= 0 or self.steps < 1 or self.learning_rate <= 0:
            raise ValueError("invalid DUST training hyperparameters")

    def fit(self, features, labels):
        X = np.asarray(features, dtype=np.float64).reshape(-1, DIM)
        y = np.asarray(labels, dtype=np.float64)
        n, positives = len(y), int(y.sum())
        self.prior = (positives + 1.0) / (n + 2.0)
        self.weights = None
        self.last_fit = {"examples": n, "positives": positives, "fitted": False,
                         "prior": self.prior, "learner": "qlabs_dust_forward_credit"}
        if n == 0 or positives in (0, n):
            return self.last_fit
        self.mean = X.mean(axis=0)
        self.scale = X.std(axis=0)
        self.scale[self.scale < 1e-8] = 1.0
        design = self._design(X)
        w = np.zeros(design.shape[1], dtype=np.float64)
        m = np.zeros_like(w)
        v = np.zeros_like(w)
        rng = np.random.default_rng(self.seed + 1000003 * n + 8191 * positives)
        beta1, beta2 = 0.9, 0.999
        for step in range(1, self.steps + 1):
            logits = design @ w
            error = activation_credit(logits, y, rng=rng, sigma=self.sigma,
                                      draws=self.draws)
            # DUST.reassemble: weight gradient = error outer input.
            gradient = (design.T @ error) / n + L2 * w
            m = beta1 * m + (1 - beta1) * gradient
            v = beta2 * v + (1 - beta2) * gradient * gradient
            w -= self.learning_rate * (m / (1 - beta1 ** step)) / (
                np.sqrt(v / (1 - beta2 ** step)) + 1e-8)
        self.weights = w
        probabilities = _sigmoid(design @ w)
        log_loss = -np.mean(y * np.log(probabilities + 1e-12)
                            + (1-y) * np.log(1-probabilities + 1e-12))
        self.last_fit.update({"fitted": True, "log_loss": float(log_loss),
                              "draws": self.draws, "steps": self.steps,
                              "sigma": self.sigma,
                              "forward_loss_evaluations": n * self.draws * self.steps})
        return self.last_fit
