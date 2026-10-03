# RSI-2 measured results

All 21 preregistered arm/seed runs completed. Positive recursive self-improvement was not established. Criteria (a), (b), (d), (c), (e) failed.

The frozen study uses 60 external DreamCoder tasks: TRAIN 36, VALIDATION 12, TEST 12; seeds 11, 22, 33; generations 0–8; B_wake = B_eval = 64; BRUTE budget 640. Heuristic synthesis has four enumeration slots and two mutation slots per round, with all valid proposals screened on four VALIDATION tasks at budget 16 and two confirmed on all VALIDATION tasks at 64. Strict full-VALIDATION improvement controls adoption.

TEST fractions below count only solutions passing separate hidden examples. Mean candidates-to-solution is conditional on a hidden-verified solve; — means no solves. Frozen BASE/BRUTE and post-round ONESHOT measurements are reused explicitly. Reused rows add no computation to run totals.

## Preregistered criteria

| Criterion | Requirement | Result | Evidence |
| --- | --- | --- | --- |
| (a) | Final FULL exceeds BRUTE on every seed | FAIL | seed 11: FULL 2/12, BRUTE 2/12; seed 22: FULL 2/12, BRUTE 2/12; seed 33: FULL 2/12, BRUTE 2/12; mean FULL 0.1667, BRUTE 0.1667 |
| (b) | Final FULL exceeds ONESHOT on every seed | FAIL | seed 11: FULL 2/12, ONESHOT 2/12; seed 22: FULL 2/12, ONESHOT 2/12; seed 33: FULL 2/12, ONESHOT 2/12; mean FULL 0.1667, ONESHOT 0.1667 |
| (c) | Three consecutive strict mean increases after g1, without any seed decline | FAIL | No three-transition window qualifies after g1. |
| (d) | Final FULL exceeds NO_HEURISTIC on every seed | FAIL | seed 11: FULL 2/12, NO_HEURISTIC 2/12; seed 22: FULL 2/12, NO_HEURISTIC 2/12; seed 33: FULL 2/12, NO_HEURISTIC 2/12; mean FULL 0.1667, NO_HEURISTIC 0.1667 |
| (e) | Library heuristic synthesis exceeds primitives on every seed at equal quota | FAIL | seed 11: library 0.1667, primitives 0.1667 (6 proposal slots each); seed 22: library 0.0833, primitives 0.0833 (6 proposal slots each); seed 33: library 0.1667, primitives 0.1667 (6 proposal slots each) |

Criteria (d) and (e) use the preregistered conservative every-seed requirement. Criterion (c) requires three strict mean increases on successive transitions starting at g1 or later, with every seed nondecreasing on each transition. Criterion (e) compares final-generation VALIDATION scores from the same pre-adoption state and incumbent with six synthesis proposal slots in each vocabulary. Task-search grammar/library/recognition remain shared in this counterfactual.

## Every arm, seed and generation

### Seed 11

| Arm | Generation | TEST hidden solves | Mean candidates to solution | VALIDATION hidden solves | Reused from |
| --- | --- | --- | --- | --- | --- |
| BASE | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| BASE | 1 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 2 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 3 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 4 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 5 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 6 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 7 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 8 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| BRUTE | 1 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 2 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 3 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 4 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 5 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 6 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 7 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 8 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| ONESHOT | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| ONESHOT | 1 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | no |
| ONESHOT | 2 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 3 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 4 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 5 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 6 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 7 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 8 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | g1 |
| FULL | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| FULL | 1 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | no |
| FULL | 2 | 2/12 (0.1667) | 11.50 | 1/12 (0.0833) | no |
| FULL | 3 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | no |
| FULL | 4 | 2/12 (0.1667) | 13.50 | 1/12 (0.0833) | no |
| FULL | 5 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | no |
| FULL | 6 | 2/12 (0.1667) | 12.00 | 2/12 (0.1667) | no |
| FULL | 7 | 2/12 (0.1667) | 15.00 | 2/12 (0.1667) | no |
| FULL | 8 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_LIBRARY | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 1 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | no |
| NO_LIBRARY | 2 | 2/12 (0.1667) | 11.50 | 1/12 (0.0833) | no |
| NO_LIBRARY | 3 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 4 | 2/12 (0.1667) | 13.50 | 1/12 (0.0833) | no |
| NO_LIBRARY | 5 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | no |
| NO_LIBRARY | 6 | 2/12 (0.1667) | 12.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 7 | 2/12 (0.1667) | 15.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 8 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 1 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 2 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 3 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 4 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 5 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 6 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 7 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 8 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 1 | 2/12 (0.1667) | 12.00 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 2 | 2/12 (0.1667) | 11.50 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 3 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 4 | 2/12 (0.1667) | 13.50 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 5 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 6 | 2/12 (0.1667) | 12.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 7 | 2/12 (0.1667) | 15.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 8 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |

