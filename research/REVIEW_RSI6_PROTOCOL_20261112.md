# RSI-6 protocol feasibility and integrity review — 2026-11-12

**Classification:** independent source-only design review with one bounded, executable arithmetic check. **Not** an RSI experiment, benchmark audit, external-verifier run, adoption decision, or work-order approval.

## Source verification

- Main base: `c4f0a8627a1c9f37dd3aa6291b0eee0c78648210`.
- Reviewed unmerged [PR #58](https://github.com/sunghunkwag/rsi-metaforge-core/pull/58) head: `355fc090d390c29933e481777d8d2a2353cf5ff4`.
- RSI-6 protocol blob: `7949aa76dd0b8c821c0389bb8d14301508273c65`.
- Draft WO-5 blob: `4fc6770e136278eb7f5cb652bbc7ed49556c258c`.
- Owner directive blob: `1f478f2db1c52d57bd7d47db390ade6bef0ec9c5`.
- Outer-loop constitution blob: `1257eb27993d0489311354690132d1e6e62bf674`.
- The reviewed work order ends in a blank `APPROVED:` line. No worker execution of WO-5 is authorized.
- No code or data from PR #58 was imported into this main-based branch. The reviewed documents were read for design review only.

## Pre-registered, executable feasibility result

The preregistration was committed first (`research/PREREG_RSI6_PROTOCOL_FEASIBILITY_20261112.md`), before the checker and its run. The Python standard-library checker was run once, with four unit tests passing locally. Its complete raw JSON is committed at `research/results/protocol_feasibility_raw_20261112.json`.

| Distinct admitted categories, n | Possible independent adoption rounds, floor((n - 6) / 2) |
| ---: | ---: |
| 7 | 0 |
| 8 | 1 |
| 9 | 1 |
| 10 | 2 |
| 11 | 2 |
| 12 | 3 |

**Finding F1 (blocking for a multi-generation claim):** the protocol currently names seven candidate categories, but its own role allocation consumes two source categories, two fresh adoption categories per round, three sealed targets, and at least one reserve. Two independent rounds therefore require **at least 10 genuinely distinct, admitted categories**, three more than are currently listed. Additional datasets from an already counted category do not resolve this. The draft may conduct a source-only pilot after explicit approval, but cannot claim a two-round RSI experiment from seven categories.

**Finding F2 (seed-count clarification):** WO-5 P10 requires the estimated seed count for 80% power to be **at most 10**; the user's independent-trajectory requirement is **at least 40 where feasible**. Their numerical difference is 30. Importantly, P10 is a *power-feasibility criterion*, **not** a cap on the number of seeds actually run. Therefore the arithmetic does not prove a shortage of 30 executed seeds. The protocol should explicitly commit to at least 40 paired trajectories when feasible and report a justified resource/power exception otherwise.

All five preregistered static arithmetic checks passed. This is a successful **consistency computation**, not evidence of learner improvement. Exact arithmetic has no sampling uncertainty: significance and 95% confidence intervals are not applicable. Measured process CPU for the checker was approximately `0.000008893` seconds, under the 2-second cap. Candidate evaluations: **0**; interpreter calls: **0**; audit tasks read: **0**. No #50–57 audit was reused.

## Further protocol findings (review, not empirical outcomes)

**F3 — Identity-invariance gate is not an equivalence test (high).** WO-5 P4 accepts a scrambled-versus-unscrambled mean difference `within two standard errors`. With noisy scores, a large standard error makes large identity effects pass. Replace it with a predeclared *equivalence margin* and a paired, category-blocked confidence interval wholly inside that margin; require deterministic evaluator isomorphism separately. A nonsignificant difference is not evidence of invariance.

**F4 — Train/fresh directionality is not a correctness invariant (medium).** WO-5 P7 treats `gain(training) < gain(fresh)` as a split/scoring error. That inequality can arise legitimately if fresh instances are easier or if the learner generalizes unusually well. Pre-register stratification by size/difficulty, report both gains, and flag potential leakage by direct identity/provenance tests, not by the sign of a difference alone.

**F5 — CPU overmatching and heterogeneous work units (high).** Protocol section 6 allows a nonrecursive baseline to receive *at least* the recursive arm's CPU and scores the first budget step that reaches it. An oversized step may be a large compute imbalance; WO-5 P8's within-environment CV of CPU per work unit does not establish cross-arm equality. Pre-register a tight symmetric tolerance (for example ±10%), report actual per-arm CPU, wall, evaluator calls, generator CPU, support-learning and verification costs, and mark a comparison **void** if parity fails. Match paired runs on the same host under interleaved scheduling.

**F6 — Statistical independence is partly at the category level (high).** Forty seeds on only three sealed target categories yield forty paired trajectories but do not yield forty independent environment categories. Report seed-clustered intervals and a category-blocked sensitivity analysis, all category-level regressions, and explicitly limit any claim about generality to the observed substrates. Do not bootstrap task/seed rows as independent observations.

**F7 — Independent shifted-instance requirement needs a mechanical gate (medium).** The protocol distinguishes training and fresh instances but does not explicitly require at least 24 independent, varied-size shifted inputs *per evaluated task*. Specify the minimum, provenance, non-overlap checks, and spurious-fit denominator before any audit.

**F8 — Forgetting and mechanism-versus-memory separation need explicit replay (medium).** The plan mentions regressions and empty-memory version comparisons, but does not require a fixed, independently verified replay audit of capabilities lost across generations. Add a separately scored replay of previously acquired capabilities and paired comparisons with skills-only, wiped, frozen-improver, and single-generation matched-compute arms. No adaptation from replay outcomes after the audit.

**F9 — The executable gate is unapproved (blocking for WO-5).** The constitution and RSI-6 governance require the Owner's exact committed approval token for WO-5. The token is blank. This review did **not** execute the learner, any environment adapter, any external verifier, or any target/reserve data. A recurring research request does not silently fill the approval line.

## Required corrections before the next RSI-6 experiment

First, vet and independently audit at least ten distinct external categories, or declare the multi-round design infeasible without opening the sealed targets. Second, revise P4/P7/P8/P10 and add explicit shifted-instance, forgetting, parity and category-clustered reporting gates before any experimental preregistration. Third, obtain the Owner's exact work-order approval and repeat the baseline suite on a quiet machine as WO-5 requires. Only then implement the shared learner and evaluate it on external, genuinely heterogeneous environments.

## Reproduction and limits

From a checkout of this review branch:

```sh
python -m unittest research.test_protocol_feasibility_20261112 -v
python -m research.protocol_feasibility_20261112 --output /tmp/protocol_feasibility.json
```

The raw JSON preserves the single local run; subsequent executions are reproducibility checks, not additional independent observations. The reviewed PR #58 is concurrent unmerged work and may change; re-check its head and document blobs before applying any suggested correction. No README or source from that PR was copied into this branch.

**Result:** a falsifiable design feasibility obstacle was demonstrated, but no RSI capability-acquisition or recursive-learning result was obtained. All previously spent audit tasks remain spent.
