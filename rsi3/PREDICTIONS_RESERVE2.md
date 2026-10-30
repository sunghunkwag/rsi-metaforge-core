# RESERVE-FAR2 evaluation: pre-registered predictions

Registered 2026-10-30, before any solver ran a RESERVE-FAR2 task. No
example of any of these tasks has been read. Only their names were listed,
to define the partition (`rsi3/reserve.py`). Misses will be scored in
RESERVE2_RESULTS.md and will not be reinterpreted.

## Why

RESERVE-FAR, the earlier test of transfer to new families, has only 12
tasks, and its outcomes are now known (RESERVE_RESULTS.md). RESERVE-FAR2
is a second, untouched test of the same kind. It holds the 21 unselected
tasks in the families RSI-2's research drew its confirmation and audit
tasks from, without those tasks themselves:

- count-k (k = 0, 1, 3, 4, 5);
- drop-k (k = 0, 1, 3, 4, 5);
- remove-index-k (k = 2–5);
- remove-mod-k (k = 2, 3, 5);
- take-k (k = 1–4).

No split contains these families, and no RSI-3 run or design decision has
used them.

## The measurement

`python -m rsi3.reserve_eval --partition far2` runs each registered arm's
final learned solver (`longrun.agent_validation`, B_eval = 64, one
verifier query per task, seeds 11/22/33). It covers the same six arms and
checkpoints as RESERVE_RESULTS.md.

## Predictions (solved of 21, every seed)

| ID | Comparison or readout | Predicted |
| --- | --- | --- |
| S1 | HONEST FAR2 > CONJ FAR2 | PASS |
| S2 | HONEST FAR2 > FOLD FAR2 | PASS (moderate) |
| S3 | HONEST FAR2 ≥ BASE FAR2 | PASS (moderate) |
| S4 | HONEST FAR2, point forecast | 9 (range 5–13) |
| S5 | some arm solves at least 11 of 21 | FAIL (low confidence) |

S4 is based on the names only, read as routine descriptions. My guesses,
by family:

| Family | Guess | Expected for HONEST |
| --- | --- | --- |
| drop-k | `tail^k` | almost all |
| remove-mod-k | a filter with the `not`/`eq` witness | most |
| take-k, remove-index-k | cons deduction, if the policy routes there | a few |
| count-k | needs a filter inside `length` or a conditional fold | few or none |

No claim about superintelligence, the singularity or consciousness is made
or tested.
