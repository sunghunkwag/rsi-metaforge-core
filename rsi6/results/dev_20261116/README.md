# Development measurements of 2026-11-16: design q, and edit effects against the training budget

Development only, on source categories, on scratch ledgers that began as copies of the committed
ledger at 4,505 records; the runs appended to them are here (`*_runs.jsonl`, every record with
its hash chain fields as written). None of this is evidence for an endpoint: no registration
covers it. It is preserved because it is a measured failure (the Owner's instruction 14: "If a
hypothesis fails, preserve the measured failure").

These runs shared the machine with the registered discovery stage of the open experiment, at a
lower priority (nice 10, later 19). Scores do not depend on load; the measured CPU-seconds of the
registered runs may have been inflated a little by the contention.

## 1. Design q: a search over the score and pick programs inside acquisition

Hypothesis: the open design (design o) cannot adapt its representation to the category it is
learning, because its programs change only through discovery across categories; moving a search
over the programs into acquisition, on the training problems of the category, should acquire
more. `rsi6/learner/design_q.py`; with no program rounds it is design o exactly (checked:
`q_equiv.py` in mode `equiv`, quadratic assignment, seed 9001, identical runs).

| comparison | runs | q0 minus o0, acquired, mean | per category |
|---|---|---|---|
| switch on one batch (`q_compare1.txt`) | 12 | -0.0031 | quadratic assignment -0.008, +0.014, +0.000; p-median 0, 0, -0.006; job shop -0.018, +0.032, -0.052; knapsack 0, 0, 0 |
| switch confirmed on a second batch (`q_compare2.txt`) | 16 | -0.0019 | quadratic assignment -0.021, -0.015, +0.001, +0.018; p-median 0, +0.001, -0.006, 0; job shop +0.035, -0.005, -0.068, +0.014; bin packing +0.009, 0, +0.007, 0 |

What failed: with one batch the programs switched in most program rounds (up to 8 of 9), on
noise; with the confirming batch they switched in 0 to 3; in neither case did the acquired score
rise on average, and the program rounds took training rounds from the learning principle (job
shop seed 9003: o0 0.875, q0 0.807, nothing learned beat the start on held-back problems). Within
the registered training budget (5 to 18 rounds of constructions on batches of four problems) a
search over programs inside acquisition is starved in the same way as discovery across
categories: the signal of a batch is weaker than the differences it would have to detect.

## 2. Edit effects and paired noise at two training budgets (`budget_scaling.py`, `.json`)

Eight single edits of generation 0 of design o, drawn uniformly over the edit cells with a fixed
generator, and generation 0, on job shop, p-median and quadratic assignment with four seeds, at
the registered search budget (train 40) and at train 200.

* CPU per run 7.1 and 27.5 seconds; generation 0's acquired score 0.640 and 0.645, its gain
  +0.021 and +0.027: five times the training budget buys almost nothing.
* Four of the eight edits change nothing measurable at either budget (every run identical to
  generation 0's), although the behaviour key counts them as changes: the liveness test misses
  edits that are semantically neutral.
* The harmful edits stay harmful at the larger budget (score/replace -0.129 and -0.123 over the
  categories; score/swap -0.096 and -0.042); none of the eight is beneficial at either budget.

## Reproduction

    PYTHONPATH=. python3 rsi6/results/dev_20261116/q_equiv.py quadassign 9001 equiv
    DEV_LEDGER=dev_q2.jsonl PYTHONPATH=. python3 rsi6/results/dev_20261116/q_equiv.py quadassign,pmedian,jobshop,binpacking 9001,9002,9003,9004 compare
    PYTHONPATH=. python3 rsi6/results/dev_20261116/budget_scaling.py run

(`q_dispatch.py` lets the kernel's design dispatch know design q in the development process
only; `rsi6/learner/designs.py` is pinned by the open registration until its last stage. The
first comparison was made before the second-batch rule was added to `design_q.py`; its q0 runs
were made by the code of commit 6522e23.)
