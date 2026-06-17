# Limitations

This repository should be read as a bounded experimental verifier and MetaForge harness. The strongest claim should be limited to what the code, logs, and reproducible runs actually demonstrate.

## Claim Boundaries

- This is not proof of general intelligence.
- This is not proof of unbounded capability.
- This is not proof of open-ended intelligence explosion.
- This is not a generic LLM-agent wrapper claim.
- Passing local tests does not automatically imply broad generalization.
- Passing a gate means passing the gate as implemented, not proving that the gate is complete.

## Validation Risks

Validation gates can be incomplete. A candidate can pass a local benchmark while failing a stronger held-out task, a transfer test, a replication run, or a reviewer-designed adversarial case.

Benchmarks can be gamed if anti-cheat controls are weak. The repository includes tests for oracle isolation, hidden expectation handling, rollback, and dynamic-evaluator blocking, but those tests should be inspected and challenged rather than treated as final proof.

Logs must be reproducible. For current public validation, the most useful artifacts are GitHub Actions runs tied to a commit, generated result JSON, uploaded logs, and local reproduction commands that a reviewer can rerun.

## Evidence Risks

The repository contains a historical evidence summary in [EVIDENCE.md](../EVIDENCE.md), but historical success for an earlier runtime is not automatic validation for later runtime changes. The current runtime should be judged by the newest successful [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml) run for the commit being reviewed.

Generated result JSON files are not checked in. This keeps the repository compact, but it means reviewers need the Actions artifact bundle or a local reproduction run to inspect detailed result records.

## Future Work

Stronger evidence would require:

- More held-out tasks designed independently of the implementation.
- Transfer tests across task families and data distributions.
- Repeated independent runs with saved seeds, logs, and result artifacts.
- External replication by reviewers who did not author the runtime.
- Clearer frozen, fixed-capacity, and ablation baselines.
- Cleaner result schemas for automated plotting and comparison.
- More explicit separation between code-level self-modification, benchmark improvement, and broader RSI claims.

Until those are in place, the repository should be described as experimental evidence for bounded, validation-gated self-modification behavior inside declared test environments.
