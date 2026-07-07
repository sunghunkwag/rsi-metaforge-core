# PREDICTIONS — Ascent Phase P (ISA-Extension Coupling Loop)

Pre-registered before the official `--mode ascent-p-battery` final runs.
Frozen protocol: `docs/ASCENT_P_SPEC.md` (P-1). Scoring: `docs/P_RESULT.md`
after the finals, misses included, no reinterpretation.

This phase exists to answer one empirical, singular question, registered
here against the honest expectation and NOT tuned to the observed result:

> When the closure itself can grow — when a crossed ISA extension is fed
> back into the task factory so the setter can draw from a larger closure —
> does the crossing trajectory REVIVE and keep climbing, or does it
> SATURATE AGAIN at a higher ceiling?

Both answers are pre-declared wins. A revived, sustained staircase would be
strong honest RSI evidence; a second saturation is the definitive "even an
open closure with a self-driven extender saturates" result. Only a
fabricated staircase is a loss.

## The registered trajectory-shape prediction

**Predicted shape: RE-SATURATION (a null result), for a stated STRUCTURAL —
not budget — reason.**

The reasoning, registered before the finals:

- The frozen catalog (K9) holds two ops, `BCAST` (int,list→list constant
  broadcast) and `ZGT` (list,list→list elementwise strict-order indicator).
  Both compute functions that are INEXPRESSIBLE in the base ISA: the
  executed constructor lemma (`no_int_to_list_constructor_lemma`) certifies
  no base op builds a constant list from pure-int stacks, and no base op is
  an elementwise order test.
- K's setter (frozen, §2.2-clean) poses only base-witness tasks. A
  base-witness task computes a base-expressible function. Therefore K's
  markers — the admitted-but-uncrossed residue — are ALWAYS
  base-expressible, and never `BCAST`- or `ZGT`-shaped.
- K8 admits an extension X iff granting X lets the extended frontier solver
  CROSS ≥ 1 marker that the base solver fails at the same frozen budget.
  Since no marker is extension-shaped, no marker is crossed by `BCAST` or
  `ZGT`. K8 therefore admits nothing, the ISA never grows, and the
  cum-crossed trajectory tracks the frozen K ceiling.
- This is a CLOSURE-SHAPE result, not a budget artifact. The frozen
  instrument budget `ASCP_B_EVAL` = 4000 is set ABOVE the search reach of a
  genuine extension crossing (the positive control crosses an
  extension-requiring task at ~3000 evaluations). So an extension-shaped
  marker WOULD cross at the frozen budget if one existed. None does.

## Numeric criteria (scored, never reinterpreted)

- **Revive** would require: the coupling arm's final `cum_crossed` strictly
  exceeds the frozen arm's, i.e. K8 admits ≥ 1 extension in the closed loop
  (`ext_admitted_total` ≥ 1) AND `cum_crossed_trajectory` rises after the
  admission. Registered probability: LOW.
- **Re-saturate** (predicted): the coupling arm's final `cum_crossed`
  EQUALS the frozen arm's, `ext_admitted_total` = 0, and the
  `isa_size_trajectory` is flat at 0 across every generation — while the
  extender still FIRES (`closed_loop_ext_requested_gens` ≥ 1) and K8 runs
  its full dual-gate trial and records an honest rejection.

## Predictions

- **P1 (determinism).** The two final battery runs are byte-identical:
  equal `ap_digest`, equal K10 chain head, `cmp`-equal
  `reports/evidence/ascent_p_results.json` and
  `reports/evidence/ascent_p_ledger.jsonl`.
- **P2 (executor equivalence, headline mechanism).** `ak_run_tokens_ext`
  with the base ISA is byte-equivalent to the untouched `ak_run_tokens` on
  the full equivalence battery (identical value/ops or identical crash
  reason); `ak_run_tokens` itself is unmodified. The extended executor runs
  `BCAST` and `ZGT`, which `ak_run_tokens` rejects (`ak_non_base_token`).
- **P3 (closed loop, headline).** The coupling arm RE-SATURATES: final
  `cum_crossed` equals the frozen arm's, `ext_admitted_total` = 0, and the
  ISA stays at the base floor (`isa_size_trajectory` flat at 0) — while P1
  fires ≥ 1 mechanical extension request (`BCAST`, whose type-signature gap
  is genuinely open) and K8 records an honest `ext_rejected`
  (`no_marker_crossed`) with the ISA restored byte-exactly.
- **P4 (positive control, mechanism proof).** For each catalog op the
  designer-stocked extension-requiring family has base passes = 0
  (impossibility pre-certificate at the frozen budget) and K8 admits the op
  by crossing ≥ 1 through the extended executor (crossing evidence): the
  gate + extended executor ARE a real crossing mechanism, so the closed-loop
  null is a genuine absence of extension-shaped markers, not a broken loop.
- **P5 (budget ladder).** Across the R0–R2 mining-budget ladder
  (b_live ∈ {9000, 15000, 25000}, `b_eval` FROZEN at 4000), the coupling
  arm's cum-crossed equals the frozen arm's at every rung and admits no
  extension: widening `b_total` does not revive the trajectory, reproducing
  the K R0–R4 finding under an OPEN closure with a self-driven extender.
- **P6 (constitution K8/K9/K10).** The catalog (K9) is hash-pinned
  (`ASCP_CATALOG_SHA256`) and unedited; every admission goes through K8 and
  only K8; a rejected request restores the exact prior ISA (hash-checked)
  and records a rejected digest; K10 is an append-only, hash-chained,
  replay-verifying per-generation ledger. The module-global `EXT_IMPL` /
  `EXT_TYPES` registries stay dormant (empty) before and after every Phase P
  run and the control — Phase P execution is a pure function of the frozen
  catalog and the isa set.
- **P7 (frozen arm untouched).** `ap_run_loop` with the coupling hook inert
  produces a K ledger byte-identical to `ak_run_loop` at the same config:
  the frozen comparison arm is bit-for-bit the untouched K flywheel.
- **P8 (suite).** The full test suite reports exactly
  `RESULT: 286 passed, 0 failed` when run after the evidence batteries (CI
  order); the 16 `test_ap_` tests pass in isolation; all six ascent pins
  (K, L, M, N, O, P) verify and every committed record is untouched.
- **P9 (claim boundary).** No configuration, instrument, catalog, or
  control family changes between this registration and the finals. The
  claim is exactly the gate-certified trajectory above. The catalog holds
  two INDEPENDENT ops (no dependency ladder), so the maximal ascent it could
  permit is two independent single-op crossings, not a dependent staircase;
  observed ascent is bounded by and stated as this catalog. No claim of
  AGI, singularity, unbounded capability, or intelligence explosion.

## Disclosure of what is known at prediction time

Per the standing protocol, the calibration run of the battery under exactly
the frozen constants was observed (single machine, CPython 3.11): digest
`506107aacab14861`, K10 head `99c519f1b38e95a8…`. Closed loop: frozen arm 3
crossings; coupling arm cum-crossed `[0,3,3,3,3,3,3]`, ISA size flat at 0,
one generation firing a `BCAST` request, zero admissions. Control: `BCAST`
base passes 0 → admitted (3 crossings); `ZGT` base passes 0 → admitted (2
crossings). Ladder: frozen 3 / coupling 3 at every rung. P1, P8 and P9 are
not implied by the calibration run; P2–P7 are registered reproductions of
the calibration observation, stated as such.
