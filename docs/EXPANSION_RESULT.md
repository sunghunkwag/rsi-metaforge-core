# EXPANSION RESULT — Final Evaluation

Two-arm protocol at fixed seeds and identical budgets (SEED=2026,
DATA_SEED=11, GATE_SEED=2027, CF_GATE_SEED=4099, WAVES=8,
RESTARTS_PER_TASK=6, ITERS_PER_RESTART=550), evaluated on the frozen
Phase 0 instrument `docs/frozen_holdout_phase0.json` (SHA-256
`527bb04dd45c010a32637a92eeba5a799024a9a68e944e5c91186d3daa3f4d24`) plus
the sealed suite.

**Claim summary (first paragraph, per claim policy):** one designer-suite
transition (claim type 1): **T15 alternating_sum, OPEN at the Phase 0
baseline, SOLVED by the final live system via an exploration-origin
macro, positive frozen-arm counterfactual, verified on the frozen
instrument**. 773 MDL-positive discoveries (claim type 2) and 134
characterized discoveries (claim type 3), all with exact numbers. One
designer-suite regression is reported alongside: T28 sum_x32, SOLVED at
baseline, is OPEN in the final system — the measured cost of enforcing
GR5 (generated-task gains no longer justify installations). Capacity
growth (Phase A) never fired in any evaluated run — a null result,
reported as such: the machinery exists, is gate-arbitered, and its
triggering condition (a stagnant wave with OPEN designer tasks) did not
occur.

## Arms and reproduction

```bash
# frozen incumbent arm
python3 rsi_levels_metaforge_unified.py --mode run-frozen  --save frozen_final.json
# final live arm (full system: Phases A-C mechanisms + Track 2 transfer pool)
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save live_final.json
# Track 2 anchors (frozen archive, hash-verified)
python3 rsi_levels_metaforge_unified.py --mode anchor-report --save anchor_report.json
```

Both arms and both anchor computations are two-consecutive-run
byte-identical (GR3). Committed artifacts:
`docs/transfer_anchor_phaseE.json` (SHA-256 `82f07438…5bd8a`),
`docs/anchor_report_phaseE.json` (SHA-256 `2c214112…9f00f3`).

Printed outcomes:

| Arm | Designer SOLVED | Generated (pressure, not score) | Digest |
|---|---|---|---|
| frozen incumbent | 19 / 33 | 4 | `e5dc308324bb10f6` |
| final live | 23 / 33 | 4 | `973f7a029c444ec7` |
| (reference: Phase 0 baseline adaptive) | 23 / 33 | 12 | `39d26f1080d4a89b` |

Frozen-arm counterfactual delta of the final live system: **+4 designer
tasks** (T11, T12, T15, T27), none solved only by the frozen arm. Every
adopted designer program in both arms passes the frozen Phase 0
instrument: final live 23/23, frozen 19/19.

## 1. Baseline vs final frontier (per designer task)

| Task | Name | Phase 0 baseline (adaptive) | Final live | Change |
|---|---|---|---|---|
| T00–T10 | core/power tier | SOLVED | SOLVED | — |
| T11 | sumx4_sq | SOLVED | SOLVED | — |
| T12 | sum_x8 | SOLVED | SOLVED | — |
| T13, T14 | middle, sum*max | SOLVED | SOLVED | — |
| **T15** | **alternating_sum** | **OPEN** | **SOLVED** | **OPEN → SOLVED** |
| T16, T17 | prefix_max_sum, second_largest | SOLVED | SOLVED | — |
| T18 | length_conditioned_sum | OPEN | OPEN | — |
| T19, T20 | pairwise_product_sum, first_quartile | SOLVED | SOLVED | — |
| T21 | last_quartile | OPEN | OPEN | — |
| T22 | sum*second_largest | OPEN | OPEN | — |
| T23 | sum*range | OPEN | OPEN | — |
| T24, T25 | parity_conditioned_sum, rolling_pair_sum | SOLVED | SOLVED | — |
| T26 | adjacent_difference_energy | OPEN | OPEN | — |
| T27 | sum_x16 | SOLVED | SOLVED | — |
| **T28** | **sum_x32** | **SOLVED** | **OPEN** | **SOLVED → OPEN (regression)** |
| T29–T32 | search-family walls (expected OPEN) | OPEN | OPEN | — |

## 2. Transitions with adoption lineage

**T15 alternating_sum (OPEN → SOLVED; origin: exploration).**
- Building block: exploration elite `[INPUT, EVENIDX, RED_ADD]` (sum of
  even-indexed elements) from the frozen Phase D archive
  (`docs/exploration_archive_phaseD.json`, SHA-256 `e107d831…a96e`;
  found by seeded exploration with no task-suite access, GR9).
- Gate record: wave 6, `META_ACCEPT [bundle_table] gained=1`; TCCI record
  for macro 106: `recovery_gained_tasks=["T15"]`, `used_in_gain=true`;
  the adoption rode the Rule 3 speculation ledger
  (`kind="exploration_batch"`, accepted).
