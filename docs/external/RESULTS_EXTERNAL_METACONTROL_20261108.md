> Moved here from `research/RESULTS_EXTERNAL_METACONTROL_20261108.md` on branch
> `research/external-preregistered-metacontrol-20261108` (commit `b0378eb`), with its two
> preregistration files, by RSI-5's Step 0 (`rsi5/OWNER_DIRECTIVE.md` §10). The 72 MB raw
> file it links stays on that branch's history at
> `research/results/external_metacontrol_raw.json` (commit `210487d`) and is not copied.
> Nothing below this line is changed.

# External DreamCoder multi-generation meta-controller: preregistered negative result

Date: 2026-11-08.
**Verdict:** the hypothesis failed its locked gate. No general RSI result.

## Provenance and commitment chronology
1. Frozen external DreamCoder source: `ellisk42/ec` commit `cb0e63f5c33cd2de360b791038b0f5272750270e`, upstream `data/list_tasks.json`, Git blob `2816d1ee51ff2f523704c1930d8736eb99711036`. The unchanged source was already committed in `rsi2/data/source_list_tasks.json` on main.
2. Protected old train/validation/TEST split exclusions: `rsi2/data/split_manifest.json`, blob `afac5b3f2dc346027caaba36f308f2b1e078ebda`. No prior TEST/J labels, RSI-4 Phase 1 data or unmerged PR source were loaded into this experiment.
3. **Before code/first run:** external task manifest in commit `ff193281d57cfaa6e1a56736d41d80fba950f8fd`, blob `c27b1c6431ab9d836c94f9ddc66269fd4216a1e0`. It fixes 16 support task IDs, 15 development IDs and 19 single-use independent audit IDs. Published audit operation families were never used by the development tasks.
4. **Before code/first run:** predictions and gates in commit `a576be9cd4831f9ec9c29a70ba98b237dfec15af` and a stricter unseen-family generation-curve addendum in `a70e1a2d54346ac3eeec700708e353698227dd30`.
5. Runner implementation committed in `2aeb0975f649d593d5fca80f7cdf8f4a479ac8bf`; no import from unmerged PRs.
6. The first run `42472348181` failed on an unseen-key lookup at the **beginning of support generation 1**, before any audit data were evaluated. Only that bug was corrected, with tests for all search actions (`96551abf275be240212b857bfed7fd19c3ac3699`). There was **no gate/hypothesis/manifest revision**. Corrected preflight CI succeeded.
7. **First complete one-shot study:** [Actions run 42472451356](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42472451356). It completed and automatically committed the **entire raw JSON**, including per-candidate public scores, per-case results, policy snapshots, CPU counters, paired wins/losses/ties and all 3 audit checkpoints, in commit **`210487d92f9f8150625d3084fe8d1cf2bbdb5c99`**.

