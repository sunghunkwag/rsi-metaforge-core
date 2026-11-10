# Phase 1 results: enumeration only, original vocabulary against restored vocabulary

The registered run of [PREDICTIONS_P1.md](PREDICTIONS_P1.md) (plan [`runs/p1.json`](runs/p1.json))
completed: C1's bottom-up engine, no learning anywhere, every exposed partition, both
vocabularies, B = 10⁶ candidate evaluations per task, the solve counts at 10³–10⁵ read
off the same deterministic run. Predictions were committed in 9fa6a8b before any
registered task was run; the engine is the code of 55ac295 (one fix to two normal-form
rules, committed before the run started). The run was made on this session's machine
(Python 3.13, four worker processes), not on GitHub Actions, because this session may
push only its own branch; `.github/workflows/rsi5-runs.yml` runs the same plan on
Actions from a branch named `rsi5/run-*`. Raw files: [`results_p1/`](results_p1/)
(`<vocabulary>_<partition>.json`, one record per task with the program, the candidate
count at which it was found and the verifier's verdict; the `replay/` directory holds the
second run of FRESH-1 and RESERVE-FAR2, `replay_python311/` and `replay_sealed/` the later
replays described under Determinism). Tables are `python -m rsi5.report_p1` output;
the generalisation audit is `python -m rsi5.audit_p1`.

**After the run** the pull request was reviewed adversarially: 35 findings, every one
reproduced. No registered number changes. The sealing, the run driver, the report tool,
two tests and the documents were corrected. A second review, of those corrections, found
fourteen more defects in them, two of them ways through the rewritten guard; these were
corrected as well. The engine was left as it ran: its defects
lose programs the language has, they cannot turn a wrong program into a solve, and
repairing them changes the enumeration, so they are pinned by tests and wait for a new
registration. The list is in "Adversarial review" below.

**Headline, misses first.**

| Registered | Observed | |
| --- | --- | --- |
| P1-1 restored FRESH-1 at 10⁵ ≥ 15 of 33 | **5 of 33** | miss |
| P1-3 ≥ 2 of the five corpus-lacking FRESH-1 routines solved (restored, 10⁵) | **1** (`replace-index-k-with-n`, k = 1, as `cons 2 (tail xs)`); 2 at 10⁶ (`identify-is-prime` at 203,860) | miss at 10⁵, hit at 10⁶ |
| P1-2 original FRESH-1 at 10⁵ ≤ 10 | 6 of 33 | hit |
| P1-4 RESERVE-FAR2 ≥ 10 of 21 at 10⁵ (the registered wording names no vocabulary: both scored) | original 11, restored **15** of 21 (14 and 18 at 10⁶) | hit with either |
| P1-5 throughput ≥ 10⁴ candidates/s/core | 32,439 candidates/s on one core (`results_p1/throughput.json`) | hit |

**The §3.3 gate.** P1-1 and P1-3 both miss at the registered budget 10⁵. The directive
says: stop and report. This file is the report; §4 is not built. At 10⁶, P1-3 passes
and the picture is different (below), so the Owner's reading of the gate decides whether
Phase 2 proceeds on this engine, on a repaired one, or not at all.

**What the run shows.**

1. **Budget is first-order; the restored vocabulary is second-order and costs breadth.**
   With no learning, enumeration at 10⁶ solves 10 of 33 FRESH-1 with either vocabulary
   (HONEST, the best rsi3 arm, 7 at 64 candidates), 28 of 100 FRESH-2 (rsi3 best 13),
   63 / 72 of 100 RESERVE-NEAR (HONEST 56–57, HONEST@256 67), 14 / 18 of 21 RESERVE-FAR2
   (HONEST 5, HONEST@256 13) and 6 / 2 of 24 COMPOSE-24 (HONEST 0, HONEST@256 4). The
   restored vocabulary's pools are 1.5–4× larger per size level, so at equal budget it
   completes one level less (mean top-context size 7.3 against 8.2 on FRESH-1); it gains
   where a constant 3, 4, 5, `index` or `is_prime` shortens the program (FAR2 +4,
   NEAR +9, TRAIN +2, VALIDATION +1) and loses where the program is long and uses only
   the original symbols (COMPOSE-24 −4, three FRESH-1 and three FRESH-2 tasks). On
   FRESH-1 the two vocabularies solve different sets of ten.
2. **Closure escape is real but small.** Tasks solved with the restored vocabulary whose
   family has no solve with the original at the same budget (E, §8.1): at 10⁶, FRESH-1 1
   (`identify-is-prime`), FRESH-2 3, RESERVE-FAR 1 (`is-primes`), every other partition 0.
   Of these five, three are the named routine (`map (λx. if (is_prime x) 1 0)`,
   `is_empty (filter (λx. not (is_prime x)) xs)`, `repeat-k then identify-geq-k` as a
   constant list of ones of length 5·|xs|); two are coincidences that passed the hidden
   examples (`rotate-k then is-squares` as `is_empty (filter is_prime xs)`, `identify-geq-k
   then modulo-k` as `map (λx. div (mod 5 x) 3)`). The only escape by a restored
   *primitive* rather than a constant is `is_prime`; `unfold`, `fix1`, `zip` and the pairs
   appear in no verified program at all.
