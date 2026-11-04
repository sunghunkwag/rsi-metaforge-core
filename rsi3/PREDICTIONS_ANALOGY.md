# Practice-only analogy and chain actions at held-out time: pre-registered predictions

Registered 2026-11-02, before the runs `rsi3/run-analogy-registered`
(plan `rsi3/runs/analogy-registered.json`) were launched. Misses will be
scored in ANALOGY_RESULTS.md and not reinterpreted.

## What is measured

Three arms, each retrained for 16 generations at B_wake = B_eval = 64 with
seeds 11/22/33 in one job (one TRAIN trajectory, per-seed dreams and
recognition; VALIDATION measured every generation for reporting only):

- **RSI3_META_HONEST**, the registered comparator (`experiment_config_honest.json`).
- **RSI3_META_ANALOGY_P**: HONEST plus the `analogy` action (`analogy.py`,
  edits of the system's own verified programs, at most 32 candidates per
  task per ranked source set), trained by honest practice on imagined
  tasks only and offered at held-out time; it takes no TRAIN wake budget
  (`wake_new_actions = False`).
- **RSI3_META_COMPOSE**: ANALOGY_P plus the `chain` action (`chain.py`,
  one of the system's own list programs as a first stage, the residual by
  behavioural search; one stage, a 32-candidate window of its own).

Both new arms use `experiment_config_analogy.json`. Each final checkpoint
is evaluated with `rsi3.reserve_eval` (one verifier query per task,
B_eval = 64) on:

- **FRESH-1** (33 tasks) and **FRESH-2** (100 two-stage pipelines),
  frozen in commit 8267495 and never run by any solver (PREDICTIONS_FRESH.md).
- **RESERVE-NEAR** (100), **RESERVE-FAR2** (21) and **COMPOSE-24** (24),
  all exposed; reported, not the measure.

TEST is not opened. Nothing reads a FRESH example before the run.

## Exposure, in full

- `analogy.py` and `chain.py` were designed and tuned on TRAIN
  (leave-one-out) and on RESERVE-NEAR and COMPOSE-24, both exposed.
- The practice-only configuration (the actions out of the TRAIN wake, the
  chain window and single stage) was chosen after reading development
  runs 1–4 on NEAR and COMPOSE-24 (ANALOGY_DEVELOPMENT_NOTE.md): at seed 44,
  ANALOGY_P NEAR 61 against HONEST 56–57; COMPOSE NEAR 60 and COMPOSE-24
  9 of 24 against 0. Those numbers are the reason for this study and are
  not evidence for it.
- The self-curriculum arm of development run 5 is not registered (TRAIN
  25, NEAR 40).
- No FRESH task has been run or read by any arm here or by any other
  solver. The 33 FRESH-1 names were printed once when the partition was
  built (PREDICTIONS_FRESH.md).

## Predictions

"Every seed" means seeds 11, 22 and 33 of the same job.

| ID | Comparison or readout | Predicted |
| --- | --- | --- |
| A1 | TRAIN trajectory of ANALOGY_P and of COMPOSE equals HONEST's registered trajectory (10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29) | PASS (high) |
| A2 | ANALOGY_P NEAR > HONEST NEAR, every seed | PASS (moderate; exposed) |
| A3 | COMPOSE COMPOSE-24 ≥ 8 and HONEST COMPOSE-24 = 0, every seed | PASS (moderate; exposed) |
| A4 | FRESH-1: \|ANALOGY_P − HONEST\| ≤ 1, every seed (no gain from edits on new routines or new constants) | PASS (moderate) |
| A5 | ANALOGY_P FRESH-1, point forecast | 9 of 33 (range 5–14), the same as HONEST's |
| A6 | FRESH-2: COMPOSE > HONEST, every seed | PASS (moderate) |
| A7 | COMPOSE FRESH-2, point forecast | 10 of 100 (range 4–18); HONEST 6 (2–12, as registered) |
| A8 | COMPOSE NEAR > HONEST NEAR, every seed | PASS (low confidence) |
| A9 | Every arm solves at most 20 of 100 FRESH-2 | PASS |
| A10 | COMPOSE CPU ≤ 2 × HONEST CPU for the same job | PASS (moderate) |

## Reasons

- **A1.** With the new actions out of the TRAIN wake the wake is HONEST's
  code path; development run 3 reproduced HONEST's trajectory generation
  for generation in all three arms.
- **A2, A3, A8.** The development numbers are at seed 44; the held-out
  solver is per-seed through its recognition model and policy, and HONEST
  itself varies by one task across seeds (56–57). A gain of four on NEAR
  should survive that; the `has-k` losses may grow on some seed, which is
  why A8 is low confidence.
- **A4, A5.** The analogy action edits verified programs: a constant
  becomes a hole and the hole is filled from the grammar's constants
  (−1, 0, 1, 2) or by a sub-search. FRESH-1's parameters are −2 and 10 and
  its routines are ones the corpus lacks; an edit of a corpus program does
  not reach them. The gains on NEAR are k-variants of corpus families; I
  do not expect them on FRESH-1.
- **A6, A7.** Chain composes one of the system's own list programs with
  a behavioural residual. The FRESH-2 pipelines are random pairs of
  routines from the source file; those whose first stage the system
  holds a program for (`tail^k`, reverse, the appends) and whose second
  stage is a map, filter or fold are the reachable ones. On the 24-task
  suite, which was built from corpus routines, that was 9 of 24; FRESH-2
  is drawn from a wider routine set, so a lower rate.
- **A9.** The FRESH pre-registration's E5, kept.
- **A10.** Ranking sources and enumerating edits is interpreter time the
  candidate count does not show; run 3 measured 1.65×.

## Interpretation rules

- A2 passes and A4 passes: the analogy action's held-out gains are
  confined to parameter variants of the corpus's own families; it is not
  a route to new routines. Report it as such.
- A6 fails: one-stage composition of the system's own programs does not
  transfer beyond the suite it was tuned on.
- A1 fails: the retrained comparator differs from the registered HONEST;
  every other comparison is then between retrained arms only and is
  marked so.

## Scale

36 TRAIN tasks, 64 candidates per task per generation, three seeds of one
trajectory per arm. No claim about recursive self-improvement,
superintelligence or the singularity.
