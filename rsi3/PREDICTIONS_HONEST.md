# Honest self-play study: pre-registered predictions

Registered 2026-10-30, before any run of RSI3_META_HONEST on the registered
seeds (11/22/33). The runs use `experiment_config_honest.json` and
`python -m rsi3.longrun`. Misses will be scored in HONEST_RESULTS.md and
will not be reinterpreted.

## The question

In both behavioural arms the held-out solver routed its 64 candidates away
from behavioural search (BEHAVE_RESULTS.md, BEHAVE_FOLD_RESULTS.md). The
traced cause is how the meta-policy is trained:

- **Skeleton actions** are credited *by construction* on the tasks
  self-play imagines (`decompose:map` 341 of 344).
- **Behavioural actions** get their real one-chunk outcomes
  (`behave:whole` 125 of 2,224).

RSI3_META_HONEST is RSI3_META_BEH_FOLD with one change, `selfplay_honest`.
On every imagined task, the prior and every skeleton that fits are run for
one chunk too, and each action is recorded with its actual outcome. No
action is credited by construction.

Does an honestly trained policy route the held-out budget better?

## Disclosure

**TRAIN is determined** by the development run (seed 44,
`--skip-validation`, VALIDATION never loaded):

| Arm | TRAIN g1–g16 | TRAIN g16 | CPU s (dev) |
| --- | --- | --- | --- |
| RSI3_META_BEH_FOLD (registered) | 10 14 17 23 24 24 24 25 25 25 25 26 28 28 29 29 | 29 | ~2,500 |
| **RSI3_META_HONEST** | 10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29 | **29** | 4,030 |

The final TRAIN set is identical to FOLD's.

**What is known about VALIDATION, which is no longer an unseen set.**

- **Arms already run.** The per-task held-out outcomes and spending of
  RSI3_META_CONJ, RSI3_META_BEH, RSI3_META_BEH_BASE and RSI3_META_BEH_FOLD
  are known, and this change was designed after reading them.
- **This arm.** No VALIDATION outcome of RSI3_META_HONEST exists, and no
  VALIDATION example has been read. TEST was never opened.

**The policy, examined on TRAIN shapes only.** After the development run,
I compared the policies' first-choice probabilities on TRAIN task shapes.
Honest practice lowers the skeletons' optimism:

| Task shape | Action | FOLD policy | HONEST policy |
| --- | --- | --- | --- |
| map | `decompose:map` | 0.90 | 0.56 |
| map | `behave:map` | 0.81 | 0.80 (now first) |
| any | `decompose:any_list` | 0.80 | 0.43 |

It does not raise `behave:whole` on slice shapes (0.17 against
`filter_list` 0.29). The policy's shape features do not separate
fixed-length outputs from filters, and the imagined tasks contain no
fixed-length outputs.

## Predictions (seeds 11/22/33, generation 16)

| ID | Comparison or readout (every seed) | Predicted | Basis |
| --- | --- | --- | --- |
| — | HONEST TRAIN g16 | 29 | determined |
| H1 | HONEST agent > FOLD agent (5 / 5 / 5) | PASS (moderate) | forecast |
| H2 | HONEST agent > CONJ agent (5 / 5 / 5) | PASS (moderate) | forecast |
| H3 | HONEST agent ≥ 6 | PASS (low–moderate) | forecast |
| H4 | HONEST agent, point forecast | 6 (range 5–8) | forecast |
| H5 | `slice-k-n (k=3, n=3)` solved by HONEST's agent | no | forecast |

H4's basis:

- **Expected.** FOLD's five tasks (`add-k (k=5)`,
  `bool-identify-is-mod-k (k=2)`, `caesar-cipher (k=3, n=2)`,
  `prepend-index-k (k=3)`, `sum`), plus at least one of `has-k (k=2)` and
  the three caesar tasks behavioural search reaches without the library.
- **Not expected.** The slice (H5), `repeat-k`, `kth-largest`.

No claim about superintelligence, the singularity or consciousness is made
or tested.
