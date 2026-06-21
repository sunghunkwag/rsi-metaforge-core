# Evidence

This repository is a bounded, CPU-scale research artifact for **measured,
sealed-evaluation recursive self-improvement (RSI)**. It is not a
general-intelligence claim, not proof that unrestricted recursive
self-improvement has been solved, and it sets no "AGI/ASI achieved" flag.

The useful claim is narrow and falsifiable: the runtime exposes verifier and
fitness harnesses that compare adaptive behaviour against frozen / cold
baselines under explicit gates, sealed held-out evaluation, and counterexample
audits — and a self-proposed abstraction measurably increases what the system
can solve, without leaking hidden answers or weakening gates.

## Runtime files

| File | Role |
| ---- | ---- |
| `asi_unified_core.py` | Distilled, self-contained 8-layer RSI core with a 49-test suite. |
| `rsi_metaforge_core.py` | Comprehensive runtime (the full monolith): the 8 layers plus stack-VM substrate, file-world tasks, self-forge admission, continuous functional substrate, grammar expansion, and the cross-domain meta-gate. |
| `verify_rsi.py` | Single-command RSI verification (both gates below). |

This runtime consolidates four source files (`asi_unified_core.py`,
`asi_architecture_core.py`, `asi_guarded.py`, `rsi_metaforge_core_v15.py`). The
architecture core was byte-identical to the unified core (only its header
docstring differed) and the guarded layer was a stand-alone module that could
not run on its own; both are folded into `asi_unified_core.py`. See the README
for the full mapping.

## Recursive self-improvement verification

Run:

```bash
python verify_rsi.py
```

It passes (exit 0) only when **both** independent, measured gates hold.

### Gate 1 — distilled-core self-improvement suite

`python asi_unified_core.py test` →

```text
RESULT: 49 passed, 0 failed (of 49 across 8 layers)
```

The self-improvement claims are backed directly by tests in that suite:

- `test_aint_learning_lowers_cost` — a learning run solves at least as much as a
  no-learning control while using strictly less total search cost.
- `test_aint_cumulative_abstraction_lineage_ge_3` — abstraction lineage reaches
  depth ≥ 3 (an improvement built on top of a previous improvement).
- `test_aint_compression_progress_measured` — the solved library compresses
  below its fully-expanded base-op size.
- `test_evolve_derived_operator_reduces_cost` — a derived operator reduces
  future search cost on later tasks.
- `test_guarded_loop_only_verified_operators` /
  `test_guarded_gate_rejects_spurious_accepts_true` — operator promotion is
  gated by an adversarial Socratic audit: spurious operators are rejected with
  an explicit counterexample; only verified operators are adopted.
- `test_*_determinism` across every layer — identical results across runs under
  fixed seeds.
- `test_evolve_derived_operator_kernel_fingerprint_unchanged` and the per-layer
  kernel-fixed tests — the immutable, hash-pinned kernel never moves while
  expressivity grows.

### Gate 2 — cross-domain meta-gate self-improvement

`python rsi_metaforge_core.py --mode general-domain-test` →

```json
{
  "meta_gate": {
    "accepted": true,
    "budget_max_cost": 4,
    "cold_frontier_validated": 0,
    "delta": 8,
    "warm_frontier_validated": 8
  },
  "unsupported_probe": { "total": 2, "validated": 0 },
  "train_total": 5,
  "train_validated": 5,
  "proposed_macros": [
    { "name": "GM0", "body": "MUL(SLOT,SLOT)",
      "source_tasks": ["grid_area_square", "list_sum_square", "record_sum_square",
                       "string_digit_square", "string_len_square"] }
  ],
  "claim_boundary": "heterogeneous feature-level self-improvement over list/string/grid/record tasks; not unbounded real-world general intelligence"
}
```

