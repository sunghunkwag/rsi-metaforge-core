# FRESH evaluation: measured results

The six registered arms' final learned solvers ran on FRESH-1 (33 single
routines) and FRESH-2 (100 two-stage pipelines), seeds 11/22/33, in
Actions run 41394848010 (branch `rsi3/run-fresh-registered`, plan
[`runs/fresh-registered.json`](runs/fresh-registered.json)). FRESH is the
partition frozen in commit 8267495 from DreamCoder's second list-task
file, which no split, run or design decision in RSI-2 or RSI-3 had used.
Predictions were registered in
[PREDICTIONS_FRESH.md](PREDICTIONS_FRESH.md) (commit c81f086) before any
FRESH task was run. Raw files are in [`results_fresh/`](results_fresh/)
(`<ARM>_seed11-22-33_fresh1.json`, `_fresh2.json`; the `tasks` field of
each seed records the candidates spent per action on every task).

**Headline.**

| Partition | Best arm | Every other arm |
| --- | --- | --- |
| FRESH-1, 33 new single routines | HONEST **7 of 33** on every seed | PORTFOLIO 5, BEH / BASE / FOLD 4, CONJ 1 |
| FRESH-2, 100 two-stage pipelines | BEH and BASE **13 of 100**, CONJ 12–13 | FOLD 10, HONEST 9, PORTFOLIO 8 |

The order reverses between the two partitions. Honest practice wins on
single routines with constants the corpus never used; the decomposition
arms win on pipelines, and the reason is one skeleton their policies
route to and the honest policy never tries (below). Six of seven
predictions hit; the miss is the pipeline comparison E7.

## How the runs were produced

The plan retrains each arm on its registered config with the three
seeds in one job (shared TRAIN trajectory, per-seed dreams and
recognition) and evaluates the final checkpoint, instead of loading the
registered checkpoints as [`reserve_eval`](reserve_eval.py) does. The
workflow ran at commit 81aba49 of the development branch, which carries
the analogy code of PREDICTIONS_ANALOGY.md; none of the six configs
enables it. The check the plan prescribes passed for all 18 arm/seed
pairs: the TRAIN trajectory, the VALIDATION and VALIDATION-agent
trajectories, the final solution set, the library size and the config
are identical to the registered files in `results_*/`. The arms
evaluated here are therefore the registered arms.

## Results

FRESH-1, solved of 33 (seeds 11 / 22 / 33), and the tasks, which are the
same on every seed:

| Arm | FRESH-1 | Tasks solved |
| --- | --- | --- |
| **RSI3_META_HONEST** | **7 / 7 / 7** | `add-k` (k = -2, 10), `mult-k` (k = -2, 10), `prepend-k (k=-2)`, `identify-is-mod-k (k=2)`, `identify-geq-k (k=7)` |
| RSI3_META_PORTFOLIO | 5 / 5 / 5 | `add-k (k=-2)`, `mult-k (k=-2)`, `prepend-k (k=-2)`, `identify-is-mod-k (k=2)`, `identify-k (k=-2)` |
| RSI3_META_BEH | 4 / 4 / 4 | `add-k (k=-2)`, `mult-k (k=-2)`, `prepend-k (k=-2)`, `identify-is-mod-k (k=2)` |
| RSI3_META_BEH_BASE | 4 / 4 / 4 | the same four |
| RSI3_META_BEH_FOLD | 4 / 4 / 4 | the same four |
| RSI3_META_CONJ | 1 / 1 / 1 | `prepend-k (k=-2)` |

None of the routines the corpus lacks (`intersperse-k`, `positions`,
`uniq`, `identify-is-prime`, `replace-index-k-with-n`, ...) was solved by
any arm.

FRESH-2, solved of 100 (seeds 11 / 22 / 33):

| Arm | FRESH-2 | Solved on every seed |
| --- | --- | --- |
| RSI3_META_BEH | **13 / 13 / 13** | 13 |
| RSI3_META_BEH_BASE | **13 / 13 / 13** | 13 |
| RSI3_META_CONJ | 12 / 12 / 13 | 12 |
| RSI3_META_BEH_FOLD | 10 / 10 / 10 | 10 |
| RSI3_META_HONEST | 9 / 9 / 9 | 9 |
| RSI3_META_PORTFOLIO | 8 / 8 / 8 | 8 |

Five pipelines are solved by every arm on every seed: `identify-k (-2)`
then `identify-geq-k (-7)`, `modulo-k (2)` then `identify-is-prime`,
`modulo-k (3)` then `identify-geq-k (5)`, `reverse` then `sum`, and
`append-k (-2)` then `head` (CONJ solves this one on seed 33 only). The
rest split by arm family:

- **BEH, BASE, FOLD and CONJ, not HONEST or PORTFOLIO:** `identify-geq-k (3)`
  then `empty`, `mult-k (10)` then `is-odds`, `pow-base-k (4)` then
  `is-evens`, `replace-all-k-with-n (3, -2)` then `is-odds`; BEH, BASE
  and CONJ also `identify-geq-k (2)` then `is-odds` and `slice-k-n (3, 3)`
  then `is-odds`; BASE and CONJ `slice-k-n (3, 3)` then `is-evens`.
