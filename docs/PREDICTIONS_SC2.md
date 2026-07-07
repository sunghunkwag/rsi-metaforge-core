# Fence Expansion (SC2-1) Prediction Register

Committed and pushed BEFORE any `--mode sc2-battery` evidence run exists.
Scored in `docs/SC2_RESULT.md` after the runs, misses included.
Observations already made at prediction time are marked
**[known-at-prediction-time]**.

## Protocol under prediction

One battery configuration (frozen in `docs/SELF_CURRICULUM_SPEC_V2.md`:
SC2_GENERATIONS=8, forge 3/gen, mint 2/schema/gen (scan 12), N_FEAS=3,
kill_min 4/5, disc_min 3/4, collude_max 1/2, probation window 4,
M5 delta ≥ 1 over the 6 most recent other-schema tasks, B_FROZEN=1500,
B_LIVE=25000, SC2_MASTER_SEED=411941, corpus manifest
`0725895068…f77143`), executed twice with byte-identical `sc2_digest`
required.

## Known-at-prediction-time observations

1. **[known-at-prediction-time]** The loop portion was executed during
   calibration under exactly the frozen constants: 28 provisional solves
   over 8 generations (cumulative 5, 11, 17, 23, 26, 28, 28, 28), archive
   28, ~10 schemas admitted spanning all four templates (T_A, T_BC, T_X,
   T_B), schema rejections including `i18_duplicate_schema` (T_B
   duplicating T_BC's behavioral territory) and `i6_infeasible`
   (starvation late in the run), task rejections including `i4_duplicate`
   floods, `i5_frozen`, `i1_identity`, and `i8_archive`. Every M5
   ablation computed a delta of exactly 0 (sibling-macro redundancy), so
   **M6 ended at 0 permanent schemas** and every solved schema retired at
   its probation window. The battery must reproduce this loop portion
   exactly (same seeded code path).
2. **[known-at-prediction-time]** Cross-capsule T_X tasks were admitted
   (the frozen baseline can never solve them — no codec vocabulary) and
   solved during calibration: capability crossed the capsule codec.
   Corpus-fed T_BC tasks were admitted and solved with harness-owned
   corpus sampling.
3. **[known-at-prediction-time]** A superseded calibration configuration
   (B_FROZEN=6000, template-major forge order) produced a full stall
   (0 solves in 8 generations); it is disclosed in the spec's calibration
   section and was replaced before this freeze.
4. **[known-at-prediction-time]** An earlier calibration variant of the
   M5 ablation (chronological-first eval tasks, 2-task sets) produced a
   NEGATIVE delta for one schema (vocabulary pollution: extra macro
   tokens widen branching at fixed budget). Negative deltas are possible
   and will be reported as measured.

## Predictions

**P1 — Determinism.** Both battery runs produce byte-identical
`sc2_digest` values and byte-identical artifacts. Any divergence stops the
phase.

**P2 — Loop reproduction.** The battery's loop portion reproduces
observation 1 exactly: 28 provisional solves, archive 28, M6 = 0.

**P3 — Headline (M6).** The permanent-schema count stays at zero for the
whole run: every M5 ablation delta lands below the pre-registered
threshold (sibling-macro redundancy at B_LIVE=25000 makes each schema's
marginal contribution zero on the 6-task eval sets). Per Directive 2
Section 8, if this holds, the headline of `SC2_RESULT.md` is exactly that
sentence, unsoftened. A schema achieving permanence would be a positive
surprise reported with its full ablation table.

**P4 — Provisional/permanent separation (I19).** The provisional curve
(ending 28) and the permanent curve (ending 0) are reported separately in
every artifact; no provisional solve ever enters the permanent curve
without an explicit `credit_permanent` conversion record.

**P5 — M7 sealed shard.** The final-checkpoint sealed-shard evaluation
solves at least 1 of its ≤ 6 corpus-minted tasks (the archive holds
band-2 pipeline macros by then), and no sealed-shard solution is adopted
into the archive. If it solves 0, that null is reported.

**P6 — Fence-expansion evidence short of permanence.** At least one T_X
(cross-capsule) task and at least one T_BC (corpus-fed) task are solved
under schemas the frozen baseline provably cannot enter — the fence moved
(new task kinds were invented, admitted, and solved); what the move did
NOT buy, at these budgets, is measured transfer (P3).

**P7 — No incumbent regression.** The full suite passes at exactly 194
(178 incumbent + 16 SC2), zero failures, batteries-first order; the D1
battery digest `f56c6c13a2bf3028` and the Phase J record are untouched.

**P8 — Ledger integrity.** Every schema and every task lands in the
hash-chained ledger with an explicit disposition; retired schemas keep
their provisional credit visible; the two-run chain heads are identical.

## Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode sc2-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode sc2-battery   # run 2
# byte-identical sc2_digest required; artifacts under reports/evidence/
python3 rsi_levels_metaforge_unified.py --mode test          # 194 passed
```
