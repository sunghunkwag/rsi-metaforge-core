# What is read from the table of design s, fixed before it runs

Committed before the plan `rsi6/runs/dev-grid-s.json` is pushed to the runners. Development:
none of this is evidence. The design is `DESIGN.md`.

## What had been seen when this was written

* The diagnostics in `DESIGN.md` (budget, the scan read per category).
* On this session's machine, while writing the code: the comparison of design s (new fields
  off) with the first design on 12 runs (identical); a smoke run of `dev_grid` (6 mechanisms,
  a quarter of the budget, one seed); and six versions on quadratic assignment with four seeds
  (739911 to 739914), to see that the two new steps stay inside the budget. Their means, for
  the record: `model.batch` 2: 0.5035; with `adapt.spread` self: 0.4766; with `adapt.race` 1:
  0.4630; `model.batch` 8 with race: 0.4805; 8 with race and self: 0.4297; 8 alone: 0.4080.
  Four seeds on one category: they decided nothing about the design.
* A table of the whole list on quadratic assignment alone (seeds 731901 to 731908) was being
  measured on this session's machine to test `chain_s.py` on real rows. Its numbers had not
  been looked at when this file was committed.
* The unit tests of the chains on tables with a made-up landscape.

Fixed before any of that: the list, `TAU` (0.7), the plan of a raced round, one step of the
list as one unit of the search. None of them was tuned on a measurement.

## The table

`rsi6/runs/dev-grid-s.json`: all 324 mechanisms on quadratic assignment, p-median, bin packing,
job shop, quadratic 0-1, weighted tardiness, maximum clique and multidimensional knapsack,
seeds 731001 to 731016, the run budget of the registrations. (Set covering and graph
partitioning are left out for their cost, about 140 and 270 CPU-seconds a run; project
scheduling and the two prediction categories because no change of these fields has moved
them.)

## The chains

`scripts/folds.py`, with nothing changed after the tables are seen:

* Four folds. The categories are paired (quadratic assignment with quadratic 0-1, p-median with
  weighted tardiness, bin packing with maximum clique, job shop with knapsack: one category of
  the old pool with one that was held out until 2026-11-22). In fold k pair k is the test set,
  the next pair the gate set, the other two pairs the discovery set. Every category is test
  once, gate once, discovery twice.
* In every fold: every one of the 324 mechanisms as a start, 30 repetitions, 4 generations,
  the four arms of `DESIGN.md`, seed 1, `train` 40.
* The gate reads seeds 731001 to 731008 and the first half of the fresh instances of its
  categories, the confirmation seeds 731009 to 731016 and the other half.
* Read on the test categories of each fold with all 16 seeds: per arm, the mean over starts and
  repetitions of the acquired score of the chain's version after generation 4 minus that of
  its start. A statistic is the mean of the four folds. Its 5 % point comes from 2000
  resamplings of the seeds of the test categories, the chains kept as they ran.

## The reading

Three statistics, after generation 4, mean of the four folds:

| | Statistic | Holds if |
|---|---|---|
| A | recursive: where the chains end, above their starts | mean at least 0.005 and 5 % point above 0 |
| B | recursive minus frozen | 5 % point above 0 |
| C | recursive minus random | 5 % point above 0 |

* **A, B and C hold:** in this list, on categories the chains did not read, chains improve
  what they acquire, they end higher when the improver is the improved version than when it
  stays the start, and the search adds to what the gate alone would let through. Stage 2 of
  `DESIGN.md` is then prepared: new categories, registration, repetition on new seeds.
* **B does not hold:** an improved improver does not matter in this list (and if the mean of B
  is below zero with its 95 % point below zero: a version that acquires better is a worse
  improver here). Stage 2 is not run. This is the reading that counts against the design.
* **B holds and C does not:** the difference between the improvers is real but a uniform draw
  with the same gate does as well; the search is not what improves the chains. Stage 2 is not
  run.
* **A does not hold:** the chains do not improve on unseen categories at all, whatever B and C
  say. Stage 2 is not run.

Reported with them and deciding nothing: every generation, every fold, the neighbour arm, how
often a generation nominates and adopts, the chains from generation 0 of the first design and
from the version process d adopted, and the *alignment*: over the 324 mechanisms, the rank
correlation between what a mechanism acquires on the test categories and what one generation
of it as improver yields there from 40 incumbents drawn from the list (6 repetitions each).

## Predictions

| | Probability |
|---|---|
| A holds | 0.60 |
| B holds | 0.25 |
| C holds | 0.40 |
| A, B and C hold | 0.15 |

Expected mean of B: between −0.002 and +0.003. Expected for the two named starts: almost no
chain from the adopted version changes its version; from generation 0 some adopt `model.batch`
2 where the gate set is sensitive to it.

Why B is not likely: at the level of versions an evaluation is far noisier than a construction
is at the level of weights, so a mechanism that acquires better (small batches, more rounds)
is not obviously the better improver; and a spread of 0.2 steps, which some categories prefer
for acquiring, hardly moves on a list.
