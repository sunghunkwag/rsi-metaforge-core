# Design s in development: the chains do not improve on unseen categories, and an improved improver changes nothing

Development, not evidence. The design is [`DESIGN.md`](DESIGN.md); what would be read, and how,
was committed before the table ran ([`PREDICTION.md`](PREDICTION.md), commit `c913c05`).

**None of the three statistics holds.** By the reading fixed beforehand: the chains do not
improve what they acquire on categories they did not read; an improved improver does not
matter in this list; the search adds nothing a uniform draw with the same gate would not.
Stage 2 (new categories, registration, repetition) is not run. Nothing was registered, no
category was built, the reserves and the sealed targets were not touched.

## The reading

Mean of the four folds after generation 4; 324 starts, 30 repetitions each
([`reading.json`](reading.json)).

| | Statistic | Mean | 5 % point | 95 % point | Holds if | |
|---|---|---|---|---|---|---|
| A | recursive: where the chains end, above their starts | +0.00110 | +0.00092 | +0.00128 | mean at least 0.005 and 5 % point above 0 | **no** |
| B | recursive minus frozen | +0.00000 | −0.00000 | +0.00001 | 5 % point above 0 | **no** |
| C | recursive minus random | +0.00016 | −0.00001 | +0.00035 | 5 % point above 0 | **no** |

The chains end a thousandth above where they start, a fifth of the gate's margin. A chain
whose improver is the current version ends where a chain ends whose improver stayed the start.
A uniformly drawn nominee with the same gate does about as well.

| Fold | Test categories | recursive | frozen | random | neighbour | recursive − frozen |
|---|---|---|---|---|---|---|
| 1 | quadratic assignment, quadratic 0-1 | +0.00354 | +0.00352 | +0.00255 | +0.00147 | +0.00001 |
| 2 | p-median, weighted tardiness | −0.00172 | −0.00173 | −0.00091 | −0.00061 | +0.00001 |
| 3 | bin packing, maximum clique | +0.00131 | +0.00131 | +0.00003 | +0.00021 | +0.00000 |
| 4 | job shop, knapsack | +0.00129 | +0.00129 | +0.00209 | +0.00104 | −0.00001 |

In fold 2 every arm ends *below* its starts: what passed the gate on bin packing and maximum
clique made weighted tardiness worse.

## Why

**Adoptions are rare, and the search does not make them likelier.** The search nominates in
about 40 % of generations; the gate adopts in 2 to 9 % (first generation, by fold: 2.4, 7.8,
4.5, 9.4 %). A version drawn uniformly from the list passes the same gate in 8.3, 7.2, 8.0 and
17.0 %. At the level of versions one evaluation is one run, whose score moves by 0.02 to 0.09
from seed to seed, while good and poor mechanisms differ by a few hundredths: a population
judged on two to eight runs each, and a held-back check on four, cannot tell them apart.

**What passes does not carry over.** On the categories the gate read, the recursive chains
gain +0.0008, +0.0038, +0.0017 and +0.0142; on the test categories +0.0035, −0.0017, +0.0013
and +0.0013.

**The comparison of improvers was hardly exercised.** The recursive and the frozen arm are one
chain until an adoption changes the improver. Their paths differ in 8, 48, 15 and 209 of 9,720
chains per fold (0.08 to 2.2 %). B is zero because almost nothing happened, not because many
changed improvers were tried and found equal. This is a limit of the chains as they were
specified: four generations at these adoption rates give the improved improver almost no
second generation to work in.

**Where improvers were compared directly, the better acquirers are not the better
improvers.** Every one of the 324 mechanisms as improver for one generation from the same 40
incumbents (6 repetitions each): the rank correlation between what a mechanism acquires on the
test categories and what it yields there as improver is **−0.28** (5 % point −0.31, 95 % point
−0.23; by fold −0.31, −0.71, −0.08, −0.04). The third of the list that acquires most yields
+0.00002 as improvers, the third that acquires least +0.00045 (difference −0.00043, 95 % point
−0.00036). The reason was named in `PREDICTION.md`: many categories prefer a small spread for
acquiring (`model.sigma` 0.2), and a search with a spread of 0.2 steps hardly moves on a list.
The premise design s was built to exercise, that a mechanism which acquires better is thereby
a better improver, is false here in sign, at a size that does not matter.

## What the tables say about the list

Descriptive; nothing here was fixed beforehand ([`table_effects.txt`](table_effects.txt),
[`table_neighbours.txt`](table_neighbours.txt), [`table_loco.txt`](table_loco.txt)). 36,864
measured runs (288 different searches, eight categories, 16 seeds), 112 CPU-hours.

* **Mean over the eight categories:** the list runs from 0.728 to 0.809. Generation 0 of the
  first design is at 0.792 (rank 142 of 324), the version process d adopted at 0.802 (rank 33).
* **Around generation 0** three changes of one field gain, and they are the same gain by three
  routes, more rounds of learning in the same budget: `adapt.race` 1 (+0.0170, standard error
  0.0052), `model.pop` 8 (+0.0115, 0.0057), `model.batch` 2 (+0.0099, 0.0058).
