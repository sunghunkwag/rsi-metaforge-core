# Self-Curriculum Compounding Loop — Frozen Specification (SC-1)

Spec-freeze document. Every constant, seed, budget, threshold, and protocol
rule below is frozen at commit time, BEFORE the first `--mode sc-battery`
evidence run. Changing any value after the first battery run requires a new
predictions file; this one stays committed. The pre-registered predictions
are in `docs/PREDICTIONS_SC.md`; results are scored in `docs/SC_RESULT.md`.

## 1. Mission and claim boundary

A closed loop that generates its own tasks, proves each task feasible before
admitting it, solves tasks under sealed evaluation, and composes solved
tasks into harder ones — with **zero human-authored tasks added**. The
deliverable is the measured compounding curve (M1–M4 below), not an
open-ended autonomy claim. Transfer to the frozen human instrument (M3) is
the pre-registered external test. A flat or negative curve ships as-is.

## 2. Architecture (five components, strict separation)

| Component | Implementation | Sees |
| --- | --- | --- |
| C1 Poser | `SCPoser`, `_sc_units_track_*`, `_sc_enum_weighted` | frozen primitive units, gate-adopted archive bodies, aggregated per-band pass/fail statistics |
| C2 Harness | `sc_admit`, `sc_witness_validate`, `_sc_sample_inputs` | both sides (trusted; source hash-pinned) |
| C3 Solver | `sc_solve` | canonicalized public pairs, archive macro bodies, its budget — nothing else |
| C4 Gate | `_sc_gate_score`, `_sc_mdl_ok` | sealed held-out pairs (gate-private store) |
| C5 Ledger | `SCLedger` | append-only, SHA-256 hash-chained |

Poser and solver share exactly one channel: the adopted archive
(`{"aid", "tokens"}` entries only — no free-form metadata). The poser
additionally receives aggregated per-band `{attempted, solved}` counts,
never solver programs or traces. Witnesses and sealed pairs live in
write-once, memory-only stores (`SCSealedStore`) and never reach the
workspace before task retirement (the ledger carries hashes only).

The trusted evaluation side (`sc_transfer_eval`, `sc_control_library`,
`sc_battery`) drives the existing frozen-instrument machinery with adopted
bodies, exactly like the Phase D–I exploration-archive offers. It is not in
the self-curriculum namespace and its results never feed back into the loop.

## 3. Substrate

The stack VM base ISA only (`OP_IMPL`; granted EXT ops are invisible to SC
by construction — `_sc_run_tokens` dispatches through the base table).

- **Track A (inverse / round-trip).** Generators are affine chains over
  singleton-int inputs, composed from the frozen invertible step set
  `SC_STEPS_A` = {+1, +2, +3, ×2, ×3}. Each step's exact inverse exists in
  the ISA (`SUB k`; `DIVI k`, exact on the reachable set), so the witness
  pair (G, G_inv) exists **by construction** and G_inv is itself a program
  in the solver's search language. Solver task: from pairs ((y,), v), find
  any H with H(G(v)) == v on the sealed held-outs.
- **Track B (forward synthesis).** Generators are list pipelines over the
  frozen unit set `SC_UNITS_B` = {TAIL, REVL, SORTL, SCAN_MAX, SCAN_ADD,
  EVENIDX, ODDIDX, DUP+ZADD, DUP+ZMUL} applied to length-6 lists with
  values in [0, 8). The witness is G itself. Solver task: find any P
  behaviorally equal to G on the sealed held-outs.

Composition: the poser builds candidate generators from elementary units
plus gate-adopted archive programs whose expanded bodies parse back into
the unit grammar (`_sc_parse_a_unit` / `_sc_parse_b_seg`); Track A archive
units are only eligible when their forward form is injective by
construction (pure ADD/MUL chains or exact complements of SUB/DIVI chains).
The solver's vocabulary is the frozen `SC_SOLVER_VOCAB` (21 base ops — the
closure of the poser languages plus exact inverses) plus adopted archive
macros. This is the compounding mechanism under test: adopted solutions
compress search for deeper tasks.

