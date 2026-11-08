# Worst-domain transfer gate: new-family evidence, 2026-11-08

## Frozen sources and intellectual background
- Original historical VM (immutable): https://github.com/sunghunkwag/rsi-metaforge-core/commit/3cfc329eca17a08e1a1565064b61a5bd4a1dd520
- Previous typed-sampling research (frozen dependency, not modified): https://github.com/sunghunkwag/rsi-metaforge-core/commit/1d0a54d408378fa26b462ffa3bad66c8e98c0ea6
- New source: https://github.com/sunghunkwag/rsi-metaforge-core/blob/research/worst-domain-transfer-gate-20261108/research/worst_domain_transfer_gate_20261108.py
- Reproducible CI, complete per-seed JSON artifact: https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42468205806
- Conceptual motivation, **not code replication**: Sagawa et al., group distributionally robust optimization, https://arxiv.org/abs/1911.08731 ; Xie et al., DoReMi, https://arxiv.org/abs/2305.10429 .
- Limitation on arbitrary universal improvement: Wolpert and Macready, "No Free Lunch Theorems for Optimization", https://doi.org/10.1109/4235.585893 .

## Research question
Does retaining a guaranteed fraction of *type-valid uniform proposals* while using token weights learned from new support task families yield a **strict non-regressing improvement on each observed development domain**, and independently reproduce on fresh audit families? We preregister strict per-domain thresholds: average gain cannot compensate for a lost domain.

This is research-only. No change was made to production search, its frozen verifier, archival artifacts, RSI-4 Phase 1, TEST/J pools, or collaborators' PRs #48-53.

## Design, split and budgets
- Original 34-token typed-stack VM; existing frozen typed sampler restricts programs to 2-4 postfix operations. Every candidate is statically type-valid; this is **one integer-list program-synthesis substrate**, not every domain of AI.
- Three **new support tasks**: minimum, sum of prefix maxima, sum of squares, with input seed 317. The successful support programs were, respectively, `INPUT SORTL HEAD`, `INPUT SCAN_MAX SORTL RED_ADD`, `INPUT INPUT ZMUL RED_ADD`. Credit only the first train-exact support program for each task. These task names are disjoint from PR #53's support/development/audit task names.
- Support training cap 768 proposals per task, maximum 2,304 proposals; **actually executed 1,230 proposals** (244 minimum, 268 prefix max, 718 squares), 24,600 charged input-probe slots. This is an **extra training expense**, excluded from each inference arm's logical budget and separately accounted for.
- Frozen learned weights: `INPUT=6, SORTL=4, RED_ADD=4, HEAD=2.5, SCAN_MAX=2.5, ZMUL=2.5`. All unmentioned tokens have weight 1.
- Six arms: typed uniform, explicit uniform null, fully learned, and fixed deterministic quota mixtures retaining 75%, 50%, or 25% uniform samples.
- Development tasks (6): second-smallest, second-from-end, drop-two length, sorted suffix sum, sum of prefix sums, maximum prefix sum. Input seed 707.
- **New, single-use independent audit tasks** (8): sum after two drops, reverse odd/even sum, minimum/maximum after drop, sum of prefix maxima after drop, sum of sorted prefix sums, minimum prefix sum. Input seed 909. These audit labels are never used to choose a mixture.
- Additional support retention evaluation on support training families, explicitly **not independent forgetting evidence**.
- Fixed paired seeds 401 through 464 inclusive (64). All arms spend 20 candidate evaluations per task-seed, each charged for 20 training-input probes. Therefore each development arm has 7,680 charged candidate evaluations and 153,600 charged probe slots; each audit arm has 10,240 and 204,800 respectively; each support-retention arm has 3,840 and 76,800.
- 24 separately generated distribution-shift examples: lengths 0, 1, 2, 5, 8, 13, 21 and 34 (3 per length), with values from -19 to 31. These were not used to fit the weights.
- CPU used per arm is measured, but CPU budgets are **not exactly matched**. Fixed CPU ceiling 0.5 seconds per task-seed-arm, checked after execution; no ceiling breaches.

