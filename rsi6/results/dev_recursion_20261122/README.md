# The recursion question, asked where it can have an answer: no answer from this run

2026-11-22 to 23. Development only: four light categories of the pool, scratch ledgers, seeds
nothing else uses. `PREDICTION.md` fixed the reading before the run (commit `a636c70`); plan
`rsi6/runs/dev-recursion.json`, run 45080814109, twelve repetitions, all finished.

**The reading: no signal, and neither improver produced a next step.** In twelve repetitions no
arm ended with a nominee: not the changed learner as improver, not generation 0 as improver,
not the random proposer. Every value is 0, every difference is 0 (`reading.json`). By the rule
fixed beforehand this says nothing about which improver is better. `PREDICTION.md` expected
this, with a probability of about 0.9.

| Arm | Rounds | Rollouts per search (mean) | Different versions among them (mean) | Searches whose learned version differed from the start | Kept by the final check |
|---|---|---|---|---|---|
| recursive (improver: generation 0 with `model.batch` 2) | 18 to 23 | 649 | 45 | 1 of 12 | 0 |
| frozen (improver: generation 0) | 8 to 11 | 603 | 42 | 0 of 12 | 0 |
| random (no learning) | 8 to 12 | 615 | 94 | 3 of 12 had a candidate above the start | 0 |

## Why it produced nothing: the construction, not the question

The improver is the learner's population search, transcribed, with a version for a policy. Two
things made it too weak to find a step, and both are in the construction:

* **It stops exploring after a few rounds.** The learner shrinks the spread of its candidates
  by a tenth every round. On real-valued weights that is refinement. On a grid of field values
  a spread below half a grid step produces the mean again: after about four rounds nearly every
  candidate is the start itself. Of about 650 rollouts in a search only about 45 were of
  different versions. Twice as many rounds (the recursive arm) are then twice as many rounds of
  the same version.
* **A candidate is measured on two or four runs.** The changes known to help on these four
  categories are of the order of +0.005 to +0.02; one run varies by several times that.

So the run does not show that a changed learner cannot be a better improver. It shows that
this improver, at this budget, on these categories, improves nothing, whoever runs it.

## What an answer would take

* An improver that keeps exploring on a discrete space (the same selection in rounds, without a
  spread that shrinks below the grid), and candidates measured on enough runs to see +0.01.
* Categories on which there is something to find at a price that allows thousands of runs.
  Since the gate of process d the pool has one: on quadratic 0-1 a single field is worth
  +0.055 (`../gate_d1_20261122/`).
* A reading fixed before the run, as here, and a registered version only if development shows
  a signal.

None of this is built. It is a new design of the improver, not a setting of this one.

## Files

`reading.json` (the reading), `scripts/read.py`, `artifacts/recursion.tar.gz` (what the twelve
jobs uploaded: one JSON and the run records per repetition).
