# Design v in development (2026-11-24): a learner that searches acquires far more; no second half

Development only. Nothing here was registered and nothing here is evidence for the hypothesis.
Every number is from training instances or fresh instances of kinds already used in
development, and none from a kind held for a test.

## What design v is

Designs a to s construct an assignment once or twice and stop. A capability of design v
(`learner/design_v.py`) is a *search*: a greedy construction, then moves until the meter of the
problem ends. The moves are generic operators (exchange the options of two variables; shift one
variable; unassign a few variables and assign them again by the exact changes the problem
reports), which share the units of a search by what each gained per unit. A *way to search* is
six settings of that search, three levels each, 729 ways (`LEVELS`).

## It acquires more, by construction of the learner

Through the kernel, budget of the registrations (training 40, two constructions and one
evaluation per variable on a fresh problem), two seeds, fresh instances. Three credit rules were
tried in turn; the last is in the code.

| kind | first design, acquired | design v, no kind-specific learning | design v, acquired |
|---|---|---|---|
| knapsack | 0.8397 | 0.9032 | 0.9181 |
| p-median | 0.6920 | 0.6852 | 0.6847 |
| job shop | 0.7994 | 0.7931 | 0.7768 |
| quadratic assignment | 0.4723 | 0.3505 | 0.3705 |

Mixed with the generic way, and the tables below say why: on quadratic assignment the generic
way is the wrong one. This is a change of the learner made by its designer. It is not a
self-modification and counts for neither half.

## The 729 ways on six kinds (`experiments/dev_ways.py`, `scripts/ways_read.py`)

Every way on the training problems of a kind, two searches each, a search allowed three
constructions of units. Score of the assignment a search ends on, mean over problems.

| kind | the generic way | median way | best way | worst way |
|---|---|---|---|---|
| quadratic assignment | 0.5070 | 0.4923 | 0.5851 | 0.4131 |
| weighted tardiness | 0.2667 | 0.2004 | 0.4521 | 0.0109 |
| knapsack | 0.8535 | 0.8473 | 0.8587 | 0.8445 |
| p-median | 0.6826 | 0.6811 | 0.6885 | 0.6785 |
| quadratic 0-1 | 0.5708 | 0.5612 | 0.5814 | 0.5449 |
| maximum clique | 0.6911 | 0.6911 | 0.6911 | 0.6911 |

* One setting decides: which operators there are at all. With evaluations only: +0.143 on
  tardiness and +0.032 on quadratic assignment against the mean of all ways; with repairs only:
  −0.171 and −0.039. On knapsack and p-median the signs are the other way round (small at this
  length of search).
* So the ways rank alike inside two groups of kinds and oppositely between them: rank
  correlation +0.74 (knapsack, p-median) and +0.86 (quadratic assignment, tardiness), −0.56 to
  −0.74 across. The way that is best on the other kinds, used on a kind left out, is 0.081
  *worse* there than the generic way on average. There is no better generic way to find; what a
  kind needs has to be found on the kind.
* What a kind's own best way is worth over the generic one: +0.078, +0.186, +0.005, +0.006,
  +0.011, 0.

## Three ways to carry something from kind to kind, simulated on those tables

**The settings of the race that acquires** (`scripts/race_sim.py`; 243 settings: how many ways
enter, how far from the version's own, how many are kept, on how many problems, how the winner
is checked). A race gains over the generic way what its number of trials buys (wider, farther,
more problems: +0.002 to +0.011 on average) and nothing else: a setting that is good on some
kinds is not good on another (correlations −0.37, −0.22, +0.25, +0.09), and the same race over
all kinds together, which would be the improver's, ends below the generic way. Rank correlation
between a setting's worth as an acquirer and its worth in that pooled race: +0.03.

**A memory of ways, keyed by what a problem looks like** (`scripts/sim_memory.py`; six kinds,
one left out, 200 draws; acquisition is a sweep over the settings from a starting way, with a
cap on trials). Starting from the way remembered for the kind that looks most alike:

| trials allowed | generation 1 − generation 0 | recursive − frozen, generation 2 | generation 3 | recursive − shuffled, generation 3 |
|---|---|---|---|---|
| 18 | +0.0042 (0.0015) | +0.0005 (0.0017) | +0.0010 (0.0017) | +0.0128 (0.0021) |
| 36 | +0.0033 (0.0014) | +0.0004 (0.0015) | +0.0003 (0.0013) | +0.0086 (0.0016) |
| 72 | +0.0025 (0.0012) | −0.0001 (0.0012) | −0.0002 (0.0013) | +0.0018 (0.0013) |

The first half shows, small, and only for the pair of kinds that look alike (quadratic
assignment and tardiness: +0.006 and +0.018 at 18 trials). The second does not: a memory made
by a learner that itself started from memory is no better on a kind left out than a memory made
by generation 0 again.

**Which variables a repair takes out** (`scripts/pick_probe.py`): choosing them by what they
cost when they were assigned, by how little they had to lose, or by how late they came is worse
than choosing them at random (knapsack, twelve variables: 0.958 at random, 0.852 otherwise,
which is where the construction left it). Nothing to learn there with these descriptions.

**Moves built from the same parts** (`scripts/op_probe.py`; six training instances, the budget
of a fresh problem). Taking every variable off one option and assigning them again, with that
option closed or open, or redoing a run of consecutive variables: p-median 0.705 and 0.703
against 0.702 for the generic way; quadratic 0-1 0.962 with the option left open against 0.943;
knapsack, clique, quadratic assignment and tardiness lower than the generic way. No move of
that sort is worth what would make constructing moves a space of its own.

## Where this leaves the second half

The same thing as in design t, in a different form of problem and with effects ten times the
size. What a kind needs is found on the kind, by the learner as it is, within its budget. What
carries from kind to kind is one fact per group of kinds, known after one pass. A version that
knows it is no better at finding the next thing, because there is no next thing of that sort
to find.

`tables.tar.gz` holds the six tables; `scripts/` what read them.
