# Phase 1: pre-registered predictions

Registered 2026-11-06, before any rsi4 run touched a stage-train task or a
J pool. Misses will be scored first in RESULTS_P1.md and will not be
reinterpreted. The thresholds are the directive's (§6, Gate 1); G1a's
comparison is spelled out below in two readings, because the base code's own
record schema differs from the registered files.

## The question

Does the base arm, continued unchanged through three new stages of two-stage
pipelines, (a) reproduce its registered checkpoint, and (b) forget what it
learned on earlier stages?

## What runs

- **Plan.** [`runs/p1.json`](runs/p1.json), on GitHub Actions through
  `.github/workflows/rsi4-runs.yml` (branch `rsi4/run-p1`).
- **Arms.**
  - **B0** (BASE): RSI3_META_HONEST after TRAIN only, on its registered
    config `rsi3/experiment_config_honest.json`. Its checkpoint is B1's
    after-TRAIN milestone.
  - **B1** (BASE_SEQ): the same run continued through S1 → S2 → S3, 8
    generations each, unchanged.
  - **B2** (ANALOGY_SEQ): RSI3_META_ANALOGY_P on
    `rsi3/experiment_config_analogy.json`, the same stream. Reported, not
    gating.
- **Code.** `rsi4/stages.py` and `rsi4/report.py` at 0ff97c3 (StageRuntime;
  the module docstring defines "continued unchanged"); J at 9183407, frozen.
- **Measurement.** J evaluates each arm's learned solver
  (`rsi3.longrun.agent_validation` semantics, B_eval = 64) on the three
  stage-eval pools after TRAIN and after each stage: R[i][j], i = 0..3,
  j = 1..3, 100 tasks each, solved on at least 2 of 3 seeds. ACC, BWT, FGT and
  FWT and their 95% bootstrap intervals come from J's `metrics` operation.

## Gate 1 (the directive's thresholds; G1a in two readings)

- **G1a.** META_HONEST under its registered config reproduces TRAIN 29/36 and
  FRESH-1 7/33 on every seed, byte-identical to the base's registered result
  files. Compared: the TRAIN phase's per-seed `generations`, `final` and
  `config` against `rsi3/results_honest/RSI3_META_HONEST_seed<s>.json`, and
  `rsi3.reserve_eval`'s FRESH-1 output on the after-TRAIN checkpoint against
  `rsi3/results_fresh/RSI3_META_HONEST_seed11-22-33_fresh1.json`, as
  canonical JSON after removing the timing fields (`cpu_seconds`,
  `wall_seconds`). It is scored in two readings, both reported:
  - **Literal**: exactly that comparison.
  - **Key-exact**: the same comparison after also removing five keys that the
    base code (1e6868a) writes and the registered files (written at 03e7e2f)
    lack, and only if each of them holds its empty value in every record:
    `wake.meta.selfplay.composed_practised` = 0 and
    `wake.meta.selfplay.dreams_practised` = 0 in each generation, and
    `final.analogy` = {}, `final.chain` = {}, `final.curriculum` = []. rsi3's
    dream-practice (c830d19) and composition-practice (213573f) work added
    them to the record schema after HONEST was registered.

  **This is a conflict with the directive, reported here before the run.**
  The literal reading cannot pass for any code that runs the base unchanged,
  because the base's own record schema differs from the registered files by
  these five keys. Gate 1 is scored on the key-exact reading, and the Owner is
  asked to confirm that reading before Phase 2 starts. If the key-exact
  reading fails, the failure report is written and Phase 1 stops.
- **G1b.** B1 is measured. If its mean FGT is at least 3 tasks, forgetting is
  live, and the FGT and BWT comparisons of Gates 2 and 3 gate. If FGT is under
  3, the record reads "no measurable forgetting in this substrate": the FGT
  and BWT comparisons become report-only and the continual claim rests on
  FWT.

## Disclosure

**Development run (2026-11-06, local, before this file).** The TRAIN phase
of B0 through the real entry point (`python -m rsi4.stages`, guard and
watchdog on), on the registered config with VALIDATION recorded each
generation, as the registered runs did, under Python 3.13 / NumPy 2.5.3
(Actions uses Python 3.11). No stage generation ran, no stage-train task was
searched, and J evaluated nothing.

- TRAIN g1–g16, every seed: 10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29,
  the registered trajectory.
- Against the registered files: every value of every record is equal on
  every seed; the literal reading fails only on the five keys above, and the
  key-exact reading is identical on every seed (`generations`, `final`;
  `config` identical).
- FRESH-1 through `rsi3.reserve_eval` on the after-TRAIN checkpoint: 7 / 7 / 7,
  each seed's record byte-identical to the registered file with timing
  removed.
