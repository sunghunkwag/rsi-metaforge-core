# rsi-metaforge-core

**rsi-metaforge-core** is a standalone Python runtime implementing a budget-constrained stochastic search system for program synthesis, stacked VM bytecode generation, and measured recursive self-improvement (RSI) gates.

## Core Architecture

This core is rebuilt with a focus on real measured self-improvement rather than hardcoded oracles:
- **Typed Stack VM**: Values are integers or list of integers. Out-of-bounds, type errors, and overflows trigger explicit `VMCrash` exceptions.
- **Budgeted Stochastic Search**: Synthesizes programs from training input/output pairs using mutation, macro extraction, and evolutionary search.
- **Meta-Gate Validation**: Candidate macro improvements must pass A/B testing against the incumbent searcher on a fresh frontier using equal resources.
- **Multi-Mechanism General-Domain Layers**:
  - **S1 PRM**: StepScorer with PRM beam search.
  - **S2 Debate**: Committee debate under a scarce label budget.
  - **S3 World Model**: Learn op-semantics models from real VM observations.
  - **S4 Meta-Learning**: Oracle-free configuration selection and curriculum drift audit.

## Verification & Tests

The core contains an extensive verification suite comprising 99 tests:
- **VM Safety**: Tests crash behaviors, stack sizes, and integer capping.
- **Deterministic Playback**: Ensures that fixed seeds produce identical macro adoptions and search trajectories.
- **Counterfactual Gain**: Validates that the adaptive searcher strictly outperforms the frozen baseline.
- **HDC Space & Kuramoto Decoders**: Verifies phase-locking synchronization and analogy transfer in high-dimensional vector representations.

### How to Run

To run the adaptive demo:
```bash
python rsi_levels_metaforge_unified.py --mode demo
```

To run the unit verification suite:
```bash
python rsi_levels_metaforge_unified.py --mode test
```

To run the integration smoke tests:
```bash
python rsi_levels_metaforge_unified.py --mode organic
```
