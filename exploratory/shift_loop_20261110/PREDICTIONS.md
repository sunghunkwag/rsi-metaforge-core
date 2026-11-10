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

# Addendum 2: three ideas added on top (written before any run with them)

Written after loops A and B, the ablations of A's best state and the generation-0 ablation
had been read, and before any run of the mechanisms below. The equal-cumulative-budget
control at 2.4 x 10^5 had not finished.

What the first loop showed: its moves rearrange a vocabulary and none creates a new kind of
search; its acceptance signal (learning-set solves) overfits, and the cut that helped it
find symbols hurts held-out when kept (learned symbols without the cut: 90 learning, 62
held-out in configuration A).

## What is added
- R, representation search. The spec shift S fixes one re-representation of the input (the
  list as its elements). With R, when S does not apply or fails, a tenth of the budget
  enumerates list programs A over the input; every A under which the outputs are the
  element-wise image of A(xs), or A(xs) filtered by a predicate on the value, is a candidate
  re-representation; the first two get an `int -> element` sub-search and the solution is
  lifted as `map f (A xs)` or `filter p (A xs)`. Learned symbols enlarge the set of A.
- D, dream tasks. The driver composes pairs of its own verified learning programs into new
  tasks with known answers (8 public and 8 check examples on seeded random lists): 40 at
  generation 0, 20 more from newly solved programs after each accepted move, at most 100.
  Dream solves count in the acceptance signal (verified learning solves + dream solves) and
  verified dream programs join the compression corpus and the usage counts.
- Regrow, a move that restores the full vocabulary while keeping the learned symbols.
- Moves: compress, apoptosis, unused, regrow. Entropy is dropped (never accepted). Rollback as
  before. Budget 10^4 per task per run, at most 24 runs, configurations A and B as before.
- Control: generation-0 machinery with R, on the real tasks, at the loop's cumulative budget
  (runs x 10^4 x (338 + dream tasks) / 338).

## Predictions
| ID | Prediction | Expected |
| --- | --- | --- |
| H16 | R at generation 0 raises held-out solves by at least 4 over S + C + f at 10^4 | PASS (low) |
| H17 | With dream solves in the signal, the 60% cut is rejected at generation 0 in both configurations | PASS (moderate) |
| H18 | The new loop makes at least 4 accepted steps in configuration B | PASS (moderate) |
| H19 | In configuration B real held-out solves end at least 6 above its own generation 0 and above the first loop's best (26) | PASS (low) |
| H20 | Dream solves rise at least three times as much as real solves (learning + held-out) over the loop: the internal signal inflates | PASS (moderate) |
| H21 | Generation-0 machinery with R at the cumulative budget solves at least as many real held-out tasks as the loop (R3 fails again) | PASS (moderate) |
| V3 | More accepted steps and a larger real held-out gain than the first loop, yet not recursive self-improvement by R1 to R4 | moderate |

# Addendum 3: expert iteration with three principles taken from Terminal-RSI

Written after the public repository of Terminal-RSI (arXiv:2610.22192, jyyang26/Terminal-RSI,
read at commit 8f1e700) had been read, after the controls of the first loop had finished, and
before any run of the mechanism below. The second loop (representation search, dream tasks,
regrow) was running and had not been read.

Nothing of that repository's code is used: it trains a 27B transformer with PPO, which this
repository forbids. Three of its design principles are transferred to the symbolic loop.

| Their mechanism | Their definition | What it becomes here |
| --- | --- | --- |
| Family Dense Reward | a per-family divisor, so a full solve is worth about 1 in every family | the acceptance signal is the sum over learning families of the fraction of the family verified |
| Success-Prioritized Reward | R = S + P / (P + D): every failure below 1, every success at least 1 | only verified solves score; no partial credit enters the signal |
| Recursive Self-Rewrite | successes of a complementary, stronger harness, screened for leakage and freshly verified, become supervision | programs harvested by the same machinery at ten times the budget are compressed into symbols, and a symbol is kept only if tasks of at least two families support it |

What their own notes showed and this study then measured on the first loop: an aggregate
score is mostly a task-mix metric. In configuration A all 17 learning gains are one family
(`slice-k-n`: 12 of 16 in NEAR, 5 of 6 in TRAIN); families with a solve stay 26 of 42; the
family-normalised score moves from 22.47 to 24.05.

## The loop (fixed now)
- Cycle k: (1) harvest: the current vocabulary at 10^5 candidates per task on the learning
  partitions; verified programs join the corpus, one per task, the shortest kept. (2) distil:
  compression proposes symbols; one supported by fewer than two families is banned and the
  next is tried; up to 3 per cycle. (3) gate: the candidate vocabulary is run at 10^4 on every
  task and accepted only if the family-normalised verified score on the learning partitions
  rises; if rejected, its symbols are banned and the cycle retries once. (4) record the student
  at 10^4 on held-out, never consulted.
- At most 6 cycles; stop when a cycle accepts nothing. No vocabulary cut, no mutation, no
  dreams, machinery S + C + f as in the first loop. Configurations A and B.
- Compounding would show as the harvest itself growing: the teacher at 10^5 with the cycle-k
  vocabulary verifying more learning tasks, in more families, than at cycle 0.
- Controls: generation-0 machinery at 10^4 (deployment at equal budget) and at the loop's
  cumulative budget per real task.

