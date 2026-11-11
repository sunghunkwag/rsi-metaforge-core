# Shift loop: exploratory tests of a search that modifies its own vocabulary

**Status: exploratory, report-only, not part of the rsi5 package and not a registered
result.** Requested by the Owner on 2026-11-10 after the Phase 1 gate failed. One question:
if the unchanged rsi5 engine is wrapped in a loop that modifies its own search vocabulary,
does improvement compound across generations by itself?

Everything here runs on the exposed partitions. The machinery was designed after the
FRESH-1 failures of Phase 1 had been read, so no number here is a clean test and none may
be quoted as a result of the package. A claim needs J's sealed pools.
[`PREDICTIONS.md`](PREDICTIONS.md) was written before each run it predicts.

## Answer

Not by the four criteria fixed in advance. Three loops were built and run in two
configurations each. The one positive comparison was then put to a registered replication
on 300 new tasks, and its outcome class is "not established".

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

## Predictions, misses first

Scored on verified counts, as registered. Where the sound count changes the reading it is
given in the last column. K1 and Q1 to Q10 were registered on sound counts and are scored
on them.

Eleven of 47 predictions missed, and three of the four verdicts written in advance were
wrong in part. The outcome class expected for the replication ("replicated on FRESH-3, for
the divisibility family only") was wrong too: the class is "not established".

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

No loop meets all four. Counting criteria met does not rank the loops: the first loop in A
meets R1 on verified counts while its held-out solves end five below where they started.

R3 as registered fails for every loop, and it is what the Phase 1 result already pointed
at: on a fixed set of tasks, budget is a strong baseline. At a deployment budget of 10^5
the picture is closer. On the 124 held-out tasks the trained state has 44 sound solves
and generation 0 has 38 over the four budgets of the registered union, 39 over the seven
budgets it has been run at, up to 1.1 million candidates per task. On 300 new
tasks it has 71 against 64. Neither difference is separated from chance by the registered
test, and both are confined to tasks that contain a routine the learned symbols encode.

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
   everything generation 0 solves at any budget. Criterion: the registered sign test on
   FRESH-3 passes. Measured: 71 against 64, p = 0.13.
7. **Breadth.** Target: the lead reaches tasks whose routines are not the ones the symbols
   encode. Criterion: a lead on the tasks without those routines. Measured: 42 against 42
   on the 196 tasks without a divisibility stage; 62 against 63 without `slice-k-n`.
8. **New routines.** Target: transfer to routines and parameters the loop has not met.
   Criterion: a registered test on such tasks. Measured: not tested. FRESH-3 re-pairs the
   stage instances of FRESH-1 and FRESH-2.
9. **Independent review of every part.** Target: each file attacked by someone who did not
   write it. Criterion: a reviewed finding list per file. Measured: `hybrid.py` and
   `loop.py` reviewed; `compress.py` (written by a sub-agent) is covered by round-trip
   tests on real programs and by the review's 24,000 inlining checks, not by its own
   review; `replicate.py` and `fresh3.py` were reviewed as a draft before the run and
   their results recounted after it; `dream.py`, `expert.py`, `oracles.py`,
   `audit_all.py`, the ablation and frontier tools and the fixes made after the first
   review were reviewed in the sixth review; `deepen.py`, `confirm.py` and `fresh4.py` as
   drafts before the run of Addendum 8.

## Files and how to run

`hybrid.py` (harness), `loop.py`, `compress.py`, `dream.py`, `expert.py`, `frontier.py`,
`state_run.py` (re-run one state), `expert_ablate.py`, `expert_dependence.py`,
`replicate.py` (the registered replication) and `fresh3.py` (its new tasks),
`oracles.py` and `audit_all.py` (the audit), `summarise.py` (tables), `checks.py`
(self-checks), `audit_hybrid.py` and `map_shift.py` (first audit and first pilot,
superseded). `results/` holds every report and log, and `harness_review.json` the
review's findings with their evidence.

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
```

Standard library and NumPy only. No transformer or attention layer. No learned controller.
Attribution: Intelligence Research Project.
