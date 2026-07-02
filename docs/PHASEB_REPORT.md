# Phase B Report — Generated Tasks as Pressure, Never as Score

Branch note: delivered as its own commits on
`claude/gated-generalization-exploration-otka5i` (session branch rules);
phase separation by commit boundaries. Nothing touched `main`.

## B1 — Origin tagging; generated tasks shape the candidate stream

- `SealedTask` gained `origin: str = "designer"`; `seal_task` passes it
  through; `mint_task` seals every minted task with `origin="generated"`.
  Restored runstates replay mints, so tags survive serialization.
- The pressure path is unchanged and now explicitly documented: minted
  tasks enter `rs.tasks`, are scheduled by `run_wave`, their solved
  programs feed `mine_macros` (macro mining) and `derive_weights`
  (proposal-weight shaping), and fresh mints/adoptions keep the
  improvement loop supplied with material.

## B2 — Hard separation in the meta-gate

`meta_gate` now computes its comparison set as
`[t for t in rs.unsolved() if t.origin == "designer"]`. Everything else
about the gate — both stages, the ≥1-newly-gated-task criterion, sealed
dual gates, budgets, seeds — is untouched (GR2: this restricts what may
count as a gain; it adds no acceptance path and weakens nothing).
Generated-origin tasks can no longer justify an installation. Macros
mined from generated-task solutions remain ordinary candidates that must
earn adoption by newly gating a designer task.

Solved-count surfaces split by origin (GR5(a)): `run-adaptive`,
`run-frozen`, and `step` now print `{"solved": <designer>,
"solved_generated": <generated>, ...}`; `demo` prints the same split.
`adoption_log_digest` and the runstate schema keys are unchanged
(bookkeeping, not statistics); `counterfactual_report` was already
designer-only, and `counterfactual_report_from`'s pre-existing
total-vs-external split is left as-is (GR7).

## Primary finding

**`mint_adopted = 4`.** Under designer-only acceptance, minted-macro
adoptions fall from >= 10 (the pre-B empirical pin) to 4. That drop is
the measured effect of removing generated-task gains from acceptance --
nothing more is claimed. The single pre-existing magnitude assertion
encoding the old dynamics was amended under one-time user authorization
(commit `9a6ed41`, `mint_adopted >= 10` -> `== 4`, exact equality pinned
after two byte-identical re-derivations); every other line of every
pre-existing test is untouched and GR1 remains in force.

## Measured behavioral delta (the honest cost of the separation)

Baseline (Phase 0/A) meta-gate acceptances at waves 2–5 were justified
**only** by generated-task gains (G04–G11). Under B2 those are rejections.
Post-B adaptive run at identical seeds/budgets:

| Quantity | Phase 0/A baseline | Post-B |
|---|---|---|
| designer SOLVED | 23 (incl. T28) | 22 — **T28 (sum_x32) regressed to OPEN** |
| generated adopted (pressure) | 12 | 4 (G00–G03, all reach="frontier") |
| accepted meta-gate installs | 6 | 2 (waves 0, 1 — both designer-justified) |
| installed macros | 7 | 2 (mid 100 depth-1; mid 103 depth-2 = [100,100,25]) |
| runtime (adaptive arm) | 3m35s | 1m26s |
| digest | 39d26f1080d4a89b | 42576f55a5cec8b6 |

T28's baseline adoption depended on macros whose installation had been
justified by generated-task gains alone; with that justification removed,
T28 is OPEN at Phase B. This is reported as a designer-frontier
regression caused by enforcing GR5, not silently absorbed. T27 (sum_x16)
survives via the designer-justified wave-1 install (macro 103 mined from
T11/T12 programs, used in T27's adopted solution — the recursive-chain and
depth-2 properties still hold and their pre-existing tests still pass).
The frozen arm is bit-identical to Phase 0 (digest `e5dc308324bb10f6`;
adopted sets equal), and the counterfactual delta remains +3 designer
tasks (22 vs 19) with no frozen-only solves.

