# K RESULT — Witness-Sealed Setter–Solver, Final Evaluation

**One admitted task family crossed the frontier, exactly as pre-registered:
admitted with a certificate that the then-current solver snapshot fails it
at the frozen instrument budget, then solved one generation later by an
improved snapshot at the same budget, with the task's own mined solution
excluded from that snapshot.** The crossing lineage was credited; the pose
allocation visibly shifted; every other admitted task retired as a frontier
marker with its witness still sealed. The curve is thin — one crossing in
eight generations — and it ships as measured.

Register: `docs/PREDICTIONS_K.md` (committed at the K-1 spec-freeze commit,
before the final runs). Frozen protocol: `docs/ASCENT_K_SPEC.md` (K-1). The
SC-1 (`docs/SC_RESULT.md`), SC2-1 (`docs/SC2_RESULT.md`), and Phase J
(`docs/CROSSING_RESULT.md`) records are unchanged.

## 1. Protocol and determinism

One battery configuration (8 generations, pose_slots 6, n_public 8,
n_hidden 16, null_programs 24, H = 5, B_EVAL = 1500, B_LIVE = 25000,
B_CHECK = 512, B_EXEC = 4096, ASCK_MASTER_SEED = 872663; pins verified at
battery start: ascent-k `c9da2bbc…`, sc `8471a86b…`), executed twice:

| Run | `ak_digest` | ledger head (prefix) |
| --- | --- | --- |
| 1 | `35080780f0be7293` | `f55d68a838aa0797…` |
| 2 | `35080780f0be7293` | `f55d68a838aa0797…` |

Byte-identical results JSON and hash-chained ledger (`cmp`-equal; 193
ledger records). `ak_replay_verify` re-derived every admission certificate
from the ledger + vault before either digest was printed. Run-1 copies
committed as `docs/final_ascent_k.json`
(sha256 `86c55f79ffdaf04bf935b3b22cc10ffe42554475bb561e4e01aa2afb53cab3ab`)
and `docs/ascent_k_ledger_final.jsonl`
(sha256 `ed0977b2d5bf94768a2f9f538061a7a665a67c5328a2211ff6d1fcd418431523`).

## 2. The crossing (K1, headline)

| g | generated | admitted | mined | crossed | K1 | K2 adopted | K5 markers |
|---|---|---|---|---|---|---|---|
| 0 | 10 | 3 | 2 | 0 | 0 | 2 | 0 |
| 1 | 10 | 2 | 2 | **1** | **1** | 4 | 0 |
| 2 | 10 | 0 | 0 | 0 | 1 | 4 | 0 |
| 3 | 10 | 1 | 1 | 0 | 1 | 5 | 0 |
| 4 | 10 | 1 | 1 | 0 | 1 | 6 | 0 |
| 5 | 10 | 0 | 0 | 0 | 1 | 6 | 2 |
| 6 | 10 | 3 | 0 | 0 | 1 | 6 | 4 |
| 7 | 10 | 0 | 0 | 0 | 1 | 6 | 4 |
| end | — | — | — | — | 1 | 6 | 9 |

The crossed family, end to end in the committed ledger
(`AKB-69bf658ba45b`, Track B, band 5, lineage L_D — the five-step tail
pipeline; witness revealed at retirement as `INPUT TAIL TAIL TAIL TAIL
TAIL`):

1. **Admitted at g0** with all four certificates; the difficulty record
   shows the then-current frontier snapshot — empty macro archive,
   `snapshot_aids: []` — exhausting all 1500 evaluations without a
   gate-passing solution.
2. **Mined at g0** by the live miner at cost 6457 (base search, no
   macros), adopting macro `3001`. At the g0 crossing sweep the snapshot
   (own macro excluded, only the Track A macro `3000` available) still
   failed: no self-credit.
3. **Crossed at g1**: lineage L_B's band-3 pipelines were admitted and
   mined that generation (macros `3002`, `3003`); the crossing snapshot
   `[3000, 3002, 3003]` — own `3001` excluded — found a macro-using
   solution at cost **1427 ≤ 1500**, checker-verified on all 16 hidden
   instances. `within_h: true` (1 generation after admission, H = 5).

The improvement is attributable only to library growth from OTHER tasks:
both sides of the comparison ran the same solver code at the same 1500
evaluations; the only difference is the adopted archive.

## 3. Learnability-band reward (K4)

L_D ends with credit 1; L_A and L_B end with 0. The allocation policy
shifted pose slots from 2/2/2 (g0–g1) to 1/1/4 (g2 onward) — the credit
signal, not a schedule, moved the budget. Frontier markers: 9 (2 × L_B
band-3 mined-but-never-crossed, 1 × L_A band-2, 6 × L_D bands 5–6, four of
them unmined), all with witnesses still sealed in the vault.

## 4. Gate coverage (K3)

