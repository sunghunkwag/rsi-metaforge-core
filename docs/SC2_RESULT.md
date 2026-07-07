# SC2 RESULT — Fence Expansion, Final Evaluation

**The permanent-schema count stayed at zero for the whole run.** That is
the headline, unsoftened, exactly as the pre-registered protocol requires.
The fence itself moved — the system invented, gate-admitted, and solved
task kinds no prior template expressed (cross-capsule base-8 digit-record
products and corpus-fed families), with 28 provisionally-credited solves
across all four templates — but no schema earned permanence: every M5
ablation delta was exactly 0 (sibling-macro redundancy at the frozen live
budget), so every solved schema retired at its probation window and the
permanent credit curve ends at 0.

Register: `docs/PREDICTIONS_SC2.md` (committed at the SC2 spec-freeze
commit, before any official sc2 battery run). Frozen protocol:
`docs/SELF_CURRICULUM_SPEC_V2.md` (SC2-1). Directive 1's record
(`docs/SC_RESULT.md`) is unchanged.

## 1. Protocol and determinism

One battery configuration (8 generations, forge 3/gen, kill_min 4/5,
disc_min 3/4, collude_max 1/2, probation window 4, M5 delta ≥ 1,
B_FROZEN=1500, B_LIVE=25000, SC2_MASTER_SEED=411941; pins verified at
battery start: sc `8471a86b…`, sc2 `85673e90…`, corpus manifest
`07258950…`), executed twice:

| Run | `sc2_digest` | ledger head (prefix) |
| --- | --- | --- |
| 1 | `50e46bc7c135ceaa` | `24f1b39acf96e06a…` |
| 2 | `50e46bc7c135ceaa` | `24f1b39acf96e06a…` |

Byte-identical results JSON and hash-chained ledger (`cmp`-equal; 911
ledger records). Artifacts: `reports/evidence/sc2_battery_results.json`,
`reports/evidence/sc2_ledger.jsonl`; run-1 copies committed as
`docs/final_sc2_battery.json` and `docs/sc2_ledger_final.jsonl`.

## 2. The fence-expansion curve (M6, headline) and provisional credit

| g | schemas admitted | schemas rejected | tasks admitted | tasks rejected | solved | provisional cum | permanent cum | M6 |
|---|---|---|---|---|---|---|---|---|
| 0 | 3 | — | 6 | 7 | 5 | 5 | 0 | 0 |
| 1 | 2 | i6_infeasible 1 | 8 | 26 | 6 | 11 | 0 | 0 |
| 2 | 2 | i6_infeasible 1 | 10 | 47 | 6 | 17 | 0 | 0 |
| 3 | 1 | i18_duplicate 1, i6_infeasible 1 | 6 | 56 | 6 | 23 | 0 | 0 |
| 4 | 1 | i6_infeasible 2 | 4 | 75 | 3 | 26 | 0 | 0 |
| 5 | 1 | i6_infeasible 2 | 2 | 51 | 2 | 28 | 0 | 0 |
| 6 | 0 | i6_infeasible 3 | 0 | 36 | 0 | 28 | 0 | 0 |
| 7 | 0 | i6_infeasible 3 | 0 | 36 | 0 | 28 | 0 | 0 |

Full-ledger accounting: 24 schemas generated, 10 admitted, 14 rejected
(13 `i6_infeasible`, 1 `i18_duplicate_schema` — the T_B family claiming
territory already held by the corpus-fed T_BC schema, exactly as the
input-independent behavioral signatures require). Task rejections, all
ledgered: `i4_duplicate` 269, `i5_frozen` 38, `i1_identity` 25,
`i8_archive` 2. `human_authored_tasks: 0`; archive 28 adopted solutions.

## 3. M5 — schema transfer credit (the permanence criterion)

Every solving schema was ablation-tested (archive with vs without its
adopted solutions, both solving the 6 most recent other-schema tasks at
the frozen live budget):

| schema | template | checkset | provisional solves | M5 (full / ablated / delta) | disposition |
| --- | --- | --- | --- | --- | --- |
| SCH-3bb308a6f7fd | T_A | (5,) | 10 | 5 / 5 / **0** | retired (window) |
| SCH-4c33b2ceef46 | T_BC | (5,) | 9 | 6 / 6 / **0** | retired (window) |
| SCH-b176e12f309a | T_X | (5,) | 1 | 5 / 5 / **0** | retired (window) |
| SCH-b4ccf388b27b | T_B | (5,) | 2 | 5 / 5 / **0** | retired (window) |
| SCH-60d7ac481c82 | T_A | (2,5) | 6 | 5 / 5 / **0** | retired (window) |
| SCH-79df3be26424 | T_X | (2,5) | 0 | — | retired (window) |
| SCH-e88dedfde444 | T_A | (1,5) | 0 | — | retired (window) |
| SCH-6feec9fa444d | T_BC | (1,5) | 0 | — | retired (window) |
| SCH-e47828026545 | T_BC | (4,5) | 0 | — | probation at end of run |
| SCH-9e4ef3f3d5ea | T_B | (4,5) | 0 | — | probation at end of run |

