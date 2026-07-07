# PREDICTIONS — Ascent Phase N (Proof Kernel & Formal Domain)

Pre-registered before the official `--mode ascent-n-battery` final runs.
Frozen protocol: `docs/ASCENT_N_SPEC.md` (N-1). Scoring: `docs/N_RESULT.md`
after the finals, misses included, no reinterpretation.

## Disclosure of what is known at prediction time

Per the standing protocol, the kernel, prover, lineage policies, and
budgets were calibrated before spec-freeze (the b_eval sweep, the
odd-ladder and lane policies, the step-size bound, and the step-theorem
adoption are all disclosed in the spec), and the calibration run of the
battery under exactly the frozen constants was observed (single machine,
CPython 3.11): digest `63c189f031795d35`; N1 = 35 theorems (6 mined goals,
10 MP-step, 19 axiom-instance-step); N2 = 8 refutations (the ADV probe
each generation; the setter's truth-table screening keeps lineage poses
tautology-only by policy); N3 = 0 crossings; 3 abbreviations adopted
through the master gate; 13 admitted conjectures; zero axiom adoptions.
The finals are two fresh runs of the same frozen configuration; P2–P7 are
reproductions of the calibration observation, registered as such. P1 and
P8–P10 are not implied by the calibration run.

## Predictions

- **P1 (determinism).** The two final battery runs are byte-identical:
  equal `an_digest`, equal ledger heads, `cmp`-equal
  `reports/evidence/ascent_n_results.json` and
  `reports/evidence/ascent_n_ledger.jsonl`.
- **P2 (theorem economy, headline).** N1 = 35 ≥ 20 theorems adopted, every
  one through the kernel (the only adoption path), each with its complete
  proof object in the ledger; composition split 6 goal / 10 MP-step / 19
  axiom-instance-step, reported as such.
- **P3 (refutation path).** N2 = 8 ≥ 1 conjectures refuted via bounded
  countermodel search and archived with their countermodels (the
  pre-registered ADV non-tautology fires every generation).
- **P4 (zero axiom adoptions).** The full-ledger count of proof-less
  adoptions is exactly 0; the battery aborts otherwise; the in-suite
  negative test constructs proof-less, forged, and thm-smuggling
  adoption attempts and all raise.
- **P5 (kernel audit).** The kernel audit checklist passes and is
  recorded in `docs/N_RESULT.md`: totality, structural checking only, no
  dynamic evaluation, no I/O, no randomness, no wall-clock, ≤ 500 audit
  lines, source bound into `ASCN_PIN_SHA256` (verified at battery start
  in both finals).
- **P6 (MDL interestingness).** 3 abbreviations adopted through the L-1
  master-gate rule on the theorem corpus (strict negative training delta,
  strictly positive holdout savings against the frozen SHA-pinned
  tautology corpus); every adoption and rejection carries exact bit
  deltas; every theorem record carries its codelen at adoption.
- **P7 (crossings).** N3 = 0 — registered as the honest expected outcome
  of this domain at b_eval = 20 (pool-squared instantiation sweeps grow
  with the library; the spec discloses this and registers the
  context-ordered prover as a Phase O Channel A candidate). If the finals
  produce a crossing, this prediction is scored as a MISS.
- **P8 (replay).** `an_replay_verify` re-derives every adopted theorem's
  proof through the kernel against the library prefix at its ledger
  index, and every abbreviation's deltas, in both finals.
- **P9 (suite).** The full test suite reports exactly
  `RESULT: 258 passed, 0 failed` when run after the evidence batteries
  (CI order); the 15 `test_an_` tests pass in isolation; the K-1, L-1,
  M-1, SC-1, and SC2-1 pins verify and their committed records are
  untouched.
- **P10 (claim boundary).** No configuration, axiom, grammar, or budget
  changes between this registration and the finals. The domain's
  decidability scope note stands: the measured frontier is
  derivability-under-budget, not truth. Axiom-base extensions remain an
  owner-pre-registered amendment path; nothing in this phase creates one.