3. **Short public sets make enumeration find coincidences.** 31 public matches across the
   16 result files were rejected by the verifier on the hidden examples (7 of 100 on each
   FRESH-2 run, 3 of 100 on each NEAR run), and the protocol's single query then leaves
   the task unsolved. Among the solves the verifier *accepted*, the post-hoc audit of
   [`audit_p1.py`](audit_p1.py) (200 fresh random inputs per task against a reference
   oracle; verdicts unchanged) finds 3 of the original vocabulary's 10 FRESH-1 solves and
   1 of the restored's 10 to be coincidental (`identify-k (k=-2)` as `div (add x -1) x`,
   which is 1 at −2 and 0 on 0–16 except that it fails at 0 and gives 2 at −1), while all
   14 / 18 FAR2 and 6 / 2 COMPOSE-24 solves generalise. Counting only generalising
   programs, FRESH-1 is original 7, restored 9.
4. **The five corpus-lacking routines.** `identify-is-prime` is solved (restored, 10⁶).
   `replace-index-k-with-n` is solved only at k = 1, where it is `cons n (tail xs)`
   (both vocabularies, under 600 candidates); k = 2, 3, 5 need `index`/`zip` programs of
   size ≥ 12 symbols and are not reached. `intersperse-k`, `positions`, `uniq` and
   `rotate-k`, `append-k`, `has-k` are not reached by either vocabulary at 10⁶: their
   shortest programs in this language are 9–12 symbols (`fold`-based) and the engine
   completes size 8–9 at 10⁶.

## How the run was produced

`python -m rsi5.phase1 --plan rsi5/runs/p1.json --output rsi5/results_p1 --workers 4`,
interrupted once by a machine restart after the original vocabulary and FRESH-1 of the
restored vocabulary had finished, and resumed for the remaining seven restored
partitions with the same plan (each (vocabulary, partition) is an independent,
deterministic unit; the digests do not depend on worker count or on the interruption).
Engine: bottom-up by symbol count, observational equivalence on the public inputs plus
the 16-input probe set (`data/probe_set.json`, SHA-256 `0035a70c…`), normal-form filter,
goal-typed shapes first then round-robin within a level, lambda depth 2, 64-point child
contexts, `fix1` at the task's type with angelic recursion, size cap 20 (never reached),
step budget 2000. Budget unit: one constructed term evaluated on its context's points,
counted whether or not it was then pruned (pruned shares ran 60–75%). The first public
match is re-checked with the reference interpreter and handed once to the frozen
verifier ([`verifier.py`](verifier.py)), which checks every public and hidden example.

**Determinism.** FRESH-1 and RESERVE-FAR2 were run a second time with both vocabularies
after the main run ([`results_p1/replay/`](results_p1/replay/)); all four digests (SHA-256
over every record field except wall-clock) are identical to the main run's:
`e0c447248af39613` (FRESH-1 original), `fd51abe16b6a785d` (FRESH-1 restored),
`bdd3737767cb1a38` (FAR2 original), `d5ee7213169b6a6a` (FAR2 restored). The same two
RESERVE-FAR2 digests come out of Python 3.11
([`results_p1/replay_python311/`](results_p1/replay_python311/); the main run used 3.13,
Actions uses 3.11). The driver as corrected after the two reviews was then run on the
whole plan: all sixteen digests equal the registered ones and every record is equal
outside wall-clock ([`results_p1/replay_sealed/`](results_p1/replay_sealed/)). So the
digest does not depend on the interpreter version on RESERVE-FAR2, or on which process
holds the tasks on any partition.

**Throughput.** 32,439 candidates/s on one core (40,000 candidates of the restored
vocabulary on `rsi2/benchmark.py`'s example set, `list(range(n))` for n < 12, in 1.23 s;
Python 3.13.18, x86_64, measured on a quiet machine after the run; `tests/test_throughput.py`
asserts ≥ 10⁴). Across the run the per-task rates were 20,000–50,000/s: 3.5 × 10⁸
candidates in about 57 minutes of four-worker wall-clock, against RSI-2's 10–83/s.

## Results

Solved (verifier-accepted) per partition and vocabulary at each budget; a task solved at
B is solved at every larger budget by the same program.

| Partition | Tasks | Vocabulary | B = 10³ | B = 10⁴ | B = 10⁵ | B = 10⁶ | Public matches rejected |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FRESH-1 | 33 | original | 2 | 4 | 6 | 10 | 1 |
| FRESH-1 | 33 | restored | 1 | 4 | 5 | 10 | 1 |
| FRESH-2 | 100 | original | 11 | 17 | 21 | 28 | 7 |
| FRESH-2 | 100 | restored | 12 | 15 | 21 | 28 | 7 |
| RESERVE-NEAR | 100 | original | 22 | 36 | 49 | 63 | 3 |
| RESERVE-NEAR | 100 | restored | 21 | 40 | 51 | 72 | 3 |
| RESERVE-FAR2 | 21 | original | 5 | 9 | 11 | 14 | 0 |
| RESERVE-FAR2 | 21 | restored | 4 | 7 | 15 | 18 | 0 |
| COMPOSE-24 | 24 | original | 0 | 1 | 2 | 6 | 0 |
| COMPOSE-24 | 24 | restored | 0 | 0 | 1 | 2 | 0 |
| VALIDATION | 12 | original | 0 | 2 | 4 | 7 | 1 |
| VALIDATION | 12 | restored | 0 | 3 | 3 | 8 | 1 |
| RESERVE-FAR | 12 | original | 2 | 3 | 7 | 8 | 2 |
| RESERVE-FAR | 12 | restored | 2 | 3 | 4 | 8 | 2 |
| TRAIN | 36 | original | 8 | 13 | 18 | 21 | 1 |
| TRAIN | 36 | restored | 9 | 17 | 19 | 23 | 2 |

