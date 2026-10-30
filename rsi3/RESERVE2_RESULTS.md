# RESERVE-FAR2 evaluation: measured results

The six registered arms' final learned solvers ran on RESERVE-FAR2, seeds
11/22/33, with `python -m rsi3.reserve_eval --partition far2`. That
partition holds 21 tasks in 5 families that no split, run or design
decision had used. Predictions were registered in commit 0f9596a, before
any of these tasks was run. Raw files are in
[`results_reserve/`](results_reserve/) (`*_far2.json`).

**Headline.**

| Arms | FAR2 solved (every seed) | What they solved |
| --- | --- | --- |
| HONEST, PORTFOLIO | **5 of 21** | the identity, plus real tasks of new families |
| CONJ, FOLD, BEH, BASE | 1 of 21 | only the identity, `drop-k (k=0)` |

This is a modest but clean gain in transfer to new families. RESERVE-FAR
(12 tasks) had shown none: there every arm scored 2–4.

## Results (solved of 21, seeds 11 / 22 / 33)

| Arm | FAR2 | Tasks solved (seed 11) |
| --- | --- | --- |
| **RSI3_META_HONEST** | **5 / 5 / 5** | `drop-k` (k = 0, 1, 3, 4), `take-k (k=1)` |
| **RSI3_META_PORTFOLIO** | **5 / 5 / 5** | `drop-k` (k = 0, 1), `remove-mod-k (k=2)`, `take-k` (k = 1, 2) |
| RSI3_META_BEH_BASE | 1 / 1 / 1 | `drop-k (k=0)` |
| RSI3_META_BEH | 1 / 1 / 1 | `drop-k (k=0)` |
| RSI3_META_BEH_FOLD | 1 / 1 / 1 | `drop-k (k=0)` |
| RSI3_META_CONJ | 1 / 1 / 1 | `drop-k (k=0)` |

How HONEST's solver spent its 64 candidates, seed 11:

- **Solved:**
  - `drop-k` (k = 1, 3, 4): two skeleton chunks, then `behave:whole` in 14–15
    candidates, finding `tail^k` with the system's own power concepts;
  - `take-k (k=1)`: `behave:whole` in 11.
- **Not reached:**
  - `drop-k (k=5)`: `behave:whole` got 16 candidates, not enough.
  - `remove-mod-k`: all 64 went to the `filter` and `filter_list` skeletons.
    `behave:filter`, whose witness solves this shape on TRAIN, got no turn.
  - `count-k`: all 64 went to the fold skeleton.
  - `take-k` (k ≥ 2) and `remove-index-k`: the budget went to `filter_list`
    and `fold_nil` before cons deduction got its turn.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| S1 HONEST FAR2 > CONJ FAR2 | PASS | 5 vs 1 | hit |
| S2 HONEST FAR2 > FOLD FAR2 | PASS (moderate) | 5 vs 1 | hit |
| S3 HONEST FAR2 ≥ BASE FAR2 | PASS (moderate) | 5 vs 1 | hit |
| S4 HONEST point forecast | 9 (range 5–13) | 5 | hit (at the range's lower edge) |
| S5 some arm ≥ 11 of 21 | FAIL (low confidence) | best 5 | hit |

Five of five hit. S4's point forecast was too high. I expected most of
`remove-mod-k` and all of `drop-k`, and the routing denied both.

## What this adds

- **New-family transfer.** Across both clean new-family tests, 33 tasks in
  all, the two arms with honest practice solve 7–9 tasks against 4 for
  every other arm. That counts FAR and FAR2 together: HONEST 2 + 5,
  PORTFOLIO 3–4 + 5, the rest 3 + 1. The gain comes from behavioural
  search built from self-acquired concepts (`tail^k`), routed by the
  honestly trained policy. It is small.
- **The ceiling.** The failures above share one cause, also seen on
  VALIDATION and RESERVE-NEAR. On new shapes the policy, trained on TRAIN
  and imagined tasks, spends the 64 candidates on skeleton chunks before
  the action that fits.
- **Scale.** No claim about superintelligence, the singularity or
  consciousness.
