# RSI MetaForge Core

Experimental Python research runtime for studying validation-gated adaptive search, program synthesis, and candidate modification under bounded benchmark environments.

This repository is not an AGI system, not an ASI system, and not a deployed autonomous agent. It is a research artifact for examining whether adaptive search procedures can produce measurable improvements over frozen baselines under explicitly defined evaluation gates.

## Scope

- Single-file experimental research runtime
- Program synthesis, VM-style execution, mutation, and validation-gated candidate selection
- Adaptive search procedures compared against frozen baselines
- Bounded benchmark environments with explicit evaluation rules
- Development history preserved for review and reconstruction

## Non-scope

- Not a claim of general intelligence
- Not an open-ended autonomous self-improving system
- Not a deployed agent
- Not a production framework
- Not safety-certified
- Not intended for real-world autonomous operation

## Usage

For local research inspection:

```bash
python rsi_levels_metaforge_unified.py --mode test
python rsi_levels_metaforge_unified.py --mode demo
python rsi_levels_metaforge_unified.py --mode organic
Interpretation

Passing tests or outperforming frozen baselines should be interpreted as bounded adaptive improvement within this repository's defined benchmark environments.

It should not be interpreted as evidence of open-ended general recursive self-improvement, autonomous AGI, ASI, or deployment readiness.

Repository status

This repository is maintained as a research artifact. Results, terminology, and implementation details should be read as experimental, bounded, and subject to revision.
