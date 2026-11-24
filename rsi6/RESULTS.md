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

## Process c (amendment 3): where it stopped

Registration: `registry/registration_c.json` (ledger record 2196). `python -m rsi6.experiments.report`
prints the process from the ledger. Six generations are registered. The ledger holds
generation 1 and most of generation 2 (2,280 runs, 27,506 CPU-seconds); the process was set
aside for the open experiment and has not been taken up again.

**Generation 1** searched on bin packing, job shop, quadratic assignment and set covering and
was gated on forecasting, graph partitioning and p-median.

| technique | nominee | gate | lower bound | CPU ratio | confirmation | adopted |
|---|---|---|---|---|---|---|
| single, remeasure, combine (the same nominee) | `model.pop` 16 to 8 | +0.0106 | −0.0077 | 1.00 | +0.0127 | no |
| climb (the learner's own search over versions) | seven fields | +0.0176 | +0.0066 | 1.00 | +0.0035 | yes |

The adoption is provisional by registration: the categories set aside belong to the pool, and
every generation tests up to four nominees. It is not evidence of improvement on unseen
categories.

**Generation 2** started from the adopted version, searched on bin packing, p-median,
quadratic assignment and graph partitioning, and was to be gated on job shop, knapsack and
set covering. Its climb was run by the adopted version as improver.

| technique | nominee | gate | lower bound | CPU ratio | confirmation | adopted |
|---|---|---|---|---|---|---|
| single, remeasure, combine (the same nominee) | `model.pop` 16 to 8 | +0.0376 | −0.0065 | 0.88 | +0.0178 | no |
| climb | ledger record 4504 | not run | | | | |

So far the process has one adopting generation. Predictions: C1 (at least one provisional
adoption) held; C2 to C5 are not scored, because the process has not ended.

**On a second machine, outside the ledger (2026-11-22;
`results/second_machine_20261122/`).** The 18 recorded incumbent runs of generation 2's gate
were measured again on another machine: all 18 have the recorded scores, per-instance scores,
units and capability digests, and they took 0.78 of the recorded CPU. Scores do not depend on
the machine; CPU-seconds do. A driver started again on another machine would therefore compute
the gate's CPU ratio from two machines, and the registered driver was not continued there.
The gate of the climb's nominee was then computed with the package's rule and no ledger: its
18 gate runs had used at least 2.6 times the incumbent's CPU when nothing else was running,
and at least 4.1 times when they were stopped unfinished; the rule allows 1.15. By the
registered rule the nominee is not adopted whatever its scores, and generation 2 closes with
no adoption. The nominee was found within 1.25 times the current version's CPU on the
categories searched; on the categories it had not seen its cost did not hold. The registered
record of this gate is still to be written.

## The open design and the discovery of its mechanisms (amendment 5)

Registration: `registry/registration_o.json` (written to the ledger before the first run of the
experiment, with the SHA-256 of the 32 files that run; the driver refuses to run when one
differs). Every number in this section is printed by `python -m rsi6.open.report` from the
ledger (`results/open_20261116/report.txt`). The later held-out stage on the sealed categories
has not run; it follows the target test.

**What was tested.** The learner of the open design (design o, `learner/design_o.py`) is a set of
programs of one small vector machine: a score program and a pick program (its representation and
its decisions, over generic sensors of the problem forms) and three programs that form its
learning principle (`init`, `propose`, `update`: how a population of constant vectors is filled
and how fitness turns into new state). Discovery (`open/discovery.py`) edits these programs. The
edit distribution is learned, and in the recursive arm it is learned by the current mechanism's
own learning principle, restarted at every accepted mechanism: what is discovered changes how
the next candidates are generated. The question: does such a system improve its own ability to
discover, measurably, on categories it never saw?

**Arms and controls.** recursive; frozen (generation 0's principle always); uniform (no learning);
shuffled (generation 0's principle learning from permuted values); tune (constants and numbers
only). Two lineages per arm, 6,000 CPU-seconds each, on job shop, knapsack, p-median and
quadratic assignment. Acceptance: screen, promote, confirm on four seeds used for nothing else,
t at least 2.6 (null calibration: about 1% false acceptance per step). Held-out: bin packing,
partitioning, set covering, with every control given the measured CPU of the recursive arm's
final mechanism.

**What missed.** The two predictions that the experiment needed missed. O1 (every recursive
lineage accepts at least one mechanism) and O4 (the recursive arm accepts at least one change of
the learning principle): no lineage of any arm accepted anything. 152 steps of discovery tried
912 candidates and 18 confirmations; none passed. Every final mechanism is generation 0.

| arm | lineages | steps | CPU-s | candidates | confirmations passed | accepted |
|---|---|---|---|---|---|---|
| recursive | 2 | 16, 16 | 6,102, 6,139 | 96, 96 | 0 of 2, 0 of 1 | 0 |
| frozen | 2 | 16, 16 | 6,101, 6,153 | 96, 96 | 0 of 2, 0 of 1 | 0 |
| uniform | 2 | 16, 13 | 6,292, 6,340 | 96, 78 | 0 of 1, 0 of 4 | 0 |
| shuffled | 2 | 14, 17 | 6,062, 6,196 | 84, 102 | 0 of 3, 0 of 1 | 0 |
| tune | 2 | 14, 14 | 6,172, 6,201 | 84, 84 | 0 of 2, 0 of 1 | 0 |

What follows from that, as registered:

* The recursion was never exercised. The swap test did not run.
* On the held-out categories every arm is generation 0, so every registered difference between
  arms is exactly 0 (acquired 0.9124, gain +0.3365, 211.8 CPU-s per run, 18 runs per arm). The
  success condition is not met: E1, E3(a), E3(b) and E3(c) are all false.
* O2, O3 and O5 held (E1 not met; no advantage of the learned discoverer over uniform edits; no
  advantage in the swap test), but they hold because nothing was accepted, not because a
  discovered mechanism was tested and found equal.
* Reference only: generation 0 of the open design against the first design given its CPU,
  +0.0103 (interval -0.0072 to +0.0388; bin packing -0.007, partitioning -0.004, set covering
  +0.043). Not distinguishable from zero.

**What limited discovery** (post hoc and read-only: `open/diagnose.py`, `open/transfer_bound.py`;
outputs in `results/open_20261116/`). None of this is evidence for or against an endpoint.

* The 18 candidates that reached confirmation were worth +0.0080 on the discovery seeds that
  selected them and +0.0000 on the four confirmation seeds that no selection had touched (10 of
  18 positive there). What looked like gains was selection among noise.
* The registered rule accepts a mean difference of about 0.011 over 16 paired runs at the
  measured noise (median confirmation sd 0.017). No candidate was near it.
* Screening does not predict. The correlation between a candidate's value on the screening seed
  and its value on the two other discovery seeds is 0.03 (298 promoted candidates).
* Edits mostly hurt. The 741 screening values that are not exactly zero have mean -0.018 and sd
  0.050, against a one-seed noise of 0.009: the effects of edits are large next to the noise and
  centred below zero.
* The effects of a candidate on different categories are correlated (0.09 to 0.75 after the
  noise correction), and the common part is harm (mean effect -0.001 on job shop, -0.022 on
  knapsack, -0.042 on p-median, -0.008 on quadratic assignment).

So the step that failed is not the learning of the edit distribution, which never got an accepted
mechanism to learn from. It is that almost every edit of the programs makes the learner worse,
and the few that look better on three seeds are not better on four more.

**What followed.** Two attempts on the same question, both on source categories only so far:

* Design q searches over its score and pick programs inside one acquisition, with the measured
  noise in mind (a switch must win on a second batch). At training budget 40 it gained nothing
  over generation 0 of the open design (-0.003 and -0.002; `results/dev_20261116/`).
* Design r (amendment 6, in preparation) carries the record of that inner search from one
  acquisition to the next across categories. Its first development check found why more budget
  made the inner search worse: a batch judged by mean rank takes programs that break a hard
  constraint on some problems. With batches judged hard constraints first, four times the budget
  acquires +0.0125 more instead of -0.0140 less, on the same development seeds
  (`results/dev_r_20261116/`). That is a development result, not evidence; the registered test
  of design r is on four categories no process has used.

  Its second development check, repeated on 2026-11-22 on GitHub-hosted runners
  (`results/dev_r_d2_20261122/`), is negative. Over 24 chains, on a category the chain had
  not met, the learner that carries the relay's memory acquired 0.0078 less than the learner
  that carries nothing (80% interval -0.0147 to -0.0010; negative on each of the three
  left-out categories), and no more than its shuffled placebo (-0.0021). The prior built
  from the memory does not predict what the next acquisition finds useful (prospective
  Spearman +0.04). The rule written before the check stops the registration only if the first
  check is also below its bound, which it is not; so the rule leaves the experiment to be
  registered, and the numbers say that its primary endpoint, this same comparison on the four
  held-out categories, starts below zero. It has not been registered.

## Development: a scan of generation 0, and one change that held on new seeds (2026-11-22)

Not registered, not in the ledger, on the nine categories of the pool only. The record, with the
order in which things were fixed and read, is `results/dev_landscape_20261122/`.

Every registered process of the first design chose a version on some categories and lost on
others. The scan measured what none of them had: generation 0 and each of its single-field
changes on every category of the pool (8 seeds; 4 on partitioning and set covering).

* **What a small scan shows is mostly not there.** With six categories read, leaving each out
  in turn chose `assess.holdback` 0.25 → 0.3 every time, at +0.0197 on the category left out.
  The choice, and the reasons to expect most of that to disappear, were committed before the
  other three categories were read. On 32 new seeds per category (16 on the two heavy ones) it
  kept +0.0030, 5 % point −0.0055: not confirmed.
* **One change held.** `model.batch` 4 → 2 was one of four changes measured beside the choice
  and was above zero. It was then fixed as the choice, with its reading, before a second run
  on seeds nothing had used: +0.0246 over the nine categories (5 % point +0.0154) at 1.04 times
  the CPU; +0.0066 (5 % point +0.0009) with set covering left out. It had been picked on six
  categories and is above zero on the three it was picked without (set covering +0.168 and
  +0.139 in the two runs, partitioning +0.027 and +0.011, knapsack +0.002 and +0.001).
* **Why.** A run of generation 0 gets one to three rounds of learning from the registered
  budget on six of the seven assignment categories and then keeps or drops what it learned as a
  whole (bin packing keeps in 61 of 64 runs, quadratic assignment 54, job shop 49, p-median 19,
  knapsack 2; the gain is exactly 0 when it drops). A batch of 2 at least doubles the rounds at
  the same counted budget. With a batch of 8 the budget allows no round at all on bin packing
  and p-median, and in six runs of eight on quadratic assignment.
* **What it does not show.** The change is carried mostly by one category, as the nominees of
  rounds 1 and 2 were. The statistic by which the continued process ranks candidates in its
  search (amendment 2) puts it at +0.0037, because no category counts there for more than
  +0.01; the registered gate, which decides an adoption, counts the plain mean (a first
  version of this paragraph said the process would not adopt the change: that confused the
  two, see the correction in the record). Two changes that each add rounds
  (`model.batch` 2 with `model.pop` 8) are not better together than the first alone. And one
  changed field is not recursion.

When this section was written no learner had run on a category outside the pool. The Owner's
instruction 18 then opened the test of this change: the next section.

## Process d, generation 1 (amendment 6): the change through the registered gate (2026-11-22)

Registered; in the ledger (records 9373 to 9895); the record is `results/gate_d1_20261122/`.

One nominee, generation 0 with `model.batch` 2, against generation 0, on the four categories
that had been held out since 2026-11-16 (weighted tardiness, quadratic 0-1, project scheduling,
maximum clique), by the registered gate with its rules unchanged, 32 seeds at the gate and 32
at the confirmation. The records that open the categories were committed before anything was
measured; the gate ran in one job on a hosted runner; the returned ledger was verified and a
sample of 32 runs was measured again on the session's machine with identical scores.

| | Gate (deciding half) | Confirmation (other half) | Both halves |
|---|---|---|---|
| quadratic 0-1 | +0.0722 | +0.0381 | +0.0552 (48 runs above, 16 below) |
| weighted tardiness | +0.0032 | +0.0067 | +0.0050 (44 / 20) |
| project scheduling | −0.0002 | −0.0015 | −0.0009 (20 / 26) |
| maximum clique | +0.0030 | −0.0396 | −0.0183 (28 / 35) |
| mean | **+0.0195**, 10 % point +0.0135, CPU 1.04 | **+0.0009** | +0.0102 |

**Passed** by the rule fixed beforehand (the gate's three conditions and a confirmation above
zero), and the version is adopted as generation 1 of process d. It passed narrowly: the
confirmation is above zero by 0.0009, because on that half the gain on quadratic 0-1 is met by
a loss of the same size on maximum clique.

What it is: the first modification of this package to pass a gate on categories that no
search, no development run and no learner had touched; one independently validated step. What
it is not: broad (it rests on one category of four), and recursive. The amendment fixed the
second point before the run: the learner improves versions with its fields `edit.*` only, the
adopted change is not among them, and as an improver the adopted learner is generation 0
exactly. Of the four predictions of the amendment the first was wrong (the gate would not
pass, with a probability of 0.4 given to a pass) and three were right (nothing on the two
ordered categories, at least +0.01 on one of the two unordered ones, CPU between 0.95 and
1.10).

## Development: no second step among single-field changes (2026-11-23)

Not registered; `results/dev_landscape_20261122/G1.md`. The same scan, centred on the adopted
version (generation 0 with `model.batch` 2), on the nine categories of the first scans with new
seeds; what would be done with it was fixed before it ran (`PREDICTION_3.md`).

* The way back (`model.batch` 4, which is generation 0) is 74th of 78 changes, at −0.021: a
  third measurement of the first step, from the other side, with the same sign.
* The five changes of its short list were measured again on 32 new seeds per category (16 on
  the two heavy ones). None has a 5 % point above zero; the largest mean is +0.0015. By the
  rule fixed beforehand there is no second step among single-field changes at this precision.
* One of them, `model.sigma` 0.2, is clearly above the centre on knapsack (14 runs of 32 above,
  1 below) and clearly below it on job shop (8 above, 19 below). What is left to gain is in
  settings that differ by category, which a search over one version for all categories cannot
  hold.

So process d has one generation. A second would need either a modification of another kind
than a single field, or a learner that chooses such settings per category while it acquires.

## The recursion question in development (2026-11-22 to 23)

Not registered; `results/dev_recursion_20261122/`. In the first design a changed learner can be
a better improver only through its fields `edit.*`; the adopted change is not among them. To
ask the question where it can have an answer, the learner's acquisition loop was transcribed
into an improver of versions and run from the adopted version by that version itself, by
generation 0, and by a random proposer, twelve times each at the same counted budget, with the
reading fixed beforehand. No arm produced a next step: the run gives no answer. The record
says why (on a grid of field values the loop stops exploring after a few rounds; a candidate is
measured on two or four runs) and what an answer would take. **No recursion has been
observed, and none could have been by the registered check.**

## Design s in development: one search procedure at two levels (2026-11-23 to 24)

Not registered; `results/design_s_20261124/` (design, the reading fixed before the run, the
tables, the chains). Instruction 19. Design s makes the learner's acquisition one function and
uses the same function, with the fields of the improving version, as the improver of versions;
and it adds two steps that adapt inside a search (`adapt.spread`, `adapt.race`). With the new
fields off it is the first design run by run. Every one of its 324 mechanisms was measured on
eight categories of the pool with 16 seeds (36,864 runs), and chains of self-modification were
then run on those tables from every mechanism, 30 times each, in four assignments of the
categories to discovery, gate and test.

| | Statistic (mean of the folds, after four generations, on test categories) | Mean | 5 % point | Needed |
|---|---|---|---|---|
| A | where the chains end, above their starts | +0.0011 | +0.0009 | mean 0.005 |
| B | improver is the current version, minus improver stays the start | +0.0000 | −0.0000 | 5 % point above 0 |
| C | the search, minus a uniformly drawn nominee with the same gate | +0.0002 | −0.0000 | 5 % point above 0 |

None holds. The gate adopts a nominee of the search in 2 to 9 % of generations and a uniformly
drawn version as often or more; the recursive and the frozen arm differ in 0.08 to 2.2 % of
chains, so the comparison of improvers was hardly exercised; and where every mechanism was
compared as improver from the same incumbents, those that acquire more yield less (rank
correlation −0.28).

What the tables settle, beyond the chains: choosing with every table of seven categories in
hand the best version of the list and scoring it on the eighth gives −0.0070 against the
adopted version (5 % point −0.0143, 95 % point +0.0003) and +0.0029 against generation 0
(−0.0060, +0.0119). Around generation 0 three changes gain and are one gain by three routes,
more rounds in the same budget (`adapt.race` 1 +0.0170, `model.pop` 8 +0.0115, `model.batch` 2
+0.0099); around the adopted version nothing gains (largest +0.0035, standard error 0.0042),
the two new procedures included (+0.0010, +0.0009). A diagnostic run before the design
(`DESIGN.md`) had the adopted version with 16 times the training budget gain about 0.02 on
quadratic assignment and nothing on p-median. **Where the first design stands, what it acquires
is bounded by what the weights of its policy can express; no change of how it searches for
them, by a setting or by a procedure, lifts it, and no improver has a second step to find in
that space.** The registered stage of the design was not run.

## Design t in development: a learner of programs, and three ways to make it improve itself (2026-11-24)

Development only; nothing registered. The account with every table is
`results/design_t_20261124/README.md`.

**What was built.** A different learner, in the prediction form (`learner/design_t.py`): a
capability is at most four passes of small programs over a fresh problem, and a version is
what the learner knows about its own programs: a library it tries first, a memory of programs
with their skill, and a model of its programs that it acquires itself by an ordinary
acquisition on problems made from that memory. Six kinds of prediction problem were added
(three from PMLB, three from the Monash archive). Each reading leaves one kind out, makes
versions from the other kinds of its form, and measures them on the kind left out.

**What missed.** The second half, three times.

* A proposal distribution fitted to what the runs found: nothing on a kind left out (0.6802
  against 0.6821 for generation 0, training budget 40).
* A library made from the learner's own runs: generation 1 gains on the kinds left out
  (unordered +0.018 on average, training budget 12), but a chain whose steps are made from the
  current version's runs ends below a chain whose steps are made from generation 0's runs
  (0.6521 against 0.6775 at generation 3).
* Memory and a model of its own programs: the same order (0.6585 against 0.6829), and the
  recursive chain is no better than its shuffled control (0.6548).

**What held.** The first half, in development: with knowledge made on three kinds, what is
acquired on the fourth rises by +0.044 (regression), +0.043 (friedman), +0.008 (table) and
+0.015 (binary) at a training budget of 12. And one link of the second half: a learner that
carries a library models its own programs more accurately than generation 0 does (rank
correlation with the value of unseen programs 0.68 to 0.74 against 0.57 to 0.63).

**Why nothing follows from that link.** With library and memory equal, the version whose model
the modified learner made acquires +0.0014 more on average than the version whose model
generation 0 made (+0.0060, −0.0005, −0.0003, +0.0004; 48 seeds, three models each). And when
the next programs to evaluate are chosen by a perfect model of their value on the kinds in use,
the library that results covers the kind left out no better than when they are drawn at random
(+0.0015 and −0.0024 unordered, −0.011 ordered). The space of programs is flat: the best
program of one stage is as good as the best of three, and a hundred random draws hold what
carries over. One step exhausts what can be known about it in general.

**What limits these numbers.** Compute was matched in the learner's units (passes), not in CPU;
a stage of the most expensive model costs twelve times the cheapest, and one version used 3.4
times the CPU of generation 0 on one kind. Four kinds per form. No gate.

## How to reproduce

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m rsi6.tests.test_kernel
    python -m rsi6.experiments.report        # every number of the rounds
    python -m rsi6.experiments.replay        # every search again, from the ledger alone
    python -m rsi6.open.report               # every number of the open experiment
    python -m rsi6.open.diagnose --ledger rsi6/ledger/main.jsonl      # what limited its discovery