* **Around the adopted version nothing gains.** The largest is `model.sigma` 0.2 at +0.0035
  (standard error 0.0042): +0.032 on quadratic assignment, −0.056 on weighted tardiness. The
  two new procedures there: `adapt.race` 1 +0.0010 (0.0038), `adapt.spread` self +0.0009
  (0.0048). What is clear around it is what is worse: `model.batch` 8 −0.0385, `model.batch` 4
  −0.0099, `model.elite` 0.5 −0.0059.
* **The two new procedures over the whole list.** Racing helps on average (bin packing +0.015,
  maximum clique +0.008, job shop −0.001, knapsack +0.002, p-median +0.003, quadratic assignment
  +0.017, quadratic 0-1 +0.035, weighted tardiness +0.005) because it gives mechanisms with
  large batches the rounds they lack; once a mechanism has its rounds it adds nothing. The
  self-adapting spread is level or slightly worse (−0.009 to +0.001 by category).
* **The best possible use of the tables finds nothing above the adopted version.** Choose, with
  all 16 seeds of seven categories in hand, the version of the list with the best mean there,
  and score it on the eighth: against the adopted version **−0.0070** on average (5 % point
  −0.0143, 95 % point +0.0003); against generation 0 +0.0029 (−0.0060, +0.0119). Choose the
  best on the first eight seeds of all categories (+0.0117 over the adopted version there) and
  score it on the other eight: −0.0072.

The last point is the one that settles it. An improver can only find what the list holds, and
the list holds no version that beats the adopted one on a category it was not chosen on. The
32 versions ranked above the adopted one are above it by the luck of 16 seeds. No improver,
this one or a better one, has a second step to find here; and the first step, from generation
0, is small enough (+0.003 on a held-out category with every table in hand) that chains of
noisy searches cannot collect it either.

This is what `DESIGN.md` said before the table ran ("this design is not expected to lift the
top"), now measured: where the first design stands, its acquisition is bounded by what the
weights of its policy can express. Changing how it searches for those weights, by a setting or
by a procedure that adapts, moves it down easily and up not at all.

## Predictions, scored

| | Predicted | Outcome |
|---|---|---|
| A holds | 0.60 | did not hold: +0.0011 where 0.005 was needed |
| B holds | 0.25 | did not hold |
| C holds | 0.40 | did not hold |
| A, B and C hold | 0.15 | no |
| Mean of B | between −0.002 and +0.003 | +0.000005 |
| From the adopted version almost no chain changes its version | | so in folds 1 to 3 (0 of 30 in the two improver arms); in fold 4, 8 of 30 changed, and the 30 end −0.0002 on average |
| From generation 0 some chains adopt `model.batch` 2 where the gate is sensitive to it | | not as predicted: chains from generation 0 changed in 0, 23, 63 and 13 % of repetitions, to many different versions, most with racing on and few with `model.batch` 2; over the 30 repetitions they end −0.0059, +0.0029 and +0.0023 on the test categories in the folds where any changed |

The prediction for A was wrong in the direction that matters: the design was expected to show
at least that chains from poor starts climb on unseen categories, and they barely do.

## What was looked at between fixing the reading and reading it

A table of the list on quadratic assignment alone, measured on this session's machine with
seeds 731901 to 731908 ([`pilot/`](pilot/)), after `PREDICTION.md` was committed; the main
effects of the tables while the last three jobs were still running; the chains of folds 1 and
2 while folds 3 and 4 ran. No rule and no parameter was changed after any of them:
`scripts/folds.py`, `rsi6/meta/chain_s.py` and `rsi6/learner/design_s.py` ran as committed in
`c913c05`, with the defaults.

## Checked

* The table: run `45274258641` on the runners (42 jobs, all succeeded; the unit tests of the
  design ran in every job). Eight categories, each with seeds 731001 to 731016 and all 324
  versions; the untrained score is the same for every version of a seed, as the chains assume.
* The chains repeat: 8 starts of folds 1 and 3 (30 repetitions, four arms) run again gave the
  stored paths and nominees exactly. The reading computed again from the stored chains is the
  stored reading exactly.
* With the new fields off, design s is the first design run by run
  (`rsi6/tests/test_design_s.py`, in the workflow of the RSI-6 tests).

## Files

| | |
|---|---|
| `DESIGN.md`, `PREDICTION.md` | the design and the reading, as committed before the run |
| `reading.json` | every statistic, per fold and for the mean of the folds, per generation |
| `table_effects.txt`, `table_neighbours.txt`, `table_loco.txt` | the descriptive readings of the tables |
| `artifacts/tables.tar.gz` | the 40 table files of the run |
| `artifacts/records.tar.gz` | the run records behind them (one per measured run) |
| `artifacts/chains.tar.gz` | the chains and the one-generation comparison of all improvers, per fold |
| `scripts/folds.py` | the chains and the reading: `python scripts/folds.py TABLES OUT` |
| `scripts/grid_effects.py`, `grid_neighbours.py`, `grid_loco.py` | the descriptive readings |
| `scripts/oracle_budget.py`, `oracle_budget_rows.json`, `scripts/g1_percat.py` | the diagnostics of `DESIGN.md` |
| `pilot/` | the one-category table measured locally |

To repeat the reading: unpack `artifacts/tables.tar.gz` into a directory and run
`python rsi6/results/design_s_20261124/scripts/folds.py <directory> <out>` from the repository
root (about 50 minutes on two cores).
