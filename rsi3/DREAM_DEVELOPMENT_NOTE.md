# Dream practice: a development-only result, not registered

RSI3_META_DREAM is RSI3_META_HONEST plus `selfplay_dreams`. Each
generation it also practises every action on 64 dreams. A dream is a
program sampled from the fitted grammar and run on TRAIN public inputs,
using RSI-2's `dream_pairs` with a generation-keyed stream. The intent
was to give `behave:whole` practice on fixed-length outputs, which
skeleton-imagined tasks never have.

**Development run** (seed 44, `--skip-validation`, so VALIDATION and
RESERVE were never loaded):

| Arm | TRAIN g1–g16 | TRAIN g16 | CPU s |
| --- | --- | --- | --- |
| RSI3_META_HONEST (registered) | 10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29 | 29 | ~4,370 |
| RSI3_META_DREAM | 10 13 16 21 21 24 24 24 25 25 25 25 25 25 25 25 | 25 | 4,679 |

**What it changed.**

- **The loss.** DREAM loses HONEST's reverse family: reverse, append-k ×2
  and append-index-k. Its policy credits the prior highly, because dreams
  are samples of the very grammar the prior searches, so the prior finds
  them. That credit pulled chunks away from the fold action that finds
  reverse.
- **Measured.** On the slice shape at generation 12, its first choices
  were the prior (0.31), then `behave:whole` (0.19).

**Decision.** The arm is not registered and no held-out run was made. It
is a TRAIN regression, and practising on samples of the search's own
prior biases the policy toward that prior. A fairer version would weight
dreams by their distance from the prior, or practise only on dreams the
prior does not find in one chunk. That is not attempted here.
