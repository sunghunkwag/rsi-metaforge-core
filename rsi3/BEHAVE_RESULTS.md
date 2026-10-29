# Behavioural-search study: measured results

All six registered runs completed: RSI3_META_BEH and RSI3_META_BEH_BASE ×
seeds 11/22/33 × 16 generations. They used `experiment_config_behave.json`,
unchanged since the pre-registration commit 2dc0d3f, and ran with
`python -m rsi3.longrun`. The comparator is the committed RSI3_META_CONJ
runs in `results_cascade/`. Raw run files are in
[`results_behave/`](results_behave/), and the decisive table is
`python -m rsi3.report --results rsi3/results_cascade rsi3/results_behave`.

**Headline.**

- **TRAIN.** Behavioural search built from the system's own library
  solved **25/36**, against 21 for the cascade arm. The same search without
  the library also solved 21.
- **Held out.** The result went the other way, and three of the four open
  forecasts about it missed. BEH's learned solver solved **4/12** on every
  seed, below the cascade arm's 5. The designer-only control solved **7/12**
  on every seed: the highest held-out score in any RSI-3 run, and above the
  target of 6.
- **What helped and what hurt.** The algorithm transfers. What the system
  learned (more concepts and library entries, a policy trained on its own
  replay) helped on TRAIN, where budget accumulates over generations, and
  hurt at the held-out budget of 64 candidates per task.

## Results

| Arm | TRAIN g16 | VALIDATION g16 (11/22/33) | `validation_agent` g16 (11/22/33) | agent g1–g16, seed 11 | CPU s per run |
| --- | --- | --- | --- | --- | --- |
| RSI3_META_CONJ (committed) | 21 | 2 / 2 / 1 | 5 / 5 / 5 | 2 3 4 3 4 4 4 5 5 5 5 5 5 5 5 5 | 4,019 |
| RSI3_META_BEH | 25 | 1 / 1 / 1 | **4 / 4 / 4** | 4 5 6 5 5 5 4 4 4 4 4 4 4 4 4 4 | 3,714–3,732 |
| RSI3_META_BEH_BASE | 21 | 2 / 2 / 1 | **7 / 7 / 7** | 7 8 8 7 7 7 7 7 7 7 7 7 7 7 7 7 | 3,015–3,027 |

TRAIN reproduced the development trajectories exactly, as disclosed.

Held-out tasks solved at generation 16, on every seed:

| Task | CONJ | BEH | BASE |
| --- | --- | --- | --- |
| `add-k (k=5)` | yes | yes | yes |
| `caesar-cipher (k=3, n=2)` | yes | yes | yes |
| `prepend-index-k (k=3)` | yes | yes | yes |
| `sum` | yes | yes | yes |
| `has-k (k=2)` | yes | no | yes |
| `caesar-cipher (k=1, n=3)` | no | no | **yes**: `behave:map`, 13 candidates |
| `caesar-cipher (k=1, n=4)` | no | no | **yes**: `behave:map`, 13 candidates |

The two caesar tasks had never been solved by any committed RSI-2 or RSI-3
run. Unsolved by all three: `slice-k-n (k=3, n=3)`, `repeat-k (k=2)`,
`bool-identify-is-mod-k (k=2)`, `caesar-cipher (k=2, n=5)` and
`kth-largest (k=5)`.

## Why BEH's held-out score fell, traced

**1. Library growth at a fixed small budget.** By generation 16, BEH's pool
had grown well past BASE's:

| | BEH | BASE |
| --- | --- | --- |
| library entries | 18 | 9 |
| adopted concepts | 15 | 5 |

Every leaf and operation widens every size level of the pool.

- **BASE.** `caesar-cipher (k=1, n=3)` needs the behaviour `add x 1`, after
  which the `mod` witness proposes `mod (add x 1) 3`. BASE reaches it
  within 13 charged behaviours.
- **BEH.** BEH spent its 16 on `behave:map` and did not reach it.

On TRAIN the same growth paid, because a task's budget accumulates across
generations; that is where B3 comes from. At 64 per held-out task it costs.

**2. Policy routing.** The meta-policy's replay gives the behavioural
actions their real practice outcomes on imagined tasks.

- **Behavioural actions.** `behave:whole` succeeded within one chunk in 125
  of 2,224 episodes (5.6%), since most imagined tasks are not fixed-length
  outputs.
- **Skeleton actions.** These are credited by construction in self-play.
  `decompose:map` scored 341 of 344, `decompose:filter_list` 81 of 129.
- **The result.** At generation 16 BEH's agent spent all 64 candidates for
  `slice-k-n (k=3, n=3)` on `filter_list` and `fold_nil`, never on
  `behave:whole`. It spent all 64 for `bool-identify-is-mod-k (k=2)` on
  `decompose:map`.
- **The early peak.** In generation 3, before the replay had grown, BEH's
  agent reached 6. It solved `bool-identify-is-mod-k (k=2)` through
  `behave:map` in 13 candidates, and also `has-k (k=2)`. It then declined
  to 4.

**3. `has-k (k=2)`** was lost against CONJ. BEH spent 16 candidates each on
`any_list`, `any`, `fold_false` and `all` under its own grammar, and none on
`behave:any`.

## Predictions scored

| ID | Registered | Observed | Score |
| --- | --- | --- | --- |
| B1 BEH TRAIN > CONJ TRAIN | PASS (determined) | 25 vs 21 | hit |
| B3 BEH TRAIN > BASE TRAIN | PASS (determined) | 25 vs 21 | hit |
| B2 BEH agent > CONJ agent | PASS | 4 vs 5 | **miss** |
| B4 BEH agent > BASE agent | PASS (moderate) | 4 vs 7 | **miss** |
| B5 BEH agent ≥ 6 | PASS | 4 | **miss** |
| B6 BEH plain VALIDATION > CONJ plain VALIDATION | FAIL | 1 vs 2 / 2 / 1 | hit |
| B7 BEH agent, point forecast | 8 (6–10) | 4 | **miss** |
| B8 BASE agent, point forecast | 6 (4–8) | 7 | hit (in range) |

Four of eight hit, and the two determined ones were known in advance. Every
open forecast about BEH's held-out capability missed. The pre-registration
said that if B4 failed, the held-out gain belongs to the algorithm and not
to learning. That is the finding. On held-out tasks at this budget, the
self-acquired material made the search worse (B4: 4 against 7).

## Limits

- **Designer-given parts.** Behavioural search (observational
  equivalence, cons deduction, witness functions) is designer-given.
  BASE's 7/12 is that algorithm's result, not self-improvement.
- **Exposure.** The witness functions were designed after the VALIDATION
  task names were seen (PREDICTIONS_BEHAVE.md). Development never loaded
  VALIDATION.
- **What is now known.** VALIDATION's per-task outcomes and spending for
  both arms are now known. Any later study's VALIDATION predictions are made
  with that knowledge and will say so.
- **Seeds.** TRAIN is one deterministic trajectory per arm; the seeds are
  independent only through the recognition model.
- **Scale.** 36 + 12 list tasks. No claim about superintelligence, the
  singularity or consciousness.
