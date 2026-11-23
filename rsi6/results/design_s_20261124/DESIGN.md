# Design s: one search procedure at two levels

Written 2026-11-23, 21:20 to 21:55 UTC, under instruction 19 (`rsi6/OWNER_DIRECTIVE.md`), before
any run of the design on the runners. Development: nothing in this directory is evidence until
a registered test says so.

## What it is for

After the gate of process d two things were left (`../dev_landscape_20261122/G1.md`,
`../dev_recursion_20261122/`):

1. What remains to gain differs by category: a setting that helps one category hurts another.
2. In the first design a learner that acquires better is not thereby a better improver. Its
   acquisition is a search over the weights of a policy; as an improver it only edits a known
   version with its `edit.*` fields. A change of the acquisition leaves the improver as it was.

Design s (`rsi6/learner/design_s.py`) answers the second directly and the first as far as a
search procedure can:

* **One function, `search`, is the acquisition and the improver.** It is written against a
  task (a starting point, training problems, the cost of an evaluation, the evaluation of
  candidate points). The learner calls it on the weights of its policy. The improver
  (`rsi6/meta/chain_s.py`) calls the same function on the space of versions, with the fields
  of the version that is doing the improving. The correspondence, line by line, is the table in
  the docstring of `chain_s.py`. With the new fields at their defaults `search` is the first
  design's acquisition exactly: `rsi6/tests/test_design_s.py` compares the two run by run
  (scores, capability, report, counted units).
* **Two steps that adapt inside one search**, as fields with the first design's behaviour as
  default: `adapt.spread` (`"self"`: every candidate draws its own multiplier of the spread and
  the spread follows the multipliers of the candidates that were kept) and `adapt.race` (`1`:
  the worse half of the candidates is dropped after each problem of a round, so a candidate
  gets as many evaluations as it earns). Both are generic steps of a population search.
  Neither is known to help; that is measured.

## What was known before it was written

Said first, because it limits what the design can give.

* **Where the first design stands, more search buys little.** A scratch diagnostic on this
  session's machine (no ledger; seeds 739901 to 739908; `scripts/oracle_budget.py`): the adopted
  version with 4 and 16 times the training budget.

  | Category | budget ×1 | ×4 | ×16 | runs each |
  |---|---|---|---|---|
  | quadratic assignment | 0.5015 | 0.5220 | 0.5245 | 8 |
  | p-median | 0.6910 | 0.6847 | 0.6961 | 8 |
  | multidimensional knapsack | 0.8464 | 0.8536 | not run | 4 |

  Sixteen times the budget adds about 0.02 on quadratic assignment and nothing that can be
  told from noise on p-median. On these categories what the learner can acquire is bounded by
  what a weight vector of its policy can express, not by how well it searches.
* **The scan around the adopted version, read per category**
  (`scripts/g1_percat.py` on `../dev_landscape_20261122/artifacts/landscape_g1.tar.gz`): taking
  for every category the best change of a field the search reads, chosen on the same 8 (or 4)
  seeds it is scored on, gives +0.021 on average over the nine categories. That number contains
  the luck of the choice; what a procedure could really collect per category is well below
  it. The same table shows what is clear in this space: the directions down. `model.batch` 8
  (−0.045), `model.pop` 32 (−0.011), `model.elite` 0.5 (−0.020).

So this design is not expected to lift the top of what the first design acquires. What it can
show is the thing no earlier design could even exercise: whether, when the improver is the
acquisition itself, a version that has been improved is better at producing the next version.

## The list, and why chains start everywhere in it

A chain of design s moves in a list of 324 mechanisms: every combination of

| Field | Values |
|---|---|
| `model.batch` | 2, 4, 8 |
| `model.pop` | 8, 16, 32 |
| `model.elite` | 0.1, 0.25, 0.5 |
| `model.sigma` | 0.2, 1.0, 2.0 |
| `adapt.spread` | schedule, self |
| `adapt.race` | 0, 1 |

with every other field as in generation 0 of the first design. Generation 0 itself and the
version process d adopted are two of the 324. (288 of them search differently: a population of
8 keeps 2 candidates at `model.elite` 0.1 and at 0.25.)

The list is closed and small on purpose. Every mechanism of it is measured on every category
(`rsi6/experiments/dev_grid.py`), and then a search over the list needs no new run: every
evaluation an improver asks for is a row that exists. Chains can therefore be run from every
starting mechanism and repeated until the only uncertainty left is that of the measured runs.
The earlier recursion run (`../dev_recursion_20261122/`) had 12 repetitions of one start and
could not tell its arms apart.

**Chains start from every mechanism of the list, not from generation 0 only.** Generation 0
was set by hand and one validated step later sits, as far as the scans know, near the top of
this list; from there neither arm has anything to find, and a comparison of improvers says
nothing. Whether an improved improver matters can be measured only where there is something to
improve. The mean over all 324 starts is a property of the list, not of a chosen start; the
chains from generation 0 and from the adopted version are reported separately, whatever they
show.

## One generation of a chain

The improver draws 16 training problems: the same number of (category, seed) pairs from each
discovery category. It runs `search` from the incumbent version: a point is a version (one
coordinate per field of the list, one step of the list is one unit), an evaluation is the
acquired score of that version's run on the pair, the budget is `train` (40) evaluations of
every problem, as an acquisition has 40 construction units of every training problem. If the
version the search ends on beats the incumbent on the held-back pairs it is the nominee. The
nominee meets the incumbent at the gate: the registered rule (`rounds.gate`: margin 0.005, 10 %
point of the gain above zero, CPU at most 1.15 times; then the confirmation above zero), on
categories the improver did not read, the gate on the first half of their seeds and fresh
instances, the confirmation on the other halves. Only a nominee that passes replaces the
incumbent.

Arms, which differ in who nominates: **recursive**, the current version of the chain;
**frozen**, the version the chain started from, whatever has been adopted since; **random**, a
version of the list drawn uniformly; **neighbour**, a uniformly drawn change of one field. The
recursive and the frozen arm use the same random stream, so they are one chain until an
adoption makes their improvers differ.

The endpoint is read on test categories that neither the improvers nor the gates read.

## Stages

1. **Development (this run).** The table on eight assignment categories of the pool
   (`rsi6/runs/dev-grid-s.json`), chains with the categories rotated through the three roles,
   the reading fixed in `PREDICTION.md` before the plan runs.
2. **Only if that reading holds:** categories no learner has run on are built without any run
   of a learner on them, the same reading is registered, and the table and the chains are
   repeated on new seeds with the final test on those categories. The two reserves and the four
   sealed targets are not used for it.

## What is not claimed, whatever the tables show

* The list is closed and written by the experimenter. A chain chooses among 324 mechanisms; it
  cannot write one that is not listed. A result here is about whether improvement of the
  improver compounds inside such a list, not about open-ended self-improvement.
* Starts are drawn over the whole list. A chain that climbs from a poor mechanism to a good one
  recovers settings; it does not exceed the best of the list, and the best of the list is not
  expected to exceed the adopted version by much.
* A development reading is not a result. Only stage 2 can be reported as one.
