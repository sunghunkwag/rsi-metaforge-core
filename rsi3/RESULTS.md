# RSI-3 measured results

All 15 registered runs completed (5 arms × seeds 11/22/33 × 8 generations;
configuration `experiment_config.json`, unchanged since the pre-registration
commit a09a426). Elapsed 2,913 s wall on 2 workers. Raw run files are in
[`results/`](results/); the tables below are `python -m rsi3.report` output.

**Headline.** The memory-feedback controller did not move certified
capability. Every learned RSI-3 arm ended at 6/36 TRAIN on every seed — the
same six tasks RSI-2 solves — while costing 1.5–1.7× RSI-2's CPU. The only
gain in the study came from the control arm that uses memory's hard rule alone
(resume the enumeration instead of re-running its prefix) with an even budget
split: 7/36 on every seed. VALIDATION did not change in any arm. All five
decisive comparisons fail; C1, predicted to pass, is a miss.

## TRAIN hidden-verified solved, per generation

| Arm | Seed | g1 | g2 | g3 | g4 | g5 | g6 | g7 | g8 | VALIDATION g8 | CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RSI2 | 11 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 251 |
| RSI2 | 22 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 1/12 | 234 |
| RSI2 | 33 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 237 |
| RSI3 | 11 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 435 |
| RSI3 | 22 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 1/12 | 427 |
| RSI3 | 33 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 394 |
| RSI3_NO_REPLAY | 11 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 420 |
| RSI3_NO_REPLAY | 22 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 1/12 | 434 |
| RSI3_NO_REPLAY | 33 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 396 |
| RSI3_NO_GENESIS | 11 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 374 |
| RSI3_NO_GENESIS | 22 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 1/12 | 369 |
| RSI3_NO_GENESIS | 33 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 2/12 | 357 |
| RSI3_UNIFORM | 11 | 6 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 2/12 | 384 |
| RSI3_UNIFORM | 22 | 6 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 1/12 | 375 |
| RSI3_UNIFORM | 33 | 6 | 6 | 6 | 6 | 7 | 7 | 7 | 7 | 1/12 | 369 |

The six tasks every arm solves in generation 1: bool-identify-k (k=1),
caesar-cipher-k-modulo-n (k=0,n=3), (k=1,n=2), (k=2,n=2), (k=5,n=5), and
prepend-k (k=0). RSI3_UNIFORM adds index-k (k=3) in generation 5 on every seed,
at rank 273 of the prior enumeration (window start 231 + 42 candidates).

## Means over seeds

| Arm | TRAIN g1 | TRAIN g8 | VALIDATION g8 | CPU s per run | CPU vs RSI2 |
| --- | --- | --- | --- | --- | --- |
| RSI2 | 6.00 | 6.00 | 1.67 | 241 | 1.00× |
| RSI3 | 6.00 | 6.00 | 1.67 | 419 | 1.74× |
| RSI3_NO_REPLAY | 6.00 | 6.00 | 1.67 | 417 | 1.73× |
| RSI3_NO_GENESIS | 6.00 | 6.00 | 1.67 | 367 | 1.52× |
| RSI3_UNIFORM | 6.00 | 7.00 | 1.33 | 376 | 1.56× |

## Predictions scored

| Prediction | Registered | Observed | Score |
| --- | --- | --- | --- |
| RSI2 TRAIN g8 | 6 (5–7) | 6 | hit |
| RSI3 TRAIN g8 | 8 (7–10) | 6 | **miss** |
| RSI3_NO_REPLAY TRAIN g8 | 8 (7–9) | 6 | **miss** |
| RSI3_NO_GENESIS TRAIN g8 | 8 (7–9) | 6 | **miss** |
| RSI3_UNIFORM TRAIN g8 | 8 (7–9) | 7 | in range, point miss by 1 |
| VALIDATION g8, every arm | 1–2 | 1–2 on every run | hit |
| C1 RSI3 > RSI2 (TRAIN) | PASS | FAIL (6 vs 6 ×3) | **miss** |
| C2 RSI3 > RSI3_UNIFORM | FAIL | FAIL (6 vs 7 ×3) | hit |
| C3 RSI3 > RSI3_NO_REPLAY | FAIL | FAIL (6 vs 6 ×3) | hit |
| C4 RSI3 > RSI3_NO_GENESIS | FAIL | FAIL (6 vs 6 ×3) | hit |
| C5 RSI3 > RSI2 (VALIDATION) | FAIL | FAIL (2/1/2 vs 2/1/2) | hit |
| M1 RSI2 wake share on still-unsolved tasks | ≥ 85% | 99.1% (46,080 of 46,498) | hit |
| M2 RSI3_UNIFORM deepest position | ≥ 300 | 308 | hit |
| M3 a genesis pathway produces a verified solve | yes, ≥ 1 seed | no seed | **miss** |
| M4 verifier rejections per RSI3 run | 1–10 | 0, 0, 0 | **miss** |
| M5 integrator skips per RSI3 run | 0–5 | 0, 0, 0 | hit (mechanism never received input) |
| M6 RSI3 CPU relative to RSI2 | ≥ 1.3× | 1.74× | hit |

