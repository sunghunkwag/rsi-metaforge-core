# Ascent Phase M — Ledger-Trained Amortizer — Frozen Specification (M-1)

Spec-freeze document for the Ascent directive, Phase M (module M5). Every
constant, seed, model form, and protocol rule below is frozen at commit
time, BEFORE the first `--mode ascent-m-battery` evidence run. Post-hoc
changes require a new predictions file. Predictions:
`docs/PREDICTIONS_M.md`; results: `docs/M_RESULT.md`. Phases K and L
(`docs/ASCENT_K_SPEC.md`, `docs/ASCENT_L_SPEC.md`) are read-only under
this phase.

## 1. Mission and claim boundary

Amortize search: learn a proposal ordering from the system's own ledger —
and nothing else — and adopt it only if it strictly improves certified
gate passes per logical budget on a frozen probe battery whose task
families the model never trained on. The amortizer's entire epistemic diet
is what the gates certified: the adopted solution bodies of the committed,
chain-verified Phase K and Phase L final ledgers. No external data, no
pretrained weights, no floating-point transcendentals anywhere in the
model path (fixed-point integer arithmetic keeps replay byte-identical).
A model that fails the gate is rolled back, and the rollback ships as part
of the record.

## 2. Models

- **v0 — counting model** (`AMCountModel`): integer bigram counts over
  consecutive expanded base-op pairs of every training body, with a
  virtual start symbol before each body's first op and Laplace smoothing
  `+1`. Proposal scoring: a vocabulary token `t` (base op or library
  macro) in context `c` (the last expanded base op of the parent surface,
  or start) scores `count(c, first_op(t))`. Ordering: score descending,
  token id ascending on ties.
- **v1 — tiny neural model** (`AMNeuralModel`): a one-hidden-layer MLP in
  fixed-point integer arithmetic (scale 2^8): one-hot context (35 inputs:
  34 ops + start) → 16 ReLU units → 35 output scores. Manual backprop,
  integer SGD (learning-rate shifts, no floats, no exp), seeded
  initialization from `random.Random(ASCM_INIT_SEED)`, exactly
  `ASCM_EPOCHS` epochs over the training pairs sorted by
  (solution body SHA-256, position) — the ledger-hash data order the
  directive requires. Deterministic by construction.
- Both models order proposals inside `am_solve`: the K-1 breadth-first
  solver discipline with the per-parent vocabulary iteration order given
  by the model in the parent's context. With the null model (no
  reordering) `am_solve` reduces exactly to the canonical `sc_solve`
  order; the reduction is a tested identity.

## 3. Training corpus (the ledger, nothing else)

`am_training_corpus()` loads `docs/ascent_k_ledger_final.jsonl` and
`docs/ascent_l_ledger_final.jsonl`, verifies both hash chains, and
extracts the expanded bodies of every `mined` / `cross_adopted` record
(the gate-certified adoptions), in file order then ledger order. Every
training body must hash-match its ledger record; a tampered body aborts.
The Phase L seed corpus (the K bodies) appears once (deduplicated by
body).

## 4. The frozen probe battery (sealed holdout instrument)

The probe battery derives from the frozen Phase L holdout corpus
(`docs/frozen_holdout_ascentL.json`, SHA re-verified) — 48 program
families the training ledgers never contained (disjoint by construction;
the contamination test constructs the overlap attack and asserts abort).
Each program becomes a sealed task exactly as in the K-1 harness: Track A
programs yield inverse tasks (witness = the parsed exact inverse chain),
Track B programs yield forward tasks (witness = the program); checkers
are the K-1 constructors; instances derive from the task cid and
`ASCK_MASTER_SEED`; public labels by witness replay; hidden instances
sealed. A probe PASS for ordering `O` is a checker-certified,
MDL-capped solve within exactly `ASCM_B_PROBE` candidate evaluations.
`passes(O)` is the count over all 48 probes; per-probe costs are
recorded.

## 5. Adoption gate and rollback

Orderings are adopted sequentially against the incumbent (initially the
canonical fixed order), all under the same strict rule — adopt iff
`passes(candidate) > passes(incumbent)` at equal `ASCM_B_PROBE`, else
`rollback` (ledgered, incumbent unchanged):

1. v0, trained on the full corpus.
2. The pre-registered data-ablation retrain `v0_sliceA`: v0 retrained on
   the Track A slice of the training corpus only (a single body in the
   committed record — disclosed in §12: calibration shows this
   near-empty prior OUTSCORES the full v0 on the frozen battery, because
   most of the uplift is the learned INPUT-first root transition; the
   ablation ships to make that attribution part of the record).
3. v1, trained on the full corpus — the retrain whose gate failure
   demonstrates the rollback path live in the finals (calibration:
   v1 underperforms the then-incumbent; if the finals reproduce that, the
   rollback record is the required demonstration).