## Preregistered decision rule
On development only, accept a candidate mixture when:
1. Total train-exact solved task/seed cases improve by **at least +4** over typed uniform.
2. **Every development task** has nonnegative train-exact delta.
3. **Every development task** also has nonnegative independent shift delta.
4. Both logical resource counts match and the CPU ceiling is satisfied.

If more than one arm passes, select the candidate with highest minimum task delta, then highest total gain, then strongest uniform floor. **Selection happens before executing independent audit tasks.**

The chosen policy, if any, must *then* replicate a positive total audit gain with **zero audit task regressions (train and shift)** and no support-retention regressions; otherwise production eligible remains false. This empirical gate does not mathematically guarantee generalization beyond the sampled tasks.

## Reproduced empirical results

| Arm | Development TRAIN (384 cases) | Development shifted (384 cases) | Independent audit TRAIN (512 cases) | Audit shifted (512 cases) |
|---|---:|---:|---:|---:|
| Typed uniform | 67 | 12 | 74 | 13 |
| Typed explicit-uniform null | 67 | 12 | 74 | 13 |
| Typed learned | **91** | 26 | **83** | 21 |
| 75% uniform floor | 77 | 18 | 76 | 16 |
| 50% uniform floor | 90 | **27** | 76 | 17 |
| 25% uniform floor | 88 | 24 | 78 | 16 |

Uniform and explicit uniform null are asserted exactly equal on selected programs, candidate counts, and results. All six arms have identical counted proposal/probe budgets per stage.

Important development learned-versus-uniform per-task deltas: maximum-prefix-sum +10, second-from-end **-5**, second-smallest +2, sorted-trim-sum +3, sum of prefix sums +14, drop-two length 0. Despite **+24 average gain**, there is a meaningful domain regression and a shifted-input regression on maximum-prefix-sum (-1).

The most conservative 75% uniform mixture improved total development solved cases from 67 to 77, but still dropped second-from-end from 5 to 4 and reduced shifted-input success on that task by one. **Every proposed mixture failed the zero-regression development criterion.** Thus `development_selection.selected = null`, `independent_audit_gate.pass = false`, and `production_eligible = false`.

**High-value counterexample to training-only verification:** on the fresh independent audit's `minimum_prefix_sum` task, learned weights yielded **64/64 TRAIN exact** but only **2/64 shifted-input pass**. The uniform baseline yielded 61/64 TRAIN exact but 0/64 shifted-input pass. This is striking *both as a distribution shift failure and as a warning about apparent complete success on a narrow training distribution*. The first train-exact program returned by the sampler is what is checked for shift, as in the frozen prior protocol.

Other independent audit regressions: learned weights reduced `sum_after_two_drops` from 1 to 0 and `sum_prefix_max_after_drop` from 2 to 1. Some other audit tasks improved, but **we did not select a candidate**, so audit results cannot retroactively justify adoption.

## Failures and limitations
- Strict uniform quotas do not guarantee the uniform baseline's successful programs are sampled within the same finite proposal budget; retaining 75% of uniform proposals still allows regressions. This is expected and empirically observed.
- Not a proof of "all-domain" improvement; the only substrate is the historical integer-list VM, with an intentionally restricted four-token grammar. Several tasks remain unsolved by all arms.
- Support matches are train-exact, not formal semantic proofs. Historical VM operations are used for execution, and shifted inputs expose spurious matches.
- Distinct seed/task observations are not necessarily independent samples from an externally defined real-world task distribution. No statistical universal generalization claim is warranted.
- Candidate/probe *opportunities* are equal, but actual executed VM instructions and CPU time differ; support-training cost is incremental.
- The independent audit is an evaluation only, not a tuning pool. It is now **spent**. A future revision must use fresh independent task families and new preregistration, and should include at least one genuinely different problem substrate (e.g. strings or graphs) before claiming cross-substrate transfer.

## Next falsifiable hypothesis
A **task-conditioned, uncertainty-aware proposal policy** could avoid global over-weighting of operations while preserving a uniform prior. Fit task-conditioning on fresh support-only data, define a worst-group and shifted-distribution guard on new development families, then validate once on never-before-used independent suites across at least two different substrates. A positive average without preserved worst-group and OOD performance is **failure**, not an RSI breakthrough.

The experimental branch is deliberately unmerged; **no general RSI, AGI or universal improvement is claimed**.
