# Preregistration: RSI-6 protocol feasibility review (2026-11-12)

## Scope and source pins

This is a **static, deterministic protocol-feasibility review**, not an RSI performance experiment or an audit-task evaluation. No benchmark tasks, hidden instances, verifiers, or unmerged PR code will be executed or imported.

- Main base: `c4f0a8627a1c9f37dd3aa6291b0eee0c78648210`.
- Reviewed draft PR: #58, head `355fc090d390c29933e481777d8d2a2353cf5ff4` (review-only, not a code dependency).
- Reviewed protocol document blob: `7949aa76dd0b8c821c0389bb8d14301508273c65` (`rsi6/RESEARCH_PLAN.md`).
- Reviewed work order document blob: `4fc6770e136278eb7f5cb652bbc7ed49556c258c` (`docs/work_orders/WO-5_rsi6_build_and_pilot.md`).
- Reviewed Owner directive blob: `1f478f2db1c52d57bd7d47db390ade6bef0ec9c5`.
- Reviewed outer-loop constitution blob: `1257eb27993d0489311354690132d1e6e62bf674`.
- The work order's approval line is blank; no work-order implementation or pilot is authorized by this review.

## Frozen quantitative checks and predictions

The protocol specifies 2 source categories, 2 distinct adoption categories per round, 3 final target categories, and at least 1 reserve category; its stated formula is `G = floor((n - 6) / 2)`. Seven candidate categories are named. For a claim about multiple independent improvement rounds, require at least two rounds.

- P1: At `n=7`, `G=0`, not a multi-generation study.
- P2: At `n=8` and `n=9`, `G=1`; at `n=10`, `G=2`.
- P3: The minimum number of independently admitted categories for two rounds is `10`; the current seven-category proposal is short by `3`.
- P4: The draft pilot's P10 ceiling of `10` seeds is `30` below the requested `40` independent paired seed trajectories. This is a design mismatch, not proof that forty are computationally feasible.
- P5: No empirical significance or confidence interval can be computed from these exact arithmetic checks; record inference as `not_applicable`, not as a positive result.

## Resource limits, stop rules, and exclusions

Run the pure-stdlib arithmetic checker exactly once with the frozen inputs; 0 candidate evaluations, 0 VM/interpreter calls, 0 task reads, no network, and a 2-second process-CPU ceiling. Stop and mark the review stale if any reviewed source blob changes. Record the raw JSON and the executable checker. This review does **not** approve WO-5, open the sealed target categories, retune #57 or #50–56 audit tasks, or support an RSI claim.

A separate narrative design review will inspect non-arithmetic risks: confidence-interval equivalence versus 'within two standard errors', train-vs-fresh directionality, actual CPU matching, forgetting, and clustering by environment category. Those are review findings, not outcomes of this arithmetic test.
