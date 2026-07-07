# Limitations

This repository should be read as a bounded experimental verifier and
MetaForge harness. The strongest claim should be limited to what the code,
logs, and reproducible runs actually demonstrate.

## Claim Boundaries — Target Properties and Pre-Registered Criteria

Under the Ascent directive, each open-endedness disclaimer below is stated
in two parts: the boundary as it stands, and the pre-registered,
falsifiable criterion under which a partial claim could ever be made. A
criterion being met would license exactly the stated partial claim and
nothing more; none of these criteria has been met unless a committed
RESULT document says so.

- **General intelligence.** Not demonstrated and not claimed. Target
  property: cross-domain competence under one verifier discipline.
  Pre-registered criterion for a partial claim: gate-certified,
  byte-identically reproduced improvement records in ≥ 3 substrates with
  disjoint value domains (the stack VM, the file world, and the formal
  domain), each with its own frozen instruments and its own
  pre-registered predictions scored, misses included. Status: the K-1
  (VM tasks), N-1 (formal domain), and file-world records exist
  separately; no unified cross-domain instrument has been registered, so
  no such claim is made.
- **Unbounded capability.** Not demonstrated and not claimed. Target
  property: sustained frontier growth without human-supplied tasks.
  Pre-registered criterion for a partial claim: ≥ 3 consecutive certified
  crossing cycles (impossibility or difficulty certificate → library/ISA
  growth through the registered gates → certified crossing at the same
  frozen budget), each cycle reproduced byte-identically twice, on
  instruments frozen before the first cycle. Status: the K-1 record
  certifies ONE such crossing cycle; the L-1 record certifies three
  crossings inside one run under the MDL-gated library; the O-1 record
  certifies one extender cycle (impossibility pre-certificate → grant →
  crossing evidence). No run has yet chained three consecutive cycles
  with ISA growth between them; the claim is not made.
- **Open-ended intelligence explosion.** Not demonstrated, not claimed,
  and not a goal (see the directive's hard non-goals). Target property:
  a flywheel whose every turn is certified. Pre-registered criterion for
  the only claim this repository will ever make in this direction:
  "the flywheel turned N times" for the measured N in the committed
  RESULT documents — certified gate passes per unit of logical budget on
  frozen instruments, nothing else. The measured N is small and the
  records say exactly where each turn stalled (K-1 §7: the crossing
  window is structurally narrow; SC/SC2: transfer was flat or negative).
- **LLM-agent generality.** This is not a generic LLM-agent wrapper
  claim; there are no model calls anywhere in the runtime (test-enforced:
  the dynamic-evaluator guard and the stdlib-only constraint). Target
  property: none — this boundary is permanent by the directive's
  constitution (§2.2: no LLM, embedding, or model-API calls of any kind).
- **Generalization from local tests.** Passing local tests does not
  imply broad generalization. Target property: transfer to instruments
  the searcher never touched. Pre-registered criterion (already in force
  since Phase SC): a curriculum/library must beat its matched-compute
  control arm on the frozen human instrument to claim transfer; the
  SC-1 record scored this honestly NEGATIVE (control 24 vs curriculum 23)
  and the claim is not made. The M-1 amortizer record is the first
  positive transfer-shaped result at a smaller scope: a strict
  passes-per-budget uplift on 48 sealed holdout families the training
  ledger never contained (2 → 6 at equal budget), and its claim is
  exactly that measurement.
- **Gate completeness.** Passing a gate means passing the gate as
  implemented, not that the gate is complete. Target property: gates
  that survive adversarial construction. Pre-registered criterion (in
  force): every new gate ships with red-team tests that CONSTRUCT the
  attack (the K7 battery, extended in every ascent phase); a gate
  without a constructed attack does not count as anti-cheat coverage.
  This is a discipline, not a completeness proof, and reviewers should
  challenge it.

## Validation Risks

Validation gates can be incomplete. A candidate can pass a local benchmark
while failing a stronger held-out task, a transfer test, a replication
run, or a reviewer-designed adversarial case.

Benchmarks can be gamed if anti-cheat controls are weak. The repository
includes tests for oracle isolation, hidden expectation handling,
rollback, dynamic-evaluator blocking, witness-vault isolation, no-self-
credit crossing snapshots, holdout contamination, and axiom-adoption
refusal — but those tests should be inspected and challenged rather than
treated as final proof.

Logs must be reproducible. For current public validation, the most useful
artifacts are GitHub Actions runs tied to a commit, generated result JSON,
uploaded logs, and local reproduction commands that a reviewer can rerun.

## Evidence Risks

The repository contains a historical evidence summary in
[EVIDENCE.md](../EVIDENCE.md), but historical success for an earlier
runtime is not automatic validation for later runtime changes. The current
runtime should be judged by the newest successful
[Full Evidence](https://github.com/sunghunkwag/rsi-metaforge-core/actions/workflows/full-evidence.yml)
run for the commit being reviewed.

Battery-generated result JSON files are not checked in. This keeps the
repository compact, but it means reviewers need the Actions artifact
bundle or a local reproduction run to inspect those records. The Phases
0–I research-program artifacts and the ascent-phase final artifacts are
the exception: they are committed under `docs/` with SHA-256 pins asserted
by the test suite or recorded in the RESULT documents.

## Current Measured Frontier

The Phases 0–J program left a concrete, attributed frontier (see
[SEQUENCING_RESULT.md](SEQUENCING_RESULT.md),
[CROSSING_RESULT.md](CROSSING_RESULT.md), and
[ATTRIBUTION_F.md](ATTRIBUTION_F.md)): 28 of 33 designer tasks solved on
the frozen Phase 0 instrument in the extended ISA; T18/T21/T22 open with a
vocabulary attribution; T31/T32 certified out of reach at the certified
horizon. The self-curriculum line (SC/SC2) measured honest negative
transfer and zero permanent schemas. The ascent line (K/L/M/N/O) measured
one witness-sealed crossing cycle, three MDL-gated crossings, a 3×
amortizer uplift on sealed holdouts with one rollback, a 35-theorem
kernel-checked formal domain with zero axiom adoptions, and a
channel-certified improver upgrade from 2 to 8 union-battery passes —
each with its own predictions scored in its RESULT document, misses
included.

Interventions that did not move a frontier are recorded as nulls with
their measurements ([ADVANCE_RESULT.md](ADVANCE_RESULT.md)), and
prediction misses are scored against the pre-registered predictions files
rather than reinterpreted.

## Future Work

Stronger evidence would require: more held-out tasks designed
independently of the implementation; transfer tests across task families
and data distributions; external replication by reviewers who did not
author the runtime; deeper axiom bases for the formal domain through the
owner-pre-registered amendment path; and a unified cross-domain instrument
for the criteria above. Until then, the repository should be described as
experimental evidence for bounded, validation-gated self-modification
behavior inside declared test environments.
