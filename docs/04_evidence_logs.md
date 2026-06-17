# Evidence Logs

Evidence in this repository should be read as a ladder. Higher rungs require stronger artifacts than lower rungs.

```mermaid
flowchart BT
    A[Speculative RSI claim] --> B[Code-level self-modification]
    B --> C[Patch accepted by gate]
    C --> D[Held-out improvement]
    D --> E[Transfer improvement]
    E --> F[Repeated lineage improvement]
```

## Current Evidence Level

From checked-in files alone, the repository shows code-level self-modification mechanisms, explicit validation gates, expected battery commands, and a historical public evidence summary in [EVIDENCE.md](../EVIDENCE.md).

Generated logs and result JSON files are not checked in. The current runtime should therefore be validated against the newest successful [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml) run for the commit under review, or by reproducing the commands locally.

The historical evidence described in [EVIDENCE.md](../EVIDENCE.md) supports bounded held-out improvement for an earlier runtime. It should not be treated as automatic proof that every later runtime revision has the same evidence level.

## Result JSON Files

No structured result JSON files are currently checked into the repository. [Full Evidence](../.github/workflows/full-evidence.yml) is configured to collect these generated files if the corresponding batteries create them:

| Generated file | Producer mode | Status |
| --- | --- | --- |
| `file_world_results.json` | `--mode file-battery` | Generated artifact, not checked in. |
| `forge_results.json` | `--mode forge-battery` | Generated artifact, not checked in. |
| `closure_scan.json` | `--mode horizon-scan` | Generated artifact, not checked in. |
| `cfs_results.json` | `--mode cfs-battery` | Generated artifact, not checked in. |
| `expansion_results.json` | `--mode expansion-battery` | Generated artifact, not checked in. |
| `grammar_results.json` | `--mode grammar-battery` | Generated artifact, not checked in. |
| `grammar2_results.json` | `--mode grammar2-battery` | Generated artifact, not checked in. |

Because these files are not present in the checkout, structured plotting requires cleaner generated result schemas or an artifact bundle from a completed evidence run. This patch intentionally does not add plots or fabricate data.

## Battery Outputs

Evidence-oriented runtime modes include:

- [`file_battery`](../rsi_levels_metaforge_unified%20%283%29.py#L9164): file-world hidden A/B evaluations.
- [`forge_battery`](../rsi_levels_metaforge_unified%20%283%29.py#L8050): self-forge primitive admission and downstream reuse.
- `horizon-scan`: closure certificate generation through the final CLI dispatch.
- [`cfs_battery`](../rsi_levels_metaforge_unified%20%283%29.py#L13077): continuous functional substrate tests and propagation checks.
- [`expansion_battery`](../rsi_levels_metaforge_unified%20%283%29.py#L13580): residue-driven extension tests.
- [`grammar_battery`](../rsi_levels_metaforge_unified%20%283%29.py#L13883): depth-1 grammar feature expansion.
- [`grammar2_battery`](../rsi_levels_metaforge_unified%20%283%29.py#L14219): depth-2 grammar feature expansion beyond depth 1.

## Pytest and Built-In Test Outputs

The repository uses a built-in test harness invoked through:

```bash
python "rsi_levels_metaforge_unified (3).py" --mode test
```

[Full Evidence](../.github/workflows/full-evidence.yml) records this output to `reports/evidence/full_test.log` and checks for:

```text
RESULT: 116 passed, 0 failed
ALL TESTS PASSED
```

That string is an expected workflow condition. Reviewers should confirm it in the actual Actions log or local run output for the commit under review.

## Demo Outputs

The runtime exposes demonstration and comparison commands:

```bash
python "rsi_levels_metaforge_unified (3).py" --mode demo
python "rsi_levels_metaforge_unified (3).py" --mode counterfactual
python "rsi_levels_metaforge_unified (3).py" --mode run-adaptive --save adaptive.json
python "rsi_levels_metaforge_unified (3).py" --mode run-frozen --save frozen.json
python "rsi_levels_metaforge_unified (3).py" --mode cf-report --adaptive-json adaptive.json --frozen-json frozen.json
```

Demo output is useful for orientation but is weaker than a clean evidence run with saved artifacts, logs, and commit identity.

## Accepted Modifications

Accepted modifications are reflected in:

- `RunState.adopted_tokens`, `adopted_wave`, and `adopted_searcher_version`.
- `META_ACCEPT` events and `gate_records`.
- [`lineage_report`](../rsi_levels_metaforge_unified%20%283%29.py#L1966).
- [`runstate_summary`](../rsi_levels_metaforge_unified%20%283%29.py#L2033).
- Battery-specific result JSON files when generated.

## Rejected Modifications

Rejected or blocked modifications are reflected in:

- `GATE_FAIL`, `CF_GATE_CATCH`, `META_REJECT`, `NO_PROPOSAL`, and `SKIP_DUPLICATE_PROPOSAL` events.
- `RunState.rejected_digests`.
- Battery-specific rollback, give-up, and clean-rejection tests.
- Full-suite tests that assert gates reject sabotage, train-only fits, undeclared oracle access, and unsupported targets.

## Failure Cases

Known failure or weakness categories include:

- Historical evidence for an older runtime does not automatically validate the current runtime.
- Local pass criteria can be narrower than broad generalization.
- Missing generated result artifacts make independent inspection harder until Actions artifacts or local runs are collected.
- Battery results depend on the declared task and gate design.
- A gate can be incomplete even if all current tests pass.

## Ambiguous Cases

Ambiguous evidence includes candidates that pass train checks but fail sealed gates, speculative candidates that roll back, grammar expansions that only work inside declared feature closure, and historical results whose exact runtime does not match the current file.

Reviewers should prefer artifacts with commit identity, workflow logs, generated JSON, and clear accepted/rejected lineage over narrative summaries alone.
