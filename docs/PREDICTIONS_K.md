# PREDICTIONS — Ascent Phase K (Witness-Sealed Setter–Solver)

Pre-registered before the official `--mode ascent-k-battery` final runs.
Frozen protocol: `docs/ASCENT_K_SPEC.md` (K-1). Scoring: `docs/K_RESULT.md`
after the finals, misses included, no reinterpretation.

## Disclosure of what is known at prediction time

Per the SC-1/SC2-1 protocol, budgets and starting bands were calibrated for
loop liveness before spec-freeze, and the calibration run of the battery
under exactly the frozen constants was observed (single machine, CPython
3.11): digest `35080780f0be7293`, K1 = 1 crossing (lineage L_D, Track B,
within horizon), archive 6, markers 9, gate families fired
`{ka: 8, kb: 8, kc: 10, kd: 44}`. The finals are two fresh runs of the same
frozen configuration; determinism makes P2–P7 reproductions of the
calibration observation, and they are registered as such — the risk they
carry is nondeterminism or hidden environment coupling, and that is exactly
what they test. P1 and P8–P10 are not implied by the calibration run.

## Predictions

- **P1 (determinism).** The two final battery runs are byte-identical:
  equal `ak_digest`, equal ledger heads, `cmp`-equal
  `reports/evidence/ascent_k_results.json` and
  `reports/evidence/ascent_k_ledger.jsonl` across runs.
- **P2 (headline crossing).** K1 final = 1: exactly one admitted task
  family transitions unsolved → crossed, within the horizon H = 5, at the
  frozen `B_eval` = 1500, with the task's own mined macros excluded from
  the crossing snapshot. The crossing is Track B, lineage L_D.
- **P3 (learnability-band reward).** Exactly one lineage (L_D) ends with
  credit 1; the allocation policy visibly reallocates pose slots after the
  crossing (slots move from 2/2/2 to 1/1/4 at the next generation) and the
  starved lineages keep their base slot.
- **P4 (gate coverage).** Each admission-gate family rejects at least one
  candidate in the final logs: ka ≥ 8, kb ≥ 8, kc ≥ 10, kd ≥ 40
  (the ADV lineage guarantees the floor; natural rejections add to it).
  Zero ADV probes admitted; the canary never fires.
- **P5 (frontier markers).** At least 8 admitted tasks retire as frontier
  markers (admitted, never crossed within H), witnesses still sealed:
  the ledger contains no witness tokens outside `retired_crossed` records.
- **P6 (replay).** `ak_replay_verify` passes on the final state: every
  admission certificate re-derives from the ledger + vault, including the
  reconstructed difficulty snapshots and their exact frontier evaluation
  counts.
- **P7 (budget accounting).** The kernel meter accounts every logical
  spend path; final module totals match the calibration run exactly
  (admission cand_evals 18453, crossing cand_evals 61427, mining
  cand_evals 226897, setter proposals 80).
- **P8 (suite).** The full test suite reports exactly
  `RESULT: 215 passed, 0 failed` when run after the evidence batteries
  (CI order); the 21 `ak_` tests pass in isolation; the SC-1 and SC2-1
  digests and the Phase J record are untouched.
- **P9 (credit-supplier gap, carried finding).** The lineage that supplies
  the enabling band-3 macros (L_B) earns zero credit at these budgets even
  though removing its adoptions would remove the crossing — the
  learnability reward pays the crosser, not the supplier. Registered as a
  finding for Phases M/O, not as a defect to be patched post-hoc.
- **P10 (claim boundary).** No configuration, seed, threshold, or gate
  changes between this registration and the finals; `ASCK_PIN_SHA256`
  verifies at battery start in both final runs.
