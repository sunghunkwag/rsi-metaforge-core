# O RESULT — Meta-Improvement & Recursion Closure, Final Evaluation

**The improver is inside the modification scope, and both adoption
channels are live with adoptions AND rejections on record. Channel B
adopted two kernel-certified completeness-preserving search
transformations and refused the pre-registered false-premise
instantiation. Channel A, on frozen instruments at equal budgets, adopted
the ledger-trained amortizer (2 → 6 passes) and the MOD vocabulary grant
(6 → 8, with the extender protocol end-to-end: impossibility
pre-certificate `mod 0/6` before, crossing evidence `mod 2/6` after),
and rolled back the useless SELECT grant and the worse setter policy.
End-to-end: certified passes per logical budget on the union battery rose
4×, every step through a channel, with every frozen-kernel pin intact.**

Register: `docs/PREDICTIONS_O.md` (committed at the O-1 spec-freeze
commit, before the final runs). Frozen protocol: `docs/ASCENT_O_SPEC.md`
(O-1). Phases K/L/M/N records are unchanged.

## 1. Protocol and determinism

All five ascent pins verified at battery start (K `c9da2bbc…`,
L `c85150e9…`, M `aada1e9c…`, N `df7fc303…`, O `bae57bdf…`). Executed
twice:

| Run | `ao_digest` | ledger head (prefix) |
| --- | --- | --- |
| 1 | `f064a014d33b3f89` | `38969e84ab533fed…` |
| 2 | `f064a014d33b3f89` | `38969e84ab533fed…` |

Byte-identical results JSON and hash-chained ledger. Run-1 copies committed as `docs/final_ascent_o.json`
(sha256 `60f76483d0d2435ef2cc07ce77b36ad6cbe50fcafa21a6a783417ba7ec3ae6eb`)
and `docs/ascent_o_ledger_final.jsonl`
(sha256 `3ce8c2ef7610215ee6b3824b5c96ea53efc8c28b43c34615d35600cc8bb45bc8`).

## 2. Channel B — certified (O2)

The two schema-skeleton proof objects (161 kernel steps each; committed
generator `docs/make_schema_proofs_ascentO.py`; pinned artifact SHA
`b4144faa…`) were re-verified by the frozen N-1 kernel at battery start.
Instantiations — proposed by mutable code, checked by the kernel with the
substitution composed through every proof step:

- **S1_depth1_crash_prune** (skeleton B): adopted; premise verified
  exhaustively by execution (all 16 excluded ops crash on the empty
  stack across every frozen probe input).
- **S2_input_required** (skeleton C): adopted; per-task premise (varying
  publics) verified by direct inspection at solve time.
- **S1_bad_premise_red_team**: the pre-registered false premise (`INPUT`
  smuggled into the exclusion set) REFUSED (`o_premise_false`) and
  rolled back on record.

The certified filters are proven non-lossy in-suite (same solutions, no
greater cost, on a probe sample); no benchmark was needed for adoption —
the certificates are about the search space.

## 3. Channel A — empirical (O1) and the extender protocol (O3)

Sequential counterfactual A/B on the frozen union instrument (48 Phase M
holdout probes + 6 MOD probes) at exactly 1500 evaluations per probe:

| candidate | jurisdiction | passes /54 | disposition |
| --- | --- | --- | --- |
| incumbent (base vocab, canonical order, schemas) | — | 2 | — |
| A1_amortizer_v0_sliceA | solver policy | 6 | **adopted** |
| A2_extender_grant_MOD | ISA extender | 8 | **adopted** — `mod 0/6 → 2/6` |
| A3_extender_grant_SELECT | ISA extender | 8 | **rolled back** (no strict improvement) |
| A4_setter_LD_band6 | setter policy | 4 vs 4 | **rolled back** (loop-arm A/B) |

The extender protocol ran end-to-end on record: the impossibility
pre-certificate (the pre-grant configuration passes 0 of the 6 MOD
probes at budget — a measured certificate, not an assumption) precedes
the grant; the crossing evidence (2 of 6 MOD probes pass at the same
budget) follows it; and the second grant demonstrates that extender
modifications do not pass by default.

End-to-end recursion closure: union-battery passes 2 → 8 at identical
budgets. Every constitutional component (vault, meter, ledger, replay,
MDL formula, proof kernel, anti-cheat pins) is untouched by every adopted
modification: the adopted improver lives entirely in mutable-citizen
territory (vocabulary, ordering, filters).

## 4. Prediction scoring (register: docs/PREDICTIONS_O.md)

| # | prediction | verdict |
| --- | --- | --- |
| P1 | two final runs byte-identical | **CONFIRMED** — `f064a014d33b3f89` twice |
| P2 | Channel B: 2 adoptions + red-team refusal | **CONFIRMED** — §2 |
| P3 | Channel A: adopt/adopt/rollback/rollback across three jurisdictions | **CONFIRMED** — §3 |
| P4 | extender protocol end-to-end with pre/post certificates | **CONFIRMED** — §3 |
| P5 | recursion closure 2 → 8 at equal budgets | **CONFIRMED** |
| P6 | certified filters non-lossy | **CONFIRMED** (in-suite) |
| P7 | suite 270/0 in CI order; 12 test_ao_ green; five pins verify | **CONFIRMED** — see §6 |
| P8 | no post-registration changes; no order-optimality claim | **CONFIRMED** |
| P9 | constitution intact under every adopted modification | **CONFIRMED** |

Score: 9 confirmed, 0 miss.

## 5. Carried findings

- The amortizer adopted here is the Phase M incumbent, completing the
  jurisdiction hand-off the M spec registered: measured on its own
  frozen battery there, adopted into the improver through Channel A
  here.
- Channel B's honest split — kernel-certified logic over exhaustively
  verified executable premises — is the v0 shape of certified search
  transformation. Richer schemas (dedup completeness, ordering
  exchange over full sweeps) want a VM-semantics-aware formalism, which
  is amendment-path territory, not a v0 gap to paper over.
- A4's rejection is jurisdiction working as intended: setter-policy
  changes are now inside the A/B protocol, and the first candidate
  measured was not an improvement — so it did not ship.

## 6. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode ascent-o-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode ascent-o-battery   # run 2
# expect: identical {"ao_digest": "f064a014d33b3f89", ...} and byte-identical
# reports/evidence/ascent_o_results.json + ascent_o_ledger.jsonl
python3 rsi_levels_metaforge_unified.py --mode test --only test_ao_   # 12 guards
python3 rsi_levels_metaforge_unified.py --mode ascent-o           # CI-safe demo
```
