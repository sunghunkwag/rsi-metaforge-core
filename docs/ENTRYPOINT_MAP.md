# Entry Point Map — `rsi_levels_metaforge_unified.py`

Phase 0 execution-structure survey. All line numbers refer to the file as of
the Phase 0 baseline commit (re-derive by grep after any later change).

## Execution model on direct invocation

The file contains **six** textual `if __name__ == "__main__":` blocks
(lines 29945, 31128, 31616, 33354, 34737, 35703). **Only the last one
(line 35703) is executable code.** The other five sit inside raw-string
literals of the `INTEGRATED_SOURCE_ARCHIVE` (lines 14399–34741), which
preserves five original source files verbatim as inert text:

| Archive key | String literal spans | Origin file |
|---|---|---|
| `systemtest_4_1` | 14400–29949 | `Systemtest (4)(1).py` |
| `open_ended_rsi` | 29952–31132 | `open_ended_rsi.py` |
| `hdc_experiment` | 31135–31712 | `hdc_experiment.py` |
| `rsi_levels_emergence_1` | 31715–33358 | `rsi_levels_emergence(1).py` |
| `rsi_levels_plus_1` | 33361–34741 | `rsi_levels_plus(1).py` |

Direct invocation (`python3 rsi_levels_metaforge_unified.py ...`) therefore
executes module-level definitions top to bottom (importing is cheap, ~0.2 s;
the archive assignments just build strings) and then runs exactly **one**
CLI: `main()` at line 35595. There is no sequential multi-`__main__`
execution in practice.

Archived subsystems become live only through `OrganicSubsystemManager`
(line 34802), which writes each archive string to
`<tempdir>/organic_metaforge_embedded/<name>.py` and imports it as an
isolated module named `organic_<name>` (lines 34838–34848). Because
`__name__` is then `organic_<name>`, the archived `__main__` blocks never
fire. Note (GR6): the archived `open_ended_rsi` source redefines
`MAX_STACK`/`MAX_PROGRAM_LEN` (near line 29994) for that embedded subsystem
only; the live top-VM constants are lines 94–101.

## The single live CLI (`main()`, line 35595)

`argparse` parser "real-search RSI core"; flags: `--mode` (default `demo`),
`--save`, `--only`, `--wave-from`, `--wave-to` (default `WAVES`=8),
`--adaptive-json`, `--frozen-json`, `--extract-dir`. Dispatch chain at lines
35619–35700; an unmatched mode falls through to `demo()`.

