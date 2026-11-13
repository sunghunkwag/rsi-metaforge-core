# Adapters of the third adoption set: build and audit records

The adapters of `partitioning` and `setcover` were written by builder agents that did not
write the learner, each in its own copy of the package, and audited by other agents with their
own parsers and evaluators. No agent ran the learner on a benchmark instance (the role lock
stays until the gate of round b1). The files here are the agents' structured reports, as
returned:

* `build_partitioning.json`, `audit1_partitioning.json` (verdict: admit; three minor findings
  on wording, applied when the adapter was merged).
* `build_setcover.json` (the first build), `audit1_setcover.json` (verdict: fix and audit
  again; major finding: the text misstated where the reference values come from),
  `fix1_setcover.json` (text corrected; every reference value shown from the pinned files to be
  attained and optimal), `audit2_setcover.json` (verdict: admit; it proved optimality of all 40
  values with its own code).

A first attempt of both builders was cut off by the session's usage limit and produced no
report; the second attempt reused its downloads after checking them against fresh ones.

Decisions the reports left to the orchestrating session:

* Set covering leaves out eight published instances within its size limit (scpclr10 to 13,
  scpcyc06 to 09) because the source names no reference value for them. Accepted: an instance
  without a reference cannot be scored.
* Set covering's threshold (0.95) equals the mean, on the fresh side, of a textbook heuristic
  the builder measured (0.9501). Whether it was fixed before that was seen cannot be verified.
  Kept as it is and reported as it is: the threshold is an operating point.
* The kernel's split gives set covering 20 fresh instances, not 24, and graph partitioning 24
  fresh instances on 8 graphs of one family.
* The partitioning reference is a published upper bound that the auditor's plain local search
  went below on 22 of 78 instances.
