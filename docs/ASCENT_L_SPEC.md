# Ascent Phase L — MDL Master Gate — Frozen Specification (L-1)

Spec-freeze document for the Ascent directive, Phase L (module M2). Every
constant, seed, formula term, and protocol rule below is frozen at commit
time, BEFORE the first `--mode ascent-l-battery` evidence run. Post-hoc
changes require a new predictions file. Predictions:
`docs/PREDICTIONS_L.md`; results: `docs/L_RESULT.md`. Phase K
(`docs/ASCENT_K_SPEC.md`, `docs/K_RESULT.md`) is read-only under this
phase; Phase L reuses its kernel by call and mirrors loop code where
semantics change, exactly as SC2 did with SC-1.

## 1. Mission and claim boundary

One registered, frozen coding formula becomes the single value judge for
all vocabulary growth: an abstraction (macro) enters the solver's library
iff it strictly compresses the system's own corpus of gate-adopted
solutions AND strictly compresses a frozen, committed holdout corpus it
never trained on. Abstraction spam is impossible by construction: every
abstraction pays its own description length, and vocabulary growth itself
is charged through the code width. This unifies the Phase E instrument
(greedy re-encoding over a frozen archive, `docs/mdl_spec_phaseE.md`) and
the Phase J extension measurement (multi-vocabulary comparison with
per-primitive definition cost, `docs/measure_mdl_extension_J.py`) into one
adoption gate. The deliverable is the measured adoption/rejection record
and the retrofit MDL value scores over the Phase K archive; a run where
the gate rejects everything ships as-is.

## 2. The registered coding formula (K5 — frozen at this commit)

All quantities are exact integers (bits). For a library `L` of macro
bodies (each a fully expanded base-token tuple) over the core ISA of
`N_BASE_OPS` = 34 ops:

- Vocabulary width: `bits(L) = (34 + |L| - 1).bit_length()` — the
  fixed-width cost in bits of naming one token from the base ISA plus the
  library (integer ceiling of log2 of the vocabulary size).
- Encoding: `al_encode(p, L)` — deterministic greedy longest-match: scan
  the expanded program left to right; at each position emit the single
  longest matching library body as one token (two distinct bodies of equal
  length cannot both match), else emit the base token; advance by the
  match length. `n_enc(p, L)` is the emitted token count.
- Program cost: `codelen(p | L) = n_enc(p, L) * bits(L)`.
- Library cost: `codelen(L) = Σ_m (len(body_m) + 1) * bits(L)` — every
  abstraction is charged its full expanded body plus one naming token, at
  the current vocabulary width (the Phase E `defcost(m) = len(m) + 1`,
  generalized to bit units).
- Corpus cost: `MDL(C, L) = codelen(L) + Σ_{p ∈ C} codelen(p | L)`.
- Candidate delta: `ΔMDL(m; C, L) = MDL(C, L ∪ {m}) - MDL(C, L)`.

