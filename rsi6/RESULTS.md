# RSI-6: results of the rounds of self-modification

Every number here is printed by `python -m rsi6.experiments.report` from the ledger
(`rsi6/ledger/main.jsonl`, hash-chained). The registration is `rsi6/registry/registration.json`,
written to the ledger before the first round. The test on the sealed target categories has not
been run yet: this document covers the rounds of self-modification only. The first sections are
about the two registered rounds (first design of the learner), the section near the end about
the continued process (second design).

## What missed, and what did not go as designed

* **Nothing was adopted.** Four nominees went to a gate (the learner's own and the random
  proposer's, in two rounds). None passed. All three lineages end at generation 0, so the
  registered primary comparison (final self version against generation 0 on the targets) has
  nothing to compare.
* **Prediction R4 missed.** It said the random proposer would do at least as well as the learner
  at improving the learner on the source pool in at least one round. In both rounds the
  learner's search found the better version there (0.0224 against 0.0162, and 0.0246 against
  0.0154). On the adoption sets, which decide, neither was better than generation 0.
* **The registered run stopped once with an error**, in the gate of round 2, at the first run
  of the learner on knapsack and regression: problems of one environment had different numbers
  of attribute columns. No record of those environments existed. The two adapters now present
  every problem in one layout (zero columns for absent constraints or variables, which is
  exact), and the kernel checks the layout before the learner is called. The learner was not
  changed. Record: `registry/corrections.json`; audit: `audit/layout_correction_20261112/`.
* **The second audit of that correction did not finish.** One auditor passed it with findings
  (fixed). The other was stopped by the session's usage limit before it reported; its working
  files show that it had repeated all 1,192 recorded runs with the corrected code, every one
  identical to its record. It gave no verdict.