The expected shape — about +2 TRAIN tasks from resumption, learned components
adding 0–1 — was wrong in both directions: resumption gave +1, and the learned
controller cancelled it.

## Why the learned controller lost to an even split

The numbers below are for RSI3 seed 11; seeds 22 and 33 differ by at most a
few windows (RSI3_UNIFORM's trajectory is identical on all three seeds, since
it uses no seeded choice before RSI-2's sleep).

1. **The verifier gave almost no signal to learn from.** Memory received six
   positive labels in the whole run, all in generation 1, all at depth 0 or 32,
   all from the easiest tasks. Generations 2–8 produced no positive and no
   rejection (a public match that fails hidden examples never occurred). The
   value model was refit eight times on the same six positives.
2. **With a base rate near 1%, the exploration term decided allocation.** A
   verified solve occurred in 6 of 581 windows (1.0%). The UCB bonus,
   0.3 × √(log(1 + N) / (1 + n)), is still 0.23 for a slot tried ten times at
   N = 581. Allocation spread over 108 slots (30 unsolved tasks × prior,
   recognized, and two analog pathways); in generations 2–8, 47% of the 504
   windows started at depth 0. The per-slot probabilities the value model
   produced were not logged, so this point rests on the base rate and the
   observed allocation, not on the model's outputs.
3. **Breadth starved depth.** The one task within reach sits at rank 273 of the
   prior enumeration. RSI3 searched that task's prior pathway to depth 128
   (96 on seed 33); RSI3_NO_GENESIS, with fewer slots, reached 224–256. Neither
   reached 273. The uniform split, which spends every candidate on one pathway
   per task, reached it in generation 5.
4. **The recognized pathway cannot resume.** RSI-2 refits the recognition model
   every generation, so the conditioned grammar's fingerprint changes every
   generation and its search restarts at depth 0. It received 5,344 of 16,128
   candidates in generations 2–8 (8,992 without genesis): re-searching shallow
   prefixes under a slightly different order.
5. **Genesis added slots, not solves.** Six analog pathways were created and
   five were woken; they received 7,232 candidates in generations 2–8 and
   produced no verified solve on any seed. This repeats the toy study's growth
   finding at program-synthesis scale: adding pathways is not automatically a
   gain, and here it diluted depth.
6. **Replay could not matter without signal.** RSI3_NO_REPLAY's value model had
   zero positives after generation 1 and fell back to its Laplace prior;
   allocation was nearly identical because the exploration term dominated in
   both arms. C3's tie is a statement about this signal regime, not evidence
   against replay in general.

## What did work, and what was never exercised

- **Resumption** (a hard memory rule, no learning): the only source of gain.
  It reached rank 308 and solved index-k (k=3) on every seed.
- **RSI-2's waste is replicated exactly**: 99.1% of RSI-2's wake candidates went
  to tasks it left unsolved, the same figure as `rsi2/research/FAILURE_ANALYSIS.md`.
- **Mechanics verified by test**: windowed search equals `rsi2.search.solve`;
  dormant pathways hold no search state until woken; a grammar change discards
  the frontier; forged, tampered, or self-reported receipts are rejected; no
  module but the verifier reads hidden examples.
- **The binding integrator was never exercised**: with zero verifier rejections
  in all 12 RSI-3 runs, it had nothing to bind against. Its value is unmeasured.

## Where improvement stopped

| Arm | Last new TRAIN best | Flat from |
| --- | --- | --- |
| RSI2, RSI3, RSI3_NO_REPLAY, RSI3_NO_GENESIS | g1 | g1 |
| RSI3_UNIFORM | g5 | g5 |

After RSI3_UNIFORM's generation-5 solve, the refit prior changed the
enumeration order, all frontiers restarted, and the remaining three
generations reached depth 240 without another solve.

## Open problems, as target properties with criteria

1. **Allocation that does not lose to an even split under sparse
   verification.** Criterion: a learned arm's TRAIN count ≥ RSI3_UNIFORM's on
   every seed at the same budget. Measured gap: −1 on every seed.
2. **Resumption that survives a grammar change.** A program that failed the
   public examples fails them under any enumeration order, so the set of
   already-failed programs remains valid knowledge when the order changes;
   this package discards it with the frontier. Criterion: after a grammar
   change, no previously failed program is charged again, verified by test,
   and the post-change search reaches past the pre-change depth within one
   generation.
3. **A verification signal denser than one bit per solved task.** Criterion: at
   least one positive or rejection per generation reaches memory in
   generations 2–8 on every seed, from the frozen verifier only.

## Scope and limits

36 TRAIN and 12 VALIDATION tasks of RSI-2's frozen 60-task DreamCoder subset;
B_wake = B_eval = 64; RSI-2's search limits (AST size ≤ 12, 20,000 expansions,
2,000 steps); constant-zero heuristic in every arm. TEST was not opened.
Hidden-example verification establishes agreement on those examples, not
semantic equivalence. Results apply only to these tasks, budgets, and seeds.
No claim of recursive self-improvement is made: no arm improved the procedure
that improves it, and the learned components did not improve task capability.