The updated Phase B frontier (designer OPEN = 11: baseline 10 + T28) is
the working frontier for later phases; the Phase 0 instrument and
BASELINE_FRONTIER.md remain the frozen baseline reference.

## B3 — Post-run report

`generated_pressure_report(rs)` (serialized as `generated_report` in every
runstate summary): minted count, generated-solved-as-pressure count,
generated tids contributing lineage to installed macros, and installed
macros with generated parents. Post-B adaptive run:
`{"generated_minted": 14, "generated_solved_as_pressure": 4,
"generated_contributing_macro_lineage": [],
"installed_macros_with_generated_parents": []}` — in this run the two
surviving installs were mined from designer-adopted programs, so the
generated-lineage count is 0. That is a measured fact about this run, not
a design property; the machinery reports whatever happens.

## B4 — New tests (3 added; none modified)

1. `test_origin_tags_designer_and_generated` — designer suite all
   designer-origin; minted tasks generated-origin; default is designer.
2. `test_meta_gate_excludes_generated_from_acceptance` — a generated-only
   frontier records `empty_frontier` and refuses without evaluating; real
   run's `gate_records.probe_tids` contain zero generated tids; no gate
   gain event names a generated task; the frozen evaluation instrument
   holds designer ids only (GR5(c)).
3. `test_generated_pressure_report_and_determinism` — report consistency
   with run state; solved split partitions adoptions; two 2-wave runs
   produce byte-identical summaries (origin tags and generated report
   included).

## Acceptance outputs (shared: Phases B + C + D + the authorized amendment)

One combined suite run at the Phase D commit (e9050c7), which contains
Phases B and C and the user-authorized single-pin amendment; battery
artifacts from the Phase 0 official run (artifact-producing subsystems
untouched since).

### Native suite (`--mode test`, full, untruncated)

