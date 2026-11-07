# Exact vs signature rejection: first matched TRAIN-only smoke

**Execution:** [GitHub Actions run #42422251625](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42422251625)  
**Code SHA:** `acbbe30800855253f229511250333bb44e48d362`  
**Pre-registered before execution:** [PREDICTIONS_EXACT_REJECTION_PILOT.md](PREDICTIONS_EXACT_REJECTION_PILOT.md)  
**Raw JSON:** [exact_rejection_pilot_results.json](exact_rejection_pilot_results.json)

## Observed results

| Seed | Mode | G1 TRAIN | G2 TRAIN | G2 logical evaluations | Verifier queries | Rejected receipts | Suppressed candidates |
|---|---|---:|---:|---:|---:|---:|---:|
| 11 | signature | 5/36 | 6/36 | 1108 | 6 | 0 | 0 |
| 11 | exact | 5/36 | 6/36 | 1108 | 6 | 0 | 0 |
| 22 | signature | 5/36 | 6/36 | 1104 | 6 | 0 | 0 |
| 22 | exact | 5/36 | 6/36 | 1104 | 6 | 0 | 0 |

The pilot uses two generations, seeds 11/22, B_wake=16 per task,
B_eval=16, dreams=4, with all 36 TRAIN tasks. No external VALIDATION,
TEST, or RSI-4 judge partitions were loaded by this driver.

The targeted unit-and-regression suite completed: **25 tests OK** on Python
3.11. The CI job and developmental pilot completed successfully. The JSON
was also uploaded as a GitHub Actions artifact.

## Interpretation

**Null result for this restricted pilot.** Both arms followed identical
candidate trajectories and TRAIN counts. No frozen verifier issued a negative
receipt, so neither suppression mechanism activated. This experiment does
**not** test whether real collisions occur in the search grammar, whether the
exact mode helps generalization, or whether any recursive self-improvement
occurred. CPU seconds differed slightly, but those differences are not
meaningful evidence from two unpaired sequential wall environments.

The synthetic collision unit test passes: distinct AST digests are kept
separate even when the probe signatures have been forcibly made identical.
This establishes a gate-level property, not improved problem solving.

## Next falsifiable experiment

Create *grammar-reachable*, public-matching program pairs that produce equal
probe signatures but opposite outcomes under an independent hidden verifier.
Without leaking held-out partitions, compare signature, exact, and
no-suppression controls with equal candidate/CPU budgets and record the
actual false-suppression frequency. Only then run a frozen multi-seed study
with transfer and forgetting metrics. Keep the registered RSI-4 phases sealed.