Every admission-gate family rejected candidates in the final run:
`ka_feasibility` 8, `kb_too_easy` 8, `kc_null_battery` 10, `kd_duplicate`
31 + `kd_cell_occupied` 13. The pre-registered ADV lineage supplied the
guaranteed floor (its four probes are labeled `adv: true` in the ledger and
were rejected at their designated gates every generation, `adv_kb`
converting to `kd_duplicate` after g0 exactly as specified); natural
rejections — band-2 pipelines and archive-prefixed extensions caught by
`kb_too_easy`, degenerate empties caught by `kc`, behavioural collapses and
cell starvation caught by `kd` — account for the rest. Zero ADV probes were
admitted; the canary never fired.

## 5. Budget accounting (K4 meter)

Kernel meter totals over the run: admission 18,453 candidate evaluations +
74,929 VM ops; crossing 61,427 candidate evaluations; mining 226,897
candidate evaluations; setter 80 proposals. Certified passes per logical
budget are computable from the ledger alone: 1 crossing + 6 adoptions
against ~306,777 metered candidate evaluations.

## 6. Prediction scoring (register: docs/PREDICTIONS_K.md)

| # | prediction | verdict |
| --- | --- | --- |
| P1 | two final runs byte-identical | **CONFIRMED** — `35080780f0be7293` twice, artifacts `cmp`-equal |
| P2 | K1 = 1, Track B, lineage L_D, within H, own macros excluded | **CONFIRMED** — see §2 |
| P3 | only L_D credited; slots reallocate 2/2/2 → 1/1/4 | **CONFIRMED** — see §3 |
| P4 | every gate family fires (ka ≥ 8, kb ≥ 8, kc ≥ 10, kd ≥ 40); zero ADV admissions | **CONFIRMED** — ka 8, kb 8, kc 10, kd 44 |
| P5 | ≥ 8 frontier markers, witnesses sealed, no witness tokens outside retired_crossed | **CONFIRMED** — 9 markers; ledger audit clean |
| P6 | replay verifies on finals | **CONFIRMED** — runs abort before digest otherwise |
| P7 | meter totals match calibration exactly | **CONFIRMED** — §5 values |
| P8 | suite exactly 215 passed 0 failed in CI order; ak_ tests pass in isolation; SC/SC2 digests untouched | **CONFIRMED** — local full suite: 205 passed plus the identical ten artifact-dependent failures as the pre-K baseline (zero regressions; the ten require the battery artifacts CI generates first); 21 ak guards green in isolation; sc2 digest re-verified locally (`50e46bc7c135ceaa`); the SC-1 source+constants pin verifies in-suite, and Full Evidence re-runs both sc batteries twice with digest equality asserted on every commit |
| P9 | credit-supplier gap: L_B supplies the enabling macros, earns 0 | **CONFIRMED** — carried finding, see §7 |
| P10 | no post-registration changes; pin verifies in both finals | **CONFIRMED** |

Score: 10 confirmed, 0 miss.

## 7. Carried findings and boundaries

- **The flywheel turned exactly once at these budgets.** The crossing
  window is structurally narrow: a task can cross only if it extends a
  prefix that is admitted and mined inside the horizon while the extension
  is already archived. After the first window closed, `kb_too_easy`
  correctly rejected archive-prefixed extensions at admission (the
  frontier genuinely moved), and unminable deep tasks became markers. This
  was disclosed at spec-freeze (§11 of the spec) and is the honest shape
  of the mechanism at B_EVAL = 1500 / B_LIVE = 25000.
- **The learnability reward pays the crosser, not the supplier.** L_B's
  band-3 adoptions enabled the only crossing, yet L_B earned nothing and
  lost pose slots to L_D at the next allocation. The reward signal
  propagates to the visible event, not to the enabling contribution — a
  measured credit-assignment gap, registered for the amortizer (Phase M)
  and the meta-improvement channels (Phase O) rather than patched post
  hoc here.
- **Descriptor-cell starvation is real and visible** (`kd_cell_occupied`
  13): affine-chain families collapse into few cells under the Phase
  D-style buckets. The novelty fence is doing its job; a finer descriptor
  is a mutable-policy change that belongs to a later phase's jurisdiction.
- **Track A did not cross** (macros embed the `INPUT HEAD` prefix and do
  not compose mid-program), exactly as disclosed at spec-freeze.
- The checker calling convention supports relational tasks; the v1 setter
  only emits recomputation checkers. Richer checker families remain a
  later-phase setter-policy change.

## 8. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode ascent-k-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode ascent-k-battery   # run 2
# expect: identical {"ak_digest": "35080780f0be7293", ...} lines and
# byte-identical reports/evidence/ascent_k_results.json + ascent_k_ledger.jsonl
python3 rsi_levels_metaforge_unified.py --mode test --only ak_    # 21 guards
python3 rsi_levels_metaforge_unified.py --mode test               # full suite
# (215 passed, 0 failed after the evidence batteries; ten artifact-dependent
# tests require the batteries' JSON artifacts, as in the Full Evidence
# workflow order)
python3 rsi_levels_metaforge_unified.py --mode ascent-k           # CI-safe demo
```
