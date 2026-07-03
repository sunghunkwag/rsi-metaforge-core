# Phase J5 Prediction Register

Committed and pushed BEFORE any Phase J5 evaluation run exists. Scored in
docs/CROSSING_RESULT.md after the runs, misses included. Every claim below
derives from committed evidence only; observations already made at
prediction time are marked **[known-at-prediction-time]**.

## Protocol under prediction

Two arms at identical budgets and seeds (WAVES=8, RESTARTS_PER_TASK=6,
ITERS_PER_RESTART=550, SPECULATION_BUDGET_PER_WAVE=2,
EXPLORATION_BATCHES_PER_WAVE=14; SEED=2026, DATA_SEED=11, GATE_SEED=2027,
CF_GATE_SEED=4099), each executed twice with byte-identical artifacts
required (GR3):

- **Arm A (incumbent):** `--mode transfer-anchor` — the unchanged Phase I
  live configuration.
- **Arm B (candidate):** `--mode crossing-anchor` — identical configuration
  plus the capability-grant channel (approved frozen spec
  docs/ISA_EXTENSION_SPEC.md; grant disposition exclusively via the
  unchanged gate discipline).

Verification instruments (frozen before any run): docs/frozen_holdout_phase0.json
(SHA 527bb04d…da24) and docs/frozen_holdout_extJ.json (SHA e28ba073…f4ed).

## Known-at-prediction-time observations

1. **[known-at-prediction-time]** Extended-ISA enumeration at surface <= 6 is
   untruncated with classes-per-length [5, 38, 368, 3157, 34073, 348070] and
   reaches exactly one wall vector: T29 at length 6 (committed measurement
   docs/mdl_extension_J.json; pinned by test).
2. **[known-at-prediction-time]** Designer witnesses pass all sealed gates at
   expanded lengths 6 (T29), 8 (T30), 18 (T31), 20 (T32)
   (docs/witnesses_J.json; never counted as solved).
3. **[known-at-prediction-time]** In the 2-wave mechanism test (no
   exploration pool), the grant bundle is offered and gate-adopted at wave 0
   with gained == ['T29'], and T29 is adopted by run_wave at wave 1 through
   the full train-reverify + holdout + counterfactual sequence, twice
   byte-identically (test_capability_grant_adoption_and_roundtrip_two_run_identity).
4. **[known-at-prediction-time]** The committed BCAST-only admission trial at
   maximal declared budget found no wall program (expressibility at depth 19
   did not imply reachability) — the cautionary precedent for T30-T32.
5. **[known-at-prediction-time]** The Phase I incumbent record is 26/33
   designer tasks, adoption digest e2c2893448da4cdf (docs/final_live_phaseI.json).

## Predictions

**P1 — Arm A reproduction (inertness).** Arm A solves 26/33 designer tasks
with adoption digest exactly `e2c2893448da4cdf`, twice byte-identically. This
doubles as the backward-compatibility claim for the J3 code: with the channel
off, the runtime is behaviorally identical to the Phase I runtime. A miss
here invalidates the candidate arm and stops the phase (bug, not finding).

**P2 — Grant adoption (Arm B).** The grant bundle {BCAST, ZGT} is offered at
wave 0 (the mechanical request locator fires from wave-0 residues) and
gate-adopted at wave 0 with gained == ['T29'] exactly; the speculation log
records one accepted `capability_grant` entry with a clean pre/post hash
protocol. Contingency: if a wave-0 budget interaction with the stratified
schedule defers the offer, it re-fires at the next wave (window 0-6); if the
gate rejects it, the rejection is recorded and re-offer is blocked by digest
— reported as a null.

**P3 — T29 crossing (Arm B).** T29 `count_above_threshold` is adopted at
wave 1 (window 1-2) via the persisted grant-earned solution, passing train
re-verify, sealed holdout, and counterfactual gates; the adopted program has
expanded length 6 and uses both BCAST and ZGT; it passes both frozen
instruments on replay (phase0 + extJ). This satisfies the phase threshold
(>= 1 of T29-T32 gate-adopted and instrument-verified).

**P4 — T30 remains OPEN (Arm B).** No length-<=6 solution exists (certified,
extended ISA); the 8-token witness is beyond the enumeration horizon; the
stochastic channel at these budgets is not expected to find it. Window if
crossed anyway: any wave, via drift channel or macro compression. A crossing
would be a positive surprise, reported with full lineage.

**P5 — T31, T32 remain OPEN (Arm B).** Witness depths 18 and 20; expected
honest nulls at these budgets, with the extended-ISA certificates (blocked
<= 6) and witnesses (expressible at 18/20) bounding each wall's band.

**P6 — No incumbent regression (Arm B).** All 26 Arm-A designer adoptions
remain adopted in Arm B: the grant consumes at most one wave-0 speculation
slot and the granted vocabulary strictly extends the incumbent one.
Risk, stated: post-grant enumeration tables allocate part of their class
budget to extended-op classes, which could displace a base solution the
incumbent arm finds (the T28-style displacement precedent). Contingency: any
regression is reported per-task with a displacement-style trace; the arm
comparison remains the measured claim either way.

**P7 — Determinism.** Both arms, both runs, byte-identical artifacts; any
divergence is a determinism bug and stops the phase (worse than a null).

## Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save armA_run1.json
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save armA_run2.json
python3 rsi_levels_metaforge_unified.py --mode crossing-anchor --save armB_run1.json
python3 rsi_levels_metaforge_unified.py --mode crossing-anchor --save armB_run2.json
```
