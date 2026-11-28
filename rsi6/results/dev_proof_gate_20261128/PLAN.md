# Through the gate: an acquisition that finds what it is missing and spends on it. Plan, fixed before the run (2026-11-28)

Development only, like `../dev_proof_depth_20261128/`: the same pool, the same search, the same
checker, nothing outside the pool read.

## Why

The depth measurement found that the search's own library stops after the first section of the
pool, at the definition of the biconditional: the theorems that introduce and eliminate it,
`impbi` and `biimp`, are not found at 200,000 units, and almost every later theorem depends on
them. A probe after that run (not a result; the reason for this plan) found both with the same
search and the same library when given more units: `impbi` at 211,583, `biimp` at 3,798,041.
So the gate is a matter of where the units go, and a mechanism that can tell which failures
block the rest could spend on them out of what other theorems leave unused.

## Arm D, an acquisition that allocates its own budget

Arm D is arm B (the library of the axioms and of what the run proved itself) with one change:
how the units are spent. The search is unchanged.

* **Allowance.** Every theorem brings 200,000 units, as in B; the total is 200,000 times the
  number of readable theorems, the same as B's. What a theorem does not spend goes into a bank.
  The bank is the only source of extra units, so D can never spend more than B was allowed.
* **First attempt.** Every theorem, in the database's order, is tried once with 100,000 units.
* **What is missing.** For every syntax constructor (a label such as `wi` or `wb`, never a
  section's name) the run counts the theorems attempted so far that contain it: proved, and not
  yet proved. A constructor is *blocked* by the ratio not-proved / (proved + 1). A failed
  theorem's *priority* is the largest blocked ratio among the constructors of its statement and
  hypotheses.
* **When to spend.** After 10 first attempts in a row have failed, the run retries one failed
  theorem: the one of highest priority; among equals, the one tried with the fewest units; then
  the earliest. The retry has four times the units of its last attempt and uses only what is
  earlier in the database. It is made only if the bank covers it.
* **After a retry proves a theorem.** The theorem joins the library; the failed theorems after
  it, up to the current position, are tried once more at 100,000 units each while the bank
  covers it; the count of failures in a row starts again.
* Every proof is checked by the kernel; the total spent is asserted to stay within the total
  allowance.

## How it is read

* **Validity.** Every proof accepted by the checker; the total within the allowance.
* **The gate.** D proves `impbi` and `biimp`.
* **What the gate opens.** D proves at least 100 theorems after the first section that B does
  not, at the same total allowance.
* Reported beside it: proved per section, the units spent on retries, and what D still does not
  reach that C (the database's lemmas) does.

What a reading that holds says, and what it does not. It says that in this form an acquisition
that measures which constructs it is failing on and spends there gets through a gate that the
same search with the same total budget does not. The rule is this package's designer's, written
here before the run; it is not a modification the system made to itself, and it does not touch
the hypothesis of the README. It is the first mechanism of this form with something measured to
gain, which is what a self-modifying version of it would need.
