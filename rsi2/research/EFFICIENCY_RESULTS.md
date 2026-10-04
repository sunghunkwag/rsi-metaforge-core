# Evaluation-reuse follow-up

Observed matched-prefix decision: **KEEP**; logical comparison: **EQUAL_OBSERVED_PREFIX**. Full-study equivalence: **UNKNOWN**.

The comparison covers 11 completed paired cycles. It measures saved actual inner task-search candidates and cycle CPU, preserving the original candidate policy and all logical outcomes. It does not establish better solver capability, a better proposal ranker, or recursive self-improvement. Reporting-only audit outcomes are excluded.

## Matched-cycle costs

| Seed | Arm | Cycle | Logical equal | Baseline actual inner candidates | Reuse actual inner candidates | Saved actual inner candidates | Baseline CPU s | Reuse CPU s | Saved CPU s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | original | 1 | True | 2590 | 2590 | 0 | 220.6785 | 242.3291 | -21.6506 |
| 11 | static | 1 | True | 1973 | 925 | 1048 | 940.3992 | 586.1015 | 354.2978 |
| 11 | learned | 1 | True | 1973 | 0 | 1973 | 603.1815 | 9.0895 | 594.0920 |
| 22 | original | 1 | True | 2619 | 2619 | 0 | 107.9230 | 241.3560 | -133.4330 |
| 22 | original | 2 | True | 0 | 0 | 0 | 1.1777 | 8.3108 | -7.1331 |
| 22 | static | 1 | True | 1944 | 909 | 1035 | 605.2730 | 500.7572 | 104.5158 |
| 22 | learned | 1 | True | 1944 | 0 | 1944 | 584.3080 | 8.3133 | 575.9947 |
| 33 | original | 1 | True | 2587 | 2587 | 0 | 213.3988 | 122.3254 | 91.0734 |
| 33 | original | 2 | True | 0 | 0 | 0 | 1.0859 | 9.2806 | -8.1947 |
| 33 | static | 1 | True | 2005 | 958 | 1047 | 891.0181 | 511.8036 | 379.2145 |
| 33 | learned | 1 | True | 2005 | 0 | 2005 | 503.5293 | 9.0070 | 494.5223 |

Matched actual inner candidates: baseline 19640, reuse 10588, saved 9052. Matched cycle CPU saved: 2423.2991 s. Actual inner candidates are differences of each arm's cumulative memory counter between successive matched cycles. Initial TRAIN/wake/dream overhead and later unmatched cycles are excluded from these savings. Negative savings remain visible.

## Secondary actual workload

| Seed | Arm | Cycle | evaluation_steps | heuristic_calls | heuristic_evaluations | heuristic_steps | verification_examples | verification_steps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 11 | original | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 11 | static | 1 | 45450 | 228484 | 343 | 20343 | 9 | 114 |
| 11 | learned | 1 | 252314 | 1015353 | 1773 | 118817 | 10 | 149 |
| 22 | original | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 22 | original | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| 22 | static | 1 | 46523 | 223047 | 341 | 20204 | 14 | 254 |
| 22 | learned | 1 | 249528 | 999995 | 1746 | 116255 | 15 | 289 |
| 33 | original | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 33 | original | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| 33 | static | 1 | 51050 | 209736 | 345 | 20634 | 9 | 114 |
| 33 | learned | 1 | 294599 | 876709 | 1762 | 116231 | 10 | 149 |

These columns are saved actual source assessment operations, not changed logical search outcomes. Selected-result aliases are counted once. They expose interpreter and heuristic work even when a capped search attempts zero complete task candidates. Unknown source telemetry remains unknown rather than zero.

## Coverage

| Seed | Arm | Matched cycles | Completed baseline rows without pair | Reuse-only cycles | Baseline unrun cycles |
| --- | --- | --- | --- | --- | --- |
| 11 | original | [1] | [] | [2, 3] | [2, 3] |
| 11 | static | [1] | [] | [2] | [2, 3] |
| 11 | learned | [1] | [] | [2] | [2, 3] |
| 22 | original | [1, 2] | [] | [3] | [3] |
| 22 | static | [1] | [] | [2] | [2, 3] |
| 22 | learned | [1] | [] | [2] | [2, 3] |
| 33 | original | [1, 2] | [] | [3] | [3] |
| 33 | static | [1] | [] | [2, 3] | [2, 3] |
| 33 | learned | [1] | [] | [2] | [2, 3] |

