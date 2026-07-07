# Self-Curriculum (SC-1) Prediction Register

Committed and pushed BEFORE any `--mode sc-battery` evidence run exists.
Scored in `docs/SC_RESULT.md` after the runs, misses included. Every claim
below derives from committed evidence or disclosed calibration only;
observations already made at prediction time are marked
**[known-at-prediction-time]**.

## Protocol under prediction

One battery configuration (frozen in `docs/SELF_CURRICULUM_SPEC.md`:
SC_GENERATIONS=10, SC_B_LIVE=25000, SC_B_FROZEN_BASE=1500 doubling to
24000, SC_B_WITNESS=4096, α=1/2 + 24-token MDL cap, window [0.2, 0.8],
SC_MASTER_SEED=730117), executed twice with byte-identical `sc_digest`
required. M3 transfer arms at matched compute on the frozen human
instrument via the existing offer machinery
(`run_system(adaptive=True, exploration_pool=…)`, pool cap 24):

- **Curriculum arm:** SC archive bodies in adoption order.
- **Control arm:** `explore_run(seed=EXPLORE_SEED, budget=E(g))` elites,
  frozen elite order.

## Known-at-prediction-time observations

1. **[known-at-prediction-time]** The loop portion (no transfer) was
   executed during calibration under exactly the frozen constants:
   M1 curve 4, 5, 8, 10, 11, 12, 12, 12, 12, 14; the band ratcheted 2→3
   after g5; B_frozen tightened 1500→24000 over g0–g4; archive size 14;
   total loop evaluations E(10) = 462095 (E(5) = 115074). The battery must
   reproduce this loop portion exactly (it is the same seeded code path).
2. **[known-at-prediction-time]** M4 at the reference band ROSE during
   calibration (945 → 1134 → 1737 → 3037 → 4037 → 4199 → null): the I5
   tightening rule raises the admission floor inside the band, which
   selects progressively harder reference-band tasks. This confounds the
   directive's expectation that amortization drives M4 down; the confound
   is pre-registered here and the curve ships either way.
3. **[known-at-prediction-time]** Baseline transfer evaluation with an
   empty pool (`--mode run-adaptive`, the identical code path to the g=0
   checkpoint): designer solved 23, adoption digest `93338b61e81fe6e1`.
4. **[known-at-prediction-time]** The macro-compounding mechanism test:
   a +6 affine-chain task is unsolved bare at 25000 evaluations but solved
   via an adopted half-depth macro at a small fraction of the budget
   (test_sc_macro_compounding_reduces_cost).
5. **[known-at-prediction-time — superseded protocol]** One full battery
   execution (including transfer arms) ran during development under a
   SUPERSEDED control-arm rule (24 globally-shortest explore cells; an
   adversarial review then flagged that curation as unfair to the control
   arm and it was replaced by the whole-archive canonical order frozen in
   the spec). Its transfer numbers, disclosed for completeness: g0 23/23
   shared; g5 curriculum 23 (pool 11) vs control 22 (pool 24); g10
   curriculum 23 (pool 14) vs control 23 (pool 24). The committed
   protocol's control numbers are NOT known at prediction time; the loop
   portion of that run matched observation 1.

## Predictions

**P1 — Determinism.** Both battery runs produce byte-identical `sc_digest`
values (ledger head + canonical metrics). Any divergence is a determinism
bug and stops the phase (worse than a null).

**P2 — Loop reproduction.** The battery's loop portion reproduces the
calibration record in observation 1 exactly: final M1 = 14 distinct solved
tasks with human-authored task count 0, max admitted band 3, archive 14.
A miss here is a bug, not a finding (the loop is a pure function of the
frozen seeds).

**P3 — Compounding evidence.** At least one generation solves tasks at a
band the frozen baseline provably cannot enter (I5-passed admissions), and
at least one solve at band ≥ 3 lands only after the archive is non-empty
(the g9 band-3 solves in calibration). At least one solved record carries
`used_macro = true` — the M1 decomposition separates library-compression
solves from budget-gap solves, and the compounding claim rests on the
former. The M1 curve is monotone nondecreasing with a visible stall
(g6–g8) — the stall ships as part of the honest record.

**P4 — M4 direction (against the naive expectation).** M4 at band 2 rises
or goes null in later generations, per observation 2. If it falls instead,
that is a miss of this prediction and is reported as such.

**P5 — Transfer anchor (the real judge; the committed protocol's control
arm has never been run).** Expected direction: curriculum ≥ control on
designer-solved at each checkpoint. Pre-registered pass threshold:
curriculum arm STRICTLY exceeds the control arm at the final checkpoint
(g10). Prediction: the threshold is NOT met — both arms land within ±1
task of the empty-pool baseline (23), because the SC library (affine-chain
inverses and short list pipelines) is unlikely to contain the missing
vocabulary for the open walls (T18/T21/T22 class). The curriculum arm's
own numbers under the superseded-protocol run (observation 5) were 23 at
every checkpoint and are expected to repeat (the curriculum pool is
protocol-invariant); the control arm under the whole-archive rule is the
genuinely open quantity. If the curriculum arm exceeds the control arm,
that is a positive surprise reported with full lineage; if it falls below,
that negative result is the headline.

**P6 — g0 checkpoint anchor.** The shared empty-pool evaluation at g = 0
reports designer solved 23 with adoption digest `93338b61e81fe6e1`
(observation 3), twice byte-identically.

**P7 — No incumbent regression.** The full built-in suite passes at
exactly 178 (156 incumbent + 22 SC) with zero failures under the
batteries-first CI order; the Phase J record (28/33, its artifacts and
pins) is untouched.

**P8 — Ledger integrity.** Every generated candidate appears in the
ledger with an admitted/rejected disposition; denominators in the metrics
equal the ledger counts; the two-run chain heads are identical; no
witness appears in any ledger record before its task's retirement.

## Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode sc-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode sc-battery   # run 2
# byte-identical sc_digest required; artifacts under reports/evidence/
python3 rsi_levels_metaforge_unified.py --mode test         # 178 passed
```
