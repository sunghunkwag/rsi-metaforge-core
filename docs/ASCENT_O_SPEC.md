# Ascent Phase O — Meta-Improvement & Recursion Closure — Frozen Specification (O-1)

Spec-freeze document for the Ascent directive, Phase O (module M4). Every
constant, instrument, candidate, and protocol rule below is frozen at
commit time, BEFORE the first `--mode ascent-o-battery` evidence run.
Post-hoc changes require a new predictions file. Predictions:
`docs/PREDICTIONS_O.md`; results: `docs/O_RESULT.md`. Phases K/L/M/N are
read-only under this phase.

## 1. Mission and claim boundary

Close the recursion: the improver — the ISA extender, the amortizer
ordering, the setter policy, the search filters — is inside the
modification scope, and every modification ships through one of two
mandatory channels. Nothing here weakens a gate; the channels ARE gates.
The historical failure mode this phase is built against is the
finite-benchmark-win-that-transfers-nowhere; both channels are designed so
that a win is either measured on frozen instruments at equal budgets or
proved about the search space itself.

## 2. Channel A — empirical (counterfactual A/B on frozen instruments)

The frozen instrument is the union probe battery: the 48 Phase M probes
(from the committed L holdout corpus) plus the 6 MOD probes (§4), every
probe judged by its sealed checker on hidden instances at exactly
`ASCO_B_PROBE` = 1500 candidate evaluations. Candidates run sequentially
against the current incumbent; the rule is strict improvement in certified
passes or rollback; every record carries both pass counts and the full
per-probe cost vectors.

The pre-registered candidate sequence (jurisdictions in parentheses):

1. `A1_amortizer_v0_sliceA` (solver policy): the Phase M final incumbent
   ordering, registered there as this phase's first Channel A candidate.
2. `A2_extender_grant_MOD` (ISA extender): vocabulary grant of the base
   op `MOD` to the ascent solver. Carries the full extender protocol:
   the impossibility pre-certificate (the incumbent configuration passes
   0 of the 6 MOD probes at budget — recorded as `mod_passes_pre`) and
   the crossing evidence after (`mod_passes_post`).
3. `A3_extender_grant_SELECT` (ISA extender): vocabulary grant of
   `SELECT` — the pre-registered useless grant whose rejection
   demonstrates that extender modifications do not pass by default.
4. `A4_setter_LD_band6` (setter policy): the Phase L loop with lineage
   L_D starting at band 6 instead of 5, judged against the incumbent
   policy on two full L test-scale loop arms at identical frozen budgets;
   metric = certified adoptions (mined + crossed).

## 3. Channel B — certified (kernel-checked schema library)

Two completeness-preserving search-transformation schemas. Each schema is
a propositional skeleton proved ONCE — the proof objects are constructed
mechanically by the deduction-theorem algorithm (committed generator
`docs/make_schema_proofs_ascentO.py`, run once) and committed as
`docs/schema_proofs_ascentO.json` (SHA-256
`b4144faa3d9ada9d0b4e0ec3713fb7dd0933727032a3488674ca4bb6fb5fb959`);
the frozen N-1 kernel re-verifies both proofs at every battery start —
plus an executable premise verifier. Mutable code may INSTANTIATE a
schema; the kernel checks each instantiation: the outer substitution is
composed through every axiom step of the proof object and the whole
instance re-verified step by step. Channel B adoptions need no benchmark;
the certificate is about the search space.

- **S1 (depth-1 crash pruning; skeleton B, hypothetical syllogism
  `(p→q)→((q→r)→(p→r))`, 161 steps).** Semantic mapping, registered:
  p := "candidate is a solution", q := "candidate's first op does not
  crash on the empty stack", r := "candidate survives the filter".
  Premise (verified exhaustively by execution over the frozen probe
  inputs): every excluded op crashes on the empty stack. License: a
  solution always survives — pruning the excluded ops at depth 1 is
  complete.
- **S2 (INPUT-required; skeleton C, exchange
  `(p→(q→r))→(q→(p→r))`, 161 steps).** Semantic mapping, registered:
  p := "candidate is a solution", q := "the task's public outputs vary",
  r := "candidate contains INPUT". Premise (verified per task by direct
  inspection of the public pairs): an INPUT-free candidate computes a
  constant and cannot fit varying publics. The kernel-checked exchange
  turns the premise form into the filter license form: given varying
  publics, any solution contains INPUT.