* **The gate and confirmation runs of round 2 were measured on a loaded machine** (the second
  auditor's processes were running). Scores do not depend on load; measured CPU-seconds may.
* **Five of the 24 fresh laws of regression are mis-scaled by the frozen learner** (its test for
  a constant target is absolute). The regression numbers of round 2 have to be read with this.

## What was measured

Scores are on fresh instances: instances from published groups the learner was not trained on.
`untrained` is the learner without acquisition, `acquired` after it, `gain` the difference.

**Generation 0 on every category** (all its recorded runs):

| category | role | untrained | acquired | gain | threshold | runs that kept what they learned | rounds of learning |
|---|---|---|---|---|---|---|---|
| bin packing | source | 0.9283 | 0.9836 | +0.0553 | 0.980 | 1.00 | 1.0 |
| job shop | source | 0.8130 | 0.8488 | +0.0357 | 0.850 | 0.50 | 8.0 |
| forecasting | source | 0.9378 | 0.9378 | 0.0000 | 0.938 | 0.00 | 1.0 |
| quadratic assignment | adoption 1 | 0.3599 | 0.4243 | +0.0644 | 0.900 | 0.71 | 1.9 |
| p-median | adoption 1 | 0.6883 | 0.6900 | +0.0018 | 0.950 | 0.50 | 1.1 |
| knapsack | adoption 2 | 0.8411 | 0.8411 | 0.0000 | 0.970 | 0.00 | 2.8 |
| regression | adoption 2 | 0.4085 | 0.4101 | +0.0016 | 0.999 | 0.08 | 1.0 |

Generation 0 gains on three of seven categories and reaches its threshold on one (bin packing;
job shop is at the threshold within noise). On the four categories it was not developed on it
gains on one.

**The rounds.** `source pool` is what the search measured for its nominee; the gate decides on
the deciding half of the fresh instances of two categories no earlier round used; the
confirmation is the other half, with other seeds. The value is the smaller of the mean change
of the acquired score and the mean change of the gain.

| round | improver | candidates | nominee, source pool | gate | confirmation | adopted |
|---|---|---|---|---|---|---|
| 1 | learner (generation 0) | 42 | +0.0224 | −0.0023 | −0.1367 | no |
| 1 | random proposer | 41 | +0.0162 | +0.0098 (lower bound −0.0030) | +0.0129 | no |
| 2 | learner (generation 0) | 37 | +0.0246 | −0.0563 | −0.0095 | no |
| 2 | random proposer | 35 | +0.0154 | 0.0000 | 0.0000 | no |

Round 1 was gated on quadratic assignment and p-median, round 2 on knapsack and regression.
The fixed-improver lineage is identical to the self lineage in both rounds, because nothing was
adopted.

**Why the nominees did not carry over** (computed per search from its runs):

* The searches did not rank noise. The improvement of a candidate measured with one seed and
  with the other correlate at 0.75 and 0.94 over the learner's candidates (0.10 and 0.09 for the
  random proposer's single-field changes, most of which change little).
* The effects are specific to a category. Over the candidates of a search, the change of the
  acquired score in one category is nearly uncorrelated with the change in another: mean
  correlation −0.002, −0.21, +0.018, +0.062 in the four searches. No candidate improved bin
  packing or forecasting. Job shop improved under 76% and 92% of the learner's candidates.
* So the nominee of round 1 was a setting for job shop (job shop +0.07, bin packing −0.005,
  forecasting 0) and lowered the untrained score on quadratic assignment. The nominee of round
  2, found on five categories, improved two of them and harmed none there, and lost on both new
  categories (regression −0.104).

**Replay.** Every search can be played again from the ledger alone
(`python -m rsi6.experiments.replay`): all eight replay identically, candidate by candidate.
`results/candidates.json` holds the version record of every candidate.

## What was predicted

| | prediction | outcome |
|---|---|---|
| R1 | round 1: the self search finds a version that improves the source pool | held (0.0224) |
| R2 | round 1: the self nominee is not adopted | held |
| R3 | the self lineage adopts at most one version in two rounds | held (none) |
| R4 | the random proposer does at least as well as the learner on the source pool in one round | **missed** |
| R5 to R8 | about the target test | not scored: the test has not been run |

## What limits the result

1. **The budget gives generation 0 almost no learning.** At the registered training budget it
   gets 1.0, 1.1, 1.9 and 2.8 rounds of its population search on bin packing, p-median,
   quadratic assignment and knapsack, and 8.0 on job shop (the prediction form fits once by
   construction). With one round, what it acquires is the best of sixteen random variations of
   its prior.
2. **Its own check discards most of what it learns** where learning is weak: on knapsack,
   forecasting and regression it kept nothing.
3. **Improvements of this learner, in the space it can search, do not generalise across
   categories.** This is the measured answer of these two rounds to the hypothesis: the
   modifications the improver found were tunings to the categories it saw.
4. **The space of modifications is a closed list.** A version is 38 fields written by the
   experimenter. The improver chooses among their values; it cannot write a mechanism that is
   not on the list. Two independent design reviews named this before the run, and nothing in
   the run speaks against them.
5. **The improver depends on its own version only weakly**: through the fields of its
   answer-editing function. A version adopted for better acquisition changes the improver only
   if it touches those fields.

## What is not claimed

* No recursive self-improvement was observed: nothing was adopted.
* The thresholds are operating points chosen before the runs, not external facts, except where
  the environment's text says otherwise.
* Nothing is claimed about categories of other kinds (proof, planning, software, judgement):
  they are not in the experiment.
* No language model is called by any code of the experiment (amendment A1 of the constitution
  is not enacted). No third-party code is executed.
* Nothing here is evidence about artificial general intelligence.

## What happened next

Amendment 1 kept the targets sealed until the improvement process is complete. Amendment 2
registered the continued process: a second design of the learner, written by the experimenter
from the findings above (one descriptor at a time, descriptors built from existing ones, a
proposal distribution and plans relative to the budget as version fields), searches that count
breadth across categories, a gate on the third adoption set, and one target test that covers
both processes, with an arm that gives the first design the measured CPU of the second. Its
round is reported below. Both processes are now frozen; the target adapters are being built
and audited by independent agents, and the target test follows.

## The continued process: round b1 (amendment 2)

Generation 0 here is the second design of the learner, written by the experimenter. What is
tested is whether versions the system finds for itself pass a gate on categories it has not
seen. Registration: `registry/registration_b.json`. Round b1 searched the pool of seven
categories and was gated on graph partitioning and set covering, whose adapters were built and
audited by independent agents (`audit/adapters_adoption3/`).

**What missed.** Nothing was adopted here either. No registered prediction about the round
missed: B1, B2 and B3 held.

| improver | candidates | nominee, source pool (breadth) | gate | confirmation | adopted |
|---|---|---|---|---|---|
| learner (generation 0, second design) | 26 | +0.0045 | −0.0818 | −0.0176 | no |
| random proposer | 29 | +0.0035 | +0.0097 (lower bound −0.00005) | +0.0137 | no |

* The learner's nominee changed seven fields. At the gate it lost on set covering (acquired
  −0.143) and changed nothing on partitioning (−0.002).
