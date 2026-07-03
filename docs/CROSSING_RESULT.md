# Phase J5 — Crossing Result

**Outcome against the registered threshold, stated plainly: the threshold
(>= 1 of T29–T32 gate-adopted and instrument-verified in the extended ISA)
is exceeded — two of the four certified walls crossed.** The crossing arm
solves **28/33 designer tasks** (adoption digest `1b36ff714b128546`), gaining
**T29 `count_above_threshold`** (wave 1) and **T30 `argmax_index`** (wave 2)
over the incumbent's 26/33, with **zero regressions**, both runs
byte-identical (artifact SHA-256
`fb2efb864a28b399bdb874ffb963531813ce26071e5bd3454b9a1734761312bb`, committed
as `docs/final_live_phaseJ.json`). Both adopted wall programs pass the sealed
Phase 0 holdout and counterfactual gates and all 70/70 pairs of the frozen
extended-ISA instrument (`docs/frozen_holdout_extJ.json`,
SHA `e28ba073…f4ed`, frozen before any Phase J5 search). T31 and T32 remain
OPEN, exactly as predicted — honest nulls with quantified bands. Each crossed
task's committed base-ISA impossibility certificate and its adopted
extended-ISA solution now sit side by side in this repository, which is this
project's operational definition of a qualitative transition.

## 1. Protocol (as pre-registered in docs/PREDICTIONS_J.md)

Two arms, identical budgets and seeds (WAVES=8, RESTARTS_PER_TASK=6,
ITERS_PER_RESTART=550, SPECULATION_BUDGET_PER_WAVE=2,
EXPLORATION_BATCHES_PER_WAVE=14; SEED=2026, DATA_SEED=11, GATE_SEED=2027,
CF_GATE_SEED=4099), each run twice:

- **Arm A (incumbent):** `--mode transfer-anchor` — the Phase I live
  configuration, unchanged.
- **Arm B (candidate):** `--mode crossing-anchor` — identical configuration
  plus the capability-grant channel of the approved frozen spec
  (docs/ISA_EXTENSION_SPEC.md, SHA `4820db39…76476c`).

Runtimes on this hardware: arm A ≈ 75 min/run; arm B ≈ 120 min/run (the
post-grant vocabulary enlarges every enumeration). All four runs completed;
no sampling, no truncation.

## 2. Arm results

| arm | run | designer solved | adoption digest | artifact SHA-256 |
|---|---|---|---|---|
| A (incumbent) | 1 | 26/33 | `e2c2893448da4cdf` | `1cffe630…63b95a` |
| A (incumbent) | 2 | 26/33 | `e2c2893448da4cdf` | `1cffe630…63b95a` (byte-identical) |
| B (crossing)  | 1 | **28/33** | `1b36ff714b128546` | `fb2efb86…312bb` |
| B (crossing)  | 2 | **28/33** | `1b36ff714b128546` | `fb2efb86…312bb` (byte-identical) |

The arm A artifact is byte-identical to the **committed Phase I artifact**
`docs/final_live_phaseI.json` — same SHA-256 — i.e., with the channel off,
the Phase J runtime reproduces the committed historical record byte for
byte. Delta = +2 designer tasks (T29, T30), none lost:
`gained = [T29, T30]`, `lost = []`.

## 3. The crossings, with full lineage

**Grant adoption (wave 0).** The mechanical, oracle-free request locator
fired from the arm's own wave-0 residues; the grant bundle {BCAST(60),
ZGT(61)} rode `speculative_meta_gate` as one candidate. The macro-closure
screen rejected it (gained 0 — the screen vocabulary carries no extended
ops); the exact bundle table accepted it (`inc 0 -> cand 1`: one previously
unsolved designer task newly passed both sealed gates at identical budgets).
Speculation ledger: wave 0, `capability_grant`, accepted, clean pre/post
hash protocol.

**T29 `count_above_threshold` — wave 1, searcher v4, expanded length 6:**

```
INPUT INPUT PUSH3 BCAST ZGT RED_ADD        tokens (4, 4, 3, 60, 61, 29)
```

count = RED_ADD(ZGT(xs, BCAST(3, xs))). This is precisely the program the
extended-ISA re-certification pinned as reachable at length 6 (and the
committed measurement found before any search). Adopted through the ordinary
run_wave sequence: train re-verify, sealed holdout, counterfactual gate.
Instruments: Phase 0 holdout PASS, cf PASS; extJ 40/40 holdout, 30/30 cf.

**T30 `argmax_index` — wave 2, searcher v8, surface 5 / expanded 9:**

```
M107 SCAN_MAX M107 ZGT RED_ADD             tokens (107, 27, 107, 61, 29)
M107 = INPUT SCAN_MAX REVL                 origin: exploration (Phase G archive)
expanded: INPUT SCAN_MAX REVL SCAN_MAX INPUT SCAN_MAX REVL ZGT RED_ADD
```

