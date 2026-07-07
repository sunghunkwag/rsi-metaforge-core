# Ascent Phase P — ISA-Extension Coupling Loop — Frozen Specification (P-1)

Spec-freeze document for the Ascent directive, Phase P (module M6). Every
constant, instrument, catalog entry, control family, and protocol rule below
is frozen at commit time, BEFORE the first `--mode ascent-p-battery` evidence
run. Post-hoc changes require a new predictions file. Predictions:
`docs/PREDICTIONS_P.md`; results: `docs/P_RESULT.md`. Phases K/L/M/N/O are
read-only under this phase. This directive extends the K–O Ascent directive;
its Constitution (K1–K7) remains in force verbatim and is amended, not
replaced, by the K8/K9/K10 items below.

## 1. Mission and claim boundary

Phase K proved a witness-sealed setter–solver flywheel turns once and then
SATURATES on a fixed ISA. The budget ladder R0–R4 established, by
measurement, that more compute moves WHEN the single crossing happens, never
HOW MANY tasks cross: the setter can only pose tasks inside the fixed
instruction set's verifiable-expressible closure, so once the solver frontier
clears the shallow layers the remaining admitted tasks pile up as frontier
markers. Budget cannot widen a closure.

Phase P builds the one mechanism that can: a coupling loop that feeds
K8-gated ISA extension back into K's task factory, so a crossed extension
enlarges the closure the setter draws from. The claim is EXACTLY the
gate-certified, byte-reproducible K10 crossing trajectory under the
pre-registered criteria — revive or re-saturate, both wins, only a fabricated
staircase a loss. The extender never invents primitives; it draws only from
the frozen `DORMANT_CAPABILITY_CATALOG` (K9). Sustained ascent, if observed,
is bounded by that catalog and stated as such. No claim of AGI, singularity,
unbounded capability, or intelligence explosion.

## 2. Constitution amendment — K8, K9, K10 (additive to K1–K7)

The K frozen kernel (K1–K7) is untouched. Phase P adds three frozen-kernel
items and three hard constraints.

- **K8 — the extension-admission gate.** The predicate that decides whether a
  requested catalog op enters K's executable ISA. It is the Phase J
  speculative-grant discipline (feasibility on sealed hidden seeds +
  frontier-solver-fails at the current ISA + non-triviality null battery +
  novelty, rollback-on-reject with a byte-exact ISA hash check and a recorded
  rejected digest) applied to K's own markers. Mutable code may REQUEST an
  extension; only K8 may admit one. K8 reads the witness vault (K1);
  `ap_extension_gate`, `_ap_cert_nontrivial`, `_ap_marker_public`.
- **K9 — the catalog.** `DORMANT_CAPABILITY_CATALOG` and every
  `CapabilitySpec.impl` are frozen and hash-pinned (`ASCP_CATALOG_SHA256`, a
  behavioural + surface fingerprint). The loop SELECTS from it; it never edits
  it. Catalog membership is an owner-pre-registered constitution amendment,
  never self-granted.
- **K10 — the closure-generation ledger.** A per-generation, append-only,
  hash-chained (SCLedger, K3 discipline), replay-verifying record of
  `(isa_fingerprint, admitted, crossed, markers, ext_requested,
  ext_admitted, cum_crossed)`. This is the instrument the sustained-ascent
  question is read off; it is frozen and byte-reproducible.

Hard constraints:

- **Extension monotonicity + provenance.** An op enters K's ISA only through
  K8, only from K9, and only with a recorded request lineage tracing to
  specific frontier markers, carrying its admitting crossing certificate. The
  base ISA is the floor; extensions are append-only within a run; a rejected
  request restores the exact prior ISA (hash-checked).
- **Per-evaluation budget frozen and equal.** `ASCP_B_EVAL` = 4000 is fixed
  at registration and identical across the compared arms (frozen-ISA vs
  coupling-live). Only `b_total` (mining, `b_live`) is self-allocated. The
  budget is set ABOVE the search reach of a genuine extension crossing (the
  control crosses at ~3000 evaluations), so a re-saturation result is a
  closure-shape finding, not a budget artifact.
