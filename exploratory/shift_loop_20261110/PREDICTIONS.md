# Hybrid shift loop: predictions written before any hybrid run

Written 2026-11-10 before the harness existed. Exploratory, report-only, on exposed
partitions; nothing here is a registered result of the package and nothing gates on it.
Already known when this was written: the map-shift pilot on FRESH-1 at 10^5 (13 of 17
element-wise tasks with the restored vocabulary, 2 of them coincidental).

## Set-up fixed in advance
- Engine: rsi5 C1, unchanged, restored vocabulary. Budget B = 10^4 candidates per task per
  generation for the loop; one confirmation at 10^5.
- Learning set: TRAIN (36) + RESERVE-NEAR (100). Held out, report-only: VALIDATION, RESERVE-FAR,
  RESERVE-FAR2, FRESH-1, FRESH-2, COMPOSE-24 (202 tasks). Every decision of the loop reads the
  learning set only (verifier verdicts, one query per task per generation).
- Components: S = element-wise spec shift; F = fusion of partial solutions in output bit-vector
  space into `if` terms (idea 4); C = constants abduced from the examples instead of enumerated
  (the SMT stand-in: no solver exists under the standard-library rule); L = lambda-term compression
  of verified programs into new symbols, at most 3 per generation, by description-length gain;
  T = on saturation, roll back to the last gaining generation and ban the abstractions the future
  showed dead (idea 3), at most 3 rollbacks.
- Generation 0 = S + F + C with no learned symbol. Generations >= 1 add L under T.
- Control: the registered enumeration and the generation-0 machinery, each at the loop's
  cumulative budget.

## What would count as recursive self-improvement (all four)
- R1: held-out solves rise in two consecutive generations at equal per-generation budget.
- R2: a gain of generation >= 2 depends on a symbol of an earlier generation (ablation loses it).
- R3: the loop beats generation-0 machinery run once at the loop's cumulative budget, on held-out.
- R4: no human input between generations.
One-shot improvement = gains in generation 1 only. None = no held-out gain after generation 0.

## Predictions
| ID | Prediction | Expected |
| --- | --- | --- |
| H1 | Generation 0 (S+F+C) solves at least 10 more held-out tasks than the registered engine at 10^4 | PASS (moderate) |
| H2 | Generation 1 raises learning-set solves by >= 3 and held-out solves by >= 1 over generation 0 | PASS (low) |
| H3 | Generations >= 2 add at most 2 held-out solves in total: no compounding | PASS (moderate) |
| H4 | Rollback with a ban list (T) changes the best learning-set count by at most 1 and costs >= 3 extra generation runs | PASS (moderate) |
| H5 | F adds >= 3 held-out solves at generation 0, and at least 30% of F's verified FRESH-1 solves are coincidental in the audit | PASS (low) |
| H6 | The loop does not beat generation-0 machinery at equal cumulative budget on held-out (R3 fails) | PASS (moderate) |
| H7 | C adds >= 2 held-out solves at generation 0 | PASS (low) |
| V | Verdict: one-shot improvement at most, not recursive self-improvement | moderate |

# Addendum: the four-idea system (written before any loop run)

Written after the generation-0 ablation at 10^4 was read (registered 89; S 129; S+C 128; S+F 151;
S+C+F 152; fusion in the element space only 140-141; C adds nothing: H7 misses; list-level fusion
passes the verifier with nonsense programs for boolean tasks) and before any generational run.

## What changes
- F is used in the element space only (switch "f"): the audit showed list-level fusion to be a
  source of coincidental solves, and the loop's decisions read verified solves.
- A (idea 1, apoptosis): a move that cuts 60% of the vocabulary's symbols, least used first,
  separately for the element space and the list space; a milder move cuts unused symbols only;
  a random 60% cut is run once as a control and decides nothing.
- E (idea 2, entropy): a move that turns on seeded random mutation of near-miss programs
  (10% of the task budget) after search and fusion fail.
- L (compression) and T (idea 3) as before. The loop tries the moves compress, apoptosis-60,
  apoptosis-unused, entropy at each state; a move is accepted only if verified learning-set solves
  rise strictly; a rejected move goes on the ban list; when no move is accepted the loop rolls back
  one accepted step, bans it and branches again (at most 3 rollbacks, at most 24 runs).
- Two configurations, both fixed now. A: learn TRAIN + NEAR, held out the other six partitions.
  B: learn the six single-routine partitions (TRAIN, NEAR, VALIDATION, FAR, FAR2, FRESH-1), held
  out the two composition partitions (FRESH-2, COMPOSE-24). B is the favourable case for
  compounding: symbols learned from single routines could make compositions short.
- Budget 10^4 per task per run. Control: generation-0 machinery (S + C + f) once at runs x 10^4.

## Predictions
| ID | Prediction | Expected |
| --- | --- | --- |
| H8 | Apoptosis-60 is accepted at least once (a smaller vocabulary reaches deeper and solves a new learning task) | PASS (low) |
| H9 | An accepted apoptosis lowers held-out solves by at least 1 in configuration A (the vocabulary overfits the learning set) | PASS (low) |
| H10 | Entropy (mutation) is never accepted, or its accepted gain is at most 1 learning task | PASS (moderate) |
| H11 | Random apoptosis loses at least 10 learning solves | PASS (moderate) |
| H12 | Configuration B: held-out composition solves rise by at least 3 over generation 0 across the loop | PASS (low) |
| H13 | In neither configuration does the loop beat generation-0 machinery at equal cumulative budget on held-out (R3 fails) | PASS (moderate) |
| H14 | Some accepted abstraction of generation >= 2 has depth 2, and it is used in at most 2 verified held-out solutions | PASS (low) |
| V2 | Verdict for both configurations: improvement over generation 0 in at most two accepted steps, then saturation; R1 to R4 are not all met | moderate |
