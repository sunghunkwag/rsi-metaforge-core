# Phase E Report — External Anchoring of Track 2 Discoveries

Branch note: delivered as its own commits on
`claude/gated-generalization-exploration-otka5i` (session branch rules);
phase separation by commit boundaries. Nothing touched `main`.

Three anchor channels, each a computation anyone can rerun against the
frozen Phase D archive (`docs/exploration_archive_phaseD.json`, SHA-256
`e107d831ab2fc590b66974d6b0bbfea8d36e9be1d8ca43cfff14224b00bca96e`).
Frozen instruments (GR4, hash-pinned by
`test_anchor_frozen_instruments_intact`):

- `docs/mdl_spec_phaseE.md` — SHA-256
  `7ab1a939729e746b870fdcd94a5851c36f50057077695c193df637d8a513c9b4`
- `docs/property_library_phaseE.md` — SHA-256
  `fad4acd7697d596a4e51c0d1cab078ac3c2ceb3deb7fc13cf5037f13ae220696`
- anchor implementation source — SHA-256
  `87ac4da05a1cfcc540b8eca4b1c89d1383046874996fe58a51cc5886fe495a99`

The property library was adapted to this VM's actual type
(`f : List[int] -> int`): list-output properties from the directive's
example list (permutation-of-input, sortedness, idempotence, involution,
length preservation) do not type-check for scalar-output programs and
were replaced by the frozen scalar-output properties below. This is a
documented instrument decision, made and hashed before any anchor ran.

## E1 — Transfer anchor

Archive elites become ordinary macro candidates (`Macro.origin =
"exploration"`, tagged end-to-end through serialization) in the standard
proposal stream: `run_system(exploration_pool=...)` proposes one batch of
up to 3 per wave through `speculative_meta_gate("exploration_batch")` —
the unchanged meta_gate behind the Rule 3 ledger, designer-only
acceptance per Phase B (GR2: no gate changes). Frozen selection policy:
halt-bucket-8 elites, expanded to base ops, expanded length 2–12,
deduplicated, frozen elite order.

CLI: `--mode transfer-anchor` (archive hash verified before use).

Official run (`--mode transfer-anchor`, two consecutive runs
byte-identical, digest `973f7a029c444ec7`; artifact
`docs/transfer_anchor_phaseE.json`):

- Pool: 192 candidate bodies from the frozen archive.
- **One exploration-origin adoption:** macro 106, body
  `[INPUT, EVENIDX, RED_ADD]` (sum of even-indexed elements), accepted at
  wave 6 (`META_ACCEPT [bundle_table] gained=1`; TCCI
  `recovery_gained_tasks=["T15"]`, `used_in_gain=true`), riding the
  Rule 3 ledger (`exploration_batch`, accepted; 7 sibling batches
  rejected with hash-verified clean rollbacks).
- **Resulting OPEN -> SOLVED lineage (claim type 1): T15
  alternating_sum**, adopted at wave 7 as
  `M106 INPUT ODDIDX RED_ADD SUB` — sum(even-indexed) −
  sum(odd-indexed). Passes the frozen Phase 0 instrument (40 holdout +
  30 counterfactual pairs) and both sealed gates; the frozen arm never
  solves T15. Final live arm: 23/33 designer solved vs frozen 19/33
  (counterfactual +4: T11, T12, T15, T27); all 23 adopted designer
  programs pass the frozen instrument.
- No other designer adoption changed relative to the Phase B/C state
  (nothing lost).

## E2 — Compression anchor (computed, not judged)

`--mode anchor-report`, two consecutive runs byte-identical:

- Corpus: all 246 elites, fully expanded; base cost **2156 tokens**.
- Candidates: 880 subsequences (length 2–8, ≥2 distinct elites).
- **773 MDL-positive discoveries** under the frozen encoding, each with
  exact numbers. Top savings:
  1. body `[INPUT, INPUT, ZMUL, INPUT, INPUT, ZMUL, ZMUL]` — net 586
     tokens (80 elites), defcost 8, archive cost 2156 → 1562.
  2. body `[INPUT, INPUT, ZMUL]` — net 524 (140 elites), defcost 4.
  3. body `[INPUT, INPUT, ZMUL, INPUT, INPUT, ZMUL]` — net 493.
  4. body `[INPUT, ZMUL, INPUT, INPUT, ZMUL, ZMUL]` — net 488.
  5. body `[INPUT, INPUT, ZMUL, INPUT, INPUT]` — net 394.
  (Elementwise-product composition patterns dominate the archive's
  regularity.) Single-macro judgments only, as frozen in the spec; joint
  compression is understated by construction and claimed accordingly.

## E3 — Property anchor (mathematical ground truth)

`--mode anchor-report` over all 246 elites, exhaustive domain len ≤ 3 /
values 0..3 (85 inputs) plus the frozen seeded extension:

- 107 elites excluded by the frozen triviality list (constant /
  degenerate aggregates / expansion < 2 ops).
- 5 elites failed every property — retained as mapped coverage,
  unclaimed (E4).
- **134 characterized discoveries**, each with its verified property set
  and exact domains. Examples:
  - `[INPUT, RED_MAX]` — total, permutation-invariant, value-monotone,
    append-monotone, concat-max, output-bounded-by-input (the maximum
    aggregate, verified on all 85 exhaustive inputs + seeded extension).
  - `[INPUT, TAIL, TAIL, LEN]` — total, permutation-invariant,
    value-monotone, append-monotone.
  - `[M100, SCAN_ADD, TAIL, TAIL, EVENIDX, LEN]` — total,
    permutation-invariant, value-monotone, append-monotone (an
    exploration composite over the transferred vocabulary).

## E4 — Unclaimed coverage

Elites failing all anchors remain in the archive as mapped territory:
5 failed all properties; every non-transferred, non-MDL-relevant elite
stays recorded in the frozen archive without any claim attached.

## E5 — New tests (4 added; none modified)

1. `test_anchor_frozen_instruments_intact` — hash pins for both spec
   documents, the archive, and the anchor implementation source.
2. `test_exploration_origin_tagging_through_gate` — a synthetic
   sum(xs)^5 wall (8-op addition-chain bound, base-unreachable at
   surface 6) is closed by an exploration candidate through the
   unchanged gate; origin tag verified end-to-end including
   serialization; acceptance statistics stay designer-only; the adoption
   rides the speculation ledger.
3. `test_mdl_computation_deterministic` — hand-checked toy encoding plus
   two-run identity on the frozen archive.
4. `test_property_verification_deterministic` — exact expected property
   vector for the sum program; two-run identity of characterization.

## Acceptance outputs (Phase E state)

Suites at the Phase E commit (c579f47), isolated artifact directory.

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
PASS test_anchor_frozen_instruments_intact
PASS test_exploration_origin_tagging_through_gate
PASS test_mdl_computation_deterministic
PASS test_property_verification_deterministic
RESULT: 138 passed, 0 failed
ALL TESTS PASSED
```

### pytest (`python3 -m pytest rsi_levels_metaforge_unified.py -q`, full, untruncated)

```text
........................................................................ [ 52%]
..................................................................       [100%]
138 passed in 834.34s (0:13:54)
```

