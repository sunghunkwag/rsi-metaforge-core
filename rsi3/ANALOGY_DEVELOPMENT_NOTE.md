# Analogy, chain, composition practice, self-curriculum: development runs

Development only. Every run here is TRAIN-only at seed 44 (`--skip-validation`,
so VALIDATION was never loaded), with the final solver evaluated on
partitions that are **exposed**: RESERVE-NEAR, RESERVE-FAR2 and COMPOSE-24
have all been read before, and designs were made afterwards. Nothing here
is a result. No FRESH task was run or read. TRAIN is seed-independent for
every arm here (the wake never reads the recognition model), so a seed-44
trajectory is the trajectory. All runs were made on GitHub Actions
(`.github/workflows/rsi3-runs.yml`; the plans are in `rsi3/runs/`), and the
raw artifacts are the workflow runs named below.

Comparator throughout: RSI3_META_HONEST (registered), TRAIN
10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29, RESERVE-NEAR 56–57,
RESERVE-FAR2 5, COMPOSE-24 0 (PR #45), CPU about 4,370 s per run.

## 1. Analogical repair, capped (`rsi3/run-analogy-dev2`, run 41370701229)

RSI3_META_ANALOGY = HONEST plus one meta-RL action, `analogy`
(`analogy.py`): edits of the system's verified programs, best first by
conditional description length, with at most 32 candidates per task per
ranked source set (`analogy.max_evaluations`). The action is offered in
the TRAIN wake, practised honestly on imagined tasks, and offered at
held-out time.

| | TRAIN g1–g16 | TRAIN g16 | NEAR | CPU s |
| --- | --- | --- | --- | --- |
| HONEST (registered) | 10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29 | 29 | 56–57 | ~4,370 |
| ANALOGY (cap 32) | 10 14 18 22 24 24 25 25 25 25 25 25 25 26 28 29 | 29 | **62** | 7,127 |

- **TRAIN.** The same 29 tasks as HONEST. One TRAIN solve came from the
  action itself: `index-k (k=5)` at generation 3, edited from the verified
  `index-k (k=3)` (`replace[0, 0]`, the constant becomes a hole). The
  reverse → append cascade arrives two generations later than in HONEST
  (reverse g14, appends g15, append-index g16). Without the cap (an earlier
  development run) the action took wake budget from the fold action and
  the cascade did not arrive at all: TRAIN 25. The cap is what makes the
  action affordable.
- **RESERVE-NEAR, 62 against 57.** Eleven tasks HONEST's solver misses were
  solved, ten of them by analogy edits of verified programs:
  `append-index-k` k=3 and k=5 (from `append-index-k k=1`), `append-k k=3`
  (from `append-k k=1`), `is-mod-k` k=1, 3, 4 (from `has-k k=3` and
  `is-mod-k k=5`), `slice-k-n` (1,2) and (2,2) (from the n=4 slices), plus
  `slice-k-n (1,3)`, `(2,1)`, `(3,1)` and `replace-all-with-index-k k=2`
  through other actions. The append family, which no registered solver
  had ever solved held-out (conjugate skeletons are not offered at
  held-out time), is reached by editing the TRAIN appends. Six tasks
  HONEST's solver solves were lost: `has-k` k=1, 4, 5,
  `bool-identify-geq-k k=4`, `index-k k=2`, `slice-k-n (4,1)`; on those the
  analogy chunk took the budget that `behave:any` or `behave:whole` needed.
- **Cost.** CPU 7,127 s against about 4,370 s: ranking sources and
  enumerating edit holes is interpreter time that the candidate count does
  not show.
- **What this is.** The first mechanism in the project that reuses the
  system's own verified output to solve held-out tasks it could not solve
  before. It is a development signal on an exposed partition.

## 2. Chain and both actions in the TRAIN wake (`rsi3/run-compose-dev1`, run 41371699498)

RSI3_META_CHAIN = HONEST plus `chain` (`chain.py`: one of the system's own
list programs first, the residual by behavioural search; `max_stages` 3,
`max_evaluations` 48). RSI3_META_COMPOSE = HONEST plus `analogy` and
`chain`. Both actions were offered in the TRAIN wake, each with the
ordinary 16-candidate chunk.

| | TRAIN g1–g16 | TRAIN g16 | NEAR | COMPOSE-24 | CPU s |
| --- | --- | --- | --- | --- | --- |
| CHAIN | 10 13 14 15 21 24 24 24 24 25 25 25 25 25 25 26 | 26 | 55 | 0 | 5,156 |
| COMPOSE | 10 13 14 15 18 23 24 24 24 25 25 25 25 25 25 25 | 25 | 47 | 0 | 4,959 |

- **Both lost the cascade.** CHAIN lacks `append-k` ×2 and
  `append-index-k`; COMPOSE lacks those and `reverse`. In generations 1–8
  the chain action took 21, 38, 17, 16, 22 and 10 chunks (256–559
  candidates a generation); the fold action that finds reverse was
  starved, and reverse arrived at generation 16 (CHAIN) or not at all
  (COMPOSE). This is the budget-theft failure mode again, now from an
  action that rarely pays on TRAIN (no TRAIN task is a two-stage
  composition the system's own programs can start).
- **COMPOSE-24: 0 of 24 for both.** On every task the solver spent exactly
  one 16-candidate chunk on each of four actions (`decompose:fold_nil`,
  `chain`, `prior`, `behave:whole` or `analogy`). Chain spends its first
  8 units ranking stages; with 16 it never reaches a residual program.
  Alone, on HONEST's final state with 32 candidates, the same search
  solves 8 of 24 (`tail^k` then `map (add 1)`, `tail^k` then reverse).
- **NEAR.** 55 and 47 against 57: the lost cascade removes the TRAIN
  appends the analogy action would edit from, and chain chunks displace
  the behavioural actions.

Decision from this run: the new actions must not take TRAIN wake budget
(`wake_new_actions = False`: trained by honest practice on imagined tasks
only, offered at held-out time), chain needs a window of its own
(`meta.windows.chain = 32`, `chain.max_stages = 1`), and the policy must
see compositions in practice (`meta.compose_selfplay`). Those are runs
3–5 below.

## 3. Practice-only new actions with windows (`rsi3/run-compose-dev2`)

_Pending: RSI3_META_ANALOGY_P, RSI3_META_CHAIN, RSI3_META_COMPOSE with
`wake_new_actions = False`, `meta.windows.chain = 32`,
`chain.max_stages = 1`._

## 4. Composition practice (`rsi3/run-compose-dev3`)

_Pending: RSI3_META_CHAIN, RSI3_META_COMPOSE as in run 3, plus
`meta.compose_selfplay = 96`._

## 5. Self-curriculum (`rsi3/run-curriculum-dev1`)

_Pending: RSI3_META_CURRICULUM (`curriculum.py`), NEAR, FAR2, COMPOSE-24._

## 6. Budget diagnostic: HONEST at 256 candidates (`rsi3/run-honest-b256`)

_Pending: B_wake = B_eval = 256._

## Scale

36 TRAIN tasks, 64 candidates per task per generation (256 in run 6), one
seed. No claim about recursive self-improvement, superintelligence or the
singularity.
