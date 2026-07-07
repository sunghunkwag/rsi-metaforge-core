# L RESULT — MDL Master Gate, Final Evaluation

**One registered, frozen coding formula judged every vocabulary-growth
candidate, adopted two abstractions that compressed the sealed corpus AND
generalized to the frozen holdout, rejected 203 candidates with their
exact bit deltas on record — and the value-judged library crossed MORE
frontiers than Phase K's raw macros at identical budgets: three certified
crossings against one.** The Phase K archive, re-judged by the same
formula, scored zero adoptable bodies: the raw K macros carry no certified
compression value; their compressive content lives in their shared
prefixes. Both findings ship as measured.

Register: `docs/PREDICTIONS_L.md` (committed at the L-1 spec-freeze
commit, before the final runs). Frozen protocol: `docs/ASCENT_L_SPEC.md`
(L-1). The K-1 record is unchanged (read-only load, chain-verified).

## 1. Protocol and determinism

One battery configuration (the K-1 loop constants unchanged; candidate cap
64/generation; holdout `docs/frozen_holdout_ascentL.json` SHA-verified at
start; pins verified: ascent-l `c85150e9…`, ascent-k `c9da2bbc…`),
executed twice:

| Run | `al_digest` | ledger head (prefix) |
| --- | --- | --- |
| 1 | `74ec178cd88013e5` | `eced01d09ea00f93…` |
| 2 | `74ec178cd88013e5` | `eced01d09ea00f93…` |

Byte-identical results JSON and hash-chained ledger. `al_replay_verify`
re-derived every admission certificate, every adoption's exact deltas,
every library snapshot, and the per-generation MDL trajectory before
either digest was printed. Run-1 copies committed as `docs/final_ascent_l.json`
(sha256 `2fd0dbe57b42ad4c4014ad6d4bc1cc778ae5871aedc7223a6e3e606fc2063d07`)
and `docs/ascent_l_ledger_final.jsonl`
(sha256 `d23486d080a80778b5e64c9ead42fe0909994616e241885314661341a354ebf6`).

## 2. The gate record (L1/L2, headline)

Two adoptions, both holdout-validated, with the registered formula's exact
integer numbers:

| aid | body | d_train (bits) | sav_hold (tokens) | d_hold (bits) |
| --- | --- | --- | --- | --- |
| 4000 | `INPUT ODDIDX TAIL` | −24 | +2 | +12 |
| 4001 | `INPUT TAIL` | −6 | +2 | +6 |

203 rejections: 178 `l_mdl_train` (candidates that do not pay their
description cost against the system's own corpus) and 25 `l_mdl_holdout`
— train-only idioms killed by the generalization clause, among them
`INPUT ODDIDX TAIL TAIL` at d_train = −24 with zero holdout occurrences:
the exact overfit shape the clause exists to reject. The code width
`bits(L)` stayed at 6 throughout (the boundary-crossing repricing is
exercised by the red-team test, as disclosed).

## 3. Crossings under the gated vocabulary (L3)

Three certified crossings — each admitted with a snapshot-failure
certificate at B_EVAL = 1500 and crossed at the same budget with
own-sourced entries excluded:

- `AKB-69bf658ba45b` (band 5, L_D, admitted g0 with an EMPTY library
  snapshot): crossed at g0, cost **121**, via `[4000, TAIL]` — expanded
  `INPUT ODDIDX TAIL TAIL`, a four-token route the checker certified on
  all 16 hidden instances, SHORTER than the task's own six-token witness.
  The value-judged abstraction found a genuinely different program.
- `AKB-20fa449a…` and `AKB-0c6c9a14…` (band 3, L_B): crossed at g2 at
  costs 1414 and 1415 with snapshot `[4000, 4001]`.

Final credits: L_A 0, L_B 2, L_D 1 — the Phase K credit-supplier gap
partially closed, because the library is generic rather than task-shaped.

## 4. The Phase K retrofit (L4)

All six committed K bodies were re-judged by the master gate in adoption
order: five rejected `l_mdl_train`, one (`INPUT ODDIDX TAIL TAIL`,
d_train = −24) rejected `l_mdl_holdout`. The K record itself is untouched
— the retrofit is a read-only, chain-verified load.

## 5. Prediction scoring (register: docs/PREDICTIONS_L.md)

| # | prediction | verdict |
| --- | --- | --- |
| P1 | two final runs byte-identical | **CONFIRMED** — `74ec178cd88013e5` twice |
| P2 | exactly 2 adoptions with the stated numbers | **CONFIRMED** — §2 |
| P3 | ≥ 200 rejections, ≥ 20 holdout-clause, the overfit idiom among them | **CONFIRMED** — 203 / 25 |
| P4 | 3 crossings, > K's 1; the 121-cost short route; credits 0/2/1 | **CONFIRMED** — §3 |
| P5 | retrofit rejects all six K bodies (5 train / 1 holdout) | **CONFIRMED** — §4 |
| P6 | replay verifies in both finals | **CONFIRMED** |
| P7 | corpus/library separation exact | **CONFIRMED** — corpus 16, library 2 |
| P8 | bits stays 6 | **CONFIRMED** |
| P9 | suite 231/0 in CI order; 16 test_al_ green; prior pins verify | **MISS on the literal count** — the register assumed per-phase code commits; the single-file architecture led to one L–O freeze commit, so the suite at finals time reports 270, not 231. The substance holds: 16 test_al_ guards green in isolation, 0 failures, all prior pins verified. Scored as a miss, not reinterpreted |
| P10 | no post-registration changes; both pins verify | **CONFIRMED** |

Score: 9 confirmed, 1 miss (P9, literal suite count — see the row).

## 6. Carried findings

- **Value-judged vocabulary beat raw adoption at equal budgets** in this
  configuration (3 crossings vs 1) — the opposite of the trade-off the
  spec's known-boundaries section braced for, measured and shipped.
- Iterative single-candidate adoption and greedy encoding remain
  registered upper-bound choices (Phase E disclosures, carried).
- The holdout clause's savings form (registered before freeze, with the
  strict-delta alternative measured vacuous) did the exact work intended:
  every adoption generalized, every train-only idiom died.

## 7. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode ascent-l-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode ascent-l-battery   # run 2
# expect: identical {"al_digest": "74ec178cd88013e5", ...} and byte-identical
# reports/evidence/ascent_l_results.json + ascent_l_ledger.jsonl
python3 rsi_levels_metaforge_unified.py --mode test --only test_al_   # 16 guards
python3 rsi_levels_metaforge_unified.py --mode ascent-l           # CI-safe demo
```
