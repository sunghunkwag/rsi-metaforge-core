# Process d, generation 1: the registered gate of `model.batch` 2 on four categories no learner had run on

2026-11-22. Registered: amendment 6 (`rsi6/registry/amendment_6.json`), driver
`rsi6/experiments/gate_d.py`, every record in the ledger (`rsi6/ledger/main.jsonl`, records 9373
to 9895). On the Owner's instruction 18.

**Outcome: passed, by the rule as registered, and narrowly.** The gate's three conditions hold
(the change is +0.0195, its 10 % point +0.0135, the CPU 1.04 times generation 0's). The
confirmation is above zero by +0.0009. Generation 0 with `model.batch` 2 is adopted as
generation 1 of process d. It is the first modification of this package to pass a gate on
categories that no search, no development run and no learner had touched.

**What carries it.** One of the four categories. On the other half of the instances the gain
on quadratic 0-1 is met by a loss on maximum clique of the same size.

| Category | Gate (deciding half, seeds 8101 to 8132) | Confirmation (other half, seeds 9101 to 9132) | Both, 64 paired runs |
|---|---|---|---|
| quadratic 0-1 | +0.0722 (se 0.0184), 24 runs above, 8 below | +0.0381 (0.0133), 24 / 8 | **+0.0552** (0.0115), 48 / 16 |
| weighted tardiness | +0.0032 (0.0035), 21 / 11 | +0.0067 (0.0052), 23 / 9 | +0.0050 (0.0031), 44 / 20 |
| project scheduling | −0.0002 (0.0008), 10 / 11 | −0.0015 (0.0014), 10 / 15 | −0.0009 (0.0008), 20 / 26 |
| maximum clique | +0.0030 (0.0054), 16 / 16 | **−0.0396** (0.0224), 12 / 19 | −0.0183 (0.0118), 28 / 35 |
| mean of the four | **+0.0195** | **+0.0009** | +0.0102 |

Change of the acquired score, nominee minus generation 0, the same seed and instances; the
untrained score does not depend on the batch, so the change of the gain is the same number.

| The gate's conditions (`rounds.gate`, rules of registration c) | | |
|---|---|---|
| the smaller of the mean changes of acquired and gain at least 0.005 | +0.0195 | holds |
| 10 % point of the mean gain change (2000 resamples of runs within categories) above 0 | +0.0135 | holds |
| measured CPU at most 1.15 times the incumbent's | 1.043 (2376.7 s against 2277.9 s) | holds |
| the confirmation above zero | +0.0009 | holds |

## What a run looked like there

| Category | Kind | Rounds of learning, generation 0 → batch of 2 (median) | Runs that keep what they learned, of 64 |
|---|---|---|---|
| quadratic 0-1 | unordered, two options | 3 → 6 | 57 → 64 |
| maximum clique | unordered, two options | 3 → 6 | 60 → 58 |
| weighted tardiness | ordered | 9 → 19 | 64 → 64 |
| project scheduling | ordered | 9 → 19 | 32 → 29 |

The pattern of the pool repeats: about three rounds on unordered problems and about nine on
ordered ones, twice as many with a batch of 2; where there are nine already, nothing much
changes. What the pool did not show is the clique confirmation: there generation 0 learns a
great deal from its three rounds (untrained 0.571, acquired 0.804), and with rounds on two
problems instead of four it learns less.

## The predictions of amendment 6

| | | |
|---|---|---|
| D1 | the gate does not pass (probability of a pass about 0.4) | **wrong**: it passed |
| D2 | tardiness and projects change by less than 0.005 either way at the gate | right (+0.0032, −0.0002) |
| D3 | at least one of quadratic and clique changes by +0.01 or more at the gate | right (quadratic +0.0722) |
| D4 | the nominee's CPU is between 0.95 and 1.10 times the incumbent's at the gate | right (1.043) |

## How it was measured and checked

* The records that open the four categories (the amendment, four `reassign`, one `unlock`) were
  written on the session's machine and committed (`82b9ba2`) before anything was measured.
* The gate ran in one job on one GitHub-hosted runner (run 45080033297, AMD EPYC 7763,
  Python 3.13.18, numpy 2.5.3), 22:51 to 23:47 UTC, after the kernel tests, the adapter checks
  and `tests/test_gate_d.py` had passed on that runner. Both versions of every block of four
  seeds were measured in one call of the kernel.
* The job's working ledger (sha256 `a431e712…cacd0`) was verified: its chain; the committed
  ledger is its first 9,379 records; its amendment record carries the hash of the amendment
  file. It was then checkpointed: 9,896 records, 9,630 runs.
* A sample of 32 of its 512 runs (two seeds of the gate and two of the confirmation, both
  versions, all four categories) was measured again on the session's machine
  (`replay_sample.json`, `scripts/replay_gate_d.py`). Every score the gate and the confirmation
  read is identical in all 32: untrained, acquired, gain, the score of every fresh instance,
  the learned weights, the report and the counted units. In two runs one diagnostic number that
  no rule reads, the mean score on the training problems, differs in its last binary digit
  (1.1e-16): it is a mean taken by numpy, whose order of summation depends on the processor.
  CPU-seconds on the session's machine were 0.44 of the runner's.

## What it shows, and what it does not

* **It shows one independently validated modification of the acquisition mechanism.** The
  change was chosen on nine categories and tested once, by a rule fixed beforehand, on four
  others. That is the first half of the hypothesis, for one step.
* **It rests on one category.** By the gate's count the pass is clear; by the confirmation's it
  is +0.0009, and with both halves together one category is up by +0.055, one is up by +0.005,
  one is flat and one is down by 0.018. This is the kind of modification the scan said it was:
  more rounds of learning from the same budget, which helps where three rounds are too few and
  can cost where they were enough.
* **It is not recursive self-improvement.** Fixed in amendment 6 before the run: the learner as
  improver works with the fields `edit.*` only, so the adopted learner is, as an improver,
  generation 0 exactly. Whether a changed learner can be a better improver at all is asked
  separately, in development (`../dev_recursion_20261122/`).
* **The four categories are spent.** They are released into the pool, which now has thirteen.
  The two reserves and the four sealed targets are untouched.
