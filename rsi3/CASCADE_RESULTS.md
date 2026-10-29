# Cascade study: measured results

All twelve registered runs completed: RSI3_META, RSI3_META_FOLD,
RSI3_META_PLAY and RSI3_META_CONJ × seeds 11/22/33 × 16 generations. They used
`experiment_config_cascade.json`, unchanged since the pre-registration commit
439506e, and ran with `python -m rsi3.longrun`. Two container restarts stopped
running jobs; each resumed from its per-generation checkpoint. Raw run files
are in [`results_cascade/`](results_cascade/), and the decisive table is
`python -m rsi3.report` over that directory.

**Headline.** The first cascade in any RSI-3 run, on every seed:

| Generation | Event |
| --- | --- |
| 13 | reverse is solved, through the fold skeleton |
| 14 | append-k (k=1) and append-k (k=4) are solved by conjugation with reverse: the system verifies that its own reverse is an involution on each task's public data, maps the task to a prepend task, solves that, and maps back |
| 14 | RSI-2's own MDL library learner adopts the shared step: `lambda acc x. cons x acc`, compressing reverse and both appends |
| 16 | the learner adopts reverse itself; append-index-k (k=1) is solved by conjugation with the compressed reverse |

TRAIN reached **21/36**, against 17 for the registered meta-RL arm. Held-out
capability (`validation_agent`) reached 5/12 on every seed, against 4. The
fifth task, `sum`, comes from the designer-given fold skeleton, not from the
cascade, as predicted. All 12 registered predictions hit.

## Results

| Arm | TRAIN g1–g16 | TRAIN g16 | VALIDATION g16 (11/22/33) | `validation_agent` g16 (11/22/33) | CPU s per run |
| --- | --- | --- | --- | --- | --- |
| RSI3_META | 7 9 11 12 15 15 15 17 17 17 17 17 17 17 17 17 | 17 | 2 / 2 / 1 | 4 / 4 / 4 | 4,647 |
| RSI3_META_FOLD | 7 9 10 10 11 13 15 15 15 17 17 17 17 17 17 17 | 17 | 1 / 1 / 2 | 5 / 5 / 5 | 5,050 |
| RSI3_META_PLAY | 7 8 10 10 11 13 15 17 17 17 17 18 18 18 18 18 | 18 | 1 / 3 / 1 | 5 / 5 / 5 | 4,744 |
| **RSI3_META_CONJ** | 7 8 10 11 11 13 15 16 17 17 17 17 18 20 20 21 | **21** | 2 / 2 / 1 | **5 / 5 / 5** | 4,019 |

TRAIN is seed-independent in these arms, as disclosed, and it reproduced
every development trajectory exactly. The seeds differ only in VALIDATION.

## What each mechanism added

- **Fold skeletons** (designer-given, `fold h init`):
  - TRAIN: nothing. The meta-RL policy received no fold reward in 16
    generations and starved the fold actions; reverse was never solved.
  - Held out: `sum` = `fold add 0`, on every seed (4 → 5).
- **Self-play** (self-directed):
  - Each generation the policy also trains on tasks it imagines through its
    own skeletons, plus five relation features in the task shape.
  - That taught it "a permutation of the input → `fold_nil`", without any
    verifier reward.
  - Reverse was solved in generation 12 (17 → 18). Held out: unchanged.
- **Conjugation** (self-directed):
  - An unsolved task is transformed by any of the system's verified list
    programs that it checks is an involution on that task's public data.
  - reverse → append-k ×2 → append-index-k (18 → 21). Held out: unchanged,
    because VALIDATION has no append-family task. This was predicted (Z4).

## RSI-2's library learner, compressing what the cascade produced

RSI-2's MDL learner needs a fragment shared by several solutions. It adopted
nothing in the first 21 registered RSI-3 runs. In this study it adopted, on
every META_CONJ seed:

| Generation | Entry | Support | Compression |
| --- | --- | --- | --- |
| 14 | `learned_g14_0 = lambda acc x. cons x acc` | 5 occurrences in reverse, append-k (k=1), append-k (k=4) | 23 nodes |
| 16 | `learned_g16_0 = lambda l. fold learned_g14_0 nil l` (reverse) | 4 occurrences in the append tasks | 8 nodes |

The second entry is built on the first.

The final append-index-k program shows the layers stacking:

    lambda l. (fold learned_g14_0 nil) (cons (head (c_9be793b42e (learned_g16_0 l))) (learned_g16_0 l))

Each layer comes from a different part of the system:

- `learned_g16_0` and `learned_g14_0` were found by RSI-2's MDL compression;
- `c_9be793b42e` (reverse) is a self-model concept;
- the outer `reverse . _ . reverse` comes from conjugation.

(The only other MDL adoption in any committed run is DEC's
`head . tail^4` at generation 9 in the meta-RL study.)

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| META TRAIN g16 | 17 (17–18) | 17 | hit |
| META_FOLD TRAIN g16 | 17 (17–19) | 17 | hit |
| META_PLAY TRAIN g16 | 18 (determined) | 18 | hit |
| META_CONJ TRAIN g16 | 21 (determined) | 21 | hit |
| Z1 CONJ TRAIN > META TRAIN, every seed | PASS | 21 vs 17 | hit |
| Z2 CONJ TRAIN > PLAY TRAIN, every seed | PASS (determined) | 21 vs 18 | hit |
| Z3 CONJ agent > META agent, every seed | PASS | 5 vs 4 | hit |
| Z4 CONJ agent > PLAY agent, every seed | FAIL | 5 vs 5 | hit |
| Z5 CONJ agent ≥ 6 | FAIL | 5 | hit |
| Z6 PLAY agent > FOLD agent, every seed | FAIL | 5 vs 5 | hit |
| C1 cascade reverse → append ×2 → append-index-k | as in development | generations 13, 14, 16 on every seed | hit |
| C2 CONJ agent tasks at g16 | 5, incl. `sum`, `add-k (k=5)` | 5, incl. both | hit |

12 of 12. META_CONJ and META_PLAY's TRAIN rows were determined by the
development runs, as disclosed, and Z2 follows from them.

## Limits

- **Designer-given parts.** The fold skeleton is designer-given. Reverse,
  the root of the cascade, came through it, found by a self-trained policy.
- **Self-directed parts.** Conjugation is self-directed in what it uses:
  the system's own programs and its own check of their algebraic property.
  But the move "transform by an involution" was written by the designer.
- **Held-out gain.** The cascade's held-out gain is zero. The only held-out
  gain in this study (+1, `sum`) is the fold skeleton's.
- **Seeds.** TRAIN is one deterministic trajectory per arm; the seeds are
  independent only through the recognition model.
- **Still unsolved.** 15 TRAIN tasks: dup, rotate, slice ×6, kth ×3,
  index-head, has-head-in-tail, is-mod-k, keep-mod-k. On VALIDATION, 7 of
  12, including three caesar variants, `slice`, `kth-largest`, `repeat-k`
  and `bool-identify-is-mod-k`.
- **Scale.** 36 + 12 list tasks. No claim about superintelligence, the
  singularity or consciousness.