- **Red team on record**: the pre-registered false-premise instantiation
  (S1 with `INPUT` smuggled into the exclusion set) must be refused
  (`o_premise_false`) and rolled back; a tampered proof-object byte must
  abort at load.

## 4. The MOD-probe family (frozen extender instrument)

Six scalar tasks whose ground truth requires `MOD`, authored as frozen
instrument data (`ASCO_MOD_PROBES`): v mod 3, v mod 2, (v mod 3)+1,
(v+1) mod 3, (2v) mod 3, (v mod 2)+2. Instances derive from the task id
and the K-1 master seed; checkers follow the K-1 scalar convention. The
solver vocabulary (`SC_SOLVER_VOCAB`) contains no `MOD`, so the family is
certifiably out of reach of the incumbent at any budget that cannot
synthesize modulus from DIVI/MUL/SUB within the MDL caps — and the
impossibility pre-certificate is measured, not assumed, at
`ASCO_B_PROBE`.

## 5. Frozen constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `ASCO_SPEC_VERSION` | "O-1" | |
| `ASCO_B_PROBE` | 1500 | per-probe budget (candidate evaluations) |
| `ASCO_MOD_SEED_TAG` | "AOMOD" | MOD-family task-id namespace |
| `ASCO_SCHEMA_SHA256` | `b4144faa…` (full value above) | schema-proof pin |
| `ASCO_S1_VARS` / `ASCO_S2_VARS` | registered substitutions | schema instantiations |
| A4 arm configuration | the L test-scale loop (generations 2, b_eval 1500, b_live 9000) | setter-policy instrument |
| `ASCO_PIN_SHA256` | see runtime constant | kernel + constants pin |

## 6. Metrics, digest, artifacts

- **O1**: the Channel A record — every candidate with adopt/rollback
  disposition, pass counts, and (for extender candidates) the
  pre/post-certificate pair.
- **O2**: the Channel B record — adopted schema instantiations with
  their kernel-checked instance goals and proof lengths, and the
  red-team refusal.
- **O3**: the end-to-end recursion-closure certificate: union-battery
  passes under the original incumbent versus under the fully adopted
  improver, at identical budgets.
- Battery digest `ao_digest`; two byte-identical runs asserted in CI;
  artifacts `reports/evidence/ascent_o_results.json` / `_ledger.jsonl`;
  run-1 copies committed as `docs/final_ascent_o.json`,
  `docs/ascent_o_ledger_final.jsonl`.

## 7. Anti-cheat battery (K7 extensions)

Schema proofs tamper-checked at load; instantiations kernel-checked (a
truncated proof object is refused); premise verifiers red-teamed with the
false-premise construction; the certified filters proven non-lossy on a
probe sample (same solutions, no greater cost); the MOD family verified
impossible for the base vocabulary at budget; Channel A adoption strictly
monotone with rollback otherwise; determinism two-run byte-identical; all
five ascent pins verified at battery start.

## 8. Known boundaries (disclosed at spec-freeze)

- The propositional skeletons carry the inferential form of the
  completeness arguments; the semantic content lives in the executable
  premise verifiers. The registered claim is exactly that split — the
  kernel certifies the logic, exhaustive execution certifies the
  premises — not that the kernel formalizes VM semantics.
- The A4 setter-policy instrument is the L test-scale loop, not the full
  battery loop (bounded battery runtime); the jurisdiction demonstration
  is the point, and the record says which instrument was used.
- `SELECT` is registered as the useless-grant candidate on the grounds
  that no probe family in the union battery needs conditionals; if the
  finals adopt it, that is a scored miss.
- Channel A candidates are judged sequentially in the registered order;
  order matters and is frozen (the same candidates in another order
  could yield another incumbent; no claim of order-optimality is made).

## 9. Calibration disclosure

The full battery under exactly these constants was observed before this
freeze and is disclosed as known-at-prediction-time in
`docs/PREDICTIONS_O.md`. After this freeze, no constant changes; the
battery runs as-is and its record ships as measured.
