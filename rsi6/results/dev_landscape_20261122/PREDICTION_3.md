# The scan one step on: what will be done with it, fixed before it runs

2026-11-22, written before plan `rsi6/runs/dev-landscape-g1.json` was started (the commit that
adds this file starts it).

## What is known

`README.md` of this directory: of the single-field changes of generation 0, `model.batch` 4 → 2
held on new seeds twice. Measured beside it, `model.batch` 2 with `model.pop` 8 together was not
better than `model.batch` 2 alone, and `model.sigma` 0.2 alone was above zero by less (+0.011
over the nine categories, +0.003 without set covering).

## The scan

The centre is generation 0 with `model.batch` 2 (digest `54945fe09723…`). It and every version
one field away from it (among them `model.batch` 4, the way back) are measured on the nine
categories of the pool, seeds 730301 to 730308, on partitioning and set covering 730301 to
730304. The same module, budget and layout of jobs as the first scan.

## What is done with it

The first scan showed what a scan of eight seeds is worth: its first choice was wrong, and the
change that held was fourth on its list. So the scan only makes a short list.

1. **Short list.** The five changes with the largest value on the nine categories as amendment
   2 counts (each category cut to [−0.03, +0.01], the smaller of acquired and gain), among those
   whose CPU over the nine is at most 1.15 times the centre's. Ties: the larger plain mean, then
   the name. No change is excluded by hand.
2. **New seeds.** The centre and the five, seeds 730401 to 730432 (16 on partitioning and set
   covering), read with `scripts/reading_2.py`.
3. **A choice, and new seeds again.** Of the changes whose 5 % point of M9 is above 0 in step 2,
   the one with the largest M9 is fixed as the choice and measured once more against the centre
   on seeds 730501 to 730532 (16 on the two). *A second step on the pool* if the 5 % point of M9
   is again above 0 and the CPU is at most 1.15 times the centre's; M8 without set covering and
   the value of amendment 2 are reported beside it.
4. **If no change has its 5 % point above 0 in step 2**, there is no second step among the
   single-field changes at this precision, and that is the result.

Steps 2 and 3 are not started by this file. The scan takes about two and a half hours on the
hosted runners, and its artifacts stay 90 days.

## What is expected

Written down so that it can be wrong: at most one change passes step 2, most likely
`model.sigma` 0.2 or none; `model.pop` 8 does not; `model.batch` 4 (the way back) is in the
lower half of the list. If changes that hold are this rare after one step, a search that moves
one field at a time has about one step in it on this pool, and what the first scan pointed to
instead (section 4 of `README.md`: choosing among several attempts by the training score,
inside each category) is where a second design would have to look.

As everywhere in this directory: the pool only, development only. Nothing here opens a sealed,
reserve or held-out category, and nothing here counts.