- Adoption: wave 7, searcher v3, program
  `M106 INPUT ODDIDX RED_ADD SUB` — sum(even-indexed) − sum(odd-indexed),
  the alternating sum by definition.
- Verification: passes the frozen Phase 0 instrument (40 holdout + 30
  counterfactual pairs) and both sealed gates; the frozen arm never
  solves T15.

**T28 sum_x32 (SOLVED → OPEN; regression, cause GR5/B2).**
At baseline, T28's enabling macros were installed at waves 2–5 justified
**only** by generated-task gains (G04–G11). Phase B's hard separation
makes those installations rejections; without them T28 is not reached at
identical budgets. This is the measured cost of removing self-generated
signal from acceptance, reported per the directive's own requirement
(user-authorized single-pin amendment records the same fact:
`mint_adopted == 4`, was `>= 10`).

## 3. Frozen-arm counterfactual

Delta +4 designer tasks (T11, T12, T15, T27); `delta_external = +4`;
no frozen-only solves. Exact reproduction: the two commands above; both
arms byte-identical across consecutive runs.

## 4. Track 2 results

- **Coverage (facts about mapped territory, not capability):** 246 cells
  filled from 60,000 evaluations (curve 28 → 246, still accruing at
  budget exhaustion); 465 insertions; lineage depth up to 26; proposal
  mix ≈ 24.4k mutations / 17.8k random / 17.8k compositions. Every
  archived behavior is either all-crash (6 cells) or near-total
  completion (240 cells) — crash behavior on this ISA is essentially
  input-independent (stack-underflow-driven).
- **MDL-positive discoveries (claim type 2): 773** under the frozen
  encoding (base archive cost 2156 tokens; 880 candidates). Top:
  `[INPUT,INPUT,ZMUL,INPUT,INPUT,ZMUL,ZMUL]` net saving 586 tokens
  (80 elites, defcost 8); `[INPUT,INPUT,ZMUL]` net 524 (140 elites);
  full list with exact numbers in `docs/anchor_report_phaseE.json`.
  Single-macro judgments only (frozen spec); joint compression is
  understated by construction.
- **Characterized discoveries (claim type 3): 134** of 246 elites
  (107 excluded by the frozen triviality list, 5 failed all properties
  and remain unclaimed coverage). Each carries its verified property set
  on the exhaustive domain (all 85 inputs with len ≤ 3, values 0..3)
  plus the frozen seeded extension — e.g. `[INPUT, RED_MAX]`: total,
  permutation-invariant, value/append-monotone, concat-max,
  input-bounded.
- **Exploration-origin adoptions: 1** (macro 106 → T15, lineage above).

## 5. Growth events and speculation ledger

- **Growth events: none fired** in any evaluated run (baseline, Phase B,
  final live). The trigger — a stagnant wave (no fresh adoptions, no
  fresh frontier) with OPEN designer tasks — did not occur; every wave
  had fresh material. The machinery is present, deterministic, bounded
  (≤56/≤128/≤96), and demonstrated under synthetic stagnation by test
  (gate-accepted stack-rung crossing). Honest null.
- **Speculation ledger (final live run): 10 entries** — 8
  `exploration_batch` (1 adopted at wave 6, 7 rejected with hash-verified
  clean rollback), 2 `generated_macro_batch` (1 adopted at wave 1, 1
  rejected clean). Frozen arm: empty ledger. All rollbacks restored the
  certified searcher byte-identically (pre/post hash equality enforced at
  runtime and by test).

## 6. Limitations

- **Circular-evaluation risks that remain:** the meta-gate's enumeration
  screen shares the train-input vectors with the searcher's worktable
  (by design); the frozen holdout/cf gate streams are the external check,
  and the frozen instrument mirrors exactly those streams — a stronger
  external set would use fresh seeds (not available without violating
  the freeze).
- **Nondeterminism encountered: none** in any evaluated command (every
  determinism pair byte-identical). Session containers restarted several
  times mid-run; all evidence was regenerated afterward.
- **Relaxed requirements:** (1) per-phase branches replaced by
  phase-separated commits on the session's mandated branch; (2) one
  user-authorized single-assertion amendment (`mint_adopted >= 10` →
  `== 4`) resolving the B2-vs-GR1 conflict; (3) the Phase E property
  library replaces list-output properties (permutation-of-input,
  sortedness, idempotence, involution, length preservation) with
  scalar-output equivalents because this VM's programs have type
  `List[int] -> int` — frozen before any anchor ran; (4) PRM/WM shaping
  paths and the mint factory keep the historical default stack bound
  (documented in the Phase A report).
- **Negative findings:** T28 regression (above); generated-task lineage
  contributed to zero installed macros in the final run
  (`generated_contributing_macro_lineage = []`) — generated pressure
  shaped scheduling but earned no lasting vocabulary at these budgets;
  capacity growth never triggered outside synthetic tests; T18, T21,
  T22, T23, T26 remain OPEN alongside the four expected-OPEN
  search-family walls; exploration coverage was still growing at budget
  exhaustion (the map is bounded by budget, not by exhausting the
  space).
