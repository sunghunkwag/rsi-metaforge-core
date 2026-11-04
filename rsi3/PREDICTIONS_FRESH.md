# FRESH evaluation of the six registered arms: pre-registered predictions

Registered 2026-10-30. No solver had run any FRESH task, and no FRESH
example had been read. Misses will be scored in FRESH_RESULTS.md and will
not be reinterpreted.

## Why

Every partition inside RSI-2's corpus has now been run and its results
read: VALIDATION, RESERVE-NEAR, RESERVE-FAR and RESERVE-FAR2. A design
made after reading them is not tested cleanly on them. FRESH
(`rsi3/fresh.py`, frozen in commit 8267495) takes its tasks from a
different file, DreamCoder's `data/list_tasks2.json`:

- **FRESH-1**: 33 single routines whose corpus-style name is not in
  RSI-2's corpus. Most use parameters the corpus never does (-2, 10).
  The rest are routines the corpus lacks (`intersperse-k`, `positions`,
  `uniq`, `identify-is-prime`, `replace-index-k-with-n`, ...).
- **FRESH-2**: 100 two-stage pipelines drawn with a fixed seed. No arm
  was ever trained on a composition of routines.

Each task has 8 public examples, against 10 in the corpus; the rest
(1 or 2) are hidden.

**Exposure, in full.**

- **Names.** The 33 FRESH-1 names were printed once, when the partition
  was built. Fifteen random names from the 174,258-task source file were
  printed while exploring it, before FRESH-2 was drawn. None of these
  showed an outcome.
- **Analogical repair.** The design (`analogy.py`) was developed after
  FRESH was frozen. It was tuned on TRAIN (leave-one-out) and on
  RESERVE-NEAR, which is exposed. Its own predictions are registered
  separately (PREDICTIONS_ANALOGY.md), before any FRESH result is read.

## The measurement

- **Command.** `python -m rsi3.reserve_eval --partition fresh1` (and
  `fresh2`) runs each registered arm's final learned solver from its
  registered checkpoint: `longrun.agent_validation`, B_eval = 64, one
  verifier query per task, seeds 11/22/33. These are the six arms and
  checkpoints of RESERVE_RESULTS.md.
- **Code.** Branch `rsi3/fresh` at 8267495, which holds no analogy code.

## Predictions (solved, every seed)

| ID | Comparison or readout | Predicted |
| --- | --- | --- |
| E1 | HONEST FRESH-1 > CONJ FRESH-1 | PASS (moderate) |
| E2 | HONEST FRESH-1 ≥ BASE FRESH-1 | PASS (moderate) |
| E3 | HONEST FRESH-1, point forecast | 9 of 33 (range 5–14) |
| E4 | PORTFOLIO FRESH-1 within 3 of HONEST FRESH-1 | PASS (moderate) |
| E5 | every arm solves at most 20 of 100 FRESH-2 | PASS |
| E6 | HONEST FRESH-2, point forecast | 6 of 100 (range 2–12) |
| E7 | HONEST FRESH-2 > CONJ FRESH-2 | PASS (low confidence) |

## Reasons

- **E1 and E3.** The FRESH-1 tasks HONEST is likely to solve are `add-k`,
  `mult-k` and `prepend-k` with k = -2 and 10. Behavioural search reaches
  them, because its witness functions read constants off the data
  (`map`, cons deduction). CONJ has no behavioural search.
  - Unlikely: `append-k` and `rotate-k` (no conjugation at held-out
    time), and the new routines.
- **E5.** Two routines composed are usually beyond 64 candidates.
  - Likely solved: pipelines that collapse into one pointwise map
    (`add-k` after `mult-k`) or one filter.

No claim about superintelligence, the singularity or consciousness.
