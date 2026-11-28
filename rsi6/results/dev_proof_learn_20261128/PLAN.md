# A learned component in the proof form, and whether it compounds: plan (2026-11-28)

**Not run.** Written before the depth measurement finished. Its reading
(`../dev_proof_depth_20261128/README.md`) showed that the search's own library does not get
past the second section of the pool, so every arm here would score near zero on the test part,
which begins after it; a first look at the learned order on the first two sections (same
README, "A learned order") was negative. Kept for when a mechanism gets through the gate.

Development only, like `../dev_proof_depth_20261128/`. No category with a role is touched;
the reserves and the sealed targets stay closed; nothing outside the pool of that measurement
is read by a search.

## The question

The search of the proof form orders its candidates by a learned component, `Usage`
(`rsi6/learner/prover.py`): how many of its own accepted proofs used each assertion, updated
after every proof. A generation hands what it learned to the next. The questions are the two
halves of the hypothesis of the README, asked of this component in development:

1. Does a generation that starts from learned knowledge acquire more, on sections of the
   database it never learned on, than generation 0 at the same budget? (first half)
2. Does a generation whose knowledge came from an improved generation's proofs acquire more
   there than the improved generation itself, and more than one generation that learns the same
   way but is given the whole chain's budget in a single pass? (second half, and the
   compute-matched control of the directive, section 5, item 5)

## What is run (`rsi6/experiments/dev_proof_learn.py`)

* **Pool.** As in the depth plan: `set.mm` at the pinned commit, every theorem before "Other
  axiomatizations related to classical propositional calculus".
* **Split.** *Train*: the pool before the section "The conditional operator for propositions".
  *Test*: from that section to the end of the pool (the conditional operator, the weak deduction
  theorem, three-way conjunction and disjunction, nand, xor, nor, the truth constants, truth
  tables, adders). No generation learns on the test part.
* **A pass.** The search through the theorems in database order with a library of the axioms
  and the theorems this pass proved itself; its `Usage` starts from what it is handed and is
  updated after every accepted proof. Every proof is checked by the kernel.
* **Budget.** 50,000 units per theorem in every pass except the control's. Not tuned on these
  arms; it is a quarter of the depth measurement's figure, chosen for run time on two cores.
* **Generations.** P1 learns on train from nothing; P2 from what P1 ended with; P3 from P2.
* **Control Q.** One generation on train that learns the same way, with 150,000 units per
  theorem (the budget of the three generations together), from nothing.
* **Measurement.** Five passes over the whole pool, each at 50,000 units, counted on the test
  part only: E0 starts from nothing (generation 0, which also learns as it goes), E1, E2 and E3
  start from what P1, P2 and P3 ended with, EQ from what Q ended with. The search is
  deterministic: one run of each.

## How it is read

* **Validity.** Every proof is accepted by the checker (proofs the checker rejects count as none
  and are reported).
* **First half (development).** E1 proves at least 2% of the test theorems more than E0, and of
  the theorems where the two differ, E1 proves more than it loses.
* **Second half (development).** E2 exceeds E1 and E3 is not below E2, each by at least 1% of
  the test theorems with more gained than lost; and E3 exceeds EQ by at least 1% of the test
  theorems with more gained than lost.

What a reading that holds would and would not say. It would be the first development reading
in this package with both halves: a learned component whose next generation, made from an
improved generation's own proofs, acquires more on sections it never saw, beyond what the same
learning given the same total compute reaches in one generation. It would not be a registered
result: one pool, one split, one budget, one run each, and the component is a small one (an
order of candidates). What it learns is about its own library (which assertions its proofs use),
not about any section's names. A registered test needs categories no learner has run on, which
`set.mm` has in plenty beyond this pool; registering one is the Owner's decision.
