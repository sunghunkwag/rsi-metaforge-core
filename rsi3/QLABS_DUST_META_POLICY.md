# Q Labs DUST local-credit transplant: RSI-3 Honest Meta-RL

## Original source, audit and license

This branch is based on the **latest scientific lineage**, `rsi3/dream-practice`
(commit `bf2463bd08fd73adc21210b37179565e10a3b911`), rather than the
outdated `main` branch. The previous Q Labs branch PR #37 only changed the
older RSI-3 value model and found no capability improvement.

- Official upstream: https://github.com/qlabs-eng/noise
- Pinned upstream commit: `f6dc47543bf62aa4926808f6aad19e88d2e1daf2`
- Exact upstream source: `train/val/dust.py`, Git blob
  `9cad7f00f9d4ab7faec43520bc6acfbf3392478b`
- Vendored (unmodified) reference:
  `rsi3/third_party/qlabs_noise/dust_reference.py`
- Original MIT license: `rsi3/third_party/qlabs_noise/LICENSE`

The upstream source remains an auditable reference, not an imported dependency:
it is a PyTorch/CUDA distributed transformer training implementation. The
new algorithm in `rsi3/dust_metapolicy.py` is a NumPy adaptation.

## What is actually transplanted

1. Q Labs `DUST.direct_errors`: Gaussian noise on a captured activation,
   repeated forward loss, `clean_loss - noisy_loss`, reward centering across
   draws, and `-mean(reward * noise) / sigma` to estimate the local loss
   derivative without backward/autograd.
2. Q Labs `DUST.reassemble`: calculate a linear layer's local weight credit
   by the average outer product of its cached inputs and estimated output error.
3. Q Labs `DUST.step`: use Adam on these forward-only credit estimates.

Here the activation is **the single scalar logit of each search action's
Meta-RL predictor**, not an attention output. The policy still chooses
actions with its existing greedy UCB-like exploration rule, keeps all
genuine action episodes and honest public imagined-task practice, and
reuses the same features, labels, frozen evaluator, grammar, library,
candidate budgets and verifier as the unchanged baseline.

Both comparison arms are constructed by `dataclasses.replace` from the
committed Honest Self-Play or Portfolio arm: `meta_dust=True` is their
**only configuration difference**. The baseline deterministic gradient
optimizer and the proposed DUST+Adam optimizer naturally differ in their
training schedules, so cost must be measured.

We did **not** port the upstream CUDA attention-specific `local_errors`
routine, and did not claim the upstream 4,000× improvement. For a single
scalar logistic head the directly relevant mathematically equivalent
local-credit primitive is `direct_errors`. DUST's `reward_to_go` is NOT
applied to earlier search actions without causal evidence: past failed
actions must not be rewarded merely because a later action succeeded.

## Study boundaries and prior prediction

This first run is a DEVELOPMENT smoke test, not an RSI or speedrun result.

- Unit tests: estimator converges to an independent analytic test oracle,
  deterministic replay, correct action selection on synthetic public
  contexts, unchanged baseline, source/partition sealing.
- Two-generation integration smoke: seed 11, B_wake=B_eval=64,
  same TRAIN corpus and Honest Self-Play settings, `selfplay=256`.
- **No VALIDATION, RESERVE, FAR2 or TEST is loaded** during development.
- Report verified TRAIN solves, fit identity, CPU cost, candidate budgets,
  estimator draw count and additional forward-loss evaluations.
- Prior forecast: the port will run and produce an honest policy fit, but a
  positive solve-count or speed advantage is *not* presumed; null or negative
  effects are considered valid measured results.
- Confirmation would require separately registered multi-seed, full-horizon
  runs and a **fresh unseen** family split. Previously examined VALIDATION,
  RESERVE and FAR2 are not eligible as new blind tests.

No changes to RSI-2, protected runtime, sealed verifier, or corpus.
Do not merge an experimental arm as a capability improvement on passing tests
alone.
