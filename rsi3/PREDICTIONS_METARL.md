# Meta-RL study: pre-registered predictions

Registered 2026-10-29, before any run of these arms on the registered seeds
(11/22/33). This file is committed together with `experiment_config_metarl.json`.
That config matches `experiment_config_invention.json` (12 generations) except
for three things: the arm list, the `meta` block (16-candidate chunks), and
that runs use `python -m rsi3.longrun`. Misses will be scored in
METARL_RESULTS.md and will not be reinterpreted.

## The question

Can the system learn how to search, carry that learning across tasks and
generations, and transfer it to tasks it has never seen?

Concretely, a meta-RL policy (`metarl.py`) decides how each task's share of
the wake budget is spent. It allocates 16-candidate chunks among three kinds
of actions:

- the prior pathway;
- the invented-concept pathway;
- the backward-decomposition skeletons the task's public shape fits.

The reward is a verifier receipt. The policy is fitted across all tasks on
the full replay of its experience.

Every mechanism here comes from the owner's repositories:

- backward decomposition: `verified-code-rsi`;
- near-miss operator invention: `LeapForge-Gated-VM` XIX;
- persistent process memory, and its wiped-memory control:
  `gated-self-improvement` v3;
- meta-learning across a task distribution with fast within-task
  adaptation: `MetaRL-Agent-Framework`.

**Transfer** is measured by `validation_agent`. The arm's own TRAIN-trained
solver is applied to each VALIDATION task at the same budget as VALIDATION
(B_eval = 64). Its actions there are the recognition-conditioned prior,
exactly as in RSI-2's `assess`, plus the skeletons. The policy is never
fitted on VALIDATION outcomes. For a prior-only arm, `validation_agent`
equals VALIDATION (tested).

## Arms

| Arm | Definition |
| --- | --- |
| RSI3_UNIFORM_FM | Comparator: the committed 12-generation runs in `results_invention/` |
| RSI3_UNIFORM_FM_DEC | Decomposition with a fixed split: half of each task's share to the prior, half shared by the fitting skeletons. No invention, no learned policy |
| RSI3_META | Meta-RL policy over prior / invented / skeletons, plus self-model invention with near-miss parts and the meta-learned inventor. The policy is fitted on the full replay every generation |
| RSI3_META_WIPE | The same, with the policy fitted on the current generation only (the wiped-memory control) |

## Disclosure: what is already known

**TRAIN outcomes are already known.** These arms' wake phase does not use
the seed: the prior, invented and skeleton searches, the self-model and the
policy are all seed-free. The seed enters only through dreams and the
recognition model, which act only in VALIDATION and in the prior action of
`validation_agent`. The development runs on seed 44 therefore fix every arm's
TRAIN trajectory on seeds 11/22/33 as well. The TRAIN rows below are
confirmations of determinism, not forecasts.

The open outcomes are VALIDATION and `validation_agent` on seeds 11/22/33.

Development runs (seed 44, 12 generations, this commit's code; RSI3_META's
first attempt was stopped by the job time limit in generation 12 and fixed,
see git history):

| Arm | TRAIN g1–g12 | `validation_agent` g1–g12 | Adopted concepts |
| --- | --- | --- | --- |
| DEC | 7, 8, 9, 9, 11, 11, 11, 12, 14, 15, 15, 16 | 2, 2, 2, 2, 4, 3, 3, 3, 3, 3, 3, 3 | 0 |
| META | 7, 9, 11, 12, 15, 15, 15, 17, 17, 17, 17, 17 | 2, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4 | 7, two built from adopted concepts, one an iterate loop |
| META_WIPE | 7, 9, 11, 12, 13, 13, 13, 13, 14, 15, 17, 17 | 2, 2, 3, 3, 2, 3, 3, 3, 3, 4, 4, 3 | 6 |

- META's held-out solves at generation 12 were `add-k (k=5)`,
  `has-k (k=2)`, `caesar-cipher (k=3, n=2)` and `prepend-index-k (k=3)`.
  Three of these had never been solved in any committed run.
- On seed 44, the UFM comparator's VALIDATION at generation 12 was 2. On the
  registered seeds it is 1, 1, 1 (committed).

## Predictions

### TRAIN (determined by the development runs)

| Arm | TRAIN g12 | Sum of TRAIN over g1–g12 |
| --- | --- | --- |
| UFM | 9 (committed) | 88 |
| DEC | 16 | 138 |
| META | 17 | 169 |
| META_WIPE | 17 | 154 |

### Open outcomes (seeds 11/22/33, generation 12)

| ID | Comparison (every seed must satisfy it) | Predicted |
| --- | --- | --- |
| X1 | META `validation_agent` > UFM VALIDATION | PASS |
| X2 | META `validation_agent` > DEC `validation_agent` | PASS (moderate confidence) |
| X3 | META `validation_agent` > META_WIPE `validation_agent` | PASS (low confidence) |
| X4 | META VALIDATION (RSI-2 `assess`) > UFM VALIDATION | FAIL |

| ID | Readout | Predicted |
| --- | --- | --- |
| Y1 | META `validation_agent` g12, per seed | ≥ 3 on every seed |
| Y2 | VALIDATION tasks solved by META's agent that no committed run ever solved, per seed | ≥ 2 on every seed |
| Y3 | UFM-equivalence: `validation_agent` = VALIDATION for prior-only arms | holds (structural) |
| Y4 | Concepts adopted by META, and those built from an adopted concept | 7 and 2 (determined) |

## What the outcomes mean

- **X1 and Y2 pass.** What the system learned on TRAIN, including its search
  policy, its invented concepts and the decomposition skeleton choices,
  solves held-out tasks no earlier configuration solved, at the same
  per-task budget. That is transfer.
- **X2 passes.** The learned policy and self-invention add held-out
  capability beyond the hand-given skeletons with a fixed split.
- **X3 passes.** Persistent memory, meaning continual learning across
  generations, adds held-out capability beyond the wiped-memory learner.
- **X2 or X3 fails.** That component's contribution to transfer is not
  shown, whatever TRAIN shows.

How much of any gain is attributable to the designer-given skeletons is
bounded by DEC, which has the skeletons and nothing self-directed.

No claim about consciousness, superintelligence or the singularity is made
or tested. This is a 36-task program-synthesis corpus.
