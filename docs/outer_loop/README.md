# Outer Loop — Ledger and Ground-Truth Map

Governing document: [`OUTER_LOOP_CONSTITUTION.md`](../../OUTER_LOOP_CONSTITUTION.md) (repo root). This directory holds the outer loop's own instruments: the ledger the loop is measured by (Article V) and, once Stage 4/S3 unlocks, the versioned meta-directive (`META_DIRECTIVE_vN.md`).

## OL_LEDGER.jsonl (Article V)

Append-only; one JSON record per **merged** work order; the Orchestrator appends on merge; the Owner spot-audits. The file is committed empty because no work order has merged yet — an empty ledger is the honest state, not a placeholder.

Record schema (all fields required; `null` where genuinely inapplicable):

```json
{
  "wo_id": "WO-1",
  "drafted_by": "constitution|orchestrator:<session>",
  "approved_date": "YYYY-MM-DD",
  "worker_started": "YYYY-MM-DDTHH:MMZ",
  "merged_commit": "<sha>",
  "cycle_hours": 0.0,
  "predictions_registered": 0,
  "predictions_hit": 0,
  "predictions_missed": 0,
  "tests_added": 0,
  "certified_passes_added": 0,
  "rollbacks": 0,
  "notes": ""
}
```

(The block above is the schema illustration, not a ledger entry.) These metrics are selection pressure, not reporting: prediction hit-rate, cycle time, rollback rate, certified-passes-per-cycle — and, once Stage 4 unlocks, verifiers admitted and external merges landed. Until S3 is unlocked (Article VII.3), the metrics are collected but the meta-rules change only by Owner hand.

## Canonical-name map (constitution names → in-repo ground truth)

The constitution refers to two inner-constitution documents by Owner-side names that do not exist as files in this repository (repo-wide grep at `98ff67f`: zero hits). The in-repo canonical equivalents:

| Constitution's name | In-repo ground truth |
|---|---|
| `METAFORGE_ASCENT_DIRECTIVE.md` §2 | `docs/ASCENT_K_SPEC.md` §2 (kernel/mutable split; K1/K3/K4 table). The complete K1–K7 enumeration lives in `docs/ASCENT_RESULT.md:43-45`; K5 is defined in `docs/ASCENT_L_SPEC.md` §2, K6 in `docs/ASCENT_N_SPEC.md` §2, K7 in `docs/ASCENT_K_SPEC.md` §10. The "§2.2 no LLM / embedding / model-API" clause is cited in-repo at `docs/05_limitations.md:47-51`; the directive document itself is held by the Owner outside the repo. |
| `PHASE_P_COUPLING_DIRECTIVE.md` §2 | `docs/ASCENT_P_SPEC.md` §2 "Constitution amendment — K8, K9, K10 (additive to K1–K7)". |

The drafting style those names point at (Article II.3: "the canonical form") is the house form of `docs/ASCENT_K_SPEC.md` / `docs/ASCENT_P_SPEC.md` plus the register→result pairing `docs/PREDICTIONS_<X>.md` → `docs/<X>_RESULT.md`.

## Aliveness checklist (Article IX) — status at this commit

- [x] Constitution text committed (`OUTER_LOOP_CONSTITUTION.md`) — merged when the Owner merges the PR carrying it.
- [x] `docs/outer_loop/OL_LEDGER.jsonl` initialized (empty, append-only).
- [ ] Amendment A1 Owner-enacted — `docs/amendments/A1_learned_proposal_layer.md` is committed as a **DRAFT**; only the Owner enacts (Article I.5).
- [ ] WO-1 carries the Owner token — `docs/work_orders/WO-1_phase_r_learned_proposal_layer.md` section (10) is empty until the Owner fills it (Article II.4).
- [ ] WO-1 executed by a fresh worker session and merged with its DoD met.
- [ ] Orchestrator's draft of WO-2 (from `R_RESULT.md`, per Article VII) sitting in a PR awaiting the Owner token.

Claim boundary: nothing in this directory asserts capability. The outer loop's claim is exactly its ledger — merged work orders, scored predictions, certified passes — and an empty ledger claims nothing.