Against the rsi3 record (its registered arms at 64 candidates per task, seeds 11/22/33,
and the one-seed HONEST@256 diagnostic):

| Partition | rsi3 best arm @64 | HONEST@256 | enumeration, original @10⁵ / @10⁶ | enumeration, restored @10⁵ / @10⁶ |
| --- | --- | --- | --- | --- |
| FRESH-1 | 7 (HONEST) | — | 6 / 10 | 5 / 10 |
| FRESH-2 | 13 (BEH, BASE) | — | 21 / 28 | 21 / 28 |
| RESERVE-NEAR | 56–57 (HONEST) | 67 | 49 / 63 | 51 / 72 |
| RESERVE-FAR2 | 5 (HONEST, PORTFOLIO) | 13 | 11 / 14 | 15 / 18 |
| COMPOSE-24 | 0 | 4 | 2 / 6 | 1 / 2 |
| TRAIN | 29 (learned, 16 generations) | 31 | 18 / 21 | 19 / 23 |

The directive's Phase-2 prediction P2-4 ("the budget-only control at B = 10⁵ already
exceeds every rsi3 number") would miss on FRESH-1 (6 vs 7), RESERVE-NEAR (49–51 vs 57)
and TRAIN (18–19 vs 29) and hit on FRESH-2, FAR2 and COMPOSE-24; at 10⁶ it misses only
TRAIN, where the rsi3 arms had 16 generations of library learning on those 36 tasks.

### Closure escape

E = tasks solved with the restored vocabulary whose family has zero solves with the
original vocabulary at the same budget; "lost" = tasks the original vocabulary solves at
that budget and the restored does not (the breadth cost).

| Partition | E @10⁵ | E @10⁶ | Escaping tasks @10⁶ (program) | Lost by restored @10⁶ |
| --- | --- | --- | --- | --- |
| FRESH-1 | 0 | 1 | `identify-is-prime`: `map (λx. if (is_prime x) 1 0) xs` | 3: `identify-geq-k (3)`, `identify-k (1)`, `identify-k (3)` (two of the three coincidental, see the audit) |
| FRESH-2 | 3 | 3 | `identify-geq-k (7) then modulo-k (…)`: `map (λx. div (mod 5 x) 3) xs` (coincidental); `repeat-k (5) then identify-geq-k (…)`: `map (λx. 1) (range (mul 5 (length xs)))`; `rotate-k (10) then is-squares`: `is_empty (filter is_prime xs)` (coincidental) | 3 |
| RESERVE-NEAR | 0 | 0 | — | 0 |
| RESERVE-FAR2 | 0 | 0 | — | 0 |
| COMPOSE-24 | 0 | 0 | — | 4: `trim-and-increment` p3, p4; `reverse-dropped-suffix` p1, p2 |
| VALIDATION | 1 | 0 | (`add-k (5)` escapes at 10⁵ only; the original finds it later) | 0 |
| RESERVE-FAR | 1 | 1 | `is-primes`: `is_empty (filter (λx. not (is_prime x)) xs)` | 1: `count-head-in-tail` |
| TRAIN | 1 | 0 | (`index-head` as `index (head xs) xs` escapes at 10⁵ only) | 0 |

Restored symbols in verified programs at 10⁶: constants 3–5 in 68 programs, `index` in
25, `is_prime` in 6, `is_square` in 2; `unfold`, `fix1`, `zip`, `pair`, `fst`, `snd` in
none.

### FRESH-1, task by task (B = 10⁶; "—" = not found; candidates to the verified solution)

| Task | original | restored | Program (restored, else original) |
| --- | --- | --- | --- |
| `add-k (k=-2)` | 1,799 | 7,615 | `map (λx. sub x 2) xs` |
| `add-k (k=10)` | — | 199,569 | `map (λx. add x (mul 2 5)) xs` |
| `append-k (k=-2)`, `append-k (k=10)` | — | — | |
| `has-k (k=10)` | — | — | |
| `identify-geq-k (k=3)` | 142,578 | — | `map (λx. if (gt x 1) 1 0) xs` (coincidental: wrong at 2) |
| `identify-geq-k (k=7)` | — | — | |
| `identify-is-mod-k (k=2)` | 29,912 | 198,932 | `map (λx. mod (sub x -1) 2) xs` |
| `identify-is-mod-k (k=3)`, `(k=7)` | — | — | |
| `identify-is-prime` | — | 203,860 | `map (λx. if (is_prime x) 1 0) xs` |
| `identify-k (k=-2)` | 30,083 | 200,024 | `map (λx. div (add x -1) x) xs` (coincidental) |
| `identify-k (k=1)` | 139,105 | — | `map (λx. if (eq x 1) x 0) xs` |
| `identify-k (k=3)` | 615,832 | — | `map (λx. mod (div 2 (add x -1)) 2) xs` (coincidental) |
| `identify-k (k=10)` | — | — | |
| `intersperse-k` (k = −2, 0, 1) | — | — | |
| `mult-k (k=-2)` | 6,626 | 32,662 | `map (λx. neg (add x x)) xs` |
| `mult-k (k=10)` | — | 199,711 | `map (λx. mul x (mul 2 5)) xs` |
| `positions` | — | — | |
| `prepend-k (k=-2)` | 373 | 1,147 | `cons (add -1 -1) xs` |
| `prepend-k (k=10)` | 144,604 | 1,315 | `cons (mul 2 5) xs` (original: `cons (mul 2 (add 1 (mul 2 2))) xs`) |
| `replace-all-k-with-n (1, 2)` | rejected | rejected | public match `map (λx. add x (div 1 x)) xs` fails a hidden example |
| `replace-all-k-with-n (2, 10)`, `(3, -2)` | — | — | |
| `replace-index-k-with-n (1, 2)` | 182 | 565 | `cons 2 (tail xs)` |
| `replace-index-k-with-n (2, 10)`, `(3, -2)`, `(5, 0)` | — | — | |
| `rotate-k` (k = −2, 10) | — | — | |
| `uniq` | — | — | |

