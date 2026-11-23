# Development: every single-field change of generation 0, on every category of the pool

2026-11-22. Development only. The nine categories are the source pool (the three source
categories and the three adoption sets, which joined the pool after their gates); every run
wrote a scratch ledger; the seeds are used by nothing else; no sealed, reserve or held-out
category was touched. Nothing here is a registered result and nothing here decides anything.
It answers a question no registered process had asked directly, and it says whether a
registered test is worth its cost.

**The question.** Every registered process of the first design chose a version on some
categories and lost on others. Does a change of one field of the learner carry from the
categories it is chosen on to a category it was not chosen on, when every change is measured
on every category?

**The answer, in one paragraph.** Most of what a small scan shows is not there: the change the
scan put first (`assess.holdback` 0.25 → 0.3, +0.0197 on categories left out) kept +0.0030 on
new seeds, with a 5 % point of −0.0055. One change does hold on new seeds, measured twice:
`model.batch` 4 → 2, the second time as a choice fixed before the run. Over the nine categories
it adds +0.0246 to what is acquired (5 % point +0.0154) at 1.04 times the CPU; with set covering,
which carries most of it, left out, +0.0066 (5 % point +0.0009). It was picked on six
categories and is above zero on the three it was picked without. The statistic by which the
continued process ranks candidates in its search (amendment 2: no category counts for more than
+0.01) puts it at +0.0037. It is a candidate for a registered test on categories no
learner has run on. It is not a result, and one changed field is not recursion.

## What was run

All on GitHub-hosted runners, one job per category or part of one, four cores each;
generation 0 and its changes always inside one job, so CPU is compared inside a job and seed.
Python 3.13.18, numpy 2.5.3. The run budget is the one of the registrations.

| Plan | Run | Versions | Seeds | Runs |
|---|---|---|---|---|
| `dev-landscape` | 45059214153 | generation 0, each of its single-field changes (85 on an assignment category, 96 on a prediction category) and the version process c adopted | 730001 to 730008; partitioning and set covering 730001 to 730004 | see below |
| `dev-pair` | 45062991243 | generation 0 and five changes | 730101 to 730132; partitioning and set covering 730101 to 730116 | 1,536 |
| `dev-pair-2` | 45066927594 | generation 0, three changes, one version with two of them | 730201 to 730232; partitioning and set covering 730201 to 730216 | 1,280 |

