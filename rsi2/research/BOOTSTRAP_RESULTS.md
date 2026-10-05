# TRAIN bootstrap search results

Original criteria a–e remain **FAIL**. These development kernels establish no RSI claim. All results below come from supplied raw artifacts; the reporter runs no tasks.

| Method | B | Seed | Evidence | Complete | Verified/observed | All attempts | Helper attempts | Search calls | Search steps | Run CPU s | Rule |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| adaptive | 64 | 11 | pilot | True | 5/36 | 2037 | unknown | 20370 | 865905 | 30.502 | PILOT_ONLY |
| adaptive | 640 | 11 | pilot | True | 7/36 | 18941 | unknown | 189410 | 8692775 | 241.437 | PILOT_ONLY |
| decomposition | 64 | 11 | pilot | True | 5/36 | 160 | 155 | 242 | 3520 | 1.194 | PILOT_ONLY |
| enumeration | 64 | 11 | pilot | True | 6/36 | 2006 | unknown | unknown | 67451 | 21.508 | PILOT_ONLY |
| enumeration | 64 | 11 | frozen_development | True | 6/36 | 2006 | unknown | 2205 | 67451 | 18.739 | BASELINE_ONLY |
| enumeration | 640 | 11 | frozen_development | True | 8/36 | 18711 | unknown | 20124 | 716842 | 178.371 | BASELINE_ONLY |
| observational | 64 | 11 | frozen_development | True | 6/36 | 2005 | 530 | 14639 | 415466 | 1.717 | REVISE_NO_VERIFIED_CAPABILITY_GAIN |
| observational | 640 | 11 | frozen_development | True | 8/36 | 18763 | 5992 | 132379 | 5185388 | 7.772 | REVISE_NO_VERIFIED_CAPABILITY_GAIN |
| repair_normalized | 64 | 11 | frozen_development | True | 5/36 | 2016 | unknown | 9396 | 297789 | 82.694 | REVISE_REGRESSION |
| stratified_decomposition | 64 | 11 | frozen_development | True | 5/36 | 160 | 155 | 241 | 4047 | 0.865 | REVISE_REGRESSION |
| stratified_decomposition | 640 | 11 | frozen_development | True | 6/36 | 754 | 748 | 969 | 24473 | 4.685 | REVISE_REGRESSION |
| stratified | 64 | 11 | frozen_development | True | 5/36 | 2016 | 0 | 2235 | 89818 | 15.810 | REVISE_REGRESSION |
| stratified | 640 | 11 | frozen_development | True | 9/36 | 16711 | 0 | 17244 | 858975 | 92.139 | REVISE_REGRESSION |
| enumeration | 64 | 11 | pilot | True | 6/36 | 2006 | unknown | 2205 | 67451 | 21.136 | PILOT_ONLY |
| enumeration | 640 | 11 | pilot | True | 8/36 | 18711 | unknown | 20124 | 716842 | 227.332 | PILOT_ONLY |
| observational | 64 | 11 | invalid_pre_scope_fix_pilot | True | 6/36 | 2005 | 530 | 14639 | 415466 | 0.855 | EXCLUDE_INVALID_PILOT |
| observational | 640 | 11 | invalid_pre_scope_fix_pilot | True | 8/36 | 18763 | 5992 | 132379 | 5185388 | 18.721 | EXCLUDE_INVALID_PILOT |
| enumeration | 640 | 11 | invalid_pre_live_cap_pilot | True | 8/36 | 18711 | unknown | 20124 | 716842 | 197.028 | EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT |
| stratified_decomposition | 64 | 11 | invalid_pre_live_cap_pilot | True | 5/36 | 160 | 155 | 241 | 4047 | 1.564 | EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT |
| stratified_decomposition | 640 | 11 | invalid_pre_live_cap_pilot | True | 6/36 | 754 | 748 | 969 | 24473 | 2.458 | EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT |
| stratified | 64 | 11 | invalid_pre_live_cap_pilot | True | 5/36 | 2016 | 0 | 2235 | 89818 | 14.266 | EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT |
| stratified | 640 | 11 | invalid_pre_live_cap_pilot | True | 9/36 | 16711 | 0 | 17244 | 858975 | 85.659 | EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT |
| repair | 64 | 11 | pilot | True | 5/36 | 2016 | unknown | 9396 | 297789 | 85.060 | PILOT_ONLY |
| sampling | 64 | 11 | pilot | True | 5/36 | 2028 | unknown | 20280 | 853965 | 27.840 | PILOT_ONLY |

Run CPU includes verification, serialization and compression overhead. Search calls/steps exclude the separately reported verifier. Unknown counters have known-only subtotals in [the full structured report](BOOTSTRAP_RESULTS.json). Shared caps do not equalize work.

- adaptive B64: eligible seeds []; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- adaptive B640: eligible seeds []; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- decomposition B64: eligible seeds []; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- enumeration B64: eligible seeds [11]; BASELINE_ONLY; no rule activated.
- enumeration B640: eligible seeds [11]; BASELINE_ONLY; no rule activated.
- observational B64: eligible seeds [11]; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- observational B640: eligible seeds [11]; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- repair B64: eligible seeds []; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- repair_normalized B64: eligible seeds [11]; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- sampling B64: eligible seeds []; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- stratified B64: eligible seeds [11]; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- stratified B640: eligible seeds [11]; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- stratified_decomposition B64: eligible seeds [11]; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.
- stratified_decomposition B640: eligible seeds [11]; PENDING_MISSING_REGISTERED_SEEDS; no rule activated.

## adaptive B64 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/adaptive_seed11_B64.json.gz`. Expansion meaning: typed production requests during draws.