### RESERVE-FAR2, task by task (B = 10⁶)

| Task | original | restored | Program (restored, else original) |
| --- | --- | --- | --- |
| `count-k` k = 0, 1 | 6,966; 7,731 | 33,101; 35,590 | `length (filter (λx. eq x k) xs)` (k = 0 as `is_empty (range x)`) |
| `count-k` k = 3, 4 | 137,637; 135,507 | 37,120; 37,475 | `length (filter (λx. eq x k) xs)` |
| `count-k` k = 5 | — | 37,886 | `length (filter (λx. eq x 5) xs)` |
| `drop-k` k = 0, 1, 3, 4, 5 | 1; 11; 160; 384; 1,747 | 1; 15; 519; 1,159; 7,565 | `tail^k xs` |
| `remove-index-k` k = 2 | 1,642 | 7,384 | `cons (head xs) (tail (tail xs))` |
| `remove-index-k` k = 3, 4, 5 | — | — | |
| `remove-mod-k` k = 2, 3 | 28,837; 531,338 | 196,822; 197,721 | `filter (λx. gt (mod x k) 0) xs` |
| `remove-mod-k` k = 5 | — | 199,593 | `filter (λx. lt 0 (mod x 5)) xs` |
| `take-k` k = 1 | 157 | 516 | `cons (head xs) nil` |
| `take-k` k = 2 | 27,346 | 32,768 | `map (λi. index i xs) (range 2)` (original: a `cons`/`head`/`tail` form) |
| `take-k` k = 3, 4 | — | 32,784; 32,813 | `map (λi. index i xs) (range k)` |

### Generalisation audit (report-only; the registered verdicts above are unchanged)

Each verifier-accepted program run on 200 seeded random inputs against a reference oracle
for its family (every FRESH-1 and FAR2 family; COMPOSE-24 through its own oracle):

| Partition | Vocabulary | Verified solves | Generalise | Coincidental |
| --- | --- | --- | --- | --- |
| FRESH-1 | original | 10 | 7 | 3: `identify-geq-k (3)`, `identify-k (-2)`, `identify-k (3)` |
| FRESH-1 | restored | 10 | 9 | 1: `identify-k (-2)` |
| RESERVE-FAR2 | original | 14 | 14 | 0 |
| RESERVE-FAR2 | restored | 18 | 18 | 0 |
| COMPOSE-24 | original | 6 | 6 | 0 |
| COMPOSE-24 | restored | 2 | 2 | 0 |

FRESH-2, RESERVE-NEAR, RESERVE-FAR, VALIDATION and TRAIN were not audited (their routines
are not all re-implemented). The FRESH partitions have eight public and one or two hidden
examples; the corpus partitions ten public and more hidden, and show no coincidence in
the audited one.

**Extended audit, added after the reviews (report-only, outside the registered audit).**
A review of the exploratory study on this branch showed that verified FRESH-2 solves of
scalar-output tasks are often wrong programs. The audit was therefore extended to every
exposed partition
([`exploratory/shift_loop_20261110/oracles.py`](../exploratory/shift_loop_20261110/oracles.py),
`audit_all.py`): a reference function is written from each task's name and used only if it
reproduces every example of the task, public and hidden (338 of 338 tasks have one); a
program is then run on 200 fresh inputs inside the task's own input range, spread over the
reference's outputs so that a boolean task gets both answers. On the 60 programs both
audits cover the verdicts are identical. Sound of verified, registered run:

| Vocabulary | Budget | TRAIN | NEAR | VALIDATION | FAR | FAR2 | FRESH-1 | FRESH-2 | COMPOSE-24 | All |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| original | 10⁵ | 18/18 | 49/49 | 4/4 | 7/7 | 11/11 | 5/6 | 15/21 | 2/2 | 111/118 |
| original | 10⁶ | 20/21 | 62/63 | 7/7 | 8/8 | 14/14 | 7/10 | 18/28 | 6/6 | 142/157 |
| restored | 10⁵ | 19/19 | 51/51 | 3/3 | 4/4 | 15/15 | 5/5 | 14/21 | 1/1 | 112/119 |
| restored | 10⁶ | 23/23 | 70/72 | 8/8 | 8/8 | 18/18 | 9/10 | 18/28 | 2/2 | 156/169 |

