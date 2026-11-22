# Written before three of the nine categories were read

2026-11-22, 19:50 UTC. The landscape (`rsi6/experiments/dev_landscape.py`, plan
`rsi6/runs/dev-landscape.json`, GitHub Actions run 45059214153) measures generation 0 of the
first design and every single-field change of it on the nine categories of the source pool.
At this time eight of its eighteen jobs are finished. **Read so far** are
forecasting, regression, quadassign, pmedian, binpacking (a, b) and jobshop (a, b), 8 seeds each.
**Not finished and not read**: knapsack (a, b), partitioning (1 to 4), setcover (1 to 4).
This file fixes a choice and three readings before those arrive. The commit time of this file
against the completion times of those jobs is the check.

## What the six categories say

`interim/loco_six_categories.json` (script `scripts/landscape_loco.py` as committed with this
file). Each category in turn is left out, the change with the largest value on the other five
is chosen by the statistic of the continued process (amendment 2; CPU at most 1.15 times
generation 0's), and what it does on the category left out is read.

| Left out | Chosen on the other five | On the category left out (acquired, gain) | Place among the 85 changes there |
|---|---|---|---|
| binpacking | `assess.holdback` 0.25 → 0.3 | +0.0009, +0.0009 | 0.98 |
| forecasting | the same | −0.0001, −0.0001 | 0.06 |
| jobshop | the same | +0.0591, +0.0591 | 0.98 |
| pmedian | the same | +0.0100, +0.0100 | 0.99 |
| quadassign | the same | +0.0485, +0.0485 | 0.87 |
| regression | the same | 0, 0 | 0.51 |

Mean on the category left out +0.0197 (resampling seeds: 5 % point +0.0020, 95 % point +0.0260).
Shuffling the changes within every category and repeating the procedure gives a mean at or
above +0.0197 in 0.45 % of 2000 shuffles.

**What already speaks against taking +0.0197 at face value.** Every change of a category is
compared with the same eight runs of generation 0. In jobshop 35 of the 40 changes whose runs
differ from generation 0's are above it (mean +0.023), in quadassign 31 of 45 (mean +0.018):
generation 0 is probably unlucky on these seeds there, and then every change looks better by
about that much. The effect of the holdback is also not monotone in its value (jobshop: 0.1
+0.012, 0.2 +0.008, 0.3 +0.059, 0.4 +0.013, 0.5 +0.057). And the change chosen is the largest
of 85. So a good part of +0.0197 is expected to disappear.

## The choice, fixed here

`assess.holdback` 0.25 → 0.3: first on the six categories taken together, and chosen in all
six folds. For comparison, the next four on the six taken together: `assess.holdback` 0.5,
`assess.holdback` 0.4, `model.batch` 2, `model.sigma` 0.2.

## Three readings, fixed here

1. **The three categories not read (knapsack, partitioning, setcover), in the landscape
   itself.** The choice was made without them. m3 = the mean over the three categories of the
   mean over seeds of the smaller of the two changes (acquired, gain) of `assess.holdback` 0.3.
   p3 = the share of the 85 common changes whose own three-category mean is at or above m3.
   *Carries to the three* if m3 > 0 and p3 ≤ 0.10. Otherwise it does not.
2. **New seeds on all nine** (plan `rsi6/runs/dev-pair.json`: generation 0 and the five changes
   named above; seeds 730101 to 730132, on partitioning and setcover 730101 to 730116).
   M9 = the mean over the nine categories of the mean over seeds of the smaller of the two
   changes, with seeds resampled within categories. *Confirmed on the pool* for a change if the
   5 % point of M9 is above 0 and its CPU over the nine categories is at most 1.15 times
   generation 0's. Reported beside it: the value of amendment 2 (each category cut to
   [−0.03, +0.01]) against the margin 0.005. Only `assess.holdback` 0.3 is the fixed choice; the
   other four are for comparison, and one of them passing would be one of four tries.
3. **What neither can be.** The nine categories are the source pool. Whatever these readings
   show is development: it can say that a registered test is worth its cost, or that it is not.
   A change counts only after a registered test on categories it was not chosen on, and
   registering one is the Owner's decision.
