# TRAIN-only repair revision: beta normalization

The first generic repair pilot retained 16 own-enumerated seeds and evaluated
48 fresh repairs per task, but solved none of its first five unsolved TRAIN
tasks. It also generated 77–83 well-typed repairs per task which could not be
scored by the frozen beta-normal grammar. Replacing a function-valued subtree
with an own-enumerated lambda can create an application redex. Rejecting all
such programs discards a valid compositional neighborhood.

This separate revision adds generic capture-avoiding beta normalization before
the final type, size and frozen-grammar checks. The default initial repair arm
remains unchanged. No target AST, literal, primitive or learned entry is added.
All original caps and program-attempt accounting remain. Raw candidate size
and normalized size both stay at most 12. A separate 20,000-node normalization
work cap debits traversal and substitution visits, and records contractions;
this is extra search work and cannot be presented as free or equal physical
cost. The 10 CPU-second task guard applies during normalization as well.

The revision is compared with initial repair, baseline and other kernels on
original TRAIN only, seeds 11/22/33, combined attempt budgets 64 then 640.
Its own source/test gate is required before the frozen revised comparison.
Source changes during a pilot invalidate that pilot for acceptance; retain and
label it, then rerun the tested version. No validation, TEST or audit feedback
selects this revision. New verified coverage and useful strict real-corpus
compression are necessary for further learner experiments; normalization
correctness alone is not RSI evidence.
