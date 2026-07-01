# Phase 0 Baseline Frontier — Designer Sealed Suite (Top Synthesis Core)

Baseline SOLVED/OPEN record for the 33 designer tasks (`T00`–`T32`,
`ORACLES` at lines 447–490 of `rsi_levels_metaforge_unified.py`), at the
documented default seeds and budgets. This is the Phase 0 reference point
for every later designer-suite transition claim.

## Exact reproduction commands

```bash
# adaptive arm (the improving system)
python3 rsi_levels_metaforge_unified.py --mode run-adaptive --save adaptive_baseline.json
# frozen arm (incumbent searcher, no self-improvement)
python3 rsi_levels_metaforge_unified.py --mode run-frozen --save frozen_baseline.json
```

Run from a clean working directory (no pre-existing `adaptive.json` /
`frozen.json`; see `docs/ENTRYPOINT_MAP.md` reproducibility caveats —
these two modes read no caches, but `demo`/`counterfactual` do).

## Default seeds and budgets (module constants, lines 76–106)

| Constant | Value | Role |
|---|---|---|
| `SEED` | 2026 | master search seed (per-task seed derived at run_wave line 1757) |
| `DATA_SEED` | 11 | public train inputs |
| `GATE_SEED` | 2027 | sealed holdout gate stream |
| `CF_GATE_SEED` | 4099 | sealed counterfactual gate stream |
| `TRAIN_LENGTHS` | (1, 2, 3, 4, 6) | public train input lengths |
| `HOLDOUT_LENGTHS` | (5, 8, 13, 21, 34) | holdout gate input lengths (unseen, longer) |
| `CF_LENGTHS` | (6, 9, 14, 22, 30) | counterfactual gate input lengths |
| `PER_LENGTH` | 4 | train vectors per length |
| `GATE_TRIALS` / `CF_TRIALS` | 8 / 6 | gate trials per length |
| `CF_VALMAX` | 15 | counterfactual gate value range |
| `WAVES` | 8 | waves per run |
| `RESTARTS_PER_TASK` | 6 | synthesis restarts per task per wave |
| `ITERS_PER_RESTART` | 550 | candidate evaluations per restart |
| `METAGATE_MAX_TASKS` | 12 | meta-gate A/B task cap |
| `MINT_PER_WAVE` / `MAX_GEN_TASKS` | 2 / 14 | self-generated task budget |
| `MAX_PROGRAM_LEN` / `MAX_STACK` / `MAX_MACROS` | 14 / 32 / 24 | top-VM capacity (lines 94–101) |

## Result summary

| Arm | Designer SOLVED | Designer OPEN | Generated adopted | Printed output |
|---|---|---|---|---|
| adaptive | 23 / 33 | 10 | 12 (`G00`–`G11`) | `{"solved": 35, "digest": "39d26f1080d4a89b"}` |
| frozen | 19 / 33 | 14 | 4 (`G02`,`G03`,`G08`,`G09`) | `{"solved": 23, "digest": "e5dc308324bb10f6"}` |

The printed `solved` count includes self-generated (`G##`) adoptions;
designer-suite numbers above count `T##` tasks only. Adaptive-arm meta-gate
record: 6 accepted of 8 proposals; final searcher version 6 with 7 macros.
Total candidate evaluations: adaptive 7,683; frozen 8,351.

Determinism (GR3): two consecutive runs of each command produced
byte-identical saved runstate JSONs (including adoption logs, events, and
digests) — adaptive digest `39d26f1080d4a89b`, frozen digest
`e5dc308324bb10f6` in both runs.

## Per-task baseline frontier

Wave = adoption wave in the adaptive arm. The four `search`-family tasks
are the documented expected-OPEN tier (no comparison/search primitives in
the ISA; ORACLES comment at lines 484–485).

| Task | Name | Family | Frozen arm | Adaptive arm | Adoption wave (adaptive) |
|---|---|---|---|---|---|
| T00 | sum | reduce | SOLVED | SOLVED | 0 |
| T01 | count | reduce | SOLVED | SOLVED | 0 |
| T02 | max | reduce | SOLVED | SOLVED | 0 |
| T03 | 2*sum | scale | SOLVED | SOLVED | 0 |
| T04 | parity | conditional | SOLVED | SOLVED | 0 |
| T05 | sum_sq | power | SOLVED | SOLVED | 0 |
| T06 | sum+count | compose | SOLVED | SOLVED | 0 |
| T07 | sum*count | compose | SOLVED | SOLVED | 0 |
| T08 | max_sq | power | SOLVED | SOLVED | 0 |
| T09 | count*count | power | SOLVED | SOLVED | 0 |
| T10 | sum_x4 | power | SOLVED | SOLVED | 0 |
| T11 | sumx4_sq | power | OPEN | SOLVED | 1 |
| T12 | sum_x8 | power | OPEN | SOLVED | 1 |
| T13 | middle | index | SOLVED | SOLVED | 0 |
| T14 | sum*max | compose | SOLVED | SOLVED | 0 |
| T15 | alternating_sum | position | OPEN | OPEN | — |
| T16 | prefix_max_sum | scan | SOLVED | SOLVED | 0 |
| T17 | second_largest | order | SOLVED | SOLVED | 0 |
| T18 | length_conditioned_sum | conditional | OPEN | OPEN | — |
| T19 | pairwise_product_sum | pairwise | SOLVED | SOLVED | 0 |
| T20 | first_quartile | index | SOLVED | SOLVED | 0 |
| T21 | last_quartile | index | OPEN | OPEN | — |
| T22 | sum*second_largest | compose | OPEN | OPEN | — |
| T23 | sum*range | compose | OPEN | OPEN | — |
| T24 | parity_conditioned_sum | position | SOLVED | SOLVED | 0 |
| T25 | rolling_pair_sum | pairwise | SOLVED | SOLVED | 0 |
| T26 | adjacent_difference_energy | pairwise | OPEN | OPEN | — |
| T27 | sum_x16 | power | OPEN | SOLVED | 2 |
| T28 | sum_x32 | power | OPEN | SOLVED | 5 |
| T29 | count_above_threshold | search | OPEN | OPEN | — |
| T30 | argmax_index | search | OPEN | OPEN | — |
| T31 | first_greater_than_previous | search | OPEN | OPEN | — |
| T32 | longest_increasing_run | search | OPEN | OPEN | — |

Baseline OPEN set (adaptive arm, 10 tasks): T15, T18, T21, T22, T23, T26,
T29, T30, T31, T32.

Tasks OPEN in the frozen arm but SOLVED in the adaptive arm at baseline
(existing self-improvement delta, for reference): T11, T12, T27, T28.

## Frozen evaluation instrument

`docs/frozen_holdout_phase0.json` — materialized dual-gate evaluation data
(holdout + counterfactual streams) for all 33 designer tasks, built by
`docs/make_frozen_holdout_phase0.py` from the pre-existing task
definitions only.

- SHA-256: `527bb04dd45c010a32637a92eeba5a799024a9a68e944e5c91186d3daa3f4d24`
- Size: 711,147 bytes; 40 holdout pairs + 30 counterfactual pairs per task.
- Freeze check: `test_frozen_holdout_phase0_instrument_intact` (native
  suite) re-hashes the file and re-derives every pair from the sealed-gate
  RNG convention.
- Read-only for the remainder of the project; sole evidence base for
  claim type 1 (designer-suite transitions).
