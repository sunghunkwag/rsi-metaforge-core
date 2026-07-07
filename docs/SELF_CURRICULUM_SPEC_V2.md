# Fence Expansion — Frozen Specification (SC2-1)

Spec-freeze document for Directive 2 (Phase SC2). Every constant, seed,
budget, threshold, grammar set, and protocol rule below is frozen at commit
time, BEFORE the first `--mode sc2-battery` evidence run. Post-hoc changes
require a new predictions file; this one stays committed. Predictions:
`docs/PREDICTIONS_SC2.md`; results: `docs/SC2_RESULT.md`. Directive 1
(`docs/SELF_CURRICULUM_SPEC.md`, SC-1) remains fully binding; all Phase SC
invariants I1–I14 apply unchanged to every task minted under any schema.

## 1. Mission and claim boundary

Directive 1 generated task *instances* inside a frozen fence. Directive 2
makes the fence itself an evolution target: the system invents new task
*kinds* (schemas) as **pure data** over a small, human-frozen algebra of
check-forms; problem material can come from hash-pinned external corpus
snapshots; substrates are packaged as capsules whose products open task
kinds no human enumerated.

Claim boundary, verbatim from the directive: *the check-form algebra is the
new fence. This directive moves the boundary one level up and measures
whether the move pays; it does not remove the boundary.*

## 2. Components

- **C6 Schema Forge** (`SC2SchemaForge`): deterministic enumerator over the
  closed schema grammar, band-major with templates innermost so all four
  templates (and thus the corpus tap and capsule products) appear within
  the first generation of proposals. A schema is a dict with EXACTLY the
  keys `(template, checkset, relset, band)` drawn from frozen id sets —
  no executable payload of any kind (I16).
- **C7 Meta-Checker Algebra** (frozen, human, hash-pinned): exactly five
  check-forms — CF1 witness-replay equality, CF2 round-trip identity, CF3
  metamorphic relation battery, CF4 differential agreement (a second
  solver run under the frozen reversed vocabulary order must agree on the
  sealed inputs), CF5 sealed-holdout equality. CF1 and CF5 are
  mechanically identical in this harness (the harness labels sealed
  inputs by replaying the witness); both names are kept for auditability.
  The relation library is frozen code; schemas only select ids:
  R1 permutation equivariance (reversal probe), R2 duplication
  invariance, R3 idempotence, R4 involution, R5 concatenation
  homomorphism, R6 constant-shift commutation, R7 record-projection
  consistency (even-index probe). Every relation is a LABEL-FREE property
  of the candidate function; sealed labels are consumed only by the
  equality forms.
- **C8 Corpus Tap**: `docs/CORPUS_MANIFEST_SC2.json` (snapshot script
  `docs/make_corpus_manifest_sc2.py`, run once) pins four frozen
  exploration-side artifacts by SHA-256 — public shard
  {exploration_archive_phaseD.json, anchor_report_phaseE.json}, sealed
  shard {exploration_archive_phaseG.json, anchor_report_phaseG.json}.
  Files are read as byte streams mod 8; the harness derives file choice
  and offsets from the task id hash (I9). The corpus supplies
  distributional material, not answers and not goals. The sealed shard is
  readable only inside the M7 evaluator (I21).
- **C9 Domain Capsules** (`SC2_CAPSULES`, frozen data): vm_int and
  vm_list, each with value space, primitive set, invertible subset,
  sampler, cost model, and the frozen codec pair ENC8/DEC8 (token ids
  500/501; 4 base-8 digits; domain [0, 4096)). Codec tokens exist only in
  the SC2 executor/solver and never leave SC2 (never offered to the
  frozen-instrument machinery). The gd/file-world substrates are NOT
  packaged in v1 — no frozen template consumes them (deviation recorded
  in `docs/SC2_RESULT.md`).
- **Poser v2** (`SC2PoserV2`, additive subclass behind the frozen
  `SC2_POSER_V2 = True` flag, sc2 paths only): unit production weights
  are integer counts of each unit's token body inside adopted archive
  expansions; ties break on the canonical v1 index; no floats anywhere in
  the ordering path (I23). D1 paths keep v1; the D1 battery digest is
  unchanged.

