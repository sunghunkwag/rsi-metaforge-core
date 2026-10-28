# Self-continuity study: pre-registered predictions

> **Status: abandoned on 2026-10-29.** The final runs were stopped by the
> repository owner's decision before any run finished. No registered-seed
> result was produced or inspected. The owner's reason was that a guard that
> only prevents losses cannot, by construction, produce a capability leap.
> Work moved to concept invention (`selfmodel.py`, PREDICTIONS_INVENTION.md).
> The guard's code and tests remain in the repository, with `continuity` off
> in every other arm. These predictions are kept unscored.

Registered 2026-10-29, before any run of the two new arms on the registered
seeds (11/22/33). This file is committed together with the code
(`continuity.py`) and `experiment_config_self_continuity.json`. That config
matches `experiment_config_failure_memory.json` except for its arm list and
the `continuity` block. Misses will be scored in SELF_CONTINUITY_RESULTS.md
and will not be reinterpreted.

## The question

Every sleep phase rewrites the system: RSI-2 refits the grammar, may adopt
library entries, and refits the recognition model. The solutions are kept as
records, but a record is not an ability. This is the ship-of-Theseus question
in operational form: after each rewrite, can the new self still do what the
previous self could? If not, should the rewrite be repaired or undone?

The guard (see `continuity.py` for exact definitions) scores each self on two
things:

- **TRAIN retention**: a heuristic-free search under that self, at
  B_audit = 64, re-derives each solved TRAIN task. The re-derived program
  must have the stored solution's probe signature, not just match the
  public outputs.
- **Self-exams**: problems with known answers that the system writes for
  itself. Each exam is a program sampled from the system's own productions
  and library with RSI-2's uniform prior weights (`exam_author: "neutral"`).
  It is run on the public inputs of a TRAIN task. Neither compared self's
  weights shaped the question. A self passes an exam if its search finds a
  program with the answer key's probe signature, which is a held-out check
  on inputs the search never saw. Three exams are written per generation, and
  each joins the bank only after that generation's comparison. Exams are
  never used to fit anything.

Continuity score = TRAIN retained + exams passed. An **alarm** means the old
self scores strictly higher than the new self.

## Arms

