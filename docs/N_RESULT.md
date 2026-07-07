# N RESULT — Proof Kernel & Formal Domain, Final Evaluation

**The formal domain ran under the same certificate discipline as the task
factory: 35 theorems adopted, every one through the kernel — the only
adoption path that exists — each with its complete proof object in the
ledger; 8 conjectures refuted by bounded countermodel search with their
countermodels archived; zero axiom adoptions, enforced by the absence of
any code path that could perform one and counted over the full ledger.**
Crossings were zero, exactly as pre-registered: at b_eval = 20 the
library-fed instantiation sweeps grow faster than the budget, and the
record says so instead of hiding it.

Register: `docs/PREDICTIONS_N.md` (committed at the N-1 spec-freeze
commit, before the final runs). Frozen protocol: `docs/ASCENT_N_SPEC.md`
(N-1). Phases K/L/M records are unchanged.

## 1. Kernel audit (K6 — frozen at this record)

The audit surface is the eight kernel functions (`an_formula_ok`,
`an_size`, `an_canon`, `an_subst`, `an_check_proof`, `an_adopt_theorem`,
`an_eval`, `an_countermodel`), asserted in-suite to be under 500 source
lines and free of dynamic evaluation, I/O, randomness, wall-clock, and
imports. Checklist, verified:

- **Totality**: proof length (≤ 512 steps) and formula size (conjectures
  ≤ 13, proof steps ≤ 128) are bounded before checking; every recursion
  is size-bounded; every input terminates.
- **Structural checking only**: axiom instantiation by substitution,
  modus ponens by tuple equality, library premises by canonical-form
  membership; no evaluation of any kind.
- **Determinism**: pure functions of their arguments; byte-identical
  across runs by construction.
- **No axiom-adoption API**: `an_adopt_theorem` is the only path into
  the library and refuses anything without a kernel-checked proof; the
  negative test constructs proof-less, forged, and thm-smuggling
  adoption attempts and all raise. Axiom-base extensions remain an
  owner-pre-registered amendment path; no code path creates one.
- **Frozen**: the kernel source and the axiom base (Łukasiewicz A1–A3)
  are bound into `ASCN_PIN_SHA256` (`df7fc303…`), verified at every
  battery start.

## 2. Protocol and determinism

One battery configuration (8 generations, pose_slots 6, b_eval 20,
b_live 20000, H 5; lineage policies as registered in the spec §3),
executed twice:

| Run | `an_digest` | ledger head (prefix) |
| --- | --- | --- |
| 1 | `63c189f031795d35` | `17d21283c3ee89ed…` |
| 2 | `63c189f031795d35` | `17d21283c3ee89ed…` |

Byte-identical results JSON and hash-chained ledger. `an_replay_verify`
re-checked every adopted theorem's proof through the kernel against the
library prefix at its ledger index, and every abbreviation's exact
deltas, before either digest printed. Run-1 copies committed as `docs/final_ascent_n.json`
(sha256 `2f664df75a2940681882cf99af5a5e196c26b74d782e201866b40857f9b21d41`)
and `docs/ascent_n_ledger_final.jsonl`
(sha256 `fa6e055b6df37be80370b7a568c115591f3e527c148cc2f728190369060ff1a5`).

## 3. The theorem economy (N1/N2/N4)

- **N1 = 35 theorems** (composition split, reported as registered: 6
  mined conjecture goals, 10 novel MP-step theorems, 19 novel
  axiom-instance step theorems — an axiom-instance THEOREM carries a
  one-step kernel proof and is not an axiom adoption). 13 conjectures
  admitted past the frontier prover; 76 setter emissions (32 of them ADV
  probes); 13 frontier markers.
- **N2 = 8 refutations**, each with its countermodel in the ledger (the
  pre-registered ADV non-tautology fires every generation; lineage poses
  are tautology-screened by the registered setter policy).
- **N4 = 3 abbreviations** adopted through the L-1 master-gate rule on
  the theorem corpus (strict negative training delta, strictly positive
  holdout savings against the frozen 69-tautology corpus,
  SHA `583dcc7d…`); 64 rejections with exact bit deltas; every theorem
  record carries its codelen at adoption — the computable
  interestingness signal.
- **N5 = 0 axiom adoptions** (full-ledger count; battery aborts
  otherwise).

## 4. Prediction scoring (register: docs/PREDICTIONS_N.md)

| # | prediction | verdict |
| --- | --- | --- |
| P1 | two final runs byte-identical | **CONFIRMED** — `63c189f031795d35` twice |
| P2 | N1 = 35 ≥ 20, split 6/10/19, proofs in ledger | **CONFIRMED** |
| P3 | N2 = 8 ≥ 1 with countermodels archived | **CONFIRMED** |
| P4 | zero axiom adoptions; negative test constructs the attempts | **CONFIRMED** |
| P5 | kernel audit checklist passes and is recorded | **CONFIRMED** — §1 |
| P6 | 3 abbreviations with exact deltas; codelen per theorem | **CONFIRMED** |
| P7 | N3 = 0 crossings (a crossing would be a MISS) | **CONFIRMED** — 0 |
| P8 | replay verifies in both finals | **CONFIRMED** |
| P9 | suite 258/0 in CI order; 15 test_an_ green; prior pins verify | **MISS on the literal count** — the L–O code froze in one commit, so the suite at finals time reports 270, not 258. The substance holds: 15 test_an_ guards green in isolation, 0 failures, prior pins verified. Scored as a miss, not reinterpreted |
| P10 | no post-registration changes; decidability scope note stands | **CONFIRMED** |

Score: 9 confirmed, 1 miss (P9, literal suite count — see the row).

## 5. Carried findings

- The prover's pool-restricted saturation is the binding constraint on
  this domain's frontier — deeper theorems need either a stronger prover
  (a Phase O Channel A candidate: the context-ordered prover) or the
  owner-gated amendment path to richer axiom bases. Registered, not
  patched.
- The theorem library's abbreviations fed back into the conjecture
  grammar as units, closing the interestingness loop the directive
  required: enumeration follows measured compression, not hand-written
  heuristics.
- Step-theorem adoption (every formula inside a kernel-checked proof is
  a theorem) is what makes the theorem economy grow at these budgets;
  the composition split keeps the accounting honest.

## 6. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode ascent-n-battery   # run 1
python3 rsi_levels_metaforge_unified.py --mode ascent-n-battery   # run 2
# expect: identical {"an_digest": "63c189f031795d35", ...} and byte-identical
# reports/evidence/ascent_n_results.json + ascent_n_ledger.jsonl
python3 rsi_levels_metaforge_unified.py --mode test --only test_an_   # 15 guards
python3 rsi_levels_metaforge_unified.py --mode ascent-n           # CI-safe demo
```
