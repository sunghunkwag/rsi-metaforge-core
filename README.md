# RSI MetaForge Core

[![Quick CI](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/quick-ci.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/quick-ci.yml)
[![Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sunghunkwag/rsi-metaforge-core)

RSI MetaForge Core is an experimental Python research runtime for studying validation-gated adaptive search, program synthesis, candidate modification, self-forge admission, continuous substrate probes, and grammar-mediated feature expansion inside bounded benchmark environments.

For the current public validation record and claim boundary, see [EVIDENCE.md](EVIDENCE.md).

## Codebase Map and DeepWiki

This repository can be explored through DeepWiki:

https://deepwiki.com/sunghunkwag/rsi-metaforge-core

Suggested DeepWiki questions:

- Where is the recursive self-improvement loop implemented?
- Where are candidate modifications generated and evaluated?
- Where are validation gates and anti-cheat controls implemented?
- Which logs support accepted self-modifications?
- Which results are inconclusive or failure cases?
- What are the current limitations and failure modes?
- How can the reported behavior be reproduced?
- How is the frozen Phase 0 holdout instrument constructed and pinned?
- How do the exploration archive, MDL anchor, and stratified offer schedule interact?
- Which designer tasks remain open, and what attribution do they carry?

Reviewer-oriented documentation:

- [Overview](docs/00_overview.md)
- [Architecture](docs/01_architecture.md)
- [Recursive Self-Improvement Loop](docs/02_rsi_loop.md)
- [Validation Gates and Anti-Cheat Controls](docs/03_validation_gates.md)
- [Evidence Logs](docs/04_evidence_logs.md)
- [Limitations](docs/05_limitations.md)

## Overview

The runtime implements VM-style program synthesis, candidate mutation, validation-gated selection, sealed hidden evaluations, rollback-sensitive admission, file-world artifact tasks, continuous functional substrate checks, and grammar expansion probes. Adaptive procedures are compared against frozen or fixed-capacity baselines under explicit gates.

Results should be interpreted as bounded adaptive improvement within the benchmark environments defined in this repository. This repository is not a general-intelligence claim, not proof of unrestricted recursive self-improvement, and not a drop-in production code-evolution system.

## Generalization Research Program (Phases 0–I)

Between 2026-07-01 and 2026-07-02 the repository ran a staged research program that generalized the runtime's gated self-improvement rules to the top-level searcher and measured the result against a frozen instrument. Every phase froze its measurement instruments before running, registered predictions before final evaluations, required two byte-identical runs for every reported artifact, and recorded null results as findings.

- **Phase 0** froze the evaluation instrument: [docs/frozen_holdout_phase0.json](docs/frozen_holdout_phase0.json), hash-pinned by test, plus the baseline frontier ([docs/BASELINE_FRONTIER.md](docs/BASELINE_FRONTIER.md)).
- **Phases A–C** generalized capacity growth, pressure/score separation, and speculative-ledger adoption to the top searcher ([docs/PHASEA_REPORT.md](docs/PHASEA_REPORT.md), [docs/PHASEB_REPORT.md](docs/PHASEB_REPORT.md), [docs/PHASEC_REPORT.md](docs/PHASEC_REPORT.md)).
- **Phases D–E** built a sealed exploration engine and external anchoring (transfer, MDL, property checks); final two-arm evaluation in [docs/EXPANSION_RESULT.md](docs/EXPANSION_RESULT.md).
- **Phases F–G** attributed the remaining open tasks ([docs/ATTRIBUTION_F.md](docs/ATTRIBUTION_F.md)) and tested interventions against that attribution; the outcome was a recorded null ([docs/ADVANCE_RESULT.md](docs/ADVANCE_RESULT.md)).
- **Phases H–I** traced why earlier offer orderings displaced useful intermediate vocabulary ([docs/DISPLACEMENT_TRACE.md](docs/DISPLACEMENT_TRACE.md)), froze a stratified offer schedule ([docs/ORDERING_SPEC.md](docs/ORDERING_SPEC.md)), registered predictions ([docs/PREDICTIONS.md](docs/PREDICTIONS.md)), and ran the final evaluation ([docs/SEQUENCING_RESULT.md](docs/SEQUENCING_RESULT.md)).

Final measured state: the live configuration solves 26 of 33 designer tasks on the frozen Phase 0 instrument (frozen baseline: 19 of 33), with both arms reproduced twice byte-identically; the final live artifact is committed at [docs/final_live_phaseI.json](docs/final_live_phaseI.json). Tasks T18, T21, and T22 remain open with a search/vocabulary attribution, and T29–T32 carry closure certificates under the current instruction set. Per-phase acceptance outputs are in `docs/PHASE*_REPORT.md`.

## Runtime File

The current runtime file is:

```text
rsi_levels_metaforge_unified.py
```


## Usage

The runtime exposes a `--mode` flag. The default mode is `demo`.

```bash
# Run the demonstration procedure
python "rsi_levels_metaforge_unified.py" --mode demo

# Run the full built-in test suite
python "rsi_levels_metaforge_unified.py" --mode test

# Run the adaptive search procedure
python "rsi_levels_metaforge_unified.py" --mode run-adaptive

# Run the frozen baseline for comparison
python "rsi_levels_metaforge_unified.py" --mode run-frozen

# Run the final live configuration from the research program
# (stratified offer schedule + exploration archive + external anchoring)
python "rsi_levels_metaforge_unified.py" --mode transfer-anchor
```

Evidence-oriented modes include:

```bash
python "rsi_levels_metaforge_unified.py" --mode file-battery
python "rsi_levels_metaforge_unified.py" --mode forge-battery
python "rsi_levels_metaforge_unified.py" --mode horizon-scan
python "rsi_levels_metaforge_unified.py" --mode cfs-battery
python "rsi_levels_metaforge_unified.py" --mode expansion-battery
python "rsi_levels_metaforge_unified.py" --mode grammar-battery
python "rsi_levels_metaforge_unified.py" --mode grammar2-battery
```

Additional modes are available via:

```bash
python "rsi_levels_metaforge_unified.py" --help
```

## Evidence Batteries

The current evidence workflow covers these bounded checks:

- file-world hidden A/B task evaluations
- self-forge primitive admission and downstream reuse checks
- horizon-scan closure certificates
- continuous functional substrate search and sealed-gate rejection checks
- dynamic feature expansion over measured residue walls
- depth-1 grammar feature expansion
- grammar2 depth-2 feature expansion beyond the depth-1 grammar
- full built-in regression suite (currently 147 tests) after evidence artifacts are generated

These batteries are designed to test verifier discipline: hidden answers should not leak, train-only fits should not be counted as solved, speculative changes should roll back when sealed gates fail, and gates should not be weakened to manufacture progress.

## GitHub Actions Validation

This repository separates lightweight hygiene checks from the longer evidence run:

- **Quick CI** runs on push, pull request, and manual dispatch. It compiles the runtime, checks the CLI surface, runs the dynamic-evaluator guard, and runs the general-domain smoke gate.
- **Full Evidence** runs automatically when the runtime or evidence workflow changes on `main`, and can also be started manually. It runs the evidence batteries listed above, then runs the full test suite and uploads generated logs and JSON evidence artifacts. The workflow asserts the exact expected suite result (`RESULT: 147 passed, 0 failed`); adding or removing tests requires updating that pin in the same change, otherwise the badge turns red.

The evidence summary links to passing Actions runs when available and keeps the claim boundary explicit: bounded verifier/fitness-harness evidence, not an unrestricted self-improvement claim.

## Repository Status

This repository is maintained as a research artifact. Results, terminology, and implementation details should be read as experimental, bounded, and subject to revision.