So ten of the 28 verified FRESH-2 solves at 10⁶ are coincidental with either vocabulary
(all ten with the original vocabulary and nine with the restored have a boolean or integer
output; every FRESH-2 task has one or two hidden examples), and the corpus partitions are not free
of coincidence: `has-k (k=5)` in RESERVE-NEAR is verified as a fold that looks at the last
element only, `is-mod-k (k=2)` as a prime test. No registered verdict, prediction or gate
changes: P1-1 to P1-4 are scored on verified counts as registered, and the five restored
FRESH-1 solves at 10⁵ are all sound. The FRESH-2 column of the headline table should be
read as 18, not 28.

### Compute

| Partition | Vocabulary | Candidates evaluated | Wall s (4 workers) | Mean completed size (top) | Mean pool size | Digest |
| --- | --- | --- | --- | --- | --- | --- |
| FRESH-1 | original | 23,141,240 | 212 | 8.2 | 215,789 | `e0c447248af39613` |
| FRESH-1 | restored | 23,245,677 | 213 | 7.3 | 230,368 | `fd51abe16b6a785d` |
| FRESH-2 | original | 68,486,289 | 623 | 7.6 | 209,742 | `1d67611a8d6b0d1a` |
| FRESH-2 | restored | 66,695,118 | 587 | 6.6 | 217,481 | `29283bdb923b6314` |
| RESERVE-NEAR | original | 41,614,593 | 400 | 6.4 | 125,477 | `9883db1d466e11d3` |
| RESERVE-NEAR | restored | 29,528,775 | 362 | 5.3 | 98,616 | `d315011fbb3ce868` |
| RESERVE-FAR2 | original | 7,879,464 | 83 | 6.4 | 113,454 | `bdd3737767cb1a38` |
| RESERVE-FAR2 | restored | 3,890,832 | 49 | 5.4 | 62,989 | `d5ee7213169b6a6a` |
| COMPOSE-24 | original | 19,281,077 | 197 | 8.7 | 258,485 | `722f685220348982` |
| COMPOSE-24 | restored | 22,226,632 | 215 | 7.9 | 316,527 | `a157ef489c901f63` |
| VALIDATION | original | 5,746,307 | 54 | 7.8 | 144,121 | `319f7917b847c6a4` |
| VALIDATION | restored | 4,098,515 | 55 | 6.6 | 116,557 | `e30149429096b49b` |
| RESERVE-FAR | original | 2,867,370 | 34 | 6.2 | 61,508 | `2d6e97a0016f1876` |
| RESERVE-FAR | restored | 3,015,272 | 53 | 5.6 | 84,732 | `b3c7f836705b63b3` |
| TRAIN | original | 15,342,680 | 142 | 6.6 | 122,967 | `9a8359e4422f235f` |
| TRAIN | restored | 12,117,433 | 144 | 5.2 | 111,250 | `90f3b2689b6c8164` |

About 3.5 × 10⁸ candidate evaluations in 57 minutes of wall-clock on four cores. "Mean
completed size" is the top-context symbol size whose level was fully enumerated before
the budget ran out.

## Predictions scored

| ID | Registered | Expected | Observed | Score |
| --- | --- | --- | --- | --- |
| P1-1 | restored FRESH-1 at 10⁵ ≥ 15 | PASS (moderate) | 5 of 33 | **miss** |
| P1-3 | ≥ 2 of the 5 corpus-lacking FRESH-1 routines (restored, 10⁵) | PASS (low) | 1 (`replace-index-k-with-n`); 2 at 10⁶ | **miss** (hit at 10⁶) |
| P1-2 | original FRESH-1 at 10⁵ ≤ 10 | PASS (moderate) | 6 of 33 | hit |
| P1-4 | RESERVE-FAR2 ≥ 10 of 21 at 10⁵ (no vocabulary named: both scored) | PASS (moderate) | original 11, restored 15 of 21 | hit |
| P1-5 | throughput ≥ 10⁴ candidates/s/core | PASS (low) | 32,439/s | hit |
| S1 | restored FRESH-1 at 10⁶: 10 (range 7–14) | — | 10 | hit |
| S2 | original FRESH-1 at 10⁶ ≤ 8 | PASS (moderate) | 10 (7 generalising) | **miss** |
| S3 | E ≥ 1 at 10⁶ on FRESH-1 with `identify-is-prime` among the escapes | PASS (moderate) | E = 1, `identify-is-prime` | hit |
| S4 | restored ≥ original on FRESH-1 and FAR2 at 10⁶ | PASS (moderate) | 10 vs 10; 18 vs 14 | hit |
| S5 | zero public matches rejected (FAIL expected, 1–5 rejections) | FAIL | 31 rejections over 16 files | **miss** (far more than predicted) |
| S6 | COMPOSE-24 at 10⁶ ≤ 4 with either vocabulary | PASS (moderate) | original 6, restored 2 | **miss** |

