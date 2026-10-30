# Portfolio study: measured results

All three registered runs completed: RSI3_META_PORTFOLIO × seeds 11/22/33
× 16 generations. They used `experiment_config_portfolio.json`, unchanged
since the pre-registration commit 101c3c8, and ran with
`python -m rsi3.longrun` in a single process. Raw run files are in
[`results_portfolio/`](results_portfolio/).

**Headline.**

| | PORTFOLIO | HONEST | BASE |
| --- | --- | --- | --- |
| TRAIN | **29/36** | 29/36 | 21/36 |
| Learned solver on VALIDATION (every seed) | **8/12** | 9/12 | 7/12 |

PORTFOLIO's held-out score is above the designer-only control's 7 and one
below HONEST, the same arm without the portfolio.

The library-free variants won the policy's practice, and the policy
preferred them. They cannot build the constant 5, which the system learned
on TRAIN. So `caesar-cipher (k=2, n=5)`, which HONEST solved with the
library pool in 34 candidates, was missed. Here the self-acquired material
decided a held-out task.

## Results

| Arm | TRAIN g16 | VALIDATION g16 (11/22/33) | `validation_agent` g16 (11/22/33) | agent g1–g16 (every seed) | CPU s per run |
| --- | --- | --- | --- | --- | --- |
| RSI3_META_BEH_BASE | 21 | 2 / 2 / 1 | 7 / 7 / 7 | 7 8 8 7 7 7 7 7 7 7 7 7 7 7 7 7 | ~3,020 |
| RSI3_META_HONEST | 29 | 2 / 1 / 1 | 9 / 9 / 9 | 6 9 8 6 8 8 8 8 8 8 8 8 8 9 8 9 | ~4,370 |
| **RSI3_META_PORTFOLIO** | **29** | 1 / 1 / 1 | **8 / 8 / 8** | 5 7 8 8 8 8 8 8 8 8 8 8 8 8 8 8 | ~3,025 |

TRAIN reproduced the development trajectory exactly:
10 13 15 16 21 21 24 24 24 24 25 27 28 29 29 29. The final TRAIN set is
HONEST's.

Held-out spending at generation 16, seed 11:

- **Solved through `behave0:map`:** `caesar-cipher (k=1, n=3)` and
  `(k=1, n=4)` in 13 candidates each, `caesar-cipher (k=3, n=2)` in 7,
  `add-k (k=5)` in 13, and `bool-identify-is-mod-k (k=2)` in 25.
- **`has-k (k=2)`:** three skeleton chunks, then `behave0:any_list` in 10.
- **Missed, `caesar-cipher (k=2, n=5)`:** `behave0:map` 32 and
  `behave:map` 16. HONEST's `behave:map` solved it in 34.
- **`slice-k-n (k=3, n=3)`:** one chunk each on `filter_list`, `fold_nil`,
  `behave0:whole` and `behave0:fold`. Not solved. The fixed-length flag did
  not move the slice to `behave:whole`.

The policy's replay at generation 16:

| Action | Rewarded / episodes |
| --- | --- |
| `behave0:map` | 491 / 516 |
| `behave:map` | 430 / 513 |
| `decompose:map` | 357 / 512 |

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| PORTFOLIO TRAIN g16 | 29 (determined) | 29 | hit |
| P3 PORTFOLIO TRAIN > BASE TRAIN | PASS (determined) | 29 vs 21 | hit |
| P1 PORTFOLIO agent > FOLD agent | PASS | 8 vs 5 | hit |
| P2 PORTFOLIO agent > HONEST agent | PASS (moderate) | 8 vs 9 | **miss** |
| P4 PORTFOLIO agent ≥ 6 | PASS | 8 | hit |
| P5 PORTFOLIO agent ≥ BASE agent (7) | PASS (moderate) | 8 | hit |
| P6 point forecast | 7 (6–8) | 8 | hit (in range) |
| P7 slice solved | no | no | hit |

Seven of eight hit. P2 was registered before HONEST's held-out result was
seen.

## Limits

- **Exposure.** VALIDATION was not an unseen set for this design
  (PREDICTIONS_PORTFOLIO.md).
- **Clean held-out measure.** RESERVE_RESULTS.md measures this arm, and
  every other, on 112 tasks no design decision has seen.
- **Scale.** 36 + 12 list tasks. No claim about superintelligence, the
  singularity or consciousness.