- Cost: 3,408 CPU seconds (seed 11's record, VALIDATION included); peak
  worker RSS 943 MB.
- The run found one defect, fixed in 0ff97c3 before this file: the worker
  pickled its runtime under `__main__`, so no other process could load a
  checkpoint.

**What is known about the new tasks.** Nothing beyond RESULTS_P0.md: pool
sizes, the stage split's counts, and each set's input/output type mix. No
stage-train or stage-eval task has been run by any solver. FRESH-2 (100
two-stage pipelines from the same source file, other names) is exposed:
HONEST solved 9 of 100 and ANALOGY_P 14 of 100 on every seed. Those are the
closest available evidence for R[0][·].

## Predictions

All counts are tasks of 100 per stage-eval pool, pooled over seeds (2 of 3),
unless stated otherwise.

| ID | Readout | Predicted | Confidence and basis |
| --- | --- | --- | --- |
| P1.1a | G1a TRAIN, literal: B0 TRAIN g16 = 29 on every seed, byte-identical | FAIL | determined: the five schema keys |
| P1.1b | G1a TRAIN, key-exact | PASS | determined by the development run (on Python 3.13; Actions runs 3.11) |
| P1.2 | G1a FRESH-1: B0 FRESH-1 = 7/33 on every seed, byte-identical | PASS | determined by the development run |
| P1.3 | R[0][j], B0 on each stage-eval pool | 9 each (range 3–18) | moderate; FRESH-2's 9/100 for this solver |
| P1.4 | Plasticity, B1: stage-train receipts per stage (of 36) | 9 per stage (range 4–18) | low; TRAIN went 10 → 29 of 36 in 16 generations on easier tasks; pipelines start near FRESH-2's 9% at 64 candidates and get 8 generations of resumed search |
| P1.5 | Within-stage gain, B1: mean over j of R[j][j] − R[0][j] | +2 (range −2 to +8) | low |
| P1.6 | G1b: B1 mean FGT | 1.5 (range 0–4); FGT ≥ 3: **no** (forgetting not live) | low; replay keeps every episode and solution, but the library, grammar and policy keep moving, and FGT takes a maximum over checkpoints, so a few flips make it positive without any trend |
| P1.7 | B1 BWT | −1 (range −4 to +2) | low |
| P1.8 | B1 FWT | +1 (range −3 to +4) | low; stages use disjoint routine groups, so only pipeline-shape experience transfers |
| P1.9 | B1 ACC | 10 (range 4–19) | low |
| P1.10 | B2 mean R[0][·] > B1 mean R[0][·] | PASS | moderate; the analogy action's FRESH-2 gain (+5) |
| P1.11 | B2 ACC > B1 ACC | PASS | low |
| P1.12 | Peak RSS per worker under 3 GB, both arms (no watchdog breach) | PASS | moderate; 943 MB in the development run's TRAIN phase; stages add memory and failure-memory entries |
| P1.13 | Worker CPU per run, B1 | 7,000 s (range 4,500–14,000) | moderate; TRAIN 3,408 s with VALIDATION in the development run, stage generations near TRAIN's early ones (60–120 s) |
| P1.14 | Worker CPU, B2 / B1 | 1.5× (range 1.2–2.2) | moderate; ANALOGY_P cost 1.51× HONEST on TRAIN |

Report-only forecasts (exposed partitions and retention; never a decision):

| ID | Readout | Predicted |
| --- | --- | --- |
| P1.15 | B1 final solver, FRESH-2 (of 100, every seed) | 10 (range 7–15); B0's registered value is 9 |
| P1.16 | B1 final solver, VALIDATION agent (of 12) | 9 (range 7–10) |
| P1.17 | B1 final solver, RESERVE-NEAR (of 100) | 55 (range 48–60) |
| P1.18 | TRAIN retention: receipted TRAIN tasks the solver re-derives at B_eval, after TRAIN → after S3 | 20 → 19 (each range 12–27) |

## Interpretation rules

- G1a's key-exact reading fails: the failure report is written with every
  number, and Phase 1 stops for the Owner, as the directive requires. The
  literal reading's predicted FAIL is reported, and Phase 2 waits for the
  Owner's ruling on the reading either way.
- G1b is applied mechanically from J's FGT point estimate (≥ 3 or not); the
  bootstrap interval is reported beside it and does not change the outcome.
- B2 does not gate anything.
- No task or seed is excluded after the draw. A crashed run is rerun on the
  same seed and the crash is logged.

No claim about superintelligence, the singularity or consciousness is made or
tested.
