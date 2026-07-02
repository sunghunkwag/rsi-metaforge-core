# Phase F — Attribution of OPEN Tasks (measurement only)

Diagnostic phase of the v3 directive: each OPEN designer task is
attributed to a blocking cause by controlled measurement. Zero mechanism
changes; all probes ran in a GR-F sandbox (throwaway `SearcherState`
clone; no artifact crossed into any live searcher state, proposal pool,
or adoption path — enforced by `test_probe_sandbox_isolation`).

Committed artifact: `docs/attribution_probe_phaseF.json` (SHA-256
`6909c3ea9c34ba2f7ec0b324cb7e7c99389700712e8dd89b03559bc637666a2d`),
two consecutive probe runs byte-identical.

Reproduction:

```bash
python3 rsi_levels_metaforge_unified.py --mode attribution-probe \
    --vocab-from docs/transfer_anchor_phaseE.json --save probe.json
```

## F1 — Capacity probe

Protocol (stated up front, spent in full): per OPEN task and per rung,
`synthesize` (the existing stochastic search machinery) on a sandboxed
searcher carrying the final live vocabulary (macros 100, 103, 106),
fixed seeds (`909090 + rung*10007 + task*211`), budget **24 restarts ×
550 iterations = 13,200 mutation-proposal iterations per task-rung**
(4× the live per-wave value; ceiling 528,000 across the ladder,
short-circuit at the first gate-passing rung — never reached). Rungs:
`max_program_len ∈ {20, 28, 40, 56}` with stack/macros scaled
proportionally from (14, 32, 24) and capped at the v2 bounds:
(20, 46, 34), (28, 64, 48), (40, 91, 69), (56, 128, 96). A "solving
program" means train-exact AND passing both sealed gates; probe-found
programs are reduced to hash + lengths and discarded (GR-F). Total
wall time: ~4 s per full pass (most mutants are rejected by the
pre-existing static-plausibility screen before scoring; the iteration
budget is spent either way — see the caveat below).

### Per-task attribution table

| Task | Name | Classification | Evidence (best train score per rung 20/28/40/56; scored evals in parens) | Transfer coverage while OPEN |
|---|---|---|---|---|
| T18 | length_conditioned_sum | **SEARCH/VOCAB** | 0.0(24) / 0.0(24) / 0.0(24) / 0.1998(53) — no train-exact at any rung | 21/192 pool offers |
| T21 | last_quartile | **SEARCH/VOCAB** | 0.1998(48) / 0.0(24) / 0.0(24) / 0.05(48) | 21/192 |
| T22 | sum*second_largest | **SEARCH/VOCAB** | 0.0(24) / 0.05(42) / 0.0(24) / 0.0(24) | 21/192 |
| T23 | sum*range | **SEARCH/VOCAB** | 0.1998(45) / 0.0(30) / 0.0(24) / 0.0(24) | 21/192 |
| T26 | adjacent_difference_energy | **SEARCH/VOCAB** | 0.0(24) / 0.2497(53) / 0.1998(97) / 0.0(24) | 21/192 |
| T28 | sum_x32 | **SEARCH/VOCAB** | 0.0(121) / 0.0(24) / 0.0(25) / 0.0(24) | 21/192 |
| T29 | count_above_threshold | **SEARCH/VOCAB** | 0.1498(162) / 0.0(24) / 0.0(24) / 0.0(24) | 21/192 |
| T30 | argmax_index | **SEARCH/VOCAB** | 0.0(24) / 0.0(24) / 0.0(24) / 0.2497(38) | 21/192 |
| T31 | first_greater_than_previous | **SEARCH/VOCAB** | 0.0(28) / 0.05(54) / 0.05(98) / 0.0(24) | 21/192 |
| T32 | longest_increasing_run | **SEARCH/VOCAB** | 0.0(25) / 0.0(24) / 0.0(24) / 0.2497(24) | 21/192 |

**CAPACITY attributions: zero.** No OPEN task produced a train-exact
program at any raised rung within budget; raising the length cap alone
unblocks nothing at these budgets.

Two diagnostic facts sharpen the SEARCH/VOCAB attribution:

1. **The scored-evaluation caveat.** The iteration budget was spent in
   full, but only 24–162 candidates per task-rung survived the
   pre-existing static-plausibility screen to be scored. A control run
   at the default capacity (14, 32, 24) with the identical protocol
   scored a similar 61–107 candidates — the screen's survival rate is
   capacity-independent, so the thin scoring is a property of the
   mutation channel, not an artifact of raised capacity.
2. **Raised capacity actively degrades this channel.** T18's best train
   score is 0.8 at default capacity but ≤ 0.1998 at every raised rung:
   longer random initial programs score worse and hill-climbing recovers
   less. Capacity growth without a search/vocabulary intervention would
   be counterproductive for these tasks.

## F2 — Transfer-pool coverage audit

