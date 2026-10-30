# Honest self-play study: measured results

All three registered runs completed: RSI3_META_HONEST × seeds 11/22/33 ×
16 generations. They used `experiment_config_honest.json`, unchanged since
the pre-registration commit 03e7e2f, and ran with `python -m rsi3.longrun`
in a single process. Raw run files are in
[`results_honest/`](results_honest/). The decisive table is
`python -m rsi3.report --results rsi3/results_cascade rsi3/results_behave rsi3/results_behave_fold rsi3/results_honest`.

**Headline.** One arm reached both stated targets on every seed:

| | Target | Reached | Previous best |
| --- | --- | --- | --- |
| TRAIN | 24/36 | **29/36** | 29, the same arm without this change |
| Learned solver on VALIDATION (64 candidates per task) | 6/12 | **9/12** | 7, the designer-only control |

The held-out score rose from 5/12 for RSI3_META_BEH_FOLD to 9/12. That arm
is identical except for how its meta-policy is trained. The change is
`selfplay_honest`: every action is credited by its actual one-chunk
outcome on the tasks the system imagines, and none by construction.

**Caveat.** VALIDATION was not an unseen set for this change. It was
designed after reading the per-task held-out outcomes of four earlier arms
(PREDICTIONS_HONEST.md). The runs themselves never adapted to VALIDATION:
development never loaded it, and the agent applies a policy trained on
TRAIN and imagined tasks only. TEST was never opened.

## Results

| Arm | TRAIN g16 | VALIDATION g16 (11/22/33) | `validation_agent` g16 (11/22/33) | agent g1–g16 (every seed) | CPU s per run |
| --- | --- | --- | --- | --- | --- |
| RSI3_META_CONJ | 21 | 2 / 2 / 1 | 5 / 5 / 5 | 2 3 4 3 4 4 4 5 5 5 5 5 5 5 5 5 (seed 11) | 4,019 |
| RSI3_META_BEH_BASE | 21 | 2 / 2 / 1 | 7 / 7 / 7 | 7 8 8 7 7 7 7 7 7 7 7 7 7 7 7 7 | ~3,020 |
| RSI3_META_BEH_FOLD | 29 | 1 / 1 / 1 | 5 / 5 / 5 | 3 5 6 6 6 5 4 5 5 5 5 5 5 4 5 5 | ~2,510 |
| **RSI3_META_HONEST** | **29** | 2 / 1 / 1 | **9 / 9 / 9** | 6 9 8 6 8 8 8 8 8 8 8 8 8 9 8 9 | ~4,370 |

TRAIN reproduced the development trajectory exactly:
10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29.

Held-out tasks at generation 16, every seed, with the candidates spent on
each:

| Task | HONEST | Spent (seed 11) | FOLD | BASE |
| --- | --- | --- | --- | --- |
| `add-k (k=5)` | yes | `behave:map` 10 | yes | yes |
| `caesar-cipher (k=3, n=2)` | yes | `behave:map` 10 | yes | yes |
| `prepend-index-k (k=3)` | yes | `decompose:prepend_of` 16 | yes | yes |
| `sum` | yes | `decompose:fold_zero` 4 | yes | yes |
| `bool-identify-is-mod-k (k=2)` | yes | `decompose:map` 16, then `behave:map` 13 | yes | no |
| `has-k (k=2)` | yes | three skeletons 48, then `behave:any` 12 | no | yes |
| `caesar-cipher (k=1, n=3)` | yes | `behave:map` 31 | no | yes |
| `caesar-cipher (k=1, n=4)` | yes | `behave:map` 32 | no | yes |
| `caesar-cipher (k=2, n=5)` | **yes** | `behave:map` 34 | no | no |
| `slice-k-n (k=3, n=3)` | no | `filter_list` 32, `fold_nil` 16, `behave:whole` 16 | no | no |
| `repeat-k (k=2)` | no | — | no | no |
| `kth-largest (k=5)` | no | — | no | no |

`caesar-cipher (k=2, n=5)` had never been solved by any committed run.

## Why, traced

The three caesar tasks the library arm used to miss needed 31–34
candidates of `behave:map`. Behavioural search reaches them with the
library; it needs more than one chunk.

- **FOLD's policy** gave `behave:map` one chunk and moved on, because its
  replay held `decompose:map` at 341 of 344: credited by construction.
- **HONEST's policy** holds `decompose:map` at 352 of 530 and `behave:map`
  at 471 of 534, both actual outcomes. So `behave:map` ranks first on map
  shapes and keeps its turn.

`has-k (k=2)` was found by `behave:any` after three skeleton chunks.

Nothing else differs between the two arms. TRAIN is the same set of 29
tasks, with the same library growth.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| HONEST TRAIN g16 | 29 (determined) | 29 | hit |
| H1 HONEST agent > FOLD agent | PASS (moderate) | 9 vs 5 | hit |
| H2 HONEST agent > CONJ agent | PASS (moderate) | 9 vs 5 | hit |
| H3 HONEST agent ≥ 6 | PASS (low–moderate) | 9 | hit |
| H4 point forecast | 6 (range 5–8) | 9 | **miss** (above the range) |
| H5 slice solved | no | no | hit |

Five of six hit. The miss was an underestimate.

## Limits

- **Exposure.** This is the strongest caveat: VALIDATION was no longer
  unseen when this change was designed. The 9/12 is measured on tasks
  whose earlier failures informed the design, though not this run's
  policy. A clean held-out measure would need tasks no design decision
  has seen. TEST is sealed under the owner's directive.
- **Designer-given parts.** Behavioural search, its witnesses, the fold
  action and the skeletons are designer-given.
- **What is self-directed.** The policy that routes the budget is learned
  from the system's own practice on tasks it imagines. The library, the
  concepts and the cascade on TRAIN are the system's own.
- **Working tree.** About three minutes after the registered run started,
  the working tree it was launched from was switched to another branch for
  an edit, then restored. The run was a single process. The modules that
  changed had all been imported when it started, and the modules it
  imports later were unchanged. So it ran the registered code.
- **Scale.** 36 + 12 list tasks. No claim about superintelligence, the
  singularity or consciousness.
