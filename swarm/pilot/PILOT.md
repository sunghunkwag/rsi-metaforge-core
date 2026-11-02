# P4 pilot: 30 minutes per arm, and the constants chosen for the registered runs

The pilot ran every arm once (seed 11) for 30 minutes of wall time with
the constants in [`pilot_config.json`](pilot_config.json), three arms at a
time on the development machine (4 cores), at commit d66ba82. Its
purpose is the one the directive gives P4: to choose `D`, `n_prop`,
`B_gen`, `B_inst`, `k_edit` and `G` before anything is registered. Its
numbers are not evidence for any of K1-K7 and are not reported as such;
[`pilot_report.md`](pilot_report.md) is the report.py rendering of the
same summaries, kept to show the report format on real runs. Per-arm
summaries are the `*_seed11_summary.json` files.

## What the pilot ran

| Constant | Pilot value |
| --- | --- |
| D | 8192 |
| n_prop (proposals per generation) | 6 |
| lineages | analogy, compose, mutate, distinguisher |
| B_gen (Builder candidates per generation) | 4000 |
| B_inst (kernel candidates per task per solve) | 200 |
| k_edit (self-edit candidates judged per generation) | 1 |
| horizon (generations before an open task becomes a marker) | 8 |
| regression sample (crossed tasks replayed by the judge) | 6 |
| executor timeout / memory | 2 s / 512 MB per child |
| wall cap | 30 minutes per arm (G was 20; no arm reached it) |

## Outcome per arm

| Arm | generations in 30 min | X(G) | archive | open | markers | forged | library | edits adopted / proposed | wake failures | wall s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWARM_FULL | 9 | 0 | 43 | 38 | 5 | 1 | 0 | 1 / 9 | 3 (g7 on) | 2126 |
| SWARM_RECORDS | 9 | 0 | 43 | 38 | 5 | 1 | 0 | 1 / 9 | 3 (g7 on) | 2127 |
| SWARM_NO_MAPPER | 9 | 0 | 43 | 38 | 5 | 1 | 0 | 1 / 9 | 3 (g7 on) | 2126 |
| SWARM_NO_SELFEDIT | 11 | 0 | 52 | 36 | 16 | 0 | 0 | 0 / 0 | 3 (g7 on) | 1938 |
| SWARM_NO_BREAKER_REGRET | 9 | 2 | 31 | 24 | 5 | 1 | 1 | 1 / 9 | 2 (g8 on) | 1867 |
| SWARM_SHUFFLED_FIELD | 8 | 1 | 38 | 37 | 0 | 1 | 0 | 1 / 8 | 2 (g6 on) | 1859 |

Three arms (FULL, RECORDS, NO_MAPPER) have identical archives, meters,
Breaker credits and Builder states generation for generation; their
ledger digests differ only through the arm name and configuration. This
is expected and worth stating: with no crossing, the Builder writes no
solution signatures and no fragments into the field (one fragment after
its first forge at g9), so the analogy lineage has nothing to read in
either channel and the mapper has no paired event to fit. The latent
channel, the records channel and the mapper can only separate after the
first crossing. NO_BREAKER_REGRET diverged from g2 because its lineage
multipliers follow admissions instead of crossings, so it proposed a
different sequence of tasks and admitted fewer (31 against 43; 12
Kc rejections). The two crossings it reached (g5, generations-to-crossing
1 and 3) came through a forged stage primitive adopted at g4 and one
library entry learned from a mined wake solution; SHUFFLED_FIELD's one
crossing (g8) came through its forge adoption at g7.

## Wall time by phase (seconds)

| Arm | g | open | propose + admit | wake + mined | crossing check | propose edits (forge) | judge | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SWARM_FULL | 1 | 5 | 14 | 36 | 12 | 2 | 13 | 77 |
| SWARM_FULL | 3 | 16 | 16 | 103 | 14 | 14 | 37 | 184 |
| SWARM_FULL | 5 | 26 | 13 | 170 | 12 | 2 | 65 | 262 |
| SWARM_FULL | 7 | 34 | 9 | 200 | 6 | 13 | 80 | 309 |
| SWARM_FULL | 9 | 38 | 14 | 200 | 13 | 2 | 105 | 334 |
| SWARM_RECORDS | 1 | 5 | 14 | 36 | 12 | 2 | 13 | 77 |
| SWARM_RECORDS | 3 | 16 | 16 | 102 | 14 | 14 | 38 | 184 |
| SWARM_RECORDS | 5 | 26 | 13 | 170 | 12 | 2 | 65 | 262 |
| SWARM_RECORDS | 7 | 34 | 9 | 200 | 7 | 13 | 82 | 311 |
| SWARM_RECORDS | 9 | 38 | 14 | 200 | 12 | 2 | 104 | 333 |
| SWARM_NO_MAPPER | 1 | 5 | 14 | 36 | 11 | 3 | 13 | 77 |
| SWARM_NO_MAPPER | 3 | 16 | 15 | 102 | 14 | 14 | 38 | 184 |
| SWARM_NO_MAPPER | 5 | 26 | 13 | 172 | 12 | 2 | 64 | 263 |
| SWARM_NO_MAPPER | 7 | 34 | 9 | 200 | 7 | 13 | 82 | 312 |
| SWARM_NO_MAPPER | 9 | 38 | 14 | 200 | 12 | 2 | 106 | 334 |
| SWARM_NO_SELFEDIT | 1 | 5 | 13 | 37 | 12 | 0 | 0 | 63 |
| SWARM_NO_SELFEDIT | 3 | 16 | 16 | 105 | 14 | 0 | 0 | 135 |
| SWARM_NO_SELFEDIT | 5 | 26 | 13 | 174 | 12 | 0 | 0 | 200 |
| SWARM_NO_SELFEDIT | 7 | 34 | 9 | 200 | 7 | 0 | 0 | 216 |
| SWARM_NO_SELFEDIT | 9 | 38 | 14 | 200 | 11 | 0 | 0 | 225 |
| SWARM_NO_BREAKER_REGRET | 1 | 5 | 14 | 37 | 12 | 2 | 13 | 79 |
| SWARM_NO_BREAKER_REGRET | 3 | 14 | 9 | 99 | 7 | 0 | 33 | 148 |
| SWARM_NO_BREAKER_REGRET | 5 | 19 | 8 | 122 | 7 | 8 | 99 | 244 |
| SWARM_NO_BREAKER_REGRET | 7 | 26 | 15 | 195 | 11 | 1 | 74 | 296 |
| SWARM_NO_BREAKER_REGRET | 9 | 24 | 4 | 200 | 3 | 21 | 1 | 229 |
| SWARM_SHUFFLED_FIELD | 1 | 5 | 14 | 37 | 13 | 3 | 13 | 79 |
| SWARM_SHUFFLED_FIELD | 3 | 16 | 16 | 106 | 14 | 14 | 37 | 187 |
| SWARM_SHUFFLED_FIELD | 5 | 26 | 14 | 172 | 11 | 2 | 66 | 265 |
| SWARM_SHUFFLED_FIELD | 7 | 34 | 10 | 200 | 7 | 5 | 80 | 301 |

