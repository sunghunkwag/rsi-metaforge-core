# Phase D Report — Track 2 Exploration Engine and Coverage Archive

Branch note: delivered as its own commit (e9050c7) on
`claude/gated-generalization-exploration-otka5i` (session branch rules);
phase separation by commit boundaries. Nothing touched `main`.

## D1 — Frozen instruments (created, hashed, then never touched)

- **Probe battery** `docs/probe_battery_phaseD.json` — SHA-256
  `b11b14dfe4616a3c13a1ac872d08b181c532e796c19f74bafe6c050d9e0c0d01`;
  116 seeded probes (44 base across lengths 0-34, plus permutation and
  value-perturbation partners for every base of length >= 2); generator
  `docs/make_probe_battery_phaseD.py` committed; the engine verifies the
  hash before every run. Every Track 2 behavioral measurement is taken
  against this battery.
- **Descriptor set** `docs/descriptor_spec_phaseD.md` — SHA-256
  `c0642490cef51691846dab3260d0e630fedaeaa46e281a3c8b94749e5d937c13`;
  reference implementation source SHA-256
  `cb7aa8ffa42d24c8eede0d73f964e7d99e71b35e6886a3e26d9296db32fb3bc7`
  (both pinned by `test_explore_frozen_instruments_intact`). Six
  descriptors: halting-fraction bucket within the fixed step budget,
  output-class signature, output-entropy bucket, input-output dependence
  class computed from probe diffs (constant / order-sensitive /
  value-sensitive / echo-like), program-cost bucket, stack-usage bucket.
  A cell is the descriptor tuple.
- **Elite ordering** (frozen total order): surface length, then executed
  step count, then lexicographic bytecode.

## D2 — Exploration loop

Seeded proposal stream (one `random.Random(424243)` stream): mutations of
current elites (p=0.4), fresh random programs (p=0.3), compositions of
two elites (p=0.3), built over base ops plus the searcher's macro
vocabulary as building blocks (GR9: vocabulary yes, task data no —
enforced by structure and by an AST sealing test). Insertion iff the
cell is empty or the candidate is strictly cheaper under the frozen
order; every insertion logged with iteration, cell, cost key, and parent
lineage (SHA-16 of parent token tuples). Fixed budget 60,000 evaluations
per run; archive serialized deterministically. CLI modes `explore` /
`explore-report` (`--vocab-from` supplies the macro vocabulary).

One engine defect was found and fixed during Phase D itself, before the
archive freeze: the coverage-curve checkpoint originally sat behind the
insertion branch and recorded nothing; the fix moved it to fire every
checkpoint interval. The frozen descriptor implementation was not
touched (its pinned hash is unchanged).

## D3 — Coverage report (facts about mapped territory, no capability claims)

Official archive `docs/exploration_archive_phaseD.json` — SHA-256
`e107d831ab2fc590b66974d6b0bbfea8d36e9be1d8ca43cfff14224b00bca96e`;
vocabulary = the deterministic adaptive searcher's macros (mids 100,
103). Two consecutive runs byte-identical; runtime ~5 s per run.

- Cells filled: **246** (of a descriptor space with roughly 10^5 nominal
  combinations, most of them presumably unreachable; no claim is made
  about the reachable fraction).
- Coverage curve: 28 cells at 5k evals -> 47 -> 65 -> ... -> 246 at 60k;
  still accruing at budget exhaustion (the map is budget-bounded).
- Insertions: 465 (246 first-fills + 219 strictly-cheaper replacements).
- Lineage depth distribution: 1 to 26 (median ~14) — long real
  mutation/composition chains, not single-shot randomness.
- Proposal mix: 24,392 mutations / 17,843 random / 17,765 compositions.
- Territory fact: every archived behavior is either all-crash (6 cells,
  halt bucket 0) or near-total completion (240 cells, halt bucket 8);
  crash behavior on this ISA is essentially input-independent
  (stack-underflow-driven), so intermediate halting fractions are rare.

## D4 — New tests (4 added; none modified)

1. `test_explore_frozen_instruments_intact` — battery, spec, and
   implementation hash pins.
2. `test_explore_archive_two_run_byte_identical` — determinism at a
   reduced test budget.
3. `test_explore_strictly_cheaper_replacement` — the frozen order
   prefers the strictly cheaper of two behaviorally identical programs
   in the same cell and never replaces with a costlier one.
4. `test_explore_sealed_from_task_data` — AST/source audit: exploration
   code references no task definitions, holdout data, or gate internals
   (GR9).

## Acceptance outputs (shared: Phases B + C + D + the authorized amendment)

One combined suite run at the Phase D commit (e9050c7); battery
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