Recomputed deterministically from the committed artifacts (audit
function `probe_transfer_coverage_audit`, two runs identical):

| Quantity | Value |
|---|---|
| Archive elites | 246 |
| Transfer pool (frozen selection: h8, expanded length 2–12, dedup) | 192 |
| **Offered to the gate** (rule: `pool[w*3:(w+1)*3]`, waves 0–6) | **21 of 192 (10.9%)** |
| MDL-positive discoveries offered | **1 of 773 (0.13%)** |
| Characterized discoveries offered | **15 of 134 (11.2%)** |

The offer set was truncated by construction: batches of 3 per non-final
wave consume at most 21 pool entries in frozen elite order (shortest
first), so 171 of 192 pool bodies — and effectively the entire
MDL-positive set, which was never routed into the pool at all — were
never evaluated by the gate. Every batch is judged against all OPEN
designer probes, so per-task coverage equals the global figure for the
ten tasks that stayed OPEN all run.

## F3 — Stagnation-trigger autopsy

Per-wave trigger conjuncts reconstructed from the final-evaluation
runstate (`docs/transfer_anchor_phaseE.json`):

| Wave | fresh_adopt | mints (reach) | fresh_frontier | trigger fires |
|---|---|---|---|---|
| 0 | 19 | G00, G01 (both frontier) | True | no |
| 1 | 4 | G02, G03 (frontier) | True | no |
| 2 | 3 | G04, G05 (frontier) | True | no |
| 3 | 0 | G06, G07 (frontier) | True | no |
| 4 | 0 | G08, G09 (frontier) | True | no |
| 5 | 0 | G10, G11 (frontier) | True | no |
| 6 | 0 | G12, G13 (frontier) | True | no |
| 7 | 1 (T15) | — (cap reached) | False | final-wave guard |

**Finding: the `not fresh_frontier` conjunct never held on any gated
wave.** Waves 3–6 satisfied `fresh_adopt == 0`, but the mint factory
produced two frontier-classified mints every wave until the
`MAX_GEN_TASKS = 14` cap, and the run ends (WAVES = 8) before any
post-cap wave can go stagnant. Global stagnation is structurally
unreachable at default budgets while pressure minting is active —
confirming the directive's hypothesis. Growth never fired because its
trigger site (`GATE_SKIPPED_NO_FRESH_MATERIAL`) is dead code in
practice, not because capacity was adequate.

### Task-local stagnation specification (spec only; no implementation in Phase F)

- **Progress definition (deterministic):** OPEN designer task `t` makes
  *lineage progress* at wave `w` iff `rs.best_scores[t]` (the cumulative,
  monotone best train score, already tracked) strictly increases at wave
  `w`, or `t` is adopted at wave `w`.
- **Stagnation:** `stagnant(t, w, k)` iff `t` is OPEN at the end of wave
  `w` and made no lineage progress at any of waves `w-k+1 … w`.
- **k = 2, justified:** (i) empirically, every OPEN task's cumulative
  best score in the final evaluation plateaus by wave 3 and never
  strictly improves again (e.g. T18 reaches 0.8 at wave 1, T21 0.85 at
  wave 1, T28 stays 0.0 for all 8 waves), so k = 2 detects every real
  plateau within the 8-wave horizon while k ≥ 3 would leave at most 5
  firing opportunities; (ii) a two-wave plateau spans both stochastic
  channels plus a meta-gate cycle, so one noisy wave cannot fire it;
  (iii) it bounds growth attempts to at most every other wave per task,
  compatible with the existing per-wave speculation budget (2).
- **Firing rule (for Phase G):** a task-local stagnation event proposes
  the next capacity rung through the unchanged gate discipline exactly
  as Phase A does today (same ladder, same bounds ≤56/≤128/≤96, same
  A/B, same logging); the trigger's *reachability* changes, nothing
  about acceptance does. Note: F1 attributes zero OPEN tasks to
  capacity, so under this directive's "no intervention without an
  attributed cause" rule, implementing this spec is justified only if
  Phase G's other interventions surface capacity-blocked residue; the
  spec is delivered for completeness and scored against that rule at
  Phase G planning time.

## Consequence for Phase G (per the directive's shrink rule)

- CAPACITY attributions: zero → **G1 (task-local trigger) has no
  attributed cause today**; the spec above is its complete design if
  cause appears.
- Transfer truncation: **found and large** → **G2 (pool widening) is
  justified** — 171/192 pool bodies and 772/773 MDL-positive
  discoveries were never offered.
- All ten OPEN tasks attribute to SEARCH/VOCAB → **G3 (directed
  generated pressure) is justified** for the full OPEN set.
- **G4 (exploration budget extension) is justified**: the coverage
  curve was still accruing at budget exhaustion, and the transfer
  pathway (the one mechanism with a proven designer-suite transition)
  draws its material from the archive.