- **HONEST, not CONJ:** `identify-geq-k (7)` then `modulo-k (4)` and
  `modulo-k (3)` then `modulo-k (6)` (also BEH, FOLD, PORTFOLIO), and,
  with PORTFOLIO, `replace-index-k-with-n (3, -2)` then `has-k`; HONEST
  alone `rotate-k (-2)` then `has-k (5)`.
- **One arm only:** BEH `take-k (3)` then `rotate-k (1)`; BASE
  `identify-geq-k (2)` then `is-evens`; CONJ `intersperse-k (0)` then
  `has-k (10)`; PORTFOLIO `drop-k (2)` then `is-odds`.

## Where the 64 candidates went

The per-task `spent` records (seed 11) explain both halves of the
headline.

- **FRESH-1.** HONEST's policy routes 852 of its 2,112 candidates to
  `behave:map`, which reads the constant off the data and solved six of
  its seven tasks (the seventh, `prepend-k`, by `decompose:prepend_of`,
  as in every arm). BEH, BASE and FOLD spend 500–550 candidates on each of
  `decompose:map`, `decompose:map_list` and `decompose:fold_nil` and only
  250–260 on `behave:map`; their three `map` solves come from the
  decomposition chunk. CONJ has no behavioural action and solves only the
  `prepend_of` task. PORTFOLIO's library-free `behave0:map` solved four.
  So the FRESH-1 gain is the one PREDICTIONS_FRESH.md gave as the reason
  for E1–E3: witness functions that compute the constant argument reach
  k = 10 and k = -2, which no corpus task uses.
- **FRESH-2.** Every pipeline the decomposition arms solve and HONEST
  does not ends in a list predicate (`is-odds`, `is-evens`, `empty`), and
  every one was found by `decompose:all` in 2–16 candidates after the
  same 48 candidates on `any_list`, `any` and `fold_false` that HONEST
  also spends. HONEST's policy spends its last 16 on `behave:any`
  instead; across the 100 tasks it never takes a `decompose:all` turn,
  and neither does PORTFOLIO. HONEST's own extra solves are `behave:map`
  on pipelines that collapse into one pointwise map (10 and 27
  candidates) and `behave:any` on `has-k` after a permutation or a
  replacement (12 candidates each), where the decomposition arms spend
  all 64 on `any`-shaped chunks.

This is the routing ceiling of RESERVE and RESERVE-FAR2 seen from the
other side: the honestly trained policy, credited only by actual
one-chunk outcomes on imagined tasks, has learned a preference order
that fits single routines and skips the `all` skeleton; the policies
trained with constructed credit keep `all` in their order and lose
`behave:map`.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| E1 HONEST FRESH-1 > CONJ FRESH-1 | PASS (moderate) | 7 vs 1 | hit |
| E2 HONEST FRESH-1 ≥ BASE FRESH-1 | PASS (moderate) | 7 vs 4 | hit |
| E3 HONEST FRESH-1 point forecast | 9 (range 5–14) | 7 | hit (inside the range; point 2 too high) |
| E4 PORTFOLIO FRESH-1 within 3 of HONEST | PASS (moderate) | 5 vs 7 | hit |
| E5 every arm ≤ 20 of 100 FRESH-2 | PASS | best 13 | hit |
| E6 HONEST FRESH-2 point forecast | 6 (range 2–12) | 9 | hit (inside the range; point 3 too low) |
| E7 HONEST FRESH-2 > CONJ FRESH-2 | PASS (low confidence) | 9 vs 12–13 | **miss** |

Six of seven hit. E7 was wrong in direction, not only in size: CONJ,
BEH and BASE all beat HONEST on pipelines, by 3–4 tasks, on every seed.
E3's reason named `add-k`, `mult-k` and `prepend-k` with k = -2 and 10
as the likely solves; five of HONEST's seven are those (the `prepend-k
(k=10)` variant was not solved), the other two are `identify-is-mod-k`
and `identify-geq-k`.

## What this adds

- **A clean transfer number for new routines.** On 33 routines never seen
  by any split, the honest-practice arm solves 7, every other arm 1–5,
  and all the solves are known routine shapes with new constants. No arm
  solves a routine the corpus lacks. This is the same picture as
  RESERVE-FAR2 (new families: HONEST and PORTFOLIO 5 of 21, others 1):
  small, repeatable, and bounded by what behavioural search can build in
  64 candidates.
- **Composition is not what the honest policy is good at.** On 100
  two-stage pipelines the ranking inverts, and the difference is a single
  action's routing. Nothing here shows a learned ability to compose two
  routines: every solved pipeline collapses into one chunk (a map, an
  `all`, an `any`, a fold).
- **Exposure.** FRESH is now read. The practice-only analogy and chain
  actions of PREDICTIONS_ANALOGY.md were registered before this file was
  written and their FRESH results will be scored as registered; any
  design made after today must treat FRESH as exposed, as RESERVE is.
- **Scale.** 36 TRAIN tasks, 64 candidates per task, three seeds that
  share one TRAIN trajectory. No claim about superintelligence, the
  singularity or consciousness.
