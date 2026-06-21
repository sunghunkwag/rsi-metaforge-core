# RSI MetaForge Core

[![Quick CI](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/quick-ci.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/quick-ci.yml)
[![Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml/badge.svg)](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)
[![DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/sunghunkwag/rsi-metaforge-core)

RSI MetaForge Core is an experimental, CPU-scale Python research runtime for
studying **measured, sealed-evaluation recursive self-improvement (RSI)**:
validation-gated adaptive search, bottom-up program synthesis, cumulative
abstraction, operator evolution, and counterexample-guided (Socratic) operator
promotion over an immutable, hash-pinned kernel.

It is **not** a general-intelligence claim, **not** proof that unrestricted
recursive self-improvement has been solved, and it sets **no** "AGI/ASI
achieved" flag. Every self-claim is backed by a test that runs in this
repository. For the claim boundary and validation record, see
[EVIDENCE.md](EVIDENCE.md).

## What this repository integrates

This runtime is the consolidation of four source files into two coherent,
runnable artifacts. The mapping is explicit so that nothing is silently
dropped:

| Source file (input)            | Where it lives now |
| ------------------------------ | ------------------ |
| `asi_unified_core.py`          | `asi_unified_core.py` (kept as the distilled core) |
| `asi_architecture_core.py`     | folded into `asi_unified_core.py` (byte-identical code; only its header docstring differed) |
| `asi_guarded.py`               | folded into `asi_unified_core.py` as the Socratic-guarded layer (it cannot run stand-alone; here it runs) |
| `rsi_metaforge_core_v15.py`    | `rsi_metaforge_core.py` (the full 20-section monolith / comprehensive runtime) |

The result is two files:

- **`asi_unified_core.py`** — a single, self-contained core that implements the
  8 RSI layers and ships a focused 49-test suite (runs in roughly a minute).
  This is the fast, readable, fully-green verification surface.
- **`rsi_metaforge_core.py`** — the comprehensive runtime (the monolith). It
  contains the same 8 ASI/RSI layers plus the broader RSI machinery: a stack-VM
  substrate, file-world artifact tasks, self-forge primitive admission,
  continuous functional substrate probes, grammar-mediated feature expansion,
  and the cross-domain **general-domain meta-gate** self-improvement test.

## The 8 layers (both files)

1. Immutable, hash-pinned **kernel** (per-substrate fingerprint) — the single
   root of trust: it evaluates, checks equivalence, and replays. It is never
   modified; trust never expands while expressivity does.
2. **Multiple substrates** — arithmetic ring, boolean algebra, stack VM.
3. **Kuramoto** phase-coupled binding — dynamic primitive binding from a cold,
   neutral start.
4. **Compression-progress** curriculum — tasks chosen by how much they compress
   what is already known.
5. **Bottom-up synthesis** — observational-equivalence search; the smallest
   solving program, found deterministically.
6. **Cumulative abstraction / macros** — solved structure is distilled into
   reusable macros (lineage depth grows: improvements built on improvements).
7. **Operator evolution + cross-substrate transfer** over the fixed kernel.
8. **Socratic gate (CEGIS) + guarded autonomous loop** — a questioner/respondent
   debate judged by the kernel kills spurious fits; operator promotion is gated
   on surviving an adversarial audit, then the loop runs
   solve → verify → abstract → gate → promote.

## Verifying recursive self-improvement

A single command runs both independent, measured demonstrations:

```bash
python verify_rsi.py
```

- **Gate 1 — distilled-core suite:** runs `asi_unified_core.py test` (49 tests
  across 8 layers). The RSI-specific tests assert that learning lowers search
  cost vs. a no-learning control, that cumulative abstraction reaches lineage
  depth ≥ 3, that the solved library compresses below its expanded size, that a
  derived operator reduces future search cost, and that the Socratic gate
  rejects spurious operators while admitting verified ones.
- **Gate 2 — cross-domain meta-gate:** runs
  `rsi_metaforge_core.py --mode general-domain-test`. The system proposes a
  macro from its own solved programs, then an A/B meta-gate measures a "warm"
  searcher (with the self-proposed abstraction) against a "cold" baseline
  (without it) on a sealed held-out cross-domain frontier
  (list / string / grid / record). Self-improvement is the measured delta:
  the run is accepted only when the warm searcher validates frontier tasks the
  cold baseline cannot, while out-of-scope probes stay rejected (no leakage).

`verify_rsi.py` exits `0` only if **both** gates pass.

## Usage

```bash
# Recursive self-improvement verification (both gates)
python verify_rsi.py

# Distilled core: full 49-test suite across 8 layers
python asi_unified_core.py test

# Distilled core: inspect a single layer's demo output
python asi_unified_core.py demo guarded     # or: integrated, open, evolve, unify, auto, search, socratic

# Comprehensive runtime: cross-domain meta-gate self-improvement
python rsi_metaforge_core.py --mode general-domain-test

# Comprehensive runtime: per-layer ASI/RSI test suites
python rsi_metaforge_core.py --mode asi-guarded-test    # also asi-integrated-test, asi-open-test, ...

# Comprehensive runtime: full built-in regression suite
#   (run the evidence batteries first so artifact-backed tests have their inputs)
python rsi_metaforge_core.py --mode test

# Comprehensive runtime: all available modes
python rsi_metaforge_core.py --help
```

> Note: a few tests in `--mode test` read JSON artifacts produced by the
> evidence batteries (`file-battery`, `forge-battery`, `horizon-scan`,
> `cfs-battery`, `expansion-battery`, `grammar-battery`, `grammar2-battery`).
> Run those modes first (as the Full Evidence workflow does) for a clean
> `0 failed` result.

## Evidence batteries

```bash
python rsi_metaforge_core.py --mode file-battery
python rsi_metaforge_core.py --mode forge-battery
python rsi_metaforge_core.py --mode horizon-scan
python rsi_metaforge_core.py --mode cfs-battery
python rsi_metaforge_core.py --mode expansion-battery
python rsi_metaforge_core.py --mode grammar-battery
python rsi_metaforge_core.py --mode grammar2-battery
```

These batteries test verifier discipline: hidden answers must not leak,
train-only fits must not count as solved, speculative changes must roll back
when sealed gates fail, and gates must not be weakened to manufacture progress.

## Reviewer-oriented documentation

- [Overview](docs/00_overview.md)
- [Architecture](docs/01_architecture.md)
- [Recursive Self-Improvement Loop](docs/02_rsi_loop.md)
- [Validation Gates and Anti-Cheat Controls](docs/03_validation_gates.md)
- [Evidence Logs](docs/04_evidence_logs.md)
- [Limitations](docs/05_limitations.md)

## GitHub Actions validation

- **Quick CI** runs on push, pull request, and manual dispatch. It compiles both
  runtimes, checks the CLI surface, and runs `verify_rsi.py` (both
  self-improvement gates).
- **Full Evidence** runs the evidence batteries, then the full regression suite,
  and uploads generated logs and JSON artifacts.

## Dependencies

Python 3.11+ and `numpy` (used by the Kuramoto binding layer):

```bash
pip install numpy
```

## Repository status

This repository is maintained as a research artifact. Results, terminology, and
implementation details should be read as experimental, bounded, and subject to
revision. The correct framing is a reference harness for testing whether a
self-modifying search loop is *actually* improving its own behavior without
leaking hidden answers, weakening gates, or retaining unsafe edits.
