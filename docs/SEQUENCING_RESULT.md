# SEQUENCING RESULT — Phase I Final Evaluation

**The threshold is exceeded: the final live configuration solves
26/33 designer tasks on the frozen Phase 0 instrument, with T15, T27,
and T28 simultaneously SOLVED — the union existence proof is realized in
one run, plus two transitions predicted OPEN: T23 (sum*range) and T26
(adjacent_difference_energy).** All 26 adopted programs pass the frozen
instrument; both arms are twice byte-identical; GR5/GR-O discipline
intact throughout; acceptance suites 147 passed, 0 failed on both
harnesses. Predictions scored 10/12 on the registered SOLVED/OPEN
outcomes — both misses are under-predictions (tasks solved that were
predicted OPEN); 9/12 under a stricter rule that also binds the
parenthetical wave/path commitments (§2 states both).

## Arms, reproduction, determinism

```bash
# frozen incumbent
python3 rsi_levels_metaforge_unified.py --mode run-frozen --save frozen_final.json
# final live (stratified schedule per docs/ORDERING_SPEC.md + G3 pressure + G4 archive)
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save live_final.json
```

Both arms run twice, byte-identical (GR3):

| Arm | Designer SOLVED | Digest | Two-run identity |
|---|---|---|---|
| final live (stratified schedule) | **26 / 33** | `e2c2893448da4cdf` | byte-identical |
| frozen incumbent | 19 / 33 | `e5dc308324bb10f6` (unchanged since Phase 0) | byte-identical |