Semantics: `SCAN_MAX(REVL(SCAN_MAX(xs)))` is the constant list
`(max(xs),) * n` — the reversed prefix-max begins at the global maximum, so
its running maximum is constant. `ZGT` of that constant-max list against the
reversed prefix-max marks the positions where the prefix maximum had not yet
reached the global maximum; `RED_ADD` counts them: the first argmax index.
Two facts make this the deepest finding of the phase: (a) the program uses
**ZGT only** — the system replaced the designer witness's BCAST comparand
with an input-derived constant-max construction the base closure always
contained; (b) **M107 is an exploration-origin macro** offered from the
frozen Phase G Track 2 archive through the Phase I stratified schedule and
installed at wave 1 by the ordinary meta-gate — the crossing composed a
designer-granted primitive with archive-transferred vocabulary, neither of
which sufficed alone (T30 is certified unreachable at <= 6 in the flat
extended vocabulary; the macro compressed the 9-token program to surface 5,
inside the enumeration horizon). Instruments: Phase 0 holdout PASS, cf PASS;
extJ 40/40, 30/30.

## 4. Certificate/solution pairs (the qualitative-transition record)

| task | committed base-ISA certificate | adopted extended-ISA solution |
|---|---|---|
| T29 | no base program of expanded length <= 7 computes the train vector (exact, untruncated; length 8 swept; `test_deep_scan_artifact_certifies_walls`, `test_closure_certificates_walls_blocked_le6`); the elementwise constant-comparand route impossible at any depth (executed constructor lemma) | expanded length 6, adopted wave 1, dual-gated + both instruments (`docs/final_live_phaseJ.json`) |
| T30 | same exact base-ISA certificates (unreachable <= 7/8); extended-ISA flat vocabulary certificate: unreachable <= 6 even with both grants (test-pinned) | surface 5 via mined macro M107, expanded 9, adopted wave 2, dual-gated + both instruments |
| T31 | unreachable <= 7/8 (base), <= 6 (extended, pinned) | none — OPEN; designer witness bounds expressibility at 18 |
| T32 | unreachable <= 7/8 (base), <= 6 (extended, pinned) | none — OPEN; designer witness bounds expressibility at 20 |

## 5. Prediction scoring (register: docs/PREDICTIONS_J.md)

| # | prediction | verdict |
|---|---|---|
| P1 | Arm A reproduces 26/33, digest `e2c2893448da4cdf`, twice byte-identical | **CONFIRMED — exceeded**: artifact byte-identical to the committed `final_live_phaseI.json` itself |
| P2 | Grant offered and gate-adopted at wave 0, gained exactly one task | **CONFIRMED** (screen reject, bundle-table accept `0 -> 1`, clean ledger) |
| P3 | T29 adopted wave 1-2, length 6, both primitives, both instruments | **CONFIRMED exactly** (wave 1, length 6, BCAST+ZGT, 70/70 + sealed gates) |
| P4 | T30 remains OPEN | **MISS — positive surprise**: adopted wave 2 via exploration-origin macro compression; full lineage above, as the register promised for this contingency |
| P5 | T31, T32 remain OPEN | **CONFIRMED** (honest nulls with quantified bands) |
| P6 | No incumbent regression | **CONFIRMED** (28 = 26 + 2; `lost = []`) |
| P7 | All runs byte-identical | **CONFIRMED** (both arms, both runs) |

Score: 6 confirmed, 1 miss — the miss being in the conservative direction
(a predicted null turned into a verified crossing).

## 6. Carried findings and boundaries

- The requirement-(ii) archive-MDL null from Phase J2 stands as a primary
  finding (docs/ISA_EXTENSION_SPEC.md §3): the old archive, living strictly
  inside the old closure, could not certify these primitives' generality by
  compression; generality was instead demonstrated by breadth (two generic
  ops, two walls crossed by different compositions, one witness per
  remaining wall) — recorded, not claimed beyond that.
- T31/T32 remain certified-blocked at <= 6 in the extended ISA with witness
  bands at 18/20; crossing them at these budgets was predicted infeasible
  and measured so.
- The walls-stay-open and cached-run-fact pins were never tripped: the
  default configuration is grant-free by construction and reproduces the
  committed record byte-identically (arm A). No test was modified; no pin
  amendment was needed (the R2 protocol declared in the spec §6 was not
  exercised).
- Full Evidence CI reproduced the complete battery + 156-test suite green
  on a clean runner at the merge commit containing this machinery.

## 7. Reproduction

```
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save armA_run1.json
python3 rsi_levels_metaforge_unified.py --mode transfer-anchor --save armA_run2.json
python3 rsi_levels_metaforge_unified.py --mode crossing-anchor --save armB_run1.json
python3 rsi_levels_metaforge_unified.py --mode crossing-anchor --save armB_run2.json
# expected: armA byte-identical to docs/final_live_phaseI.json;
#           armB byte-identical to docs/final_live_phaseJ.json;
# replay verification: extj_instrument_verify(fn, tid) over the frozen
#           docs/frozen_holdout_extJ.json for T29/T30.
```
