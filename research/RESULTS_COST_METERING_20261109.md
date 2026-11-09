# Cost-metering calibration, 2026-11-09

This is a **synthetic instrumentation test, NOT an RSI audit**. No external
task labels, protected TEST, J or prior spent audits were opened.

Preregistration: [PREREG_COST_METERING_20261109.md](PREREG_COST_METERING_20261109.md).
40 independent paired seeds, three generations, 16 candidate evaluations per
generation, four arms. All results are preserved in
[complete raw JSON](results/cost_metering_raw_20261109.json).

| Arm | Candidates | Public VM | Support VM | Verify VM | Total CPU ms | Generator CPU ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| reference | 1920 | 15360 | 480 | 2880 | 38.474 | 1.762 |
| same_work | 1920 | 15360 | 480 | 2880 | 38.186 | 1.725 |
| extra_training_call | 1920 | 15360 | 600 | 2880 | 38.445 | 1.725 |
| extra_generator_cpu | 1920 | 15360 | 480 | 2880 | 696.352 | 659.647 |

Paired strict parity rejections (out of 40): same-work **0**;
extra-training-call **40**;
extra-generator-CPU **40**.
The predeclared negative-control gates: **True**.
Same-work had **0/40** false rejections on the GitHub Actions runner (95% Wilson
interval for the underlying rejection probability: **[0, 0.087622]**).
CPU timing can nevertheless vary with machine and scheduling; report both
per-seed and aggregate CPU, never infer CPU parity from matching VM counts.
This is not evidence of learning.

All arms have an identical nominal candidate budget. The extra-training
negative control has 120 additional **actually counted** support VM calls.
The extra-generator control has matched VM calls but charged extra CPU.
OS timing, bypassed wrappers, external substrate validity, and future
held-out transfer remain unverified. No RSI adoption is warranted.

## Development preflight disclosure

Before the GitHub Actions run, a **separate local engineering dry run**
using a related, non-identical implementation of these synthetic fixtures
was inspected. Its same-work CPU gate rejected **18/40** pairs, whereas the
GitHub Actions implementation rejected **0/40**. Its extra-training and
extra-generator negative controls each rejected **40/40**. No task labels or
protected holdouts were involved, and the numerical gates were not relaxed.
The local code and timings are not interchangeable with the committed
GitHub-run code, so they must **not** be pooled as independent seed
replications or used as evidence of an RSI result. This disclosure also
shows why a CPU-time gate cannot be assumed portable across environments.

The GitHub run is the sole committed reference for this engineering
calibration. A future genuine external audit must use its own preregistered
manifest and must not be repeated after audit peeking.
