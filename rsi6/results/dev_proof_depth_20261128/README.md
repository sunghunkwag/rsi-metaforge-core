# Does the proof form have depth? Result (2026-11-28)

Development only; the plan, committed before the full run, is `PLAN.md`. The numbers are read
from the three run records by `python -m rsi6.experiments.read_proof_depth` into
`reading.json`; the records are `rsi6/runs/dev-proof-depth-{A,B,C}.json`.

## What was run

One search (`rsi6/learner/prover.py`), 200,000 units per theorem, the 1619 readable theorems of
the pool (`set.mm`, everything before "Other axiomatizations related to classical propositional
calculus"; one theorem is unreadable as a `wff` and left out), three libraries: A, the axioms
and definitions; B, those and what this run proved itself; C, those and every earlier theorem of
the database. Every proof found was run by the kernel's checker.

## What it gave

| | A: axioms | B: its own theorems | C: the database's theorems |
| --- | ---: | ---: | ---: |
| proved, whole pool (1619) | 59 | 103 | 953 |
| proved, after the first 200 (1419) | 0 | 7 | 788 |
| proofs the checker rejected | 0 | 0 | 0 |

* **R0, validity: holds.** Every one of the 1115 proofs found was accepted by the checker.
* **R1, a first step: does not hold.** B proves 44 more than A (2.7% of the pool; 10% was
  needed) and 57 that A does not (100 were needed). A larger library also costs: 13 theorems A
  proves are lost by B, whose search tries more candidates per goal.
* **R2, a second step: holds.** All 57 theorems B proves and A does not have depth 4 or more:
  each rests on a chain of at least four theorems the search proved itself, each one used by
  the next. The depths reach 16. The deepest chain, every link a theorem B proved and the next
  one used: `mp2`, `mpd`, `mpi`, `id`, `idALT`, `pm2.21`, `jarli`, `notnotr`, `con2d`, `con2`,
  `con2i`, `notnot`, `con1`, `con1i`, `simplim`, `pm2.5g`, `pm2.5`.

Where the search's own theorems stop, by section of the pool:

| section | theorems | B proved |
| --- | ---: | ---: |
| implication and negation (the first section) | 202 | 98 |
| logical equivalence | 190 | 4 |
| conjunction, disjunction, mixed connectives, and every later section | 1227 | 1 |

## What it says

In the proof form a finding of the search makes later findings reachable, over many steps: no
theorem B gained on the axioms is less than four of its own findings deep. That is the property
whose absence stopped every mechanism in the assignment and prediction forms (instruction 20,
"The obstacle"), and it is measured here, not supposed.

It also shows where it stops, and why, exactly. The second section begins with the definition
of the biconditional (`df-bi`), and nearly every later theorem uses the biconditional, directly or
through the definitions built on it. The two theorems that introduce and eliminate it from its
definition, `impbi` and `biimp`, are not found by the search at this budget; `biimp` is not
found even with the database's lemmas (C). Without them the search's own library cannot follow
the database past the first section, while the same search with the database's lemmas proves 788
of the 1419 theorems after the first 200. The obstacle in this form is therefore not that
nothing carries; it is a gate of a few theorems that everything downstream depends on, which
the search's own findings do not reach.

## A learned order (a first look after the run; not in the plan)

The search orders its candidates by number of hypotheses and recency. A learned order was tried
on the first two sections only: `Usage` (`rsi6/learner/prover.py`) counts how many of the run's
own accepted proofs used each assertion, is updated after every proof, and puts the most used
first (`scripts/probe_learned_order.py`, record `rsi6/runs/dev-proof-learned-order-probe.json`).
At 200,000 units it proved 93 theorems of the two sections against B's 102, and 2 of the 190 of
the equivalence section against B's 4. Ordering by past use does not get through the gate; it
puts the lemmas of the first section first, which is not what the second section needs.

## What this is and is not

What this is not: the accumulation of solved theorems (B) is not evidence for the hypothesis of
the README, as the directive says. No learner modifies itself here. The result says that this
form has what the second half needs and that the first thing an acquisition mechanism here has
to learn is how to get through such a gate: where to spend its search, and which intermediate
statements to pose itself, when a theorem that would unlock many others does not yield.
