# Cascade study: pre-registered predictions

Registered 2026-10-30, before any run of these arms on the registered seeds
(11/22/33). This file is committed together with
`experiment_config_cascade.json`, and the runs use `python -m rsi3.longrun`.
The config has 16 generations, four arms, and self-play at 256 imagined tasks
per generation. Misses will be scored in CASCADE_RESULTS.md and will not be
reinterpreted.

## The question

The meta-RL study (METARL_RESULTS.md) reached 17/36 TRAIN, and its learned
solver reached 4/12 on VALIDATION. Then it stopped. The remaining tasks need
list construction by folding: reverse, append, duplicate, rotate, slice and
sort.

This study adds three mechanisms one at a time, each on top of the last:

| Arm | Adds | Kind |
| --- | --- | --- |
| RSI3_META | nothing: the registered meta-RL arm, run for 16 generations | baseline |
| RSI3_META_FOLD | fold skeletons, `fold h init` with a typed step hole (λ²-style) | designer-given |
| RSI3_META_PLAY | self-play: each generation the policy is also trained on tasks the system imagines through its own skeletons (a skeleton plus a hole sampled from its own grammar, run on TRAIN public inputs), plus five input–output relation features | self-directed |
| RSI3_META_CONJ | conjugation: an unsolved task is transformed by any of the system's own verified list programs that it checks is an involution on that task's public data (C (C x) = x), solved there by a base skeleton, and transformed back | self-directed |

Is there a cascade, meaning a newly acquired ability that becomes the tool
for further abilities? And does any of this move held-out capability?

## Disclosure: what is already known

TRAIN is seed-independent in all four arms. Wake, self-model, policy,
self-play and conjugation are all seed-free; the self-play stream is keyed
by generation only. The development runs on seed 44 therefore fix TRAIN on
the registered seeds for every generation they covered:

| Arm (development run length) | TRAIN by generation | `validation_agent` by generation, seed 44 |
| --- | --- | --- |
| META (12) | 7 9 11 12 15 15 15 17 17 17 17 17 | 2 2 3 4 4 4 4 4 4 4 4 4 |
| META_FOLD (12) | 7 9 10 10 11 13 15 15 15 17 17 17 | 3 3 3 3 3 4 4 5 5 5 5 5 |
| META_PLAY (20) | 7 8 10 10 11 13 15 17 17 17 17 18 18 18 18 18 18 18 18 18 | 2 2 3 4 3 4 4 5 5 5 5 5 5 5 5 5 5 5 5 5 |
| META_CONJ (16) | 7 8 10 11 11 13 15 16 17 17 17 17 18 20 20 21 | 2 3 4 3 4 4 4 5 5 5 5 5 5 5 5 5 |

The META_CONJ development run showed the cascade:

- generation 13: reverse, through the fold skeleton;
- generation 14: append-k (k=1) and append-k (k=4), through conjugation by
  reverse;
- generation 16: append-index-k (k=1), through conjugation.

The TRAIN outcomes of META and META_FOLD in generations 13–16 are not known.

Development also looked at VALIDATION in two ways.

- **Fold skeletons on VALIDATION.** While building the fold skeletons, they
  were run offline on VALIDATION tasks; `sum` was found at candidate 1. The
  skeletons had already been designed and were not changed.
- **Unsolved VALIDATION tasks.** The names of the VALIDATION tasks the agent
  still misses have been seen in development output: caesar-cipher variants
  (k=1, n=3; k=1, n=4; k=2, n=5), `bool-identify-is-mod-k (k=2)`,
  `repeat-k (k=2)`, `slice-k-n (k=3, n=3)` and `kth-largest (k=5)`. No
  mechanism was designed for them.

## Predictions

### TRAIN, generation 16

| Arm | TRAIN g16 | Basis |
| --- | --- | --- |
| META | 17 (range 17–18) | forecast |
| META_FOLD | 17 (range 17–19) | forecast |
| META_PLAY | 18 | determined |
| META_CONJ | 21 | determined |

### Open outcomes (seeds 11/22/33, generation 16)

| ID | Comparison (every seed) | Predicted |
| --- | --- | --- |
| Z1 | META_CONJ TRAIN > META TRAIN | PASS |
| Z2 | META_CONJ TRAIN > META_PLAY TRAIN | PASS (determined: 21 vs 18) |
| Z3 | META_CONJ `validation_agent` > META `validation_agent` | PASS |
| Z4 | META_CONJ `validation_agent` > META_PLAY `validation_agent` | FAIL |
| Z5 | META_CONJ `validation_agent` ≥ 6 | FAIL |
| Z6 | META_PLAY `validation_agent` > META_FOLD `validation_agent` | FAIL |

| ID | Readout | Predicted |
| --- | --- | --- |
| C1 | META_CONJ cascade: reverse, then append-k (k=1, k=4) through conjugation, then append-index-k (k=1) | as in development (determined) |
| C2 | VALIDATION tasks solved by META_CONJ's agent at generation 16, per seed | 5, including `sum` and `add-k (k=5)` |

## What the outcomes mean

- **Z1 and C1 hold.** A self-acquired ability became the tool for three
  further abilities. That is a cascade, the first in any RSI-3 run.
  Conjugation is the self-directed step: the system checks a property of
  its own program and uses it to transform problems. Reverse itself came
  from a designer-given skeleton, found by a policy trained on self-play.
- **Z4 and Z5 fail, as predicted.** The cascade is confined to TRAIN's
  append family. Held-out capability stays at the level fold plus self-play
  reach, because VALIDATION contains no task in that family. This would be
  stated as such, not as transfer.
- **Z3 passes.** Held-out gain over the registered meta-RL arm, from the
  fold skeleton (`sum`). That gain is designer-given structure.

No claim about superintelligence, the singularity or consciousness is made
or tested.
