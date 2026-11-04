# Practice-only analogy and chain actions at held-out time: measured results

The registered run `rsi3/run-analogy-registered` (Actions run 41394850706,
plan [`runs/analogy-registered.json`](runs/analogy-registered.json), code
at 81aba49) retrained RSI3_META_HONEST, RSI3_META_ANALOGY_P and
RSI3_META_COMPOSE for 16 generations with seeds 11/22/33 in one job per
arm and evaluated each final checkpoint on FRESH-1, FRESH-2 (never run
before by any arm), RESERVE-NEAR, RESERVE-FAR2 and COMPOSE-24 (exposed,
reported). Predictions were registered in
[PREDICTIONS_ANALOGY.md](PREDICTIONS_ANALOGY.md) before the run was
launched. Raw files are in [`results_analogy/`](results_analogy/) (per
arm: `<ARM>_seed<seed>.json` TRAIN runs and `<ARM>_seed11-22-33_<partition>.json`
evaluations; each task record carries the candidates spent per action
and, for the new actions, the source program the solve came from).

**Headline.**

| Arm | TRAIN (of 36) | FRESH-1 (of 33) | FRESH-2 (of 100) | NEAR (of 100) | FAR2 (of 21) | COMPOSE-24 (of 24) | TRAIN CPU (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RSI3_META_HONEST | 29 | 7 | 9 | 57 / 56 / 56 | 5 | 0 | 3533–3545 |
| RSI3_META_ANALOGY_P | 29 | 7 | **14** | **61** | **6** | 2 | 5327–5337 |
| RSI3_META_COMPOSE | 29 | 7 | **14** | 60 | **6** | **9** | 7454–7469 |

Every number is the same on all three seeds except HONEST's NEAR (one
task, `index-k (k=2)`, on seed 11 only). The analogy action gains five
FRESH-2 pipelines, four NEAR tasks and one FAR2 task net, and nothing on
FRESH-1; the chain action gains seven COMPOSE-24 tasks, the suite it was
tuned on, and nothing anywhere else. Nine of ten predictions hit; A10
(CPU within 2x) missed.

## How the runs were produced

The three arms share HONEST's TRAIN code path (the new actions take no
TRAIN wake budget) and their TRAIN trajectories, final solution sets and
libraries are identical to each other and to the registered HONEST files
in `results_honest/` (A1). The retrained HONEST's FRESH-1 and FRESH-2
solved sets are identical to those of the FRESH study
(FRESH_RESULTS.md), run from the same code path five hours earlier.

Two defects of `chain.py` were reported by the Codex session on PR #47
after this run had started (comment of 2026-11-02 09:45 UTC) and are
confirmed on reading: the composed program is returned without being
re-evaluated on the public examples at the search's step budget, and a
residual slice is not clamped to the remaining evaluation cap. Neither
can produce a false solve here: "solved" is the verifier's acceptance of
the returned program on the hidden examples under the evaluator's step
budget, so an over-budget composition fails that check. The first can
only lose solves (the search stops on a program that then fails); the
second could let a task spend more than 64 candidates. The per-task
`spent` records show a maximum of 64 for every task of ANALOGY_P and
COMPOSE on every partition and seed, so the cap was not exceeded in this
run; HONEST's own actions spend 65 on one NEAR task (`index-k (k=2)`),
a one-candidate overshoot that predates the new code. The fixes go on
the development branch with tests; these registered artifacts are not
rerun.

## Results

Solved of N, seeds 11 / 22 / 33, and the tasks that differ from HONEST
(the same on every seed unless marked).

- **FRESH-1 (33).** 7 / 7 / 7 in every arm, the same seven tasks
  (`add-k` and `mult-k` with k = -2 and 10, `prepend-k (k=-2)`,
  `identify-is-mod-k (k=2)`, `identify-geq-k (k=7)`). The analogy action
  spends 256 (ANALOGY_P) or 224 (COMPOSE) of the 2,112 candidates and
  finds nothing; the chain action spends 384 and finds nothing.
- **FRESH-2 (100).** HONEST 9, ANALOGY_P 14, COMPOSE 14. ANALOGY_P gains
  seven pipelines, every one by an `analogy` edit of one of two verified
  TRAIN programs, `is-mod-k (k=5)` and `index-k (k=5)`: `add-k (-2)` then
  `is-squares`, `identify-geq-k (3)` then `empty`, `identify-k (10)` then
  `len`, `mult-k (10)` then `is-odds`, `prepend-k (-2)` then `is-mod-k (-2)`,
  `replace-all-k-with-n` then `is-odds`, `rotate-k (10)` then `is-squares`,
  in 1–14 candidates each. It loses two that HONEST solves with
  `behave:any` (`replace-index-k-with-n` then `has-k`, `rotate-k (-2)`
  then `has-k (5)`): on those tasks the analogy action's 16 candidates
  take the slot `behave:any` had. COMPOSE solves exactly ANALOGY_P's
  fourteen; the chain action adds no FRESH-2 pipeline.
