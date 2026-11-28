# Does the proof form have depth? Plan, fixed before the full run (2026-11-28)

Development only. Nothing here is registered, no category with a role is touched, and the
reserves and the sealed targets stay closed. The proof form has no role in
`rsi6/registry/roles.json`; this plan reads one section of `set.mm` and leaves the rest of the
database unread by any search.

## Why this is asked

Eight mechanisms of self-modification were measured in the assignment and prediction forms and
none showed the second half of the hypothesis. The reason was measured each time
(`OWNER_DIRECTIVE.md`, instruction 20, "The obstacle"): what a kind needs is found on the kind,
and what carries between kinds is small and known after one pass, so no improver has a second
step to find. Depth was named as what is missing: something whose first part makes the rest
easier to find. The protocol names a third form, formal proof (`RESEARCH_PLAN.md`, section 2,
C1: Metamath `set.mm`), which was never built. This plan asks whether that form has depth at
all, at the object level, before a learner is built in it.

## What is measured

* **Data.** `set.mm` at commit `04fc7e75a93e788879987546b4a0921891b96b07` of `metamath/set.mm`,
  pinned by SHA-256 in `rsi6/environments/manifests/setmm.json`.
* **Pool.** Every theorem (`$p` with typecode `|-`) before the section "Other axiomatizations
  related to classical propositional calculus": the section "Propositional calculus" and the
  pre-logic before it. 1620 theorems; a theorem whose statement the kernel cannot read as a
  `wff` is counted as unreadable and left out.
* **Search.** `rsi6/learner/prover.py`, unchanged between arms: backward chaining with
  unification, depth deepened one step at a time, one unit per unification attempt.
* **Budget.** 200,000 units per theorem, the same in every arm. The figure was chosen on the
  first 200 theorems of the pool, where A proved 59, B 96 and C 165 at this budget (20,000 units
  gave A 43, B 31 and C 55 on the first 80). Those 200 are inside the pool; the reading below is
  given for the whole pool and for theorems 201 to the end separately.
* **Arms.** `A`: axioms and definitions stated before the theorem. `B`: those and every earlier
  theorem of the pool that this run proved itself and the checker accepted. `C`: those and every
  earlier theorem of the database (a reference: what the database's own lemmas reach).
* **Checking.** Every proof found is run by the kernel's checker (`rsi6/kernel/metamath.py`).
* **Depth of a proof in B.** 0 if the proof uses no theorem of the pool; otherwise 1 plus the
  largest depth among the pool theorems it uses (each of them proved earlier by B itself).

## How it is read

* **R0, validity.** Every proof found is accepted by the checker. One rejection voids the run.
* **R1, a first step.** B proves at least 10% of the readable pool more than A, and at least 100
  theorems of the pool are proved by B and not by A.
* **R2, a second step.** At least 30 theorems proved by B and not by A have depth 2 or more: they
  use a theorem B proved that itself used a theorem B proved.
* **Descriptive.** The distribution of depths in B, the largest depth, and the theorems A proves
  and B does not (what a larger library costs a search that does not choose among it).

R1 and R2 both holding says that in this form a finding of the search makes later findings
reachable, over more than one step. It does not say anything about the hypothesis of the
README: this is the accumulation of solved theorems, which the directive names as no evidence of
meta-level improvement by itself. It says whether the form has what the second half needs and
the other two forms did not.