## 4. Frozen constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `SC_MASTER_SEED` | 730117 | harness sampling seed root |
| `SC_GENERATIONS` | 10 | battery generations |
| `SC_CHECKPOINTS` | (0, 5, 10) | M3 transfer checkpoints (g = 0, every 5) |
| `SC_BAND_START` / `SC_BAND_MAX` | 2 / 12 | composition band ladder |
| `SC_POSE_PER_TRACK` | 4 | band candidates per track per generation |
| `SC_POSE_M4_PER_TRACK` | 2 | reference-band stream for M4 |
| `SC_M4_REF_BAND` | 2 | fixed band for the M4 cost curve |
| `SC_M_INPUTS` / `SC_M_PUBLIC` | 28 / 8 | instances per task; public split (20 sealed) |
| `SC_B_WITNESS` | 4096 | witness-validation execution budget (I6) |
| `SC_B_FROZEN_BASE` / `SC_B_FROZEN_MAX` | 1500 / 24000 | I5 frozen-baseline budget; doubles on too-easy, capped |
| `SC_B_LIVE` | 25000 | live solver candidate-evaluation budget |
| `SC_MDL_ALPHA_NUM/DEN` | 1/2 | MDL cap α = 0.5 (integer arithmetic) |
| `SC_MDL_ABS_TOKENS` | 24 | absolute surface-length cap (I7) |
| `SC_TASK_MAX_ATTEMPTS` | 2 | attempts before retirement |
| `SC_ARCHIVE_TOPK` | 256 | archive programs replayed at admission (I8); K exceeds any reachable archive size (≤ 10 generations × 12 candidates), so top-K = the whole archive in practice |
| `SC_TRANSFER_POOL_CAP` | 256 | bodies offered per transfer arm (effectively uncapped for both arms) |
| `SC_MIN_DISTINCT_OUTPUTS` | 3 | probe-battery diversity floor (I2) |
| window | [1/5, 4/5] | learnability window for the ratchet |
| `SC_STEP_LIMIT` | 200 | expanded program length cap |
| `SC_VMAX_A` | 60 | Track A input domain [0, 60) |
| `SC_LIST_LEN_B` / `SC_VALMAX_B` | 6 / 8 | Track B input shape |
| probe batteries | `SC_PROBES_A` (16) / `SC_PROBES_B` (12) | frozen literals in source |
| `SC_PIN_SHA256` | `8471a86b13c61e07e46eb948c1fbc458d2486e24c480224e191549cd3824145f` | gate+harness source pin (I10) |

The pin input is the concatenated source of every pinned component PLUS the
canonical dump of every constant in this table
(`_sc_frozen_constants_canon`, including seeds, probes, step/unit tables,
and the solver vocabulary) — so seed-shopping or threshold drift flips the
pin and aborts the battery, not merely a test. The battery additionally
asserts its configuration against LITERAL spec values.

MDL cap rule (I7): a candidate P is scored only if
`len(json(P_surface)) * 2 <= len(json(public_pairs))` (α = 1/2, canonical
compact serializations) AND `len(P_surface) <= 24` tokens. Serialization is
of the SURFACE form (macro tokens allowed), so deep solves require genuine
library compression, never pair memorization.

Task identity: `sha256(canon([track, expanded_G_tokens]))`. The per-task
input PRNG is `random.Random(int(cid[:16], 16) ^ SC_MASTER_SEED)` — the
poser cannot influence which inputs appear (I9; suggestions are discarded).

Band integrity: every task's difficulty band is MEASURED by the harness
from the generator itself (`_sc_measured_band`: Track A = parsed step
count, Track B = parsed unit count, with a token-length fallback for
non-grammar generators). The poser's claimed band is recorded in the
ledger as `band_claimed` for audit and is trusted nowhere — a fabricated
label cannot move the M2 ladder (red-team test
`test_sc_band_fabrication_ignored`).

Configuration validity is enforced at construction: an empty sealed split
(`m_public >= m_inputs`), an out-of-domain Track A sample size, or a
non-positive budget raises immediately. A Track B sampling shortfall is
its own rejection reason (`sampling_shortfall`), never mislabeled.

## 5. Task lifecycle and admission order

`generated` → checks, in this frozen order → `admitted` or
`rejected(reason)`:

1. `i6_witness` — witness must exist (Track A: G_inv present).
2. `i6_witness_exec` / `i6_witness_budget` — witness executes
   deterministically on the full probe battery within `SC_B_WITNESS`.
3. `i3_injective` — Track A: G injective on the probe battery (and on the
   sampled instance set).
4. `i6_roundtrip` — Track A: `G_inv(G(x)) == x` on the full probe battery.
5. `i1_identity` — fixed-point fraction > 50%, or output-multiset equality
   fraction > 50%, rejects.
6. `i2_diversity` — fewer than 3 distinct probe outputs rejects.
7. `i4_duplicate` — behavioral signature (sha256 of canonical probe
   outputs) already seen rejects.
8. `i5_frozen` — the frozen baseline solver (base vocabulary only, current
   I5 budget) solves the task through the same gate → rejects (below the
   ladder).
9. `i8_archive` — any of the top-K archive programs already passes the
   sealed set → rejects (non-novel).

Admitted tasks are attempted once per generation (budget `SC_B_LIVE`),
gate-scored on sealed pairs + MDL cap, and retire on solve or after 2
attempts (`retired` reveals the witness in the ledger — never earlier).
Whatever is still open when the run ends is retired then, so the lifecycle
terminates and no admitted task escapes the record. Each generation also
appends a `gen_summary` ledger record (band and I5 budget in effect during
the generation and after the ratchet, attempted/solved counts, archive
size, cumulative candidate evaluations) so the matched-compute budgets and
the ratchet trajectory are themselves covered by the hash chain. Every
`solved` record carries `used_macro` — whether the adopted solution's
surface uses an archive macro — so M1 decomposes into
solved-via-library-compression versus solved-by-base-search (the honest
split between compounding and the frozen-vs-live budget gap).

