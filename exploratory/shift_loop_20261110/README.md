# Shift loop: exploratory tests of a search that modifies its own vocabulary

**Status: exploratory, report-only, not part of the rsi5 package and not a registered
result.** Requested by the Owner on 2026-11-10 after the Phase 1 gate failed. One question:
if the unchanged rsi5 engine is wrapped in a loop that modifies its own search vocabulary,
does improvement compound across generations by itself?

Everything here runs on the exposed partitions and on tasks generated from them. The
machinery was designed after the FRESH-1 failures of Phase 1 had been read, so no number
here is a clean test and none may be quoted as a result of the package. A claim needs J's
sealed pools. [`PREDICTIONS.md`](PREDICTIONS.md) was written before each run it predicts.

## Answer

For the first three loops: no, by the four criteria fixed in advance. For the fourth, the
deepening loop: yes by the count rule the criteria were registered with, over two
generations, and two of the four hold by margins that a sign test does not separate from
chance. Then the loop stops.

The deepening loop (Addendum 8):

- It was tested by a registered run on 800 new tasks (FRESH-4), with the outcome classes
  and the predictions fixed first. The outcome class is "confirmed", for list outputs. At
  10^5 candidates per task its vocabulary has 171 sound solves on the 756 list-output
  tasks. Everything generation 0 solves at any of five budgets up to 1,126,452 is 116.
  Seventy-five tasks against 20, p = 6 x 10^-9.
- The four criteria on the same 800 tasks at 10^4: sound solves by generation are 61, 121,
  126; 14 tasks are solved only through a symbol that was built on an earlier symbol; the
  final vocabulary has 126 against 125 for generation 0 at any budget; no step is decided
  by a person. All four hold by count. The second generation's gain is 14 tasks won and 9
  lost, and the margin over generation 0 is one task. Neither is separated from chance.
- The loop built on itself once. `reverse` became a symbol in the first cycle. With it the
  second cycle's teacher solved the `append-k` tasks, which generation 0 does not solve at
  the same budget. That solution became a symbol, and the symbol solves 13 new tasks.
- It is not separated from the earlier loop's vocabulary at the same deployment budget
  (171 against 158, p = 0.094). It shows nothing where its dreams had not composed the
  pair of routines (56 against 51) and nothing on routines it never solved alone (4
  against 4). Most of its lead sits in tasks with `reverse` or `append-k`.
- The third cycle accepted no symbol. This is bounded improvement on new pairings of
  routines the loop trained on. It is not open-ended self-improvement.
