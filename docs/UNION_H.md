# Phase H — Union Table (H1)

The existence proof, made citable. All rows derive from committed,
deterministic artifacts; every configuration is two-consecutive-run
byte-identical at fixed seeds and identical budgets, fully
de-circularized (GR5 in force throughout).

## Configurations

| Configuration | Artifact | Digest | Designer solved |
|---|---|---|---|
| v2 final (Phase E transfer, pre-G ordering) | `docs/transfer_anchor_phaseE.json` | `973f7a029c444ec7` | 23 |
| G3-only (directed pressure, no offer pool) | `docs/adaptive_g3only_phaseH.json` (committed this phase; reproduces the digest cited in ADVANCE_RESULT.md) | `93338b61e81fe6e1` | 23 |
| G combined (G2 offers + G3 pressure) | `docs/final_live_phaseG.json` | `47324408543b7365` | 22 |

**A "G2-only" configuration does not exist and cannot be cited.** G2 and
G3 shipped in one commit; the runtime has no toggle separating them, and
adding one would be a mechanism change outside Phase H's mandate. The
union below therefore rests on the three real configurations.

Reproduction commands:

```bash
python3 rsi_levels_metaforge_unified.py --mode run-adaptive --save g3only.json      # G3-only
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save combined.json # G combined
```

## Union

**Union count: 24 distinct designer tasks** solved across the three
configurations. 21 tasks (T00–T14, T16, T17, T19, T20, T24, T25) are
solved in all three. The three that differ:

| Task | Solved in | Adoption wave | Gate record / lineage |
|---|---|---|---|
| T15 alternating_sum | v2 final (w7); G combined (w1) | 7; 1 | exploration body `[INPUT,EVENIDX,RED_ADD]` gate-accepted (w6 `bundle_table` gained=['T15'] in v2 final; w0 `bundle_table` in G combined); program `M· INPUT ODDIDX RED_ADD SUB` |
| T27 sum_x16 | v2 final (w2); G3-only (w2) | 2; 2 | mined-macro ladder: w1 `SCREEN_INSTALL gained=['T27']` — the x¹⁶ stepping-stone macro mined from that run's own T11/T12 adoptions |
| T28 sum_x32 | G3-only (w3) only | 3 | w2 `SCREEN_INSTALL gained=['T28']`; macro mined from that run's own T27 adoption; program `M106 M106 ZMUL RED_ADD` |

No single configuration holds T15, T27, and T28 simultaneously:
the v2 final holds {T15, T27}, G3-only holds {T27, T28}, G combined
holds {T15} alone. The union {T15, T27, T28} + the 21 universal tasks =
24 — the v4 primary threshold is exactly the demand that one run realize
this union.
