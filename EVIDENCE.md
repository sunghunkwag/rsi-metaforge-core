# Evidence

This repository should be read as a bounded research artifact for validation-gated adaptive search and self-forge style candidate admission. It is not an AGI claim, not a drop-in Hermes Phase 4 implementation, and not proof that unrestricted recursive self-improvement has been solved.

The useful claim is narrower: the runtime exposes a verifier/fitness harness that can compare adaptive behavior against frozen baselines under explicit gates, hidden evaluations, rollback-sensitive admission, and full-suite regression checks.

## Runtime Evidence Anchor

The currently cited runtime evidence anchor is the GitHub Actions run below. Later documentation-only commits may point back to this run unless the runtime changes and a newer Full Evidence run supersedes it.

- Workflow: [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)
- Run: [27588469107](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/27588469107)
- Commit: `87d6f08d77eda690cd5a10d38f057ca2d0ffd8d3`
- Result: `success`
- Date: `2026-06-16`

That run completed these stages:

- Python compile check
- File-world evidence battery
- Self-forge evidence battery
- Horizon-scan certificate
- Full test suite after generated evidence artifacts
- Evidence artifact upload

The same commit also passed the lightweight [Quick CI](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/27588469100) workflow.

## File-World Evidence Battery

The file-world battery runs sealed hidden A/B evaluations on unseen eval seeds. The hidden expectations are not written into the workspace.

| Task family | Frozen score | Adaptive score |
| --- | ---: | ---: |
| `csv_normalize` | `0.000` | `1.000` |
| `log_aggregate` | `0.111` | `1.000` |
| `config_migrate` | `0.000` | `1.000` |
| `repo_repair` | `0.704` | `1.000` |
| Mean | `0.204` | `1.000` |

This is evidence for adaptive improvement inside the repository's bounded file-task harness, not for open-ended autonomy.

## Self-Forge Evidence Battery

The self-forge battery checks whether system-synthesized primitives can be admitted through sealed gates and then reused downstream.

The public Actions run reported:

- `forged=4/4`
- `gate-adopted=2/4`
- downstream general-domain bridge completed
- forged-operator downstream task solved only with the admitted forged operations

The gate is intentionally selective: train-only fits can be rejected even when a candidate appears useful during search.

## Full Test Suite

The full test suite was run after evidence artifact generation. The Actions log ended with:

```text
RESULT: 99 passed, 0 failed, 0 skipped
ALL TESTS PASSED
```

Relevant tested properties include:

- adaptive search strictly exceeding frozen baselines in the bounded counterfactual setting
- sealed self-generated tasks and search blindness
- hidden file-world expectations not being present on disk
- agents not touching sealed scoring
- skill-gate rejection blocking reuse
- repair patches passing hidden checks
- forged admission being clean and revocable
- verifier pin stability
- semantic gates rejecting sabotage

## Reproduction Paths

GitHub Actions is the preferred public verifier because it gives external timestamps, commit identity, logs, and uploaded artifacts.

Manual workflow dispatch:

1. Open [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml).
2. Select `Run workflow`.
3. Inspect the completed run log and artifact bundle.

Equivalent local commands, if a reviewer wants to run them outside Actions:

```bash
python -m py_compile rsi_levels_metaforge_unified.py
python -u rsi_levels_metaforge_unified.py --mode file-battery
python -u rsi_levels_metaforge_unified.py --mode forge-battery
python -u rsi_levels_metaforge_unified.py --mode horizon-scan
python -u rsi_levels_metaforge_unified.py --mode test
```

## Boundary

This evidence is most relevant to verifier design around code-evolution systems:

- hidden eval handling
- adaptive-vs-frozen comparisons
- promotion gates
- rollback-sensitive admission
- full-suite regression checks
- artifact-level auditability

It should not be presented as solving Phase 4 code evolution by itself. The correct framing is a reference harness that can help test whether future mutation loops are actually improving behavior without leaking hidden answers, weakening gates, or retaining unsafe edits.
