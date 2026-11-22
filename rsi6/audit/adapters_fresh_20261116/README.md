# Adapters of four categories no process had used: build, audit, fix and second-audit records

Built on 2026-11-16 for the experiments that follow the open design (the Owner's instructions 12
to 14 require held-out evaluation on tasks no earlier attempt has seen). Every adapter was written
by a builder agent in its own copy of the package (no learner, no ledger, no other category's
data), audited by another agent with its own parser and evaluator, fixed by a third, and audited
again by a fourth. No agent ran a learner on any instance of these categories; their role is
`fresh` (`registry/roles.json`), locked by the kernel until the held-out stage of a registered
experiment writes an `unlock` record. The files here are the agents' structured reports, as
returned (paths of the session's scratch directory are written `<scratch>/`).

| category | source | instances | first audit | second audit |
|---|---|---|---|---|
| tardiness | OR-Library single-machine total weighted tardiness (wt40, wt50, wt100; wtopt40, wtopt50, wtbest100b) | 375 | admit after fixes | admit |
| quadratic | Biq Mac library, unconstrained binary quadratic programming (bqp50/100/250, gka a to e, be; optima from biqmaclib.tex) | 150 | admit after fixes | admit after fixes |
| projects | PSPLIB single-mode RCPSP j30 and j60 (optima, lower and upper bounds as published) | 960 less the trivially solved ones | admit after fixes (one blocking finding) | admit after fixes |
| clique | Second DIMACS challenge maximum clique graphs (at most 1000 vertices; sizes from results.dmclique, solution files, comment lines) | 56 | admit after fixes | admit |

Each second audit confirmed parsing, evaluation, references, relabelling and the absence of
privileged information with code of its own (for example: quadratic, all 150 references and
matrices and 360 complete answers exact; tardiness, all 375 instances and 300 answers; projects,
all 960 files and 720 references; clique, all 56 graphs and 948 answers).

## What was changed when the adapters were merged

* quadratic: the anchor and the threshold paragraph now say, in the second auditor's words, that
  neither reaching the threshold nor a gain within the metered budget is evidence on this
  category (computation on the exposed arrays is not metered), and that a gain counts only when
  the answers compared were produced with equal CPU time; the plain-descent figures that the
  second audit did not reproduce now carry the audit's ranges beside them.
* clique: the scorer and decode accept only `numpy.ndarray` itself (a masked array subclass is
  scored 0, checked); two documentation errors corrected (the count of the volume's duplicate
  graphs; johnson8-2-4 is the subgraph of hamming8-4 induced on its weight-2 vectors).
* the four adapters and their manifests are new files; they are not in the registry on disk
  (`environments/__init__.py` is pinned by the open registration until its last stage);
  `environments/fresh.py` installs them at run time for a registered driver, and
  `registry/fresh.json` lists them with the hash of each module as merged.

## Findings left open, and what a registration that uses these categories must say

* Thresholds are operating points, and on all four categories plain procedures that learn
  nothing reach or come close to them (one-pass dispatching rules on tardiness, plain descent on
  quadratic, the latest-finish-time rule on projects, greedy on the confirming half of clique).
  A registration must not count a threshold crossing as an acquired capability; it must compare
  arms at matched measured CPU.
* quadratic: the be files of one generator seed share stretches of the library generator's value
  stream across the split and across the halves (disclosed; the second auditor found no
  position-by-position relation and no exploitable leak). The rule that the bin-packing adapter is
  held to (no shared stretch) is therefore not met; a registration must record that.
* projects: the score scale is compressed at the top (random lists in precedence order score
  0.970 on the fresh split; 0.01 of score is about 3.2% of a j60 makespan), so its paired
  differences are small next to other categories'; a registration should report the makespan
  excess beside the score.
* tardiness: on the deciding half 9 of 14 instances are at the ceiling of the due-date order; the
  two halves are different due-date regimes.
* The kernel's test that looks for a reference value among the scalars of a problem would flag
  zero references spuriously if applied beyond the first instance (tardiness has 53 zero
  references); it passes as written.