Two costs dominate and both grow with the generation count:

1. **The wake grew linearly and hit its timeout.** 36 s at g1, 68, 103,
   138, 170, 197, then the 200 s allowance from g7 on in every arm
   (`live_call_failed`, "timeout after 200s"; those generations show
   `builder 0 cand`). The budget did not grow: every wake spent exactly
   B_gen = 4000 candidates. Profiling on the pilot's own tasks found the
   cause: typed best-first enumeration costs 8-12 ms per distinct
   candidate (`grammar.productions` and unification; evaluation is
   cheap), and the per-generation wake process re-enumerated each task's
   whole search prefix from scratch before evaluating anything new
   (`ResumableSearch.fast_forward`). The re-enumeration cost equals the
   cumulative budget ever spent on the tasks still open, so it rose by
   about B_gen x 8 ms every generation. Commit e93e052 replaces the
   fast-forward with a checkpoint of the search frontier (heap, serial,
   expansion count, distinct-term set, fresh-name watermarks) stored
   per task and grammar order in the Builder's state file, about 1 MB
   and 0.4 s per task; the checkpoint continues the enumeration
   identically (tests in `swarm/tests/test_resumable.py`). A
   four-generation check of SWARM_FULL at B_gen = 6000 after the fix
   (same machine, one worker) gives wake times of 41, 46, 41 and 57 s
   with 3, 6, 9 and 13 open tasks, against 36, 103, 170 and 200+ s in
   the pilot at B_gen = 4000.
2. **The judge grows with the open set.** The kernel solves every open
   task plus the crossed sample from the candidate snapshot at B_inst
   (the incumbent's solves are memoised per snapshot): about 2.4 s per
   open task at B_inst = 200, so 13 s at 5 open tasks and 105 s at 38.
   The pilot's open set grew by about 5 tasks per generation because the
   admission rate was high (43 of 49 proposals in FULL) and crossings
   were rare, and the horizon only retires a task after 8 generations.

Two more observations the constants have to respect:

- **A task's search under one grammar order is finite.** With
  `max_expansions` = 20000 (generation-0 `params.json`), the enumerator
  yields about 2500 distinct programs for a list-to-list request before
  it is exhausted; further budget on that task is unspent until a forge
  or a library adoption changes the grammar order and restarts the
  frontier. In the pilot the oldest tasks reached positions of 1924 at
  g6 and had not crossed. The Builder's `allocation` parameters (`even`
  or `commit`, in the self-edit menu) are its own means of moving budget.
- **Crossings came from substrate change, as the design intends.** No
  task was crossed by budget alone in any arm; the three crossings
  followed a forge adoption or a learned library entry.

## Constants chosen

| Constant | Registered value | Reason |
| --- | --- | --- |
| D | 8192 | latent operations are a negligible cost at this width; unchanged from the pilot |
| n_prop | 4 | one proposal per lineage per generation; with 80-90 % admission and horizon 8 the open set settles near 25-30 instead of the pilot's 38+, which bounds the judge |
| B_gen | 6000 | 200-250 candidates per open task per generation, so a task sees about 2000 of its roughly 2500 reachable programs before the horizon retires it; wake about 60 s after the fix |
| B_inst | 200 | unchanged from the pilot: the admission margin and the crossing check keep the same meaning |
| k_edit | 1 | the judge is the costliest kernel step and scales with the open set; one candidate per generation |
| G | 20 | the second-difference rule reads the last half, ten generations; at about 150 s per generation a run is 50 minutes, and 18 runs take about 4 hours on 4 workers |
| horizon | 8 | unchanged from the pilot |
| executor memory | 1024 MB per child | a restored frontier at position 2000 holds about 190 MB; 512 MB held in the pilot but leaves little margin at B_gen = 6000 |

The constants are fixed in `swarm/experiment_config.json` (P5) together
with the kernel pins and seeds 11, 22, 33, and are not changed after
registration.

## What the pilot does not show

One seed, 8-11 generations, three arms numerically identical for the
whole run: nothing here supports or refutes K1-K7, and nothing here is a
capability result. The pilot shows that the loop runs end to end, where
its wall time goes, that crossings occur through substrate change, and
which constants keep a 20-generation run inside the compute available.