A retained efficiency rule applies only to the observed matched prefix. No logical equivalence or savings are inferred for unrun or unmatched cycles. An intervention missing a completed baseline row leaves the narrow policy decision UNKNOWN. A partial baseline can support a limited observed-prefix efficiency decision while full-study equivalence remains UNKNOWN.

## Independent verifier evidence

| Verifier | Status | Count | Test identifiers or paths |
| --- | --- | --- | --- |
| exact_reuse | passed | 18 | rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_all_certificate_scope_dependencies_require_new_measurement, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_budget_hit_cannot_hide_a_solution_at_larger_budget, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_certificate_is_only_reused_upwards_not_at_a_smaller_budget, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_completed_failed_space_certificate_equals_direct_higher_budget, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_empty_measurement_has_defined_zero_counts, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_expansion_cap_certificate_is_reused_but_changed_cap_misses, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hidden_list_and_tuple_inputs_and_outputs_cannot_share_scope, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hidden_verifier_failure_never_supplies_a_cross_budget_certificate, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hit_wall_time_and_actual_counters_do_not_copy_historical_work, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_live_multitask_decomposition_equals_original_assessment, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_live_primitive_order_change_can_change_success_and_must_miss, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_partial_hit_and_duplicate_tasks_charge_only_new_task_work, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_public_list_and_tuple_arguments_cannot_share_a_scope, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_recognizer_parameter_changes_invalidate_exact_scope, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_shared_cross_arm_exact_hits_have_independent_actual_counters, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_shared_store_does_not_expose_mutable_report_aliases, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_typed_scope_keys_preserve_nested_containers_and_scalar_types, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_zero_candidate_certificate_records_saved_heuristic_work |
| exhaustion_certificate | passed | 7 | rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_all_certificate_scope_dependencies_require_new_measurement, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_budget_hit_cannot_hide_a_solution_at_larger_budget, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_certificate_is_only_reused_upwards_not_at_a_smaller_budget, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_completed_failed_space_certificate_equals_direct_higher_budget, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_expansion_cap_certificate_is_reused_but_changed_cap_misses, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hidden_verifier_failure_never_supplies_a_cross_budget_certificate, rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_zero_candidate_certificate_records_saved_heuristic_work |

A narrative assertion of safety is insufficient: exact-reuse and exhaustion-certificate checks require supplied passing status, nonempty test identifiers/paths and measured counts. The comparator ignores only the named timing/cache/actual-work telemetry allowlist. Candidate/evaluation/heuristic/verifier logical counts, failure evidence, ASTs, order, coefficients, policy state and online decisions remain exact.

## Eleven intervention fields

**current performance:** {"baseline_actual_inner_candidates": 19640, "baseline_cpu_seconds": 4671.972935780999, "effective_actual_inner_candidates": 10588, "effective_cpu_seconds": 2248.673858854, "matched_cycles": 11, "saved_actual_inner_candidates": 9052, "saved_cpu_seconds": 2423.2990769269995}

**failure clusters:** {"logical_differences": [], "unknown_checks": []}

**bottleneck:** Redundant exact task assessments and certified early-terminated searches, rather than a changed candidate objective

**previous attempt insufficiency:** Whole-assessment caching cannot reuse overlapping task subsets or share identical task evidence across arms

**intervention:** Per-task exact reuse and guarded cross-budget early-termination certificates

**mechanism:** Reuse only completed scope-equivalent evidence; preserve source logical counts and separately charge actual work

**verification plan:** Compare every completed baseline cycle recursively, including ASTs, probes, selections, fitted models, online decisions and source task/search counters; require external exact-reuse and exhaustion tests

**regression risks:** Unsound budget extrapolation, changed primitive/grammar insertion order, stale recognizer or example scope, hidden-verifier failures mistaken for search exhaustion, and attributing unmatched cycles as savings

**result:** {"full_study_equivalence": "UNKNOWN", "logical_status": "EQUAL_OBSERVED_PREFIX", "totals": {"baseline_actual_inner_candidates": 19640, "baseline_cpu_seconds": 4671.972935780999, "effective_actual_inner_candidates": 10588, "effective_cpu_seconds": 2248.673858854, "matched_cycles": 11, "saved_actual_inner_candidates": 9052, "saved_cpu_seconds": 2423.2990769269995}}

