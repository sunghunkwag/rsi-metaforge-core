# Contrastive DUST policy: precommitted development protocol

Parent: PR #39, Q Labs DUST local-credit learner; scientific code base:
`rsi3/dream-practice` at `bf2463bd08fd73adc21210b37179565e10a3b911`.

## Hypothesis

A DUST local-credit predictor trained on a task's **relative** observed action
outcomes will route scarce candidate windows better than a DUST predictor
trained on unrelated absolute binary outcomes. Each synthetic practice task
actually executes all of its available actions. Action successes and failures
are unmodified. For practice groups with mixed results, use a sample weight
`1 + 2 * abs(actual_reward - within_task_success_rate)` in the
forward-only DUST local-credit update; leave constant-outcome groups and
genuine TRAIN receipts unweighted. The scalar DUST estimator and chosen-action
UCB policy are otherwise unchanged.

This is a Q Labs-inspired *relative local-credit extension*, not the original
DUST GPU algorithm and not the Noise 4000x challenge.

## Development test and decision

Only TRAIN and the policy's honest synthetic-practice tasks are accessed.
Freeze the source and run four generations with seed 11 and B_wake=64:
`RSI3_META_HONEST_DUST` versus
`RSI3_META_HONEST_DUST_CONTRAST`. All settings match except
`meta_dust_contrastive`. Do not load VALIDATION/RESERVE/FAR/FAR2/TEST
at this stage. Measure actual verifier-approved TRAIN solutions per generation,
candidate work, policy fitting cost, CPU, and count of contrasted groups.

If there is no additional TRAIN solve, label development NULL and do not
claim transfer. If it improves TRAIN, a separate frozen 16-generation
study may be warranted.

## Scientific caveats

- No causal effect can be inferred merely from temporal proximity; comparison
  is only within the *same imagined task* after the actual outcome of each
  action is known.
- The early TRAIN comparison is only a developer diagnostic and has no
  generalization metric.
- Existing `RESERVE-FAR2` was published and inspected before this design.
  Re-evaluating it is a retrospective regression, **not a new blind test**.
  A new unexposed problem-family evaluation is mandatory for blind transfer
  claims.
- Do not change the frozen verifier, RSI-2 language, canonical corpus,
  original runtime, or protected files. Remain a draft PR until review.