- **RESERVE-NEAR (100).** HONEST 57 / 56 / 56, ANALOGY_P 61, COMPOSE 60.
  ANALOGY_P gains ten (`append-k` k = 0, 2, 3 and `append-index-k (k=5)`
  from the corpus's own append programs, `is-mod-k` k = 2, 3, 4 from
  `is-mod-k (k=5)`, `slice-k-n` (1, 2), (2, 1), (2, 2) from other slices)
  and loses six (`has-k` k = 1, 4, 5, `index-k (k=2)`, `slice-k-n` (1, 1)
  and (4, 1)), again where the analogy's turn displaces `behave:any` or
  `behave:whole`. COMPOSE loses `append-index-k (k=5)` to the chain's
  turn.
- **RESERVE-FAR2 (21).** HONEST 5, ANALOGY_P and COMPOSE 6: `drop-k (k=5)`
  and `take-k (k=4)` by analogy from `prepend-index-k (k=2)` and
  `slice-k-n (1, 4)`, `take-k (k=1)` lost.
- **COMPOSE-24 (24).** HONEST 0, ANALOGY_P 2, COMPOSE 9. The chain solves
  `trim-and-increment` p1–p4 (first stage `tail` or a self-invented
  `tail^k` concept, residual `map`) and `reverse-dropped-suffix` p1–p3
  (the same first stages, residual `whole`), in 28–30 candidates each;
  the analogy solves `append-reversed-prefix` p1 and
  `reverse-dropped-suffix` p4 from the corpus's `append-index-k (k=1)`
  and `reverse`. The `filter-nondivisible-and-shift` family and the
  harder p5–p6 instances are solved by nothing.
- **CPU.** TRAIN CPU per job: HONEST 3,533–3,545 s, ANALOGY_P
  5,327–5,337 s (1.51x), COMPOSE 7,454–7,469 s (2.11x). The held-out
  evaluations: HONEST 101 s, ANALOGY_P 296 s, COMPOSE 345 s.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| A1 TRAIN trajectories equal HONEST's registered one | PASS (high) | identical, all arms and seeds | hit |
| A2 ANALOGY_P NEAR > HONEST NEAR, every seed | PASS (moderate; exposed) | 61 vs 57 / 56 / 56 | hit |
| A3 COMPOSE COMPOSE-24 ≥ 8 and HONEST = 0, every seed | PASS (moderate; exposed) | 9 and 0 | hit |
| A4 FRESH-1 \|ANALOGY_P − HONEST\| ≤ 1, every seed | PASS (moderate) | 7 vs 7 | hit |
| A5 ANALOGY_P FRESH-1 point forecast | 9 (range 5–14) | 7 | hit (inside the range; point 2 too high) |
| A6 FRESH-2 COMPOSE > HONEST, every seed | PASS (moderate) | 14 vs 9 | hit, by the analogy action: the chain adds nothing on FRESH-2 |
| A7 COMPOSE FRESH-2 point forecast | 10 (range 4–18); HONEST 6 (2–12) | 14; 9 | hit (both inside their ranges; both points too low) |
| A8 COMPOSE NEAR > HONEST NEAR, every seed | PASS (low confidence) | 60 vs 57 / 56 / 56 | hit |
| A9 every arm ≤ 20 of 100 FRESH-2 | PASS | best 14 | hit |
| A10 COMPOSE CPU ≤ 2 × HONEST CPU for the same job | PASS (moderate) | 2.11x on TRAIN, 2.15x with the evaluations | **miss** |

Nine of ten hit. A6 passed for a reason other than the one registered:
the reasons named the chain's first stages (`tail^k`, reverse, the
appends) as the route to FRESH-2 pipelines, and the chain solved none;
the gain is the analogy action's edits of two predicate programs. A10
missed by a tenth: the chain's residual searches cost interpreter time
the candidate count does not show, as the reasons said, but more of it.

## What this adds

- **The analogy action is a k-variant generator.** Every held-out gain
  it produced is a verified corpus program with one constant replaced,
  found in a handful of candidates: `is-mod-k` for `is-mod-k`,
  `is-odds`, `is-squares` and `empty` endings; the appends and slices for
  their neighbours; `prepend-index-k` and `slice-k-n` for `drop-k` and
  `take-k`. On FRESH-1, whose routines are new or whose constants are
  outside the grammar's, it found nothing, as A4 and A5 predicted. By the
  registered interpretation rule (A2 and A4 pass): the action's held-out
  gains are confined to parameter variants of the corpus's own families;
  it is not a route to new routines.
- **Its cost is a slot.** Each gain displaces one 16-candidate turn of a
  behavioural action; the tasks HONEST solved by `behave:any` on the
  `has-k` shape are lost in both new arms. Net: +5 of 100 on FRESH-2, +4
  of 100 on NEAR, +1 of 21 on FAR2.
- **The chain action does not transfer.** It solves seven of the 24
  compositions it was tuned on (the two families whose first stage is a
  `tail` the system holds) and nothing on FRESH-2's 100 random pipelines,
  at 2.1x the CPU. The registered rule for a failed A6 does not apply
  because A6 passed, but the finding it describes is what the data show
  for the chain: one-stage composition of the system's own programs did
  not transfer beyond the suite it was tuned on.
- **Exposure.** FRESH is now read by three more arms. NEAR, FAR2 and
  COMPOSE-24 were exposed before this study.
- **Scale.** 36 TRAIN tasks, 64 candidates per task, three seeds of one
  TRAIN trajectory per arm. No claim about recursive self-improvement,
  superintelligence or the singularity.
