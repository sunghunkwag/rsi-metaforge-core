# Frozen full-horizon DUST depth-practice transfer experiment

This branch inherits all code, immutable test partitions and fixed
hyperparameters from the depth-two DUST extension in PR #42. No
modifications to optimizer, data, search algorithm or verifier are made.
The previously published Honest Self-Play baseline is 29/36 TRAIN and
RESERVE-FAR2 5/21 at generation 16, B_eval=64.

**Predictions registered before this full-horizon run**
- DUST depth-two Meta-RL will complete 16 generations without reading
  VALIDATION, RESERVE or TEST during TRAIN.
- We do NOT predict a positive transfer gain; the hypothesis is
  `FAR2_depth > 5/21` after 16 generations, and failure is a valid null.
- Stronger criterion: any verified solved task newly transferred to
  a previously unresolved routine family, with no increased B_eval.
- Account CPU time and additional synthetic training evaluations.

**Method**
Run one independent TRAIN trajectory, seed 11, all 16 generations,
B_wake=64, 256 synthetic-practice attempts per generation.
After the checkpoint is frozen, perform exactly one retrospective
evaluation on FAR2 using the original `rsi3.reserve_eval` harness.
Do not tune or rerun based on FAR2 outcomes. The 21 FAR2 task
definitions and earlier arm results had already been viewed; hence
the new measurement is strictly a *retrospective known-benchmark
comparison*, not a fresh blind test. TEST remains sealed.

A new unexposed family split and three independent-seed trajectories
are needed before claiming a reproducible generalization advance.
The prior 4000x Q Labs contest record cannot be inferred from any
result of this RSI-3 experiment.