**keep revert revise:** KEEP

**updated rule:** {"claim_limit": "Efficiency for the observed matched prefix only; full-study equivalence is UNKNOWN", "decision": "KEEP", "diagnosis": "Actual inner evaluation work can repeat while the scientific policy is unchanged", "evidence": {"coverage": [{"arm": "original", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [2, 3], "effective_cycles_without_baseline": [2, 3], "matched_cycles": [1], "seed": 11}, {"arm": "static", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [2, 3], "effective_cycles_without_baseline": [2], "matched_cycles": [1], "seed": 11}, {"arm": "learned", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [2, 3], "effective_cycles_without_baseline": [2], "matched_cycles": [1], "seed": 11}, {"arm": "original", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [3], "effective_cycles_without_baseline": [3], "matched_cycles": [1, 2], "seed": 22}, {"arm": "static", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [2, 3], "effective_cycles_without_baseline": [2], "matched_cycles": [1], "seed": 22}, {"arm": "learned", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [2, 3], "effective_cycles_without_baseline": [2], "matched_cycles": [1], "seed": 22}, {"arm": "original", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [3], "effective_cycles_without_baseline": [3], "matched_cycles": [1, 2], "seed": 33}, {"arm": "static", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [2, 3], "effective_cycles_without_baseline": [2, 3], "matched_cycles": [1], "seed": 33}, {"arm": "learned", "baseline_completed_missing_from_effective": [], "baseline_unrun_cycles": [2, 3], "effective_cycles_without_baseline": [2], "matched_cycles": [1], "seed": 33}], "logical_status": "EQUAL_OBSERVED_PREFIX", "matched_cycles": 11, "totals": {"baseline_actual_inner_candidates": 19640, "baseline_cpu_seconds": 4671.972935780999, "effective_actual_inner_candidates": 10588, "effective_cpu_seconds": 2248.673858854, "matched_cycles": 11, "saved_actual_inner_candidates": 9052, "saved_cpu_seconds": 2423.2990769269995}, "verification": {"exact_reuse": {"count": 18, "status": "passed", "tests": ["rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_all_certificate_scope_dependencies_require_new_measurement", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_budget_hit_cannot_hide_a_solution_at_larger_budget", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_certificate_is_only_reused_upwards_not_at_a_smaller_budget", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_completed_failed_space_certificate_equals_direct_higher_budget", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_empty_measurement_has_defined_zero_counts", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_expansion_cap_certificate_is_reused_but_changed_cap_misses", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hidden_list_and_tuple_inputs_and_outputs_cannot_share_scope", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hidden_verifier_failure_never_supplies_a_cross_budget_certificate", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hit_wall_time_and_actual_counters_do_not_copy_historical_work", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_live_multitask_decomposition_equals_original_assessment", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_live_primitive_order_change_can_change_success_and_must_miss", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_partial_hit_and_duplicate_tasks_charge_only_new_task_work", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_public_list_and_tuple_arguments_cannot_share_a_scope", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_recognizer_parameter_changes_invalidate_exact_scope", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_shared_cross_arm_exact_hits_have_independent_actual_counters", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_shared_store_does_not_expose_mutable_report_aliases", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_typed_scope_keys_preserve_nested_containers_and_scalar_types", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_zero_candidate_certificate_records_saved_heuristic_work"]}, "exhaustion_certificate": {"count": 7, "status": "passed", "tests": ["rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_all_certificate_scope_dependencies_require_new_measurement", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_budget_hit_cannot_hide_a_solution_at_larger_budget", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_certificate_is_only_reused_upwards_not_at_a_smaller_budget", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_completed_failed_space_certificate_equals_direct_higher_budget", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_expansion_cap_certificate_is_reused_but_changed_cap_misses", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_hidden_verifier_failure_never_supplies_a_cross_budget_certificate", "rsi2.tests.test_research_efficient_memory.EfficientMemoryTests.test_zero_candidate_certificate_records_saved_heuristic_work"]}}}, "id": "exact_evaluation_reuse", "intervention": "Share exact per-task evidence and sound early-termination certificates without changing proposals or search", "next_test": "Test a newly preregistered workload for further evaluation savings; do not claim solver or RSI gains", "pattern": "Completed task evidence is recomputed across overlapping exact scopes or a certified larger budget", "scope": "observed_matched_prefix", "type": "loop"}
