# The recursion question, asked where it can have an answer: reading fixed before the run

2026-11-22, written before plan `rsi6/runs/dev-recursion.json` was started (the commit that adds
this file starts it). Development only: the four light categories of the pool, scratch ledgers,
seeds nothing else uses.

## Why the question had no answer so far

The hypothesis has two halves. The first: a modification adopted after independent validation
makes the learner acquire more on kinds of environment it has not met. The second: the modified
mechanism is also better at producing the next modification. The registered recursion check
(amendment 4) asks the second by letting a version improve versions with the learner's own
search over versions. That search is the learner's local editing of a known answer: only the
fields `edit.*` take part in it. The one change that has held on new seeds, `model.batch` 4 → 2,
is in how the learner acquires. As an improver the changed learner is generation 0 exactly, and
the registered check can only report "no difference" for it, whatever the truth.

## What is run

`rsi6/experiments/dev_recursion.py`: the improver is the learner's acquisition loop itself (the
population search of `Learner._acquire_assign`, transcribed: same fields, same order of draws,
the learner's own `_fitness`, the same keep-or-drop check on held-back problems), applied to the
space of versions. A candidate is a version; a problem is a (category, seed) pair; a rollout is
one measured acquisition run; the budget is counted as the learner counts its own, 40 times the
cost of all sixteen problems.

Twelve repetitions (k = 1 to 12). In each, from the same start (generation 0 with
`model.batch` 2), on the same sixteen problems (binpacking, jobshop, pmedian, quadassign; seeds
740000 + 100 k + 1 to 4), with the same counted budget:

* **recursive**: the improver is the start version (a batch of 2: about nineteen rounds);
* **frozen**: the improver is generation 0 (a batch of 4: about nine rounds), same search seed;
* **random**: no learning; candidates drawn as in a first round, the best by mean value.

A nominee is what the arm's final check keeps. Its value is its mean change against the start
(the smaller of acquired and gain, mean over seeds, then over the four categories) on seeds
745001 to 745016, at the run budget, on all fresh instances. An arm without a nominee has the
value 0.

## The reading, fixed here

D = the mean over the twelve repetitions of (value of recursive − value of frozen), with a 5 %
point from resampling repetitions (10,000 resamples, pairs kept).

* **A recursion signal in development** only if both hold: the 5 % point of D is above 0, and
  the 5 % point of the mean value of the recursive arm is above 0 (the improver has to produce
  something before it can be said to produce more).
* **No signal** otherwise. If no arm's mean value has a 5 % point above 0, the reading is
  "neither improver produced a next step", which says nothing about which is better.
* Reported beside it: recursive − random and frozen − random the same way; how many searches
  ended with a nominee; what the nominees changed.

One script reads it, `scripts/read.py`, committed with this file.

## What is expected

No signal (the experimenter's probability of a signal: about 0.1). Reasons, so that they can be
wrong: on these four categories the changes known to help are small against the noise of a run
(`model.batch` 2 itself is about +0.005 there; its size on the pool comes from set covering,
which is too costly to search on); a candidate is measured on two or four runs; most searches
will end with the start or with a version the check drops; and halving the batch helps the
learner because its rollouts are exact, while here every rollout is a noisy run.

## What it cannot show

Twelve repetitions on four categories of the pool. A signal here would be a reason to register
a recursion check built this way, not a result. No signal here does not show that recursion is
impossible in this package; it shows that this construction, at this budget, did not exhibit
it. The search space is the 38 fields the experimenter wrote.
