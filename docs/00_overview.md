# Overview

This repository is an experimental Recursive Self-Improvement / MetaForge research codebase. It explores whether a bounded runtime can propose, test, reject, and accept its own modifications under validation gates.

The central question is not whether the system has general intelligence. The central question is whether any self-modification is actually validated instead of merely appearing impressive.

The repository should be inspected as a set of connected artifacts:

- Runtime code: [rsi_levels_metaforge_unified.py](../rsi_levels_metaforge_unified.py)
- Claim boundary and historical evidence notes: [EVIDENCE.md](../EVIDENCE.md)
- Public CI checks: [Quick CI](../.github/workflows/quick-ci.yml) and [Full Evidence](../.github/workflows/full-evidence.yml)
- Reviewer guide: this `docs/` directory

The runtime includes candidate synthesis, candidate mutation, gated acceptance, rollback-sensitive admission, lineage tracking, battery modes, and a built-in regression suite. These are evidence for bounded verifier behavior inside the repository's test environments. They are not proof of unrestricted RSI, unbounded capability, or open-ended intelligence explosion.

## Reviewer Questions

- Where is the recursive self-improvement loop implemented?
- Where are candidate modifications generated?
- Where are validation gates implemented?
- Which modifications were accepted or rejected?
- Which logs support the claim of actual improvement?
- Which results are weak, inconclusive, or failure cases?
- How can the behavior be reproduced?

## First Files to Read

Start with [EVIDENCE.md](../EVIDENCE.md) for the claim boundary and reproduction commands. Then inspect [01_architecture.md](01_architecture.md), [02_rsi_loop.md](02_rsi_loop.md), [03_validation_gates.md](03_validation_gates.md), and [04_evidence_logs.md](04_evidence_logs.md) alongside the runtime source.

For current public validation, prefer the newest successful [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml) run for the commit under review. The checked-in documentation names the expected commands and artifacts, but generated logs and JSON results are produced by runs rather than stored in this repository.
