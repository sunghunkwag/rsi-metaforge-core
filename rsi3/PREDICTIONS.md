# RSI-3 pre-registered predictions

Registered 2026-10-27, before the final runs, and committed in the same commit
as the code and the frozen `experiment_config.json`. The configuration (seeds
11/22/33, 8 generations, B_wake = B_eval = 64, chunk 32, exploration 0.3, two
analog neighbors, RSI-2's search limits) is frozen from this commit. Misses
will be scored in RESULTS.md, not reinterpreted.

Disclosure: before registration, development smoke runs on seed 11 only
(generations 1–2 of RSI3 and RSI3_UNIFORM, generation 1 of RSI2, and a
unit-test TRAIN subset) were used to debug mechanics. They showed 6/36 TRAIN
and 1/12 VALIDATION after generations 1 and 2 for every arm run, and RSI2
spending 95.7% of its generation-1 wake candidates on tasks it left unsolved.
No configuration value was changed after those runs.

## Metrics

- **TRAIN**: cumulative number of the 36 TRAIN tasks with a hidden-example
  verified solution after generation 8.
- **VALIDATION**: RSI-2's `assess` at B_eval = 64 with the final state, out of
  12. Reporting only.
- Logical wake budget per generation is capped at 64 × 36 = 2,304 candidate
  evaluations in every arm.

## Numeric predictions (mean over three seeds, generation 8)

| Arm | TRAIN | Plausible range | VALIDATION |
| --- | --- | --- | --- |
| RSI2 | 6 | 5–7 | 1–2 |
| RSI3 | 8 | 7–10 | 1–2 |
| RSI3_NO_REPLAY | 8 | 7–9 | 1–2 |
| RSI3_NO_GENESIS | 8 | 7–9 | 1–2 |
| RSI3_UNIFORM | 8 | 7–9 | 1–2 |

Expected shape: a gain of about two TRAIN tasks over RSI2, coming mainly from
resumption (searching past the prefix RSI2 re-evaluates every generation),
which roughly reproduces the depth RSI-2's own diagnostics reached at B640
(8/36). Learned allocation, replay, and genesis are each expected to add
between zero and one task. No transfer to VALIDATION is expected: RSI-2's
calibration shows VALIDATION flat at 2/12 from B64 to B1024, and a library
entry would have to be adopted for the grammar to change materially.

## Decisive comparisons (every seed must satisfy the inequality)

| ID | Question | Criterion | Predicted |
| --- | --- | --- | --- |
| C1 | Does memory-regulated allocation beat uniform retry? | RSI3 TRAIN > RSI2 TRAIN | PASS |
| C2 | Does learning add beyond resumption? | RSI3 TRAIN > RSI3_UNIFORM TRAIN | FAIL |
| C3 | Does full replay matter? | RSI3 TRAIN > RSI3_NO_REPLAY TRAIN | FAIL |
| C4 | Does genesis matter? | RSI3 TRAIN > RSI3_NO_GENESIS TRAIN | FAIL |
| C5 | Does anything transfer? | RSI3 VALIDATION > RSI2 VALIDATION | FAIL |

## Mechanism readouts

| ID | Readout | Predicted |
| --- | --- | --- |
| M1 | Share of RSI2 wake candidates spent on tasks still unsolved after that generation | ≥ 85% |
| M2 | Deepest searched position on any task by generation 8, RSI3_UNIFORM | ≥ 300 candidates |
| M3 | At least one analog (genesis) pathway produces a verified solve | yes, in ≥ 1 of 3 RSI3 seeds |
| M4 | Verifier rejections (public match, hidden failure) per RSI3 run | 1–10 |
| M5 | Integrator skips of behaviour equivalent to a rejected program, per RSI3 run | 0–5 |
| M6 | CPU per run, RSI3 relative to RSI2 | ≥ 1.3× (deeper candidates are larger programs) |

## What a null means

If C1 fails, budget reallocation with resumption did not move certified TRAIN
capability at this scale, and the remaining bottleneck is the reach of the
language and enumerator rather than how the budget is spent. If C2–C4 fail,
the learned components are not contributing beyond the hard memory rules. Both
outcomes are deliverables.
