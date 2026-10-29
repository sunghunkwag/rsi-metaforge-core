# Meta-RL study: measured results

All nine registered runs completed: RSI3_UNIFORM_FM_DEC, RSI3_META and
RSI3_META_WIPE × seeds 11/22/33 × 12 generations. They used
`experiment_config_metarl.json`, unchanged since the pre-registration commit
aeb506f, and ran with `python -m rsi3.longrun`. The comparator is the committed
RSI3_UNIFORM_FM runs in `results_invention/`. Raw run files are in
[`results_metarl/`](results_metarl/), and the decisive table is
`python -m rsi3.report` over both directories.

**Headline.**

- **TRAIN.** The meta-RL arm solved 17/36 TRAIN tasks, against 9/36 for the
  best earlier arm, at the same logical budget.
- **Transfer.** Its TRAIN-trained solver, applied to VALIDATION at the same
  per-task budget (`validation_agent`), solved 4/12 on every seed. The
  fixed-language comparator solved 1/12, the hand-given skeletons with a
  fixed split 3/12, and the identical learner with its memory wiped each
  generation 3/12. Two of the four tasks, `has-k (k=2)` and
  `prepend-index-k (k=3)`, had never been solved by any committed RSI-2 or
  RSI-3 run.
- **Plain VALIDATION.** RSI-2's `assess`, which only searches the
  recognition-conditioned prior, did not improve, as predicted.
- **Predictions.** All 12 registered predictions hit.

## Results

TRAIN is seed-independent in these arms (disclosed before the runs), and
it reproduced the seed-44 development trajectories exactly.

| Arm | TRAIN g1–g12 | TRAIN g12 | Sum g1–g12 | VALIDATION g12 (11/22/33) | `validation_agent` g12 (11/22/33) | CPU s per run |
| --- | --- | --- | --- | --- | --- | --- |
| RSI3_UNIFORM_FM (committed) | 6 6 6 7 7 7 7 8 8 8 9 9 | 9 | 88 | 1 / 1 / 1 | 1 / 1 / 1 (= VALIDATION) | 736 |
| RSI3_UNIFORM_FM_DEC | 7 8 9 9 11 11 11 12 14 15 15 16 | 16 | 138 | 2 / 2 / 2 | 3 / 3 / 3 | 2,640 |
| RSI3_META_WIPE | 7 9 11 12 13 13 13 13 14 15 17 17 | 17 | 154 | 1 / 1 / 1 | 3 / 3 / 3 | 2,343 |
| **RSI3_META** | 7 9 11 12 15 15 15 17 17 17 17 17 | **17** | **169** | 1 / 2 / 1 | **4 / 4 / 4** | 4,023 |

`validation_agent` per generation, seed 11:

| Arm | g1–g12 |
| --- | --- |
| DEC | 2 1 3 3 3 3 3 3 3 3 3 3 |
| META_WIPE | 3 3 3 4 2 3 3 3 3 4 4 3 |
| META | 3 3 3 5 4 4 4 4 4 4 4 4 |

CPU is per run; the trajectory is computed once and each seed adds only its
VALIDATION.

## What transferred, and why

At generation 12, META's agent solved these VALIDATION tasks on every seed:

| Task | Solved before in any committed run? | How META's agent spent its 64 candidates |
| --- | --- | --- |
| `has-k (k=2)` | never | 13 on the `any` skeleton, solved |
| `prepend-index-k (k=3)` | never | 15 on the `prepend_of` skeleton, solved |
| `add-k (k=5)` | once (INV, seed 11, generation 12) | 25 on the `map` skeleton, solved |
| `caesar-cipher (k=3, n=2)` | always (every arm) | 3 on `map`, solved |

A replay of META's final state (its generation-12 checkpoint) shows the
programs found. VALIDATION was read here for analysis only.

    add-k (k=5)              map (add c_c630174878)                     c_c630174878 = sub 2 (sub -1 2) = 5
    has-k (k=2)              lambda l. not (is_empty (filter (gt c_6f980a69c7) l))   c_6f980a69c7 = sub 2 -1 = 3
    prepend-index-k (k=3)    lambda l. cons (head (c_a60e9b11ed l)) l   c_a60e9b11ed = tail^2

All three use concepts the system invented on TRAIN and admitted through TRAIN
solves. The `add-k` constant is a concept built from another concept.

There is one caveat. The `has-k (k=2)` program tests "some element is less
than 3", not "2 occurs". It passes every hidden VALIDATION example, which is
what the verifier checks, but it is not the intended function. Verification
by examples admits such programs. DEC solves `has-k (k=2)` and
`prepend-index-k (k=3)` without any concept, so for those two the concepts
are not what made the difference.

The one task that separates META from DEC and from META_WIPE is `add-k
(k=5)`. The decisive traces are in the run files.

- **DEC** splits its budget by a fixed rule: 32 to the prior, 16 to `map`,
  16 to `map_list`. The hole needs about 25 candidates under `map` (with
  the constant 5), so 16 is not enough, and DEC fails it at every
  generation.