Every evaluation, adoption, and rollback is a ledger record carrying both
pass counts and the per-probe cost vectors. A guaranteed-failing
candidate (the adversarial inversion of the incumbent ordering) is
additionally constructed in the anti-cheat battery, so the rollback path
is red-teamed independently of the finals' dispositions.

## 6. Jurisdiction boundary: adoption into the live loop is Phase O scope

Phase M delivers the amortizer and its gate record on the frozen probe
battery. Wiring the adopted ordering into the live setter–solver loop is
an improver modification, and improver modifications ship through the
Phase O Channel A protocol (counterfactual A/B on frozen instruments) —
that is the directive's own module boundary, and the adopted Phase M
incumbent is registered here as the first Channel A candidate for
Phase O. Nothing in the M battery mutates the K-1/L-1 loop machinery.

## 7. Metrics, digest, artifacts

- **M1 (headline)**: the gate record — `passes(incumbent)`,
  `passes(v0)`, `passes(v0_trackA)`, `passes(v1)`, each with adoption or
  rollback disposition; certified passes per logical budget on the frozen
  battery.
- **M2**: per-track pass splits and per-probe cost vectors for every
  candidate (the attribution record behind M1).
- **M3**: training-corpus provenance (bodies, ledger heads, dedup count).
- Battery digest: `sha256(ledger_head + canon(metrics))[:16]`, printed as
  `am_digest`; two byte-identical runs asserted in CI; artifacts
  `reports/evidence/ascent_m_results.json`,
  `reports/evidence/ascent_m_ledger.jsonl`; run-1 copies committed as
  `docs/final_ascent_m.json`, `docs/ascent_m_ledger_final.jsonl`.

## 8. Frozen constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `ASCM_SPEC_VERSION` | "M-1" | |
| `ASCM_B_PROBE` | 1500 | probe-battery budget (candidate evaluations) |
| `ASCM_INIT_SEED` | 424987 | v1 weight-initialization seed |
| `ASCM_EPOCHS` | 8 | v1 training epochs (fixed) |
| `ASCM_HIDDEN` | 16 | v1 hidden width |
| `ASCM_SCALE_BITS` | 8 | fixed-point scale (2^8) |
| `ASCM_LR_SHIFT` | 4 | integer SGD step = gradient >> 4 |
| `ASCM_LAPLACE` | 1 | v0 smoothing |
| loop constants | Phase K/L values unchanged | |
| `ASCM_PIN_SHA256` | see runtime constant | kernel source + constants pin |

## 9. Scaled configurations (also frozen)

- `--mode ascent-m` (demo, CI-safe): probe battery restricted to the
  first 16 holdout programs, `ASCM_B_PROBE` = 1500.
- Test configuration: probe battery restricted to the first 12 holdout
  programs.

## 10. Anti-cheat battery (K7 extensions)

- **Contamination**: `test_am_holdout_contamination_aborts` constructs
  the attack — a training corpus containing a probe-family body must
  abort the battery (provenance check: every training body must
  hash-match a chain-verified adoption record; probe generators are
  checked disjoint from training bodies at battery start).
- **Rollback**: `test_am_rollback_on_failing_model` constructs an
  adversarial ordering (worst-case inversion of the incumbent) and
  asserts the gate rejects and the incumbent survives.
- **Null-model identity**: `am_solve` under the null model must equal
  `sc_solve` output and cost exactly on a probe sample.
- **Determinism**: v0 counts, v1 weights, probe pass vectors, and the
  full battery are two-run byte-identical (integer-only paths audited:
  the model source contains no float literals, `math.`, or `random.`
  outside the seeded init).
- **Ledger-only diet**: the amortizer namespace is AST-audited to
  reference no instrument stores, no vault symbols, and no corpus files
  other than the two committed ledgers and the frozen holdout loader.

## 11. Known boundaries (disclosed at spec-freeze)

- The training corpus is small (the K and L records are thin by honest
  construction); v0/v1 learn shallow op-transition statistics, not deep
  structure. The uplift claim is exactly `passes-per-budget on the frozen
  battery`, nothing more.
- The probe battery is same-substrate (SC unit grammars); cross-domain
  amortization is out of scope until the Phase N corpus exists.
- v1's fixed-point SGD with a tiny corpus can underfit v0's counts; the
  registered claim is that at least one of v0/v1 clears the gate
  (pre-verified in calibration, §12), not that v1 beats v0.
- The setter-side reweighting the directive names is exercised as the
  SC2 poser-v2 style unit-count weighting inside the loop run (its
  effect is ledgered); its ADOPTION discipline (Channel A jurisdiction
  over setter policy) is Phase O scope by the directive's own module
  boundaries.

## 12. Calibration disclosure

Calibration runs of the probe battery and both models under exactly these
constants were observed before freeze and are disclosed as
known-at-prediction-time in `docs/PREDICTIONS_M.md` (numbers therein).
After this freeze, no constant changes; the battery runs as-is and its
record ships as measured.