Two of the directive's five predictions miss, and three of my six secondary ones. The misses have one shape: I under-estimated how much a 10⁶ enumeration finds with
the *original* vocabulary (S2, S6, P1-1's premise) and how often what it finds is a
coincidence (S5). P1-1 was wrong by a factor of three at 10⁵ and would still be wrong at
10⁶ (10, not 15).

## What this adds, and what it does not

- **The budget separation the directive asked for, measured.** Going from 64 to 10⁶
  candidates with RSI-2's own vocabulary and no learning does more on every exposed
  partition than any rsi3 mechanism did (FRESH-2 28 vs 13, FAR2 14 vs 5, COMPOSE-24 6 vs
  0), and matches or beats the 4× budget diagnostic (HONEST@256) everywhere but TRAIN.
  That is the F2 observation taken to its end: budget is the first-order variable.
- **Vocabulary is second-order at this budget, and its gain is almost entirely
  constants.** Restoring DreamCoder's set adds +9 NEAR, +4 FAR2, +2 TRAIN, +1 VALIDATION,
  costs −4 COMPOSE-24, and nets 0 on FRESH-1 and FRESH-2. Of the 82 verified programs
  that use a restored symbol, 68 use a constant 3–5, 25 use `index` (mostly `take-k` and
  NEAR parameter variants), 6 use `is_prime` and 2 `is_square`; `is_prime` carries the
  true escapes.
  `unfold`, `fix1`, `zip` and the pairs carry nothing within 10⁶ candidates: the programs
  that need them are 12+ symbols and the enumeration completes 8–9.
- **Closure escape exists and is tiny.** Three true escapes (two families: `identify-is-prime`
  / `is-primes`, and `repeat-k`), all by `is_prime` or a constant, none by a structural
  primitive. The routines F4 named as closure failures (`intersperse-k`, `positions`,
  `uniq`) stay unsolved: in this language their programs are `fold`s of 9–12 symbols, and
  the engine's reach, not the vocabulary, is the binding limit.
- **Coincidental solutions are a measured hazard of enumeration at this scale.** 31
  verifier rejections and 4 coincidental acceptances in the two audited partitions. The
  FRESH protocol's one or two hidden examples do not separate a 10⁶-candidate search's
  matches from the intended routine; Phase 2's G2 (shortcut solvers, refutation of
  nearest competitors) and the §8.6 re-expressed-verifier audit are the right tools, and
  the Phase 1 numbers should be read with the audit column beside them.
- **Not claimed.** No learning, no library, no invention, no J evaluation, nothing on J's
  pools, nothing on TEST. No statement about Phase 2's tiers. The run was on one machine,
  not on Actions; the digests make it reproducible there.

## Adversarial review

Seven reviewers, one per area (evaluator, closures, normal forms, engine, sealing, driver,
documents), read the pull request to break it. They returned 35 findings, 26 distinct.
Each was then reproduced by a script or a test, or confirmed in the code, before it was
accepted; all 35 hold. Two rules decided what to do with a finding: a correction must not
change a registered number, and the engine that produced the numbers is not edited after
the fact. `PREDICTIONS_P1.md` and the result files are untouched.

### Corrected (no registered number changes)

| Finding | Correction | Shown by |
| --- | --- | --- |
| The guard let a sealed file be reached through a directory descriptor (`dir_fd`), an inherited descriptor, a hard link, a rename, the working directory or a child program. | [`guard.py`](guard.py) rewritten: every such route is refused, as are the start methods that launch a fresh interpreter and an unaudited file reader. | [`tests/test_guard.py`](tests/test_guard.py): 105 constructed attacks on a decoy tree are refused; one residual is pinned |
| The run driver built the tasks and the verifier before it forked its workers, so every worker held every hidden example in memory. | The workers are forked first, hold no task and no loader, seal the loader packages for themselves and receive public examples only. A worker forked late refuses to search. | `test_workers_are_forked_before_any_task_is_loaded`, `test_worker_forked_after_the_tasks_refuses_to_search` |
| The check that no solver module imports J missed `from . import judge` and `from .. import judge`; J's copied audit flags no rsi5 import. | Relative imports are resolved before the check. A solver module may import only a short list of modules. | `test_judge_import_check_catches_every_form`, `test_import_list_refuses_the_unaudited_routes` |
| The admitted-primitive loader used a dynamic importer, which J's audit refuses. | Static imports (fixed before this section was written). | `test_judge_audit_findings_are_the_declared_ones` |
| "TEST is never loaded" was true of TEST's file only: the RESERVE loaders parse DreamCoder's source file, which holds TEST's twelve records, and discard them by name. | The sentence now says exactly that. The guard seals TEST's file; no solver module names its loader. | `test_task_file_directory_exposes_only_the_listed_files`, `test_no_solver_module_names_the_sealed_partition` |
| The report scored P1-3 as a miss when its result file was absent, and scored P1-4 on the restored vocabulary although the registered wording names none. | An absent file is "(not run)". P1-4 is scored with both vocabularies: original 11, restored 15 of 21, a hit with either. | `python -m rsi5.report_p1` |
| The plan's child-context point cap and the relation between report budgets and the run budget were not checked. | The driver refuses a plan whose cap differs from the engine's constant or whose report budget exceeds the run budget. | [`phase1.py`](phase1.py) `load_plan` |
| The closure agreement test could not see a closure that fails where the interpreter succeeds. | The test fails on that case outside one known class, which it pins: 191 cases on its corpus, all in terms with a partial application, which the engine never builds. | `test_closures_agree_with_reference` |
| `NORMAL_FORMS.md` called every rule an equivalence; `ARCHITECTURE.md` said lambda depth 2 and contexts created on demand; the README said every primitive terminates under the step budget. | Each document now states what the code does. | the documents |
| The package layout differs from the directive's §11 sketch. | `ARCHITECTURE.md` lists the differences; `test_vocabulary_matches_VOCABULARY_md` exists under that name. | [ARCHITECTURE.md](ARCHITECTURE.md) |

