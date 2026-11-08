# Real grammar-reachable finite-probe collision: synthetic three-arm result

**Date:** 2026-11-08 UTC  
**Scope:** synthetic development tasks only; not TRAIN/VALIDATION/TEST or RSI-4 judge pools.  
**Pre-registration:** [b40784d](https://github.com/sunghunkwag/rsi-metaforge-core/commit/b40784d5a2e203ad2998c05a7021e6a9eeecfb3f) committed before the experiment driver and CI.  
**Source parent:** PR #50 at `30d32cfe643575953af479d3ef773f85db225f78`.  
**Executed source:** `92fc88e06dd3d3b2ba51feb4047635579939fcb7`.  
**CI:** [Actions run 42439748881](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42439748881), Python 3.11, **30/30 targeted and existing regression tests passed**.  
**Raw data:** [GitHub Actions artifact grammar-collision-synthetic](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42439748881) (14-day retention); extracted `grammar-collision.json` SHA-256 `fadd3b80a5ad99dc811bcd1e1cc46a4c2c965060081033824455120427c15cb3`.  
**Permanent aggregate:** `rsi3/grammar_collision_summary_20261108.json`.

## Measured outcomes

The default RSI-2 grammar admits both ASTs with finite log probability. They are beta-normal, well typed, distinct, and of sizes 12 (rejected) and 2 (correct), within the registered `max_size=12`. Both match all 10 public examples and produce identical **actual, unmocked** behavior on the integrator's 10 finite probes. A separate synthetic oracle generator produces 12 disjoint checks per task and detects the wrong branch.

| Arm | Correct candidates falsely suppressed | Correct candidates accepted | Verifier queries | Public logical evaluations | Probe interpreter calls | Total CPU seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| signature (legacy) | **12/12** | **0/12** | 12 | 24 | 240 | 0.009163 |
| exact (PR #50) | **0/12** | **12/12** | 24 | 24 | 120 | 0.009342 |
| none (null control) | **0/12** | **12/12** | 24 | 24 | 120 | 0.009228 |

Four grammar-default trigger constants `[-1,0,1,2]` crossed with seeds `[11,22,33]` gave 12 constructed witnesses. The independent synthetic oracle checks include all integers -3..3 and five separately seeded samples in 30..49; therefore the branch trigger is deliberately covered. The actual signature probes lie in 11..20. The rejected AST receives an authentic negative receipt in generation 1; the correct AST appears in generation 2, preserving the frozen one-query-per-task-per-generation cap.

**P1, P2, P3 passed for these deliberately constructed witnesses.** This is a concrete counterexample to the universal assumption that equal finite-probe signatures imply interchangeable verifier outcomes. The exact-rejection mode avoids this specific false suppression, while spending an additional verification query per constructed task.

## Limitations and negative evidence

- This is an **existence proof**, not an estimate of collision frequency in naturally sampled RSI-3 search. The two candidate ASTs were manually constructed from the existing grammar and injected into a fixed stream. `Grammar.log_probability` establishes grammar reachability but does **not** establish that the enumerator reaches the 12-node candidate within its ordinary `max_expansions` or `B_wake` budget.
- The synthetic oracle was constructed independently of the public/probe inputs but deliberately includes the trigger range. It is **not** an untouched external holdout. No sealed evaluation partitions were opened or used.
- The same 2-second **CPU ceiling** applied to each arm/task; actual CPU consumption was not equalized. Millisecond differences are noise, not speedup evidence.
- The earlier [PR #50 TRAIN-only pilot](https://github.com/sunghunkwag/rsi-metaforge-core/blob/research/exact-rejection-20261108/rsi3/RESULTS_EXACT_REJECTION_PILOT.md) remains a null result: 5/36 then 6/36 for both signature and exact on seeds 11/22, with zero negative receipts and zero skips. The synthetic witness does not revise that observation.
- The exact digest is not semantic equivalence. If referenced library definitions change, a term-only digest may not safely identify the same executable program; this experiment uses an empty library.
- No demonstrated improvement in TRAIN solving, held-out transfer, forgetting, online RL, recursive self-improvement, or AGI.

## Next falsifiable step

Freeze a *natural* typed-enumerator collision-rate protocol on synthetic development tasks: run actual `enumerate_programs` with unchanged `max_size=12`, `max_expansions=20000`, equal logical/CPU budgets, and report whether a rejected and a correct public-matching program with equal unmocked probe signatures are **both actually visited**. Compare signature/exact/no-suppression without choosing seeds or thresholds after looking at results. If no such pair is encountered, report a null result and the measured search coverage rather than relaxing budgets post hoc.

Keep PR #51 draft and isolated from the sealed RSI-4 phases and PRs #48/#49/#50.
