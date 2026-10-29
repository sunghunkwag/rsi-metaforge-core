# Behavioural fold follow-up: pre-registered predictions

Registered 2026-10-30, before any run of RSI3_META_BEH_FOLD on the
registered seeds (11/22/33). It is also registered before the registered
RSI3_META_BEH runs (PREDICTIONS_BEHAVE.md) finished.

Correction, made in the commit after the registration commit and before
any FOLD run: the first version said no VALIDATION outcome of a
behavioural arm had been seen. That was wrong. The progress lines of the
registered BEH and BASE runs print plain VALIDATION (RSI-2's `assess`),
and I saw them through about generation 12:

- BEH: 1 / 1 / 1;
- BASE: 2 / 2 / 2.

Their `validation_agent` outcomes, on which R2, R4 and R5 are scored, had
not been seen. Plain VALIDATION is not a forecast here. The
runs use `experiment_config_behave_fold.json` and `python -m rsi3.longrun`.
Misses will be scored in the results file and will not be reinterpreted.

## The question

RSI3_META_BEH gains the slices and the mod tasks over the cascade arm. It
loses the cascade arm's reverse family, because the fold skeleton never
reached reverse's hole under its reshaped grammar.

This follow-up adds one designer-given action, the **behavioural fold**
(`behave.StepPool`):

- **Steps.** Closed steps `lambda acc x. body` are built bottom up, one per
  behaviour on probe pairs from the public inputs.
- **Folds.** Each step is folded from every init, and over every list of
  size 1–2 in the pool.

Everything else is RSI3_META_BEH unchanged. If reverse comes back, does the
system's own conjugation rebuild the append cascade on it? Does any of this
move held-out capability?

## Disclosure

**TRAIN is determined.** TRAIN is seed-independent. The development run
(seed 44, `--skip-validation`, VALIDATION never loaded) fixes it:

| Arm | TRAIN g1–g16 | TRAIN g16 | CPU s (dev) |
| --- | --- | --- | --- |
| RSI3_META_CONJ (committed) | 7 8 10 11 11 13 15 16 17 17 17 17 18 20 20 21 | 21 | 4,019 |
| RSI3_META_BEH (development) | 11 14 15 16 23 23 24 24 25 25 25 25 25 25 25 25 | 25 | 3,344 |
| **RSI3_META_BEH_FOLD** | 10 14 17 23 24 24 24 25 25 25 25 26 28 28 29 29 | **29** | 2,351 |

FOLD solves everything BEH solves, plus:

| Generation | Task | How |
| --- | --- | --- |
| 12 | reverse | the fold action: `fold (lambda acc x. cons x acc) nil l` |
| 13 | append-k (k=1) and (k=4) | conjugation by the system's own reverse |
| 13 | (RSI-2's MDL learner) | compresses the step (support 5) and reverse (support 3) into its library |
| 15 | append-index-k (k=1) | conjugation with the compressed reverse |

Seven TRAIN tasks remain unsolved:

- dup;
- rotate-k;
- kth-smallest, and kth-largest ×2;
- index-head;
- has-head-in-tail.

**Earlier exposure.** The exposure listed in PREDICTIONS_BEHAVE.md applies:
the VALIDATION task names were seen, and CONJ's per-task agent spending was
read. The only outcomes of RSI3_META_BEH or RSI3_META_BEH_BASE seen are
the in-progress plain VALIDATION values above; no `validation_agent`
outcome of either has been seen. No VALIDATION example has been read, and TEST was never opened.

**Comparators.** These are the registered RSI3_META_BEH runs (in progress
at registration) and the committed RSI3_META_CONJ runs.

## Predictions (seeds 11/22/33, generation 16)

| ID | Comparison or readout (every seed) | Predicted | Basis |
| --- | --- | --- | --- |
| R1 | FOLD TRAIN > BEH TRAIN | PASS (29 vs 25) | determined |
| R3 | FOLD TRAIN > CONJ TRAIN | PASS (29 vs 21) | determined |
| R2 | FOLD agent > BEH agent | FAIL (equal) | forecast |
| R4 | FOLD agent ≥ 6 | PASS | forecast |
| R5 | FOLD agent, point forecast | 8 (range 6–10), the same tasks as BEH's | forecast |
| C3 | the cascade readout: reverse g12, append-k ×2 g13, append-index-k g15 | as in development | determined |

R2's basis: VALIDATION has no task in the reverse or append family. Its
fold-shaped task, `sum`, should already be within reach of the fold
skeleton both arms share. So the fold action should add TRAIN tasks and
no held-out ones. If FOLD's agent scores higher, it is reported as found;
if lower, as the cost of one more action sharing 64 candidates.

No claim about superintelligence, the singularity or consciousness is made
or tested.
