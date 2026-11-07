# Exact rejection pilot: development protocol frozen before execution

**Status:** developmental smoke experiment, not a registered external evaluation
and not a claim of transfer or RSI improvement.

## Conditions

- Base: main commit `c4f0a8627a1c9f37dd3aa6291b0eee0c78648210`
- Branch: `research/exact-rejection-20261108`, opt-in exact skip only
- Fixed arm: `RSI3_UNIFORM_FM` (no adaptive controller, failure memory enabled)
- Mode A: `binding_skip_mode="signature"` (historical default)
- Mode B: `binding_skip_mode="exact"` (receipt-anchored AST digest)
- Seeds: 11, 22
- Generation count: 2
- Tasks: all 36 TRAIN tasks, sorted by task name; do not load VALIDATION/TEST
- Per-generation budget: B_wake=16 per TRAIN task, B_eval=16, dreams=4
- Search: max_size=12, max_expansions=20000, step_budget=2000
- Controller: chunk=8, exploration=0.3, analog_neighbors=2
- Serial execution, OPENBLAS_NUM_THREADS=1, OMP_NUM_THREADS=1

No intermediate results, hidden task inputs, or prior pilot runs are inspected
for hyperparameter selection. This is too small to establish equivalence or
superiority. The experiment should report every generation's TRAIN count,
negative receipts, total verifier queries, exact/signature skips, logical
evaluations, and CPU time for both modes.

## Before-run predictions

P1: For each mode the verifier query cap holds; no more than one query per
task per generation.

P2: If neither arm triggers its pre-verification skip, both modes have equal
TRAIN solution counts and exact matching candidate evaluation trajectories.

P3: The opt-in exact filter will never skip a different AST digest solely due
to probe-signature equality; the signature control can (mocked collision test).

**Interpretation:** A null difference in this smoke run is not evidence against
the structural false-suppression flaw. Any observed score difference is
development data; independent, budget-matched evaluation remains required.
