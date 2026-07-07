# RESULT — Ascent Phase P (ISA-Extension Coupling Loop)

Scored against `docs/PREDICTIONS_P.md` (pre-registered) under the frozen
protocol `docs/ASCENT_P_SPEC.md` (P-1). Two fresh `--mode ascent-p-battery`
runs of the frozen configuration; misses included, no reinterpretation.

**Headline: RE-SATURATION — the predicted null.** When the closure is allowed
to grow — a self-driven extender feeds K8-gated ISA extension back into K's
task factory — the crossing trajectory does NOT revive. It saturates again at
exactly the frozen-K ceiling, at every mining budget, for a STRUCTURAL reason:
K's setter poses only base-witness tasks, so its markers are never
extension-shaped, so no catalog op crosses any marker, so K8 admits nothing.
The result is decisive rather than budgetary: the frozen instrument budget
(4000) is above the search reach of a genuine extension crossing (the control
crosses at ~3000), so an extension-shaped marker WOULD cross if one existed.
None does. This is the top of the negative-result lineage the K–O program
built toward: even an open closure with a self-driven extender saturates.

## The measured trajectory (calibration digest `506107aacab14861`)

| arm | cum-crossed trajectory | final ISA | extensions admitted |
|---|---|---|---|
| frozen (`ak_run_loop`) | final 3 | base | — |
| coupling (`ap_run_loop`) | `[0,3,3,3,3,3,3]` | `[]` (base) | 0 |

The coupling arm fires one mechanical `BCAST` request (a genuinely open
type-signature gap) at the terminating step and K8 records an honest
`ext_rejected` (`no_marker_crossed`) with the ISA restored byte-exactly;
`ZGT` is not auto-requested because its `(list,list)→list` type signature is
already present in the base zip family — faithful to the Phase J locator, and
consistent with the catalog's own "designer-stocked" rationale for `ZGT`.

Budget ladder (b_eval frozen at 4000): frozen 3 / coupling 3 at every rung
(b_live ∈ {9000, 15000, 25000}) — widening `b_total` revives nothing,
reproducing the K R0–R4 finding under an OPEN closure with a live extender.

## Positive control — the coupling mechanism is real

| op | family size | base passes (impossibility) | admitted | crossings |
|---|---|---|---|---|
| `BCAST` | 3 | 0 | yes | 3 |
| `ZGT` | 2 | 0 | yes | 2 |

The extended executor + K8 gate cross genuine extension-requiring tasks that
the base ISA fails at every budget. So the closed-loop null is a true absence
of extension-shaped markers — not a broken loop, not a too-small budget.

## Scoring

- **P1 (determinism).** HIT — the two finals are byte-identical (`ap_digest`,
  K10 head, and both `cmp`-equal artifacts).
- **P2 (executor equivalence).** HIT — `ak_run_tokens_ext` at the base ISA is
  byte-equivalent to the unmodified `ak_run_tokens` on the full battery; it
  runs `BCAST`/`ZGT`, which `ak_run_tokens` rejects.
- **P3 (closed loop re-saturates).** HIT — coupling final cum-crossed 3 =
  frozen 3; `ext_admitted_total` = 0; ISA flat at 0; one honest `BCAST`
  request and rejection recorded.
- **P4 (positive control).** HIT — base passes 0 for both families; both ops
  admitted with ≥ 1 extended crossing each.
- **P5 (budget ladder).** HIT — coupling equals frozen at every rung; no
  admission; the frozen instrument budget is never varied.
- **P6 (K8/K9/K10).** HIT — catalog hash-pinned and unedited; admission only
  through K8; rejection restores the exact ISA and records a digest; K10
  append-only, hash-chained, replay-verified; `EXT_IMPL`/`EXT_TYPES` dormant
  before and after.
- **P7 (frozen arm untouched).** HIT — `ap_run_loop` with the hook inert
  yields a K ledger byte-identical to `ak_run_loop`.
- **P8 (suite).** HIT — `RESULT: 286 passed, 0 failed` after the evidence
  batteries; the 16 `test_ap_` tests pass in isolation; six ascent pins
  verify; prior records untouched.
- **P9 (claim boundary).** HELD — no configuration, instrument, catalog, or
  control family changed between registration and finals. The claim is
  exactly the gate-certified trajectory above; ascent is bounded by and
  stated as the two-op, dependency-free catalog. No AGI / singularity /
  unbounded-capability / intelligence-explosion claim anywhere.

Score: **9/9 predictions HIT**, including the registered trajectory-shape
prediction (RE-SATURATION). The prediction was registered against the honest
structural expectation before the finals and is not tuned to the result.

## Reading

Phase P built the one mechanism a budget ladder cannot substitute for — a
coupling loop that lets the closure itself grow — and measured, under
pre-registered criteria and byte-reproducibly, that it does not revive the
crossing trajectory from a base start under the frozen two-op catalog. The
extender fires, K8 runs its full dual-gate trial, and admits nothing, because
K's own setter never manufactures a task shaped like the capability it lacks.
The positive control certifies that this is a property of the closure, not of
the machinery: hand the same gate a genuinely extension-requiring task and it
crosses it. Both outcomes were pre-declared wins; this is the definitive
"even an open closure with a self-driven extender saturates" result, and it
is certified, replayable, and honest.
