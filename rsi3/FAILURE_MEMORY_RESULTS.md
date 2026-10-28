# Failure-memory study — measured results

All six registered runs completed (RSI3_UNIFORM_FM and RSI3_FM × seeds
11/22/33 × 8 generations; `experiment_config_failure_memory.json`, unchanged
since the pre-registration commit 8a8ebb8). Comparators are the committed runs
in `results/`. Raw run files for this study are in
[`results_failure_memory/`](results_failure_memory/); the tables are
`python -m rsi3.report` output over both directories.

**Headline.** Carrying public failures across grammar changes and pathways
moved verified capability for the first time in RSI-3. The uniform arm
reached 8/36 TRAIN on every seed (RSI-2: 6, resumption alone: 7). The learned
controller rose from 6 to 7, 8, 7. In that arm, a pathway the system created
from its own earlier solution produced a verified solve on every seed. All
12 registered predictions hit, including the two registered FAILs;
VALIDATION did not change, as predicted.

## TRAIN hidden-verified solved, per generation

| Arm | Seed | g1 | g2 | g3 | g4 | g5 | g6 | g7 | g8 | VALIDATION g8 | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RSI3_UNIFORM_FM | 11 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 8 | 2/12 | 460 |
| RSI3_UNIFORM_FM | 22 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 8 | 1/12 | 475 |
| RSI3_UNIFORM_FM | 33 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 8 | 2/12 | 476 |
| RSI3_FM | 11 | 6 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 1/12 | 1055 |
| RSI3_FM | 22 | 6 | 6 | 6 | 6 | 7 | 7 | 7 | 8 | 2/12 | 1097 |
| RSI3_FM | 33 | 6 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 2/12 | 1042 |

## Means over seeds, with the earlier arms

| Arm | TRAIN g8 | VALIDATION g8 | CPU s per run | CPU vs RSI2 |
| --- | --- | --- | --- | --- |
| RSI2 | 6.00 | 1.67 | 241 | 1.00× |
| RSI3 | 6.00 | 1.67 | 419 | 1.74× |
| RSI3_UNIFORM | 7.00 | 1.33 | 376 | 1.56× |
| **RSI3_UNIFORM_FM** | **8.00** | 1.67 | 470 | 1.95× |
| **RSI3_FM** | **7.33** | 1.67 | 1065 | 4.42× |

## What was solved beyond RSI-2's six tasks

| Task | Arm | Pathway | Generation | Seeds |
| --- | --- | --- | --- | --- |
| index-k (k=3) | RSI3_UNIFORM_FM | prior | 4 (was 5 without failure memory) | all three |
| prepend-k (k=4) | RSI3_UNIFORM_FM | prior | 8 | all three |
| prepend-k (k=4) | RSI3_FM | **analog:prepend-k (k=0)** — a genesis pathway | 5 | all three |
| prepend-k (k=5) | RSI3_FM | recognized | 8 | 22 |

The genesis result is the first verified solve by a system-created pathway in
any RSI-3 run (the first study's M3 predicted one and missed). The pathway
was created in generation 1 from the system's own verified solution to
prepend-k (k=0), held no search state until the controller woke it in
generation 2, and solved prepend-k (k=4) in generation 5. In that window it
evaluated 18–21 new programs and skipped 74–78 programs already known to fail.

RSI3_FM never reached index-k (k=3), which needs rank ~273 in the prior
pathway's order. Its allocation still spreads over about a hundred slots, so
no single order gets that deep.

## Predictions scored

| Prediction | Registered | Observed | Score |
| --- | --- | --- | --- |
| RSI3_UNIFORM_FM TRAIN g8 | 8 (7–9) | 8, 8, 8 | hit |
| RSI3_FM TRAIN g8 | 7 (6–8) | 7, 8, 7 (mean 7.33) | hit |
| VALIDATION g8, both arms | 1–2 | 1–2 on every run | hit |
| F1 RSI3_UNIFORM_FM > RSI3_UNIFORM | PASS | PASS (8 vs 7 ×3) | hit |
| F2 RSI3_FM > RSI3 | PASS | PASS (7/8/7 vs 6) | hit |
| F3 RSI3_FM > RSI3_UNIFORM_FM | FAIL | FAIL (7/8/7 vs 8) | hit |
| F4 RSI3_UNIFORM_FM > RSI2 | PASS | PASS (8 vs 6 ×3) | hit |
| F5 RSI3_UNIFORM_FM VALIDATION > RSI2 | FAIL | FAIL (2/1/2 vs 2/1/2) | hit |
| G1 known failures skipped free, every run | > 0 | 10,437 per uniform run; 50,445–52,694 per learned run | hit |
| G2 distinct failed programs, most-searched task, uniform | ≥ 450 | 615 | hit |
| G3 first generation with 7 solved, uniform | ≤ 5 | 4 | hit |
| G4 CPU, uniform FM vs uniform | ≥ 1.0× | 1.25× | hit |

The expected shape was right on every point, including the two registered
FAILs. One thing the predictions did not anticipate: the genesis-pathway
solve, and that the learned arm reached a task (prepend-k, k=5) the uniform
arm did not.

## Cost

Skipping a known failure is free in logical budget but not in CPU: the
enumerator still has to produce the program before it can be skipped. The
learned arm restarts the recognized pathway's search every generation and
keeps about a hundred live searches, so it skipped ~51,000 known failures per
run and cost 2.54× RSI3's CPU (4.42× RSI-2's). Its worker peaked at about
4.5 GB of memory. The uniform arm cost 1.25× RSI3_UNIFORM's CPU.

## Execution note

The first launch ran two workers. When one learned-arm run peaked at about
4.5 GB on this 7 GB machine, the pool was stopped about one minute into its
next two jobs, before two learned-arm runs could overlap. The three
unfinished runs were rerun from scratch with the same configuration: the
learned-arm seeds sequentially in one process, the last uniform-arm seed in
another. Runs are deterministic given (arm, seed, config); RSI3_UNIFORM_FM's
three seeds are identical, as RSI3_UNIFORM's were. No configuration value,
seed, or budget changed.

## Where it stopped

| Arm | Last new TRAIN best | Distinct failed programs, most-searched task |
| --- | --- | --- |
| RSI3_UNIFORM_FM | g8 | 615 |
| RSI3_FM | g5 (seed 22: g8) | 874–896 |

VALIDATION stayed at RSI-2's level in every run, and no library entry was
adopted in either arm. TRAIN gains came from searching deeper and wasting
less, not from a grammar that transfers. That is the open problem this study
leaves, as a target property: a VALIDATION gain on every seed at B_eval = 64,
which requires RSI-2's abstraction step to adopt at least one library entry.

## Claim boundary

36 TRAIN tasks (hidden-example verified) and 12 VALIDATION tasks of RSI-2's
frozen corpus; B_wake = B_eval = 64; RSI-2's search limits; seeds 11/22/33.
TEST was not opened. The gain is a better use of a fixed search procedure's
budget through memory of its own failures; it is not recursive
self-improvement and not a generalization result.