| Mode | Handler (line) | What it does | Writes |
|---|---|---|---|
| `demo` (default) | `demo` (2240) | Builds/loads the adaptive RunState and prints solved/open tasks, meta-gate records, lineage report, events. | none |
| `test` | `run_tests` (2841) | Runs every function in the `TESTS` registry (117 after Phase 0; 116 pre-existing + 1 added instrument check); PASS/FAIL per test; `SystemExit(1)` on any failure. `--only` = substring filter on test names. | none directly |
| `counterfactual` | `demo_counterfactual` (2268) | Builds adaptive and frozen arms at identical tasks/budgets/seeds; prints counterfactual comparison JSON. | none |
| `run-adaptive` | `run_system` (1921) | Full wave loop, `adaptive=True`; prints `{solved, digest}`. | runstate JSON at `--save` if given |
| `run-frozen` | `run_system` (1921) | Same loop, `adaptive=False` (frozen searcher). | runstate JSON at `--save` if given |
| `cf-report` | `counterfactual_report_from` (2163) | Compares two saved runstate summaries (`--adaptive-json`, `--frozen-json`). | none |
| `step` | `run_system` (1921) | Resumable checkpointed run between `--wave-from` and `--wave-to`; restores from `--save` if it exists. | always saves runstate JSON (`--save` or `adaptive.json`) |
| `manifest` | `print_integrated_manifest` (34761) | JSON manifest (lines/chars/sha256_16) of archive entries + runtime-core counters. | none |
| `extract` | `extract_integrated_sources` (34765) | Writes each archived source to `<extract-dir>/<name>.py`. | `<extract-dir>/*.py` |
| `organic` | `run_organic_smoke` (35022) | Loads archived subsystems into isolated namespaces; per-subsystem status JSON; exit 1 unless ≥5 load and ≥3 smoke checks pass. | temp module files |
| `organic-test` | `run_full_organic_tests` (35043) | Full `run_tests()` then organic smoke; exit 0 only if both pass. | none directly |
| `hdc-rsi` | `demo_hdc_rsi` (2687) | Hypervector plan encode/transfer/decode demo (Kuramoto phase-locking). | none |
| `general-domain-test` | `run_general_domain_self_improvement_test` (35535) | Heterogeneous list/string/grid/record feature-synthesis self-improvement test with cold/warm frontier meta-gate; exit 1 on gate rejection or unsupported-probe leakage. | report JSON at `--save` if given |
| `directive-battery` | `directive_battery` (3890) | S1 PRM ablation, S2 debate/constitution, S3 world-model coverage experiments; prints measurements. | none |
| `wm-report` | `build_wm` (3881) | Bootstraps `OpSemanticsModel` and prints its coverage report JSON. | none |
| `reflection-battery` | `reflection_battery` (5062) | Reflection-tower drills (retraction/poisoning quarantine, cross-substrate transfer, calibration, frame audit). | none |
| `closure-report` | `closure_report` (5027) | Constructor lemma + wall reachability certificates summary JSON. | none |
| `horizon-scan` | `targeted_reach_scan` (5535) | Exact observational-equivalence reachability scan of wall targets to depth 8 (`class_cap=700000`). | `closure_scan.json` (checkpointed) |
| `horizon-report` | `horizon_report` (5824) | Pretty-prints the capability-horizon report from scan artifacts if present. | none |
| `hdc-battery` | `hdc_battery` (6403) | A/B of VSA interference-field-shaped search vs plain search under equal budgets/seeds + deception probe. | none |
| `clash-battery` | `clash_battery` (6869) | Semantic-vs-structural adjudication: failure covariance, quarantine lab, recompression. | none |
| `forge-battery` | `forge_battery` (8050) | Self-forge primitive admission for the certified walls + GD bridge + downstream reuse. | `forge_results.json` |
| `file-battery` | `file_battery` (9164) | File-world skill rounds + sealed hidden A/B on unseen eval seeds. | `file_world_results.json`, `./fileworld/` |
| `ext-battery` | `ext_battery` (12753) | Re-runs the ten ported extension-layer test functions with timing. | none at top level |
| `cfs-battery` | `cfs_battery` (13077) | Continuous functional substrate battery on walls T29–T32 + sealed-gate rejection checks. | `cfs_results.json` |
| `expansion-battery` | `expansion_battery` (13580) | SECTION 24 expansion rules battery (residue-driven growth, speculative adoption + rollback). | `expansion_results.json` |
| `grammar-battery` | `grammar_battery` (13883) | Depth-1 feature-grammar expansion battery + honest give-up target. | `grammar_results.json` |
| `grammar2-battery` | `grammar2_battery` (14219) | Depth-2 grammar battery (masked-reduction closes what depth-1 cannot) + give-up target. | `grammar2_results.json` |
| `explore` | `explore_run` (Phase D) | Track 2 exploration of the VM behavior space against the frozen probe battery; seeded, budgeted, deterministic; `--vocab-from` supplies searcher macros as building blocks (GR9: vocabulary only). | archive JSON at `--save` (default `exploration_archive_phaseD.json`) |
| `explore-report` | `explore_coverage_report` (Phase D) | Prints coverage facts (cells filled, curve, lineage depths, example elites) from a saved exploration archive at `--save`. | none |

## Native test harness

- Registry: `TESTS` list, initialized with 26 entries at line 2810, grown by
  13 `TESTS.extend`/`.append` sites through line 14378 (all live code), plus
  the Phase 0 instrument check appended after line 14384. Total: 117.
- Runner: `run_tests(only="")` (line 2841) — plain loop, exception = FAIL,
  `SystemExit(1)` on any failure, prints `ALL TESTS PASSED` otherwise.
- The 31 additional textual `def test_*` occurrences inside the archive
  strings are inert (never collected by the native runner or pytest).
- `python3 -m pytest rsi_levels_metaforge_unified.py` collects exactly the
  live zero-argument `test_*` functions; `__main__` blocks do not fire.

## Reproducibility caveats

- `build_adaptive()`/`build_frozen()` (lines 2226–2237) **read**
  `adaptive.json` / `frozen.json` from the current working directory as
  caches if present (they never write them). Modes `demo`, `counterfactual`,
  and several batteries, plus tests that use these builders, will silently
  reuse stale state from a dirty CWD. Run from a clean CWD for baseline
  measurements.
- `horizon-report` reads `closure_scan.json` / `closure_scan_L7.json` if
  present; `file-battery` creates `./fileworld/` workspaces.
- All battery result JSONs land in the CWD and are `.gitignore`d.
