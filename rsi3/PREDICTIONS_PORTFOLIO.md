# Portfolio study: pre-registered predictions

Registered 2026-10-30, before any run of RSI3_META_PORTFOLIO on the
registered seeds (11/22/33). It is also registered before the registered
RSI3_META_HONEST runs finished. Of those, only their plain VALIDATION
(2 / 2 / 2 through generation 12) had been seen in progress lines; no
`validation_agent` outcome. The runs use `experiment_config_portfolio.json`
and `python -m rsi3.longrun`. Misses will be scored in PORTFOLIO_RESULTS.md
and will not be reinterpreted.

## The question

No arm has yet combined the most TRAIN (RSI3_META_BEH_FOLD, 29/36) with
the most held-out capability (RSI3_META_BEH_BASE, 7/12).

- **The library arms.** Their behavioural pools are wide, because the
  system's own abstractions widen them. That pays on TRAIN, where budget
  accumulates.
- **The control.** Its pool is narrow and cheap, which pays at 64
  candidates per held-out task.

RSI3_META_PORTFOLIO is RSI3_META_HONEST with two changes:

1. **`behave_dual`.** Every behavioural problem is offered twice:
   - as `behave:<kind>`, built from the library and ordered by the fitted
     grammar;
   - as `behave0:<kind>`, built from RSI-2's primitives in a fixed order.

   The honestly practised policy chooses per task shape.
2. **`meta_fixed_length`.** A fixed-output-length flag joins the policy's
   task shape.

## Disclosure

**TRAIN is determined** by the development run (seed 44,
`--skip-validation`, VALIDATION never loaded):

| Arm | TRAIN g1–g16 | TRAIN g16 | CPU s (dev) |
| --- | --- | --- | --- |
| RSI3_META_BEH_FOLD (registered) | 10 14 17 23 24 24 24 25 25 25 25 26 28 28 29 29 | 29 | ~2,500 |
| RSI3_META_HONEST (development) | 10 14 17 22 24 25 25 25 25 25 25 26 28 28 29 29 | 29 | 4,030 |
| **RSI3_META_PORTFOLIO** | 10 13 15 16 21 21 24 24 24 24 25 27 28 29 29 29 | **29** | 2,831 |

The final TRAIN set is identical to FOLD's.

**VALIDATION is not an unseen set.** These changes were designed after I
read the per-task held-out outcomes and spending of CONJ, BEH, BASE and
FOLD. No VALIDATION example has been read, and TEST was never opened.

**The policy on TRAIN shapes** (development checkpoint; first-choice
probability among the actions each shape allows):

| TRAIN shape | Ranking |
| --- | --- |
| map (int or bool) | `behave0:map` 0.87–0.88, ahead of `behave:map` and `decompose:map` |
| filter | `behave0:filter` 0.90 |
| any | `decompose:any_list` 0.48, `fold_false` 0.48, `any` 0.47, `behave0:any_list` 0.46 |
| slice | still `decompose:filter_list` 0.22, `fold_nil` 0.18, `behave0:whole` 0.18 (the flag did not move it) |

## Predictions (seeds 11/22/33, generation 16)

| ID | Comparison or readout (every seed) | Predicted | Basis |
| --- | --- | --- | --- |
| — | PORTFOLIO TRAIN g16 | 29 | determined |
| P3 | PORTFOLIO TRAIN > BASE TRAIN (21) | PASS | determined |
| P1 | PORTFOLIO agent > FOLD agent (5 / 5 / 5) | PASS | forecast |
| P2 | PORTFOLIO agent > HONEST agent | PASS (moderate) | forecast |
| P4 | PORTFOLIO agent ≥ 6 | PASS | forecast |
| P5 | PORTFOLIO agent ≥ BASE agent (7) | PASS (moderate) | forecast |
| P6 | PORTFOLIO agent, point forecast | 7 (range 6–8) | forecast |
| P7 | `slice-k-n (k=3, n=3)` solved by PORTFOLIO's agent | no | forecast |

P6's basis:

- **Expected:**
  - `add-k (k=5)`;
  - `caesar-cipher (k=3, n=2)`;
  - `prepend-index-k (k=3)`;
  - `sum`;
  - through `behave0:map`: `bool-identify-is-mod-k (k=2)`,
    `caesar-cipher (k=1, n=3)` and `(k=1, n=4)`;
  - `has-k (k=2)`, about even odds.
- **Not expected:**
  - `caesar-cipher (k=2, n=5)`, which BASE also missed;
  - the slice;
  - `repeat-k`;
  - `kth-largest`.

If P4 and P5 pass, one arm holds both the most TRAIN (29/36) and the most
held-out capability (≥ 7/12). The held-out part comes from a designer-given
portfolio choice made by a self-trained policy. The TRAIN part comes from
the system's own abstractions inside the same search.

No claim about superintelligence, the singularity or consciousness is made
or tested.
