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

# Addendum 6: the control at the full cumulative budget for the combined state

Written after the runs of Addenda 4, 5 and 5b had been read: the expert vocabulary with
representation search solves 55 held-out tasks at 10^5 (FRESH-2 45, COMPOSE-24 10; 44 sound),
generation 0 with R solves 45 at 10^5, 46 at 181,775 and 50 at 251,479 (35, not audited, and
37 sound). Before any run at the budget below.

R3 as registered compares the loop's state at its own budget of 10^4 with generation 0 at the
loop's cumulative budget. There it fails: 38 verified and 33 sound against 50 and 37 at
251,479 already. This addendum asks the same question at a deployment budget of 10^5, and
charges the trained state everything it cost: 533,195 candidates per task for expert
iteration in configuration B, plus the 10^5 run on the 124 held-out tasks (36,686 per task
over 338 tasks), 569,881 in all.

One run: generation 0, machinery S + C + f + R, no learned symbol, at 569,881 candidates per
task on the held-out partitions of configuration B.

| ID | Prediction | Expected |
| --- | --- | --- |
| K1 | Generation 0 at 569,881 solves fewer sound held-out tasks than the combined state at 10^5 (44) | PASS (moderate) |
| K2 | Generation 0 at 569,881 solves at most as many verified held-out tasks as the combined state at 10^5 (55) | PASS (low) |

Reading fixed in advance: if K1 holds, the trained state at 10^5 beats untrained machinery
that is given the whole training and deployment budget, on these 124 exposed tasks. That is
R3 at a 10^5 deployment budget for one configuration, built by adding R to the expert
vocabulary after the fact. It is not R3 as registered, and not a clean test.

# Addendum 7: registered replication of the one positive result

