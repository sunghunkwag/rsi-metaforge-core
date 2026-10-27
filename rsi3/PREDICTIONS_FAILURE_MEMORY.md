# Failure-memory study — pre-registered predictions

Registered 2026-10-28, before any full run of the two new arms, and committed
together with the code and `experiment_config_failure_memory.json`. That file
is identical to `experiment_config.json` except for its arm list. Misses will
be scored in FAILURE_MEMORY_RESULTS.md, not reinterpreted.

## The question

RESULTS.md found that the only gain in the first study came from resumption
(never re-evaluating a searched prefix), and that it was thrown away twice:

- after every new solution, RSI-2's sleep refits the prior grammar, the
  enumeration order changes, and every frontier restarts at depth 0
  (RSI3_UNIFORM: depth 308 in generation 5, then 80 / 160 / 240);
- the recognized pathway's grammar changes every generation, so it restarts
  every generation, and different pathways re-evaluate each other's programs.

A program that failed a task's public examples fails them under every order
(same examples, same frozen evaluator, library entries only ever added). The
new arms keep, per task, the set of programs that failed the public examples,
shared by every pathway and kept across grammar changes, and skip them without
charging the logical budget. Does keeping that knowledge move verified
capability?

## Arms

| Arm | Definition |
| --- | --- |
| RSI3_UNIFORM_FM | RSI3_UNIFORM + failure memory |
| RSI3_FM | RSI3 (learned allocation, replay, genesis) + failure memory |

Comparators are the committed runs in `results/` (RSI2, RSI3, RSI3_UNIFORM),
reused, not rerun. Before registration, RSI3_UNIFORM seed 11 was rerun with
this commit's code (failure memory off) and compared episode by episode with
the committed file, to confirm the code change does not alter existing arms.
Same seeds (11/22/33), 8 generations, B_wake = B_eval = 64, per-generation cap
2,304 logical evaluations, one verification per task per generation. TEST is
not opened; VALIDATION is reporting only.

Disclosure: before registration, failure memory was exercised only by unit
tests on TRAIN subsets (`tests/test_failure_memory.py`). No full run of either
new arm was made.

## Numeric predictions (mean over three seeds, generation 8)

| Arm | TRAIN | Plausible range | VALIDATION |
| --- | --- | --- | --- |
| RSI3_UNIFORM_FM | 8 | 7–9 | 1–2 |
| RSI3_FM | 7 | 6–8 | 1–2 |

Expected shape: RSI3_UNIFORM_FM matches RSI3_UNIFORM through generation 1,
finds index-k (k=3) no later than generation 5, and then keeps going past the
depth RSI3_UNIFORM lost, reaching about the depth where RSI-2's own B640
diagnostic verified 8/36. RSI3_FM recovers part of RSI3's loss because
pathways stop re-evaluating each other's programs, but its allocation still
spreads over ~100 slots, so it stays below RSI3_UNIFORM_FM. No VALIDATION
change is expected: no library entry has been adopted in any run so far.

## Decisive comparisons (every seed must satisfy the inequality)

| ID | Comparison | Predicted |
| --- | --- | --- |
| F1 | RSI3_UNIFORM_FM TRAIN > RSI3_UNIFORM TRAIN | PASS |
| F2 | RSI3_FM TRAIN > RSI3 TRAIN | PASS |
| F3 | RSI3_FM TRAIN > RSI3_UNIFORM_FM TRAIN | FAIL |
| F4 | RSI3_UNIFORM_FM TRAIN > RSI2 TRAIN | PASS |
| F5 | RSI3_UNIFORM_FM VALIDATION > RSI2 VALIDATION | FAIL |

## Mechanism readouts

| ID | Readout | Predicted |
| --- | --- | --- |
| G1 | Known failures skipped without charge, per run, both arms | > 0 on every run |
| G2 | Distinct failed programs on the most-searched task by generation 8, RSI3_UNIFORM_FM | ≥ 450 |
| G3 | First generation with 7 TRAIN solved, RSI3_UNIFORM_FM | ≤ 5 |
| G4 | CPU per run, RSI3_UNIFORM_FM relative to RSI3_UNIFORM | ≥ 1.0× |

## What a null means

If F1 fails, carrying public failures across grammar changes did not reach
any further verified task at this budget; the remaining wall is then the
reach of the size-12 enumeration under RSI-2's frozen expansion cap, not
wasted re-evaluation. If F1 passes and F3 fails, the learned controller is
still the weaker allocator even after its waste is removed.
