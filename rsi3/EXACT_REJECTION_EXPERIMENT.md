# Receipt-anchored exact rejection: isolated RSI-3 research

## Problem

The baseline `rsi3/integrator.py` suppresses a candidate if its behavior on
a finite collection of public-input-derived probes matches a previously
rejected candidate. Equal outputs on finitely many probes do **not** imply
equivalence on future inputs. A candidate that would satisfy the frozen
hidden verifier can therefore be skipped before receiving its one permitted
verification query for that task and generation.

## Change (opt-in, not a result)

Set `binding_skip_mode: exact` in an experiment's *copied* runtime config.
The integrator then suppresses a candidate only if its AST digest equals
one certified by an authentic, negative verifier receipt for the same task.
Signatures continue to be recorded for observational analysis and
provenance, but never authorize an exact-mode skip. With no flag, the
historical signature filter is unchanged. No benchmark corpus, budget,
frozen verifier, or registered RSI-4 run is modified.

The change trades reduced false-equivalence risk for possibly more verifier
queries spent on behaviorally similar but structurally different programs.
The digest denotes an AST, not a semantic proof of equivalence. An experiment
must ensure referenced library definitions retain their meanings across
generations; changing definitions requires a stronger program-plus-library
identity key or invalidating old rejection records.

## Test

```bash
python -m unittest rsi3.tests.test_exact_rejection
python -m unittest rsi3.tests.test_components rsi3.tests.test_verifier_memory
```

The collision test deliberately forces two distinct ASTs to have an identical
probe signature, then verifies only the receipt-rejected AST is suppressed
in exact mode. This is a *regression test of the gate*, not a demonstrated
RSI-3 TRAIN/VALIDATION gain.

## Falsifiable experiment

Use the existing preregistered evaluation partition without inspecting hidden
examples. Freeze the implementation and declare seeds and hypotheses **before**
external evaluation. Compare signature mode, exact mode, and no rejection
suppression under identical seeds, TRAIN exposure, candidate evaluations,
verifier query caps, and CPU budgets. Separately report attempted verifies,
behavioral collisions, solved TRAIN tasks, generalization, runtime, and
memory. Unchanged TRAIN 8/36 is a baseline observed in earlier failure-memory
studies, not a promised result for this experimental branch.

Do not merge into any registered RSI-4 phase during its active experiment.