The corrected driver was then run on the whole plan: eight partitions, both vocabularies,
10⁶ candidates per task. All sixteen digests equal the registered ones and every record
field outside wall-clock is equal ([`results_p1/replay_sealed/`](results_p1/replay_sealed/);
the identity table is in `python -m rsi5.report_p1`). These files were produced by the
driver as it stands after the second review below.

### Second review, of the corrections themselves

The corrections were then attacked in turn, on a copy of the tree that holds neither J's
directory nor an unexposed task file. Four reviewers finished (guard, driver, tests,
documents); the reviewer of the normal-forms argument and all four skeptics who were to
re-test the findings were cut off by a usage limit, so the fourteen findings were re-tested
by the author instead. Every one reproduced. The reviewer of the guard built no undeclared
route through it; the reviewer of the driver found three by other means.

| Finding | Correction | Shown by |
| --- | --- | --- |
| The guard failed open on a name it could not read: a `bytearray` or `memoryview` path (accepted by Python 3.11, the Actions version) and an `__index__` object standing for a descriptor were not resolved, so a sealed file was opened and a sealed directory listed. | The hook reads the characters the system call will see from any bytes-like, path-like or `str`-subclass object, resolves `__index__` descriptors, and refuses a name it cannot read. | `test_every_path_into_a_sealed_directory_is_refused` (49 attacks) |
| From a working directory removed after the hook was installed, `os.getcwd()` fails while the kernel still follows `..`; a relative path into a sealed directory was allowed. | The directory is read from `/proc/self/cwd`; with no working directory known, a relative name is refused. | `test_deleted_working_directory_still_resolves` |
| "A worker forked late fails the run" was false for the case that produces one: a worker that dies leaves `multiprocessing.Pool` waiting for ever. | The pool is a `concurrent.futures` executor, which never replaces a worker and raises when one dies. | `test_dead_worker_fails_the_run` |
| The test that no hidden example travels to a worker could not fail: its byte pattern never occurs inside another pickle. | It compares values, for every task of every partition, and a second test feeds it views that do leak. | `test_public_view_is_plain_data_without_hidden_examples`, `test_hidden_example_check_catches_a_leaking_view` |
| No test ran the driver: with both `guard.install()` calls removed from `phase1.py` the suite stayed green. | One test runs `phase1.main` with a probe around the worker's function and checks the hook in the driver and in every worker, the content of each job, and the written verdicts against an independent verifier and the registered file. `load_plan`'s refusals have their own tests. | `test_run_driver_itself`, [`tests/test_plan.py`](tests/test_plan.py) |
| The import list tested the first component of a name, so `from multiprocessing import util, sharedctypes` passed, and the documents said the list closed the unaudited process starts. | `multiprocessing` and `concurrent` are held to exact names; no solver module spells the identifiers of the unaudited routes. The documents now say what this cannot close. | `test_import_list_refuses_the_unaudited_routes`, `test_no_solver_module_spells_an_unaudited_route` |
| The closure agreement test excused any failure in a term with a partial application anywhere, and did not assert its pinned count. | The count is asserted (191), and a second test admits no excuse on the corpus that matters: 2,386 programs from the engine's own pools, both vocabularies. | `test_closures_agree_on_the_programs_the_engine_builds` |
| The static scans passed on an empty file list; several spellings of the sealed names were not seen. | A test names the modules the scans must cover; constants built with `%`, `join`, `format` and bytes are folded. | `test_static_scans_cover_the_solver_modules` |
| Renames and links relative to a directory descriptor, a link into a sealed directory, bytes paths, a seal given through a symbolic link and `pty.spawn` were claimed and held by no attack. | Attacks added for each. | `tests/guard_attacks.py` |
| The guard test opened the package's own `list_tasks2.json` for writing: had the guard regressed, the test would have truncated it. | The write is aimed at a decoy of that name; the real file is decided from its name alone. | `test_guard_blocks_pool_access` |
| The documents said an `and`/`or` guard is always lost. Only the vectorised path is strict; the closures skip the right side, so a guard inside a lambda body works when the canonical order puts it first. | `NORMAL_FORMS.md`, `ARCHITECTURE.md` and the table below say so. | `test_vectorised_and_or_are_strict` |

Not re-reviewed: the normal-forms argument ("a replacement is defined at least as often")
had no reviewer; these corrections of the corrections have had none either.

### Deferred to a new registration (engine findings)

Every program the engine returns is re-checked by the reference interpreter and judged by
the frozen verifier, so none of these can produce a false solve. Each loses programs or
misdescribes the search. Each is pinned in
[`tests/test_review_findings.py`](tests/test_review_findings.py).