Seed 730901 was used for two checks that the options `--only` and `--also` work (quadratic
assignment and forecasting, on the session's machine); it is in no file here.

The artifacts of the three runs are in `artifacts/` as they were uploaded (GitHub keeps them 90
days). `scripts/` has what read them; every number below is printed by one of them:

```
mkdir x && for f in artifacts/*.tar.gz; do tar xzf $f -C x; done
python3 -I scripts/landscape_loco.py x/landscape --out loco.json        # leave one category out
python3 -I scripts/reading_1.py      x/landscape --out reading_1.json
python3 -I scripts/reading_2.py      x/pair      --out reading_2.json
python3 -I scripts/reading_2.py      x/pair2     --out second_reading_M9.json
python3 -I scripts/reading_2.py      x/pair2     --out second_reading_M8.json --leave-out setcover
python3 -I scripts/learned_rates.py  x/pair x/pair2
python3 -I scripts/landscape_train_pick.py x/landscape
```

## The order of events

What was fixed before what was read is the point of this record; the commit times and the
completion times of the jobs are the check.

| UTC | |
|---|---|
| 19:10 | `dev-landscape` starts |
| 19:49:57 | commit `08509ed`: `PREDICTION.md`. Six categories read; knapsack, partitioning and set covering not finished. The choice (`assess.holdback` 0.3), four changes for comparison, and three readings are fixed |
| 19:50:11 | `dev-pair` starts |
| 19:51:34 | commit `ef25e36`: the scripts of readings 1 and 2 |
| 19:55 to 20:15 | the two knapsack jobs of the landscape finish |
| 20:31:34 | commit `33e791e`: `PREDICTION_2.md`. Seventeen of the eighteen jobs of `dev-pair` read; the landscape's partitioning and set covering not read. The second choice (`model.batch` 2) and its reading are fixed |
| 20:31:39 | `dev-pair-2` starts |
| 20:39 | `dev-pair` finishes |
| 21:08 | `dev-pair-2` finishes |

## 1. The scan and its first choice

With six categories read, each was left out in turn and the change with the largest value on
the other five was chosen (the statistic of amendment 2; CPU at most 1.15 times generation
0's). All six folds chose `assess.holdback` 0.25 → 0.3; on the category left out it was at
+0.0197 on average, and shuffling the changes within every category gave that much in 0.45 %
of 2000 shuffles (`interim/loco_six_categories.json`). `PREDICTION.md` fixed it as the choice
and wrote down, before the rest was read, why a good part of +0.0197 should disappear:
generation 0 looked unlucky on those eight seeds in two categories, and the change was the
largest of 85.

**Reading 2 of `PREDICTION.md`, new seeds, all nine categories** (`reading_2.json`):

| Change | M9 | 5 % point | CPU | Categories above / below | |
|---|---|---|---|---|---|
| `assess.holdback` 0.3 (the choice) | +0.0030 | −0.0055 | 1.01 | 6 / 3 | **not confirmed** |
| `assess.holdback` 0.5 | +0.0029 | −0.0046 | 1.00 | 6 / 2 | |
| `assess.holdback` 0.4 | +0.0002 | −0.0117 | 0.99 | 7 / 2 | |
| `model.batch` 2 | +0.0188 | +0.0106 | 1.03 | 6 / 1 | above zero; one of four comparisons |
| `model.sigma` 0.2 | +0.0063 | +0.0008 | 1.00 | 6 / 1 | above zero; job shop −0.029 (7 runs above, 19 below) |

Job shop, where the scan had the choice at +0.059, has it at +0.012 (standard error 0.010) on
the new seeds; quadratic assignment +0.008 where the scan had +0.049. The prediction was right
and the choice was wrong.

**Reading 1 of `PREDICTION.md`** (the choice on the three categories it was made without, in
the scan itself) is negative too: section 5 and `ADDENDUM.md`.

## 2. The second choice

`PREDICTION_2.md` fixed `model.batch` 4 → 2 and its reading before `dev-pair-2`
(`second_reading_M9.json`, `second_reading_M8.json`).

| | `model.batch` 2 | |
|---|---|---|
| M9, all nine categories | +0.0246, 5 % point +0.0154, 95 % point +0.0338 | **confirmed on the pool a second time** |
| CPU over the nine | 1.04 times generation 0's | within 1.15 |
| M8, set covering left out | +0.0066, 5 % point +0.0009 | **not carried by one category alone**, narrowly (2.9 % of resamples at or below 0) |
| Value of amendment 2 (the search's ranking statistic) | +0.0037, 5 % point +0.0004 | above zero; see the correction below |

By category, mean change of what is acquired, standard error, runs above / below:

| Category | First measurement (`dev-pair`) | Second (`dev-pair-2`) |
|---|---|---|
| set covering | +0.139 (0.043), 13 / 3 | +0.168 (0.044), 13 / 3 |
| partitioning | +0.011 (0.007), 12 / 4 | +0.027 (0.021), 10 / 6 |
| quadratic assignment | +0.016 (0.012), 21 / 9 | +0.023 (0.016), 20 / 12 |
| bin packing | +0.003 (0.002), 12 / 7 | +0.005 (0.003), 12 / 9 |
| p-median | +0.005 (0.003), 11 / 8 | +0.001 (0.003), 10 / 5 |
| knapsack | +0.001 (0.001), 2 / 0 | +0.002 (0.004), 4 / 3 |
| job shop | −0.006 (0.010), 15 / 14 | −0.004 (0.011), 13 / 17 |
| forecasting, regression | 0 | 0 |

The change was put among the comparisons from six categories. Knapsack, partitioning and set
covering were not among them, and it is above zero on all three in both measurements.

The comparisons of `dev-pair-2` decide nothing. `model.pop` 16 → 8: M9 +0.0090 (5 % point
+0.0011), without set covering +0.0015 (−0.0034). `model.sigma` 1.0 → 0.2: +0.0112 (+0.0031),
without set covering +0.0031 (−0.0010). `model.batch` 2 and `model.pop` 8 together: +0.0181,
below `model.batch` 2 alone, and without set covering +0.0010 (−0.0036), with job shop at −0.023
(10 runs above, 19 below). Two changes that each add rounds of learning do not add up.

## 3. Why a batch of 2 could matter: what a run of generation 0 is

From the run reports of `dev-pair` and `dev-pair-2` (`scripts/learned_rates.py`), generation 0,
the two runs together, 64 runs per category (32 on partitioning and set covering):

| Category | Rounds of learning the budget allows (median, range) | Runs that keep what they learned | Gain when kept | Gain when not | Rounds with a batch of 2 (median) |
|---|---|---|---|---|---|
| bin packing | 1 (1 to 1) | 61 of 64 | +0.058 | 0 | 2 |
| p-median | 1 (0 to 2) | 19 of 64 | +0.012 | 0 | 2 |
| quadratic assignment | 2 (1 to 4) | 54 of 64 | +0.093 | 0 | 5 |
| partitioning | 2 (1 to 4) | 32 of 32 | +0.231 | | 5 |
| set covering | 2 (2 to 4) | 32 of 32 | +0.463 | | 6 |
| knapsack | 3 (2 to 4) | 2 of 64 | +0.036 | 0 | 6 |
| job shop | 9 (6 to 14) | 49 of 64 | +0.087 | 0 | 19 |

(`learned_rates.txt`.)

A run of the first design is a few rounds of a population search over the weights of a
scoring rule, and then one check on the held-back training problems that keeps the learned
weights or drops them as a whole. When they are dropped the gain is exactly 0. Two things
follow.

* **The scan's noise.** Whether a run keeps its weights is close to a coin for several
  categories, and almost any change of a field moves the search enough to throw the coin
  again. In the scan generation 0 kept its weights in 2 of 8 runs on job shop; on the 32 new
  seeds of `dev-pair` it kept them in 24. That is the bad luck `PREDICTION.md` suspected, and it
  is why the scan had 35 of 40 changes above generation 0 there.
* **The batch.** Halving the batch at least doubles the rounds at the same counted budget and
  about the same CPU (last column). In the scan the opposite change is as clear: with a batch
  of 8 the budget allows no round at all on bin packing and p-median (every run) and on
  quadratic assignment (six runs of eight), and all of the gain is gone; a population of 32
  does the same to bin packing. The registered run budget sits at the edge of what this
  learner needs to learn anything.

## 4. What picking by the training score shows

Inside one category and seed of the scan, take the version with the best score on the
*training* problems and read its score on the *fresh* ones (`scripts/landscape_train_pick.py`;
seven categories read): job shop +0.067, quadratic assignment +0.094, p-median +0.027 above
generation 0, in 7 of 8 seeds each; the rank correlation between the two scores over the
versions is 0.40, 0.75 and 0.88. On the two prediction categories the pick is slightly below.

This is an upper reference, not a mechanism: every version in the files had a full budget, so
the pick costs 86 runs. What it says is where the room is. A setting found on some categories
carries little to others; the procedure "try several, keep what does best on the training
problems" carries, because it is run again inside each category. Whether it pays at equal
compute has not been measured.

## 5. The scan on all nine categories, and reading 1

`ADDENDUM.md`. In short: reading 1 is negative as well (the first choice does not carry to the
three categories it was made without), and with all nine categories in, leaving each out in
turn chooses `model.batch` 2 in every fold.

## What this is, and what it is not

* It is development on the pool. A change counts only after a registered test on categories it
  was not chosen on, and no learner has run on any of the ten such categories.
* `model.batch` 2 is the first modification of this package that kept its sign and size on new
  seeds with the choice fixed beforehand, and that is above zero on categories it was picked
  without. It is carried mostly by one category, as the nominees that failed in rounds 1 and 2
  were; unlike them it has been measured on 32 to 64 new seeds per category rather than 18
  paired runs on three.
* **Correction (2026-11-22, 22:40 UTC).** `PREDICTION_2.md`, and this file as first written,
  set the value of amendment 2 (+0.0037) against "the margin of 0.005" and concluded that the
  continued process as registered would not adopt the change. That confused two things.
  Amendment 2's statistic (`rsi6/meta/rounds.py`, `breadth`) is what the searches of the
  continued process rank candidates by, and what they ask of it is to be above zero. The
  margin of 0.005 belongs to the gate (`gate`, the same since the first registration), which
  decides an adoption and counts the plain mean of the change: at least 0.005, a 90 % lower
  bound of the gain above zero, CPU at most 1.15 times the incumbent's. On the pool this change
  is at +0.0246 by the gate's count. `PREDICTION_2.md` is left as it was committed; the
  readings it fixed (M9, M8) do not depend on the mistaken sentence.
* One changed field of a hand-written learner is not recursive self-improvement. It would be
  the first verified step; whether the changed learner is better at finding the next step is
  the question that follows it.