- **META_WIPE** concentrated on `map` and solved it at generations 10 and
  11. At generation 12 it refitted its policy on that generation's
  episodes alone, which spread the budget back to 32/16/16, and it lost
  the task.
- **META** used its persistent replay of 1,743 chunk episodes and gave
  `add-k` its whole budget on `map` from generation 4 onward. It solved the
  task at every generation from then on, on every seed.

So the transfer gain beyond the hand-given skeletons is a learned routing
decision: which structural decomposition fits a task's public shape. It was
learned from TRAIN rewards, carried across generations, and applied to a
task the policy never trained on. The constant 5 itself is reachable because
of the self-invented constants: META adopted `sub 2 (sub -1 2)` = 5 in
generation 3. DEC has no invention.

The learned policy, fitted on the full replay:

| Action | Chunks | Rewarded |
| --- | --- | --- |
| prior | 427 | 0 |
| invented | 893 | 2 |
| `prepend_of` | 34 | 5 |
| `map` | 32 | 4 |
| `filter` | 32 | 3 |
| `map_const` | 11 | 2 |
| `any` | 40 | 1 |
| `filter_list` | 146 | 0 |
| `map_list` | 69 | 0 |
| `all` | 30 | 0 |
| `any_list` | 29 | 0 |

It learned that the undirected prior search stopped paying, and which shape
calls for which skeleton.

## Concepts the system invented and admitted (META, identical on every seed)

| Generation | Kind | Admitted through | Concept |
| --- | --- | --- | --- |
| 2 | constant | has-k (k=3) | `sub 2 -1` = 3 |
| 2 | power | prepend-k (k=4) | `(sub 1)^3` |
| 2 | constant | prepend-k (k=4) | `sub -1 2` = −3 |
| 3 | constant | prepend-k (k=5) | `sub 2 c_c68925c9f8`, built from the adopted −3 |
| 4 | power | index-k (k=3) | `tail^2` |
| 5 | power | index-k (k=5) | `c_a60e9b11ed . c_a60e9b11ed`, built from the adopted `tail^2` |
| 8 | iterate | modulo-k (k=2) | `lambda n x. fold (lambda acc _. sub 1 acc) x (range n)`, a loop generalized from a repetition |

Two of the seven are built from concepts the system had already admitted,
which is compounding. RSI-2's MDL learner still adopted nothing.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| TRAIN g12 / sum, DEC | 16 / 138 (determined) | 16 / 138 | hit |
| TRAIN g12 / sum, META | 17 / 169 (determined) | 17 / 169 | hit |
| TRAIN g12 / sum, META_WIPE | 17 / 154 (determined) | 17 / 154 | hit |
| TRAIN g12 / sum, UFM | 9 / 88 (committed) | 9 / 88 | hit |
| X1 META agent > UFM VALIDATION, every seed | PASS | 4 vs 1 on every seed | hit |
| X2 META agent > DEC agent, every seed | PASS (moderate) | 4 vs 3 on every seed | hit |
| X3 META agent > META_WIPE agent, every seed | PASS (low) | 4 vs 3 on every seed | hit |
| X4 META VALIDATION > UFM VALIDATION, every seed | FAIL | 1 vs 1, 2 vs 1, 1 vs 1 | hit |
| Y1 META agent g12 ≥ 3 on every seed | ≥ 3 | 4, 4, 4 | hit |
| Y2 never-before-solved VALIDATION tasks, per seed | ≥ 2 | 2 on every seed (`has-k k=2`, `prepend-index-k k=3`) | hit |
| Y3 agent = VALIDATION for prior-only arms | holds | holds (test, and the UFM column) | hit |
| Y4 META concepts adopted / built from adopted | 7 / 2 | 7 / 2 | hit |

12 of 12. The four TRAIN rows were determined in advance, as disclosed, so
they confirm determinism rather than test a forecast. The eight open
predictions all hit.

## Limits

- **The skeletons are designer-given.** They are generic list combinators
  ported from `verified-code-rsi`. Most of the TRAIN gain (9 → 16) is
  theirs, as DEC shows. What the self-directed parts add, measured, is +1
  TRAIN, +31 in TRAIN area, and +1 held-out task on every seed, with the
  cause traced above.
- **X2 and X3 rest on one task.** Both margins are a single task,
  `add-k (k=5)`. META_WIPE matched META's 4 at generations 10–11. The
  advantage of persistent memory is real in this data (a stable routing
  where the wiped learner oscillated), but it is narrow.
- **The seeds are not independent for TRAIN.** They are independent only
  through the recognition model, so the held-out results are three
  correlated measurements of one trained solver.
- **Plain VALIDATION did not move.** The transfer appears only when the
  learned solver is used at test time. That is the point of
  `validation_agent`, and it is also why the old metric could never show it.
- **Scale.** 36 TRAIN and 12 VALIDATION list tasks, and a size-12
  enumerator. Nothing here bears on superintelligence or consciousness.