## 3. Templates (frozen harness logic)

- `T_A`: D1 Track A affine chains (vm_int).
- `T_B`: D1 Track B pipelines (vm_list).
- `T_BC`: Track B pipelines whose instances are drawn from the corpus
  public shard. Ordered before T_B in the forge so corpus-fed families
  claim their behavioral territory first (task signatures are
  input-independent, so T_B duplicates T_BC by I4/I18 — recorded, not
  hidden).
- `T_X`: cross-capsule product — affine steps split around the codec
  block `ENC8 · REVL · DEC8` (encode base-8, reverse the digit record,
  decode). Band = 1 + pre-steps + post-steps; pre-steps additive only
  (codec-domain safety, input domain [0, 4000]); post-steps use the full
  invertible step set. The witness inverse composes exactly; the frozen
  baseline can never solve T_X (its vocabulary has no codec), so I5
  passes by construction and the family's solvability is a pure test of
  cross-capsule library compression.

## 4. Frozen constants

| Constant | Value |
| --- | --- |
| `SC2_GENERATIONS` / `SC2_CHECKPOINTS` | 8 / (0, 4, 8) |
| `SC2_FORGE_PER_GEN` | 3 |
| `SC2_MINT_PER_SCHEMA` / `SC2_MINT_SCAN` | 2 / 12 |
| `SC2_N_FEAS` / `SC2_FEAS_SCAN` / `SC2_B_SCHEMA` | 3 / 96 / 120000 |
| `SC2_KILL_MIN` (I15) | 4/5 over ≤ 10 mutants |
| `SC2_MUTATION_OPS` | (SUB, DEL, DUP, SWP), frozen positions order |
| `SC2_DISC_K` / `SC2_DISC_MIN` | 8 / 3/4 (vacuous-pass if < 2 archive programs, ledgered) |
| `SC2_COLLUDE_MAX` (I17) | 1/2 |
| `SC2_PROBATION_WINDOW` | 4 generations |
| `SC2_M5_DELTA_MIN` / `SC2_M5_EVAL_TASKS` | 1 / 6 (most recent other-schema tasks) |
| `SC2_M7_EVAL_TASKS` | 6 |
| `SC2_B_FROZEN` | 1500 (the D1 entry rung) |
| solver budgets | D1's `SC_B_LIVE` = 25000, `SC_B_WITNESS` = 4096, MDL α = 1/2 + 24 tokens |
| `SC2_MASTER_SEED` | 411941 |
| `SC2_ENC8` / `SC2_DEC8` / width / domain / `SC2_X_VMAX` | 500 / 501 / 4 / 4096 / 4000 |
| checksets | ((5,), (2,5), (1,5), (4,5), (3,5), (2,3,5), (1,3,5), (3,)) |
| relsets | ((4,), (6,), (7,), (3,), (4,6), (5,7), (1,2), (2,)) |
| bands | (2, 3, 4) |
| `SC2_CORPUS_MANIFEST_SHA256` | `072589506828cfe8885ac4c37a0adbc03bdd50aae1c7668261cc72f5e3f77143` |
| `SC2_PIN_SHA256` | `2b8e828003a924ff4aa222fe476841c9da877362eb529d4ac5fd04a722d574c2` |

The SC2 pin input is the concatenated source of every pinned component
(codecs, executor, solver, corpus tap, all seven relations, the check-form
dispatcher, grammar validator, template instantiator, task admission,
mutation operators, collusion check, schema gate, forge, poser v2, loop,
ablation, sealed-shard evaluator, metrics) PLUS the canonical dump of every
constant above including the corpus manifest hash — extending the algebra,
the relation library, or the mutation operators at runtime flips the pin
and aborts the battery (I22). The battery also asserts its configuration
against literal spec values.

## 5. Schema lifecycle