Because `bits(L)` applies to every term, growing the vocabulary across a
power-of-two boundary re-prices the whole corpus — vocabulary growth is
never free. Under a constant `bits`, the formula reduces exactly to the
Phase E token accounting; pricing non-base primitives through `len + 1`
naming terms subsumes the Phase J per-primitive convention inside one
formula. Relation to the directive's `log2(#choices)` form: the fixed-width
integer ceiling is the registered instantiation (chosen over floating
`log2` so that byte-identical replay never depends on a platform's libm).

## 3. Adoption rule (the master gate)

A candidate abstraction `m` is ADOPTED into the library iff

1. `ΔMDL(m; C_train, L) < 0` — strict, on the sealed training corpus
   `C_train` (§4): the abstraction pays its full description cost against
   the system's own data and still compresses it, and
2. `sav_hold(m; L) > 0` — the holdout-validation clause: re-encoding the
   frozen holdout corpus `docs/frozen_holdout_ascentL.json` (SHA-256
   `3f2c0d53739bdb3ae56af4a4a35d249dc549f0d09e26fe62ea4255838c192c49`,
   generated once by the committed `docs/make_frozen_holdout_ascentL.py`,
   seed 553211, 48 programs, disjoint from the loop's minting stream by
   construction) with `L ∪ {m}` must emit strictly fewer tokens than with
   `L`. The description cost is charged once, against the training data
   that motivated the abstraction (clause 1); the holdout clause is a
   generalization test — a train-only idiom that never occurs in unseen
   programs has `sav_hold = 0` and is rejected. The full
   `ΔMDL(m; C_hold, L)` is additionally recorded in every ledger record
   for audit. (Registered before freeze, with the measurement disclosed in
   §12: under a strict holdout delta the 48-program corpus cannot
   amortize any definition cost — every candidate ever measured has
   `ΔMDL_hold ≥ 0` — so a strict-delta clause is vacuous: it admits
   nothing and can reject nothing selectively. The savings clause is the
   non-vacuous registered form.)
3. the expanded body length is within `[ASCL_BODY_MIN, ASCL_BODY_MAX]`.

Both deltas and the holdout savings are recorded in the adoption ledger
record; every rejection is ledgered with its numbers and reason
(`l_mdl_train`, `l_mdl_holdout`, `l_body_bounds`). Judgments are
single-candidate, applied iteratively in a frozen order (§5); joint
re-encoding of multiple candidates is not claimed (the Phase E disclosure
carries over).

## 4. Corpus and candidate sources

- `C_train` is seeded at loop start with the six adopted solution bodies
  of the committed, chain-verified Phase K final ledger
  (`docs/ascent_k_ledger_final.jsonl` — the system's own ledger is its
  only training data, and the K record qualifies), and grows only through
  the sealed solve gate: solution bodies admitted by the Phase K checker
  discipline (mining and crossing events). Solutions always enter
  `C_train` (they are the data); the LIBRARY is what the master gate
  controls.
- Candidate abstractions, per generation, in frozen order:
  1. every full solution body newly added to `C_train` this generation
     (in adoption order), then
  2. every contiguous base-token subsequence of length
     `ASCL_BODY_MIN..ASCL_BODY_MAX` occurring in ≥ 2 distinct `C_train`
     programs (the Phase E enumeration), ordered by (training net saving
     descending, body lexicographic), capped at `ASCL_CANDS_PER_GEN`
     evaluations per generation.
- After each adoption the library changes, so subsequent candidates in the
  same generation are judged against the updated `L` (iterative greedy,
  deterministic).

## 5. The loop (mirrors Phase K; differences only where stated)

The Phase L battery runs the K-1 loop discipline (same lineages, ADV
probes, admission certificates, crossing measurement, credit, allocation,
meter, replay) with exactly two changes:

1. **Vocabulary = library.** The frontier snapshot, the miner, and the
   crossing snapshot search over base ops plus the MDL-certified library —
   not over raw adopted solutions. The no-self-credit rule carries over:
   a task's crossing snapshot excludes library entries whose source task
   is the task itself.
2. **Adoption is gated.** `al_adopt_solution` records the solve and grows
   `C_train` unconditionally (the record is the data), then routes every
   candidate abstraction through the master gate (§4). Only gate-passing
   bodies become searchable vocabulary.

K1 (crossings) remains the capability headline; the Phase L headline is
the gate record itself (§7 L1/L2) plus the K-archive retrofit (§6).

## 6. Retrofit: MDL value scoring of the Phase K archive

After the loop, the battery loads the committed Phase K final ledger
(`docs/ascent_k_ledger_final.jsonl`, chain-verified), reconstructs its six
adopted solution bodies in adoption order, and scores each body's marginal
value under the registered formula against the Phase K corpus itself:
`value_i = ΔMDL(body_i; C_K, L_i-1)` with `C_K` = all six bodies and
`L_i-1` = the gate-adopted prefix library. The six values (adopt/reject
under the master gate, with both deltas) are reported as `l4_k_retrofit` —
the Phase K archive re-judged by the universal value judge, committed as
data, changing nothing in the frozen K record.

## 7. Metrics, digest, artifacts

- **L1 (headline)**: per-generation adoption/rejection record of the
  master gate: candidates evaluated, adopted (with both deltas), rejected
  by reason; cumulative library size; `bits(L)` trajectory.
- **L2**: holdout-validation record: every adoption's `ΔMDL_hold < 0`
  bit, plus at least one candidate rejected specifically by the holdout
  clause (`l_mdl_holdout`) if one occurs; the count ships as measured.
- **L3**: K1-style crossing curve under the gated vocabulary, with the
  same certificate discipline as Phase K.
- **L4**: the Phase K retrofit scores (§6).
- Battery digest: `sha256(ledger_head + canon(metrics))[:16]`, printed as
  `al_digest`; two byte-identical runs asserted in CI; artifacts
  `reports/evidence/ascent_l_results.json`,
  `reports/evidence/ascent_l_ledger.jsonl`; run-1 copies committed as
  `docs/final_ascent_l.json`, `docs/ascent_l_ledger_final.jsonl`.

## 8. Frozen constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `ASCL_SPEC_VERSION` | "L-1" | |
| `ASCL_BODY_MIN` / `ASCL_BODY_MAX` | 2 / 8 | abstraction body bounds (Phase E bounds) |
| `ASCL_CANDS_PER_GEN` | 64 | subsequence-candidate evaluations per generation |
| `ASCL_HOLDOUT_SHA256` | `3f2c0d53739bdb3ae56af4a4a35d249dc549f0d09e26fe62ea4255838c192c49` | frozen holdout corpus pin |
| `ASCL_HOLDOUT_SEED` | 553211 | committed generator seed (documentation; the file is the instrument) |
| loop constants | Phase K values unchanged (`ASCK_*`) | generations 8, B_EVAL 1500, B_LIVE 25000, H 5, pose slots 6, N_HIDDEN 16, p_null 9/10 |
| `ASCL_MACRO_BASE` | 4000 | library token ids (never leave Phase L) |
| `ASCL_PIN_SHA256` | see runtime constant | kernel source + constants pin |

The pin input is the concatenated source of every Phase L kernel component
(formula, encoder, gate, corpus loader, loop, metrics, retrofit, replay)
plus the canonical dump of every constant above including the holdout pin.

## 9. Scaled configurations (also frozen)

- `--mode ascent-l` (demo, CI-safe): the Phase K demo configuration
  (generations 3, b_eval 1500, b_live 12000, H 3, n_public 6, n_hidden 8,
  null_programs 12) with the gate active and `ASCL_CANDS_PER_GEN` = 32.
- Test configuration (`_al_test_cfg`): the Phase K test configuration
  (generations 2, b_eval 1500, b_live 9000, H 2, n_public 5, n_hidden 6,
  null_programs 8) with `ASCL_CANDS_PER_GEN` = 32.

## 10. Anti-cheat battery (K7 extensions)

- The holdout corpus is tamper-checked (SHA) at battery start; a modified
  byte aborts (`test_al_holdout_tamper_detected` constructs the attack).
- The gate cannot be weakened from mutable code: formula, encoder, and
  gate are pinned kernel; the mutable citizens' AST audit extends to the
  Phase L symbols (`test_al_gate_unreachable_from_mutable_code`).
- Abstraction spam is red-teamed: a synthetic corpus where a candidate
  saves tokens on training but not on holdout must reject
  (`test_al_holdout_clause_rejects_overfit`); a candidate that pushes the
  vocabulary across a power-of-two boundary without paying for itself
  must reject (`test_al_bit_width_reprices_vocabulary`).
- Formula identities are tested: reduction to Phase E token accounting at
  constant width; exact integer arithmetic (no floats anywhere in the
  gate path); determinism of the greedy encoder including the
  longest-match tie impossibility.
- The retrofit is read-only on the Phase K record: it loads the committed
  ledger, verifies the chain, and writes nothing back
  (`test_al_retrofit_reads_frozen_k_record`).

## 11. Known boundaries (disclosed at spec-freeze)

- Greedy longest-match encoding is not optimal parsing; the formula is a
  registered upper bound, applied identically to every candidate (the
  Phase E disclosure, carried).
- Iterative single-candidate adoption understates joint compression
  (Phase E disclosure, carried).
- The holdout corpus is same-substrate (SC unit grammars). It validates
  generalization across programs, not across domains; cross-domain value
  judgment enters with the Phase N theorem library, where interestingness
  is ΔMDL on a different corpus under the SAME registered formula.
- With the thin Phase K-scale corpus (few adopted solutions per run), the
  gate is expected to reject most subsequence candidates early; adoptions
  concentrate where solution bodies genuinely share structure. A sparse
  adoption record is the honest reading, not a defect.
- `bits(L)` is constant at 6 for library sizes 0–30 in practice; the
  boundary-crossing term is exercised by the red-team test rather than by
  the battery-scale run.

## 12. Calibration disclosure

Before this freeze, the candidate space over the six committed Phase K
bodies was measured against both corpora under the registered formula:
12 subsequence candidates occur in ≥ 2 programs; the best training delta
is −24 bits (`INPUT EVENIDX TAIL TAIL`, holdout savings 0 — a train-only
idiom, the natural holdout-clause rejection); `TAIL TAIL` scores −12
training bits with holdout savings 2 (the natural adoption); and NO
candidate achieves a strict negative holdout delta (defcost cannot
amortize over 48 unseen programs), which is why the savings form of the
holdout clause was registered (§3). The loop portion under exactly these
constants was observed before this freeze and is disclosed as
known-at-prediction-time in `docs/PREDICTIONS_L.md`. After this freeze,
no constant changes; the battery runs as-is and its record ships as
measured.