```text
PASS test_vm_total_and_crash_safe
PASS test_macro_expansion_semantics
PASS test_synthesizer_receives_no_oracle
PASS test_adopted_programs_are_synthesized_not_oracles
PASS test_dual_gates_block_wrong_and_pass_right
PASS test_all_adoptions_pass_both_gates
PASS test_no_task_to_solution_lookup
PASS test_meta_gate_rejects_sabotage
PASS test_determinism_same_seed_same_adoptions
PASS test_counterfactual_adaptive_strictly_exceeds_frozen
PASS test_macro_lineage_depth2_used_in_solutions
PASS test_improvement_chain_is_recursive
PASS test_installed_macros_have_usage_credit
PASS test_family_metadata_blind_search_internals
PASS test_expected_isa_blocked_walls_stay_open
PASS test_no_dynamic_python_evaluator_calls
PASS test_selfgen_tasks_sealed_and_search_blind
PASS test_frontier_selfgen_discriminator
PASS test_drift_orchestrator_bookkeeping
PASS test_negative_grams_never_contradict_adoptions
PASS test_rewrite_rules_formally_verified_small_domain
PASS test_cascade_threshold_bookkeeping
PASS test_via_operator_composition_semantics
PASS test_hdc_algebra_soundness
PASS test_kuramoto_phase_locking
PASS test_zero_shot_analogy_transfer
PASS test_wm_learns_declared_families
PASS test_wm_never_mispredicts_where_it_predicts
PASS test_wm_composed_prediction_sound_and_abstains
PASS test_wm_learner_is_blind_to_implementation
PASS test_prm_scorer_deterministic_and_separates
PASS test_prm_beam_finds_sum_and_is_train_exact_only
PASS test_prm_paths_are_oracle_free
PASS test_gd_env_no_oracle_attribute_and_budget
PASS test_gd_debate_resolves_designed_ambiguity
PASS test_gd_distinguisher_finds_separating_input
PASS test_gd_constitution_parsimony_prefers_min_cost
PASS test_gd_pipeline_deterministic
PASS test_gd_agent_and_selection_paths_oracle_free
PASS test_gd_meta_select_structure
PASS test_gd_generation_drift_shows_qualitative_gain
PASS test_prm_channel_bookkeeping_in_adaptive_run
PASS test_r0_retraction_cascades_and_prm_replay
PASS test_r0_ledger_records_provenance
PASS test_r1_lessons_from_mechanical_predicates
PASS test_r2_transfer_resolves_length_hidden_ambiguity
PASS test_r2_reflective_paths_are_oracle_free
PASS test_r3_budget_bookkeeping_bounded
PASS test_r4_discovers_orphan_failure_type
PASS test_closure_certificates_walls_blocked_le6
PASS test_certificates_consistent_with_solved_tasks
PASS test_no_int_to_list_constructor_lemma
PASS test_reflective_clean_run_has_no_false_retractions
PASS test_extension_registry_dormant_inertness
PASS test_bcast_semantics_and_typing_agree
PASS test_capability_request_is_mechanical_and_oracle_free
PASS test_witness_passes_gates_and_is_never_counted_solved
PASS test_targeted_scan_cross_validates_full_table
PASS test_deep_scan_artifact_certifies_walls
PASS test_bcast_certificate_consistent_with_witness
PASS test_admission_trial_is_honest_and_revokes
PASS test_hdv_encoding_deterministic_and_positional
PASS test_interference_paths_are_oracle_free
PASS test_hdc_budget_parity_and_wall_consistency
PASS test_deception_probe_refutes_similarity_validity
PASS test_smoothness_probe_quantifies_discontinuity
PASS test_adopted_programs_have_zero_ablation_slack
PASS test_bloat_passes_semantic_gates_but_not_structural
PASS test_clash_matrix_routes_all_cells
PASS test_quarantine_lab_recovers_minimal_form
PASS test_failure_covariance_channels_disagree_on_bloat
PASS test_lineage_scores_match_cached_run_facts
PASS test_verifier_pin_is_stable_and_meaningful
PASS test_forge_language_total_and_deterministic
PASS test_forge_synthesis_paths_are_oracle_free
PASS test_forge_finds_count_above_threshold
PASS test_forge_results_walls_fall_through_sealed_gates
PASS test_forged_admission_is_clean_and_revocable
PASS test_gd_bridge_lifts_forged_semantics
PASS test_forge_downstream_mint_solvable_only_with_forged_ops
PASS test_forge_symmetry_prior_oracle_free
PASS test_fw_generators_deterministic
PASS test_fw_hidden_expectations_never_on_disk
PASS test_fw_agents_never_touch_sealed_scoring
PASS test_fw_results_adaptive_beats_frozen_on_hidden
PASS test_fw_skill_gate_rejects_and_blocks_reuse
PASS test_fw_skills_do_not_encode_eval_ids
PASS test_fw_curriculum_round_two_improves
PASS test_fw_repair_single_line_patch_passes_hidden
PASS test_fw_traces_deterministic_and_archive_roundtrip
PASS test_real_artifact_harness_provisions_public_files
PASS test_real_artifact_hidden_file_gate_blocks_train_only_artifact
PASS test_real_artifact_reference_runner_solves_csv_xlsx_json_and_repo
PASS test_real_artifact_tool_action_layer_trace_and_path_guard
PASS test_emergent_domain_feature_invention_and_recursive_rsi
PASS test_universal_domain_residue_features_expand_scope
PASS test_open_domain_self_improvement_expands_beyond_original_matrix
PASS test_self_edit_capability_patch_improves_copy_without_gate_mutation
PASS test_longcycle_attempt_residue_loop_expands_capability
PASS test_persistent_longcycle_loop_runs_checkpointed_cycles
PASS test_cfs_decoder_total_deterministic
PASS test_cfs_search_oracle_free_and_interference_bookkeeping
PASS test_cfs_results_walls_and_propagation
PASS test_quest_extension_closes_span_phi_walls
PASS test_speculative_adoption_gate_fenced_and_rolls_back
PASS test_expansion_results_consistent
PASS test_grammar_features_are_oracle_free
PASS test_grammar_closes_wall_that_fixed_bank_cannot
PASS test_grammar_extension_is_deterministic
PASS test_grammar_gate_not_weakened_honest_giveup
========================================================================================
GRAMMAR BATTERY (generative feature-expression reach extension of Section 24 Rule 1)
========================================================================================

[G1] witness target = count(elements == max)
  (A) base cfs_phi      : train_exact=True sealed_gates=False  -> span(phi) wall=True
  (B) fixed bank (S.24) : added=['argmax_index', 'argmin_index'] final_gates=False  -> bank cannot close=True
  (C) grammar (S.25)    : added=['count_eq_max'] final_gates=True dim 26->27  -> grammar closes=True

[G2] give-up target = second-largest value (outside grammar closure)
  grammar           : added=['count_eq_first', 'count_eq_last'] final_gates=False  -> honest give-up (no false adoption)=True

reading: the fixed bank exhausts ['argmax_index', 'argmin_index'] and the sealed gate still fails; one composed feature ['count_eq_max'] crosses the SAME gate. measured reach extension over Section 24 = True; verifier left intact = True.
boundary kept honest: grammar primitives remain designer-declared; this is one level of regress removed, not a singularity.
PASS test_grammar_battery_artifact_consistent
PASS test_grammar2_features_are_oracle_free
PASS test_grammar2_closes_wall_that_depth1_cannot
PASS test_grammar2_extension_is_deterministic
PASS test_grammar2_gate_not_weakened_honest_giveup
========================================================================================
GRAMMAR-2 BATTERY (depth-2 masked-reduction reach extension of Section 25)
========================================================================================

[H1] witness target = max(elements strictly below the mean)
  (A) base cfs_phi      : train_exact=True sealed_gates=False  -> span(phi) wall=True
  (B) fixed bank (S.24) : final_gates=False added=['argmax_index', 'argmin_index']  -> cannot close=True
  (C) depth-1 grm (S.25): final_gates=False added=['count_eq_first', 'count_eq_last']  -> cannot close=True
  (D) depth-2 grm (S.26): final_gates=True added=['mred_max_lt_mean'] dim 26->27  -> closes=True

[H2] give-up target = second-largest value (outside depth-2 closure)
  depth-2 grammar   : final_gates=False added=['count_eq_first', 'count_eq_last']  -> honest give-up=True

reading: the fixed bank and the depth-1 grammar both exhaust their candidates and the sealed gate still fails; one masked reduction ['mred_max_lt_mean'] crosses the SAME gate. measured reach extension over Section 25 = True; verifier intact = True.
boundary kept honest: ops/comparators/reducers remain designer-declared; this is one more rung, not a singularity.
PASS test_grammar2_battery_artifact_consistent
PASS test_frozen_holdout_phase0_instrument_intact
PASS test_capacity_defaults_and_second_namespace_unchanged
PASS test_capacity_growth_ladder_bounded
PASS test_capacity_growth_fires_under_synthetic_stagnation
PASS test_capacity_growth_never_fires_in_healthy_run
PASS test_capacity_growth_log_deterministic
PASS test_origin_tags_designer_and_generated
PASS test_meta_gate_excludes_generated_from_acceptance
PASS test_generated_pressure_report_and_determinism
PASS test_permanent_install_single_call_site
PASS test_generated_derived_classification
PASS test_speculative_rollback_restores_certified_state
PASS test_speculation_budget_bounded_per_wave
PASS test_speculation_ledger_deterministic
PASS test_explore_frozen_instruments_intact
PASS test_explore_archive_two_run_byte_identical
PASS test_explore_strictly_cheaper_replacement
PASS test_explore_sealed_from_task_data
RESULT: 134 passed, 0 failed
ALL TESTS PASSED
```

### pytest (`python3 -m pytest rsi_levels_metaforge_unified.py -q`, full, untruncated)

```text
........................................................................ [ 53%]
..............................................................           [100%]
134 passed in 806.25s (0:13:26)
```

