# Ascent Phase N — Proof Kernel & Formal Domain — Frozen Specification (N-1)

Spec-freeze document for the Ascent directive, Phase N (module M3). Every
constant, axiom, grammar set, and protocol rule below is frozen at commit
time, BEFORE the first `--mode ascent-n-battery` evidence run. Post-hoc
changes require a new predictions file. Predictions:
`docs/PREDICTIONS_N.md`; results: `docs/N_RESULT.md`. Phases K/L/M are
read-only under this phase.

## 1. Mission and claim boundary

An honestly open formal domain with zero external-oracle demand: a
propositional proof kernel, audited once and then frozen (K6), inside the
K-1 setter–solver discipline. The system poses its own conjectures,
refutes false ones by bounded countermodel search, proves true ones under
budget, and adopts ONLY kernel-checked theorems — never axioms. The scope
note from the directive is registered verbatim: propositional calculus is
decidable, so this domain's frontier is derivation-reachability under
budget (and MDL compression), not truth-reachability; deeper axiom bases
are a pre-registered amendment path, not a v0 requirement.

## 2. The kernel (K6 — frozen after the audit)

A Hilbert-system checker for propositional logic over implication and
negation (Łukasiewicz axioms), in pure stdlib, structural checking only:

- Formulas: `("v", i)` for variables (i < AN_MAX_VARS),
  `("not", f)`, `("imp", f, g)` — nested tuples, canonically serialized
  for identity.
- Axiom schemas (the FROZEN axiom base; instantiation = substitution of
  formulas for schema variables):
  - A1: `φ → (ψ → φ)`
  - A2: `(φ → (ψ → χ)) → ((φ → ψ) → (φ → χ))`
  - A3: `(¬φ → ¬ψ) → (ψ → φ)`
- Inference: modus ponens only.
- Proof object: a list of steps; each step is
  `("ax", axiom_id, substitution)` or `("mp", i, j)` with `i, j` prior
  step indices. `an_check_proof(proof, goal)` verifies every step
  structurally, bounds total steps (`AN_MAX_PROOF_STEPS`) and formula
  size (`AN_MAX_FORMULA_SIZE`), and accepts iff the last step's formula
  equals the goal exactly.
- Adoption API: `an_adopt_theorem(library, formula, proof)` — the ONLY
  path into the theorem library; it calls the kernel and refuses anything
  unchecked. There is no axiom-adoption API at all; the negative test
  constructs the attempt (an "axiom" is a proof-less adoption) and
  asserts refusal.
- Audit checklist (recorded in `docs/N_RESULT.md` at freeze): totality
  (every input terminates: step count and formula size are bounded before
  checking), no dynamic evaluation, no I/O, no randomness, no wall-clock;
  structural equality only; determinism by construction; kernel source
  ≤ 500 lines including the audit-relevant helpers; source SHA-256 bound
  into `ASCN_PIN_SHA256`.

## 3. Conjecture setter (M1 variant: no witness)

