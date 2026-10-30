# RESERVE evaluation: pre-registered predictions

Registered 2026-10-30, before any reserve task was run by any solver. No
example of any reserve task has been read. Only the names were listed, to
define the partitions (`rsi3/reserve.py`). At registration the registered
RSI3_META_PORTFOLIO runs had not finished, and only their in-progress plain
VALIDATION had been seen. Misses will be scored in RESERVE_RESULTS.md and
will not be reinterpreted.

## Why

VALIDATION is no longer an unseen set. The last two studies were designed
after its per-task outcomes were read (HONEST_RESULTS.md). TEST stays sealed
under the owner's directive.

RSI-2's corpus has 207 eligible tasks, of which only 60 were ever selected.
`rsi3/reserve.py` defines, from the committed manifests alone, two
partitions that no split, no run and no design decision has touched:

- **RESERVE-NEAR (100 tasks).** Unselected tasks in the families of the 60
  selected ones: other parameter values of known routines. They come from
  22 families.
- **RESERVE-FAR (12 tasks).** Unselected tasks in the 12 families that
  RSI-2's research left unused:
  - count-head-in-tail;
  - empty;
  - evens, odds;
  - head, last;
  - is-odds, is-primes;
  - min, product;
  - repeat, repeat-many.

  No split contains these families.

Records are built by RSI-2's own normalizer: ten public inputs, the rest
hidden for the frozen verifier.

## The measurement

`python -m rsi3.reserve_eval` runs each arm's final (generation 16)
learned solver at B_eval = 64 per task, with one verifier query per task,
for seeds 11/22/33. It is `longrun.agent_validation` itself. The harness
was checked by reproducing RSI3_META_HONEST's recorded final VALIDATION
exactly, on every seed: the same 9 tasks and the same per-action spending.

The arms, using each one's registered final checkpoint:

| Arm | Registered results |
| --- | --- |
| RSI3_META_CONJ | `results_cascade` |
| RSI3_META_BEH | `results_behave` |
| RSI3_META_BEH_BASE | `results_behave` |
| RSI3_META_BEH_FOLD | `results_behave_fold` |
| RSI3_META_HONEST | `results_honest` |
| RSI3_META_PORTFOLIO | its registered run, when complete |

## Predictions (solved counts, every seed)

| ID | Comparison or readout | Predicted |
| --- | --- | --- |
| Q1 | HONEST NEAR > FOLD NEAR | PASS |
| Q2 | HONEST NEAR > CONJ NEAR | PASS |
| Q3 | HONEST NEAR > BASE NEAR | PASS (moderate) |
| Q4 | HONEST NEAR > BEH NEAR | PASS |
| Q5 | BASE NEAR > BEH NEAR (the library cost at 64 replicates) | PASS (moderate) |
| Q6 | PORTFOLIO NEAR > HONEST NEAR | FAIL (low confidence) |
| Q7 | HONEST NEAR, point forecast | 60 of 100 (range 45–75) |
| Q8 | HONEST FAR, point forecast | 3 of 12 (range 1–6) |
| Q9 | HONEST FAR > CONJ FAR | PASS (low confidence) |

## What the outcomes mean

- **Q1–Q4 pass.** HONEST's held-out advantage on VALIDATION survives on
  100 tasks that no design decision has seen. The VALIDATION exposure did
  not manufacture it.
- **They fail.** The 9/12 was, at least in part, fitted to VALIDATION
  through design, and would be reported as such.
- **FAR.** This partition measures transfer to unseen families. It is the
  harder and smaller test.

No claim about superintelligence, the singularity or consciousness is made
or tested.