### Seed 22

| Arm | Generation | TEST hidden solves | Mean candidates to solution | VALIDATION hidden solves | Reused from |
| --- | --- | --- | --- | --- | --- |
| BASE | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| BASE | 1 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 2 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 3 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 4 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 5 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 6 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 7 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 8 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| BRUTE | 1 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 2 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 3 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 4 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 5 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 6 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 7 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 8 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| ONESHOT | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| ONESHOT | 1 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | no |
| ONESHOT | 2 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | g1 |
| ONESHOT | 3 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | g1 |
| ONESHOT | 4 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | g1 |
| ONESHOT | 5 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | g1 |
| ONESHOT | 6 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | g1 |
| ONESHOT | 7 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | g1 |
| ONESHOT | 8 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | g1 |
| FULL | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| FULL | 1 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | no |
| FULL | 2 | 2/12 (0.1667) | 18.00 | 1/12 (0.0833) | no |
| FULL | 3 | 2/12 (0.1667) | 19.00 | 2/12 (0.1667) | no |
| FULL | 4 | 2/12 (0.1667) | 18.50 | 1/12 (0.0833) | no |
| FULL | 5 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| FULL | 6 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| FULL | 7 | 2/12 (0.1667) | 15.50 | 2/12 (0.1667) | no |
| FULL | 8 | 2/12 (0.1667) | 19.50 | 1/12 (0.0833) | no |
| NO_LIBRARY | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 1 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 2 | 2/12 (0.1667) | 18.00 | 1/12 (0.0833) | no |
| NO_LIBRARY | 3 | 2/12 (0.1667) | 19.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 4 | 2/12 (0.1667) | 18.50 | 1/12 (0.0833) | no |
| NO_LIBRARY | 5 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_LIBRARY | 6 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_LIBRARY | 7 | 2/12 (0.1667) | 15.50 | 2/12 (0.1667) | no |
| NO_LIBRARY | 8 | 2/12 (0.1667) | 19.50 | 1/12 (0.0833) | no |
| NO_RECOGNITION | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 1 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 2 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 3 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 4 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 5 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 6 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 7 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 8 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 1 | 2/12 (0.1667) | 13.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 2 | 2/12 (0.1667) | 18.00 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 3 | 2/12 (0.1667) | 19.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 4 | 2/12 (0.1667) | 18.50 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 5 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 6 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 7 | 2/12 (0.1667) | 15.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 8 | 2/12 (0.1667) | 19.50 | 1/12 (0.0833) | no |

### Seed 33

