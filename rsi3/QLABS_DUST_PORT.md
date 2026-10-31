# Q Labs DUST: pinned source and RSI-3 port

## Source acquisition

The original Q Labs algorithm source was fetched directly through the
GitHub repository connector and copied byte-for-byte into this branch:

- Upstream: https://github.com/qlabs-eng/noise
- Upstream pinned commit: `f6dc47543bf62aa4926808f6aad19e88d2e1daf2`
- Original path: `train/val/dust.py`
- Original Git blob SHA: `9cad7f00f9d4ab7faec43520bc6acfbf3392478b`
- Local exact source copy: `third_party/qlabs_noise/dust_reference.py`
- MIT license: `third_party/qlabs_noise/LICENSE`

The upstream reference is **not imported into RSI-3**: it requires PyTorch
and GPU/distributed GPT training. It is retained to make the port auditable.

## Directly ported algorithm

The port in `dust_value_model.py` follows exactly the computation in the
upstream `DUST.direct_errors` and `DUST.reassemble` methods:

1. Run a clean forward pass and obtain per-example loss.
2. Perturb the chosen activation site with independent Gaussian noise
   `z_perturbed = z + sigma * a`.
3. Run forward passes to calculate perturbed losses.
4. Calculate `reward = clean_loss - perturbed_loss` and center over draws.
5. Estimate the **loss** derivative of that activation as
   `-mean(reward * a) / sigma`.
6. Calculate the local weight gradient as the average input–error outer product.
7. Apply Adam to the estimated gradient. **No analytic data-loss derivative or
   backward/autograd pass** is called.

At the source activation site, Q Labs' method supports many dimensions and
network blocks; the RSI-3 value learner is a *single linear logit head*.
This adaptation faithfully ports the local estimator but **does not port**
Noise speedrun's fused kernels, tensor-parallel communication, attention-head
credit, block recurrences, or memory layouts. It cannot claim their speedups.

The feature vector, episode replay data, frozen verifier, external corpus,
training labels and prediction API remain identical between the experiment
and the existing RSI3_FM arm. The only intervention is the value model
parameter update. The comparison isolates DUST local credit rather than
changing the program-synthesis grammar, search, or acceptance gates.

## Hypotheses and test protocol

- Unit check: sampled forward local credit converges toward the analytic
  logistic loss gradient as draw count increases. This is a *test oracle only*.
- Functional check: the port learns a separable synthetic dataset and
  remains deterministic with a fixed seed.
- Development-only integration smoke: compare RSI3_FM,
  RSI3_DUST_FM, and RSI3_UNIFORM_FM for seed 11, 3 generations at
  B_wake = B_eval = 64. Record TRAIN hidden-verified solves,
  VALIDATION reporting, logical candidate budget and CPU time.
- Do not inspect TEST, use VALIDATION for tuning, or call a smoke-run
  a confirmatory result.
- Null or negative result means the port is technically successful but
  failed to establish a capability gain.
- A full 3-seed, 8-generation confirmatory study would require new
  pre-registration and separate evaluation. No final is claimed here.

This is a research experiment, not a claim of RSI or Q Labs benchmark parity.
