# SC RESULT — Self-Curriculum Compounding Loop, Final Evaluation

**The loop compounded internally and did not transfer externally — and the
control arm edged the curriculum arm on the frozen human instrument (24 vs
23 designer tasks at the final checkpoint). Per the pre-registered
protocol, that negative transfer result is the headline.** The system
generated, witness-proved, admitted, and solved 14 distinct tasks with
zero human-authored tasks added; 13 of the 14 solves used gate-adopted
archive macros (library compression), and the composition band climbed
from 2 to 3 through the pre-registered ratchet. The pre-registered pass
threshold for M3 (curriculum strictly above control at g10) was NOT met,
and the expected direction (curriculum ≥ control) was missed at g10:
matched-compute random exploration transferred (+1 designer task over the
empty-pool baseline); the self-curriculum library transferred nothing (±0).

Register: `docs/PREDICTIONS_SC.md` (committed at the spec-freeze commit,
before any official battery run). Frozen protocol:
`docs/SELF_CURRICULUM_SPEC.md` (SC-1). Misses are scored below.

## 1. Protocol and determinism

One battery configuration, frozen before the runs (SC_GENERATIONS=10,
SC_B_LIVE=25000, SC_B_FROZEN 1500→24000, SC_B_WITNESS=4096, MDL α=1/2 +
24-token absolute cap, learnability window [0.2, 0.8],
SC_MASTER_SEED=730117, pin `8471a86b13c61e07e46eb948c1fbc458d2486e24c480224e191549cd3824145f`),
executed twice on the same machine:

| Run | `sc_digest` | ledger head (prefix) |
| --- | --- | --- |
| 1 | `f56c6c13a2bf3028` | `adaafb451679d44e…` |
| 2 | `f56c6c13a2bf3028` | `adaafb451679d44e…` |

Both runs byte-identical (`sc_battery_results.json` and
`sc_ledger.jsonl` compare equal with `cmp`). Artifacts:
`reports/evidence/sc_battery_results.json`,
`reports/evidence/sc_ledger.jsonl` (uploaded by the Full Evidence
workflow); run-1 copies are committed as `docs/final_sc_battery.json`
and `docs/sc_ledger_final.jsonl`.

## 2. The compounding curves (M1, M2, M4)

Full ledger accounting: 96 candidates generated, 16 admitted, 80 rejected
with reasons (i5_frozen 42, i4_duplicate 32, i1_identity 5, i8_archive 1),
14 solved, 4 unsolved attempts, every task retired by end of run,
`human_authored_tasks: 0`.

| g | band | B_frozen | generated | admitted | solved | M1 (cum distinct) | M2 (max adm band) | M4 (median cost @ band 2) | ratchet |
|---|------|----------|-----------|----------|--------|-------------------|-------------------|---------------------------|---------|
| 0 | 2 | 1500 | 8 | 4 | 4 | 4 | 2 | 945 | tighten_i5 |
| 1 | 2 | 3000 | 8 | 1 | 1 | 5 | 2 | 1134 | tighten_i5 |
| 2 | 2 | 6000 | 8 | 3 | 3 | 8 | 2 | 1737 | tighten_i5 |
| 3 | 2 | 12000 | 8 | 2 | 2 | 10 | 2 | 3037 | tighten_i5 |
| 4 | 2 | 24000 | 8 | 1 | 1 | 11 | 2 | 4037 | tighten_i5 (capped) |
| 5 | 2 | 24000 | 8 | 2 | 1 | 12 | 2 | 4199 | band_up → 3 |
| 6 | 3 | 24000 | 12 | 0 | 0 | 12 | — | — | hold |
| 7 | 3 | 24000 | 12 | 0 | 0 | 12 | — | — | hold |
| 8 | 3 | 24000 | 12 | 1 | 0 | 12 | 2 | — | hold |
| 9 | 3 | 24000 | 12 | 2 | 2 | 14 | 3 | — | tighten_i5 (capped) |

**M1 decomposition (pre-registered honesty split):** 14 solved total —
**13 solved using archive macros** (library compression: the compounding
channel), **1 solved by base search only** (the frozen-vs-live budget
gap). The g6–g8 stall and the band-3 recovery at g9 (two macro-compressed
solves) are the curve's shape; nothing is smoothed.

**M4 rose, as pre-registered (observation 2 / P4):** 945 → 1134 → 1737 →
3037 → 4037 → 4199 → null. The I5 tightening rule raises the admission
floor inside the reference band, selecting progressively harder tasks —
the amortization signal is confounded by design and is reported as
confounded.

## 3. Transfer anchor (M3) — the pre-registered external judge

