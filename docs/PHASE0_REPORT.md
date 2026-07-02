# Phase 0 Report — Baseline and Frozen Instruments

Branch note (deviation from GR11's per-phase branch naming): this session's
harness mandates all development on `claude/gated-generalization-exploration-otka5i`
and forbids pushing to other branches. Phase 0 is therefore delivered on that
branch instead of `phase0-baseline`. Phase separation is preserved by commit
boundaries. Nothing was pushed to `main`.

## 1. Rename (directive step 1)

- `git mv "rsi_levels_metaforge_unified (3).py" rsi_levels_metaforge_unified.py`
  — committed as a pure rename (100% similarity).
- References updated: `README.md`, `EVIDENCE.md`, all `docs/*.md`, and both
  GitHub Actions workflows (`.github/workflows/quick-ci.yml`,
  `full-evidence.yml`) — the workflows invoke the runtime by filename, so
  they were part of the rename's blast radius, not a cleanup (GR7).
- One stale README sentence about the old filename's spaces/parentheses
  removed.

## 2. Compile + execution structure (directive step 2)

- `python3 -m py_compile rsi_levels_metaforge_unified.py` passes
  (Python 3.11.15).
- `docs/ENTRYPOINT_MAP.md` created. Key finding: the file contains SIX
  textual `if __name__ == "__main__":` blocks, not five; five are inert
  text inside `INTEGRATED_SOURCE_ARCHIVE` raw-string literals (lines
  14399–34741), and exactly ONE (line 35703) executes. Direct invocation
  runs a single argparse CLI (`main()`, line 35595, 27 `--mode` choices).
  There is no sequential multi-`__main__` execution in practice; the
  archived subsystems are loaded only via `OrganicSubsystemManager` into
  isolated `organic_*` module namespaces where their `__main__` blocks
  cannot fire.

## 3. Test harnesses (directive step 3)

- Native harness: `--mode test` → `run_tests()` over the module-level
  `TESTS` registry (116 pre-existing functions; 117 after the Phase 0
  instrument check was added).
- 147 textual `def test_*` occurrences: 116 live + 31 inside inert archive
  strings — matching the directive's expected order of magnitude (~147).
- IMPORTANT precondition discovered: 10 of the 116 pre-existing tests
  verify battery ARTIFACTS (`forge_results.json`, `closure_scan.json`,
  `file_world_results.json`, `cfs_results.json`, `expansion_results.json`)
  and fail with "artifact missing; run --mode X first" in a clean
  directory. This matches the repository's own Full Evidence CI order
  (batteries first, then `--mode test`) and `EVIDENCE.md`'s documented
  reproduction sequence. It is a documented precondition, not a
  pre-existing failure: with the batteries run first, all tests pass
  (outputs below).
- Both suites were therefore run in the documented order in a clean
  isolated working directory: the seven evidence batteries, then
  `--mode test`, then `python3 -m pytest rsi_levels_metaforge_unified.py -q`.

All ten steps were executed in one clean isolated working directory in the
documented order. Step ledger (UTC; the native_test line at 23:23:21 was
interrupted by a session-container restart and re-run to completion at
02:11:07 against the same surviving battery artifacts):

```text
START py_compile 22:43:55
DONE py_compile rc=0 elapsed=0s
START file_battery 22:43:55
DONE file_battery rc=0 elapsed=1s
START forge_battery 22:43:56
DONE forge_battery rc=0 elapsed=1515s
START horizon_scan 23:09:11
DONE horizon_scan rc=0 elapsed=700s
START cfs_battery 23:20:51
DONE cfs_battery rc=0 elapsed=5s
START expansion_battery 23:20:56
DONE expansion_battery rc=0 elapsed=2s
START grammar_battery 23:20:58
DONE grammar_battery rc=0 elapsed=32s
START grammar2_battery 23:21:30
DONE grammar2_battery rc=0 elapsed=111s
START native_test 23:23:21
START native_test 02:11:07
DONE native_test rc=0 elapsed=1224s
START pytest 02:31:31
DONE pytest rc=0 elapsed=1129s
ALL_STEPS_COMPLETE
```

### 3a. Native suite output (`--mode test`, full, untruncated)

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
RESULT: 117 passed, 0 failed
ALL TESTS PASSED
```

### 3b. pytest output (`python3 -m pytest rsi_levels_metaforge_unified.py -q`, full, untruncated)

```text
........................................................................ [ 61%]
.............................................                            [100%]
117 passed in 1128.36s (0:18:48)
```

## 4. Baseline frontier (directive step 4)

`docs/BASELINE_FRONTIER.md` created: per-task SOLVED/OPEN for the 33
designer tasks (`T00`–`T32`) in both arms at default seeds/budgets
(SEED=2026, DATA_SEED=11, GATE_SEED=2027, CF_GATE_SEED=4099, WAVES=8,
RESTARTS_PER_TASK=6, ITERS_PER_RESTART=550).

- Adaptive arm: 23 designer SOLVED / 10 OPEN
  (OPEN: T15, T18, T21, T22, T23, T26, T29, T30, T31, T32);
  plus 12 self-generated (`G##`) adoptions; digest `39d26f1080d4a89b`.
- Frozen arm: 19 designer SOLVED / 14 OPEN; digest `e5dc308324bb10f6`.
- Adaptive-only baseline delta over frozen: T11, T12, T27, T28.
- Determinism (GR3): both arms re-run; saved runstate JSONs byte-identical
  across consecutive runs.

## 5. Frozen evaluation instrument (directive step 5)

- `docs/frozen_holdout_phase0.json` (711,147 bytes): materialized dual
  sealed-gate streams (40 holdout + 30 counterfactual pairs per task) for
  all 33 designer tasks, built ONLY from pre-existing designer task
  definitions by `docs/make_frozen_holdout_phase0.py`, following the
  file's existing holdout convention (length extrapolation: train lengths
  (1,2,3,4,6) vs holdout (5,8,13,21,34) / cf (6,9,14,22,30) with
  out-of-range values 0..15).