| Arm | Definition |
| --- | --- |
| RSI3_UNIFORM_FM_SCM | RSI3_UNIFORM_FM, guard in `measure` mode: both selves judged after every rewrite and recorded; nothing changed, nothing charged |
| RSI3_UNIFORM_FM_SC | RSI3_UNIFORM_FM, guard in `restore` mode: if any ability was lost, the highest-scoring candidate is kept (the new self; a rehearsed self if TRAIN tasks were lost; or the old self's weights and recognition with the current library). Ties keep the new self. All audit work is charged to the next wake |

The base is RSI3_UNIFORM_FM, the best arm so far (8/36 on every seed). The
measure arm is trajectory-identical to it by construction
(`tests/test_continuity.py::test_measure_mode_is_passive`). Its committed
runs in `results_failure_memory/` are therefore already known:

- TRAIN per generation is 6, 6, 6, 7, 7, 7, 7, 8 on every seed.
- VALIDATION per generation:
  - seed 11: 1, 1, 2, 1, 2, 1, 2, 2 (2 drops)
  - seed 22: 2, 1, 2, 1, 1, 1, 1, 1 (2 drops)
  - seed 33: 1, 1, 2, 2, 2, 2, 1, 2 (1 drop)

The task that flips is `sum`. The two arms are compared with each other.
Seeds are 11/22/33, 8 generations, B_wake = B_eval = 64, a per-generation cap
of 2,304 logical evaluations, and one verification per task per generation.
TEST is not opened. VALIDATION is reporting only: the guard never reads it.

## Disclosure: development before registration

All development runs used the unregistered seed 44, in measure mode only.

1. **TRAIN-only audit** (commit 17c57d1).
   - Retained 6/6, 6/6, 6/6, 7/7, 7/7, 7/7, 7/7, 8/8: no TRAIN ability was
     ever lost.
   - VALIDATION per generation was 1, 2, 2, 1, 2, 1, 2, 2, with `sum` lost
     and regained.
   - Re-derivation ranks were mostly 1–3. index-k ranged 4–11, and the total
     rank per generation was 8, 8, 8, 21, 12, 14, 11, 29.
   - Conclusion: a TRAIN-only guard is a null by construction at this budget.
     This is why the self-exams were added.
2. **Neutral exams** (this commit's code).
   - Exams passed, old → new / sat: 0→0/0, 3→3/3, 6→6/6, 9→8/9, 10→9/12,
     10→10/15, 12→13/18, 16→17/21. Exams were lost in generations 4–8.
   - The only alarm was at generation 5 (old 17 vs new 16). At that
     generation VALIDATION rose 1 → 2.
   - The two VALIDATION drops (generations 4 and 6) raised no alarm. In
     generation 4 the new self lost an exam but also re-derived the newly
     solved TRAIN task, so the scores tied.
   - Old and new judgements together cost 94, 33, 123, 361, 517, 806, 955
     and 931 evaluations per generation, 3,820 in all.
3. **Self-authored exams** (`exam_author: "self"`; same code).
   - The only alarm was again at generation 5 (old 19 vs new 17).
   - Exam writing cost 3–117 evaluations per generation.

The neutral author was chosen because its questions cannot favour either of
the compared selves. On the development seed both authors raised the same
single alarm, so the choice was not driven by an outcome. No restore-mode
run of any length was made before registration. The development evidence
says the exam signal moves, but on seed 44 it did not line up with
VALIDATION. The predictions below follow that evidence.

## Numeric predictions (mean over three seeds, generation 8)

| Arm | TRAIN | Plausible range | VALIDATION |
| --- | --- | --- | --- |
| RSI3_UNIFORM_FM_SCM | 8 | exactly 8 | 1.67 (2, 1, 2, identical to committed) |
| RSI3_UNIFORM_FM_SC | 7 | 6–8 | 1–2 |

Expected shape for SC: the charged audits reach several hundred evaluations
per generation from generation 4 on, which takes roughly a fifth of the
total wake budget. That should delay the deep resumable searches behind the
7th and 8th solves, so prepend-k (k=4) is no longer reached by generation 8
on most seeds. Restoration acts rarely. When it does, it swaps one
generation's weights and recognition model, which the next sleep refits from
scratch anyway.

## Decisive comparisons (every seed must satisfy the inequality)

| ID | Comparison | Predicted |
| --- | --- | --- |
| S1 | SC TRAIN > SCM TRAIN | FAIL |
| S2 | SC VALIDATION > SCM VALIDATION | FAIL |
| S3 | SC VALIDATION drops < SCM VALIDATION drops | FAIL |

## Mechanism readouts

| ID | Readout | Predicted |
| --- | --- | --- |
| P0 | SCM TRAIN and VALIDATION, every generation and seed, identical to the committed RSI3_UNIFORM_FM runs | identical |
| R1 | SCM TRAIN abilities lost (binary audit), every generation and seed | 0 everywhere |
| R2 | SCM runs with at least one generation in which the new self lost an exam | 3 of 3 |
| R3 | SCM, generations 2–8 pooled: alarms that coincide with a VALIDATION drop, and VALIDATION drops that coincide with an alarm | each at most half (or no alarms) |
| R4 | SC decisions other than accept_new, per run | 0–3 (point 1); at least one revert over the three runs |
| R5 | SC audit and exam work charged, per run | 2,500–6,000 logical evaluations |
| R6 | SC seeds on which 8 TRAIN tasks are reached by generation 8 | at most 1 of 3 |

## What the outcomes mean

- **S2 and S3 fail as predicted.** At this scale, checking that the
  rewritten self still has its predecessor's abilities does not protect
  held-out capability. The `sum` flips are then not a loss of generality that
  self-generated problems can detect. The most likely cause is the
  recognition model being refit with a new seed every generation, which
  changes conditioning on one specific task. The guard costs real budget for
  no gain, and a negative result here argues against spending wake budget on
  self-auditing at this budget.
- **S2 or S3 passes.** The self-exam carries information about held-out
  ability that the development seed did not show. That would be the first
  change in VALIDATION in any RSI-3 study.
- **R3 shows the alarm tracking drops while S2/S3 fail.** The detection
  works but the repair does not. Restoring the old self's weights would then
  be the wrong remedy, and the next step would be repairing the recognition
  model instead.

A functional self-continuity check is not consciousness or subjective
experience, and the study makes no claim about either.