Lineages enumerate candidate formulas from the typed grammar over
variables `p0..p2`, `imp`, `not`, plus gate-adopted theorem-library
abbreviations as units (the K-1 archive-unit discipline transplanted);
band = formula size in grammar nodes. Registered lineage policy (mutable
citizen, disclosed at freeze): implication-rooted candidates only
(negation-rooted tautologies are double-negated theorems, out of the
pool-restricted prover's reach by construction); setter-side truth-table
screening — the SC-1 feasible-by-construction discipline: the setter
offers only claimed tautologies, the admission gate re-runs the
countermodel search hermetically, and the ADV probe keeps the refutation
path firing on record every generation; lane partitioning (index mod 3)
so overlapping band ladders never re-propose each other's candidates; and
bands step by two (implication-rooted tautologies live at odd sizes; even
bands are contingent-dense dead zones for this grammar). Admission
certificates, frozen order:

- `n0_malformed` — well-formedness and size bounds.
- `nr_refuted` — **the refutation path**: bounded countermodel search
  (complete truth-table over the formula's ≤ `AN_MAX_VARS` variables); a
  falsifying assignment refutes the conjecture, which is archived as
  `refuted` with its countermodel in the ledger. Refuted conjectures are
  terminal (never posed again — their signature is claimed).
- `nd_duplicate` / `nd_cell_occupied` — novelty: exact dedup on the
  canonical formula (truth-table identity cannot serve here: every
  tautology shares the all-true table, so table-level dedup would
  collapse the whole domain into one cell — registered before freeze),
  then descriptor-cell occupancy with cell = (n_vars, size bucket, depth
  bucket, connective-profile bucket). Same-shape re-skins collide on the
  cell; structurally new formulas (e.g. double negations of a known
  theorem) are honestly new derivability targets and are admitted on
  their own merits.
- `nb_too_easy` — difficulty: the frozen frontier prover (§4) derives the
  formula within `ASCN_B_EVAL` derivation expansions → rejected.

Admitted conjectures enter the open queue, capped at `ASCN_QUEUE_CAP`
with horizon decay exactly as K-1 frontier markers (uncrossed after
`ASCN_H` generations → `frontier_marker`, signature stays claimed).

## 4. Prover (solver) and theorem crossings

`an_prove(goal, library, budget)` — deterministic forward saturation in
the subformula universe: the candidate pool is the subformula closure of
the goal plus the library formulas up to `AN_MAX_FORMULA_SIZE`; axiom
instances are enumerated over the pool in canonical order; modus ponens
closes over proved formulas; every instantiation or MP attempt spends one
derivation expansion from the budget (the K4 logical-budget currency for
this domain). Returns a kernel-checkable proof object or None.

- **Mining**: open conjectures are attempted at `ASCN_B_LIVE` (and
  re-attempted while open whenever the theorem library has grown since
  the last attempt — the subformula pool is library-fed, so growth
  genuinely changes the search space); a proof is kernel-checked and the
  theorem adopted into the library (with its proof in the ledger —
  proofs are public data, like solution bodies). Every formula derived
  inside an adopted proof is itself a kernel-checked theorem: novel MP
  conclusions and novel axiom instances are adopted with their extracted
  proof slices (capped at 8 per proof), ledgered as `step_adopted` /
  `step_adopted_ax`. N1 reports the composition split (goal, MP-step,
  axiom-instance-step) — an axiom-instance THEOREM carries a one-step
  kernel proof and is not an axiom adoption; the axiom BASE is frozen
  data the kernel owns, and no API can extend it.
- **Crossing**: per generation, each open conjecture is attempted at
  exactly `ASCN_B_EVAL` with the current library; the admission record
  already proves the admission-time library failed at the same budget.
  Library entries whose source conjecture is the conjecture itself are
  excluded (the K-1 no-self-credit rule). A crossing credits its lineage
  within `ASCN_H`.

## 5. MDL-driven interestingness (M2 applied to the theorem library)

The registered K5 formula shape, parameterized by this domain's alphabet
(`AN_ALPHA` = imp, not, p0..p2 → 5 core tokens): theorems are encoded in
prefix notation; the theorem corpus is the adopted-theorem encodings; an
abbreviation library grows ONLY through the L-1 master gate (strict
negative training delta on the theorem corpus; holdout validation against
the frozen `docs/frozen_holdout_ascentN.json` — a committed corpus of
tautology encodings generated once at freeze, SHA-pinned). Every theorem's
ledger record carries its codelen under the library at adoption time —
the computable interestingness signal that replaces hand-written
heuristics: the conjecture lineages' unit sets grow from gate-adopted
abbreviations, so enumeration order follows measured compression, not
taste.

## 6. ADV probes (every gate fires on record)

Per generation: a malformed emission (fails n0), a non-tautology
(`p0 → ¬p0` family — refuted via countermodel: the refutation path is
exercised every generation on record), an axiom instance (fails
nb_too_easy at generation 0, nd_duplicate after), and its twin (fails
nd_duplicate). An ADV admission aborts the battery. The axiom
self-adoption attempt is additionally red-teamed in-suite: adopting a
formula with a forged or absent proof raises, and the library after every
battery run contains zero entries lacking a kernel-checked proof.

## 7. Frozen constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `ASCN_SPEC_VERSION` | "N-1" | |
| `AN_MAX_VARS` | 3 | variables p0..p2 |
| `AN_MAX_FORMULA_SIZE` | 13 | grammar nodes per formula |
| `AN_MAX_STEP_SIZE` | 128 | proof-step formula-size bound |
| `AN_MAX_PROOF_STEPS` | 512 | kernel proof-length bound |
| `ASCN_B_EVAL` | 20 | frontier/crossing derivation budget |
| `ASCN_B_LIVE` | 20000 | mining derivation budget |
| `ASCN_GENERATIONS` | 8 | battery generations |
| `ASCN_H` | 5 | crossing horizon |
| `ASCN_QUEUE_CAP` | 24 | open-conjecture cap |
| `ASCN_POSE_SLOTS` | 6 | non-ADV pose slots per generation |
| lineage bands at start | N_A 3, N_B 5, N_D 7 | size-band ladders (ratchet as K-1) |
| `ASCN_CANDS_PER_GEN` | 32 | abbreviation candidates per generation |
| `ASCN_HOLDOUT_SHA256` | `583dcc7d80b867d3a1242cf3f538e75587491d179a45274f491db6308f0b4665` | frozen tautology-corpus pin |
| `ASCN_PIN_SHA256` | `738d2ddd0e2f5794fe5ababd3bb8e33109193952a50f38e2017fb1a60d152bca` | kernel + constants pin |

## 8. Metrics, digest, artifacts

- **N1 (headline)**: cumulative adopted-theorem count per generation
  (target ≥ 20 across the battery), each entry kernel-checked, with
  proof length and codelen-at-adoption.
- **N2**: refutation record (≥ 1 required; ADV guarantees one per
  generation) with countermodels in the ledger.
- **N3**: crossing record (admitted conjecture unproved at `B_EVAL` →
  proved at the same budget later), the K-1 certificate discipline.
- **N4**: the abbreviation-gate record (adoptions/rejections with exact
  bit deltas) and the per-theorem interestingness signals.
- **N5**: zero axiom adoptions (a counted assertion over the full
  ledger, plus the in-suite negative test).
- Battery digest `an_digest`; two byte-identical runs asserted in CI;
  artifacts `reports/evidence/ascent_n_results.json` / `_ledger.jsonl`;
  run-1 copies committed as `docs/final_ascent_n.json`,
  `docs/ascent_n_ledger_final.jsonl`.

## 9. Scaled configurations (also frozen)

- `--mode ascent-n` (demo, CI-safe): generations 3, pose_slots 6,
  b_eval 20, b_live 8000, H 3.
- Test configuration (`_an_test_cfg`): generations 2, pose_slots 4,
  b_eval 20, b_live 6000, H 2.

## 10. Known boundaries (disclosed at spec-freeze)

- Decidability: truth-table search settles truth for every candidate;
  the measured frontier is derivability-under-budget. This is the
  directive's own scope note, registered.
- The Hilbert prover is weak by construction (no deduction theorem, no
  resolution; substitution values come only from the subformula pool);
  many admitted conjectures retire as frontier markers. The N1 target is
  met by mining at `B_LIVE`, not by frontier crossings.
- **Crossings are expected to be rare or zero in this domain at these
  budgets**: a crossing re-proof at `B_EVAL` = 20 must beat pool-squared
  axiom-instantiation sweeps, and the library-fed pool GROWS as theorems
  accumulate. The K-1/L-1 records carry the crossing story; N's
  contribution is the kernel, the refutation path, and the theorem
  economy. A context-ordered prover is registered as a Phase O Channel A
  candidate (the Phase M amortizer transplanted to this domain).
- `AN_MAX_STEP_SIZE` = 128 bounds proof-step formulas separately from the
  size-13 conjecture bound: the classic five-step proof of `p → p`
  passes through a size-17 instance, and the deduction-theorem proof
  objects of the Phase O schema skeletons pass through ~70-node
  instances, so a single shared bound would make the kernel vacuously
  strict (measured before freeze). `AN_MAX_PROOF_STEPS` = 512 for the
  same reason (the schema proofs are 161 steps).
- Conservative definitions are implemented as gate-adopted abbreviations
  (pure notation, conservative by construction); a richer definitional
  mechanism and any axiom-base extension (FOL, arithmetic) are
  constitution amendments requiring an owner-pre-registered spec, never
  self-granted — the negative test enforces the absence of any such path
  in code.
- Kernel audit is self-audit against the §2 checklist; external audit is
  invited (the checklist and the ≤ 500-line source region make the
  surface small).

## 11. Calibration disclosure

The loop portion under exactly these constants was observed before this
freeze and is disclosed as known-at-prediction-time in
`docs/PREDICTIONS_N.md`. After this freeze, no constant changes; the
battery runs as-is and its record ships as measured.