Approved by the Owner on 2026-11-10 ("expert iteration with representation search from
generation 0, predictions and control fixed before the run"). Written after every result
above had been read. A draft (commit 20b6fb1) was attacked by four independent reviewers
before anything ran at a real budget: confounds and leakage, fairness of the control,
statistics and claims, implementation. They returned 19 findings. This text is the draft as
changed by them; what each changed is listed at the end. Nothing below has been run at a real
budget, and no solver has run on the registered evaluation set at any budget.

## The claim under test

A vocabulary learned by expert iteration lets the same machinery solve more held-out
composition tasks at 10^5 candidates per task than generation 0 solves under a budget
ceiling equal to the whole training and deployment budget.

The one measurement behind it (Addendum 6): 44 sound held-out solves against 37, for a state
built by switching R on after the loop had run without it, on the 124 tasks the combination
was chosen on. What the reviewers found in it, each point checked again by the author:

- Eleven tasks only the trained state solves, four only generation 0: a one-sided sign test
  gives p = 0.059. Against everything generation 0 solves at any of the five budgets it was
  run at (39 sound), nine against four: p = 0.13.
- The lead is one routine family. In the 30 FRESH-2 tasks with a divisibility routine in a
  stage it is eight against one. In the other 70 it is three against three. COMPOSE-24 has no
  task that only one arm solves.
- On five of the eleven, generation 0 had not run out of budget: it had stopped at a wrong
  first match (a verified program that is not sound) after 4% to 50% of its ceiling.

That is not evidence yet, and where it points is narrow.

## Mechanism (frozen)

`replicate.py`, one process, deterministic, no step between loop and evaluation decided by a
person:

1. Expert iteration exactly as in Addendum 3 (student 10^4, teacher 10^5, at most three
   symbols per cycle, a symbol needs two families, the gate is the family-normalised verified
   score on the learning partitions, one retry, at most 6 cycles), with one change: the
   machinery is S + C + f + R for student and teacher. Configuration B. The harness as fixed
   after the review.
2. Generation 0 (same machinery, no learned symbol) and the final vocabulary at 10^4 and at
   10^5 on the evaluation sets.
3. Generation 0 at the cumulative budget ceilings. T = student runs x 338 x 10^4 + teacher
   runs x 214 x 10^5: every run of the loop is charged at its ceiling, rejected vocabularies
   included. For an evaluation set of N tasks, D = N x 10^5.
   - C2 = (T + D) / N: the whole training and deployment budget on the evaluated tasks alone.
     Run on both sets.
   - C1 = (T + D) / 338: every task of the study gets the same share, the accounting of R3
     and of Addendum 6. Under it the control spends 37% of what the trained state is charged.
     Run on held-out B, for comparison with Addendum 6.
   - On FRESH-3 one more rung, mid = sqrt(10^5 x C2).
   - "Any budget": the union of everything generation 0 solves on a set at every budget run
     there (FRESH-3: 10^4, 10^5, mid, C2; held-out B: 10^4, 10^5, C1, C2). A larger budget
     changes the share each route gets, so generation 0 can lose at C2 a task it solves with
     less. The union gives the control more than equal cost and is the control of the
     primary comparison.
4. Secondary arm: the earlier combination itself (the 15 symbols of `results/expertB.json`
   with R) at 10^5 on FRESH-3.

Cost is counted in constructed candidates, at ceilings. Not counted for the trained arm:
compression in the driver, and the verifier's verdicts on the learning tasks in every run of
the loop, which generation 0 never receives. The report gives both (seconds, and the number
of verdicts).

The registered FRESH-3 set is checked by its digest before the loop starts. The runs at the
largest budgets come first, so a failure for lack of memory (a test on four learning tasks
at 1.7 million candidates showed 3.2 GB per worker) happens before any FRESH-3 outcome
exists. If the process dies it is restarted with `--from-loop` on the saved loop report,
with fewer workers if memory was the cause; results do not depend on the number of workers.
The report says if that happened.

## Evaluation sets

- **FRESH-3** (primary): 300 new two-stage tasks made by `fresh3.py`.
  - Stage-1 instances are the first stages of FRESH-2 tasks and the FRESH-1 routines;
    stage-2 instances are the second stages of FRESH-2 tasks. Each routine is read the one
    way that reproduces every FRESH task it occurs in.
  - Candidates are all ordered pairs whose pair of routine names is not the pair of a FRESH-2
    task (3,710 pairs), in the order of one seeded shuffle.
  - Inputs are public example inputs of FRESH-1 and FRESH-2, drawn with the frequency they
    have there, 16 distinct lists per task among those the pipeline is defined on: 8 public,
    8 hidden. If the 8 public outputs are all equal although the pipeline is not constant,
    the last public example is exchanged for one with another output.
  - A candidate is skipped if fewer than 16 inputs are usable, if it is constant, if it is
    the identity on its examples, or if it computes on its 16 inputs what some exposed
    task's reference or an earlier FRESH-3 task computes.
  - Quotas by output type in FRESH-2's proportions: 213 list, 33 integer, 54 boolean.
  - 3,113 candidates gave the 300 tasks. Digest
    `4da13e671411da8c20a341e10d528eee26e1edad78045f8de32b4fb4473ae120`.
- **Held-out B** (secondary): FRESH-2 and COMPOSE-24, 124 tasks. The combination was chosen on
  these, so this half replicates the procedure, not the result on new tasks. It is not a
  sample: p-values on it, and pooled with it, are descriptive.

What FRESH-3 is and is not.

- New pairings of (routine, parameter) instances already used in FRESH-1 and FRESH-2. No
  routine is new and no parameter value is new.
- 104 of its 300 tasks have a divisibility routine in a stage (30 of 100 in FRESH-2). This
  family is fixed now, by names only: `modulo-k`, `is-mod-k`, `keep-mod-k`, `remove-mod-k`,
  `identify-is-mod-k`, `is-evens`, `is-odds`.
- Its inputs differ from FRESH-2's: an empty public input in 96 of 300 tasks (52 of 100), a
  negative public value in 41 (4), median longest public input 9 (7). It has 8 hidden
  examples per task where FRESH-2 has 1 or 2.
- Its generator was written by the author after the results above were known.
- What has run on it: nothing. An earlier draft set (another seed and rule, digest
  `333e3506...`) was run at toy budgets by the author (its first 100 tasks; generation 0
  solved 2, 13 and 18 of them at 300, 1,500 and 9,948 candidates) and by the review (all
  300, at up to 4,316 candidates; the author has not read those counts). That set is
  discarded. Smoke tests of the present code use a separate seed.

## Outcome measure

Sound solves: the verified program agrees with the reference on 200 fresh inputs in the
task's own input range (`audit_all.py`; for FRESH-3 the reference is the generating
function, and inputs whose reference output lies beyond the generator's caps are skipped).
Verified counts are reported beside them.

A run stops at its first public match. If that program is wrong the task is lost for that
run in both arms and the rest of the budget is not spent: a budget is a ceiling. For every
task only one arm solves soundly, the report states what the other arm did on it: (a) no
public match within its budget, (b) a public match the verifier rejected, (c) a verified
program that is not sound. For generation 0 this is read at C2.

## Primary outcome and how it is read (fixed now)

Primary comparison: on FRESH-3, the trained state at 10^5 against generation 0 at any
budget, sound solves, exact one-sided sign test on the tasks only one arm solves, alpha
0.05. The 300 tasks are a seeded draw from the 3,710 candidate pairs, so the test is valid
for that population of pairs, for the one vocabulary this run produces.

| Outcome | Reading |
| --- | --- |
| A registered run is missing, or the set is not the registered one | No class. The report says what is missing. |
| The loop accepts no symbol | Not replicated: the trained state is generation 0. |
| Trained has no more sound solves than the control | Not replicated on FRESH-3. If the trained state leads generation 0 at any budget on held-out B, the earlier lead is read as specific to the tasks it was chosen on. If it does not, the loop with R from generation 0 did not rebuild the combined state and the run says nothing about the earlier lead. |
| More, with p >= 0.05 | Not established. The size of the lead is reported; no claim. |
| More, with p < 0.05 | Replicated on FRESH-3 against everything generation 0 solves at any budget run, with the four endings below. |

Endings of a "replicated" outcome, each decided mechanically:

1. Family: the same comparison on the 196 tasks without a divisibility stage. "For the
   divisibility family only" if the trained state has no more sound solves than the control
   there; "outside the divisibility family not separated from chance" if it has more with
   p >= 0.05; "beyond the divisibility family" if p < 0.05 there.
2. Budget: "with reach beyond the budget" if the trained-only tasks of kind (a) outnumber
   the control-only tasks of kind (a); otherwise "as a different first match, not reach
   beyond the budget". The words "with the entire budget" are used for kind (a) only.
3. Output type: "for list outputs only" if the control has more sound solves on the 87
   integer and boolean tasks.
4. Held-out B: "and on held-out B" if the trained state has more sound solves there than
   generation 0 at any budget; otherwise "not on held-out B".

"More" means strictly more. The class is decided on sound counts; the same rule on verified
counts is printed beside it and a difference is stated.

Secondary, reported without deciding anything: every comparison against the single runs
(equal budgets, mid, C1, C2), on held-out B and pooled (C2 on both sets; any budget on both
sets); the primary test without each routine in turn, with the largest of those p-values
and its routine; the trained-only tasks by the learned symbols their programs use; the sign
test over routine clusters (first-stage routine, second-stage routine, the divisibility
family as one cluster), where the larger p-value is the one quoted; a stricter reading of
sound on FRESH-3 (agreement with the generating function on every usable input of the
pool); the earlier combination on FRESH-3. If the task-level test passes and the larger
cluster p-value is 0.05 or more, the report says that the lead holds over pairs and not
over routines, names the routines with a positive net, and claims nothing for the others.

What a positive outcome would license: for the one vocabulary this run produced, on the
pairs `fresh3.py` draws from, at 10^5 candidates per task, the trained state has more sound
solves than generation 0 has at any budget run, cost counted in constructed candidates,
with the four endings as they fall. What it would not: new routines or parameters; the loop
as a procedure (one run, one vocabulary); cost in time; J's sealed pools; the loop's own
budget of 10^4; recursive self-improvement by R1 to R4 (R3 as registered compares at 10^4).

## Predictions

| ID | Prediction | Expected |
| --- | --- | --- |
| Q1 | At least 3 cycles accept a symbol and the final student has at least 138 verified learning solves at 10^4 (121 at generation 0) | PASS (moderate) |
| Q2 | Held-out B at 10^4: the final student has at least 28 sound solves (generation 0: 22; the combination: 33) | PASS (moderate) |
| Q3 | Held-out B at 10^5: the trained state has at least 40 sound solves (generation 0: 35; the combination: 44) | PASS (low) |
| Q4 | Held-out B: trained at 10^5 has more sound solves than generation 0 at C1 | PASS (moderate) |
| Q5 | Held-out B: trained at 10^5 has more sound solves than generation 0 at any budget | PASS (low) |
| Q6 | FRESH-3 at equal budgets: the trained state leads generation 0 by at least 6 sound solves at 10^4 and at 10^5 | PASS (moderate) |
| Q7 | FRESH-3, primary: trained at 10^5 has more sound solves than generation 0 at any budget | PASS (moderate) |
| Q8 | FRESH-3, primary: the sign test gives p < 0.05 (scored only if Q7 passes) | PASS (low) |
| Q9 | FRESH-3 without the divisibility family: trained has more sound solves than the control | FAIL (moderate) |
| Q10 | FRESH-3: the trained-only tasks on which generation 0 found no public match outnumber the control-only tasks of that kind | PASS (low) |

Expected outcome class, not counted as a prediction: replicated on FRESH-3, for the
divisibility family only.

## What the review changed

- Task mix: quotas by output type (the draft set had 283 list, 8 integer, 9 boolean tasks,
  which favoured the trained arm: S and R act on list outputs only); inputs drawn with their
  FRESH frequency; a constant draw repaired instead of rejected.
- Independence: pairs that repeat a FRESH-2 routine pair are excluded (50 of the draft's
  300 did); the registered set comes from a new seed and has been run by nothing.
- Control: the union over budgets is the primary control, with one more rung on FRESH-3;
  held-out B is compared with the union too, not with C1 alone.
- Readings: the family ending, the budget ending, the output-type ending; a failure on
  FRESH-3 is not attributed to the tasks unless held-out B replicates; "no class" cases;
  the class on verified counts beside the class on sound counts.
- Statistics: the cluster tests decide nothing (they measure neither validity nor breadth
  well; a power simulation by the reviewer showed a family-only effect passing both in 74%
  of draws); leave-one-routine-out and the family ending carry breadth instead.
- Wording: no new parameters; one run, one vocabulary; candidates, not time; what the
  trained arm uses outside its budget.
- Code: the digest is checked before the run; the largest runs come first; smoke tests
  cannot touch the registered set; every prediction is scored by the script.

# Addendum 8: a deepening loop, tested on new tasks (DRAFT, not in force)

Written 2026-11-11, after Addendum 7 had been scored (outcome class "not established").
The Owner's instruction after that result was to continue until the criteria are met. This
registration was not put to the Owner before the run; it is the author's, fixed before
anything ran on the evaluation set. This text is a draft: it comes into force when the
design review at the end has been acted on and the commit says so. Nothing below has been
run on FRESH-4, and no solver has run on a FRESH-4 task at any budget.

## What Addendum 7 left open, and what development changed

Read off the replication's own records (learning set only):

- The loop never solved 60 of its 214 learning tasks, and 17 routine families not once
  (`append-k`, `rotate-k`, `has-k` but for one task, `reverse`, `sum`, `product`, ...).
  Generation 0 solves eight of the 60 at about 200,000 candidates; the teacher stopped at
  100,000 and spent most of that on tasks the student already solved.
- A routine that is solved once has no reuse inside the learning set, so compression never
  proposed it, and the two-family screen removed routine symbols that it did propose.
- On FRESH-3 the lead sat in the routines the nine symbols encode. Routines the loop had
  not solved alone were not solved in compositions by either arm (`append-k`: 1 of 31 tasks
  for the trained state, 2 for generation 0; `has-k`, `rotate-k`, `reverse`: none).

`deepen.py` changes four things (its docstring states them): the teacher's budget goes to
the learning tasks the student does not solve; compression counts reuse on dream
compositions of the loop's own verified programs, half of them built around the teacher's
solutions the student cannot find; symbols are tried one at a time, those a teacher's
solution uses first; real verdicts decide before dream solves.

Development ran the loop in configuration B, twice. Its decisions read learning tasks
only. The author read held-out B and FRESH-3 after each run and chose between two variants
on them, so both are development sets now and nothing measured on them is evidence:

| | First variant (three symbols per trial, in order of gain) | Second variant, the one frozen here (one symbol per trial, targets first) |
| --- | --- | --- |
| Student at 10^4 on the 214 learning tasks, generation 0 to last | 121 to 150 | 121 to 177 after two cycles (still running at the time of this draft) |
| Held-out B at 10^4 by cycle, verified | 27, 37, 42 | 27, 45, 50 (running) |
| Symbols | 15 | 19 after two cycles (running) |
| Training ceiling | 110,739,887 | pending |
| Final state at 10^5, sound/verified: held-out B; FRESH-3 | 52/65; 101/115 | pending |
| Final state at 10^4, sound/verified: held-out B; FRESH-3 | 33/42; 67/81 | pending |

For comparison, from Addendum 7: the old state at 10^5 has 44/55 on held-out B and 71/86 on
FRESH-3; generation 0 at any budget has 38 and 64 sound solves. A recursive link showed in
both variants: `reverse` became a symbol in the first cycle, and in the second cycle the
teacher solved the `append-k` tasks with it (`reverse (cons k (reverse xs))`), which became
a symbol defined through the first.

## The claim under test

The vocabulary the deepening loop builds lets the same machinery solve more new two-stage
tasks at 10^5 candidates per task than generation 0 solves at any budget up to the whole
training and deployment budget.

## Mechanism (frozen)

`confirm.py`, one process, deterministic, no step between its parts decided by a person:

1. `deepen.run`, configuration B, machinery S + C + f + R, constants as in `deepen.py` at
   the registered commit: student 10^4; a teacher run has a ceiling of 214 x 10^5
   candidates, spent in equal shares of at most 10^6 on the learning tasks the student does
   not solve; 100 gate dreams and 300 corpus dreams per cycle, up to 150 of the 300 around
   the targets; at most 24 trials per cycle; the second phase of a cycle ends after 3
   rejections in a row; at most 12 cycles; the loop stops after a cycle that accepts
   nothing. Its final vocabulary is the state called *new*.
2. *old*: the final vocabulary of the Addendum 7 loop, from `results/replication.json`.
   Generation 0: the same machinery with no learned symbol.
3. Training ceilings: T_new is the sum, over every run the deepening loop makes, of budget
   x tasks run (teacher runs, every trial, the dream runs, the held-out report runs).
   T_old = 127,280,000 (Addendum 7).
4. Evaluation on FRESH-4 (N = 1,000) at the student budget 10^4 and the deployment budget
   10^5 for *new*, *old* and generation 0. Generation 0 also at
   - C2old = (T_old + N x 10^5) / N = 227,280,
   - C2new = (T_new + N x 10^5) / N,
   - 524,267: the whole-budget rung of Addendum 7 on FRESH-3, kept so that the control is
     run at least as far as it was there.
   "Any budget": the union of everything generation 0 solves on FRESH-4 at the five
   budgets. It is the control of the primary comparison.
5. Held-out B (124 tasks, a development set): the three states at 10^4 and 10^5;
   generation 0 at 413,254 and 1,126,452 (the rungs of Addendum 7) and at
   C1new = (T_new + 124 x 10^5) / 338 if that is at most 1,700,000, the largest budget
   four workers hold in memory. FRESH-3 (a development set): *new* at 10^4 and 10^5,
   compared with the rows of Addendum 7.
6. For criterion R2, after the loop and outside it: generation 0 on each later cycle's
   unsolved learning tasks at that cycle's teacher budget; the final vocabulary without
   the first cycle's symbols and the symbols defined through them, at 10^4.

Cost is counted in constructed candidates, at ceilings. Not counted for the trained arms:
compression and dream making in the driver, and the verifier's verdicts on the learning
tasks, which generation 0 never receives. The report gives both (seconds; the number of
verdicts on learning tasks).

The registered FRESH-4 set is checked by its digest before the loop starts. The largest
runs come first. If the process dies it is restarted with `--resume`: the loop report is
kept if the loop had finished (otherwise the loop runs again from its start), and a
finished evaluation row is kept if it was made by the same vocabulary at the same budget
on the same tasks. The report says if that happened. Results do not depend on the number
of workers.

## Evaluation set

**FRESH-4** (primary): 1,000 new two-stage tasks made by `fresh4.py`.

- The candidates are FRESH-3's 3,710 pairs of stage instances (Addendum 7) without the 300
  that became FRESH-3 tasks, in the order of one shuffle under a new seed.
- Inputs, the 8 public and 8 hidden examples and the repair of an all-equal public side
  are made as for FRESH-3, with each task's own seeded generator.
- A candidate is skipped if fewer than 16 inputs are usable, if it is constant, if it is
  the identity on its examples, or if it computes on its 16 inputs what an exposed task's
  reference, a FRESH-3 task or an earlier FRESH-4 task computes.
- No quota by output type. The first 1,000 candidates that pass are FRESH-4 (1,669
  examined). The candidates after them are a reserve that nothing generates or runs.
- Digest `d54c6593098b45401c639c33e47e2abadec477849a2d9750a1f09139213a64b4`.

What FRESH-4 is and is not.

- New pairings of the stage instances of FRESH-1 and FRESH-2. No routine is new and no
  parameter value is new. No pair of stage instances is a FRESH-3 task, but the same
  routines and instances occur in both sets.
- 964 list outputs, 28 integer, 8 boolean. FRESH-3's quotas used up nearly every pipeline
  with an integer or boolean output (a check of the unused candidates found 73 and 24
  among 1,904). On FRESH-3 the trained state led on list outputs only (62 against 55; 9
  against 9 on the others), and S and R act on list outputs only. FRESH-4 therefore tests
  the claim for list outputs; it cannot show anything for integer or boolean outputs.
- 332 tasks have a divisibility routine in a stage and 73 have `slice-k-n`. These are the
  routines the old symbols encode (Addendum 7). The names are fixed now: `slice-k-n` and
  the divisibility family of Addendum 7.
- An empty public input in 367 tasks, a negative public value in 141, median longest
  public input 9.
- Its generator was written by the author after Addendum 7 and the development runs above
  had been read. FRESH-3 guided the design; FRESH-4 comes from the same population of
  pairs.
- What has run on it: nothing. The generator was run to count the set and to print its
  digest. Smoke tests use FRESH-3 tasks and generate no FRESH-4 candidate.
- The loop's dreams are pairs of its own solved routines, which is the form of these
  tasks. A dream can compute the same function as a FRESH-4 task when both stages are
  learning tasks the loop solved. The report counts the FRESH-4 tasks whose 16 examples
  some dream program of the run reproduces, and the fourth ending below reads the primary
  comparison without them.

## Outcome measure

Sound solves, as in Addendum 7: the verified program agrees with the generating function
on the fresh inputs of `oracles.fresh_inputs` (up to 200, inside the task's own range,
inputs whose reference output lies beyond the generator's caps skipped). New here: a
verdict needs at least 20 such inputs; with fewer the program is not counted as sound, in
any arm, and the report gives the number of programs this removes. Verified counts are
reported beside sound counts.

A run stops at its first public match, as before. For every task only one arm solves
soundly the report states what the other arm did: (a) no public match within its budget,
(b) a public match the verifier rejected, (c) a verified program that is not sound. For
generation 0 this is read at its largest budget.

## Primary outcome and how it is read (fixed now)

Primary comparison: on FRESH-4, *new* at 10^5 against generation 0 at any budget, sound
solves, exact one-sided sign test on the tasks only one arm solves, alpha 0.05. The test is
valid for the population of pairs FRESH-4 is drawn from, for the one vocabulary this run
produces.

| Outcome | Reading |
| --- | --- |
| A registered run is missing, or the set is not the registered one | No class. The report says what is missing. |
| The loop accepts no symbol | Not confirmed: the new state is generation 0. |
| *New* has no more sound solves than the control | Not confirmed. |
| More, with p >= 0.05 | Not established. The size of the lead is reported; no claim. |
| More, with p < 0.05 | Confirmed on FRESH-4 against everything generation 0 solves at any budget run, with the four endings below. |

Endings of a "confirmed" outcome, each decided mechanically. In each, "none" means *new*
has no more sound solves than the other arm, "not separated" means more with p >= 0.05,
and "significant" means more with p < 0.05 (the same sign test).

1. Breadth: the primary comparison on the tasks with neither `slice-k-n` nor a
   divisibility routine. "Only where a routine of the earlier symbols is present" (none);
   "outside the routines of the earlier symbols not separated from chance"; "also outside
   the routines of the earlier symbols" (significant).
2. Against the earlier loop: *new* at 10^5 against *old* at 10^5 on FRESH-4. "No more than
   the earlier loop"; "not separated from the earlier loop"; "and more than the earlier
   loop".
3. Budget: "with reach beyond the budget" if the new-only tasks of kind (a) outnumber the
   control-only tasks of kind (a); otherwise "as a different first match, not reach beyond
   the budget".
4. Dreams: the primary comparison on the tasks that no dream program of the run computes.
   "Not on the tasks no dream of the loop computed"; "on the tasks no dream of the loop
   computed not separated from chance"; "also on the tasks no dream of the loop computed".

"More" means strictly more. The class is decided on sound counts; the same rule on verified
counts is printed beside it and a difference is stated.

Secondary, reported without deciding anything: every comparison against the single runs;
*new* at 10^4 against generation 0 at any budget; *old* at 10^5 against generation 0 at any
budget and against the union up to its own C2 (the comparison of Addendum 7 again, on
these tasks); *new* against *old* at 10^4; the strata by output type; the primary test
without each routine in turn, with the largest of those p-values and its routine; solves
by routine for the three arms; the sign test over routine clusters (it decides nothing);
the new-only tasks by the learned symbols their programs use, and how many use a symbol
defined through another symbol; sound by the audit and on the whole input pool; held-out B
and FRESH-3, both development sets.

## The four criteria

Scored on held-out B at 10^4 and on the learning set, descriptive: held-out B is a
development set.

- R1: sound held-out B solves of the student rise in two cycles running.
- R2: (a) some later cycle's teacher solves a learning task that generation 0 does not
  solve at the same budget, and (b) without the first cycle's symbols and those defined
  through them, the final student loses a learning solve that was first made after the
  first cycle.
- R3: the final student at 10^4 has more sound held-out B solves than generation 0 at any
  budget run there. If C1new exceeds the memory limit, the report says that the cumulative
  budget itself was not run.
- R4: no step of `confirm.py` is decided by a person.

The same four on FRESH-4 are not defined (no cycle-by-cycle run there); the secondary
comparison of *new* at 10^4 against generation 0 at any budget is the R3 analogue on new
tasks.

## What a positive outcome would license

For the one vocabulary this run produces, on the pairs `fresh4.py` draws from (list
outputs, 96 in 100), at 10^5 candidates per task: more sound solves than generation 0 has
at any budget run, up to the larger of 524,267 and the whole training and deployment
budget, cost counted in constructed candidates, with the four endings as they fall.

What it would not: new routines or parameter values; integer and boolean outputs; the loop
as a procedure (one run, one vocabulary, one configuration, the favourable one); cost in
time; J's sealed pools; TEST; anything about systems other than this enumerator on these
list tasks.

## Predictions

Thresholds marked provisional are fixed when the registration comes into force, from the
development numbers of the frozen variant; the review is asked to treat them as open.

| ID | Prediction | Expected |
| --- | --- | --- |
| D1 | FRESH-4, primary: *new* at 10^5 has more sound solves than generation 0 at any budget | PASS (high) |
| D2 | The sign test of D1 gives p < 0.05 (scored only if D1 passes) | PASS (high) |
| D3 | *New* at 10^5 leads generation 0 at any budget by at least 80 sound solves (provisional) | PASS (moderate) |
| D4 | Breadth: on the tasks with neither `slice-k-n` nor a divisibility routine, *new* has more sound solves than the control with p < 0.05 | PASS (moderate) |
| D5 | *New* at 10^5 has more sound solves than *old* at 10^5 with p < 0.05 | PASS (high) |
| D6 | *Old* at 10^5 has more sound solves than generation 0 at any budget with p < 0.05 (the comparison of Addendum 7 on more tasks) | PASS (moderate) |
| D7 | *New* at 10^4 has more sound solves than generation 0 at any budget | PASS (low) |
| D8 | On the tasks no dream computes, *new* has more sound solves than the control with p < 0.05 | PASS (moderate) |
| D9 | The new-only tasks of kind (a) outnumber the control-only tasks of kind (a) | PASS (high) |
| D10 | R2 holds in both parts | PASS (moderate) |
| D11 | Integer and boolean outputs (36 tasks): *new* and the control are within 3 sound solves of each other | PASS (moderate) |

Known from development and therefore not predictions: the loop's own trajectory (it is
deterministic and the registered run repeats it), R1 and R3 on held-out B.

Expected outcome class, not counted as a prediction: confirmed, also outside the routines
of the earlier symbols, more than the earlier loop, with reach beyond the budget, also on
the tasks no dream computed.

## What the review changed

(to be written after the design review)
