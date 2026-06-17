# Evidence

This repository should be read as a bounded research artifact for validation-gated adaptive search, self-forge style candidate admission, continuous substrate probes, and grammar-mediated feature expansion. It is not a general-intelligence claim, not a drop-in Hermes Phase 4 implementation, and not proof that unrestricted recursive self-improvement has been solved.

The useful claim is narrower: the runtime exposes verifier and fitness harnesses that compare adaptive behavior against frozen or fixed-capacity baselines under explicit gates, hidden evaluations, rollback-sensitive admission, and full-suite regression checks.

## Current Runtime

The current runtime file is:

```text
rsi_levels_metaforge_unified (3).py
```

The current runtime extends the previous public evidence line with:

- continuous functional substrate checks through `cfs-battery`
- dynamic residue-driven feature expansion through `expansion-battery`
- depth-1 grammar feature expansion through `grammar-battery`
- depth-2 grammar feature expansion through `grammar2-battery`
- a full built-in regression suite expected to report `116 passed, 0 failed`

The current runtime should be treated as publicly validated only after the **Full Evidence** GitHub Actions workflow succeeds for the commit that contains it.

## Runtime Evidence Anchor

The previous public runtime evidence anchor covered an older 99-test runtime. It remains useful as historical evidence for the earlier file-world, self-forge, horizon-scan, and full-suite checks, but it does not validate the current `(3)` runtime by itself.

- Workflow: [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)
- Historical run: [27588469107](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/27588469107)
- Historical commit: `87d6f08d77eda690cd5a10d38f057ca2d0ffd8d3`
- Historical result: `success`
- Historical date: `2026-06-16`

For the current runtime, use the newest successful [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml) run on `main` after this file and `rsi_levels_metaforge_unified (3).py` are committed.

## Full Evidence Workflow

The Full Evidence workflow runs these stages:

- Python compile check
- File-world evidence battery
- Self-forge evidence battery
- Horizon-scan certificate
- Continuous functional substrate battery
- Expansion battery
- Grammar battery
- Grammar2 battery
- Full built-in test suite after generated evidence artifacts
- Evidence artifact upload

The workflow uploads generated logs and JSON artifacts under `reports/evidence`.

## File-World Evidence Battery

The file-world battery runs sealed hidden A/B evaluations on unseen eval seeds. The hidden expectations are not written into the workspace.

The historical public evidence record reported:

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

The historical public evidence record reported:

- `forged=4/4`
- `gate-adopted=2/4`
- downstream general-domain bridge completed
- forged-operator downstream task solved only with the admitted forged operations

The gate is intentionally selective: train-only fits can be rejected even when a candidate appears useful during search.

## Continuous Functional Substrate Battery

The CFS battery tests a continuous vector substrate where candidate programs are represented through feature geometry rather than discrete token programs.

The evidence boundary is important:

- geometric or closed-form train fits are measured separately from sealed-gate success
- train-exact vectors can still be rejected by hidden gates
- propagation and cascade revocation are checked through a ledger
- the verifier remains the judge; the substrate does not remove the need for sealed gates

## Expansion Battery

The expansion battery checks whether the system can add measured feature dimensions from residue when the fixed substrate cannot cross a wall.

The intended evidence is:

- fixed-capacity failures are distinguished from extended-substrate successes
- extensions are admitted only when sealed gates pass
- speculative candidates can run ahead of the gate but must roll back if finalization fails
- the verifier is not weakened to manufacture a closure result

## Grammar Batteries

The grammar and grammar2 batteries test declared feature-expression grammars as bounded reach extensions.

The intended evidence is:

- generated grammar features are pure functions of public inputs
- grammar enumeration is deterministic
- depth-1 grammar can close a witness wall that the fixed bank cannot
- grammar2 is a deterministic superset that can close a witness wall beyond depth-1 grammar
- honest give-up cases remain rejected when the target lies outside the declared grammar closure

The grammar primitives are designer-declared. These batteries measure bounded expressive reach; they are not evidence of unrestricted capability invention.

## Full Test Suite

The current Full Evidence workflow requires the built-in full suite to end with:

```text
RESULT: 116 passed, 0 failed
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
- continuous substrate search and sealed-gate rejection discipline
- residue-driven expansion without gate weakening
- speculative adoption rollback
- deterministic grammar and grammar2 feature expansion
- honest rejection of targets outside declared grammar closure

## Reproduction Paths

GitHub Actions is the preferred public verifier because it gives external timestamps, commit identity, logs, and uploaded artifacts.

Manual workflow dispatch:

1. Open [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml).
2. Select `Run workflow`.
3. Inspect the completed run log and artifact bundle.

Equivalent local commands, if a reviewer wants to run them outside Actions:

```bash
python -m py_compile "rsi_levels_metaforge_unified (3).py"
python -u "rsi_levels_metaforge_unified (3).py" --mode file-battery
python -u "rsi_levels_metaforge_unified (3).py" --mode forge-battery
python -u "rsi_levels_metaforge_unified (3).py" --mode horizon-scan
python -u "rsi_levels_metaforge_unified (3).py" --mode cfs-battery
python -u "rsi_levels_metaforge_unified (3).py" --mode expansion-battery
python -u "rsi_levels_metaforge_unified (3).py" --mode grammar-battery
python -u "rsi_levels_metaforge_unified (3).py" --mode grammar2-battery
python -u "rsi_levels_metaforge_unified (3).py" --mode test
```

## Boundary

This evidence is most relevant to verifier design around code-evolution systems:

- hidden eval handling
- adaptive-vs-frozen comparisons
- promotion gates
- train-fit rejection
- rollback-sensitive admission
- grammar-bounded feature expansion
- full-suite regression checks
- artifact-level auditability

It should not be presented as solving Phase 4 code evolution by itself. The correct framing is a reference harness that can help test whether future mutation loops are actually improving behavior without leaking hidden answers, weakening gates, or retaining unsafe edits.