The zero deltas are marginal-value measurements, not absences of
capability: with five sibling schemas contributing 28 macros, removing any
one schema's contribution leaves substitutes that solve the same eval
tasks at the same budget. The frozen-anchor ablation report (M5b) is empty
by protocol — it runs only for permanent schemas, and there were none.

## 4. M7 — corpus sealed shard

| checkpoint | solved / total |
| --- | --- |
| g0 | 0 / 0 (empty library, definitional) |
| g8 (final) | **6 / 6** |

Six tasks minted inside the gate from the sealed corpus shard (never
readable by the forge, poser, or solver — enforcement red-teamed in
`test_sc2_sealed_shard_access_denied`) were all solved by the final
library; no sealed-shard solution was adopted.

## 5. Prediction scoring (register: docs/PREDICTIONS_SC2.md)

| # | prediction | verdict |
| --- | --- | --- |
| P1 | two runs byte-identical | **CONFIRMED** — `50e46bc7c135ceaa` twice, artifacts `cmp`-equal |
| P2 | loop reproduces calibration (28 provisional, archive 28, M6 = 0) | **CONFIRMED** |
| P3 | headline: permanent-schema count stays at zero; all M5 deltas below threshold | **CONFIRMED** — all measured deltas exactly 0 |
| P4 | provisional/permanent separation (I19) | **CONFIRMED** — provisional 28 vs permanent 0, never merged |
| P5 | M7 final checkpoint solves ≥ 1, no adoption | **CONFIRMED** — 6/6, zero adoptions |
| P6 | fence-expansion evidence short of permanence: T_X and T_BC families admitted and solved where the frozen baseline provably cannot enter | **CONFIRMED** — T_X 1 solve (codec-crossing), T_BC 9 solves (corpus-fed) |
| P7 | full suite exactly 194 passed, 0 failed; D1 digest and Phase J record untouched | **CONFIRMED** — see reproduction; `sc_digest f56c6c13a2bf3028` re-verified by the committed artifacts |
| P8 | ledger integrity: every schema/task dispositioned; retired schemas keep provisional credit visible; identical chain heads | **CONFIRMED** — 911 records, chain verified in both runs |

Score: 8 confirmed, 0 miss.

## 6. Carried findings, boundaries, and deviations

- **What the fence move bought:** new task KINDS were invented as pure
  data and genuinely exercised — the cross-capsule T_X family (integer →
  base-8 digit record → digit reversal → integer) is inexpressible in
  Directive 1's grammar and unsolvable by the frozen baseline by
  construction; the corpus tap fed real external byte streams into task
  material under full witness discipline; the sealed shard scored 6/6.
- **What it did not buy, at these budgets:** measured transfer. Marginal
  schema value was zero everywhere the protocol looked; probation
  retirement did its job. The judging language never moved: zero
  mutation-kill exemptions, zero relation-library edits, zero
  out-of-grammar schemas admitted (`i16` red-teamed; `i15_vacuous`
  observed live in calibration).
- Schema starvation via global behavioral signatures dominates late
  generations (`i4_duplicate` 269, `i6_infeasible` 13) — the enumeration
  space at band 2 is claimed quickly; bands 3–4 were never reached by the
  forge in 24 proposals. A longer run or band-mixed forge order is the
  obvious v2 lever; per the spec it stays frozen for this record.
- **Deviations from Directive 2, with reasons:** (1) gd/file-world
  substrates are not packaged as capsules v1 — no frozen template
  consumes them, and dead capsule wrappers would violate the no-stub
  rule; (2) SC2 task admission mirrors the D1 I1–I9 battery in
  `sc2_admit` rather than calling the pinned `sc_admit` — the D1 runner
  cannot execute codec tokens and D1 code is read-only under this
  directive; the mirror is inside the SC2 pin; (3) CF1 and CF5 are
  mechanically identical in this harness (single-witness labeling), kept
  as separate named forms for auditability; (4) the spec doc's
  `SC2_PIN_SHA256` table row initially transcribed a stale calibration
  pin and was corrected in the results commit — the pinned CODE constant
  was frozen at the spec-freeze commit and never changed (verifiable in
  git history); the battery verified against the code constant.

## 7. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode sc2-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode sc2-battery   # run 2
# expect: identical {"sc2_digest": "50e46bc7c135ceaa", ...} lines and
# byte-identical reports/evidence/sc2_battery_results.json + sc2_ledger.jsonl
python3 rsi_levels_metaforge_unified.py --mode test          # 194 passed, 0 failed
python3 rsi_levels_metaforge_unified.py --mode schema-forge  # CI-safe demo
```