Ratchet (pre-registered): per generation, on the current band's solve rate
r = solved/attempted: r inside [0.2, 0.8] → band + 1; r > 0.8 → I5 budget
doubles (capped); r < 0.2 or no attempts → hold. Implemented in integer
arithmetic (`5*solved >= attempted`, `5*solved <= 4*attempted`).

## 6. Metrics (computed from the FULL ledger)

- **M1** cumulative distinct-solved per generation (headline curve).
- **M2** maximum admitted band per generation.
- **M3** transfer anchor at checkpoints {0, 5, 10}: designer-solved on the
  frozen human instrument via `run_system(adaptive=True,
  exploration_pool=<library>)` (the pre-I cursor-walk offer schedule),
  two arms at matched compute, each offering its WHOLE library in its own
  regime's canonical order (no curated subset on either side):
  - curriculum arm: all adopted SC bodies in adoption order;
  - control arm: all `explore_run(seed=EXPLORE_SEED, budget=E(g))` archive
    bodies in the archive's canonical order (sorted cell keys, exactly as
    `explore_serialize` emits it).
  Both are subject to the same generous `SC_TRANSFER_POOL_CAP` = 256.
  Matched compute: E(g) = cumulative candidate-program evaluations spent by
  the SC loop (live solver + I5 frozen solver) through generation g — the
  same native unit (candidate programs considered) both regimes report;
  E(g) values are read from the hash-chained `gen_summary` records.
  At g = 0 both libraries are empty; one shared evaluation is recorded for
  both arms.
- **M4** median solve cost (candidate evaluations) at fixed band 2, per
  generation; null when no reference-band solve occurred.

Battery digest (I12): `sha256(ledger_head + canon(metrics_json))[:16]`,
printed as `sc_digest`; metrics include the M3 arms, all budgets, and
`human_authored_tasks: 0`. CI runs the battery twice and asserts equal
digests. Artifacts: `reports/evidence/sc_ledger.jsonl`,
`reports/evidence/sc_battery_results.json`.

## 7. Scaled configurations (also frozen)

- `--mode self-curriculum` (demo, CI-safe): generations=3,
  pose_per_track=3, pose_m4_per_track=1, m_inputs=20, m_public=6,
  b_frozen_base=800 (max 6400), b_live=8000, no transfer checkpoints.
- Test configuration (`_sc_test_cfg`): generations=2, pose_per_track=2,
  pose_m4_per_track=1, m_inputs=16, m_public=5, b_frozen_base=400
  (max 3200), b_live=4000.

The battery mode asserts its configuration equals the frozen constants and
aborts otherwise (I14); it also verifies `SC_PIN_SHA256` against the live
source of every pinned component and aborts on mismatch (I10).

## 8. Isolation from the human instrument (I13)

The self-curriculum namespace (`_sc_scan_components()`) is test-enforced to
contain none of the sealed-instrument symbols (ORACLES, TRAIN_INPUTS,
holdout/counterfactual gate constructors, seed constants, adoption records,
…) — the same source-scan discipline used for the Phase D exploration
engine. All SC file I/O goes through `_sc_guarded_open`, which raises
`PermissionError` on any path containing `frozen_holdout` and confines
writes to `reports/evidence/`. Self-curriculum tasks live in their own
ledger namespace (`SCA-*`/`SCB-*`) and are never counted in any designer
solved statistic.

## 9. Known boundaries (disclosed at spec-freeze)

- **Solver/gate cap divergence (theoretical):** `sc_solve` bounds the
  SURFACE form; a candidate whose macro expansion exceeds `SC_STEP_LIMIT`
  would be found by the solver and then rejected by the gate's
  `_sc_expand` cap. This requires an archive body near 200 tokens; across
  the battery, demo, and test configurations the largest adopted body is
  ~13 tokens and zero gate-side expansion rejections occur. The gate-side
  cap is the binding enforcement; the divergence wastes solver budget only
  in configurations that cannot arise under this spec.
- **Sampler reconstructibility:** the per-task input draw is a public
  function of the task id and the committed master seed (necessarily so,
  for two-run reproducibility). A learned poser could in principle mine
  generators whose induced public split is favorable; the v1 poser is a
  fixed deterministic enumerator and has no such channel. Recorded as the
  first hardening target for any future learned poser.
- **M1 is not purely compounding:** part of the distinct-solved count
  reflects the frozen-vs-live budget gap (I5 admits tasks the frozen
  budget misses that base-vocabulary live search still reaches). The
  `used_macro` decomposition separates the two; the compounding claim
  rests on the macro-using solves and the M2 band climb, not the raw M1
  total.

## 10. Calibration disclosure

Before spec-freeze, budgets were calibrated for feasibility on prototype
runs (the loop must have a reachable entry rung: at `SC_B_FROZEN_BASE` the
frozen baseline fails band-2 tasks that the live budget solves; adopted
macros measurably unlock deeper bands). The calibration run of the loop
portion under exactly these constants was observed and is disclosed as
known-at-prediction-time in `docs/PREDICTIONS_SC.md`. After this freeze, no
constant changes; the battery (including the never-run M3 transfer arms)
runs as-is and its curves ship as measured.
