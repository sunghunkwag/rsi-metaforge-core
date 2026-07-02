# Architecture

The repository is centered on one monolithic runtime file, [rsi_levels_metaforge_unified.py](../rsi_levels_metaforge_unified.py), plus evidence documentation and GitHub Actions workflows. The architecture is best read as a gated experimental harness rather than a generic wrapper around an external model.

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
| Task / environment source | [`build_sealed_tasks`](../rsi_levels_metaforge_unified.py#L553), [`mint_task`](../rsi_levels_metaforge_unified.py#L648), [`SealedFileTask`](../rsi_levels_metaforge_unified.py#L8741), [`build_general_domain_tasks`](../rsi_levels_metaforge_unified.py#L37641) | Sources of bounded tasks, generated tasks, file-world tasks, and general-domain probes. |
| Candidate generator | [`synthesize`](../rsi_levels_metaforge_unified.py#L1227), [`propose_improvement`](../rsi_levels_metaforge_unified.py#L1505), [`forge_synthesize`](../rsi_levels_metaforge_unified.py#L7938), [`fw_propose_from_residues`](../rsi_levels_metaforge_unified.py#L9324) | Search, macro proposal, self-forge primitive synthesis, and file-world residue-driven proposals. |
| Mutation or patch proposal | [`_mutate`](../rsi_levels_metaforge_unified.py#L917), [`_mutate_drift`](../rsi_levels_metaforge_unified.py#L983), [`ImprovementProposal`](../rsi_levels_metaforge_unified.py#L1434), [`gd_mine_macros`](../rsi_levels_metaforge_unified.py#L37605) | Token mutations, drift mutations, macro bundles, and mined general-domain macros. |
| Sandbox execution | [`compile_program`](../rsi_levels_metaforge_unified.py#L1323), [`file_world_run`](../rsi_levels_metaforge_unified.py#L9504), [`ArtifactFileTask`](../rsi_levels_metaforge_unified.py#L9819) | Candidate execution inside bounded VM/file-task contexts. |
| Test battery | [`run_tests`](../rsi_levels_metaforge_unified.py#L3231), [`file_battery`](../rsi_levels_metaforge_unified.py#L9561), [`forge_battery`](../rsi_levels_metaforge_unified.py#L8447), [`cfs_battery`](../rsi_levels_metaforge_unified.py#L13474), [`grammar_battery`](../rsi_levels_metaforge_unified.py#L14280), [`grammar2_battery`](../rsi_levels_metaforge_unified.py#L14616) | Built-in test suite and evidence battery entrypoints. |
| Validation gate | [`_make_gate`](../rsi_levels_metaforge_unified.py#L451), [`meta_gate`](../rsi_levels_metaforge_unified.py#L1665), [`forge_admit`](../rsi_levels_metaforge_unified.py#L8169), [`gd_validates`](../rsi_levels_metaforge_unified.py#L37559), [`structural_gate`](../rsi_levels_metaforge_unified.py#L7033) | Hidden gates, meta-gates, forge admission, domain validation, and structural anti-bloat checks. |
| Accepted modification | [`run_wave`](../rsi_levels_metaforge_unified.py#L2055), [`_install`](../rsi_levels_metaforge_unified.py#L1647), [`forge_admit`](../rsi_levels_metaforge_unified.py#L8169) | Places where passed candidates are stored or made available to later iterations. |
| Rejected modification | [`MetaGateRecord`](../rsi_levels_metaforge_unified.py#L1540), [`RunState.rejected_digests`](../rsi_levels_metaforge_unified.py#L2016), gate-failure events in [`run_wave`](../rsi_levels_metaforge_unified.py#L2116) | Rejection logs, duplicate-proposal suppression, holdout failures, and counterfactual gate catches. |
| Lineage update | [`RunState`](../rsi_levels_metaforge_unified.py#L2005), [`lineage_report`](../rsi_levels_metaforge_unified.py#L2301), [`runstate_summary`](../rsi_levels_metaforge_unified.py#L2397) | Adopted tokens, waves, searcher versions, macro lineage, events, and serialized run summaries. |

## External Validation Layer

The CI layer is intentionally split:

- [Quick CI](../.github/workflows/quick-ci.yml) compiles the runtime, checks the CLI, runs a dynamic-evaluator guard, and runs the general-domain smoke gate.
- [Full Evidence](../.github/workflows/full-evidence.yml) runs the evidence batteries, the full regression suite, and uploads generated logs and JSON artifacts under `reports/evidence`.

DeepWiki should connect the architecture to those executable checks. A description that ignores gates, accepted/rejected candidates, lineage, or evidence artifacts misses the core research claim.