Committed artifact: `docs/final_live_phaseI.json` (SHA-256
`1cffe630…3b95a`). All 26 live and all 19 frozen adopted designer
programs pass the frozen Phase 0 instrument. Runtime: ~66 min per live
run (~90+ gate batches with more accepted installs than any prior
configuration — the schedule's intended effect); no run truncated.
A post-fix confirmation run (after the CLI print repair) produced a
byte-identical artifact to run 1: confirmed (CONFIRM_IDENTICAL; SHA-256 matches run 1 exactly).

## 2. Per-task table: H evidence → prediction → actual

| Task | H evidence | Predicted | Actual | Score |
|---|---|---|---|---|
| T15 | enabler offered w1 (S2 mechanics); gate-accepted in both prior offering configs | SOLVED w1–2 | SOLVED w2 — via a NEW compositional program `M106 M104 EVENIDX RED_ADD SUB` (even-sum − tail-even-sum) | hit |
| T27 | G3-only genealogy; x⁴ fragment in wave-0 first batch | SOLVED w0–1 (pool-offer path) | SOLVED w2 — the offered x⁴ fragment installed w0, but the gating object was the **mined x⁸ macro** (`M108 = M101·M101`, parents T12): `M108 M108 ZMUL RED_ADD` | hit (path partially wrong: offer seeded the genealogy; mining closed it) |
| T28 | genealogy must resume via mining; Mechanism-2 contingency stated | SOLVED w1–3 (fresh-mining path) | SOLVED w2 — `M108 M108 ZMUL DUP ZMUL RED_ADD`, same wave as T27; the Mechanism-2 contingency did **not** trip (the x⁸ gram ranked in top-3) | hit (path as predicted) |
| T23 | attributed SEARCH/VOCAB; "no stratified body supplies the vocabulary" | OPEN | **SOLVED w5** — `M110 M103 SCAN_ADD ZMUL LAST` over sorted/reversed fragments (`M110 = INPUT SORTL DUP REVL ZSUB`, `M103 = INPUT REVL`) | **miss (under-prediction)** |
| T26 | attributed SEARCH/VOCAB | OPEN | **SOLVED w1** — `M104 INPUT ZSUB DUP ZMUL RED_ADD` (tail−self, squared, summed) via the TAIL fragment | **miss (under-prediction)** |
| T18, T21, T22 | SEARCH/VOCAB | OPEN | OPEN | hits |
| T29–T32 | certified ISA walls | OPEN | OPEN | hits |

Prediction score: **10/12 on the registered SOLVED/OPEN outcome per
task** — the falsifiable claim each row committed to. Stated scoring
rule: the parenthetical wave windows and acquisition paths are scored
qualitatively in the table above but do not flip a row; under a stricter
rule that binds them, T27 becomes a third miss (predicted w0–1 via pool
offer; actual w2 via mining) and the score is 9/12. Both numbers are
reported; the discrepant values are printed in the row either way.
The H attribution "no stratified body
supplies the missing vocabulary" was wrong for T23/T26: order-statistic
and shifted-difference vocabulary DID exist among the list-valued
fragments (SORTL/REVL/TAIL family) — the type-blind pre-I pipeline had
simply never offered it. T28's known-at-prediction-time marking applied
to the G3-only observation; its Phase I path (fresh mining in a novel
corpus) ran as predicted.

## 3. Lineage and schedule (spec vs execution)

Fresh-offer schedule executed exactly as the H3 dry-run mechanics:
S1 x² and x⁴ fragments in wave 0's first batch; terminal compressors
deferred to S2/S3 slots; T15 enabler offered w1. Installed vocabulary
(all through the unchanged gates; every install wave-logged):

| Macro | Origin | Body | Installed |
|---|---|---|---|
| 101 | exploration (S1) | `INPUT INPUT ZMUL INPUT INPUT ZMUL ZMUL` (x⁴ list) | w0 |
| 103 | exploration (S1) | `INPUT REVL` | w0–1 |
| 104 | exploration (S1) | `INPUT TAIL` | w0–1 |
| 105 | exploration (S1) | `INPUT SORTL DUP TAIL ZSUB ODDIDX` | w0–1 |
| 106 | exploration (S2) | `INPUT EVENIDX RED_ADD` | w1 |
| 108 | **mined** (from T12's program) | `M101 M101 ZMUL` (x⁸ list) | w1 |
| 110 | exploration (S1, fresh) | `INPUT SORTL DUP REVL ZSUB` | w4 |

The staircase: offered x⁴ (w0) → T12 adopts through it → mining yields
x⁸ (w1) → enumeration reaches sum x¹⁶ and sum x³² at surface ≤ 6 → T27
and T28 adopt in the same wave (w2). Exactly the H2 genealogy, restarted
one rung higher by the offer schedule.

Offer/accept statistics: 98 measured exploration batches over the 7
gating waves w0–w6 (14 per wave, the stated bound; the run's 8th and
final wave iteration skips gating by construction —
`GATE_SKIPPED_FINAL_WAVE`), 6 accepted (3 at w0, 2 at w1, 1 at w4); 36 re-offers
drawn and logged (33 prior=rejected, 3 prior=dropped_rider) — none of
the eventual installs came via re-offer in this run (macro 110 was a
fresh S1 offer); the re-offer machinery worked as specified and its
contribution here was null. Facts, not claims.

## 4. Frozen-arm counterfactual

Delta **+7 designer tasks** (T11, T12, T15, T23, T26, T27, T28 —
live-only; no frozen-only solves). For reference: v2 final delta was +4,
Phase G combined +3. Reproduction commands above; every determinism
pair in this phase was byte-identical.

## 5. Displacement trace of the new schedule

Not applicable in the null sense — the run met the threshold — but the
residual frontier is traced: T18, T21, T22 remain OPEN with the same
SEARCH/VOCAB attribution (their missing vocabulary — length-parity
conditionals, index arithmetic, order-statistic-times-aggregate at
surface ≤ 6 — does not appear in any stratified body), and T29–T32
remain the certified ISA walls. The one under-performance relative to
the dry-run: the x⁴ fragment did not gate T27 directly at w0 (the
enum's macro-lane admission at that wave did not surface the 6-token
x¹⁶ composition); the mined x⁸ rung closed it one wave later — the
genealogy, not the direct offer, remains the operative mechanism for
deep power towers.

## 6. Limitations and GR-O boundary cases

- **Implementation decision (documented in-code):** re-offer batches
  salt the duplicate-digest with their round; without it, the Phase E
  bookkeeping guard silently voids the frozen re-offer policy. Judged an
  implementation-layer conflict, not a spec defect (the spec's policy is
  implemented exactly; the guard is not part of the spec). Flagged for
  review rather than silently absorbed.
- **GR-O boundary:** ordering/eligibility keys read only the archive and
  the frozen anchor report (isolation-tested); the re-offer *trigger*
  reads exploration-batch outcomes (rejected/dropped) as the spec
  mandates — never designer identities, scores, or adoption history.
- **CLI print defect** found by the final run: the transfer-anchor
  summary referenced a pre-strata variable and raised after saving;
  artifacts unaffected (save precedes the print), fixed in a follow-up
  commit, post-fix confirmation run byte-identical to run 1.
- The H attribution under-called the fragment vocabulary's reach
  (T23/T26) — attribution tables bound what interventions are built,
  and this one was too conservative; recorded as a calibration fact for
  future attribution phases.
- Runtime: live runs ≈ 66 min each (heavier than Phase G: more accepted
  installs → more worktable rebuilds — the intended effect of the
  schedule); all bounds stated up front were respected; no run truncated.
