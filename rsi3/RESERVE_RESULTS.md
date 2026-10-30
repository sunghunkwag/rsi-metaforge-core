# RESERVE evaluation: measured results

Every arm's final learned solver ran on the two RESERVE partitions
(`rsi3/reserve.py`), seeds 11/22/33, with `python -m rsi3.reserve_eval`.
That is `longrun.agent_validation` at B_eval = 64 per task, one verifier
query per task, from each arm's registered final checkpoint. Predictions
were registered in commit 1e7fa35, before any reserve task was run. Raw
files are in [`results_reserve/`](results_reserve/), including the
harness check: it reproduces RSI3_META_HONEST's recorded final VALIDATION
exactly on every seed, the same tasks with the same per-action spending.

RESERVE consists of eligible tasks of RSI-2's corpus that no split, no run
and no design decision had used. TEST stays sealed.

**Headline.** On the 100 RESERVE-NEAR tasks, the honest self-play arm's
solver solved **56–57**, against 39–52 for every other arm, on every seed.
Its VALIDATION lead was not manufactured by the design's exposure to
VALIDATION; the ranking holds on tasks nothing had seen. Transfer to new
families (RESERVE-FAR, 12 tasks) stays at 2–4 for every arm, and there
HONEST is lowest.

## Results (solved, seeds 11 / 22 / 33)

| Arm | TRAIN | VALIDATION agent (/12) | **RESERVE-NEAR (/100)** | RESERVE-FAR (/12) |
| --- | --- | --- | --- | --- |
| RSI3_META_CONJ | 21 | 5 / 5 / 5 | 39 / 40 / 40 | 3 / 3 / 3 |
| RSI3_META_BEH_FOLD | 29 | 5 / 5 / 5 | 42 / 42 / 42 | 3 / 3 / 3 |
| RSI3_META_BEH | 25 | 4 / 4 / 4 | 43 / 43 / 43 | 3 / 3 / 3 |
| RSI3_META_BEH_BASE | 21 | 7 / 7 / 7 | 44 / 44 / 44 | 3 / 3 / 3 |
| RSI3_META_PORTFOLIO | 29 | 8 / 8 / 8 | 52 / 51 / 51 | 3 / 3 / 4 |
| **RSI3_META_HONEST** | **29** | **9 / 9 / 9** | **57 / 56 / 56** | 2 / 2 / 2 |

The top three on RESERVE-NEAR are in VALIDATION's order: HONEST, then
PORTFOLIO, then BASE. The bottom three (BEH, FOLD, CONJ) are within four
tasks of one another, in a different order from VALIDATION's (4, 5 and
5). Across all six arms together, 60 of the 100 tasks were solved by some
arm (seed 11).

RESERVE-NEAR by family, seed 11:

| Family (tasks) | HONEST | PORTFOLIO | BASE | BEH | FOLD | CONJ |
| --- | --- | --- | --- | --- | --- | --- |
| caesar-cipher (14) | **14** | 10 | 10 | 6 | 6 | 6 |
| has-k (4) | **4** | 2 | 1 | 1 | 1 | 3 |
| slice-k-n (16) | 2 | **3** | 0 | 0 | 0 | 0 |
| bool-identify-geq-k (5) | 4 | 4 | 4 | 2 | 3 | 3 |
| index-k (3) | 3 | 3 | 2 | 3 | 1 | 1 |
| modulo-k (3) | 3 | 2 | 1 | 3 | 3 | 1 |
| mult-k (5) | 5 | 5 | 3 | 5 | 5 | 5 |
| add-k (5), bool-identify-k (5), prepend-k (2) | all | all | all | all | all | all |
| append-k (4), append-index-k (3), rotate-k (4), kth-largest (2), kth-smallest (2) | 0 | 0 | 0 | 0 | 0 | 0 |

The seven other families (`bool-identify-is-mod-k`, `is-mod-k`,
`keep-mod-k`, `pow-k`, `prepend-index-k`, `repeat-k`,
`replace-all-with-index-k`) differ by at most one task between arms.

- **Where HONEST's lead comes from.** Most of it is the caesar family (14
  of 14) and has-k (4 of 4), the same mechanism traced in
  HONEST_RESULTS.md: `behave:map` and `behave:any` keep their turn under
  the honestly trained policy.
- **The append family is solved by no arm, including those that solve
  appends on TRAIN.** On TRAIN, appends come from conjugation by the
  system's own reverse. The held-out solver (`agent_validation`) offers
  the prior, the skeletons and behavioural search, but not conjugate
  skeletons or the generation's invented concepts. That is a limit of the
  registered measure, stated here and not changed after the fact.
- **RESERVE-FAR.**
  - HONEST solved `head` and `last`.
  - CONJ, FOLD, BEH and BASE also solved `empty`.
  - PORTFOLIO solved `evens`, `odds` and `last`, plus `head` on seed 33.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| Q1 HONEST NEAR > FOLD NEAR | PASS | 57 / 56 / 56 vs 42 | hit |
| Q2 HONEST NEAR > CONJ NEAR | PASS | vs 39 / 40 / 40 | hit |
| Q3 HONEST NEAR > BASE NEAR | PASS (moderate) | vs 44 | hit |
| Q4 HONEST NEAR > BEH NEAR | PASS | vs 43 | hit |
| Q5 BASE NEAR > BEH NEAR | PASS (moderate) | 44 vs 43 | hit (by one task) |
| Q6 PORTFOLIO NEAR > HONEST NEAR | FAIL (low confidence) | 52 / 51 / 51 vs 57 / 56 / 56 | hit |
| Q7 HONEST NEAR point | 60 (45–75) | 56–57 | hit |
| Q8 HONEST FAR point | 3 (1–6) | 2 | hit |
| Q9 HONEST FAR > CONJ FAR | PASS (low confidence) | 2 vs 3 | **miss** |

Eight of nine hit.

## What this establishes, and what it does not

- **Established: clean held-out evidence.** This is the first held-out
  evidence in the project on tasks that no design decision has seen. The
  honestly trained meta-policy, with behavioural search built from the
  system's own library, transfers to unseen parameter variants of known
  routines better than every other arm: about 56% against 39–52%, on
  every seed.
- **Not established: transfer to new routines.** On unseen families,
  every arm solves 2–4 of 12, mostly the trivial `head`, `last` and
  `empty`. The system generalizes within the families it trained on, not
  beyond them.
- **Scale.** 36 TRAIN tasks; 100 + 12 reserve tasks. No claim about
  superintelligence, the singularity or consciousness.
