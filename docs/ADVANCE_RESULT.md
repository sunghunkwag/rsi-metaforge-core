# ADVANCE RESULT — Phase G Final Evaluation

**Final designer count: 22/33 on the frozen Phase 0 instrument — the
≥ 24/33 threshold is NOT met. This is a null result, reported plainly.**
T15 is retained (re-adopted at wave 1 via exploration macro 102,
`M102 INPUT ODDIDX RED_ADD SUB`, frozen-instrument verified). T28 is
NOT re-solved in the final configuration; the secondary finding is
therefore split: T28 **was** re-solved through fully designer-justified
acceptance in the G3-only development configuration (committed,
deterministic, digest `93338b61e81fe6e1` — wave-2 gate record
`gained=['T28']`, macro mined from that run's own T27 adoption, program
`M106 M106 ZMUL RED_ADD`), but the combined G2+G3 final system loses it,
along with T27 — an interaction effect diagnosed below. GR5 remained
fully intact throughout; predictions were registered before the final
run and are scored below (10/12 hits, with the T28 miss being the
disclosed known-at-prediction-time case and T27's regression entirely
unpredicted).

## Arms, reproduction, determinism

```bash
# frozen incumbent
python3 rsi_levels_metaforge_unified.py --mode run-frozen --save frozen_final.json
# final live (G2 widened offers + G3 directed pressure + G4 extended archive)
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save live_final.json
```

Both arms run twice, byte-identical (GR3):

| Arm | Designer SOLVED | Digest | Two-run identity |
|---|---|---|---|
| final live | 22 / 33 | `47324408543b7365` | byte-identical |
| frozen incumbent | 19 / 33 | `e5dc308324bb10f6` (unchanged since Phase 0) | byte-identical |

Committed artifact: `docs/final_live_phaseG.json`. Every adopted
designer program in both arms passes the frozen Phase 0 instrument
(live 22/22, frozen 19/19). Runtime: each live run ~55 min wall (~42
CPU-min; ~90 gate batches at the stated offer bounds); no run truncated.

## Interaction diagnosis (the phase's central finding)

At wave 0 the widened, MDL-gain-ordered offer stream installed
exploration macros 101 (`[INPUT,INPUT,ZMUL,INPUT,INPUT,ZMUL,ZMUL,
RED_ADD]` — a complete sum-of-x⁴ program body, int-valued) and 102
(`[INPUT,EVENIDX,RED_ADD]`), immediately gaining T11, T12 (and T15 at
wave 1). In the plain G3 arm those same tasks were solved via the mined
list-valued fragment `[INPUT,INPUT,ZMUL]`-family macros, and the
wave-1/2 mining over THOSE adopted programs produced the composable
x¹⁶ stepping-stone that gated T27 and then T28. In the final arm the
adopted T11/T12 programs are built from the terminal macro 101, the
stepping-stone never gets mined (86 consecutive designer-gain rejections
across waves 1–3), and T27/T28 stay OPEN.

**Finding: greedy MDL-gain ordering front-loads self-contained
compressors (int-valued full solutions) over composable list-valued
intermediates, and early terminal installs can flatten the curriculum
gradient that compositional adoption depends on.** Wider offers are not
monotonically better under a compression-greedy ordering.

## Per-task table: attribution → intervention → predicted → actual

| Task | F attribution | Intervention | Predicted | Actual | Score |
|---|---|---|---|---|---|
| T18 | SEARCH/VOCAB | G2+G3 | OPEN | OPEN | hit |
| T21 | SEARCH/VOCAB | G2+G3 | OPEN | OPEN | hit |
| T22 | SEARCH/VOCAB | G2+G3 | OPEN | OPEN | hit |
| T23 | SEARCH/VOCAB | G2+G3 | OPEN | OPEN | hit |
| T26 | SEARCH/VOCAB | G2+G3 | OPEN | OPEN | hit |
| T28 | SEARCH/VOCAB | G3 (+G2) | SOLVED (known-at-prediction-time, not foresight) | **OPEN** | **miss** |
| T29 | SEARCH/VOCAB | G2+G3+G4 | OPEN | OPEN | hit |
| T30 | SEARCH/VOCAB | G2+G3+G4 | OPEN | OPEN | hit |
| T31 | SEARCH/VOCAB | G2+G3+G4 | OPEN | OPEN | hit |
| T32 | SEARCH/VOCAB | G2+G3+G4 | OPEN | OPEN | hit |
| T15 | retention | G2 full pool | SOLVED (retained) | SOLVED | hit |
| T27 | (not OPEN at prediction time — not predicted) | — | — | **OPEN (regression)** | unpredicted |

