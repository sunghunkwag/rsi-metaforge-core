# M RESULT — Ledger-Trained Amortizer, Final Evaluation

**Search was amortized from the ledger alone and the gate kept what
worked: certified passes per logical budget on the frozen 48-probe
holdout battery rose from 2 (canonical ordering) to 4 (v0 counting model)
to 6 (the pre-registered single-body ablation retrain) — a 3× uplift —
and the neural retrain, scoring 3 against the incumbent's 6, was ROLLED
BACK on the record.** The attribution is part of the record: most of the
uplift at this corpus scale is the learned INPUT-first root transition
plus inverse-chain bigrams, which is why the near-empty ablation prior
outscores the full model.

Register: `docs/PREDICTIONS_M.md` (committed at the M-1 spec-freeze
commit, before the final runs). Frozen protocol: `docs/ASCENT_M_SPEC.md`
(M-1). The K-1 and L-1 records are unchanged.

## 1. Protocol and determinism

Training corpus: the 11 deduplicated adopted bodies of the chain-verified
committed K-1 and L-1 final ledgers (1 Track A, 10 Track B), every body
hash-matched to its adoption record. Probe battery: 48 sealed tasks built
from the frozen L holdout corpus the training ledgers never contained
(disjointness checked at battery start; the contamination red-team
constructs the violation and asserts abort). Budget: 1500 candidate
evaluations per probe, identical for every candidate. Executed twice:

| Run | `am_digest` | ledger head (prefix) |
| --- | --- | --- |
| 1 | `fc8a471de9f6466f` | `06c73b615657b82f…` |
| 2 | `fc8a471de9f6466f` | `06c73b615657b82f…` |

Byte-identical results JSON and hash-chained ledger. Run-1 copies committed as `docs/final_ascent_m.json`
(sha256 `102ce0ed75c4ad6debef21271458d5e6fbd97ed86837133ea66f9e1d5ad3083e`)
and `docs/ascent_m_ledger_final.jsonl`
(sha256 `61d4b3498cb4e0ff162ab71762756c9b01f03f1e504d3cd49c6c7c0817f0845c`).

## 2. The gate record (M1, headline)

| candidate | passes /48 | disposition |
| --- | --- | --- |
| canonical (incumbent) | 2 | — |
| v0 (full-corpus counting model) | 4 | **adopted** |
| v0_sliceA (single-body ablation retrain) | 6 | **adopted** |
| v1 (fixed-point neural retrain) | 3 | **rolled back** |

Every record carries both pass counts and the full per-probe cost
vectors (M2). Final incumbent: `v0_sliceA` at 6/48 — 3× the canonical
ordering's certified passes at the identical budget. Per-track split:
canonical 0A/2B; v0 1A/3B; v0_sliceA 1A/5B; v1 1A/2B.

## 3. Model discipline (the directive's absolute clause)

Both models are integer-exact and ledger-fed: v0 is Laplace-smoothed
bigram counts over expanded op transitions of the training bodies; v1 is
a one-hidden-layer fixed-point MLP (manual backprop, integer SGD, seeded
init, fixed epochs, training pairs ordered by solution-body hash). The
model path contains no floats, no libm, no unseeded randomness (source-
audited in-suite); `am_solve` under the null model is bit-identical to
the pinned `sc_solve` (tested identity). The amortizer's entire epistemic
diet is the two committed ledgers; a training body without a
chain-verified adoption record aborts.

## 4. Prediction scoring (register: docs/PREDICTIONS_M.md)

| # | prediction | verdict |
| --- | --- | --- |
| P1 | two final runs byte-identical | **CONFIRMED** — `fc8a471de9f6466f` twice |
| P2 | v0 uplift 2 → 4, adopted | **CONFIRMED** |
| P3 | ablation retrain 6/48, adopted; attribution stated | **CONFIRMED** |
| P4 | v1 rolled back at 3 vs 6; final incumbent v0_sliceA | **CONFIRMED** |
| P5 | per-track splits as registered | **CONFIRMED** — §2 |
| P6 | corpus provenance: 11 bodies, chain-verified, probe-disjoint | **CONFIRMED** |
| P7 | null-model identity with sc_solve | **CONFIRMED** (in-suite) |
| P8 | suite 243/0 in CI order; 12 test_am_ green; prior pins verify | **MISS on the literal count** — the L–O code froze in one commit, so the suite at finals time reports 270, not 243. The substance holds: 12 test_am_ guards green in isolation, 0 failures, prior pins verified. Scored as a miss, not reinterpreted |
| P9 | no post-registration changes; three pins verify; loop wiring deferred to Phase O | **CONFIRMED** |

Score: 8 confirmed, 1 miss (P8, literal suite count — see the row).

## 5. Carried findings

- **The rollback is the headline as much as the uplift**: the neural
  retrain lost to a one-body counting prior and the gate said so. An
  amortizer gate that only ever adopts would be indistinguishable from
  self-credit.
- The uplift claim is exactly passes-per-budget on the frozen battery;
  wiring the adopted ordering into the live loop is Phase O Channel A
  jurisdiction (and is registered there as the first candidate).
- The training corpus is thin by honest construction (the K/L records);
  the models learn shallow op-transition statistics, and the ablation
  proves it — that attribution is a measurement, not a defect.

## 6. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode ascent-m-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode ascent-m-battery   # run 2
# expect: identical {"am_digest": "fc8a471de9f6466f", ...} and byte-identical
# reports/evidence/ascent_m_results.json + ascent_m_ledger.jsonl
python3 rsi_levels_metaforge_unified.py --mode test --only test_am_   # 12 guards
python3 rsi_levels_metaforge_unified.py --mode ascent-m           # CI-safe demo
```
