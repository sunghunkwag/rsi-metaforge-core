# Through the gate: arm D, an acquisition that allocates its own budget. Result (2026-11-28)

Development only; the plan, committed before the run, is `PLAN.md`; the record is
`rsi6/runs/dev-proof-gate-D.json`.

## What it gave

Same pool, search and checker as the depth measurement; the same total allowance as arm B
(200,000 units for each of the 1619 readable theorems, 323,800,000 in all). D spent
323,639,383 of it: every theorem's first attempt at 100,000, and 164,791,378 on 413 retries.

| | B | D | C (the database's lemmas) |
| --- | ---: | ---: | ---: |
| proved, whole pool | 103 | 122 | 953 |
| implication and negation (202) | 98 | 103 | 167 |
| logical equivalence (190) | 4 | 19 | 109 |
| every later section (1227) | 1 | 0 | 677 |
| proofs the checker rejected | 0 | 0 | 0 |

* **Validity: holds.** Every proof accepted; the total spent within the allowance.
* **The gate: half.** D proves `impbi`, the theorem that introduces the biconditional: on its
  retry at 400,000 units it is found with 211,583. That opens ten further theorems at once
  (`impbii`, `impbid1`, `impbid2`, `2th`, `notnotb`, `con1b`, `con2b`, `pm5.21im`, `2false`,
  `bi2.04` among them). D does not prove `biimp`, the theorem that eliminates it: it was retried
  at 100,000 and at 400,000 units and needs 3,798,041.
* **What the gate opens: does not hold.** After the first section D proves 15 theorems that B
  does not, all in the equivalence section; 100 were needed. Every later section stays closed, in
  D as in B.

## Why it stopped where it did

All 413 retries were made at 400,000 units, four times a first attempt; none at 1,600,000.
The rule picks the most blocked failure and, among equals, the one tried with the fewest units.
The constructor that blocks is the biconditional, and every failed theorem that contains it is
equally blocked, so the rule went through them one by one at four times the first attempt
instead of going deeper on any one of them. `biimp` needed 1.2% of the allowance in one place
(3.8 million units); the retries spent 164.8 million in all, so the bank could have paid for it
many times over. The rule never asked for it.

The signal that picks *what* is missing worked: from the second section on, the retries went to
theorems that contain the biconditional, which is what the section's theorems need. What it does
not tell apart is *which* of them the others need. A rule that could would have to estimate, for
a failed theorem, how much it would unlock if it were proved, before proving it: for instance by
assuming its statement for a moment and trying a sample of the later failures with it. That is a
new rule, and it is not run here; it would be its own plan, fixed before its run.

## What this is and is not

A rule written by this package's designer before the run, not a modification the system made to
itself. It gets through half of the gate at no extra compute and shows where the other half
lies. It says nothing about the hypothesis of the README.