- Four of its 14 predictions missed. Two were too optimistic (a lead over the earlier
  vocabulary, a lead where no dream reached). Two were too pessimistic (R3 and "all four
  criteria" were expected to fail).

The earlier loops. Three were built and run in two configurations each. The one positive
comparison was put to a registered replication on 300 new tasks, and its outcome class is
"not established".

- The gains that are real come from machinery designed by hand. At 10^4 candidates per
  task the spec shift, element-space fusion and representation search take sound held-out
  solves from 28 to 61 of 202.
- The two loops that rearrange the vocabulary saturate within one to three accepted steps.
  Generation-0 machinery given a loop's cumulative budget once solves more held-out tasks
  than that loop's state does at 10^4. This holds for every loop.
- One step of real transfer was measured, twice. In configuration B both loops learned
  `filter (lambda x. gt (mod x k) 0)` as one symbol. In the second loop representation
  search used it as a new view of the input, and sound held-out solves on the composition
  partitions went from 22 to 30 at 10^4. The net lead of its symbols closes with budget
  (6 sound solves at 10^4, 3 at 10^5, 1 at 251,479), but the solved sets stay different.
  No later symbol was accepted.
- A signal the loop can produce by itself is gamed at once. With dream tasks in the
  acceptance signal, configuration A took its dream solves from 26 to 84 while sound
  held-out solves fell from 61 to 48.
- Expert iteration with three principles taken from Terminal-RSI did nothing in
  configuration A: its two-family screen removed every useful symbol. In configuration B
  five cycles in a row were accepted. At 10^4 sound learning solves went from 119 to 143
  and sound held-out solves from 15 to 21, and eight later solves rest on first-cycle
  symbols.
- With representation search in that loop from generation 0 (the registered replication),
  sound held-out solves rose at each of three accepted cycles: 22, 23, 25, 30 at 10^4.
- On 300 new tasks the learned vocabulary helps at an equal budget: 58 sound solves
  against 45 at 10^4 (p = 0.018) and 71 against 54 at 10^5 (p = 0.002).
- Against everything generation 0 solves at any budget up to the whole training and
  deployment budget it is 71 against 64, which the registered test does not separate from
  chance (p = 0.13). The lead sits in tasks with a slice or a divisibility routine, which
  are the routines the learned symbols encode. On the 196 tasks without a divisibility
  routine it is 42 against 42.
- A review of this harness found that part of what the verifier accepts on FRESH-2 is
  wrong programs: its tasks have one or two hidden examples. Every count below is therefore
  given twice, sound/verified.

## What was built

The rsi5 engine (`rsi5/engine/bottomup.py`) is used unchanged. Around it:

| Part | File | What it does |
| --- | --- | --- |
| S, spec shift | `hybrid.py` | An element-wise or value-filter task is re-posed as an `int -> element` problem and the solution lifted back with `map` / `filter`. |
| F / f, fusion | `hybrid.py` | Two partial solutions and a separating predicate from the engine's pools are merged into one `if` term, found by bit masks over the public examples. `F` fuses everywhere, `f` in the element space only. |
| C, constants | `hybrid.py` | Integers abduced from the examples become size-1 constants. This stands in for an SMT solver, which the standard-library rule excludes. |
| R, representation search | `hybrid.py` | When S fails, a tenth of the budget enumerates list programs A over the input. Where the outputs are the element-wise image of A(xs), or A(xs) filtered by value, the task is solved as `map f (A xs)` or `filter p (A xs)`. Learned symbols enlarge the set of A. |
| L, compression | `compress.py` | Verified programs are anti-unified into named symbols by description-length gain. Symbols are inlined before a term leaves the engine. |
| A, apoptosis | `loop.py` | A move that cuts 60% of each space's symbols, least used first. A milder move cuts unused symbols only. `regrow` restores the full vocabulary and keeps the learned symbols. |
| E, entropy | `hybrid.py` | Seeded random mutation of near-miss programs on a tenth of the budget. |
| T, rollback | `loop.py` | A rejected move is banned. When no move is accepted the loop rolls back one accepted step, bans it and branches again. |
| D, dream tasks | `dream.py` | The driver composes pairs of its own verified programs into new tasks with known answers. Dream solves count in the acceptance signal. |
| Expert iteration | `expert.py` | Programs harvested at ten times the budget are distilled into symbols. A symbol needs support from two families. The gate is a family-normalised score. |

Process layout as in `rsi5/phase1.py`: workers are forked before any partition is loaded
and receive public examples only; the driver holds the frozen verifier.

Two configurations. **A** learns on TRAIN and RESERVE-NEAR (136 tasks) and holds out the
other six partitions (202). **B** learns on the six single-routine partitions (214) and
holds out the two composition partitions, FRESH-2 and COMPOSE-24 (124). B is the favourable
case: FRESH-2 tasks are pairs of the routines B learns on.

## How a solve is counted

*Verified*: the frozen verifier accepted the program on the task's public and hidden
examples. This is the registered protocol and it is what every loop decision reads.

*Sound*: the verified program also agrees with a reference function on 200 fresh inputs
(`oracles.py`, `audit_all.py`). A reference is written from the task's name and used only
if it reproduces every example of the task, public and hidden. All 338 exposed tasks have
one. The fresh inputs stay inside the task's own range of lengths and values and are spread
over the reference's outputs, so a boolean task is tested on both answers. The two audits
agree on the 60 programs that `rsi5.audit_p1` also covers.

Sound therefore means right inside the range of the task's examples, and no further. A
reviewer re-tested the 630 distinct sound programs of the result files on wider inputs:
89 fail there, most of them on `caesar-cipher` tasks whose examples lie below the modulus
(the program is right on the task's real domain). The comparisons do not move: on held-out
B none of the 10 trained-only and none of the 4 control-only programs fails; on FRESH-3
none of the 18 trained-only and one of the 11 control-only.

Counts are written sound/verified. The audit is report-only: no loop reads it. Hidden
examples per task: 1 or 2 on FRESH-1 and FRESH-2, 14 on COMPOSE-24, mostly 3 to 5 elsewhere.

## Results

Restored vocabulary, 10^4 candidates per task per run unless stated.

### Generation 0: the machinery before any learning

| Machinery | Budget | Learning A (136) | Held-out A (202) | FRESH-1 (33) | FRESH-2 (100) | COMPOSE-24 (24) |
| --- | --- | --- | --- | --- | --- | --- |
| registered engine | 10^4 | 57/57 | 28/32 | 4/4 | 11/15 | 0/0 |
| S | 10^4 | 80/80 | 44/49 | 10/10 | 12/17 | 0/0 |
| S + C | 10^4 | 80/80 | 44/48 | 10/10 | 12/16 | 0/0 |
| S + C + F | 10^4 | 80/83 | 54/69 | 17/20 | 15/27 | 0/0 |
| S + C + f | 10^4 | 80/80 | 54/61 | 17/19 | 15/20 | 0/0 |
| S + C + f + R | 10^4 | 80/80 | 61/68 | 17/19 | 19/24 | 3/3 |
| registered engine | 10^5 | 70/70 | 42/49 | 5/5 | 14/21 | 1/1 |
| S + f | 10^5 | 84/84 | 67/78 | 17/19 | 18/27 | 1/1 |
| registered engine | 2.4 x 10^5 | 92/94 | 62/73 | 9/10 | 18/28 | 2/2 |
| S + C + f | 2.4 x 10^5 | 93/95 | 74/88 | 17/19 | 22/34 | 1/1 |
| S + C + f + R | 251,479 | 93/95 | 88/103 | 17/19 | 27/40 | 10/10 |
| registered engine | 10^6 | 93/95 | 63/74 | 9/10 | 18/28 | 2/2 |

The harness with every component off reproduces the registered engine task by task
(`checks.py`). S adds 16 sound held-out solves, element-space fusion 10, representation
search 7. C adds nothing. Fusion at the whole-list level adds 8 verified held-out solves
over element-space fusion and no sound one: all 8 are coincidental.

### First loop: the four ideas (compress, apoptosis, entropy, rollback)

A move is one run of every task and is accepted only if verified learning solves rise.

| Configuration A | Learning (136) | Held-out (202) |
| --- | --- | --- |
| generation 0 | 80/80 | 54/61 |
| apoptosis | 84/84 | 50/53 |
| compress | 94/94 | 52/55 |
| compress (best state, run 5 of 24) | 97/97 | 52/56 |
| best state without its depth-2 symbol | 94/94 | 52/56 |
| best state without the two slice symbols | 80/80 | 47/51 |
| the cut alone | 84/84 | 50/53 |
| the symbols with the full vocabulary | 90/90 | 55/62 |
| best state at 10^5 | 97/97 | 53/60 |
| generation 0 (S + f) at 10^5 | 84/84 | 67/78 |
| generation 0 (S + C + f) at 2.4 x 10^5 | 93/95 | 74/88 |

| Configuration B | Learning (214) | Held-out (124) | FRESH-2 | COMPOSE-24 |
| --- | --- | --- | --- | --- |
| generation 0 | 119/121 | 15/20 | 15/20 | 0/0 |
| apoptosis | 121/123 | 16/19 | 15/18 | 1/1 |
| compress (best state, run 4 of 23) | 123/127 | 18/26 | 18/26 | 0/0 |
| the symbols with the full vocabulary | 121/123 | 19/24 | 19/24 | 0/0 |
| best state at 10^5 | 126/131 | 25/35 | 18/28 | 7/7 |
| generation 0 (S + f) at 10^5 | 132/134 | 19/28 | 18/27 | 1/1 |
| generation 0 (S + C + f) at 2.4 x 10^5 (the loop's own cumulative budget is 2.3 x 10^5) | 144/148 | 23/35 | 22/34 | 1/1 |

- All 17 learning gains of configuration A are one family, `slice-k-n`. The second
  compress step defines a symbol on a first-step symbol (`s4_1 = s3_1 (tail xs) n`) and
  carries the last three solves. Learning families with a solve stay 17 of 26; the
  family-normalised score moves from 14.23 to 15.0.
- The cut is chosen by learning-set usage and loses what other distributions need:
  sound held-out falls 54 to 50 at the cut. A random 60% cut of generation 0 gives 50
  verified learning solves.
- Entropy was never accepted. Rollback found nothing better in three branches.
- The held-out rise in configuration B, 20 to 26 verified, is 15 to 18 sound.

### Second loop: representation search, dream tasks, regrow

The acceptance signal is verified learning solves plus dream solves.

| Configuration A | Learning (136) | Held-out (202) | Dream solves |
| --- | --- | --- | --- |
| generation 0 | 80/80 | 61/68 | 26 of 40 |
| apoptosis | 84/84 | 56/61 | 30 of 40 |
| compress | 84/84 | 59/65 | 42 of 60 |
| compress | 80/80 | 56/62 | 61 of 80 |
| four more accepted steps, 15 symbols (best state, run 23 of 24) | 81/81 | 48/55 | 84 of 100 |
| generation 0 at 251,479 (the loop's own cumulative budget is 253,846) | 93/95 | 88/103 | |

| Configuration B | Learning (214) | Held-out (124) | FRESH-2 | COMPOSE-24 | Dream solves |
| --- | --- | --- | --- | --- | --- |
| generation 0 | 119/121 | 22/27 | 19/24 | 3/3 | 23 of 40 |
| apoptosis | 119/121 | 23/28 | 19/24 | 4/4 | 28 of 40 |
| compress, third branch after two rollbacks | 122/127 | 30/38 | 21/29 | 9/9 | 72 of 100 |
| unused cut (best state, run 20 of 24) | 122/127 | 30/38 | 21/29 | 9/9 | 73 of 100 |
| the symbols with the full vocabulary | 115/119 | 28/34 | 21/27 | 7/7 | 55 of 100 |
| generation 0 at 251,479 | 144/148 | 37/50 | 27/40 | 10/10 | |

- In configuration A the loop learned to solve its own dreams. Accepted steps lowered real
  learning (84 to 80) because dream solves rose more.
- In configuration B the third branch learned `s12_2 = filter (lambda x. gt (mod x k) 0)`.
  Six of the eight sound held-out gains are COMPOSE-24 tasks. Five of them, one family,
  are solved as `map (lambda x. sub x -1) (s12_2 k xs)`: representation search found the
  symbol as a pre-image and the element search finished the task.
- The first two compress branches proposed other symbols and gained 0 and 1 sound
  held-out solves. The useful symbols were reached only after the rollback had banned
  those. The first loop had learned the same filter symbol in configuration B; without
  representation search it paid only at 10^5 (COMPOSE-24 0/0 at 10^4, 7/7 at 10^5).

### Deployment frontier of the second loop's best state (configuration B)

Does the learned vocabulary stay ahead when every vocabulary gets the same larger budget?
Held-out partitions only, machinery S + C + f + R, run with the harness as fixed after the
review (the 10^4 row reproduces the loop's own numbers).

| Budget per task | Generation 0 | Best state (symbols and cut) | Symbols, full vocabulary |
| --- | --- | --- | --- |
| 10^4 | 22/27 | 30/38 | 28/34 |
| 10^5 | 35/45 | 32/42 | 38/50 |
| 181,775 | 36/46 | | |
| 251,479 | 37/50 | 33/46 | 38/51 |

The cut helps at 10^4 and costs at every larger budget. A cut state's numbers measure the
cut together with the engine's normal-form filter: the filter refuses `length nil` for the
literal `0`, and this state's cut dropped that literal from the list space, so both are
gone (a reviewer showed `cons 0 xs` not found at all in it). How many solves that costs is
not measured. The three symbols lead generation
0 by 6, 3 and 1 sound solves. The net lead closes; the solved sets do not merge. At 251,479
the symbols solve four tasks that generation 0 solves at none of the five budgets it was
run at (it spends 251,479 candidates on each without a public match), and they miss three
that generation 0 solves.

### Expert iteration (three principles from Terminal-RSI)

Machinery S + C + f, no R, no cut, no dreams. Student at 10^4, teacher at 10^5.

Configuration A: the teacher solves 84 learning tasks. Fifteen proposed symbols are
screened out because one family supports each (the `slice-k-n` symbol of the first loop
among them). The six that pass are fragments such as `mod x 5`; neither batch raises the
gate. Student 80/80 and 54/61 before and after; teacher 84 and 84.

Configuration B:

| Cycle | Student at 10^4: learning (214) | held-out (124) | family score | Teacher at 10^5 with the vocabulary before the cycle |
| --- | --- | --- | --- | --- |
| 0 | 119/121 | 15/20 | 26.58 | |
| 1 | 133/135 | 16/22 | 28.61 | 132/134 |
| 2 (second batch) | 138/142 | 17/22 | 28.87 | 149/151 |
| 3 | 140/144 | 20/25 | 29.08 | 148/155 |
| 4 | 140/144 | 21/26 | 29.22 | 144/150 |
| 5 | 143/147 | 21/26 | 29.95 | 145/150 |
| 6 | two batches rejected | | | 145/150 |

- After cycle 1 the student at 10^4 solves more learning tasks than the teacher did at
  10^5 without symbols (135 against 134).
- The harvest grew once on sound counts (132 to 149) and twice on verified counts (134,
  151, 155), then fell back to 150 as the vocabulary grew.
- One recursive link. Replaying the proposal step (`expert_dependence.py`) shows that one
  of the three cycle-2 symbols, `tail (tail (tail xs))`, is proposed only because of the
  programs the cycle-1 symbols added: seven of the ten programs it folds are slice programs
  the teacher found with the take symbol. The other two (the filter symbol and a constant)
  and the symbols of cycles 3, 4 and 5 were already waiting in the older corpus. An earlier
  version of this sentence counted the filter symbol too: the replay compared one attempt's
  batch only, and a reviewer found it.
- Ablations of the final 15 symbols at 10^4 (`expert_ablate.py`): all, 143/147 and 21/26;
  without the three depth-2 symbols, 143/147 and 22/27; without the cycle-1 symbols and
  the three built on them, 120/124 and 19/23. Cycle 1 gained 15 verified learning solves
  and lost one. Removing its symbols loses 23: those 15 and 8 that were first solved in
  later cycles, so 8 later solves rest on cycle-1 symbols. The worker's record of the
  symbols each search used shows the dependence from another side: 9 learning solutions
  combine a cycle-1 symbol or a symbol built on one with a cycle-2 symbol (`slice-k-n`
  with k = 4 or 5 as take-n of drop-3), 7 of them among the 8. The depth-2 symbols
  themselves are shorthand: dropping them loses nothing.
- The 15 symbols at 10^5 on held-out: 28/38, against 19/28 for generation 0 (S + f).
- Against generation 0 at the loop's cumulative budget (533,195 per task) the student
  loses on held-out: 21/26 against 23/35 at 2.4 x 10^5 already.

### The combination: the expert vocabulary with representation search

Expert iteration ran without R, yet its vocabulary holds the filter symbol that R used as
a pre-image in the second loop. One run each with R switched on, registered before it ran:

| State | Budget | Learning B (214) | Held-out B (124) | FRESH-2 | COMPOSE-24 |
| --- | --- | --- | --- | --- | --- |
| generation 0, S + C + f + R | 10^4 | 119/121 | 22/27 | 19/24 | 3/3 |
| second loop, best state | 10^4 | 122/127 | 30/38 | 21/29 | 9/9 |
| expert vocabulary + R | 10^4 | 143/147 | 33/38 | 25/30 | 8/8 |
| generation 0, S + C + f + R | 10^5 | | 35/45 | 25/35 | 10/10 |
| expert vocabulary + R | 10^5 | | 44/55 | 34/45 | 10/10 |
| generation 0, S + C + f + R | 251,479 | 144/148 | 37/50 | 27/40 | 10/10 |
| generation 0, S + C + f + R | 569,881 | | 37/50 | 27/40 | 10/10 |

At an equal budget per task the combined state leads generation 0 by 11 sound held-out
solves at 10^4 and by 9 at 10^5, and at 10^5 it is ahead of generation 0 at 251,479.

Generation 0 has stopped gaining: 37 sound held-out solves at 251,479 and 37 at 569,881.
That budget is the per-task share of training (533,195) plus deployment when the total is
spread over all 338 tasks. Run on the 124 held-out tasks only, it is 37% of the total. The
trained state at 10^5 has 44: eleven sound FRESH-2 solves generation 0 does not reach,
four the other way. Both predictions written before that control ran hold (K1, K2).

Read as fixed in advance: this is R3 at a deployment budget of 10^5, for one configuration,
for a state built by switching R on after the loop had run without it. It is not R3 as
registered: at the loop's own 10^4 the state has 33 against 37. It is not a clean test.

What a design review then found in it, each point checked again by the author. Eleven
against four is p = 0.059 on a sign test, and nine against four against everything
generation 0 solves at any of five budgets (39). The lead is one routine family: eight
against one in the 30 FRESH-2 tasks with a divisibility routine, three against three in
the other 70, none in COMPOSE-24. On five of the eleven, generation 0 had not run out of
budget: it had stopped at a wrong first match.

### Registered replication on new tasks (Addendum 7)

The Owner approved a replication with its predictions and controls fixed first. Four
independent reviewers attacked the draft protocol before anything ran at a real budget
(19 findings, `results/design_review_addendum7.json`); the registered protocol is the
draft as changed by them. `replicate.py` runs it in one process with no decision between
its steps: expert iteration with R from generation 0, the evaluation, the controls, the
audit, the outcome class. The first process died with its container during the
evaluation. It was restarted from the saved loop report, as the registration provides,
and the three rows it had finished came out identical.

**FRESH-3**: 300 new two-stage tasks drawn by a seeded rule from the stage instances of
FRESH-1 and FRESH-2 (`fresh3.py`): new pairings, no new routine, no new parameter value,
no pair of routine names that FRESH-2 has, no function an exposed task computes, FRESH-2's
mix of output types, 8 public and 8 hidden examples. No solver had run on its examples
before the registered run. Nine of its 300 generating functions are also in the 60-task
smoke set (another seed, other inputs), which smoke tests run at toy budgets; two of the
nine are among the 18 tasks only the trained state solves.

The loop, configuration B:

| Cycle | Student at 10^4: learning (214) | held-out B (124) | Teacher at 10^5 before the cycle |
| --- | --- | --- | --- |
| 0 | 119/121 | 22/27 | |
| 1 | 128/130 | 23/30 | 132/134 |
| 2 | 136/140 | 25/33 | 149/151 |
| 3 | 142/147 | 30/38 | 149/153 |
| 4 | two batches rejected | | 146/152 |

It kept nine symbols, among them take-n, drop-2, keep-multiples-of-k and
remove-multiples-of-k. Its training ceiling is T = 127,280,000 candidates.

Evaluation:

| State | Budget per task | Held-out B (124) | FRESH-3 (300) |
| --- | --- | --- | --- |
| generation 0 | 10^4 | 22/27 | 45/57 |
| trained | 10^4 | 30/38 | 58/72 |
| generation 0 | 10^5 | 35/45 | 54/68 |
| trained | 10^5 | 44/55 | 71/86 |
| generation 0 | 228,969 | | 55/71 |
| generation 0 | 413,254 (C1 on held-out B) | 37/50 | |
| generation 0 | 524,267 (C2 on FRESH-3: the whole budget on these tasks) | | 61/78 |
| generation 0 | 1,126,452 (C2 on held-out B) | 37/50 | |
| generation 0, everything solved at any budget above | | 38 sound | 64 sound |
| the earlier combination (15 symbols, R switched on afterwards) | 10^5 | 44/55 | 75/91 |

**Primary comparison.** FRESH-3, the trained state at 10^5 against generation 0 at any
budget: 71 sound solves against 64. Eighteen tasks only the trained state solves, eleven
only generation 0: p = 0.13. **Outcome class: not established**, on sound and on verified
counts.

Beside it, as registered, deciding nothing:

- Equal budget per task: 58 against 45 at 10^4 (23 against 10, p = 0.018) and 71 against
  54 at 10^5 (24 against 7, p = 0.0017).
- Against the single run with the whole budget on these tasks (524,267): 71 against 61
  (21 against 11, p = 0.055). Against the run at 228,969: 71 against 55 (25 against 9,
  p = 0.005).
- Tasks where the other arm ran out of budget without a public match: 13 only trained
  against 5 only control (p = 0.048). Of the other trained-only tasks, on 4 the control
  stopped at a first match the verifier rejected and on 1 at a verified program that is
  not sound; of the other control-only tasks, on 6 the trained state stopped at a rejected
  first match.
- Family: 29 against 22 on the 104 tasks with a divisibility stage; 42 against 42 on the
  other 196.
- Routines: the first-stage clusters with a net for the trained state are `slice-k-n`
  (+8), the divisibility family (+7) and `drop-k` (+1); seven routines have a net of 1 or 2
  for the control. Without the 29 tasks that contain `slice-k-n` it is 62 against 63. The
  trained-only solutions use the take symbol (8), drop-2 (7), remove-multiples (5),
  bool-to-int (5), keep-multiples (5) and a constant-map symbol (3).
- The sign test over routine clusters, of which the registration quotes the larger
  p-value: 0.95 over first-stage routines (3 clusters for the trained state, 7 for the
  control); 0.14 over second-stage routines (6 against 2).
- Output type: 62 against 55 on list outputs, 9 against 9 on integer and boolean outputs.
- Agreement on the whole input pool, the registered secondary reading: 61 against 53
  (p = 0.11). It is another test, not a stricter one: two of the trained state's programs
  and one of the control's pass it and fail the audit. Sound by the audit and on the whole
  pool: 59 against 52 (19 against 12, p = 0.14).
- Held-out B: 44 against 38 at any budget of the registered union (10 against 4,
  p = 0.09), 44 against 37 at C1 and at C2. An earlier run of generation 0 at 181,775
  solves one more task soundly: over the seven budgets generation 0 has been run at it is
  44 against 39 (9 against 4, p = 0.13). The loop with R rebuilt the earlier combination's
  count. These 124 tasks are the ones the idea was found on: descriptive.
- Pooled with held-out B, descriptive as registered: 115 against 102 at any budget (28
  against 15, p = 0.033); 115 against 98 at C2 (32 against 15, p = 0.009).
- The earlier combination on FRESH-3: 75 against 64 (20 against 9, p = 0.03). One of
  several secondary comparisons, uncorrected, and not against that state's whole budget:
  its loop has a training ceiling of 180,220,000 candidates, which is 700,733 per task on
  these 300, and generation 0 was run to 524,267 (75% of that).
- Outside its budget the loop read 2,354 verifier verdicts on learning tasks and spent 4
  seconds in compression (3,098 verdicts were issued; the 744 on held-out tasks are
  recorded and not read). The evaluation runs spent 56% to 75% of their budget ceilings.

Reading. On new pairings of routines it has met, the learned vocabulary is worth much at a
fixed budget per task. Against the same machinery with the whole budget the lead is seven
sound solves in 300 and the registered test does not separate it from chance. The lead is
where the task contains a routine that a learned symbol encodes, and nowhere else. The loop
turns the routines of its learning set into symbols; it does not turn them into reach on
other routines.

What the earlier combination costs: 533,195 candidates per task of training for all 338
tasks, 1.8 x 10^8 in all. At 10^4 the trained state reaches about what generation 0 reaches at 10^5 on the
held-out compositions (33 sound against 35), a saving near 9 x 10^4 candidates per new
task. On that arithmetic the training pays for itself after about two thousand new tasks
of the same kind; this benchmark has 124. This is arithmetic on the measured numbers, not
a measured result.

### A deepening loop, tested on new pairings of routines (Addendum 8)

After the replication the Owner's instruction was to continue until the criteria are met.
This registration was the author's and was not put to the Owner before the run. The
replication's own records say where its loop stopped, on the learning set alone:

- It never solved 60 of its 214 learning tasks, and 17 routine families not once
  (`append-k`, `rotate-k`, `reverse`, `sum`, `product`, ...). Generation 0 solves eight of
  the 60 at about 200,000 candidates. The teacher stopped at 100,000 and spent most of
  that on tasks the student already solved.
- A routine solved once has no reuse inside the learning set, so compression never
  proposed it, and the two-family screen removed the routine symbols it did propose.
- On FRESH-3, routines the loop had not solved alone were not solved in compositions by
  either arm (`append-k`: 1 of 31 tasks for the trained state, 2 for generation 0).

`deepen.py` changes four things:

| Change | What it does |
| --- | --- |
| Teacher budget | A teacher run keeps its ceiling (10^5 candidates per learning task) and spends it on the learning tasks the student does not solve, in equal shares of at most 10^6. |
| Dreams as reuse | Verified programs of learning tasks are composed in pairs, balanced over routine families. Compression runs over the real programs and 300 such dream programs, half of them built around the teacher's solutions the student cannot find. A routine solved once is then proposed as a symbol. The two-family screen is gone. |
| One symbol per trial | Each proposal is tried alone, those a teacher's solution uses first, so no symbol rides on another. |
| Real verdicts first | A symbol is accepted when the family-normalised verified score on the learning tasks rises, or stays equal while the student solves more of a second sample of 100 dreams. No dream gain pays for a real loss. |

**Development.** The loop was run three times in configuration B. Its decisions read
learning tasks only. Held-out B and FRESH-3 were read after the runs and the variants were
compared on them, so both are development sets and nothing in this table is evidence.

| | First variant | Second variant | Third variant (frozen) |
| --- | --- | --- | --- |
| What differs | three symbols per trial, in order of gain | one symbol per trial, targets first | the second, with the stop rule in both phases of a cycle |
| Student at 10^4, learning (214, verified) | 121 to 150 | 121 to 177 (stopped in its third cycle) | 121 to 177 |
| Held-out B at 10^4 by cycle | 22/27, 30/37, 33/42 | 22/27, 36/45, 41/50 | 22/27, 36/45, 41/50 |
| Symbols | 15 | 19 | 19 |
| Training ceiling | 110,739,887 | 188,819,917 after two cycles | 189,239,903 |
| Final state at 10^5: held-out B; FRESH-3 | 52/65; 101/115 | 52/63; 104/119 | the same state as the second |
| Final state at 10^4: held-out B; FRESH-3 | 33/42; 67/81 | 41/50; 67/80 | the same state as the second |

The first variant lost good symbols with bad ones: a trial of three symbols was rejected
as a whole, and `sum`, `drop-3`, `add-k` went with it.

A draft of the registration was attacked by four independent reviewers before anything
ran on the evaluation set (20 findings, `results/design_review_addendum8.json`; Addendum 8
lists what each changed). The main changes: the control runs to 1,126,452 candidates per
task; the evaluation set was regenerated on routine pairs no earlier set has and without
any pipeline a solver had run on; the class is decided on list outputs; strata by
provenance and by what the loop dreamt are fixed from data; R2 is one tied chain; the four
criteria are scored on the new set itself.

**The registered run.** `confirm.py` runs the loop, the evaluation, the controls, the
audit and the outcome class in one process with no decision between its steps. It ran
once, on four workers, without a restart, on the code of the registering commit. Its loop
repeated the frozen development run: the same 19 symbols, library digest `7b8e1ef3...`,
training ceiling T = 189,239,903 candidates (103,919,484 spent).

| Cycle | Learning tasks the student does not solve | Teacher budget per such task | Tasks the teacher newly solves | Trials | Symbols accepted | Student at 10^4: learning (214, verified) | Held-out B (124) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | | | | | | 121 | 22/27 |
| 1 | 93 | 230,107 | 27 | 21 | 15 | 165 | 36/45 |
| 2 | 49 | 436,734 | 14 | 10 | 4 | 177 | 41/50 |
| 3 | 37 | 578,378 | 5 | 6 | 0 | 177 | no symbol accepted |

The first cycle's 15 symbols are routines of the learning set: a prefix of length n,
reverse, sum, product, keep the elements equal to k, remove the multiples of k, keep the
even elements, drop three, remove the second element, replace k by a constant, and five
more. The second cycle's four are each defined through a first-cycle symbol:

| Symbol of cycle 2 | Definition | Built on |
| --- | --- | --- |
| append k | `lambda k xs. reverse (cons k (reverse xs))` | reverse |
| remove the third element | `cons (head xs) (remove-second (tail xs))` | remove the second element |
| fifth power of each element | `map (lambda x. product (map (lambda _. x) (range 5))) xs` | product |
| count the head in the tail | `length (tail (keep-k (head xs) xs))` | keep the elements equal to k |

Of the 37 trials, 19 were accepted, none on the dream tie-break. Of the 18 rejected, 16
lost more learning tasks at 10^4 than they gained and one neither gained nor lost. The
last one gained three `slice-k-n` tasks and lost one task of another family, which lowers
the family-normalised score. Every symbol dilutes a search of 10^4 candidates: with eight
of the 19 accepted symbols the student lost at least one learning task it had solved, and
three of them were accepted while its number of solved learning tasks fell (the gate
counts families, not tasks). In the third cycle the teacher solved five more tasks at
578,378 candidates each, and none of the six symbols tried from them passed the gate. The
loop stops there: improvement is bounded.

**FRESH-4**: 800 new two-stage tasks (`fresh4.py`), drawn from the pairs of stage
instances that FRESH-3 was drawn from, without every pair of routine names that FRESH-2 or
FRESH-3 has and without every pipeline a solver had ever run on. No solver ran on any of
its pipelines before the registered run. 756 have a list output, 37 an integer, 7 a
boolean; the claim, the class and the endings are for the 756. Most of the set re-pairs
the loop's own learning tasks: both stage instances are learning tasks in 336 tasks, one
in 400, none in 64. No routine and no parameter value is new.

Evaluation, sound/verified. *New* is the deepening loop's final vocabulary (19 symbols),
*old* the replication's (9 symbols), generation 0 the same machinery with no learned
symbol.

| State | Budget per task | Held-out B (124) | FRESH-4 (800) | FRESH-4, list outputs (756) |
| --- | --- | --- | --- | --- |
| generation 0 | 10^4 | 22/27 | 61/68 | 56/62 |
| new | 10^4 | 41/50 | 126/135 | 117/124 |
| old | 10^4 | 30/38 | 135/142 | 129/135 |
| generation 0 | 10^5 | 35/45 | 102/112 | 95/103 |
| new | 10^5 | 52/63 | 185/203 | 171/186 |
| old | 10^5 | 44/55 | 167/177 | 158/166 |
| generation 0 | 259,100 (the old loop's whole budget on these tasks) | | 102/113 | 94/103 |
| generation 0 | 336,550 (the new loop's whole budget on these tasks) | | 113/124 | 105/114 |
| generation 0 | 596,568 | 37/50 | | |
| generation 0 | 1,126,452 | 37/50 | 117/129 | 108/118 |
| generation 0, everything solved at any budget run | | 39 sound | 125 sound | 116 sound |

On held-out B generation 0 also ran at 181,775 (36/46) and at 251,479, 413,254 and
569,881 (37/50 each); 596,568 is the new loop's training and deployment spread over the
338 exposed tasks. Generation 0 does not solve a superset as its budget grows. A run stops
at its first public match, and with a larger budget an earlier route reaches a different
one: eight FRESH-4 tasks solved soundly at a smaller budget end at 1,126,452 on a match
that is rejected (5) or not sound (3). The single runs have 61, 102, 102, 113 and 117
sound solves and their union has 125.

**Primary comparison.** On the 756 list-output tasks, *new* at 10^5 against generation 0
at any budget: 171 sound solves against 116. Seventy-five tasks only *new* solves, 20 only
generation 0: p = 6 x 10^-9. **Outcome class: confirmed, for list outputs on FRESH-4,
against everything generation 0 solves at any budget run.** The five endings, each decided
by the registered rule:

| Ending | Tasks | New against the other arm (sound) | It reads |
| --- | --- | --- | --- |
| 1 Breadth: neither `slice-k-n` nor a divisibility routine | 494 | 95 against 63 (42 against 10, p = 5 x 10^-6) | also outside the routines of the earlier symbols |
| 2 Against *old* at 10^5 | 756 | 171 against 158 (48 against 35, p = 0.094) | not separated from the earlier loop's vocabulary |
| 3 Budget: tasks on which the other arm found no public match | 756 | 72 against 15 (p = 2 x 10^-10) | with reach beyond the budget |
| 4 Dreams: no dream computes the task or composes its pair of routines | 544 | 56 against 51 (12 against 7, p = 0.18) | not separated from chance |
| 5 Learning tasks: not both stage instances are learning tasks | 448 | 97 against 78 (29 against 10, p = 0.0017) | also where a stage is not one of its learning tasks |

On verified counts the class is the same and ending 2 differs: 186 against 166 (54
against 34, p = 0.021), which reads "and more than the earlier loop's vocabulary". The
class is decided on sound counts.

More than re-pairing of trained instances: not shown. The registration names two strata
for it and both are silent. Where no stage instance is a learning task it is 6 against 7
(62 tasks). Where a stage is a routine no learning task has it is 2 against 3 (135 tasks).

Beside the class, as registered, deciding nothing:

- Where the lead sits. Of the 50 list tasks with `reverse` the new vocabulary solves 26,
  the old one and generation 0 none. Of the 82 with `append-k` it solves 23, the others
  none. Without the 129 tasks that contain one of the two it is 125 against 116 (29
  against 20, p = 0.13): 0.36 sound solves of lead per task in those 129, 0.014 in the
  other 627. Two routines that the loop turned into symbols carry most of the lead. The
  registered rule does not read this as narrowness, because the tasks left still show a
  lead. Without any single routine the primary test still passes (largest p = 0.0003,
  without `reverse`). The sign test over routine clusters: 9 first-stage clusters for
  *new* and 4 for the control (p = 0.13); 10 second-stage clusters against 1 (p = 0.006).
- What nobody solves. No arm solves a task with `dedup`, `intersperse-k`, `repeat-k`,
  `rotate-k`, `sort` or `uniq` (349 of the 756 list tasks). On the 387 list tasks with a
  routine the loop never solved alone it is 4 against 4.
- Against *old* by stratum. With a routine of the earlier symbols: 76 against 93 (9
  against 26). Without one: 95 against 65 (39 against 9, p = 8 x 10^-6). The two vocabularies
  solve different tasks: the old one keeps `slice-k-n` (21 against 8) and `keep-mod-k` (36
  against 26), the new one has `reverse` and `append-k`. Together they solve 206 of the
  756 soundly; no merged vocabulary was run.
- *Old* at 10^5 against generation 0 at any budget: 158 against 116 (51 against 9). This
  set is 94% list outputs where FRESH-3 was 71%, so it does not change the class of
  Addendum 7.
- Equal budgets, all 800 tasks: 185 against 102 at 10^5 (98 against 15) and 126 against
  61 at 10^4 (72 against 7).
- What the other arm did on the tasks one arm solves alone. Of the 75 new-only tasks,
  generation 0 found no public match within 1,126,452 candidates on 72 and stopped at a
  match the verifier rejected on 3. Of the 20 control-only tasks, *new* found no public
  match within 10^5 on 15, stopped at a rejected match on 4 and at a verified program that
  is not sound on 1.
- The 44 tasks with an integer or boolean output: 14 against 9 (8 against 3, p = 0.11).
  Standardised to FRESH-2's mix of output types the lead is 4.4 sound solves per 100 tasks.
- Sound by the audit and right on the whole input pool: 143 against 104 (59 against 20,
  p = 6 x 10^-6). No program was left out for thin evidence.
- The symbols in the 75 new-only solutions: reverse 26, append 21, prefix 15,
  remove-multiples 13, keep-evens 9, sum 8, keep-equal 6, product 5, remove-second 2,
  drop-three 1. Twenty-one use a symbol defined through another symbol.
- Dreams: the run made 1,115 dream programs over 676 pairs of routine families. A dream
  computes 45 FRESH-4 tasks and composes the pair of routine names of 220.
- Held-out B and FRESH-3, development sets: 52/63 and 104/119 at 10^5, as in development.
- Outside the budget the loop read 8,311 verifier verdicts on learning tasks and spent
  476 seconds in compression and dream making. The evaluation runs on FRESH-4 spent 75%
  to 91% of their ceilings. Cost in time is not claimed: at 10^5 the new vocabulary took
  1,192 seconds on FRESH-4 and generation 0 took 857.

**The four criteria on FRESH-4**, all 800 tasks, sound solves at 10^4. The loop never
reads FRESH-4.

| Criterion | Measured | Holds by the registered count rule |
| --- | --- | --- |
| R1: sound solves rise in two generations running | 61, 121, 126 (verified 68, 131, 135) | yes. The second step is 14 tasks gained and 9 lost (p = 0.20) |
| R2: a gain that rests on a symbol distilled from a later teacher's discovery, lost under both ablations | 14 tasks | yes |
| R3: more than generation 0 at any of the five budgets | 126 against 125 (54 against 53, p = 0.5) | yes, by one task |
| R4: no step decided by a person | | yes |

All four hold by the count rule they were registered with. It is the first loop of this
study for which they do. Two of the four hold by margins that a sign test does not
separate from chance: the second generation's gain (five tasks net) and R3 (one task).

- The chain of R2. In the second cycle the teacher, at 436,734 candidates per task,
  solved 13 learning tasks soundly with a learned symbol where generation 0 at the same
  budget finds no public match, and none the other way: nine `append-k` and
  `append-index-k` tasks through `reverse`, and `count-head-in-tail`, `remove-index-k`,
  `pow-k` and `slice-k-n`. The four symbols of that cycle were distilled from those
  programs. On FRESH-4, 14 tasks are solved at 10^4 by the final vocabulary and by neither
  generation 0 nor the first cycle's vocabulary, each with one of the four: 13 with the
  append symbol (`append-k` paired with `mult-k`, `identify-is-prime` or `keep-mod-k`) and
  one with remove-third and sum. Generation 0 solves none of the 14 at any budget.
- The ablations add nothing here. The final vocabulary without the four recursive symbols
  is the first cycle's vocabulary, and without the first cycle's symbols and everything
  defined through them it is generation 0: the rows are equal program for program. So R2
  rests on the 14 gains and their programs. The third ablation, reported beside it, removes
  the 15 first-cycle symbols and keeps the four with their definitions written out: 77
  sound solves, between generation 0 (61) and the whole vocabulary (126).
- The nine losses of the second step are tasks the first cycle's vocabulary solved within
  1,200 to 5,000 candidates and the final one does not solve within 10^4: six with
  `drop-k` (k = 5) as their first stage, two with `keep-mod-k`, one with `modulo-k`. Four
  more symbols moved them out of reach.
- R3 by output type: 117 against 116 on list outputs, 9 against 9 on the others. The old
  vocabulary at 10^4 has 135 sound solves on the same 800 tasks (45 against 35 against the
  same control, p = 0.16), more than the new one's 126.
- In the third cycle the teacher made four more such discoveries. No symbol from them
  passed the gate.
- On held-out B, a development set: R1 22, 36, 41; R2 with 5 tasks; R3 41 against 39 (13
  against 11, p = 0.42).

**Reading.** On new pairings of routines it trained on, the vocabulary this loop built
solves at 10^5 candidates per task what the same machinery without it does not solve at
eleven times that budget, and the registered test separates the two. The loop built on
itself once: `reverse`, made a symbol in the first cycle, let the second cycle's teacher
solve the `append-k` tasks, their solution became a symbol, and that symbol solves new
tasks at 10^4 that neither earlier generation solves.

What this does not show:

- That the second generation is better than the first, or that the final vocabulary at
  10^4 beats generation 0 with more budget. Both hold by count and neither is separated
  from chance.
- That the new loop is better than the earlier one. At the same deployment budget they are
  not separated, and at 10^4 the earlier loop's vocabulary solves more.
- Anything outside what the loop dreamt or trained on. Where no dream composed the pair of
  routines the lead is 56 against 51. Where a routine was never solved alone, nobody
  solves the task.
- Open-ended improvement. The third cycle accepted nothing.
- New routines or parameter values, integer and boolean outputs, the loop as a procedure
  (one run, one vocabulary, the favourable configuration), cost in time, J's sealed pools.

## Predictions, misses first

Scored on verified counts, as registered. Where the sound count changes the reading it is
given in the last column. K1, Q1 to Q10 and D1 to D14 were registered on sound counts and
are scored on them.

Fifteen of 61 predictions missed, and three of the four verdicts written in advance were
wrong in part. One more, D10, was not scored: its stratum is not testable. The outcome
class expected for the replication ("replicated on FRESH-3, for the divisibility family
only") was wrong: the class is "not established". The class expected for Addendum 8
("confirmed") was right, and two of its five expected endings were wrong: more than the
earlier loop's vocabulary, and a lead where no dream composed the pair of routines. Two
predictions of Addendum 8 missed on the pessimistic side: R3 and "all four criteria" were
expected to fail on FRESH-4 and hold by count.

| ID | Prediction | Outcome (verified) | Score | On sound counts |
| --- | --- | --- | --- | --- |
| H2 | Generation 1 raises learning by 3 and held-out by 1 | A: +4 and -8 | **miss** | held-out -4 |
| H3 | Generations 2 and later add at most 2 held-out solves | A: +3; B: +7 | **miss** | +2 and +2: holds |
| H7 | C adds 2 held-out solves at generation 0 | -1 | **miss** | 0 |
| H17 | With dreams in the signal the 60% cut is rejected at generation 0 | accepted in both configurations | **miss** | |
| H18 | The second loop makes 4 accepted steps in B | 3 on the best chain (5 acceptances over all branches) | **miss** | |
| H20 | Dream solves rise three times as much as real solves | A: +58 against -12. B: +50 against +17 | **miss in B by one** | B: +50 against +11: holds |
| E1 | Expert A: the teacher's harvest ends 4 above 84 | 84 | **miss** | |
| E2 | Expert A: 3 more families with a learning solve | 17 to 17 | **miss** | |
| F1 | At 10^5 the second loop's best state leads generation 0 by 3 | 42 against 45 | **miss** | 32 against 35 |
| F4 | At 251,479 a learned vocabulary still leads by 3 | 51 against 50 | **miss** | 38 against 37 |
| Q8 | Replication, primary: the sign test on FRESH-3 gives p < 0.05 | | **miss** | p = 0.13 (18 against 11) |
| D5 | Addendum 8, ending 2: more sound solves than the earlier loop's vocabulary at 10^5 with p < 0.05 | 186 against 166, p = 0.021 | **miss** | 171 against 158, p = 0.094 |
| D7 | Addendum 8, ending 4: a lead with p < 0.05 where no dream computed the task or composed its pair of routines | | **miss** | 56 against 51, p = 0.18 |
| D13 | Addendum 8: R3 on FRESH-4, expected to fail | | **miss**: it holds, by one task | 126 against 125, p = 0.5 |
| D14 | Addendum 8: all four criteria on FRESH-4, expected to fail | | **miss**: all four hold by count | |
| V | One-shot improvement at most, not recursive | three accepted steps in A | **partly wrong** | |
| V2 | At most two accepted steps, then saturation | three in A, two in B | **partly wrong** | |
| V3 | Second loop: more steps and a larger held-out gain than the first, not recursive | right for B; in A held-out fell by 13 | **wrong for A** | |
| H1 | Generation 0 (S + F + C) solves 10 more held-out tasks than the registered engine | 69 against 32 | hit | 54 against 28 |
| H4 | Rollback changes the best learning count by at most 1 and costs 3 runs | 97 unchanged; 19 runs | hit | |
| H5 | F adds 3 held-out solves; 30% of its FRESH-1 solves are coincidental | +21; 3 of 10 | hit | list-level fusion adds no sound solve over element-space fusion |
| H6 | The first loop does not beat generation 0 at its cumulative budget | 56 against 88 | hit | 52 against 74 |
| H8 | The 60% cut is accepted at least once | both configurations | hit | |
| H9 | An accepted cut lowers held-out in A | 61 to 53 | hit | 54 to 50 |
| H10 | Entropy is never accepted | never | hit | |
| H11 | A random cut loses 10 learning solves | 80 to 50 | hit | |
| H12 | B: held-out compositions rise by 3 | 20 to 26 | hit | 15 to 18 |
| H13 | Neither configuration beats generation 0 at the cumulative budget | A: 56 against 88; B: 26 against 35 | hit | 52 against 74; 18 against 23 |
| H14 | A depth-2 symbol is accepted and serves at most 2 held-out solutions | `s4_1`; dropping it loses no held-out solve | hit | read by ablation, not from the usage counter |
| H16 | R adds 4 held-out solves at generation 0 | 61 to 68 | hit | 54 to 61 |
| H19 | Second loop, B: held-out ends 6 above generation 0 and above 26 | 27 to 38 | hit | 22 to 30 |
| H21 | Generation 0 with R at the cumulative budget solves as many held-out tasks as the second loop | A: 103 against 55; B: 50 against 38 | hit | 88 against 48; 37 against 30 |
| E3 | The expert student never falls below generation 0 on held-out and ends 3 above in one configuration | A: 61 and 61; B: 20 to 26 | hit | B: 15 to 21 |
| E4 | Three cycles accept a symbol in B | five | hit | |
| E5 | The screen rejects the `slice-k-n` symbols in A and learning ends below 97 | rejected; 80 | hit | |
| E6 | Generation 0 at the cumulative budget solves as many held-out tasks as the student | A: 78 at 10^5 against 61; B: 35 at 2.4 x 10^5 against 26 | hit | 67 against 54; 23 against 21 |
| F2 | At 10^5 the symbols with the full vocabulary do as well as the best state with its cut | 50 against 42 | hit | 38 against 32 |
| F3 | The best state's lead is smaller at 251,479 than at 10^4 | -4 against +11 | hit | -4 against +8 |
| G1 | Without the depth-2 symbols at most 3 solves are lost | none | hit | |
| G2 | Without the cycle-1 symbols 10 learning solves are lost | 23 | hit | 23 |
| G3 | At 10^5 the 15 symbols lead generation 0 by 3 held-out solves | 38 against 28 | hit | 28 against 19 |
| G4 | With R the expert vocabulary solves 6 COMPOSE-24 tasks at 10^4 | 8 | hit | 8 |
| G5 | With R it solves as many held-out tasks as the second loop's best state | 38 against 38 | hit, at the threshold | 33 against 30 |
| V4 | The harvest stops growing within 3 cycles | A: never grew; B: 134, 151, 155, 150 | right | B: 132, 149, 148, 144 |
| K1 | Generation 0 at 569,881 solves fewer sound held-out tasks than the combined state at 10^5 (44) | 37 | hit | |
| K2 | Generation 0 at 569,881 solves at most 55 verified held-out tasks | 50 | hit | |
| Q1 | Replication: 3 cycles accept a symbol and the final student has 138 verified learning solves | 3 cycles; 147 | hit | |
| Q2 | Held-out B at 10^4: the final student has 28 sound solves | | hit | 30 |
| Q3 | Held-out B at 10^5: the trained state has 40 sound solves | | hit | 44 |
| Q4 | Held-out B: more sound solves than generation 0 at C1 | | hit | 44 against 37 |
| Q5 | Held-out B: more sound solves than generation 0 at any budget | | hit | 44 against 38 |
| Q6 | FRESH-3 at equal budgets: a lead of 6 sound solves at 10^4 and at 10^5 | | hit | 13 and 17 |
| Q7 | FRESH-3, primary: more sound solves than generation 0 at any budget | | hit | 71 against 64 |
| Q9 | FRESH-3 without the divisibility family: the trained state has more (expected to fail) | | failed, as expected | 42 against 42 |
| Q10 | FRESH-3: budget-bound trained-only tasks outnumber budget-bound control-only tasks | | hit | 13 against 5 |
| D1 | Addendum 8, primary: on FRESH-4's list outputs the new vocabulary at 10^5 has more sound solves than generation 0 at any budget | 186 against 124 | hit | 171 against 116 |
| D2 | The sign test of D1 gives p < 0.05 | | hit | p = 6 x 10^-9 (75 against 20) |
| D3 | The lead of D1 is at least 50 sound solves | | hit | 55 |
| D4 | Ending 1: a lead with p < 0.05 outside the routines of the earlier symbols | | hit | 95 against 63 |
| D6 | The earlier loop's vocabulary at 10^5 has more sound solves than generation 0 at any budget with p < 0.05 | | hit | 158 against 116 |
| D8 | Ending 5: a lead with p < 0.05 where not both stage instances are learning tasks | | hit | 97 against 78 |
| D9 | Ending 3: budget-bound new-only tasks outnumber budget-bound control-only tasks with p < 0.05 | | hit | 72 against 15 |
| D10 | On the 135 list tasks with a routine no learning task has, the new vocabulary has more sound solves | | not scored: the stratum is not testable | 2 against 3 |
| D11 | R1 on FRESH-4 | 68, 131, 135 | hit | 61, 121, 126 |
| D12 | R2 on FRESH-4 | | hit | 14 tasks |

## Verdict against the four criteria

R1 is registered on held-out solves. Predictions were scored on verified counts, so both
counts are given; they disagree for the first loop.

| Loop | R1: held-out rises in two generations running (verified; sound) | R2: a later gain rests on an earlier symbol | R3: beats generation 0 at the cumulative budget (sound) | R4: no human input |
| --- | --- | --- | --- | --- |
| First, A | yes (61, 53, 55, 56); no (54, 50, 52, 52) | yes, on the learning set: without `s4_1`, built on `s3_1`, 94 of 97 | no (52 against 74) | yes |
| First, B | no (20, 19, 26); yes (15, 16, 18) | no | no (18 against 23) | yes |
| Second, A | no; no (61 down to 48) | no | no (48 against 88) | yes |
| Second, B | yes (27, 28, 38); yes (22, 23, 30) | no: the gain comes from that step's own symbols | no (30 against 37) | yes |
| Expert, A | nothing accepted | | no | yes |
| Expert, B | yes (20, 22, 22, 25, 26); yes (15, 16, 17, 20, 21) | no by the reading fixed before the ablation (the depth-2 symbols carry nothing). Observed afterwards: 8 later learning solves are lost with the cycle-1 symbols | no (21 against 23 at 2.4 x 10^5, below its cumulative 533,195) | yes |
| Expert with R, B (the replication) | yes (27, 30, 33, 38); yes (22, 23, 25, 30) | not tested | no (30 against 37 at 413,254) | yes |
| Deepening, B (Addendum 8), scored on FRESH-4 | yes (68, 131, 135); yes (61, 121, 126) | yes, by the tied chain of Addendum 8: 14 tasks | yes, by one task (126 against 125 for generation 0 at any of five budgets up to 1,126,452) | yes |

The first seven rows are scored on held-out tasks of the exposed partitions and none meets
all four. The deepening loop is scored on FRESH-4, which it never read, and meets all four
by the count rule they were registered with. It is the only loop that does. Its margins
are small where it matters: the second generation's gain is 14 tasks won and 9 lost
(p = 0.20) and R3 holds by one task of 800 (54 against 53, p = 0.5). On held-out B, a
development set, it has 22, 36, 41 by generation and 41 against 39 for R3 (13 against 11,
p = 0.42). Its R2 is stricter than the reading the earlier loops were scored by, and
those are not re-scored. Counting criteria met does not rank the loops: the first loop in
A meets R1 on verified counts while its held-out solves end five below where they started.

R3 as registered fails for every earlier loop, and it is what the Phase 1 result already
pointed at: on a fixed set of tasks, budget is a strong baseline. At a deployment budget
of 10^5 the picture is closer. On the 124 held-out tasks the replication's state has 44
sound solves and generation 0 has 38 over the four budgets of the registered union, 39
over the seven budgets it has been run at, up to 1.1 million candidates per task. On 300
new tasks it has 71 against 64. Neither difference is separated from chance by the
registered test, and both are confined to tasks that contain a routine the learned symbols
encode. The deepening loop's vocabulary at 10^5 is separated from that baseline on
FRESH-4's list outputs (171 against 116). At its own student budget of 10^4 it is level
with it (126 against 125).

## Reviews

Six independent reviews touched this study. The first, of the loop harness, is below.
The second attacked the draft of the replication's registration before it ran: four
reviewers, 19 findings, every one acted on (`results/design_review_addendum7.json`;
Addendum 7 lists what each changed). The third was to verify this document and its tools
with five reviewers; four were cut off by a usage limit (the audit, the loop code after
its fixes, the normal-forms argument of the package, the second corrections of its guard)
and only the recount finished. It recomputed 372 table cells of this README and of
`rsi5/RESULTS_P1.md` from the stored files and found none wrong, and it found seven
statements in the prose that the data does not support. The author re-tested them; all
seven are corrected here: what the frontier shows at task level, the count of criteria
met, the wording of the 569,881 control, eight later solves (not nine), the tie-break
count, which reports record rejected matches, and two controls run at another loop's
budget.

The fourth was to verify the replication and, again, the four parts the third had not
reached. Only the reviewer of the replication finished; the other four and the skeptic who
was to re-test that reviewer's findings were cut off by the same limit. The reviewer
recomputed 207 numbers of the replication from `results/replication.json` with their own
soundness verdicts (the loop table, the budgets, the evaluation table, the primary
comparison, every secondary line, Q1 to Q10, the outcome class on both counts) and found
none wrong. They confirmed that the run followed the registration, that the restart
reproduced the finished rows, that the registered set and its digest are reproducible and
that every stored verdict can be re-derived. They found six statements to correct. The
author re-tested all six, and they are corrected above: what the earlier combination's
control covers, the held-out B union against every budget generation 0 has been run at,
the pool reading of soundness, the number of verdicts read, three registered secondary
lines that were missing (the 228,969 run, the cluster p-values, the pooled comparisons),
and what "no solver had run on it" covers.

The fifth attacked the draft of Addendum 8 before anything ran on its evaluation set: four
reviewers, 20 findings, every one acted on (`results/design_review_addendum8.json`;
Addendum 8 lists what each changed). Two of the four were stopped by a usage limit at the
first attempt and were run again on another model against the revised draft.

The sixth reached the four parts that two earlier attempts had not: the audit, the loop
code after its fixes, the normal-forms argument of the package and the second corrections
of its guard and driver. Four reviewers, each finding re-tested by a second one. Five
findings: four confirmed, one already disclosed.

- Confirmed: the dependence replay compared one attempt's batch, so the Expert B section
  named two cycle-2 symbols as depending on cycle-1 programs where it is one
  (`expert_dependence.py` is fixed, its output regenerated, the sentence corrected).
- Confirmed: under a cut vocabulary, and with abduced constants, the engine's normal-form
  filter loses programs whose replacement the vocabulary no longer holds (stated above and
  in `rsi5/engine/NORMAL_FORMS.md`; not measured).
- Confirmed, in the package: a corpus size quoted in `rsi5/RESULTS_P1.md` was not asserted
  by the test cited for it (it is now).
- Already disclosed: sound is correctness inside the examples' range (the numbers above).
- What held: the audit's table for the registered run recomputes; every reference gets 200
  fresh inputs inside its domain; the PATIENCE wrapper never fires with the full
  vocabulary; the "all" ablation reproduces the final student program for program; the
  ablation arithmetic (15, 23, 8, 9 and 7) recomputes from the files.
- Not reviewed: an undeclared route through the guard's newest code. That reviewer ran no
  attack against the hook and says the lens is unreviewed, not cleared. A second attempt
  on 2026-11-11 was stopped by the reviewing model's safety classifier before any case
  ran; the request was not re-worded. The author then tested the guard's tests instead of
  the guard (`rsi5/RESULTS_P1.md`): of 30 defects made on purpose in a scratch copy, the
  test file noticed 22, and all 30 after six tests were added. The hook itself is still
  unreviewed by anyone but the author.

### The harness review

An adversarial review returned 16 findings. The seven on semantics were re-tested by a
second agent; the other nine by the author, because the skeptic agents were cut off by a
usage limit. All hold.

Changes the reading of the results:

1. **Coincidental solves.** Verified scalar-output solves on FRESH-2 are often wrong
   programs. The first audit covered three partitions only. `audit_all.py` now covers all
   eight and every table above gives both counts.
2. **Hidden examples are queried once per run, not once per loop.** Each move puts a new
   program to the same hidden examples. In the first loop, configuration B, three of the
   six learning tasks gained at the best step had a public match rejected at generation 0,
   and one acceptance off the best chain rested on such a task alone. Configuration A had
   none. Reports written from now on record every rejected match; of the stored ones only
   the expert-iteration reports do. The loop is not changed: with one or two hidden
   examples a wrong program can still be selected.
3. **The engine stops at the first size level that adds nothing.** With a cut vocabulary
   that can be level 2. Three of the 15 second-cut rows in the recorded logs are such
   stops, not searches: runs of one second with 17 or 18 solves (second loop, run 15 in A,
   runs 19 and 22 in B). The harness now continues until six levels in a row are empty. On
   a tiny run the corrected second cut solves 78 learning tasks where the stop gave 44; it
   is rejected either way. All 15 recorded second cuts were rejected; none was re-run at
   10^4.
4. **Control accounting.** The planned control gives every task runs x 10^4 candidates,
   although no decision reads the held-out tasks. What a loop needs is less: 102,544 per
   task (first loop, A), 149,290 (first, B), 140,296 (second, A), 181,775 (second, B).
   The verdict does not depend on the choice: at 10^5, below every one of these, generation
   0 already solves more sound held-out tasks than the loop (67 against 52, 19 against 18,
   67 against 48 without R, 35 against 30), and at 181,775 it solves 36 against 30.
5. **The held-out sum is mostly FRESH-2** (100 of 202 tasks in A, 100 of 124 in B). The
   tables give the partitions.

Fixed in code: a worker forked late now refuses to search and the pool never replaces a
worker; reaching the run cap is no longer booked as a rollback (the third rollback of the
second loop in configuration A did not happen); symbol use is counted as solutions the
search built with the symbol, by one rule for learning and held-out; a learned constant is
counted and cut under one name; `registered()` refuses a budget above 10^6.

Disclosed, not changed:

- Two pairs of tasks are identical. One pair spans learning and held-out in configuration
  A. At generation 0, 11 of 61 verified held-out solves in A and 7 of 20 in B are by a
  program also verified on a learning task.
- The usage numbers stored in the recorded loop reports (`abstraction_use_*`) follow the
  old, inconsistent rules and are not quoted here.
- A learned symbol's fast path is strict where its inlined term is lazy, so a program that
  fits can be dropped. No effect was measured.
- Apoptosis breaks ties in usage by name. In the recorded loops that decides 5 of the 17
  kept list symbols and 2 element symbols in configuration A, none in the first loop of
  configuration B, and 4 list symbols in its second loop.
- A list-level fused solve is booked one to three candidates over the budget (F rows only).
- `gen0_1e4*.json` and `gen0_1e5.json` were written before identity tasks were sent to the
  direct route: 14 rows per variant show `map (lambda x. x) xs` where the current code
  gives `lambda xs. xs`. The counts are equal; the current code's row is in `gen0R_1e4.json`.

## What was taken from Terminal-RSI

Terminal-RSI (arXiv:2610.22192; repository `jyyang26/Terminal-RSI`, read at commit
`8f1e700`) trains a 27B transformer with PPO. This repository forbids transformers, so no
code was used. Three design principles were transferred to `expert.py`:

| Their mechanism | What it became here |
| --- | --- |
| Family Dense Reward: a per-family divisor, so a full solve is worth about 1 in every family | The gate is the sum over learning families of the fraction of the family verified. |
| Success-Prioritized Reward: every failure scores below every success | Only verified solves score. No partial credit enters the gate. |
| Recursive Self-Rewrite: successes of a stronger harness, screened for leakage and freshly verified, become supervision | Programs harvested at ten times the budget are compressed into symbols, and a symbol is kept only if tasks of two families support it. |

Their own note that a mean reward is "mostly a task-mix metric" was checked on the first
loop and holds here: all 17 learning gains of configuration A are one family.

## Limits

Each is written as a target property and the criterion that would show it.

1. **A clean test.** Target: the loop's effect on tasks no one has seen. Criterion: the
   same counts on J's sealed pools. Measured: exposed partitions only, with machinery
   designed after FRESH-1 had been read.
2. **A verdict that means the program is right.** Target: a verified solve computes the
   task's function. Criterion: sound equals verified. Measured: 61 of 68 verified held-out solves are sound
   at generation 0 with all machinery, 19 of 24 on FRESH-2; in the registered Phase 1 run
   at 10^6, 18 of 28 on FRESH-2.
3. **An acceptance signal that cannot be gamed.** Target: a move is accepted only if it
   helps unseen tasks. Criterion: sound held-out solves never fall at an accepted step.
   Measured: they fall at the first accepted step of both loops in configuration A, and by
   13 over the second loop.
4. **One query per task.** Target: the hidden examples of a task decide once. Criterion:
   no task counted after an earlier rejection. Measured: up to 24 queries per task per
   loop; three re-queried tasks in the best step of the first loop in B.
5. **Equal-cost comparison.** Target: a loop compared with the same machinery at the same
   total cost. Criterion: candidates and uncounted work both equal. Measured: candidates
   only. The bit-mask scan of fusion, the reference re-checks, compression and dream
   making in the driver are not counted.
6. **A lead over the whole budget on new tasks.** Target: the trained state at 10^5 beats
   everything generation 0 solves at any budget. Criterion: the registered sign test
   passes. Measured: for the replication on FRESH-3, 71 against 64, p = 0.13. For the
   deepening loop on FRESH-4's list outputs, 171 against 116, p = 6 x 10^-9: met there,
   for one vocabulary, with training charged over 800 tasks.
7. **Breadth.** Target: the lead reaches tasks whose routines are not the ones the symbols
   encode. Criterion: a lead on the tasks without those routines. Measured: for the
   replication, 42 against 42 on the 196 tasks without a divisibility stage and 62 against
   63 without `slice-k-n`. For the deepening loop, 125 against 116 (p = 0.13) without the
   tasks that contain `reverse` or `append-k`, 56 against 51 where no dream composed the
   pair of routines, 4 against 4 where a routine was never solved alone.
8. **New routines.** Target: transfer to routines and parameters the loop has not met.
   Criterion: a registered test on such tasks. Measured: not tested. FRESH-3 and FRESH-4
   re-pair the stage instances of FRESH-1 and FRESH-2. Where no stage instance of a
   FRESH-4 task is a learning task it is 6 against 7.
9. **Independent review of every part.** Target: each file attacked by someone who did not
   write it. Criterion: a reviewed finding list per file. Measured: `hybrid.py` and
   `loop.py` reviewed; `compress.py` (written by a sub-agent) is covered by round-trip
   tests on real programs and by the review's 24,000 inlining checks, not by its own
   review; `replicate.py` and `fresh3.py` were reviewed as a draft before the run and
   their results recounted after it; `dream.py`, `expert.py`, `oracles.py`,
   `audit_all.py`, the ablation and frontier tools and the fixes made after the first
   review were reviewed in the sixth review; `deepen.py`, `confirm.py` and `fresh4.py` as
   drafts before the run of Addendum 8.
10. **Criteria met beyond chance.** Target: each generation's gain and the lead over
    generation 0 at the student budget hold up under a test. Criterion: a sign test passes
    for each. Measured on FRESH-4: 14 tasks won against 9 lost in the second generation
    (p = 0.20); 126 against 125 for R3 (54 against 53, p = 0.5).
11. **More than two generations.** Target: improvement that continues. Criterion: a later
    cycle accepts a symbol and the count on new tasks rises again. Measured: the third
    cycle accepted nothing. Every added symbol costs the 10^4 search a task at its edge.
12. **The loop as a procedure.** Target: the result holds over runs, learning sets and
    configurations. Criterion: registered runs on other learning sets. Measured: one run,
    one vocabulary, configuration B, on a population of routines the mechanism was
    developed on.
13. **A lead over the earlier vocabulary.** Target: the deepening loop's vocabulary beats
    the replication's at the same deployment budget. Criterion: the registered sign test
    passes on sound counts. Measured: 171 against 158, p = 0.094; with a routine of the
    earlier symbols the earlier vocabulary leads, 93 against 76.

## Files and how to run

`hybrid.py` (harness), `loop.py`, `compress.py`, `dream.py`, `expert.py`, `frontier.py`,
`state_run.py` (re-run one state), `expert_ablate.py`, `expert_dependence.py`,
`replicate.py` (the registered replication) and `fresh3.py` (its new tasks),
`deepen.py` (the deepening loop), `confirm.py` (the registered test of Addendum 8),
`fresh4.py` (its new tasks), `addendum8_tables.py` (recomputes every comparison of
Addendum 8 from the stored rows and prints the tables), `deepen_dev_eval.py` (development
evaluation), `oracles.py` and `audit_all.py` (the audit), `summarise.py` (tables),
`checks.py` (self-checks), `audit_hybrid.py` and `map_shift.py` (first audit and first
pilot, superseded). `deepen2.py` and `deepen2_eval.py` are drafts for a next loop; nothing
reported here was produced by them. `results/` holds every report and log:
`confirm.json` and `confirm.txt` are the output and the log of the registered run of
Addendum 8, `addendum8_tables.txt` the tables made from them, `replication.json` the
replication, and `harness_review.json` the first review's findings with their evidence.

The first loop, the second loop, expert iteration and their generation-0 files were
produced before the review's fixes (the expert reports already record rejected matches;
the loop reports hold only their count); the frontier, the ablations, the 569,881 control
and the replication after the fixes. At 300 candidates the fixed
harness gives field-identical records on all 338 tasks, and it reproduces the recorded
10^4 numbers of the second loop's three states and of the expert student.

Run from the repository root:

```bash
export PYTHONPATH=$PWD:$PWD/exploratory/shift_loop_20261110 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
E=exploratory/shift_loop_20261110
python $E/checks.py
python $E/hybrid.py 10000 -,S,SCf,SCfR OUT.json 4
python $E/loop.py 10000 SCfR OUT.json B 4 --moves compress,apoptosis,unused,regrow --max-runs 24 --dreams
python $E/expert.py B OUT.json 4
python $E/expert_ablate.py $E/results/expertB.json OUT.json 10000 all+R=none --components SCfR
python $E/expert_dependence.py $E/results/expertB.json
python $E/frontier.py $E/results/loopB2_1e4.json OUT.json 10000 100000
python $E/audit_all.py loop $E/results/loopB2_1e4.json --list
python $E/confirm.py OUT.json 4            # the registered test of Addendum 8, about 7.5 hours
python $E/addendum8_tables.py $E/results/confirm.json
```

Standard library and NumPy only. No transformer or attention layer. No learned controller.
Attribution: Intelligence Research Project.
