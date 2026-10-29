# Behavioural fold follow-up: measured results

All three registered runs completed: RSI3_META_BEH_FOLD × seeds 11/22/33
× 16 generations. They used `experiment_config_behave_fold.json`, unchanged
since the pre-registration commit 833beaa and its exposure correction
aa121fc, and ran with `python -m rsi3.longrun`. Raw run files are in
[`results_behave_fold/`](results_behave_fold/). The decisive table is
`python -m rsi3.report --results rsi3/results_cascade rsi3/results_behave rsi3/results_behave_fold`.

**Headline.** TRAIN reached **29/36**, the most in any RSI-3 run. This arm
solves everything RSI3_META_BEH solves, plus the reverse family rebuilt on
the fold action:

| Generation | What happened |
| --- | --- |
| 12 | reverse, through the fold action: `fold (lambda acc x. cons x acc) nil l` |
| 13 | append-k (k=1) and (k=4), by conjugation with the system's own reverse |
| 13 | RSI-2's MDL learner compresses the step and then reverse |
| 15 | append-index-k (k=1), by conjugation with the compressed reverse |

Held out, the learned solver reached **5/12** on every seed. That is one
more than RSI3_META_BEH, equal to the cascade arm, and below the
designer-only control's 7. The fold action itself transfers nothing held
out. The extra held-out task is `bool-identify-is-mod-k (k=2)`.

## Results

| Arm | TRAIN g1–g16 | TRAIN g16 | VALIDATION g16 | `validation_agent` g16 | agent g1–g16 (every seed) | CPU s per run |
| --- | --- | --- | --- | --- | --- | --- |
| RSI3_META_CONJ (committed) | 7 8 10 11 11 13 15 16 17 17 17 17 18 20 20 21 | 21 | 2 / 2 / 1 | 5 / 5 / 5 | 2 3 4 3 4 4 4 5 5 5 5 5 5 5 5 5 (seed 11) | 4,019 |
| RSI3_META_BEH | 11 14 15 16 23 23 24 24 25 25 25 25 25 25 25 25 | 25 | 1 / 1 / 1 | 4 / 4 / 4 | 4 5 6 5 5 5 4 4 4 4 4 4 4 4 4 4 | ~3,720 |
| RSI3_META_BEH_BASE | 11 14 15 15 16 17 19 19 19 19 19 19 20 21 21 21 | 21 | 2 / 2 / 1 | 7 / 7 / 7 | 7 8 8 7 7 7 7 7 7 7 7 7 7 7 7 7 | ~3,020 |
| **RSI3_META_BEH_FOLD** | 10 14 17 23 24 24 24 25 25 25 25 26 28 28 29 29 | **29** | 1 / 1 / 1 | **5 / 5 / 5** | 3 5 6 6 6 5 4 5 5 5 5 5 5 4 5 5 | ~2,510 |

TRAIN reproduced the development trajectory exactly.

At generation 16, FOLD's agent solved these held-out tasks:

- `add-k (k=5)`;
- `bool-identify-is-mod-k (k=2)`, through `behave:map` in 13 candidates;
- `caesar-cipher (k=3, n=2)`;
- `prepend-index-k (k=3)`;
- `sum`, through the fold skeleton in 4 candidates.

Like BEH, it gave `slice-k-n (k=3, n=3)` no behavioural chunk, missed
`has-k (k=2)` and spent only one chunk on `behave:map` for each caesar task.
The policy-routing failure traced in BEHAVE_RESULTS.md is unchanged here.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| R1 FOLD TRAIN > BEH TRAIN | PASS (determined) | 29 vs 25 | hit |
| R3 FOLD TRAIN > CONJ TRAIN | PASS (determined) | 29 vs 21 | hit |
| C3 cascade at g12, g13, g15 | as in development (determined) | as in development | hit |
| R2 FOLD agent > BEH agent | FAIL (equal) | 5 vs 4 | **miss** |
| R4 FOLD agent ≥ 6 | PASS | 5 | **miss** |
| R5 FOLD agent, point forecast | 8 (6–10), the same tasks as BEH's | 5 | **miss** |

Three of six hit, and all three hits were determined in advance. The three
open forecasts all missed. R4 and R5 repeated the optimism of
PREDICTIONS_BEHAVE.md's B5 and B7. They were registered before the BEH
held-out outcome they would have been corrected by.

## Limits

- **Designer-given parts.** The fold action is designer-given.
- **What is self-directed.** In the cascade on top of the fold action's
  reverse, conjugation transforms tasks with the system's own verified
  involutions, and RSI-2's MDL learner compresses the result.
- **Held-out scores.** No arm here combines the most TRAIN (FOLD, 29) with
  the most held-out capability (BASE, 7).
- **Exposure.** VALIDATION's per-task outcomes and spending for four arms
  are now known; any later forecast on VALIDATION says so.
- **Scale.** 36 + 12 list tasks. No claim about superintelligence, the
  singularity or consciousness.
