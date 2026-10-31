# Frozen long-horizon Q Labs DUST Meta-RL transfer study

The original DUST local logit estimator (PR #39, source pinned to
qlabs-eng/noise f6dc47543bf62aa4926808f6aad19e88d2e1daf2) is used
as-is, WITHOUT additional contrastive weighting, uncertainty-aware
action routing, or depth-two practice. Seed 11, 16 generations, same
TRAIN/DSL/frozen verifier and 64 evaluation candidates per task as
the Honest Self-Play research.

The published baseline at 16 generations is TRAIN 29/36 and a
retrospective RESERVE-FAR2 5/21. The pre-run hypothesis is
`DUST_FAR2 > 5/21`, with NULL/regression also legitimate outcomes.
No VALIDATION/RESERVE/FAR/FAR2/TEST data may be touched during training.
After the completed checkpoint is frozen, run the original
`reserve_eval` once on the already exposed FAR2. The resulting comparison
is **not blind** because FAR2 results were published before the design.

A separate freshly specified and unexposed family suite is required
for new blind-transfer claims. No performance conclusion is valid before
the CI result completes.
