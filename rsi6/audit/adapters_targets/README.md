# Adapters of the targets and of the reserves: build and audit records

These adapters were written after the first two improvement processes were frozen (amendment
1), by builder agents that did not write the learner, each in its own copy of the package, and
audited by other agents with their own parsers and evaluators. No agent ran the learner on a
benchmark instance; the role lock on targets and reserves stays (no `unlock` record). The files
here are the agents' structured reports, as returned (paths of the session's scratch directory
are written `<scratch>/`).

| category | role | reports | outcome |
|---|---|---|---|
| satisfiability | target | `build_`, `audit1_` | admitted |
| routing | target | `build_`, `audit1_` | admitted |
| facility | target | `build_`, `audit1_` (fix and audit again), `fix1_`, `audit2_` | admitted after the fix |
| flow shop | target | `build_` (first attempt), `build2_` (second) | **not buildable**: see below |
| tour | reserve | `build_`, `audit1_` | admitted |
| colouring | reserve | `build_`, `audit1_` (fix and audit again), `fix1_`, `audit2_` | admitted after the fix |

A first run of the builders of satisfiability, routing, flow shop and facility was cut off by
a restart of the session's machine; the workflow was started again and the finished builds
were reused. The adapters of satisfiability and routing that were kept here before their
audit (`pending_not_admitted/`, now removed) are byte for byte the files the audits admitted.

## What was changed when the adapters were merged

Wording findings of the audits, applied to the module texts and anchors:

* satisfiability: the source's words about the sets (the description page says the sets uf*
  hold satisfiable instances only); "a mean of 1 is attainable" now says: by answers of the
  form, not necessarily within a test's budget.
* routing: a parenthesis about another instance that did not support its sentence is removed.
  Three rules that would have left an instance out silently (no solution file, published routes
  that do not reproduce the published cost, a published cost above a random answer's length)
  now stop the adapter from loading instead. None is active: all 74 instances are used, before
  and after.
* tour: the module text now states the consequence of its score scale that the audit measured.
* facility: the anchor now says that the fresh side has three instances.

Nothing else was changed. After the merge the package's tests pass (29 of 29), among them the
checks that involve no learner and run on every registered adapter (fast evaluation equals the
specification, the view hides the adapter, one layout, no reference in the problem object,
groups kept apart by the split, malformed answers not repaired).

## Decisions the reports left to the orchestrating session

* **Flow shop cannot be built from here.** The first work order named a file that holds the
  generator and no bounds (an error of the work order). The second named the benchmark's own
  page; its host did not answer (about 35 requests over 40 minutes by the builder, one more by
  the session at 01:13 UTC on 2026-11-13: gateway error 503, upstream connection timeout). No
  other address was used and no value was typed from memory. The adapter text and its checks
  exist in the builder's scratch directory and were never run on real reference values. By the
  registered reserve rule the remaining reserve, **generalised assignment (genassign)**,
  replaces flow shop as a target; tour and colouring are bound as the external gate of process
  c by amendment 3. The `replace` record is written to the ledger when the adapter of
  genassign is admitted and the driver of process c is not writing.
* **Satisfiability will probably read 0 for every arm.** The score is all or nothing (an
  assignment that falsifies a clause is not a valid answer). The auditor measured, with its own
  local search and not the learner, that a satisfying assignment of a fresh instance takes
  thousands of evaluated answers, and the registered test budget pays for a few hundred. The
  category was drawn as a target before anything was built; it stays, and its result is
  reported as it comes out. Replacing it because it is hard would be choosing the targets.
* **Facility: the size rule was restated by the fixer** (at most 100,000 customer-warehouse
  pairs instead of 30,000) to admit the three instances that share no data with the others,
  and the groups are the two size classes. Without that no fresh instance was independent of
  the training ones (audit 1, major). Confirmed here: nothing had been scored, no learner had
  met the category, and the second audit admits the result. What it costs in meaning: 12
  training instances that are one body of data, **3 fresh instances**, a deciding half of two
  and a confirming half of one. The alternative grouping the first audit worded (by common
  cost columns) was computed by the fixer afterwards and gives an unusable split; that is on
  record in `fix1_facility.json`.
* **Colouring: the scale and the threshold were changed after the first audit** (plain ratio;
  0.95 instead of 0.90), with knowledge of the score of a rule with no search and no learning
  on the fresh instances (0.89) and of no learner result; the anchor says so. Its confirming
  half is saturated: that rule scores 0.989 there. A confirmation on colouring therefore
  shows little; the deciding half carries the test.
* **Tour: four small instances carry about half of the fresh mean** on the registered scale.
* **Routing: the low end of the scale** is the expected length of random routes with the
  capacity not looked at, a stated deviation from "random valid answer"; the audit measured the
  difference as below half a per cent.
