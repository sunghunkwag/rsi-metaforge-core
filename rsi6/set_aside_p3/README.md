# Set aside: Python Programming Puzzles as an external suite

Everything in this directory was written on 2026-11-11 for an earlier form of RSI-6 and is
**not part of the research plan** (`../RESEARCH_PLAN.md`). It is kept as a record.

* `freeze_p3.py`, `data/p3/`: the suite (397 puzzles, 1,715 instances, MIT licence) split by a
  seeded rule into development, validation and evaluation files, with reference solutions and
  docstrings removed. The validation and evaluation files have not been read by anyone.
* `tasks.py`: a loader that refuses the sealed splits without a stated purpose.
* `sandbox.py`: runs a verifier natively with a time limit. **Never run from this session**:
  the command that would have used it was denied by the session's permission classifier,
  because the verifiers are code from an external source.
* `interp.py`: a restricted interpreter for verifier text, written after the denial. **It has
  not been run on any external verifier and it does not preserve the verifiers' semantics**;
  section 8 of the plan lists the known differences from CPython and why equivalence cannot
  be shown here. No result may be drawn from it.

Why it is set aside: the Owner ruled out puzzle solving as the primary object of the research,
and the suite cannot be scored here without executing external code.
