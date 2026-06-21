# Architecture

The repository is centered on a single consolidated runtime file, [rsi_metaforge_core.py](../rsi_metaforge_core.py), which contains all 8 ASI/RSI layers inline, accompanied by a small verification helper, [verify_rsi.py](../verify_rsi.py), plus evidence documentation and GitHub Actions workflows. The architecture is best read as a gated experimental harness rather than a generic wrapper around an external model.

```mermaid
flowchart TD
    A[Task / environment source] --> B[Candidate generator]
    B --> C[Mutation or patch proposal]
    C --> D[Sandbox execution]
    D --> E[Test battery]
    E --> F[Validation gate]
    F -->|pass| G[Accepted modification]
    F -->|fail| H[Rejected modification]
    G --> I[Lineage update]
    H --> J[Failure archive]
    I --> K[Next iteration]
    J --> K
    K --> B
```

## Component Map

| Diagram node | Runtime anchor | What to inspect |
| --- | --- | --- |
| Task / environment source | [`build_sealed_tasks`](../rsi_metaforge_core.py), [`mint_task`](../rsi_metaforge_core.py), [`SealedFileTask`](../rsi_metaforge_core.py), [`build_general_domain_tasks`](../rsi_metaforge_core.py) | Sources of bounded tasks, generated tasks, file-world tasks, and general-domain probes. |
| Candidate generator | [`synthesize`](../rsi_metaforge_core.py), [`propose_improvement`](../rsi_metaforge_core.py), [`forge_synthesize`](../rsi_metaforge_core.py), [`fw_propose_from_residues`](../rsi_metaforge_core.py) | Search, macro proposal, self-forge primitive synthesis, and file-world residue-driven proposals. |
| Mutation or patch proposal | [`_mutate`](../rsi_metaforge_core.py), [`_mutate_drift`](../rsi_metaforge_core.py), [`ImprovementProposal`](../rsi_metaforge_core.py), [`gd_mine_macros`](../rsi_metaforge_core.py) | Token mutations, drift mutations, macro bundles, and mined general-domain macros. |
| Sandbox execution | [`compile_program`](../rsi_metaforge_core.py), [`file_world_run`](../rsi_metaforge_core.py), [`ArtifactFileTask`](../rsi_metaforge_core.py) | Candidate execution inside bounded VM/file-task contexts. |
| Test battery | [`run_tests`](../rsi_metaforge_core.py), [`file_battery`](../rsi_metaforge_core.py), [`forge_battery`](../rsi_metaforge_core.py), [`cfs_battery`](../rsi_metaforge_core.py), [`grammar_battery`](../rsi_metaforge_core.py), [`grammar2_battery`](../rsi_metaforge_core.py) | Built-in test suite and evidence battery entrypoints. |
| Validation gate | [`_make_gate`](../rsi_metaforge_core.py), [`meta_gate`](../rsi_metaforge_core.py), [`forge_admit`](../rsi_metaforge_core.py), [`gd_validates`](../rsi_metaforge_core.py), [`structural_gate`](../rsi_metaforge_core.py) | Hidden gates, meta-gates, forge admission, domain validation, and structural anti-bloat checks. |
| Accepted modification | [`run_wave`](../rsi_metaforge_core.py), [`_install`](../rsi_metaforge_core.py), [`forge_admit`](../rsi_metaforge_core.py) | Places where passed candidates are stored or made available to later iterations. |
| Rejected modification | [`MetaGateRecord`](../rsi_metaforge_core.py), [`RunState.rejected_digests`](../rsi_metaforge_core.py), gate-failure events in [`run_wave`](../rsi_metaforge_core.py) | Rejection logs, duplicate-proposal suppression, holdout failures, and counterfactual gate catches. |
| Lineage update | [`RunState`](../rsi_metaforge_core.py), [`lineage_report`](../rsi_metaforge_core.py), [`runstate_summary`](../rsi_metaforge_core.py) | Adopted tokens, waves, searcher versions, macro lineage, events, and serialized run summaries. |

## External Validation Layer

The CI layer is intentionally split:

- [Quick CI](../.github/workflows/quick-ci.yml) compiles the runtime, checks the CLI, runs a dynamic-evaluator guard, and runs the general-domain smoke gate.
- [Full Evidence](../.github/workflows/full-evidence.yml) runs the evidence batteries, the full regression suite, and uploads generated logs and JSON artifacts under `reports/evidence`.

DeepWiki should connect the architecture to those executable checks. A description that ignores gates, accepted/rejected candidates, lineage, or evidence artifacts misses the core research claim.
