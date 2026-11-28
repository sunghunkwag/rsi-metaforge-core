# Arm E: an acquisition that estimates what a missing theorem would unlock, then spends there. Plan (2026-11-28)

**The full run was not made.** The development check on the first two sections, run before
this plan would have been committed, came out below arm D (below, "The development check"), so
the rule was not taken to the full pool. The plan is kept as written so that the next rule starts
from it.

Development only, like the depth and gate measurements: the same pool, search, checker, allowance.

## Why

Arm D (`../dev_proof_gate_20261128/`) found the construct its failures share (the
biconditional) and spent its bank on theorems containing it, but treated them as equals: 413
retries at four times a first attempt, none deeper. It proved `impbi` and left `biimp`, which
needs 3.8 million units, though the bank paid 164.8 million for retries. What it lacked was a way
to tell which missing theorem the others need. That can be asked before the theorem is proved:
take its statement as given for a moment, and see whether failed theorems after it go through.

## Arm E

Arm D with one change, in what an investment does.

* **Allowance, first attempts, bank.** As in D: 200,000 units for each theorem, a first attempt
  at 100,000, the rest into the bank, nothing spent that is not in it.
* **When.** After 10 first attempts in a row have failed, one investment is made; then the
  count starts again.
* **Candidates.** The 8 failed theorems of highest priority (D's: the largest blocked ratio of
  the constructors of their statement; among equals, the earliest).
* **What a candidate would unlock.** For each candidate, the 8 most recent failed theorems after
  it are tried at 20,000 units each, with the library as it stands at each of them and the
  candidate's statement taken as given. These attempts are probes: what they find is not a proof
  and is thrown away; a candidate's *leverage* is how many of its probes succeed. Probes are paid
  from the bank, and a probe the bank cannot cover is not made.
* **The investment.** The candidate with the highest leverage, if it has at least 1 (among
  equals, the higher priority, then the earliest), is tried with four times its last units, then
  four times that, and so on, while the bank covers the next attempt and the investment has spent
  at most half of what the bank held when it began. Only what is earlier in the database is used.
  If no candidate has leverage, D's single retry is made instead.
* **After a theorem is proved.** As in D: it joins the library, and the failed theorems after
  it, up to the current position, are tried once more at 100,000 units while the bank covers it.

A development check on the first two sections (392 theorems) was run before this plan was
committed, to see that the rule runs and what its probes cost; its numbers are reported with the
result and are not part of the reading.

## How it is read

* **Validity.** Every proof accepted by the checker; the total spent within the allowance.
* **The gate.** E proves `impbi` and `biimp`.
* **What the gate opens.** E proves at least 100 theorems after the first section that B does
  not, at the same total allowance.
* Reported beside it: proved per section against B, D and C; the units spent on probes and on
  investments; where it stops.

The rule is this package's designer's, written before the full run; not a modification the
system made to itself. A reading that holds would say that in this form an acquisition that
asks what a missing theorem would unlock, before proving it, gets through gates that the same
search with the same total budget does not; which is what a self-modifying version of the rule
would have to find for itself.

## The development check (first two sections, 392 theorems; `rsi6/runs/dev-proof-leverage-E-dev392.json`)

| | B | D | E |
| --- | ---: | ---: | ---: |
| implication and negation (202) | 98 | 103 | 91 |
| logical equivalence (190) | 4 | 19 | 18 |

E spent 75.5 million of its 78.4 million units: 23.5 million on probes, 19.7 million on
investments. It proved `impbi` and not `biimp`.

What happened, from the record of its 19 investments:

* The probes found `biimp` once. At that investment `biimp` had leverage 3 and every other
  candidate 0, so E pursued it: 400,000 units, then 1,600,000. The next step, 6,400,000 (it needs
  3,798,041), was more than half of what the bank held at that moment, so the investment ended
  there. At later investments its probes found nothing, and it was not pursued again.
* Most probes find nothing: 14 of the 19 investments had leverage 0 for every candidate and fell
  back to D's single retry. At 20,000 units a later failure rarely goes through even with the
  right theorem given.
* Leverage 1 is noise. `sylbi` had leverage 1 and was pursued to 6,400,000 units in vain; it
  needs `biimp` first. In the first section the probes chose theorems that were not found at
  1,600,000 either, and the units the probes cost are units D spent on first-section retries
  that succeeded.

What it says about the next rule: the question "what would this theorem unlock" is the right
one (it found `biimp` when nothing else in the package did), but asked this cheaply it is
mostly silent, and the investment it triggers has to be allowed to finish. Both are questions
of budget inside the rule, to be fixed before a run and tested on sections the fixing did not
look at.