- **The setter cannot pre-know the extension.** The frozen K setter poses
  only base-witness tasks; a task is extension-requiring exactly when the
  frontier solver at the current ISA fails it (the difficulty certificate),
  never by a setter annotation. The AST-leakage audit covers the coupling
  path: no mutable setter symbol references K8/K9 internals or the vault, and
  the mechanical request locator (P1) references no vault, witness, or gate
  symbol.

## 3. The four modules

- **P1 — extension-request locator** (`ap_extension_request_locator`). The
  Phase J mechanical, oracle-free `propose_capability_requests` logic
  retargeted from designer-origin open tasks to K's own frontier-marker
  residue. A request fires when markers exist, the executed constructor lemma
  holds, a dormant catalog op fills a type-signature gap absent from the live
  ISA, and the marker residue (bounded base-solver exploration over the
  PUBLIC pairs only, `ASCP_RESIDUE_BUDGET` = 400) carries list-consuming token
  mass. Empty output is the common, honest case. Reads only public marker
  pairs and the frozen catalog signatures.
- **P2 — extension-admission gate K8** (`ap_extension_gate`, above).
- **P3 — extended K executor** (`ak_run_tokens_ext`, `ak_run_checker_ext`,
  `ap_solve`, `ap_gate_score`). Accepts base tokens AND admitted extension
  ids present in the isa; extended dispatch reads the FROZEN K9 catalog view
  (`_AP_EXT_IMPL`), never the mutable `EXT_IMPL` registry, so execution is a
  pure function of `(frozen catalog, isa)` and never perturbs the dormant
  registries. `ak_run_tokens` is UNMODIFIED and remains the executor of the
  frozen arm; `ak_run_tokens_ext` with `isa == AP_BASE_ISA` is provably
  byte-equivalent to it (`test_ap_executor_equivalence_base_isa`).
- **P4 — coupling controller & K10 ledger** (`ap_run_loop`,
  `ap_metrics_from_ledger`, `ap_budget_ladder`). A generation loop identical
  to `ak_run_loop` — the K flywheel runs byte-for-byte — except that after
  each generation, and after the terminating sweep, P1 scans that step's fresh
  markers and any request it fires is judged by K8; on admission the ISA grows
  (append-only) and the closure state is written to K10.

## 4. The frozen instrument and the positive control

- **Closed-loop instrument.** The K flywheel at `ASCP_GENERATIONS` = 6,
  `ASCP_B_EVAL` = 4000, `ASCP_B_LIVE` = 15000, K's frozen split
  (n_public 8, n_hidden 16, null_programs 24, h 5). The frozen arm is
  `ak_run_loop` at this config; the coupling arm is `ap_run_loop` at the same
  config. The budget ladder reruns both arms at
  `b_live ∈ {9000, 15000, 25000}` with `b_eval` frozen.
- **Positive control** (`ap_ext_battery`, `ap_control_admission`), DESIGNER-
  STOCKED and stated as such — the Phase O extender protocol carried into K's
  executor with TRUE catalog extension ids (≥ 60), not base ops. Frozen
  Track-B families whose ground truth needs a catalog op:
  `BCAST` ∈ {sum-, max-, head-broadcast}, `ZGT` ∈ {gt-rev, gt-sort}; each a
  depth-4 witness whose extended crossing is within the frozen budget. For
  each op the base ISA passes 0 (impossibility pre-certificate) and K8 crosses
  ≥ 1 through the extended executor (crossing evidence). The control proves
  the mechanism itself; it is complementary to, and distinct from, the
  closed-loop measurement, where the markers are produced by K's own setter
  and no op is pre-stocked. The frozen catalog holds two INDEPENDENT ops, so
  the maximal ascent it permits is two independent single-op crossings, not a
  dependent staircase — stated as such.

## 5. Pins and reproducibility

`ASCP_PIN_SHA256` binds the source of every K8/K9/K10 component and the
frozen constants canon (including `ASCP_CATALOG_SHA256` and the control
segments); any drift aborts the battery. `ap_verify_pin` checks the catalog
fingerprint first, then the source pin. The K10 and control ledgers are
hash-chained and replay-verified; `--mode ascent-p-battery` is run twice in
CI and asserted byte-identical.