## Predictions
| ID | Prediction | Expected |
| --- | --- | --- |
| E1 | The harvest grows: the teacher's verified learning tasks at 10^5 end at least 4 above cycle 0 in configuration A (84 at cycle 0) | PASS (low) |
| E2 | Families with a verified learning solve at 10^4 rise by at least 3 in configuration A (the first loop: 0) | PASS (low) |
| E3 | The student at 10^4 does not fall below generation 0 on held-out in either configuration, and ends at least 3 above in one | PASS (low) |
| E4 | At least 3 cycles accept a symbol in configuration B | PASS (low) |
| E5 | The two-family screen rejects the `slice-k-n` symbols that carried the first loop in configuration A, and the raw learning count at 10^4 ends below the first loop's 97 | PASS (moderate) |
| E6 | Generation-0 machinery at the cumulative budget solves at least as many held-out tasks as the student at 10^4 in both configurations | PASS (moderate) |
| V4 | The harvest stops growing within 3 cycles: distillation amortises search, it does not compound | moderate |

# Addendum 4: deployment frontier of the second loop's best state (diagnostic)

Written after the second loop had finished in configuration B and its log had been read
(generation 0: learning 121, held-out 27; best state, run 20: learning 127, held-out 38,
three learned symbols, one of them `filter (lambda x. gt (mod x k) 0)`, and a cut vocabulary
of 17 and 20 symbols), while the second loop in configuration A, the control at the loop's
cumulative budget and the expert-iteration runs were still running, and before any run of
`frontier.py`. Also known: in the first loop the best state of configuration B at 10^5 solved
35 held-out tasks against 28 for generation-0 machinery without R at 10^5.

R3 compares the loop after training with generation 0 at the loop's cumulative budget. That
comparison is fixed and stays as registered. This diagnostic asks a different question and
decides nothing: at an equal budget per task at deployment, does the learned vocabulary stay
ahead as the budget grows, or does it only find the same programs earlier?

## Set-up (fixed now)
- Held-out partitions of configuration B only (FRESH-2 and COMPOSE-24, 124 tasks).
- Three vocabularies, machinery S + C + f + R in all: generation 0 (no learned symbol, full
  vocabulary); the best state of the second loop (its three symbols and its kept sets); the
  three symbols with the full vocabulary.
- Budgets per task: 10^5 and 251,479 (the second loop's cumulative budget per real task).
  10^4 is already measured: 27, 38, and 34 for the symbols with the full vocabulary.

## Predictions
| ID | Prediction | Expected |
| --- | --- | --- |
| F1 | At 10^5 the best state solves at least 3 more held-out tasks than generation 0 at 10^5 | PASS (moderate) |
| F2 | At 10^5 the symbols with the full vocabulary solve at least as many held-out tasks as the best state with its cut | PASS (low) |
| F3 | The best state's lead over generation 0 is smaller at 251,479 than at 10^4 (11): budget closes part of the gap | PASS (moderate) |
| F4 | At 251,479 one of the two learned vocabularies is still at least 3 held-out tasks ahead of generation 0 | PASS (low) |

My reading, fixed in advance: a lead of at least 3 at all three budgets (F1 and F4) means the
learned symbols moved the frontier of what is reached, not only the order in which programs
are found. It would still be one step of learning, not a compounding one.

# Addendum 5: ablations of the expert-iteration vocabulary (diagnostic, post hoc)

Written after expert iteration had finished in both configurations and its logs had been
read (configuration B: five cycles accepted, student at 10^4 learning 121 to 147 and
held-out 20 to 26 verified, 15 symbols of which three are defined on cycle-1 symbols;
teacher at 10^5: 134, 151, 155, 150, 150, 150, 150), and before any run of
`expert_ablate.py`. The frontier runs of Addendum 4 were not complete.

R2 asks whether a gain of a later generation depends on a symbol of an earlier one, and
names ablation as the test. These runs are that test for the expert loop. They decide
nothing else.

## Runs (fixed now), configuration B's final vocabulary, machinery S + C + f
- all: the 15 symbols at 10^4 on every task. It must reproduce 147 and 26.
- no-depth-2: without `c4_2`, `c4_3`, `c5_1` (the symbols defined on `c1_1` and `c1_2`).
- no-cycle-1: without `c1_1`, `c1_2`, `c1_3` and without the three symbols defined on them.
- at-10^5: the 15 symbols at 10^5 on the held-out partitions (generation 0 without R at
  10^5: 28 verified).

## Reading fixed in advance
R2 holds for this loop if no-depth-2 loses at least 2 verified solves (learning plus
held-out) against all: a later gain then rests on symbols built on earlier symbols.

## Predictions
| ID | Prediction | Expected |
| --- | --- | --- |
| G1 | no-depth-2 loses at most 3 verified solves in total: the depth-2 symbols are shorthand, not new reach | PASS (moderate) |
| G2 | no-cycle-1 loses at least 10 learning solves: the first cycle carries most of the gain | PASS (moderate) |
| G3 | at 10^5 the 15 symbols solve at least 3 more held-out tasks than generation 0 at 10^5 (28) | PASS (low) |

## Addendum 5b: the expert vocabulary with representation search (one more run)

Added after the first ablation run of Addendum 5 had returned (all: 147 and 26, as recorded)
and while the other two were running; before any run of the combination below.

Expert iteration ran without R. Its final vocabulary holds `c2_2 = filter (lambda x. gt (mod
x k) 0)`, the symbol that representation search used as a pre-image in the second loop. One
run: the 15 symbols with machinery S + C + f + R at 10^4 on every task, and the same with no
symbol dropped at 10^5 on the held-out partitions.

| ID | Prediction | Expected |
| --- | --- | --- |
| G4 | With R the expert vocabulary solves at least 6 COMPOSE-24 tasks at 10^4 (0 without R) | PASS (moderate) |
| G5 | With R it solves at least as many held-out tasks at 10^4 as the second loop's best state (38 verified) | PASS (low) |