`schema_generated` → admission gate, in frozen order, every failure
ledgered: grammar validation (I16, `i16_code_escape`) → feasibility (≥ 3
tasks pass the full D1 I1–I9 battery within ≤ 96 candidates / `B_SCHEMA`
evaluations, AND their witness-derived solutions satisfy the schema's own
check battery — a schema describes a task family; `i6_infeasible`) →
mutation-kill soundness (I15, `i15_vacuous`) → discrimination
(`i15_indiscriminate`) → non-collusion (I17, `i17_collusion`) → behavioral
novelty (I18, `i18_duplicate_schema`) → `schema_admitted`, **probation**.

Probation solves earn `credit_provisional` records only. Permanence
requires M5 transfer credit: an ablation A/B (archive with vs without the
schema's adopted solutions, both solving the 6 most recent other-schema
tasks at the same live budget) with delta ≥ 1; conversion is an explicit
`credit_permanent` record listing the converted task ids. Schemas without
transfer inside 4 generations are `schema_retired`; their records and
provisional credits remain permanently visible (I11/I19). Task signatures
(I4) are global across schemas — behavioral territory is claimed once,
ever; later same-family schemas starve honestly and the ledger shows it.

## 6. Metrics

- **M5** per-schema ablation deltas (the permanence criterion), plus a
  frozen-anchor ablation report (`sc_transfer_eval` with vs without the
  schema's pure-base bodies) for at most the first 2 permanent schemas.
- **M6 (headline)**: cumulative permanent-schema count per generation,
  alongside the M1 curve restricted to permanent credit. Provisional
  credit is reported separately and never merged (I19).
- **M7**: sealed-shard solve score, computed only inside the gate at the
  final checkpoint (g0 is definitionally empty); solutions are never
  adopted and results never reach the forge or poser.
- D1's M1–M4 semantics continue for sc2 tasks (per-generation rows with
  full-denominator accounting from the verified hash chain).
- Battery digest: `sha256(ledger_head + canon(metrics))[:16]`, printed as
  `sc2_digest`; CI runs the battery twice and asserts equality plus
  byte-identical artifacts (`reports/evidence/sc2_battery_results.json`,
  `reports/evidence/sc2_ledger.jsonl`).

## 7. Scaled configurations (also frozen)

- `--mode schema-forge` (demo, CI-safe): generations=2, forge_per_gen=3,
  mint_per_schema=1, m_inputs=16, m_public=5, b_frozen=800, b_live=8000,
  probation_window=1.
- Test configuration (`_sc2_test_cfg`): generations=2, forge_per_gen=2,
  mint_per_schema=1, m_inputs=16, m_public=5, b_frozen=400, b_live=6000,
  probation_window=1.

## 8. Known boundaries (disclosed at spec-freeze)

- CF1 ≡ CF5 mechanically in this harness (single-witness labeling); the
  distinction becomes real only with independent labelers.
- CF4's second solver run is gate-side compute, excluded from the
  matched-compute accounting (it mints no capability).
- R6 passes vacuously on scalar-valued images (outside the relation's
  domain); schemas leaning on that vacuity die at the mutation-kill probe
  — observed in calibration as `i15_vacuous` rejections.
- Relation-only checksets are structurally hard to make sound; the
  full-pipeline path to `i17_collusion` is blocked earlier by I4/I15 in
  every configuration tried (defense in depth). The non-collusion check is
  therefore red-teamed at the enforcement layer with its gate wiring
  asserted on source.
- Task-signature globality means schema starvation is expected late in a
  run (`i4_duplicate` floods in the ledger are the visible evidence).
- The M5 ablation measures MARGINAL value given the rest of the archive;
  sibling-macro redundancy legitimately yields zero deltas.

## 9. Calibration disclosure

Constants were calibrated for feasibility on prototype runs before this
freeze: `SC2_B_FROZEN` at 6000 killed the band-2 bootstrap rung (a full
stall, 0 solves — the run is disclosed); at 1500 (the D1 entry rung) the
loop lives. The forge ordering was switched from template-major to
band-major/template-innermost after the T_A block was observed to consume
all proposals. The final calibration run of the loop portion under exactly
these frozen constants was observed and is disclosed as
known-at-prediction-time in `docs/PREDICTIONS_SC2.md`. After this freeze,
no constant changes; the battery runs as-is and its curves ship as
measured.