[Full raw committed results](https://github.com/sunghunkwag/rsi-metaforge-core/blob/210487d92f9f8150625d3084fe8d1cf2bbdb5c99/research/results/external_metacontrol_raw.json) (about 72 MB; GitHub issued a large-file warning, but the commit succeeded). CI artifacts are only a backup, not the primary evidence.

## Prespecified question and controls
Hypothesis: learning the algorithm's *proposal-action selection probabilities* across **three support generations** should transfer to unseen external DreamCoder task families better than controls, showing increasing gains over time.

Seven arms:
- `dedup_uniform`: simple candidate deduplication baseline.
- `frozen_mutation`: fixed parameter-mutation heuristic, the strongest simple fixed baseline in this run.
- `untrained_no_memory`: no learned memory/controller weights.
- `memory_wiped`: updates after each support generation but resets before the next.
- `one_generation_equal_compute`: pools the same support-feedback/evaluation budget and updates once rather than retaining intermediate policy updates.
- `adaptive_persistent`: persistent reward-weighted action probabilities updated only from external support tasks.
- `negative_inverted`: deliberately inverted-feedback control expected to fail.

Every arm was **allowed to lose**: no incumbent precedence, no superset protection, and no result-driven selection of a convenient audit candidate. All candidates were actually scored, including failures. Candidate programs were limited to a simple task-family-and-integer-parameter DSL; the controller changes proposal-action probabilities and does NOT rewrite source code.

Forty independent seed trajectories, 3 support generations, 19 externally frozen single-use audit tasks, and 32 freshly generated shifted inputs of varied lengths per audit task/seed. Each audit generation/arm evaluates 19 × 40 = **760** task/seed cases, 48 candidate programs per case, **36,480 candidate evaluations, 437,760 actual public candidate VM calls, and 24,320 shifted verification calls**. The same audit tasks are evaluated at three **snapshotted, frozen** checkpoints without feeding any audit result back into training. Overlapping tasks within one seed are treated as a cluster, not independent replications.

Task semantics were checked against 465 original external support/development examples before testing and 285 original external audit examples **only after all controller snapshots were frozen**. There were no mismatches.

## Final independent audit: checkpoint 3 (760 cases per arm)
| Arm | TRAIN-perfect | Pass all 32 shifted inputs | Spurious fits |
|---|---:|---:|---:|
| Deduplicated uniform | 658 | 658 | 0 |
| **Frozen parameter mutation** | **690** | **690** | 0 |
| Untrained / no memory | 657 | 657 | 0 |
| Memory wiped every generation | 657 | 657 | 0 |
| Equal-total-compute, one update | 652 | 652 | 0 |
| **Persistent adaptive controller** | **649** | **649** | 0 |
| Inverted-feedback negative control | 650 | 650 | 0 |

Spurious-fit rate = train-exact solutions failing any of the 32 OOD inputs divided by train-exact solutions; **0/649** for adaptive and zero for other arms in this finite check. This does not establish semantic correctness outside the tested generated inputs.

## Paired per-case evidence: adaptive persistent vs each baseline
All comparisons are on **760 identical task/seed cases**, with 40 independent seed trajectories used as bootstrap clusters (2,000 bootstrap resamples, seed 909113).

| Compared baseline | Adaptive wins | Adaptive losses | Ties | Absolute OOD effect | Paired cluster bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| Deduplicated uniform | 74 | 83 | 603 | -1.18 pp | [-4.61, +1.97] pp |
| **Frozen mutation** | **38** | **79** | **643** | **-5.39 pp** | **[-8.82, -2.11] pp** |
| Untrained no-memory | 71 | 79 | 610 | -1.05 pp | [-4.47, +2.11] pp |
| Memory wiped | 21 | 29 | 710 | -1.05 pp | [-3.03, +1.05] pp |
| Equal-total-compute one update | 20 | 23 | 717 | -0.39 pp | [-2.11, +1.45] pp |
| Inverted-feedback control | 47 | 48 | 665 | -0.13 pp | [-3.16, +2.76] pp |

The independent 95% CI against the strongest fixed baseline is entirely **negative**, which is inconsistent with the preregistered +8 percentage-point primary expectation.

## Secondary paired McNemar diagnostics (postprocessing only)

As preregistered, we compute **two-sided exact McNemar/binomial p-values** from the already recorded discordant paired case counts (`wins`, `losses`), without any rerun, policy selection or changed gate. Because multiple tasks belong to the same seed trajectory, these per-case p-values can overstate independent evidence; the **seed-cluster bootstrap confidence intervals above are primary**.

| Comparator | Discordant cases | Two-sided exact McNemar p |
|---|---:|---:|
| Deduplicated uniform | 157 | 0.523301 |
| Strongest frozen mutation | 117 | **0.0001893** |
| Untrained/no memory | 150 | 0.567775 |
| Memory wiped | 50 | 0.322236 |
| Equal-total-compute one update | 43 | 0.760792 |
| Inverted-feedback control | 95 | 1.000000 |

The fixed-mutation result is a statistically clear negative comparison even at this secondary diagnostic level. No p-value is used to alter the preregistered binary decision.


## Previously unseen audit families, across frozen checkpoints
Adaptive-minus-strongest-fixed OOD margin at the **same** external audit family tasks and common paired random tapes:

- Generation 1: **-5.92 percentage points**
- Generation 2: **-6.32 percentage points**
- Generation 3: **-5.39 percentage points**

The curve is **not nondecreasing** and its final-minus-initial improvement is approximately +0.53 pp, below the preregistered +5 pp threshold. The model does not exhibit the hypothesized improving advantage over the frozen fixed mutation policy.

The strict independent-family nonregression criterion also failed. All per-case and task-family results are retained in the raw JSON. No audit result was used for retuning or a second full audit.

## Actual CPU and matching
Each final audit arm completed **36,480** candidate evaluations, **437,760** real public VM calls and **24,320** held-out verification VM calls, and all individual cases satisfied the identical CPU ceiling.

Measured total audit process CPU:
- Fixed mutation: **4.154799 seconds**
- Persistent adaptive: **2.779268 seconds**
- Deduplicated uniform: **1.512427 seconds**
- Memory wiped: **2.752840 seconds**
- Equal-total-compute one update: **2.747904 seconds**
- Untrained no-memory: **2.660475 seconds**
- Inverted feedback: **2.688027 seconds**

This was **not an equal-CPU-consumption experiment**: fixed mutation consumed about 49.5% more process CPU than adaptive despite identical VM calls. The preregistered ±10% CPU parity guard therefore failed, even though candidate and real VM-call budgets matched. No stronger compute-efficiency conclusion is claimed.

## Locked gates and outcome
`preregistered_success = false`. The runner explicitly recorded:
- `min_eight_pp_over_strongest_fixed = false`
- `min_five_pp_over_every_memory_and_total_compute_control = false`
- `paired_seed_cluster_bootstrap_lower95_positive = false`
- `no_negative_external_audit_family = false`
- `positive_unseen_family_multigeneration_growth = false`
- `actual_cpu_within_ten_percent = false`
- `inverted_feedback_negative_control_fails = true`
- `no_cpu_cap_breach = true`
- `evaluations_matched = true`

**Conclusion:** the learning-to-search hypothesis failed this externally sourced, preregistered test. The strongest fixed heuristic won. All audit tasks and checkpoint results are **spent** and must not be reused for future tuning, even if another candidate policy is proposed.

Even a future successful version would only demonstrate a bounded optimizer meta-policy gain. This study contains no recursive code rewriting, general AGI, formal global proof of no forgetting, or universal all-domain improvement. Keep any research PR as Draft; preserve `main`, protected verifier and archived evidence unchanged.

## Further work (not a post-hoc redo)
A new preregistration must select an entirely different **external** corpus or disjoint externally frozen FRESH partitions, with new hash-pinned task manifest and seeds, prior to new code or experiments. Compare learned search policies against fixed heuristics under equal **wall/CPU and evaluation budgets**, not just equal task counts. Include task-family-level distribution shift, confidence intervals clustered by truly independent trajectories, and a negative control that remains capable of winning by chance. Do not reuse this spent audit.
