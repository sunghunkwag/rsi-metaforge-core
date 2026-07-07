# PREDICTIONS — Ascent Phase L (MDL Master Gate)

Pre-registered before the official `--mode ascent-l-battery` final runs.
Frozen protocol: `docs/ASCENT_L_SPEC.md` (L-1). Scoring: `docs/L_RESULT.md`
after the finals, misses included, no reinterpretation.

## Disclosure of what is known at prediction time

Per the SC-1/SC2-1/K-1 protocol, the candidate space was measured against
both corpora before spec-freeze (disclosed in the spec §12), and the
calibration run of the battery under exactly the frozen constants was
observed (single machine, CPython 3.11): digest `74ec178cd88013e5`,
library 2, corpus 6 + 10, L1 = 2 adopted / 203 rejected
(`l_mdl_train` 178, `l_mdl_holdout` 25), L3 = 3 crossings, retrofit 0/6.
The finals are two fresh runs of the same frozen configuration;
determinism makes P2–P8 reproductions of the calibration observation,
registered as such — they test nondeterminism and hidden environment
coupling. P1 and P9–P10 are not implied by the calibration run.

## Predictions

- **P1 (determinism).** The two final battery runs are byte-identical:
  equal `al_digest`, equal ledger heads, `cmp`-equal
  `reports/evidence/ascent_l_results.json` and
  `reports/evidence/ascent_l_ledger.jsonl` across runs.
- **P2 (gate adoption, headline).** Exactly 2 library adoptions, both
  holdout-validated with recorded numbers: `INPUT ODDIDX TAIL`
  (d_train = −24 bits, sav_hold = 2) and `INPUT TAIL`
  (d_train = −6 bits, sav_hold = 2). The searchable library contains
  nothing the gate did not certify.
- **P3 (gate rejection, headline).** ≥ 200 ledgered rejections carrying
  exact bit deltas, including ≥ 20 `l_mdl_holdout` rejections (train-only
  idioms killed by the generalization clause) and ≥ 170 `l_mdl_train`
  rejections. The train-only idiom `INPUT ODDIDX TAIL TAIL`
  (d_train = −24, sav_hold = 0) is among the holdout rejections.
- **P4 (crossings under the gated vocabulary).** L3 = 3 crossings — MORE
  than the Phase K record's 1 at identical loop budgets: the band-5 tail
  family crosses at generation 0 via a 4-token gate-certified route
  (cost 121) shorter than its own witness, and two band-3 L_B families
  cross at generation 2. Final credits: L_A 0, L_B 2, L_D 1 — the
  credit-supplier gap measured in Phase K partially closes because the
  library is generic rather than task-shaped.
- **P5 (retrofit).** All six Phase K archive bodies are REJECTED by the
  master gate (five `l_mdl_train`, one `l_mdl_holdout` — the
  `INPUT ODDIDX TAIL TAIL` body compresses train at −24 but never occurs
  in the holdout): the raw K macros carry no certified compression value;
  their compressive content lives in their shared prefixes. The K record
  itself is untouched (read-only load, chain-verified).
- **P6 (replay).** `al_replay_verify` re-derives every admission
  certificate, every adoption's exact deltas, every library snapshot, and
  the per-generation MDL trajectory from the ledger + vault in both
  finals.
- **P7 (corpus/library separation).** `corpus_size` = 6 (K seed) + every
  mined/cross-adopted body; `library_size` = 2 = the lib_adopted record
  count; every searchable macro token maps to a gate-certified body.
- **P8 (code width).** `bits` stays 6 throughout (the boundary-crossing
  repricing is exercised by the red-team test, not by the battery-scale
  run — disclosed in the spec §11).
- **P9 (suite).** The full test suite reports exactly
  `RESULT: 231 passed, 0 failed` when run after the evidence batteries
  (CI order); the 16 `test_al_` tests pass in isolation; the K-1, SC-1,
  and SC2-1 pins verify and their committed records are untouched.
- **P10 (claim boundary).** No configuration, seed, formula, or gate
  changes between this registration and the finals; `ASCL_PIN_SHA256`
  and `ASCK_PIN_SHA256` both verify at battery start in both final runs.
