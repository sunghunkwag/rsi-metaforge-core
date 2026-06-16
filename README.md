# RSI MetaForge Core

[![Quick CI](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/quick-ci.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/quick-ci.yml)
[![Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)

RSI MetaForge Core is an experimental Python research runtime for studying validation-gated adaptive search, program synthesis, and candidate modification within bounded benchmark environments. It is intended as a research artifact for investigating whether adaptive search procedures can yield measurable improvements over frozen baselines under explicitly defined evaluation gates.

## Overview

The runtime implements program synthesis with VM-style execution, candidate mutation, and validation-gated candidate selection. Adaptive search procedures are evaluated against frozen baselines across bounded benchmark environments with explicit evaluation rules. The full development history is preserved to support review and reconstruction of results.

Results should be interpreted as bounded adaptive improvement within the benchmark environments defined in this repository. Terminology, methods, and implementation details are experimental and subject to revision.

## Usage

The runtime is contained in a single file and exposes a `--mode` flag that selects the procedure to run. The default mode is `demo`.

```bash
# Run the demonstration procedure (default)
python rsi_levels_metaforge_unified.py --mode demo

# Run the test suite
python rsi_levels_metaforge_unified.py --mode test

# Run the adaptive search procedure
python rsi_levels_metaforge_unified.py --mode run-adaptive

# Run the frozen baseline for comparison
python rsi_levels_metaforge_unified.py --mode run-frozen
```

Additional modes are available via `python rsi_levels_metaforge_unified.py --help`.

## GitHub Actions validation

This repository separates lightweight hygiene checks from the longer evidence run:

- **Quick CI** runs on push, pull request, and manual dispatch. It compiles the runtime, checks the CLI surface, runs the dynamic-evaluator guard, and runs the general-domain smoke gate.
- **Full Evidence** runs automatically when the main runtime or evidence workflow changes on `main`, and can also be started manually. It runs the file-world battery, self-forge battery, horizon-scan certificate, and then the full test suite after the evidence artifacts are generated. The workflow uploads generated logs and JSON evidence artifacts.

## Repository status

This repository is maintained as a research artifact. Results, terminology, and implementation details should be read as experimental, bounded, and subject to revision.