- **current_performance**: 5/36 verified; run CPU 30.502 s; logical_program_attempts=2037; complete_program_attempts=2037; auxiliary_program_attempts=unknown; total_interpreter_calls=20388; total_interpreter_steps=866546; expansions=13406.
- **failure_clusters**: {"search_termination":{"candidate_budget":31,"public_match":5},"trial_failure_labels_known":{"sampled_program_runtime_invalid":806},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"adaptive","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Alternating prior and public near-miss count-fitted sampling"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/adaptive_seed11_B64.json.gz","classification":"pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":31,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":45,"unique_exact_ast_count":5,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## adaptive B640 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/adaptive_seed11_B640.json.gz`. Expansion meaning: typed production requests during draws.

- **current_performance**: 7/36 verified; run CPU 241.437 s; logical_program_attempts=18941; complete_program_attempts=18941; auxiliary_program_attempts=unknown; total_interpreter_calls=189436; total_interpreter_steps=8693699; expansions=154536.
- **failure_clusters**: {"search_termination":{"cpu_budget":2,"candidate_budget":27,"public_match":7},"trial_failure_labels_known":{"sampled_program_runtime_invalid":7459},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":2,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"adaptive","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Alternating prior and public near-miss count-fitted sampling"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/adaptive_seed11_B640.json.gz","classification":"pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":2,"expansion_budget_terminations":0,"candidate_budget_terminations":27,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":61,"unique_exact_ast_count":7,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## decomposition B64 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/decomposition_seed11_B64.json.gz`. Expansion meaning: combined head/component frontier pops.

- **current_performance**: 5/36 verified; run CPU 1.194 s; logical_program_attempts=160; complete_program_attempts=5; auxiliary_program_attempts=155; total_interpreter_calls=258; total_interpreter_steps=3863; expansions=1241.
- **failure_clusters**: {"search_termination":{"not_applicable":29,"public_solution":5,"candidate_budget":2},"trial_failure_labels_known":{"runtime_error: _RuntimeFailure: head of empty list":18,"public_output_mismatch":122,"runtime_error: ZeroDivisionError: integer modulo by zero":1,"runtime_error: _RuntimeFailure: tail of empty list":2},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"decomposition","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Public pointwise relation, enumerated head and scalar component, verified full root"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/decomposition_seed11_B64.json.gz","classification":"pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":2,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":3,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## enumeration B64 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/enumeration_seed11_B64.json.gz`. Expansion meaning: frontier pops.

- **current_performance**: 6/36 verified; run CPU 21.508 s; logical_program_attempts=2006; complete_program_attempts=2006; auxiliary_program_attempts=unknown; total_interpreter_calls=unknown; total_interpreter_steps=67806; expansions=unknown.
- **failure_clusters**: {"search_termination":{"candidate_budget":30,"selected_public_match":6},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"enumeration","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Frozen typed probability-order queue, with a fresh frontier per task"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/enumeration_seed11_B64.json.gz","classification":"pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":30,"search_cpu_observed_rows":0,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":4,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## enumeration B64 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/enumeration_seed11_B64.json.gz`. Expansion meaning: frontier pops.

- **current_performance**: 6/36 verified; run CPU 18.739 s; logical_program_attempts=2006; complete_program_attempts=2006; auxiliary_program_attempts=unknown; total_interpreter_calls=2226; total_interpreter_steps=67806; expansions=22228.
- **failure_clusters**: {"search_termination":{"candidate_budget":30,"selected_public_match":6},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"enumeration","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Frozen typed probability-order queue, with a fresh frontier per task"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B64.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B64.json.gz","new_verified_tasks":[],"lost_verified_tasks":[],"same_verified_set":true,"logical_work":{"logical_program_attempts":{"baseline":2006,"candidate":2006,"difference":0},"total_interpreter_calls":{"baseline":2226,"candidate":2226,"difference":0},"total_interpreter_steps":{"baseline":67806,"candidate":67806,"difference":0}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":30,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":4,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "BASELINE_ONLY"
- **updated_rule**: {"status":"BASELINE_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## enumeration B640 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/enumeration_seed11_B640.json.gz`. Expansion meaning: frontier pops.

- **current_performance**: 8/36 verified; run CPU 178.371 s; logical_program_attempts=18711; complete_program_attempts=18711; auxiliary_program_attempts=unknown; total_interpreter_calls=20155; total_interpreter_steps=717558; expansions=207296.
- **failure_clusters**: {"search_termination":{"candidate_budget":28,"selected_public_match":8},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"enumeration","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Frozen typed probability-order queue, with a fresh frontier per task"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B640.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B640.json.gz","new_verified_tasks":[],"lost_verified_tasks":[],"same_verified_set":true,"logical_work":{"logical_program_attempts":{"baseline":18711,"candidate":18711,"difference":0},"total_interpreter_calls":{"baseline":20155,"candidate":20155,"difference":0},"total_interpreter_steps":{"baseline":717558,"candidate":717558,"difference":0}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":28,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":34,"unique_exact_ast_count":6,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "BASELINE_ONLY"
- **updated_rule**: {"status":"BASELINE_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## observational B64 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/observational_seed11_B64.json.gz`. Expansion meaning: bottom-up construction ticks.

- **current_performance**: 6/36 verified; run CPU 1.717 s; logical_program_attempts=2005; complete_program_attempts=1475; auxiliary_program_attempts=530; total_interpreter_calls=14660; total_interpreter_steps=415821; expansions=15167.
- **failure_clusters**: {"search_termination":{"evaluation_budget":30,"solution":6},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":250,"known_subtotal":250,"known_rows":36,"missing_rows":0},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"observational","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Size-based typed composition and scope-specific public observational equivalence"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/observational_seed11_B64.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B64.json.gz","new_verified_tasks":[],"lost_verified_tasks":[],"same_verified_set":true,"logical_work":{"logical_program_attempts":{"baseline":2006,"candidate":2005,"difference":-1},"total_interpreter_calls":{"baseline":2226,"candidate":14660,"difference":12434},"total_interpreter_steps":{"baseline":67806,"candidate":415821,"difference":348015}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":30,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":4,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "REVISE_NO_VERIFIED_CAPABILITY_GAIN"
- **updated_rule**: {"status":"REVISE_NO_VERIFIED_CAPABILITY_GAIN","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## observational B640 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/observational_seed11_B640.json.gz`. Expansion meaning: bottom-up construction ticks.

- **current_performance**: 8/36 verified; run CPU 7.772 s; logical_program_attempts=18763; complete_program_attempts=12771; auxiliary_program_attempts=5992; total_interpreter_calls=132410; total_interpreter_steps=5186104; expansions=79980.
- **failure_clusters**: {"search_termination":{"evaluation_budget":28,"solution":8},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":3820,"known_subtotal":3820,"known_rows":36,"missing_rows":0},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"observational","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Size-based typed composition and scope-specific public observational equivalence"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/observational_seed11_B640.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B640.json.gz","new_verified_tasks":[],"lost_verified_tasks":[],"same_verified_set":true,"logical_work":{"logical_program_attempts":{"baseline":18711,"candidate":18763,"difference":52},"total_interpreter_calls":{"baseline":20155,"candidate":132410,"difference":112255},"total_interpreter_steps":{"baseline":717558,"candidate":5186104,"difference":4468546}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":28,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":34,"unique_exact_ast_count":6,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "REVISE_NO_VERIFIED_CAPABILITY_GAIN"
- **updated_rule**: {"status":"REVISE_NO_VERIFIED_CAPABILITY_GAIN","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## repair_normalized B64 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/repair_normalized_seed11_B64.json.gz`. Expansion meaning: all enumerator frontier pops; normalization visits counted separately.

- **current_performance**: 5/36 verified; run CPU 82.694 s; logical_program_attempts=2016; complete_program_attempts=2016; auxiliary_program_attempts=unknown; total_interpreter_calls=9414; total_interpreter_steps=298071; expansions=68076.
- **failure_clusters**: {"search_termination":{"candidate_budget":31,"public_match":5},"trial_failure_labels_known":{"runtime_error: _RuntimeFailure: head of empty list":815,"runtime_error: _RuntimeFailure: tail of empty list":358,"runtime_error: ZeroDivisionError: integer division or modulo by zero":24,"runtime_error: ZeroDivisionError: integer modulo by zero":24},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"repair_normalized","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Typed subtree replacement with charged beta normalization"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/repair_normalized_seed11_B64.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B64.json.gz","new_verified_tasks":[],"lost_verified_tasks":["caesar-cipher-k-modulo-n with k=1 and n=2"],"same_verified_set":false,"logical_work":{"logical_program_attempts":{"baseline":2006,"candidate":2016,"difference":10},"total_interpreter_calls":{"baseline":2226,"candidate":9414,"difference":7188},"total_interpreter_steps":{"baseline":67806,"candidate":298071,"difference":230265}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":31,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":14,"unique_exact_ast_count":3,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "REVISE_REGRESSION"
- **updated_rule**: {"status":"REVISE_REGRESSION","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified_decomposition B64 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/stratified_decomposition_seed11_B64.json.gz`. Expansion meaning: head frontier pops plus scalar prefix/argument pops and structural queries.

- **current_performance**: 5/36 verified; run CPU 0.865 s; logical_program_attempts=160; complete_program_attempts=5; auxiliary_program_attempts=155; total_interpreter_calls=257; total_interpreter_steps=4390; expansions=783.
- **failure_clusters**: {"search_termination":{"not_applicable":29,"public_solution":5,"candidate_budget":2},"trial_failure_labels_known":{"runtime_error: _RuntimeFailure: head of empty list":6,"public_output_mismatch":129,"runtime_error: ZeroDivisionError: integer division or modulo by zero":4,"runtime_error: ZeroDivisionError: integer modulo by zero":2,"runtime_error: _RuntimeFailure: tail of empty list":2},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified_decomposition","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Public pointwise relation with charged head, stratified scalar search and full-root verification"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/stratified_decomposition_seed11_B64.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{"live_shared_global_cap_v2":36},"version_unknown_rows":0,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B64.json.gz","new_verified_tasks":[],"lost_verified_tasks":["prepend-k with k=0"],"same_verified_set":false,"logical_work":{"logical_program_attempts":{"baseline":2006,"candidate":160,"difference":-1846},"total_interpreter_calls":{"baseline":2226,"candidate":257,"difference":-1969},"total_interpreter_steps":{"baseline":67806,"candidate":4390,"difference":-63416}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":2,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":3,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "REVISE_REGRESSION"
- **updated_rule**: {"status":"REVISE_REGRESSION","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified_decomposition B640 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/stratified_decomposition_seed11_B640.json.gz`. Expansion meaning: head frontier pops plus scalar prefix/argument pops and structural queries.

- **current_performance**: 6/36 verified; run CPU 4.685 s; logical_program_attempts=754; complete_program_attempts=6; auxiliary_program_attempts=748; total_interpreter_calls=988; total_interpreter_steps=24941; expansions=1846.
- **failure_clusters**: {"search_termination":{"not_applicable":29,"public_solution":6,"candidate_budget":1},"trial_failure_labels_known":{"runtime_error: _RuntimeFailure: head of empty list":93,"public_output_mismatch":579,"runtime_error: ZeroDivisionError: integer division or modulo by zero":19,"runtime_error: ZeroDivisionError: integer modulo by zero":18,"runtime_error: _RuntimeFailure: tail of empty list":26},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified_decomposition","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Public pointwise relation with charged head, stratified scalar search and full-root verification"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/stratified_decomposition_seed11_B640.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{"live_shared_global_cap_v2":36},"version_unknown_rows":0,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B640.json.gz","new_verified_tasks":["modulo-k with k=2"],"lost_verified_tasks":["index-k with k=3","prepend-k with k=0","prepend-k with k=4"],"same_verified_set":false,"logical_work":{"logical_program_attempts":{"baseline":18711,"candidate":754,"difference":-17957},"total_interpreter_calls":{"baseline":20155,"candidate":988,"difference":-19167},"total_interpreter_steps":{"baseline":717558,"candidate":24941,"difference":-692617}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":1,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":27,"unique_exact_ast_count":4,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "REVISE_REGRESSION"
- **updated_rule**: {"status":"REVISE_REGRESSION","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified B64 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/stratified_seed11_B64.json.gz`. Expansion meaning: prefix/argument frontier pops plus structural production queries.

- **current_performance**: 5/36 verified; run CPU 15.810 s; logical_program_attempts=2016; complete_program_attempts=2016; auxiliary_program_attempts=0; total_interpreter_calls=2253; total_interpreter_steps=90100; expansions=14601.
- **failure_clusters**: {"search_termination":{"candidate_budget":31,"public_solution":5},"trial_failure_labels_known":{"public_output_mismatch":1417,"runtime_error: _RuntimeFailure: head of empty list":472,"runtime_error: _RuntimeFailure: tail of empty list":122},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Charged prefix followed by round-robin input-binder argument roles"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/stratified_seed11_B64.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{"live_shared_global_cap_v2":36},"version_unknown_rows":0,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B64.json.gz","new_verified_tasks":[],"lost_verified_tasks":["caesar-cipher-k-modulo-n with k=1 and n=2"],"same_verified_set":false,"logical_work":{"logical_program_attempts":{"baseline":2006,"candidate":2016,"difference":10},"total_interpreter_calls":{"baseline":2226,"candidate":2253,"difference":27},"total_interpreter_steps":{"baseline":67806,"candidate":90100,"difference":22294}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":31,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":14,"unique_exact_ast_count":3,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "REVISE_REGRESSION"
- **updated_rule**: {"status":"REVISE_REGRESSION","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified B640 seed 11 (frozen_development)

Raw evidence: `rsi2/research/bootstrap_results/frozen/stratified_seed11_B640.json.gz`. Expansion meaning: prefix/argument frontier pops plus structural production queries.

- **current_performance**: 9/36 verified; run CPU 92.139 s; logical_program_attempts=16711; complete_program_attempts=16711; auxiliary_program_attempts=0; total_interpreter_calls=17280; total_interpreter_steps=860066; expansions=50172.
- **failure_clusters**: {"search_termination":{"candidate_budget":24,"public_solution":9,"strata_exhausted":3},"trial_failure_labels_known":{"public_output_mismatch":13048,"runtime_error: _RuntimeFailure: head of empty list":2044,"runtime_error: _RuntimeFailure: tail of empty list":830,"runtime_error: ZeroDivisionError: integer division or modulo by zero":474,"runtime_error: ZeroDivisionError: integer modulo by zero":306},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Charged prefix followed by round-robin input-binder argument roles"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/frozen/stratified_seed11_B640.json.gz","classification":"frozen_development","accounting_provenance":{"namespace":["frozen"],"reported_expansion_versions":{"live_shared_global_cap_v2":36},"version_unknown_rows":0,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":true,"baseline_comparison":{"status":"descriptive_paired_development","baseline_path":"rsi2/research/bootstrap_results/frozen/enumeration_seed11_B640.json.gz","new_verified_tasks":["prepend-index-k with k=2","replace-all-with-index-k with k=1"],"lost_verified_tasks":["index-k with k=3"],"same_verified_set":false,"logical_work":{"logical_program_attempts":{"baseline":18711,"candidate":16711,"difference":-2000},"total_interpreter_calls":{"baseline":20155,"candidate":17280,"difference":-2875},"total_interpreter_steps":{"baseline":717558,"candidate":860066,"difference":142508}},"equal_total_work_claim":false,"note":"Shared caps do not equalize interpreter work or differently defined expansions"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":24,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":51,"unique_exact_ast_count":7,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "REVISE_REGRESSION"
- **updated_rule**: {"status":"REVISE_REGRESSION","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## enumeration B64 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/instrumented/enumeration_seed11_B64.json.gz`. Expansion meaning: frontier pops.

- **current_performance**: 6/36 verified; run CPU 21.136 s; logical_program_attempts=2006; complete_program_attempts=2006; auxiliary_program_attempts=unknown; total_interpreter_calls=2226; total_interpreter_steps=67806; expansions=22228.
- **failure_clusters**: {"search_termination":{"candidate_budget":30,"selected_public_match":6},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"enumeration","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Frozen typed probability-order queue, with a fresh frontier per task"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/instrumented/enumeration_seed11_B64.json.gz","classification":"pilot","accounting_provenance":{"namespace":["instrumented"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":30,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":4,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## enumeration B640 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/instrumented/enumeration_seed11_B640.json.gz`. Expansion meaning: frontier pops.

- **current_performance**: 8/36 verified; run CPU 227.332 s; logical_program_attempts=18711; complete_program_attempts=18711; auxiliary_program_attempts=unknown; total_interpreter_calls=20155; total_interpreter_steps=717558; expansions=207296.
- **failure_clusters**: {"search_termination":{"candidate_budget":28,"selected_public_match":8},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":4,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"enumeration","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Frozen typed probability-order queue, with a fresh frontier per task"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/instrumented/enumeration_seed11_B640.json.gz","classification":"pilot","accounting_provenance":{"namespace":["instrumented"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":28,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":34,"unique_exact_ast_count":6,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## observational B64 seed 11 (invalid_pre_scope_fix_pilot)

Raw evidence: `rsi2/research/bootstrap_results/observational_seed11_B64.json.gz`. Expansion meaning: bottom-up construction ticks.

- **current_performance**: 6/36 verified; run CPU 0.855 s; logical_program_attempts=2005; complete_program_attempts=1475; auxiliary_program_attempts=530; total_interpreter_calls=14660; total_interpreter_steps=415821; expansions=15167.
- **failure_clusters**: {"search_termination":{"evaluation_budget":30,"solution":6},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":250,"known_subtotal":250,"known_rows":36,"missing_rows":0},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"observational","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Size-based typed composition and scope-specific public observational equivalence"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/observational_seed11_B64.json.gz","classification":"invalid_pre_scope_fix_pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":30,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":4,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "EXCLUDE_INVALID_PILOT"
- **updated_rule**: {"status":"EXCLUDE_INVALID_PILOT","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## observational B640 seed 11 (invalid_pre_scope_fix_pilot)

Raw evidence: `rsi2/research/bootstrap_results/observational_seed11_B640.json.gz`. Expansion meaning: bottom-up construction ticks.

- **current_performance**: 8/36 verified; run CPU 18.721 s; logical_program_attempts=18763; complete_program_attempts=12771; auxiliary_program_attempts=5992; total_interpreter_calls=132410; total_interpreter_steps=5186104; expansions=79980.
- **failure_clusters**: {"search_termination":{"evaluation_budget":28,"solution":8},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":3820,"known_subtotal":3820,"known_rows":36,"missing_rows":0},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"observational","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Size-based typed composition and scope-specific public observational equivalence"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/observational_seed11_B640.json.gz","classification":"invalid_pre_scope_fix_pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":28,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":34,"unique_exact_ast_count":6,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "EXCLUDE_INVALID_PILOT"
- **updated_rule**: {"status":"EXCLUDE_INVALID_PILOT","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## enumeration B640 seed 11 (invalid_pre_live_cap_pilot)

Raw evidence: `rsi2/research/bootstrap_results/pre_live_cap/enumeration_seed11_B640.json.gz`. Expansion meaning: frontier pops.

- **current_performance**: 8/36 verified; run CPU 197.028 s; logical_program_attempts=18711; complete_program_attempts=18711; auxiliary_program_attempts=unknown; total_interpreter_calls=20155; total_interpreter_steps=717558; expansions=207296.
- **failure_clusters**: {"search_termination":{"candidate_budget":28,"selected_public_match":8},"trial_failure_labels_known":{},"tasks_without_trial_logs":36,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"enumeration","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Frozen typed probability-order queue, with a fresh frontier per task"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/pre_live_cap/enumeration_seed11_B640.json.gz","classification":"invalid_pre_live_cap_pilot","accounting_provenance":{"namespace":["pre_live_cap"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":true,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":28,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":34,"unique_exact_ast_count":6,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT"
- **updated_rule**: {"status":"EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified_decomposition B64 seed 11 (invalid_pre_live_cap_pilot)

Raw evidence: `rsi2/research/bootstrap_results/pre_live_cap/stratified_decomposition_seed11_B64.json.gz`. Expansion meaning: head frontier pops plus scalar prefix/argument pops and structural queries.

- **current_performance**: 5/36 verified; run CPU 1.564 s; logical_program_attempts=160; complete_program_attempts=5; auxiliary_program_attempts=155; total_interpreter_calls=257; total_interpreter_steps=4390; expansions=783.
- **failure_clusters**: {"search_termination":{"not_applicable":29,"public_solution":5,"candidate_budget":2},"trial_failure_labels_known":{"runtime_error: _RuntimeFailure: head of empty list":6,"public_output_mismatch":129,"runtime_error: ZeroDivisionError: integer division or modulo by zero":4,"runtime_error: ZeroDivisionError: integer modulo by zero":2,"runtime_error: _RuntimeFailure: tail of empty list":2},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified_decomposition","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Public pointwise relation with charged head, stratified scalar search and full-root verification"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/pre_live_cap/stratified_decomposition_seed11_B64.json.gz","classification":"invalid_pre_live_cap_pilot","accounting_provenance":{"namespace":["pre_live_cap"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":true,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":2,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":19,"unique_exact_ast_count":3,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT"
- **updated_rule**: {"status":"EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified_decomposition B640 seed 11 (invalid_pre_live_cap_pilot)

Raw evidence: `rsi2/research/bootstrap_results/pre_live_cap/stratified_decomposition_seed11_B640.json.gz`. Expansion meaning: head frontier pops plus scalar prefix/argument pops and structural queries.

- **current_performance**: 6/36 verified; run CPU 2.458 s; logical_program_attempts=754; complete_program_attempts=6; auxiliary_program_attempts=748; total_interpreter_calls=988; total_interpreter_steps=24941; expansions=1846.
- **failure_clusters**: {"search_termination":{"not_applicable":29,"public_solution":6,"candidate_budget":1},"trial_failure_labels_known":{"runtime_error: _RuntimeFailure: head of empty list":93,"public_output_mismatch":579,"runtime_error: ZeroDivisionError: integer division or modulo by zero":19,"runtime_error: ZeroDivisionError: integer modulo by zero":18,"runtime_error: _RuntimeFailure: tail of empty list":26},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified_decomposition","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Public pointwise relation with charged head, stratified scalar search and full-root verification"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/pre_live_cap/stratified_decomposition_seed11_B640.json.gz","classification":"invalid_pre_live_cap_pilot","accounting_provenance":{"namespace":["pre_live_cap"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":true,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":1,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":27,"unique_exact_ast_count":4,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT"
- **updated_rule**: {"status":"EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified B64 seed 11 (invalid_pre_live_cap_pilot)

Raw evidence: `rsi2/research/bootstrap_results/pre_live_cap/stratified_seed11_B64.json.gz`. Expansion meaning: prefix/argument frontier pops plus structural production queries.

- **current_performance**: 5/36 verified; run CPU 14.266 s; logical_program_attempts=2016; complete_program_attempts=2016; auxiliary_program_attempts=0; total_interpreter_calls=2253; total_interpreter_steps=90100; expansions=14601.
- **failure_clusters**: {"search_termination":{"candidate_budget":31,"public_solution":5},"trial_failure_labels_known":{"public_output_mismatch":1417,"runtime_error: _RuntimeFailure: head of empty list":472,"runtime_error: _RuntimeFailure: tail of empty list":122},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Charged prefix followed by round-robin input-binder argument roles"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/pre_live_cap/stratified_seed11_B64.json.gz","classification":"invalid_pre_live_cap_pilot","accounting_provenance":{"namespace":["pre_live_cap"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":true,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":31,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":14,"unique_exact_ast_count":3,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT"
- **updated_rule**: {"status":"EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## stratified B640 seed 11 (invalid_pre_live_cap_pilot)

Raw evidence: `rsi2/research/bootstrap_results/pre_live_cap/stratified_seed11_B640.json.gz`. Expansion meaning: prefix/argument frontier pops plus structural production queries.

- **current_performance**: 9/36 verified; run CPU 85.659 s; logical_program_attempts=16711; complete_program_attempts=16711; auxiliary_program_attempts=0; total_interpreter_calls=17280; total_interpreter_steps=860066; expansions=50172.
- **failure_clusters**: {"search_termination":{"candidate_budget":24,"public_solution":9,"strata_exhausted":3},"trial_failure_labels_known":{"public_output_mismatch":13048,"runtime_error: _RuntimeFailure: head of empty list":2044,"runtime_error: _RuntimeFailure: tail of empty list":830,"runtime_error: ZeroDivisionError: integer division or modulo by zero":474,"runtime_error: ZeroDivisionError: integer modulo by zero":306},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"stratified","candidate_budget":640,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Charged prefix followed by round-robin input-binder argument roles"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/pre_live_cap/stratified_seed11_B640.json.gz","classification":"invalid_pre_live_cap_pilot","accounting_provenance":{"namespace":["pre_live_cap"],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":true,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":24,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":51,"unique_exact_ast_count":7,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT"
- **updated_rule**: {"status":"EXCLUDE_INVALID_PRE_LIVE_CAP_PILOT","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## repair B64 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/repair_seed11_B64.json.gz`. Expansion meaning: all enumerator frontier pops.

- **current_performance**: 5/36 verified; run CPU 85.060 s; logical_program_attempts=2016; complete_program_attempts=2016; auxiliary_program_attempts=unknown; total_interpreter_calls=9414; total_interpreter_steps=298071; expansions=68076.
- **failure_clusters**: {"search_termination":{"candidate_budget":31,"public_match":5},"trial_failure_labels_known":{"runtime_error: _RuntimeFailure: head of empty list":815,"runtime_error: _RuntimeFailure: tail of empty list":358,"runtime_error: ZeroDivisionError: integer division or modulo by zero":24,"runtime_error: ZeroDivisionError: integer modulo by zero":24},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"repair","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Grammar-generated seeds and typed single-subtree replacement"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/repair_seed11_B64.json.gz","classification":"pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":31,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":14,"unique_exact_ast_count":3,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## sampling B64 seed 11 (pilot)

Raw evidence: `rsi2/research/bootstrap_results/sampling_seed11_B64.json.gz`. Expansion meaning: typed production requests during draws.

- **current_performance**: 5/36 verified; run CPU 27.840 s; logical_program_attempts=2028; complete_program_attempts=2028; auxiliary_program_attempts=unknown; total_interpreter_calls=20298; total_interpreter_steps=854606; expansions=13319.
- **failure_clusters**: {"search_termination":{"candidate_budget":31,"public_match":5},"trial_failure_labels_known":{"sampled_program_runtime_invalid":868},"tasks_without_trial_logs":0,"reported_runtime_failure_counter":{"value":null,"known_subtotal":null,"known_rows":0,"missing_rows":36},"selected_verifier_failures":0,"unknown_verifier_rows":0,"reported_search_cpu_above_nominal_cap":0,"planning":"unknown","tool":"unknown","model":"unknown"}
- **bottleneck**: "Verified-program coverage remains the bootstrap gate; candidate count and compression alone are insufficient"
- **previous_attempt_insufficiency**: "Repeated prefixes and simple saved roots do not provide diverse reusable verified structures"
- **intervention**: {"method":"sampling","candidate_budget":64,"nominal_protocol_limits":{"candidate_budgets":[64,640],"max_size":12,"max_expansions":20000,"step_budget":2000,"max_cpu_seconds_per_task":10,"total_cpu_seconds":1800}}
- **mechanism**: "Current-prior typed stochastic draws"
- **verification_plan**: {"raw_source":"rsi2/research/bootstrap_results/sampling_seed11_B64.json.gz","classification":"pilot","accounting_provenance":{"namespace":[],"reported_expansion_versions":{},"version_unknown_rows":36,"quarantined_pre_live_cap":false,"policy":"pre_live_cap records remain invalid even if scalar results match a corrected rerun"},"public_search_then_separate_verifier":true,"reporter_executes_tasks":false}
- **regression_risks**: ["Finite coverage and public observational equivalence","CPU/candidate/expansion limits","Helper accounting differs; all recorded helper work remains charged","No causal learned-library or synthesized-heuristic comparison"]
- **result**: {"complete":true,"eligible":false,"baseline_comparison":{"status":"unavailable","reason":"requires one eligible frozen same-seed/same-budget baseline"},"compression":{"adoptions":0,"entries":0,"identity_macros":0,"mdl_delta":0,"downstream_library_benefit":"unmeasured; tiny identity compression is insufficient"},"guard_evidence":{"unobserved_tasks":0,"cpu_budget_terminations":0,"expansion_budget_terminations":0,"candidate_budget_terminations":31,"search_cpu_observed_rows":36,"run_cpu_above_nominal_total_cap":false,"enforcement_claim":"Telemetry alone does not prove guard enforcement; legacy pilots may predate guards"},"verified_program_evidence":{"total_solution_nodes":46,"unique_exact_ast_count":5,"scope":"Syntactic support only; no reusable-library capability inferred"},"original_criteria":"FAIL; preserved"}
- **keep_revert_revise**: "PILOT_ONLY"
- **updated_rule**: {"status":"PILOT_ONLY","activated":false,"lesson":"Preserve failures; bootstrap diverse verifier-accepted own programs before causal learning tests","required_next":"All registered seeds, common-kernel controls, real compression support and learned-score ablations"}

## Explicit scratch diagnostics

`rsi2/research/development_diagnostics/decomposition_diagnostic.json.gz` (pointwise_scalar_search; pilot):

```json
[
  {
    "name": "modulo-k with k=2",
    "raw_row_index": 0,
    "budget": 64,
    "candidates": 64,
    "head_attempts": 1,
    "component_attempts": 63,
    "root_attempts": 0,
    "example_evaluations": 67,
    "evaluator_steps": 828,
    "expansions": 539,
    "termination": "candidate_budget",
    "component_structural_evidence": {
      "recorded_components": 63,
      "lambda_roots": 7,
      "contains_bound_variable": 1
    },
    "existing_eleven_fields": {
      "current_performance": {
        "public_matches": 0,
        "all_program_attempts": 64
      },
      "failure_clusters": {
        "termination": "candidate_budget",
        "component_mismatches": 63,
        "planning_tool_environment": "unknown"
      },
      "bottleneck": "Whole-list prefix branching versus scalar pointwise subproblem",
      "previous_attempt_insufficiency": "Restarting the same whole-list prefix provides no new AST evidence under fixed state",
      "intervention": "Public-data-derived map decomposition with enumerated operator and scalar components",
      "mechanism": "Constrain the component request type and public scalar relation before enumerating root composition",
      "verification_plan": "All helper and root attempts share B; all interpreter calls/steps counted; full public root required; no hidden verification",
      "regression_risks": "Covers only one-input, length-preserving pointwise relations; full-public agreement does not prove generalization",
      "result": {
        "public_solution": false,
        "termination": "candidate_budget",
        "attempts": 64,
        "interpreter_calls": 67,
        "interpreter_steps": 828
      },
      "keep_revert_revise": "REVISE: exploratory architecture evidence only; independent verification and registered comparison remain pending",
      "updated_rule": "Retain all failures and compare root plus helper budgets before selecting a bootstrap kernel"
    }
  },
  {
    "name": "modulo-k with k=3",
    "raw_row_index": 1,
    "budget": 64,
    "candidates": 64,
    "head_attempts": 1,
    "component_attempts": 63,
    "root_attempts": 0,
    "example_evaluations": 75,
    "evaluator_steps": 929,
    "expansions": 539,
    "termination": "candidate_budget",
    "component_structural_evidence": {
      "recorded_components": 63,
      "lambda_roots": 7,
      "contains_bound_variable": 1
    },
    "existing_eleven_fields": {
      "current_performance": {
        "public_matches": 0,
        "all_program_attempts": 64
      },
      "failure_clusters": {
        "termination": "candidate_budget",
        "component_mismatches": 63,
        "planning_tool_environment": "unknown"
      },
      "bottleneck": "Whole-list prefix branching versus scalar pointwise subproblem",
      "previous_attempt_insufficiency": "Restarting the same whole-list prefix provides no new AST evidence under fixed state",
      "intervention": "Public-data-derived map decomposition with enumerated operator and scalar components",
      "mechanism": "Constrain the component request type and public scalar relation before enumerating root composition",
      "verification_plan": "All helper and root attempts share B; all interpreter calls/steps counted; full public root required; no hidden verification",
      "regression_risks": "Covers only one-input, length-preserving pointwise relations; full-public agreement does not prove generalization",
      "result": {
        "public_solution": false,
        "termination": "candidate_budget",
        "attempts": 64,
        "interpreter_calls": 75,
        "interpreter_steps": 929
      },
      "keep_revert_revise": "REVISE: exploratory architecture evidence only; independent verification and registered comparison remain pending",
      "updated_rule": "Retain all failures and compare root plus helper budgets before selecting a bootstrap kernel"
    }
  },
  {
    "name": "modulo-k with k=2",
    "raw_row_index": 2,
    "budget": 640,
    "candidates": 640,
    "head_attempts": 1,
    "component_attempts": 639,
    "root_attempts": 0,
    "example_evaluations": 656,
    "evaluator_steps": 13042,
    "expansions": 3194,
    "termination": "candidate_budget",
    "component_structural_evidence": {
      "recorded_components": 639,
      "lambda_roots": 35,
      "contains_bound_variable": 5
    },
    "existing_eleven_fields": {
      "current_performance": {
        "public_matches": 0,
        "all_program_attempts": 640
      },
      "failure_clusters": {
        "termination": "candidate_budget",
        "component_mismatches": 639,
        "planning_tool_environment": "unknown"
      },
      "bottleneck": "Scalar grammar prioritizes constant-first partial applications: only 35 lambda roots and 5 programs with bound variables in 639 components; no binary arithmetic inside lambda",
      "previous_attempt_insufficiency": "Restarting the same whole-list prefix provides no new AST evidence under fixed state",
      "intervention": "Public-data-derived map decomposition with enumerated operator and scalar components",
      "mechanism": "Constrain the component request type and public scalar relation before enumerating root composition",
      "verification_plan": "All helper and root attempts share B; all interpreter calls/steps counted; full public root required; no hidden verification",
      "regression_risks": "Covers only one-input, length-preserving pointwise relations; full-public agreement does not prove generalization",
      "result": {
        "public_solution": false,
        "termination": "candidate_budget",
        "attempts": 640,
        "interpreter_calls": 656,
        "interpreter_steps": 13042
      },
      "keep_revert_revise": "REVISE: exploratory architecture evidence only; independent verification and registered comparison remain pending",
      "updated_rule": "Next generic search comparison should cover typed open bodies by size/dependency while charging every fragment; do not install target-specific ASTs or alter this failed kernel after measurement"
    }
  },
  {
    "name": "modulo-k with k=3",
    "raw_row_index": 3,
    "budget": 640,
    "candidates": 640,
    "head_attempts": 1,
    "component_attempts": 639,
    "root_attempts": 0,
    "example_evaluations": 793,
    "evaluator_steps": 15866,
    "expansions": 3194,
    "termination": "candidate_budget",
    "component_structural_evidence": {
      "recorded_components": 639,
      "lambda_roots": 35,
      "contains_bound_variable": 5
    },
    "existing_eleven_fields": {
      "current_performance": {
        "public_matches": 0,
        "all_program_attempts": 640
      },
      "failure_clusters": {
        "termination": "candidate_budget",
        "component_mismatches": 639,
        "planning_tool_environment": "unknown"
      },
      "bottleneck": "Scalar grammar prioritizes constant-first partial applications: only 35 lambda roots and 5 programs with bound variables in 639 components; no binary arithmetic inside lambda",
      "previous_attempt_insufficiency": "Restarting the same whole-list prefix provides no new AST evidence under fixed state",
      "intervention": "Public-data-derived map decomposition with enumerated operator and scalar components",
      "mechanism": "Constrain the component request type and public scalar relation before enumerating root composition",
      "verification_plan": "All helper and root attempts share B; all interpreter calls/steps counted; full public root required; no hidden verification",
      "regression_risks": "Covers only one-input, length-preserving pointwise relations; full-public agreement does not prove generalization",
      "result": {
        "public_solution": false,
        "termination": "candidate_budget",
        "attempts": 640,
        "interpreter_calls": 793,
        "interpreter_steps": 15866
      },
      "keep_revert_revise": "REVISE: exploratory architecture evidence only; independent verification and registered comparison remain pending",
      "updated_rule": "Next generic search comparison should cover typed open bodies by size/dependency while charging every fragment; do not install target-specific ASTs or alter this failed kernel after measurement"
    }
  }
]
```

`rsi2/research/development_diagnostics/prefix_diagnostic.json.gz` (prefix_continuation; pilot):

```json
[
  {
    "name": "append-index-k with k=1",
    "raw_row_index": 0,
    "task_program_attempts": 64,
    "example_evaluations": 640,
    "evaluator_steps": 16972,
    "public_matches": 0,
    "total_on_public_examples": 49,
    "unique_behavior_signatures": 34,
    "first32_unique_signatures": 19,
    "continued32_new_signatures": 15,
    "existing_eleven_fields": {
      "current_performance": {
        "public_matches": 0,
        "attempts": 64
      },
      "failure_clusters": {
        "runtime_failure_programs": 15,
        "repeated_public_behavior": 30,
        "planning_tool_environment": "unknown"
      },
      "bottleneck": "Repeated whole-function prefix and low behavior novelty",
      "previous_attempt_insufficiency": "Same frozen state restarts the same typed probability prefix; repeating it cannot add new candidate evidence",
      "intervention": "Measure next32 continuation novelty and public-output equivalence without changing ranking",
      "mechanism": "Persistent frontier exposes later generated ASTs; a future context-typed behavior bank may avoid equivalent parents",
      "verification_plan": "Every enumerated task-program evaluates all public examples; no auxiliary component evaluations or hidden checks",
      "regression_risks": "Finite public observational equivalence is context-dependent; frontier remains limited to 20000 pops",
      "result": {
        "public_matches": 0,
        "total_on_public_examples": 49,
        "unique_behavior_signatures": 34,
        "continued32_new_signatures": 15
      },
      "keep_revert_revise": "REVISE: architecture hypothesis only; zero hidden verification or transfer claim",
      "updated_rule": "Next comparison must charge all task and auxiliary component attempts and compare matched actual compute"
    }
  },
  {
    "name": "index-head",
    "raw_row_index": 1,
    "task_program_attempts": 64,
    "example_evaluations": 640,
    "evaluator_steps": 13242,
    "public_matches": 0,
    "total_on_public_examples": 54,
    "unique_behavior_signatures": 16,
    "first32_unique_signatures": 11,
    "continued32_new_signatures": 5,
    "existing_eleven_fields": {
      "current_performance": {
        "public_matches": 0,
        "attempts": 64
      },
      "failure_clusters": {
        "runtime_failure_programs": 10,
        "repeated_public_behavior": 48,
        "planning_tool_environment": "unknown"
      },
      "bottleneck": "Repeated whole-function prefix and low behavior novelty",
      "previous_attempt_insufficiency": "Same frozen state restarts the same typed probability prefix; repeating it cannot add new candidate evidence",
      "intervention": "Measure next32 continuation novelty and public-output equivalence without changing ranking",
      "mechanism": "Persistent frontier exposes later generated ASTs; a future context-typed behavior bank may avoid equivalent parents",
      "verification_plan": "Every enumerated task-program evaluates all public examples; no auxiliary component evaluations or hidden checks",
      "regression_risks": "Finite public observational equivalence is context-dependent; frontier remains limited to 20000 pops",
      "result": {
        "public_matches": 0,
        "total_on_public_examples": 54,
        "unique_behavior_signatures": 16,
        "continued32_new_signatures": 5
      },
      "keep_revert_revise": "REVISE: architecture hypothesis only; zero hidden verification or transfer claim",
      "updated_rule": "Next comparison must charge all task and auxiliary component attempts and compare matched actual compute"
    }
  }
]
```

`rsi2/research/development_diagnostics/repair-tiny-train.json.gz` (typed_repair_pilot; pilot):

```json
[
  {
    "name": "keep-mod-k with k=2",
    "raw_row_index": 0,
    "baseline_candidates": 64,
    "baseline_steps": 1806,
    "baseline_public_match": false,
    "baseline_hidden_verified": false,
    "repair_public_match": false,
    "repair_hidden_verified": false,
    "repair_counters": {
      "candidates": 64,
      "evaluation_steps": 6345,
      "evaluator_calls": 261,
      "seed_candidates": 16,
      "repair_candidates": 48,
      "invalid_repairs": 77,
      "duplicate_candidates": 102,
      "expansions": 2464,
      "cpu_seconds": 2.5039579649999997
    },
    "seed_sizes": {
      "1": 1,
      "3": 7,
      "2": 2,
      "5": 4,
      "4": 2
    },
    "additional_interpreter_steps": 4539,
    "existing_eleven_fields": {}
  },
  {
    "name": "append-index-k with k=1",
    "raw_row_index": 1,
    "baseline_candidates": 64,
    "baseline_steps": 1448,
    "baseline_public_match": false,
    "baseline_hidden_verified": false,
    "repair_public_match": false,
    "repair_hidden_verified": false,
    "repair_counters": {
      "candidates": 64,
      "evaluation_steps": 6920,
      "evaluator_calls": 285,
      "seed_candidates": 16,
      "repair_candidates": 48,
      "invalid_repairs": 77,
      "duplicate_candidates": 102,
      "expansions": 2464,
      "cpu_seconds": 2.4683527799999996
    },
    "seed_sizes": {
      "1": 1,
      "3": 7,
      "2": 2,
      "5": 4,
      "4": 2
    },
    "additional_interpreter_steps": 5472,
    "existing_eleven_fields": {}
  },
  {
    "name": "prepend-k with k=4",
    "raw_row_index": 2,
    "baseline_candidates": 64,
    "baseline_steps": 1478,
    "baseline_public_match": false,
    "baseline_hidden_verified": false,
    "repair_public_match": false,
    "repair_hidden_verified": false,
    "repair_counters": {
      "candidates": 64,
      "evaluation_steps": 6967,
      "evaluator_calls": 289,
      "seed_candidates": 16,
      "repair_candidates": 48,
      "invalid_repairs": 77,
      "duplicate_candidates": 102,
      "expansions": 2464,
      "cpu_seconds": 2.7636434539999994
    },
    "seed_sizes": {
      "1": 1,
      "3": 7,
      "2": 2,
      "5": 4,
      "4": 2
    },
    "additional_interpreter_steps": 5489,
    "existing_eleven_fields": {}
  },
  {
    "name": "index-k with k=3",
    "raw_row_index": 3,
    "baseline_candidates": 64,
    "baseline_steps": 2405,
    "baseline_public_match": false,
    "baseline_hidden_verified": false,
    "repair_public_match": false,
    "repair_hidden_verified": false,
    "repair_counters": {
      "candidates": 64,
      "evaluation_steps": 12972,
      "evaluator_calls": 325,
      "seed_candidates": 16,
      "repair_candidates": 48,
      "invalid_repairs": 83,
      "duplicate_candidates": 150,
      "expansions": 1038,
      "cpu_seconds": 1.0721101389999994
    },
    "seed_sizes": {
      "1": 2,
      "3": 1,
      "2": 4,
      "5": 9
    },
    "additional_interpreter_steps": 10567,
    "existing_eleven_fields": {}
  },
  {
    "name": "index-head",
    "raw_row_index": 4,
    "baseline_candidates": 64,
    "baseline_steps": 1700,
    "baseline_public_match": false,
    "baseline_hidden_verified": false,
    "repair_public_match": false,
    "repair_hidden_verified": false,
    "repair_counters": {
      "candidates": 64,
      "evaluation_steps": 11532,
      "evaluator_calls": 397,
      "seed_candidates": 16,
      "repair_candidates": 48,
      "invalid_repairs": 83,
      "duplicate_candidates": 150,
      "expansions": 1038,
      "cpu_seconds": 1.0629571510000009
    },
    "seed_sizes": {
      "1": 2,
      "3": 1,
      "2": 4,
      "5": 9
    },
    "additional_interpreter_steps": 9832,
    "existing_eleven_fields": {}
  }
]
```

## Limits

- Earlier root/instrumented records are pilots.
- Pre-scope-fix observational pilots are invalid.
- pre_live_cap records are quarantined for stale shared caps or CPU-interrupt pop accounting.
- Missing counters are unknown, never zero-filled.
- Bounded enumeration exhaustion does not identify heap versus expansion-cap termination.
- Different expansion definitions prevent an equal-compute inference.
- Only supplied completed frozen records can support descriptive same-seed/budget comparisons.
- Tiny identity MDL reductions establish no downstream library benefit.
- These human-designed kernels do not satisfy original RSI criteria a–e.