Reading: the system solved 5 training tasks across four domains, then proposed
the macro `GM0 = MUL(SLOT, SLOT)` (a reusable "square") from its **own** solved
programs. On a sealed held-out frontier of 8 new cross-domain tasks, the warm
searcher (with `GM0`) validated all 8 at search-budget cost ≤ 4, while the cold
baseline (without `GM0`) validated 0. The measured self-improvement is
`delta = 8`. Two genuinely out-of-scope probes (`semantic_text`,
`spatial_relation`) validated 0 of 2, confirming the gate fails honestly on
targets outside the abstraction's reach (no leakage). Search saw training
examples only; the holdout was used only for validation.

This is recursive self-improvement in the precise sense used here: an
abstraction distilled from prior solutions enables solving new, previously
unreachable tasks under the same budget, verified on sealed held-out inputs.

## Full runtime regression suite

The comprehensive runtime ships a full built-in suite:

```bash
python rsi_metaforge_core.py --mode test
```

The suite contains 192 tests. A subset reads JSON artifacts produced by the
evidence batteries (`file-battery`, `forge-battery`, `horizon-scan`,
`cfs-battery`, `expansion-battery`); those tests fail by design if the suite is
run before the batteries. The **Full Evidence** workflow runs the batteries
first and then the suite, which ends with:

```text
RESULT: 192 passed, 0 failed
ALL TESTS PASSED
```

The dynamic-execution boundary is also enforced as a test
(`test_trusted_core_dynamic_execution_boundary`): every `eval`/`exec` in the
runtime must live inside a function explicitly marked
`@sandbox_execution_boundary`, so candidate execution cannot hide outside the
audited sandbox surface.

## Evidence batteries

| Battery | Mode | What it checks |
| ------- | ---- | -------------- |
| File-world | `--mode file-battery` | Sealed hidden A/B file-task evaluations; hidden expectations never on disk. |
| Self-forge | `--mode forge-battery` | System-synthesized primitives admitted through sealed gates and reused downstream. |
| Horizon scan | `--mode horizon-scan` | Closure certificates over reachability walls. |
| Continuous substrate | `--mode cfs-battery` | Continuous functional substrate search with sealed-gate rejection and cascade revocation. |
| Expansion | `--mode expansion-battery` | Residue-driven feature expansion admitted only when sealed gates pass; speculative changes roll back on failure. |
| Grammar / Grammar2 | `--mode grammar-battery` / `--mode grammar2-battery` | Deterministic, designer-declared feature grammars closing witness walls; honest give-up outside the declared closure. |

These batteries test verifier discipline rather than raw capability: hidden
answers must not leak, train-only fits must not count as solved, speculative
changes must roll back when sealed gates fail, and gates must not be weakened to
manufacture progress.

## Reproduction

```bash
pip install numpy

# Recursive self-improvement (both gates)
python verify_rsi.py

# Distilled core suite
python asi_unified_core.py test

# Cross-domain meta-gate
python rsi_metaforge_core.py --mode general-domain-test

# Full evidence ordering (batteries first, then the regression suite)
python rsi_metaforge_core.py --mode file-battery
python rsi_metaforge_core.py --mode forge-battery
python rsi_metaforge_core.py --mode horizon-scan
python rsi_metaforge_core.py --mode cfs-battery
python rsi_metaforge_core.py --mode expansion-battery
python rsi_metaforge_core.py --mode grammar-battery
python rsi_metaforge_core.py --mode grammar2-battery
python rsi_metaforge_core.py --mode test
```

GitHub Actions is the preferred public verifier because it provides external
timestamps, commit identity, logs, and uploaded artifacts. Use the newest
successful [Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)
run on `main` after this file and the runtimes are committed.

## Boundary

This evidence is most relevant to verifier design for self-modifying search:
sealed/hidden evaluation, adaptive-vs-baseline comparison, promotion gates,
train-fit rejection, rollback-sensitive admission, counterexample audits, and
full-suite regression. It should not be presented as solving open-ended,
real-world recursive self-improvement. The correct framing is a reference
harness for testing whether a mutation/abstraction loop is *actually* improving
behaviour without leaking hidden answers, weakening gates, or retaining unsafe
edits.