- SHA-256: `527bb04dd45c010a32637a92eeba5a799024a9a68e944e5c91186d3daa3f4d24`
  (generation is deterministic; two consecutive generations byte-identical).
- Freeze check (GR4 "hash checks are tests"):
  `test_frozen_holdout_phase0_instrument_intact` ADDED to the native
  suite — verifies the byte hash and re-derives every pair from the gate
  RNG convention. No existing test was modified (GR1).
- Cross-validation at creation: for all 33 tasks, the JSON's input streams
  match `_make_gate`'s RNG streams exactly and each task's oracle passes
  its live sealed gates.

## 6. Ground-rule compliance notes

- GR1: no existing test touched; one test added.
- GR3: determinism verified for both baseline arms (byte-identical
  runstate JSONs) and for instrument generation.
- GR6: top-VM constants confirmed at lines 94–101
  (`MAX_PROGRAM_LEN=14`, `MAX_STACK=32`, `MAX_MACROS=24`); the second
  namespace (`MAX_STACK=64`, `MAX_PROGRAM_LEN=60`) confirmed INSIDE the
  archived `open_ended_rsi` string (verbatim capture taken for the future
  Phase A invariance test).
- GR7: no reformatting or consolidation outside the stated scope.
- GR8: vocabulary constraints observed.
- GR12: runtime remains stdlib-only. pytest was installed in the session
  container as a dev tool solely to execute the directive's required
  pytest command; it is not a runtime dependency and nothing in the repo
  imports it.

## 7. Facts about the environment worth carrying forward

- `demo`/`counterfactual` modes and several batteries READ
  `adaptive.json`/`frozen.json` from the CWD as caches if present;
  baseline measurements must run from clean directories
  (documented in `docs/ENTRYPOINT_MAP.md`).
- `METAGATE_MAX_TASKS=12` is declared but never referenced; `meta_gate`
  probes ALL unsolved tasks (relevant when Phase A threads capacity
  through the searcher).
- SECTION 24 (lines 13239–13705) operates on the Section 23 CFS feature
  vocabulary (26 dims, `CFS_D`); Rule 1+2 are fused in
  `quest_extend_until_expressive`, Rule 3 is `SpeculativeLedger` +
  `speculative_round`. These are the semantics Phases A–C generalize.
- The printed `solved` count of `run-adaptive`/`run-frozen` includes
  self-generated (`G##`) tasks; designer-suite accounting must always
  filter to `T##` (relevant to GR5 in Phases B+).
