# A second choice, fixed before its run

2026-11-22, 20:31 UTC (the time of the commit that added this file).

## What had been seen when this was written

* The landscape on seven categories (the six of `PREDICTION.md` and knapsack). Its partitioning
  and setcover jobs were still running; nothing of them had been read.
* Plan `dev-pair` (run 45062991243), seventeen of its eighteen jobs: all categories, with twelve
  of the sixteen partitioning seeds. Read with `scripts/reading_2.py` as committed before it.

What they showed:

* **The fixed choice of `PREDICTION.md` did not hold.** `assess.holdback` 0.25 → 0.3 on the new
  seeds: M9 +0.0024, 5 % point −0.0062. Jobshop +0.012 where the landscape had +0.059,
  quadassign +0.008 where it had +0.049. Reading 2 of that file is negative for its choice (to be
  stated on all eighteen jobs when the last one is in).
* **One of the four changes measured for comparison is above zero on the new seeds:**
  `model.batch` 4 → 2, M9 +0.0187, 5 % point +0.0105, CPU 1.03 times generation 0's. By
  category: setcover +0.139 (16 seeds, 13 above, 3 below), quadassign +0.016, partitioning
  +0.010, pmedian +0.005, binpacking +0.003, knapsack +0.001, jobshop −0.006, the two
  prediction categories 0. `model.sigma` 1.0 → 0.2 is above zero by less (M9 +0.0062, 5 % point
  +0.0006) and is below zero in jobshop (−0.029, 7 runs above, 19 below).
* **Why a change of the batch could matter.** A run of generation 0 gets few rounds of learning
  from the registered budget (new seeds, median: binpacking 1, pmedian 1, quadassign 2,
  knapsack 3, jobshop 10), and what it learned is then kept or dropped as a whole by a check on
  the held-back problems (kept in 97 % of the runs on binpacking, 88 % quadassign, 75 % jobshop,
  25 % pmedian, 0 % knapsack; the gain is exactly 0 when it is dropped). Halving the batch
  doubles the rounds at the same counted budget.

What speaks against taking `model.batch` 2 at face value: it was one of four comparisons, not
the fixed choice; four fifths of its M9 is one category (setcover); with each category cut to
[−0.03, +0.01] as the continued process counts (amendment 2) its value is +0.0037, below the
margin of 0.005; and the nominees of rounds 1 and 2 were of this kind, carried by one category,
and failed their gates.

## The choice, fixed here

`model.batch` 4 → 2.

## Its reading, fixed here

Plan `rsi6/runs/dev-pair-2.json`: generation 0, `model.batch` 2, and for comparison `model.pop`
16 → 8, `model.sigma` 1.0 → 0.2 and `model.batch` 2 with `model.pop` 8 together; seeds 730201 to
730232, on partitioning and setcover 730201 to 730216; none used by any earlier run. Read with
`scripts/reading_2.py`; the option `--leave-out` it got with this file only drops the named
categories before anything is computed.

* *Confirmed on the pool a second time*, now as the fixed choice: the 5 % point of M9 is above 0
  and the CPU over the nine categories is at most 1.15 times generation 0's.
* *Not carried by one category alone*: the same with setcover left out of the mean (M8, the
  eight other categories): its 5 % point above 0. If the first holds and this does not, the
  change is a setcover effect and is reported as that.
* Reported beside both: the value of amendment 2 against the margin 0.005. Expected below the
  margin; if so, the continued process as registered would not adopt this change whatever a
  registered test showed, and that is said.
* The three comparisons decide nothing. One thing is looked at and stated either way: whether
  the two changes that add rounds of learning (`model.batch` 2, `model.pop` 8) together are at or
  above `model.batch` 2 alone.

As in `PREDICTION.md`: the nine categories are the source pool, so this is development. It can
say whether a registered test of this one change on categories it was not chosen on is worth
its cost. Registering one is the Owner's decision.
