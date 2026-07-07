# PREDICTIONS — Ascent Phase O (Meta-Improvement & Recursion Closure)

Pre-registered before the official `--mode ascent-o-battery` final runs.
Frozen protocol: `docs/ASCENT_O_SPEC.md` (O-1). Scoring: `docs/O_RESULT.md`
after the finals, misses included, no reinterpretation.

## Disclosure of what is known at prediction time

Per the standing protocol, the calibration run of the battery under
exactly the frozen constants was observed (single machine, CPython 3.11):
digest `f064a014d33b3f89`; Channel B: 2 schema instantiations adopted, 1
red-team refusal; Channel A: incumbent 2/54, A1 adopted (6/54), A2 adopted
(8/54, MOD probes 0 → 2), A3 rolled back (8 vs 8), A4 rolled back (4 vs
4 certified adoptions on the loop arms). The finals are two fresh runs of
the same frozen configuration; P2–P6 are reproductions of the calibration
observation, registered as such. P1 and P7–P9 are not implied by the
calibration run.

## Predictions

- **P1 (determinism).** The two final battery runs are byte-identical:
  equal `ao_digest`, equal ledger heads, `cmp`-equal
  `reports/evidence/ascent_o_results.json` and
  `reports/evidence/ascent_o_ledger.jsonl`.
- **P2 (Channel B, headline).** Both registered schema instantiations
  adopt with kernel-checked instance proofs (161 steps each), and the
  pre-registered false-premise instantiation is refused
  (`o_premise_false`) and rolled back on record — ≥ 1 adoption and ≥ 1
  rejection through the certified channel.
- **P3 (Channel A, headline).** A1 adopts at 6/54 over the incumbent's
  2/54; A2 adopts at 8/54; A3 rolls back at 8 vs 8; A4 rolls back at 4
  vs 4 — ≥ 1 adoption and ≥ 1 rejection through the empirical channel,
  spanning all three jurisdictions (solver policy, ISA extender, setter
  policy).
- **P4 (extender protocol end-to-end).** The adopted grant's record
  carries the impossibility pre-certificate (`mod_passes_pre` = 0 under
  the pre-grant configuration) and the crossing evidence
  (`mod_passes_post` = 2) at the same frozen budget; the useless grant
  (SELECT) is rejected.
- **P5 (recursion closure).** The end-to-end certificate: union-battery
  passes rise from 2 (original incumbent) to 8 (fully adopted improver)
  at identical per-probe budgets — a 4× improvement in certified passes
  per logical budget, every step of which went through a channel.
- **P6 (completeness preservation).** The adopted Channel B filters lose
  no solution and increase no cost on the probe sample (tested
  in-suite); the certified claim is the kernel-checked license plus the
  exhaustively verified premises.
- **P7 (suite).** The full test suite reports exactly
  `RESULT: 270 passed, 0 failed` when run after the evidence batteries
  (CI order); the 12 `test_ao_` tests pass in isolation; all five ascent
  pins (K, L, M, N, O) verify and every committed record is untouched.
- **P8 (claim boundary).** No configuration, instrument, candidate, or
  schema changes between this registration and the finals. No claim of
  candidate-order optimality; no capability claim beyond the
  gate-certified pass counts above.
- **P9 (constitution).** The frozen kernel components (K1–K7) are
  untouched by every adopted modification: the vault, meter, ledger,
  replay engines, MDL formula, proof kernel, and anti-cheat battery pins
  all verify in both finals; the adopted improver modifications live
  entirely in mutable-citizen territory (vocabulary, ordering, filters,
  setter bands).