| Arm | Generation | TEST hidden solves | Mean candidates to solution | VALIDATION hidden solves | Reused from |
| --- | --- | --- | --- | --- | --- |
| BASE | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| BASE | 1 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 2 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 3 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 4 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 5 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 6 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 7 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BASE | 8 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| BRUTE | 1 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 2 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 3 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 4 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 5 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 6 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 7 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| BRUTE | 8 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | g0 |
| ONESHOT | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| ONESHOT | 1 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | no |
| ONESHOT | 2 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 3 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 4 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 5 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 6 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 7 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | g1 |
| ONESHOT | 8 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | g1 |
| FULL | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| FULL | 1 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | no |
| FULL | 2 | 2/12 (0.1667) | 13.00 | 1/12 (0.0833) | no |
| FULL | 3 | 2/12 (0.1667) | 15.50 | 2/12 (0.1667) | no |
| FULL | 4 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| FULL | 5 | 2/12 (0.1667) | 20.00 | 1/12 (0.0833) | no |
| FULL | 6 | 2/12 (0.1667) | 15.00 | 1/12 (0.0833) | no |
| FULL | 7 | 2/12 (0.1667) | 12.00 | 2/12 (0.1667) | no |
| FULL | 8 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_LIBRARY | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 1 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | no |
| NO_LIBRARY | 2 | 2/12 (0.1667) | 13.00 | 1/12 (0.0833) | no |
| NO_LIBRARY | 3 | 2/12 (0.1667) | 15.50 | 2/12 (0.1667) | no |
| NO_LIBRARY | 4 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_LIBRARY | 5 | 2/12 (0.1667) | 20.00 | 1/12 (0.0833) | no |
| NO_LIBRARY | 6 | 2/12 (0.1667) | 15.00 | 1/12 (0.0833) | no |
| NO_LIBRARY | 7 | 2/12 (0.1667) | 12.00 | 2/12 (0.1667) | no |
| NO_LIBRARY | 8 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 1 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 2 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 3 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 4 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 5 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 6 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 7 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_RECOGNITION | 8 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 0 | 2/12 (0.1667) | 9.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 1 | 2/12 (0.1667) | 16.00 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 2 | 2/12 (0.1667) | 13.00 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 3 | 2/12 (0.1667) | 15.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 4 | 2/12 (0.1667) | 11.50 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 5 | 2/12 (0.1667) | 20.00 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 6 | 2/12 (0.1667) | 15.00 | 1/12 (0.0833) | no |
| NO_HEURISTIC | 7 | 2/12 (0.1667) | 12.00 | 2/12 (0.1667) | no |
| NO_HEURISTIC | 8 | 2/12 (0.1667) | 14.50 | 2/12 (0.1667) | no |

## Measured compute

Logical candidate counts include task-search attempts, dream attempts, heuristic proposal slots and every inner heuristic search, including duplicates and failed candidates. FULL also includes its primitive-only vocabulary counterfactual. Candidates/s uses each run's wall time; CPU time is reported separately. Per-arm summed wall time is worker duration, not parallel experiment elapsed time. For partial or failed runs, candidate totals count completed operations only and are lower bounds; an interrupted operation's attempts may not have been checkpointed.

| Arm | Seed | Status | Logical candidates | Wall seconds | CPU seconds | Candidates/s |
| --- | --- | --- | --- | --- | --- | --- |
| BASE | 11 | complete | 1363 | 36.817 | 29.243 | 37.021 |
| BASE | 22 | complete | 1363 | 39.828 | 32.147 | 34.222 |
| BASE | 33 | complete | 1363 | 39.979 | 32.238 | 34.093 |
| BRUTE | 11 | complete | 12883 | 327.724 | 261.389 | 39.311 |
| BRUTE | 22 | complete | 12883 | 158.508 | 127.758 | 81.277 |
| BRUTE | 33 | complete | 12883 | 329.737 | 262.958 | 39.071 |
| ONESHOT | 11 | complete | 7133 | 794.330 | 634.790 | 8.980 |
| ONESHOT | 22 | complete | 7132 | 597.695 | 477.129 | 11.933 |
| ONESHOT | 33 | complete | 7182 | 271.764 | 218.979 | 26.427 |
| FULL | 11 | complete | 48833 | 4761.501 | 3796.283 | 10.256 |
| FULL | 22 | complete | 49435 | 4509.121 | 3581.207 | 10.963 |
| FULL | 33 | complete | 49248 | 4984.263 | 3980.097 | 9.881 |
| NO_LIBRARY | 11 | complete | 46565 | 2100.870 | 1687.440 | 22.165 |
| NO_LIBRARY | 22 | complete | 47023 | 4225.486 | 3369.909 | 11.128 |
| NO_LIBRARY | 33 | complete | 46908 | 2093.586 | 1679.813 | 22.406 |
| NO_RECOGNITION | 11 | complete | 46299 | 2589.362 | 2355.147 | 17.880 |
| NO_RECOGNITION | 22 | complete | 46395 | 2290.615 | 2062.815 | 20.254 |
| NO_RECOGNITION | 33 | complete | 46299 | 2256.682 | 2071.334 | 20.516 |
| NO_HEURISTIC | 11 | complete | 27845 | 596.251 | 475.246 | 46.700 |
| NO_HEURISTIC | 22 | complete | 27970 | 618.501 | 500.471 | 45.222 |
| NO_HEURISTIC | 33 | complete | 27951 | 307.096 | 245.925 | 91.017 |