Prediction score: 10 hits / 12 rows (the T28 miss is the disclosed
development-run observation failing to transfer to the combined
configuration; T27's regression was outside the prediction table
entirely). The disclosed risk clause ("either T15 or T28 could fail to
land → 23/33") underestimated the interaction: the actual outcome is
22/33 because T27 fell with T28.

## OPEN → SOLVED lineage (relative to the v2 final system)

None net-new. T15 (OPEN at the Phase 0 baseline) is retained via a
re-derived lineage: exploration elite `[INPUT,EVENIDX,RED_ADD]` from the
extended archive → wave-0 `bundle_table` acceptance (designer-only A/B;
speculation-ledger kind `exploration_batch`) → wave-1 adoption
`M102 INPUT ODDIDX RED_ADD SUB` → passes the frozen Phase 0 instrument
(40 holdout + 30 counterfactual pairs). The G3-only T28 lineage
(designer-justified, from that run's own T27) is committed evidence of
the scaffolding-replacement mechanism working in isolation, but it is
not part of the final-protocol frontier and is claimed only as such.

## Frozen-arm counterfactual

Delta +3 designer tasks (T11, T12, T15 — live-only; no frozen-only
solves). For reference, the v2 final system's delta was +4 (T11, T12,
T15, T27): the Phase G configuration gives back T27 (interaction
diagnosed above) while re-deriving T15 through the widened offer path.

## Track 2 updated counts (G4)

- Archive: 246 → **404 cells** (append-only; Phase D curve prefix
  replayed exactly; 106 elites replaced strictly-cheaper; two runs
  byte-identical; SHA-256 `23dda0d8…76b4`).
- Coverage curve extension: 246 cells @60k evals → 404 @120k, still
  accruing at budget exhaustion.
- MDL-positive discoveries: 773 → **1216** (frozen spec; exact numbers
  in `docs/anchor_report_phaseG.json`, SHA-256 `5e444760…2689`).
- Characterized discoveries: 134 → **231** (frozen property library).
- Frozen-instrument hash checks: unchanged and passing.

## Growth and speculation summaries

- Capacity growth: not built (G1 had no attributed cause) and the Phase
  A global trigger never fired; growth log empty in all final-eval arms.
- Speculation ledger (final live run 1): 99 entries — 98
  `exploration_batch` (2 adopted at wave 0, 96 rejected with
  hash-verified clean rollback; full pool walked, offer cursor 294) and
  1 `generated_macro_batch`; frozen arm: empty ledger.

## Leakage attestation (zero-tolerance clause, substantiated)

The claim "no baseline T28 solution seeding" is substantiated by code
location and artifact inventory:

1. **G3 code paths read only current-run state.** `propose_mints`
   (directed block, lines 679–706) reads `rs.tasks`,
   `rs.adopted_tokens`, `rs.residues`, `rs.searcher.macros` — all
   constructed within the running evaluation; the function performs no
   file I/O (verified: zero `open`/`json.load` calls in its body).
   `_gen_oracle`'s `diff` op (lines 630–644) reads the oracle-callable
   registry `_ORACLE_REGISTRY` (line 577; environment-held functions,
   not programs) plus the spec-embedded expansion of a current-run
   residue. `mint_task` (648) and `mint_step` (739) likewise touch only
   `rs`.
2. **No committed artifact contains the baseline T28 program.** The
   Phase 0 baseline runstates (the only place that program's tokens
   ever existed) were session-scratch files and were never committed.
   `docs/transfer_anchor_phaseE.json` has no T28 adoption (verified);
   `docs/attribution_probe_phaseF.json` stores hash+length only (and
   its probes found nothing for T28); the exploration archives evolved
   from scratch under GR9 sealing with vocabulary macros
   `100=[4,4,25]`, `103=[100,100,25]` whose recorded parents are
   T05/T08/T10/T11/T12.
3. **The final evaluation reads exactly two committed inputs** — the
   hash-pinned `exploration_archive_phaseG.json` (loader at line 15614)
   and `anchor_report_phaseG.json` — neither of which contains any
   T28-derived content by (2).
4. The G3-only T28 re-solve is itself evidence of non-leakage: its
   program `M106 M106 ZMUL RED_ADD` is compositionally derived from
   that run's own T27 adoption (macro parents recorded in the artifact)
   and differs in structure from anything available to seed.

## Limitations

- **The central negative:** interventions interact. G2's widened,
  MDL-ordered offers and G3's directed pressure each work in isolation
  (T15 early re-adoption; T28 re-solve respectively) but combined they
  produced the worst designer count of any Phase G configuration
  (22 vs 23 plain-G3 vs 23 v2-final). The attribution table did not
  model install-order effects; the results contradict the implicit
  assumption that offers are monotone in coverage.
- The MDL-gain ordering is the suspect component: it ranks terminal
  compressors above composable intermediates. A composability-aware
  ordering was not built (it was not in the registered intervention
  set) and remains future work requiring a new directive.
- T28's re-solve exists only in the G3-only configuration; under the
  registered final protocol the secondary finding is a null.
- The 10 remaining OPEN causes stand as attributed in Phase F
  (SEARCH/VOCAB), now refined: for T27/T28 the specific missing object
  is a composable list-valued power fragment in the installed
  vocabulary at the right wave.
- Runtime: each final live run ≈ 55 minutes (≈ 90 gate batches at the
  stated offer bounds), 4-run protocol ≈ 2 hours — bounded and spent in
  full; no run was truncated or sampled.