| Finding | What the engine does | Effect on the registered run |
| --- | --- | --- |
| `and`, `or` | Strict in the vectorised path and reordered as commutative; the interpreter and the closures evaluate left to right and skip the right side. `and (not (is_empty xs)) (eq (head xs) 1)` is `false` on `[]` in the interpreter and a failure in the vectorised path. | A guard at the top of a program is lost; the same behaviour through `if` is one symbol longer. A guard inside a lambda body works when the canonical order puts it first. Size of the loss not measured. |
| `add`, `sub` | No 4096-bit limit in the fast paths. | A match of that kind would be a rejected re-check: none in 676 records. |
| Step charge | The closures charge per element and per recursive call; the interpreter charges per node. A closure can finish where the interpreter runs out of steps. | Same: no rejected re-check. |
| List cap | 1024 in the closures (registered), 4096 in the interpreter. | Programs with a longer intermediate list are lost. Not measured. |
| `fix1` seed | Evaluated before it is needed. | `fix1` is in no verified program. Not measured. |
| Partial application | Given arguments evaluated eagerly. | None: the engine builds no partial application. |
| Vectorised `is_prime` | No step charged; refuses integers above 64 bits. A prime near 10⁹ is answered where the interpreter runs out of steps. | No rejected re-check. |
| `neg k` | Refused for every literal, though −2 (both vocabularies) and −3, −4, −5 (restored) are not literals. | Every program that needs one is a symbol longer: `prepend-k (k=-2)` is `cons (add -1 -1) xs`. |
| `fix1` without recursion | Refused, though it is the language's only let-binding. | `fix1` is in no verified program. Not measured. |
| Two inputs of different types | The match is wrapped with its binders reversed and rejected. | None: all 338 tasks have one input. |
| Lambda nesting | The limit counts binders: a `fold` step or a `fix1` body holds no lambda, a `map` body may hold a `fold`. | Programs with a lambda inside a `fold` step are not enumerated. Not measured. |
| Child contexts | Created when a level's shapes are listed. | The `contexts` field counts empty contexts. No effect on a solve. |
| Re-check order | A program enters the pool before its re-check, so a rejected match keeps its behaviour class. | None: no rejected re-check. |
| `exhausted` | Set after one size level that adds no program. | None: the flag is set in no record, and every search without a public match spent its whole budget. |

"Not measured" means the registered files cannot show it: a program lost to pruning
leaves no trace. The measurement is the repaired engine run beside this one under a new
registration, which is the Owner's call together with the §3.3 gate.

## Limitations (Target Property + Criterion)

1. **Reach.** Target: the engine completes symbol size 12 in the top context within the
   registered budget on a list → list task. Criterion: mean completed size ≥ 12 at 10⁶ on
   FRESH-1. Measured: 8.2 (original), 7.3 (restored). Pure size-ordered enumeration spends
   60–75% of its budget on terms observational equivalence then discards, and the top
   context's int- and pair-typed programs dominate its pools.
2. **Verifier discrimination.** Target: a verified program generalises to the family's
   semantics. Criterion: 0 coincidental acceptances in the audit. Measured: 4 of 60
   audited solves (all FRESH-1; 0 of 40 on FAR2 and COMPOSE-24). The extended audit over
   every partition finds 15 of 157 (original) and 13 of 169 (restored) at 10⁶, ten of them
   on FRESH-2 with either vocabulary.
3. **Engine semantics against the reference interpreter.** Target: the engine enumerates
   every normal-form program of the language up to the completed size, keyed by the
   interpreter's behaviour. Criterion: the fast paths agree with the interpreter on every
   enumerated term and input, failures and budget included, and every pinned test in
   `tests/test_review_findings.py` is deleted because its finding is repaired. Measured:
   fourteen findings open ("Adversarial review"); zero rejected re-checks in 676 records;
   the completeness loss is not measured.
4. **Sealing.** Target: no code running in a solver process can read J's files, TEST's
   file or a hidden example. Criterion: a solver given arbitrary Python fails to read a
   secret planted in J's directory, because J and the verifier run in another process
   under an identity whose files the solver's identity cannot read. Measured: an audit
   hook in the same process, a tripwire. It refuses the 105 routes constructed in
   `tests/test_guard.py`, and static checks keep `ctypes`, native modules and
   `_posixsubprocess` out of the solver's source. Two reviews each found routes through
   the hook that the one before had missed; a third would likely find more. Arbitrary
   Python still gets through: `ctypes` or a native module, `_posixsubprocess.fork_exec`,
   `multiprocessing.util.spawnv_passfds`, a descriptor, hard link or bind mount that predates the
   hook, a thread that changes what a name refers to between the hook's check and the
   system call, code that rebinds the guard's names, and what root can do. The driver
   process holds the hidden examples by design; a search worker holds none.
5. **J.** Target: G3 evaluates C1 ∪ {f} on J's stage pools. Criterion: J accepts a program
   that uses a restored primitive. Measured: J as copied verifies with `rsi2.search.verify`
   and runs rsi3 runtimes; it cannot ([ARCHITECTURE.md](ARCHITECTURE.md) §J). Owner decision
   needed before Phase 2.
6. **Actions.** Target: the registered run executes on GitHub Actions. Criterion: a
   `rsi5/run-*` branch run with byte-identical digests. Not done from this session; the
   workflow is committed and the local digests are the reference.
7. **Scale.** 338 tasks, 10⁶ candidates per task, one vocabulary pair, one machine. No
   claim about superintelligence, the singularity or consciousness.
