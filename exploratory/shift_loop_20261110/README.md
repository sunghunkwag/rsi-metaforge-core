# Shift loop: an exploratory test of four saturation-breaking ideas

**Status: exploratory, report-only, not part of the rsi5 package and not a registered
result.** Requested by the Owner on 2026-11-10 after the Phase 1 gate failed. It asks one
question: if the unchanged rsi5 engine is wrapped in a loop that modifies its own search
vocabulary, does improvement compound across generations by itself?

Everything here runs on the exposed partitions. The machinery was designed after the
FRESH-1 failures of Phase 1 had been read, so no number here is a clean test and none may
be quoted as a result of the package. A claim needs J's sealed pools.
[`PREDICTIONS.md`](PREDICTIONS.md) was written before the runs it predicts and says how
the outcome is judged.

## What was built

The rsi5 engine (`rsi5/engine/bottomup.py`) is used unchanged. Around it:

| Part | File | What it does |
| --- | --- | --- |
| S, spec shift | `hybrid.py` | An element-wise or value-filter task is re-posed as an `int -> element` problem and the solution lifted back with `map` / `filter`. |
| F, fusion (idea 4) | `hybrid.py` | Two partial solutions and a separating predicate from the engine's pools are merged into one `if` term, found by bit masks over the public examples. |
| C, constants (SMT stand-in) | `hybrid.py` | Integers abduced from the examples (differences, ratios, new output values, decision boundaries) become size-1 constants. No SMT solver exists under the standard-library rule. |
| L, compression | `compress.py` | Verified programs are anti-unified into new named symbols by description-length gain; symbols are inlined before a term leaves the engine. |
| A, apoptosis (idea 1) | `loop.py` | A move that cuts 60% of each space's symbols, least used first; a milder move cuts unused symbols only. |
| E, entropy (idea 2) | `hybrid.py` | A move that turns on seeded random mutation of near-miss programs on a tenth of the budget. |
| T, rollback (idea 3) | `loop.py` | A rejected move is banned; when no move is accepted the loop rolls back one accepted step, bans it and branches again. |

The loop tries the moves compress, apoptosis, unused, entropy at each state. A move is one
run of every task at the per-task budget and is accepted only if verified solves on the
learning partitions rise. Held-out partitions are run each time for the record and never
consulted. Process layout as in `rsi5/phase1.py`: workers are forked before any partition
is loaded and receive public examples only; the driver holds the frozen verifier (one
query per task per run).

## Results so far (restored vocabulary, 10^4 candidates per task unless stated)

Generation 0, no learned symbol, 338 tasks (`results/gen0_*.txt`):

| Machinery | Solved | Held-out 202 | FRESH-1 (33) |
| --- | --- | --- | --- |
| registered engine | 89 | 32 | 4 |
| harness, everything off | 89 | 32 | 4 |
| S | 129 | 49 | 10 |
| S + C | 128 | 48 | 10 |
| S + F everywhere | 151 | 68 | 20 |
| S + C + F everywhere | 152 | 69 | 20 |
| S + C + F in the element space only | 141 | 61 | 19 |
| S + C + F everywhere, at 10^5 | 173 (registered 119) | 84 | 20 |

The harness with everything off reproduces the registered counts partition by partition.
Fusion at the whole-list level passes the verifier with nonsense programs for boolean
tasks (`has-k` as `if (is_empty xs) false (not (is_prime (head xs - 4)))`), so the loop
uses fusion in the element space only. C adds nothing.

The loop, configuration A (learn TRAIN + NEAR, 136 tasks; held out 202; 24 runs;
`results/loopA_1e4.txt`):

| Accepted move | Learning | Held-out |
| --- | --- | --- |
| generation 0 | 80 | 61 |
| apoptosis | 84 | 53 |
| compress | 94 | 55 |
| compress | 97 | 56 |

Three more branches after rollback all stop at 97. Configuration B (learn the six
single-routine partitions, 214 tasks; held out FRESH-2 and COMPOSE-24, 124 tasks; 23
runs): 121 / 20, apoptosis 123 / 19, compress 127 / 26, then nothing.

Ablations of configuration A's best state (`results/controls.txt`): without the depth-2
symbol `s4_1` learning falls to 94; without `s3_1` and `s4_1` to 80; the cut alone gives
84 / 53; the learned symbols without the cut give 90 learning and 62 held-out. A random
60% cut of generation 0 gives 50 learning. Entropy was never accepted.

## Reading, before the controls are complete

- The loop adapts itself to its learning distribution for two or three accepted steps and
  then saturates. In configuration A a second-generation symbol is defined on a
  first-generation one and carries the last gain.
- Held-out solves fall in configuration A (61 to 56): the vocabulary is cut by
  learning-set usage and loses what other distributions need.
- Generation-0 machinery run once at 10^5 solves more held-out tasks than either loop
  after about 2.4 x 10^5 cumulative candidates per task (78 against 56 in A, 28 against 26
  in B).
- The large gains (89 to 141) come from S and F, which were designed by hand. The loop's
  moves rearrange a vocabulary; none creates a new kind of search.

Not recursive self-improvement by the four criteria of `PREDICTIONS.md`.

## Open items

- The equal-cumulative-budget control at 2.4 x 10^5 and the 10^5 confirmation of the best
  states were still running when this was written.
- `compress.py` was written by a sub-agent and has not had its independent adversarial
  test; it round-trips the 80 programs of the real learning corpus.
- An independent review of the harness (information flow, budget fairness, semantics) was
  running when this was written. Uncounted work exists: the bit-mask scan of fusion, the
  reference re-checks, compression in the driver.
- The generalisation audit (`audit_hybrid.py`) covers FRESH-1, RESERVE-FAR2 and COMPOSE-24
  only, on a narrow value range.

## Run it

```bash
export PYTHONPATH=$PWD:$PWD/exploratory/shift_loop_20261110 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python exploratory/shift_loop_20261110/hybrid.py 10000 -,S,SCf OUT.json 4      # generation 0 by component
python exploratory/shift_loop_20261110/loop.py 10000 SCf OUT.json A 4 --max-runs 24 --random-control
python exploratory/shift_loop_20261110/state_run.py exploratory/shift_loop_20261110/results/loopA_1e4.json 10000 check
python exploratory/shift_loop_20261110/audit_hybrid.py exploratory/shift_loop_20261110/results/gen0_1e4.json
```

Standard library and NumPy only; no transformer or attention layer; no learned controller.
Attribution: Intelligence Research Project.
