# Pre-registration: external DreamCoder multi-generation metasearch

Date: 2026-11-08. This document is committed BEFORE the first experiment run and BEFORE the implementation of the replacement runner. No experiment-specific observed results have been inspected.

## Immutable task-source commitment

- Main baseline: `c4f0a8627a1c9f37dd3aa6291b0eee0c78648210`.
- Upstream tasks from DreamCoder's `ellisk42/ec`, upstream commit `cb0e63f5c33cd2de360b791038b0f5272750270e`, path `data/list_tasks.json`, upstream Git blob `2816d1ee51ff2f523704c1930d8736eb99711036`.
- Local source path, unchanged: `rsi2/data/source_list_tasks.json`.
- Existing old train/validation/TEST split exclusions: `rsi2/data/split_manifest.json`, blob `afac5b3f2dc346027caaba36f308f2b1e078ebda`. Never load `rsi2/data/test.json`, `rsi3` sealed TEST/J, or RSI-4.
- New task manifest: `research/external_metacontrol_task_manifest.json`, **blob `c27b1c6431ab9d836c94f9ddc66269fd4216a1e0`**, independently committed in `ff193281d57cfaa6e1a56736d41d80fba950f8fd` BEFORE this preregistration.
- 16 external source tasks divided among three support generations (5,5,6); 15 new development tasks (5,5,5); 19 single-use audit tasks. Audit operator families differ from both support and development families. Audit data is not available to control selection.
- Audit task *identifiers* and semantics come from the pinned external source, not invented by the experimenter. All shifted inputs are programmatically derived from deterministic published task-name semantics and **at least 32 varied-length, fresh inputs** per task/trajectory. The upstream 15 examples serve as post-freeze semantic-consistency checks. Any oracle discrepancy aborts the experiment; no post-hoc oracle fixes.
- This is one list-of-integers task substrate with different transformation families; **NOT** a four-substrate test. A later separate holdout would be required to establish other substrates.

## Pre-registered hypothesis and predictions

**Primary hypothesis H1**: Across independent 40-seed search trajectories, the search-policy controller that retains a reward-weighted distribution over its own mutation operators will improve shifted-input correctness in truly new DreamCoder function families progressively from generation 1 to 3, beyond fixed, no-memory, memory-wiped, and same-total-compute single-generation controls.

**Expected effect** (prospective, NOT an observed result): by generation 3, at least **+8 absolute percentage points** in OOD task success relative to the strongest fixed baseline, and **+5 pp** relative to the strongest memory-wiped or one-generation matched-total-compute control. Expect at least 12 of 19 audit task families/identifiers to have positive paired gains, and no more than 2 per-task losses. These are predictions, not assertions or relaxed gates.

**Decision threshold is stricter than the prediction**:
1. Each independent final audit task is correct only if the discovered program passes **all 32** shifted inputs of varied lengths, not just the public training examples.
2. At least **+8 percentage points** OOD success versus the best fixed baseline; at least **+5 points** versus *each* memory-wiped, no-memory, and same-total-compute single-generation control.
3. A 95% paired bootstrap confidence interval clustered by the 40 independent seed trajectories must have a lower bound > 0 for gains versus **every** baseline; calculate two-sided paired McNemar statistics as a secondary diagnostic and report exact per-case wins, losses and ties.
4. For each of the distinct audit families `append-k`, `keep-mod-k`, `modulo-k`, `remove-mod-k`, `rotate-k`, the paired aggregate OOD delta must be nonnegative; report every task's positive and negative cases. Do **not** use incumbent precedence or superset candidate retention; the controller can lose.
5. The *development* generation-to-generation improvement margin over the strongest fixed baseline must be nondecreasing across three checkpoints and rise **>= 5 pp from generation 1 to generation 3**. This is prospective trajectory evidence, not audit-task peeking. On final **unseen** audit-family tasks, independently trained controller state must beat the one-generation equal-total-compute control.
6. Seven arms: strongest simple deduplicated-uniform, frozen mutation, untrained randomly initialized/no-memory, memory-wiped at each generation, one-generation same-total-compute batch-learning, adaptive persistent metacontroller, inverted-feedback negative control. The negative control is **predicted to fail** all acceptance thresholds; if it passes the primary gate, mark the experiment inconclusive.
7. Require matching **actual candidate evaluations and public task VM calls**, not nominal proposal slots; charge all invalid and failed proposals identically as actual executed candidate calls using a total deterministic evaluator. Require identical per-arm CPU ceiling of 0.5 process CPU seconds per task-seed episode and report measured CPU. Reject a positive CPU-efficiency claim if total CPU differs by >10% from the strongest control; do not inflate CPU with artificial waiting.
8. All arms have 48 evaluated candidates per task/seed episode and 12 public training inputs; use 32 independent shifted inputs per task/seed. Do not stop early after an apparent train solution; every counted evaluation is run. Training evaluation and final audit verification calls are counted separately and reported.
9. Three generations; 40 independently initialized seed trajectories. Each trajectory has its own controller weights, separate candidate RNG streams, support examples and hidden shift-input RNG. Task outputs are deterministic from external semantics. Do not treat correlated task outcomes within the same trajectory as independent replicates.
10. Freeze controls, sample sizes, semantics, confidence interval method, predictions, and thresholds from this commit. No rerun/reselection after inspecting the audit result. All negative results must be retained.

## Data isolation, compute, and deliverables

- Development tasks are permitted for choosing a candidate policy and reporting learning curves; their labels must not update controller weights.
- Generation support tasks alone supply feedback. No audit-family ID, original audit labels, shift feedback, or previously used PR #50-56 audit instances may inform policy updates.
- No imports from unmerged PR #55/#56 by SHA. Build only on `main`. Existing PRs remain untouched.
- Commit the complete raw per-trajectory/per-task JSON (including each candidate score and budget counters) to the repository; do not rely only on expiring Actions artifacts.
- Update root `README.md` with links, exact final CI SHA, pass/fail outcomes, effect sizes and limitations.
- A failure of any acceptance criterion is **not a successful RSI result**. Even passing this finite test would demonstrate learning-to-search on a subset of DreamCoder tasks, not autonomously rewriting source or general RSI.

## Stop/negative-control conditions

Fail the claim on zero/negative OOD transfer, per-family regression, negative-control passing, nonmonotone development gain, CPU mismatch, evaluation-budget mismatch, identical seed trajectories masquerading as independent, oracle mismatch, missing raw JSON, source SHA mismatch, or use of any previously sealed holdout.
