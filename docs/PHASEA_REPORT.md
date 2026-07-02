# Phase A Report — Capacity Growth for the Top Synthesis Core

Branch note: same deviation as Phase 0 — session rules mandate the single
designated branch, so Phase A is delivered as its own commit(s) on
`claude/gated-generalization-exploration-otka5i` instead of a
`phaseA-capacity` branch. Nothing touched `main`.

## A1 — CapacityConfig, threaded through the top core only

`CapacityConfig` (frozen dataclass; defaults `max_program_len=14`,
`max_stack=32`, `max_macros=24` — exactly the historical module constants)
is now a field of `SearcherState`, cloned with it, serialized in
`runstate_summary` and restored by `restore_runstate`. Capacity is part of
the searcher, so a grown candidate is A/B-compared against the incumbent
by the unchanged `meta_gate`, and any rollback of the searcher rolls
capacity back with it.

Threading points (all in the top core; GR6 respected — the embedded
`open_ended_rsi` namespace is untouched, now guarded by a test):

- VM: `run_base_program`/`compile_program` accept an optional per-execution
  `max_stack`; the guard in `_push` reads a one-slot active-bound holder
  (`_ACTIVE_MAX_STACK`), set and restored exception-safely per execution.
  Default = historical `MAX_STACK`.
- Search: `_random_tokens`, `_mutate`, `_mutate_drift`, and `synthesize`'s
  restart generator now cap program length at
  `state.capacity.max_program_len`; candidate scoring runs the VM at
  `state.capacity.max_stack`.
- Macro budget: `mine_macros` caps at `state.capacity.max_macros`.
- Enumeration: `build_enum_table` became a thin wrapper that runs the
  unchanged enumeration (`_build_enum_table_inner`) under the searcher's
  `max_stack`. Enumeration budgets (`ENUM_SURFACE_MAX`, `ENUM_CLASS_CAP`,
  `ENUM_STACK_DEPTH`) are budgets, not capacity, and stay identical across
  A/B arms.
- Gate-side compiles in `meta_gate` and adoption-side compiles in
  `run_wave` execute at the owning searcher's capacity.

Not threaded (documented, deliberate): the PRM feature normalization
constant (`len(prefix)/MAX_PROGRAM_LEN`, already clamped to 1.0), PRM/WM
prefix executors, and the mint factory's `_macro_transform` — all
search-shaping or environment-side paths that never gate adoption. They
run at the historical default bound.

## A2 — Growth trigger, gate discipline, bounds

- Trigger reuses the run's existing stagnation condition verbatim: the
  `fresh_adopt == 0 and not fresh_frontier` branch of `run_system` (the
  pre-existing `GATE_SKIPPED_NO_FRESH_MATERIAL` case), additionally
  requiring at least one designer task OPEN. No new metric was invented.
- A growth attempt proposes the next rung of a deterministic ladder
  (`next_capacity_rung`): `max_program_len +6`, `max_stack ×2`,
  `max_macros +24` per rung, clamped to the default bounds
  `≤56 / ≤128 / ≤96`. At the bounds, `GROWTH_BOUND_REACHED` is logged and
  nothing is proposed.
- The rung rides an ordinary `ImprovementProposal` (new optional
  `capacity` field; `None` for all pre-existing proposal paths) through
  the **unchanged** `meta_gate`: acceptance still requires ≥1
  previously-unsolved task whose candidate-table program passes the sealed
  holdout + counterfactual gates at identical enumeration budgets (GR2).
  Macros are re-mined under the grown macro budget so the extra width has
  material to spend; the incumbent table and the candidate table each run
  at their own capacity (that is the A/B treatment; budgets and seeds are
  identical).
- Rejected rungs enter `rejected_digests` (capacity included in the
  digest, so growth digests cannot collide with ordinary proposal
  digests); an identical re-proposal is skipped, a changed one (new
  adoptions since) may retry. The frozen arm never reaches any proposal
  machinery and can never grow.
- Runtime bound: at most one growth attempt per stagnant non-final wave
  (≤ WAVES−1 = 7 per run), each costing one `meta_gate` evaluation at the
  standard enumeration budgets — the same cost class as any ordinary
  proposal. Measured: the baseline adaptive run has **zero** stagnant
  waves, so the default run attempts no growth and its runtime is
  unchanged (3m35s vs 3m30s baseline, ≈2% — the `_push` indirection).

## A3 — Growth event logging

Every attempt (adopted or rejected) appends to `rs.growth_log`:
wave, trigger values (`fresh_adopt`, `fresh_frontier`, OPEN designer ids),
old → new capacity for all three dimensions, accepted flag, the half-open
range of `gate_records` indices produced by the attempt, and the proposal
digest. `GROWTH_ADOPT` / `GROWTH_REJECT` / `GROWTH_BOUND_REACHED` events
land in the event log. The growth log is serialized and restored with the
runstate. The audit invariant — a capacity change without an accepted,
contiguous growth chain is a bug — is enforced by test.

## A4 — New tests (5 added; no existing test touched)

1. `test_capacity_defaults_and_second_namespace_unchanged` — historical
   constants intact; `CapacityConfig()` defaults equal them; ambient VM
   bound at rest; embedded `open_ended_rsi` literals (`MAX_STACK = 64`,
   `MAX_PROGRAM_LEN = 60`, siblings) unchanged (GR6).
2. `test_capacity_growth_ladder_bounded` — ladder is monotone, terminates
   exactly at the declared bounds, and proposes nothing beyond them.
3. `test_capacity_growth_fires_under_synthetic_stagnation` — a synthetic
   stack wall (`max_stack=1`, `sum+count` sealed task): the attempt is
   gate-accepted, capacity moves exactly one rung, the growth log carries
   the trigger, old→new values, and an accepted gate record, and the
   grown table reaches the wall task.
4. `test_capacity_growth_never_fires_in_healthy_run` — frozen arm never
   grows; the baseline adaptive run (fresh material every wave) attempts
   no growth and keeps default capacity; accepted-chain audit; no attempt
   without an OPEN designer task.
5. `test_capacity_growth_log_deterministic` — two-run byte-identical
   growth logs; capacity and growth log survive the serialization
   round-trip.

## Behavioral regression evidence

- Default-capacity adaptive run reproduces the Phase 0 digest exactly:
  `{"solved": 35, "digest": "39d26f1080d4a89b"}`; adopted task sets
  byte-equal to Phase 0 for both arms.
- Two consecutive runs of each arm: saved runstate JSONs byte-identical
  (GR3).

## Acceptance outputs

Both suites run in the artifact-bearing official directory (battery
artifacts generated by the Phase 0 official run; the artifact-producing
subsystems are untouched by Phase A).

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
RESULT: 122 passed, 0 failed
ALL TESTS PASSED
```

### pytest (`python3 -m pytest rsi_levels_metaforge_unified.py -q`, full, untruncated)

```text
........................................................................ [ 59%]
..................................................                       [100%]
122 passed in 843.31s (0:14:03)
```


## Notes carried forward

- In the current baseline no wave is stagnant, so growth is present but
  latent; Phase B's generated-task pressure may change wave dynamics, in
  which case `test_capacity_growth_never_fires_in_healthy_run`'s
  baseline-fact assertion (`growth_log == []` for the memoized baseline)
  will be re-examined in that phase's report if it fires — the audit
  invariants are the durable part of the test.
- `METAGATE_MAX_TASKS` remains declared-but-unused (pre-existing; not
  touched under GR7).
