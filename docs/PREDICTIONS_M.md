# PREDICTIONS — Ascent Phase M (Ledger-Trained Amortizer)

Pre-registered before the official `--mode ascent-m-battery` final runs.
Frozen protocol: `docs/ASCENT_M_SPEC.md` (M-1). Scoring: `docs/M_RESULT.md`
after the finals, misses included, no reinterpretation.

## Disclosure of what is known at prediction time

Per the standing protocol, the models and the probe battery were
calibrated before spec-freeze and the calibration run of the battery under
exactly the frozen constants was observed (single machine, CPython 3.11):
digest `fc8a471de9f6466f`; canonical incumbent 2/48; v0 4/48 (adopted);
v0_sliceA 6/48 (adopted); v1 3/48 (rolled back); training corpus 11
chain-verified bodies (1 Track A, 10 Track B). The finals are two fresh
runs of the same frozen configuration; P2–P6 are reproductions of the
calibration observation, registered as such. P1 and P7–P9 are not implied
by the calibration run.

## Predictions

- **P1 (determinism).** The two final battery runs are byte-identical:
  equal `am_digest`, equal ledger heads, `cmp`-equal
  `reports/evidence/ascent_m_results.json` and
  `reports/evidence/ascent_m_ledger.jsonl`.
- **P2 (uplift, headline).** Certified passes per logical budget on the
  frozen 48-probe battery at `B_PROBE` = 1500: canonical 2, v0 4 —
  the pre-registered v0 uplift is a strict 2× improvement, adopted by the
  gate.
- **P3 (attribution ablation).** The pre-registered Track A slice retrain
  `v0_sliceA` (trained on a single committed body) scores 6/48 and is
  adopted over v0 — most of the amortizer's value at this corpus scale is
  the learned INPUT-first root transition plus inverse-chain bigrams, and
  the record says so explicitly.
- **P4 (rollback, headline).** v1 (the neural retrain) scores 3/48
  against the then-incumbent 6/48 and is ROLLED BACK; the rollback record
  carries both pass counts and the full per-probe cost vectors. The final
  incumbent is `v0_sliceA`.
- **P5 (per-track split).** Final-incumbent passes split 1 Track A / 5
  Track B; the canonical incumbent splits 0/2.
- **P6 (training-corpus provenance).** Exactly 11 deduplicated bodies,
  every one hash-matched to a `mined`/`cross_adopted` record of the
  chain-verified committed K and L final ledgers; the corpus is disjoint
  from all 48 probe-family programs (contamination check passes; the
  red-team constructs the violation and asserts abort).
- **P7 (null-model identity).** `am_solve` under the null model is
  bit-identical to `sc_solve` in solution and cost on the probe sample
  (tested in-suite).
- **P8 (suite).** The full test suite reports exactly
  `RESULT: 243 passed, 0 failed` when run after the evidence batteries
  (CI order); the 12 `test_am_` tests pass in isolation; the K-1, L-1,
  SC-1, and SC2-1 pins verify and their committed records are untouched.
- **P9 (claim boundary).** No configuration, seed, model-form, or gate
  changes between this registration and the finals; `ASCM_PIN_SHA256`,
  `ASCL_PIN_SHA256`, and `ASCK_PIN_SHA256` all verify at battery start in
  both final runs. Wiring the adopted ordering into the live loop is NOT
  claimed here — it is registered as the first Channel A candidate for
  Phase O, per the spec §6 jurisdiction boundary.
