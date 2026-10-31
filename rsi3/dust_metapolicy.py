"""DUST-style forward-only local credit for RSI-3's Meta-RL action policy.

Source: qlabs-eng/noise at f6dc47543bf62aa4926808f6aad19e88d2e1daf2,
train/val/dust.py: DUST.direct_errors(), DUST.reassemble(), DUST.step().
The original MIT-licensed source is preserved byte-for-byte in
third_party/qlabs_noise/dust_reference.py.

This is an adaptation of the *actual* reward-weighted activation perturbation
estimator to one scalar logit per search action, NOT the upstream transformer's
attention-local DUST kernels or its 4,000x challenge record. Every learner
input is an already recorded TRAIN chunk outcome or honest synthetic-practice
outcome, identical to MetaPolicy.fit. Neither hidden examples nor held-out
partition results enter this model. No autograd/backward or analytic logistic
loss gradient is used during fitting.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib

import numpy as np

from .metarl import MetaPolicy, L2, _sigmoid


def local_logit_credit(logits, labels, *, rng, draws=16, sigma=0.25,
                       row_chunk=512):
    """Estimate d(BCE)/d(logit) with Q Labs' centered DUST direct-errors rule.

    One clean forward; each Gaussian activation perturbation is scored by
    clean_loss - perturbed_loss. Rewards are centered across draws, multiplied
    by the perturbation, then negated/divided by sigma and draw count.
    Chunking rows bounds peak RAM; all rows and draws are still evaluated.
    This estimates the gradient of a *smoothed* loss, not the exact gradient.
    """
    z = np.asarray(logits, dtype=np.float64).reshape(-1)
    y = np.asarray(labels, dtype=np.float64).reshape(-1)
    if z.shape != y.shape:
        raise ValueError("logits and labels must have the same shape")
    if draws < 2 or sigma <= 0 or row_chunk <= 0:
        raise ValueError("invalid perturbation parameters")
    if not np.all(np.isfinite(z)) or not np.all(np.isfinite(y)) or np.any((y < 0) | (y > 1)):
        raise ValueError("invalid logits or binary labels")
    result = np.empty(len(z), dtype=np.float64)
    for start in range(0, len(z), row_chunk):
        end = min(start + row_chunk, len(z))
        zi, yi = z[start:end], y[start:end]
        noise = rng.standard_normal((draws, len(zi)))
        clean_loss = np.logaddexp(0.0, zi) - yi * zi
        perturbed = zi[None, :] + sigma * noise
        changed_loss = np.logaddexp(0.0, perturbed) - yi[None, :] * perturbed
        rewards = clean_loss[None, :] - changed_loss
        rewards -= rewards.mean(axis=0, keepdims=True)
        result[start:end] = -np.mean(rewards * noise, axis=0) / sigma
    return result


class DustMetaPolicy(MetaPolicy):
    """Ablation: replace ONLY honest MetaPolicy's parameter update with DUST.

    Choice rule, exploration bonus, recorded actions, reward provenance,
    episode replay, unseen-action prior and per-action logistic model all
    remain inherited and unchanged. Adam acts on the DUST local estimate.
    """

    def __init__(self, *, exploration=0.3, wipe=False, seed=0,
                 draws=16, sigma=0.25, steps=80, rate=0.045,
                 contrastive=False):
        super().__init__(exploration=exploration, wipe=wipe)
        self.seed = int(seed)
        self.draws = int(draws)
        self.sigma = float(sigma)
        self.steps = int(steps)
        self.rate = float(rate)
        self.contrastive = bool(contrastive)
        self._active_group = None
        self._group_counter = 0
        self._episode_groups = []
        if self.draws < 2 or self.sigma <= 0 or self.steps < 1 or self.rate <= 0:
            raise ValueError("invalid DUST learner configuration")

    def begin_practice_group(self):
        """Identify actions run on the same synthetic public task.

        This changes no recorded binary label. Relative weights are only
        computed after ALL same-task counterfactual action outcomes exist.
        """
        if self._active_group is not None:
            raise RuntimeError("nested practice group")
        self._group_counter += 1
        self._active_group = self._group_counter

    def end_practice_group(self):
        self._active_group = None

    def record(self, generation, action, x, reward):
        super().record(generation, action, x, reward)
        self._episode_groups.append(self._active_group)

    def fit(self, generation: int) -> dict:
        replay = [(e, group) for e, group in zip(self.episodes, self._episode_groups)
                  if not self.wipe or e[0] == generation]
        grouped = defaultdict(list)
        if self.contrastive:
            for (_, action, x, reward), group in replay:
                if group is not None:
                    grouped[group].append(int(reward))
        group_rates = {g: sum(rs) / len(rs) for g, rs in grouped.items()
                       if len(rs) > 1}
        by_action = defaultdict(list)
        for (_, action, x, reward), group in replay:
            rate = group_rates.get(group)
            # A success distinguishing one action among numerous alternatives
            # is more informative than a success shared by every alternative.
            # All actual outcomes remain strictly 0/1; no invented positives.
            weight = (1.0 + 2.0 * abs(reward - rate)
                      if rate is not None and 0.0 < rate < 1.0 else 1.0)
            by_action[action].append((x, reward, weight))
        self.models = {}
        successes = sum(e[3] for e, _ in replay)
        self.base_rate = (successes + 1.0) / (len(replay) + 2.0)
        summary = {}
        forward_evals = 0
        for action, rows in sorted(by_action.items()):
            X = np.stack([x for x, _, _ in rows]).astype(np.float64)
            y = np.asarray([r for _, r, _ in rows], dtype=np.float64)
            weights = np.asarray([weight for _, _, weight in rows], dtype=np.float64)
            n, positives = len(y), int(y.sum())
            prior = (positives + 1.0) / (n + 2.0)
            w = None
            if 0 < positives < n:
                w = np.zeros(X.shape[1], dtype=np.float64)
                m = np.zeros_like(w)
                v = np.zeros_like(w)
                # Stable per-action seed, no Python randomized hash() values.
                digest = hashlib.sha256(action.encode("utf-8")).digest()
                action_seed = int.from_bytes(digest[:8], "little")
                rng = np.random.default_rng(
                    (self.seed * 1000003 + generation * 9176 + action_seed) % (2**64))
                for iteration in range(1, self.steps + 1):
                    z = X @ w
                    error = local_logit_credit(
                        z, y, rng=rng, draws=self.draws, sigma=self.sigma)
                    # Q Labs DUST.reassemble: outer product of error and cached input.
                    gradient = X.T @ (error * weights) / weights.sum() + L2 * w
                    m = 0.9 * m + 0.1 * gradient
                    v = 0.999 * v + 0.001 * gradient * gradient
                    w -= self.rate * (m / (1 - 0.9**iteration)) / (
                        np.sqrt(v / (1 - 0.999**iteration)) + 1e-8)
                forward_evals += n * (1 + self.draws) * self.steps
            self.models[action] = (w, prior)
            summary[action] = {"episodes": n, "rewards": positives}
        self.last_fit = {"replayed": len(replay), "actions": summary,
                         "learner": "qlabs_dust_local_logit_credit",
                         "forward_loss_evaluations": forward_evals,
                         "draws": self.draws, "sigma": self.sigma,
                         "steps": self.steps,
                         "contrastive": self.contrastive,
                         "practice_groups": len(group_rates)}
        return self.last_fit