* The random proposer's nominee changed one field (`plan.checks`). It met the margin (+0.0097
  against 0.005) and used less CPU (0.89), and failed the third condition by a hair: the lower
  bound of the gain interval was −0.00005. On the confirmation half it was +0.0137. The rule
  was registered before the round and is applied as written. The same thing happened in round
  1: the random proposer's single change came closest (+0.0098, lower bound −0.0030,
  confirmation +0.0129).
* The self search ranked its candidates above noise (correlation between the two seeds 0.53;
  0.39 for the random proposer). The changes still do not generalise: over the self search's
  candidates the mean correlation between categories is +0.10; knapsack improved under 81% of
  them and quadratic assignment under 62%, bin packing and both prediction categories under
  none.
* Round b2 was not run: the registered rule runs it only after an adoption.

**Generation 0 of the second design on the two gate categories**, its first contact with them
(12 runs each, fresh instances):

| category | untrained | acquired | gain | threshold |
|---|---|---|---|---|
| graph partitioning | 0.6046 | 0.8668 | +0.2622 | 0.900 |
| set covering | 0.1840 | 0.7072 | +0.5232 | 0.950 |

It acquires a large part of both capabilities and reaches neither threshold. This says nothing
yet about the first design on these categories, nor about equal measured CPU; the registered
comparison of the designs is on the sealed targets.

**Post hoc, not registered: the first design on the same two categories.** After the round its
gate categories joined the source pool. Generation 0 of the first design was then run on them
with the budgets and seeds of the gate and of the confirmation (`experiments/posthoc.py`;
recorded in the ledger as post hoc):

| category, half | first design: acquired (CPU-s per run) | second design: acquired (CPU-s per run) |
|---|---|---|
| graph partitioning, deciding half | 0.8652 (148) | 0.8734 (188) |
| graph partitioning, confirming half | 0.8446 (27) | 0.8601 (58) |
| set covering, deciding half | 0.7641 (92) | 0.7723 (262) |
| set covering, confirming half | 0.6765 (75) | 0.6422 (286) |

At equal counted units the two designs acquire the same on these categories (differences
+0.008, +0.016, +0.008, −0.034), and the second spends 1.3 to 3.8 times the CPU. The redesign
bought nothing here that can be seen. The large gains on these two categories belong to both
designs.

**Across the three rounds** the picture is the same: six nominees, none adopted; the two that
came closest were single-field changes proposed at random; every nominee the learner found by
following its own measurements on the pool lost on the new categories.

## How to reproduce

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m rsi6.tests.test_kernel
    python -m rsi6.experiments.report        # every number above
    python -m rsi6.experiments.replay        # every search again, from the ledger alone
