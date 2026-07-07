# Evidence

This repository should be read as a bounded research artifact for validation-gated adaptive search, self-forge style candidate admission, continuous substrate probes, and grammar-mediated feature expansion. It is not a general-intelligence claim, not a drop-in Hermes Phase 4 implementation, and not proof that unrestricted recursive self-improvement has been solved.

The useful claim is narrower: the runtime exposes verifier and fitness harnesses that compare adaptive behavior against frozen or fixed-capacity baselines under explicit gates, hidden evaluations, rollback-sensitive admission, and full-suite regression checks.

## Current Runtime

The current runtime file is:

```text
rsi_levels_metaforge_unified.py
```

The current runtime extends the previous public evidence line with:

- continuous functional substrate checks through `cfs-battery`
- dynamic residue-driven feature expansion through `expansion-battery`
- depth-1 grammar feature expansion through `grammar-battery`
- depth-2 grammar feature expansion through `grammar2-battery`
- a closed self-curriculum compounding loop through `sc-battery` (two-run digest equality asserted in CI)
- a full built-in regression suite expected to report `178 passed, 0 failed`
- the Phases 0–I generalization research program: frozen holdout instrument, sealed exploration archive, external anchoring artifacts, stratified offer schedule, and per-phase reports, all committed under `docs/` with SHA-256 pins asserted by tests

The current runtime should be treated as publicly validated only after the **Full Evidence** GitHub Actions workflow succeeds for the commit that contains it.

## Runtime Evidence Anchor

The previous public runtime evidence anchor covered an older 99-test runtime. It remains useful as historical evidence for the earlier file-world, self-forge, horizon-scan, and full-suite checks, but it does not validate the current `(3)` runtime by itself.

- Workflow: [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)
- Historical run: [27588469107](https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/27588469107)
- Historical commit: `87d6f08d77eda690cd5a10d38f057ca2d0ffd8d3`
- Historical result: `success`
- Historical date: `2026-06-16`

For the current runtime, use the newest successful [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml) run on `main` after this file and `rsi_levels_metaforge_unified.py` are committed.

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
- Self-curriculum battery, run twice with byte-identical `sc_digest` and artifact equality asserted in the workflow
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

## Self-Curriculum Battery

The self-curriculum battery (`--mode sc-battery`) measures a closed loop that generates, witness-proves, admits, and solves its own tasks with zero human-authored tasks added, then evaluates transfer against the frozen human instrument under a pre-registered two-arm protocol.

The official record (two byte-identical runs, digest `f56c6c13a2bf3028`; committed artifacts `docs/final_sc_battery.json`, `docs/sc_ledger_final.jsonl`):

- 96 self-generated candidates, 16 admitted, 80 rejected with ledgered reasons, 14 distinct tasks solved; 13 of 14 solves used gate-adopted archive macros (library compression), 1 solved by base search alone
- composition band climbed 2 → 3 through the pre-registered learnability window; the M4 cost curve rose under the pre-registered I5-tightening confound
- transfer (the headline, pre-registered in `docs/PREDICTIONS_SC.md`, scored in `docs/SC_RESULT.md`): the curriculum arm did NOT beat the matched-compute control arm on the frozen instrument — control 24 vs curriculum 23 designer tasks at the final checkpoint. Matched-compute random exploration transferred (+1); the self-curriculum library was behaviorally inert on the instrument

This is a closed-world compounding measurement with an honest negative external-transfer result — not an autonomy claim.

## Full Test Suite

The current Full Evidence workflow requires the built-in full suite to end with:

```text
RESULT: 178 passed, 0 failed
ALL TESTS PASSED
```

The count is pinned exactly on purpose: a suite that silently gains or loses tests should turn the badge red until the pin is updated in the same change that alters the suite. The count history is 99 (pre-rename runtime), 116 (renamed runtime, pre-program), 147 (after the Phases 0–I research program added 31 instrument, isolation, and determinism tests), 156 (after Phase J added 9 extension, re-certification, and determinism tests for the approved ISA extension), 178 (after Phase SC added 15 attack-construction tests — one per anti-gaming invariant I1–I14 plus a band-label-fabrication attack — and 7 positive-path tests for the self-curriculum loop).

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
- SHA-256 pins on the frozen research-program artifacts under `docs/` (holdout instrument, exploration archives, anchor reports, ordering spec, final evaluation artifacts)
- ordering/eligibility isolation: the stratified offer schedule's computation cannot reach designer-task oracles, gates, or adoption records
- two-run byte-identity for the exploration, transfer, and final-evaluation reconstructions asserted in-suite
- self-curriculum anti-gaming invariants I1–I14, each enforced in the default battery path and each covered by a dedicated test: twelve construct the attack outright (identity task, constant task, non-injective generator, behavioural duplicate, frozen-solvable task, witnessless/invalid/over-budget witness, padded lookup-table program, archive-covered task, poser input suggestions, gate-source and pin tamper, ledger mutation and record drop, forbidden instrument access); determinism (I12) is proven by two-run digest identity plus a digest-sensitivity construction; budgets (I14) are literal-pinned in-suite and bound into the source pin, with invalid configurations refused
- a band-label-fabrication attack test: the harness measures every task's difficulty band from the generator itself and records the poser's claim as audit metadata only
- self-curriculum sealed pairs and witnesses held in write-once, memory-only stores, with the ledger carrying hashes only until task retirement

## Reproduction Paths

GitHub Actions is the preferred public verifier because it gives external timestamps, commit identity, logs, and uploaded artifacts.

Manual workflow dispatch:

1. Open [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml).
2. Select `Run workflow`.
3. Inspect the completed run log and artifact bundle.

Equivalent local commands, if a reviewer wants to run them outside Actions:

```bash
python -m py_compile "rsi_levels_metaforge_unified.py"
python -u "rsi_levels_metaforge_unified.py" --mode file-battery
python -u "rsi_levels_metaforge_unified.py" --mode forge-battery
python -u "rsi_levels_metaforge_unified.py" --mode horizon-scan
python -u "rsi_levels_metaforge_unified.py" --mode cfs-battery
python -u "rsi_levels_metaforge_unified.py" --mode expansion-battery
python -u "rsi_levels_metaforge_unified.py" --mode grammar-battery
python -u "rsi_levels_metaforge_unified.py" --mode grammar2-battery
python -u "rsi_levels_metaforge_unified.py" --mode test
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