Both arms offer their whole library on the frozen human instrument via
the existing offer machinery (`run_system(adaptive=True,
exploration_pool=…)`, cursor-walk schedule), at matched compute E(g)
(cumulative SC candidate evaluations, read from the hash-chained
`gen_summary` records):

| checkpoint | E(g) | curriculum arm (pool) | control arm (pool) | adoption digest cur / ctl |
| --- | --- | --- | --- | --- |
| g0 | 0 | **23** (0) | **23** (0) | `93338b61e81fe6e1` (shared) |
| g5 | 115074 | **23** (11) | **23** (256) | `93338b61e81fe6e1` / `af91ede07019d45d` |
| g10 | 462095 | **23** (14) | **24** (256) | `93338b61e81fe6e1` / `1de5e00505b309cf` |

- The curriculum arm's 14 offered bodies (affine-chain inverses and short
  list pipelines) were never adopted by the instrument searcher: its
  adoption digest equals the empty-pool baseline at every checkpoint —
  the library is behaviorally inert on the human instrument.
- The control arm (the existing exploration regime at the same
  candidate-evaluation budget) produced bodies that the gate adopted and
  that converted one additional designer task at g10 (24 vs the 23
  baseline).
- Pre-registered pass threshold (curriculum > control at g10): **not
  met**. Pre-registered direction (curriculum ≥ control): **missed at
  g10** (23 < 24). Both arms landed within ±1 of the baseline, as
  predicted. This is the phase's headline.

## 4. Prediction scoring (register: docs/PREDICTIONS_SC.md)

| # | prediction | verdict |
| --- | --- | --- |
| P1 | two battery runs byte-identical (`sc_digest`) | **CONFIRMED** — `f56c6c13a2bf3028` twice; artifacts `cmp`-equal |
| P2 | loop portion reproduces calibration exactly (M1 final 14, band 3, archive 14, E(10)=462095) | **CONFIRMED** |
| P3 | compounding evidence: I5-passed admissions; band-≥3 solves only after archive non-empty; ≥1 `used_macro` solve; monotone M1 with g6–g8 stall | **CONFIRMED** — 13/14 solves `used_macro`, band-3 solves at g9, stall as predicted |
| P4 | M4 rises or goes null (confound pre-registered, against the naive falling expectation) | **CONFIRMED** — rose then null |
| P5 | transfer threshold NOT met; both arms within ±1 of baseline 23 | **CONFIRMED on the threshold and the ±1 band; the direction sub-claim (curriculum ≥ control) MISSED at g10** — control 24 > curriculum 23. Reported as the headline, per protocol |
| P6 | g0 checkpoint: designer 23, digest `93338b61e81fe6e1`, twice | **CONFIRMED** |
| P7 | full suite exactly 178 passed, 0 failed, batteries-first order; Phase J record untouched | **CONFIRMED** |
| P8 | ledger integrity: full denominators; no witness before retirement; identical chain heads | **CONFIRMED** — 96 = 16 + 80 per generation; witnesses appear only in `retired` records |

Score: 7 confirmed, 1 partial (P5: threshold and band confirmed,
direction sub-claim missed — the miss direction is *against* the
curriculum arm, i.e., the conservative direction for this program's
claims).

## 5. Carried findings and boundaries

- **What compounding was measured:** within the loop's own closed world,
  library compression is real and dominant (13/14 solves macro-compressed;
  a +6-step task unsolvable bare at the live budget solves at a fraction
  of the budget with a half-depth macro). The band ladder moved 2 → 3
  through the pre-registered window, with the I5 budget ratchet exhausting
  its cap first — the fence (frozen primitive grammar, band ceiling 12)
  was nowhere near saturated in 10 generations.
- **What did not happen:** no transfer to the frozen human instrument. The
  SC library is affine/pipeline material; the instrument's open walls need
  vocabulary this grammar cannot produce. Matched-compute random
  exploration DID transfer (+1) — undirected behavioral coverage beat
  directed self-curriculum on this external test, at these budgets, in
  this domain. That comparison was the point of the pre-registration.
- Known boundaries from the spec (solver/gate cap divergence — zero
  occurrences in the run; sampler reconstructibility; M1's budget-gap
  component) stand as disclosed; `end_retired` = 0 (every open task
  retired through the attempt limit before the run ended).
- No constant was changed after spec-freeze; no run was discarded; this
  is the first and only official battery execution pair.

## 6. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode sc-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode sc-battery   # run 2
# expect: identical {"sc_digest": "f56c6c13a2bf3028", ...} lines and
# byte-identical reports/evidence/sc_battery_results.json + sc_ledger.jsonl
python3 rsi_levels_metaforge_unified.py --mode test         # 178 passed, 0 failed
python3 rsi_levels_metaforge_unified.py --mode self-curriculum   # CI-safe demo
```