| Arm | Summed worker wall seconds | Summed CPU seconds |
| --- | --- | --- |
| BASE | 116.624 | 93.628 |
| BRUTE | 815.968 | 652.105 |
| ONESHOT | 1663.789 | 1330.898 |
| FULL | 14254.885 | 11357.587 |
| NO_LIBRARY | 8419.942 | 6737.161 |
| NO_RECOGNITION | 7136.659 | 6489.296 |
| NO_HEURISTIC | 1521.848 | 1221.642 |

Controller elapsed wall time: 7431.434 s. Measured aggregate CPU: 27902.035 s (7.7506 CPU-hours); limit 24 CPU-hours. Workers: 5; NumPy threads per worker: 1.

## Where improvement stopped

Descriptive stopping point means the last generation reaching a strictly higher all-time best TEST solved count; it is g0 if no later generation exceeds g0. The flat suffix is the earliest generation in the final constant-valued suffix containing at least two observations. These descriptions did not stop or tune any run.

| FULL curve | Last new best | Final flat suffix begins |
| --- | --- | --- |
| 11 | g0 | g0 |
| 22 | g0 | g0 |
| 33 | g0 | g0 |
| Mean FULL | g0 | g0 |

Mean FULL TEST fractions: g0=0.1667, g1=0.1667, g2=0.1667, g3=0.1667, g4=0.1667, g5=0.1667, g6=0.1667, g7=0.1667, g8=0.1667.

## Learned library entries

All adopted entries are printed below, ordered within each run by MDL reduction. Their source generation is the generation when first adopted.

No learned library entries were adopted in the recorded runs.

## Every adopted heuristic

No heuristic was adopted in the recorded runs; the initial four-input constant-zero heuristic remained incumbent.

Every proposed heuristic, including duplicates and rejections, remains in its arm/seed JSON generation log. The final FULL JSON also contains the primitive-only comparison's proposal log.

## Predictions versus observations

| Generation | Arm | Preregistered mean | Observed mean | Observed − predicted |
| --- | --- | --- | --- | --- |
| 0 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 0 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 0 | ONESHOT | 0.1667 | 0.1667 | -0.0000 |
| 0 | FULL | 0.1667 | 0.1667 | -0.0000 |
| 1 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 1 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 1 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 1 | FULL | 0.0833 | 0.1667 | +0.0834 |
| 2 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 2 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 2 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 2 | FULL | 0.0833 | 0.1667 | +0.0834 |
| 3 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 3 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 3 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 3 | FULL | 0.1667 | 0.1667 | -0.0000 |
| 4 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 4 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 4 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 4 | FULL | 0.1667 | 0.1667 | -0.0000 |
| 5 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 5 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 5 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 5 | FULL | 0.1667 | 0.1667 | -0.0000 |
| 6 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 6 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 6 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 6 | FULL | 0.1667 | 0.1667 | -0.0000 |
| 7 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 7 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 7 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 7 | FULL | 0.1667 | 0.1667 | -0.0000 |
| 8 | BASE | 0.1667 | 0.1667 | -0.0000 |
| 8 | BRUTE | 0.2500 | 0.1667 | -0.0833 |
| 8 | ONESHOT | 0.0833 | 0.1667 | +0.0834 |
| 8 | FULL | 0.1667 | 0.1667 | -0.0000 |

Predictions were committed before final TEST measurement in [PREDICTIONS.md](PREDICTIONS.md). Reported prediction errors do not alter the frozen protocol.

## Scope and limits

This is the resource-scaled 60-task subset of 207 eligible external tasks, with eight learning generations, AST size at most 12 and expansion limit 20,000. Each selected task has ten distinct search examples and only one to five hidden examples. Named parameter variants of a routine can cross TRAIN/VALIDATION/TEST boundaries; this limits claims about generalization to new routine families. Hidden verification establishes agreement on those observed examples, not universal semantic equivalence. The original primitive set, evaluator and four-input heuristic interface remain frozen. No LLM is used by synthesis, learning or evaluation. Conclusions apply only to the measured tasks and configured search limits.

Configuration: [experiment_config.json](experiment_config.json). Corpus provenance and split: [DATASET.md](DATASET.md). One JSON per arm/seed run is retained in [results/](results/); execution_summary.json contains controller timing and completion status.
