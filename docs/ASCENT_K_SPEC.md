# Ascent Phase K — Witness-Sealed Setter–Solver — Frozen Specification (K-1)

Spec-freeze document for the Ascent directive, Phase K (module M1). Every
constant, seed, budget, threshold, grammar set, and protocol rule below is
frozen at commit time, BEFORE the first `--mode ascent-k-battery` evidence
run. Post-hoc changes require a new predictions file; this one stays
committed. Predictions: `docs/PREDICTIONS_K.md`; results: `docs/K_RESULT.md`.
The SC-1 (`docs/SELF_CURRICULUM_SPEC.md`) and SC2-1
(`docs/SELF_CURRICULUM_SPEC_V2.md`) records are unchanged and their code is
read-only under this phase; Phase K supersedes the SC/SC2 line going
forward. The delta versus SC2 is exactly three certificates — sealed-witness
feasibility (Ka), frozen-frontier difficulty (Kb), and the learnability-band
reward — plus the checker-as-program task form, the witness vault, the
logical budget meter, and the task archive they require.

## 1. Mission and claim boundary

The system manufactures its own tasks as verifiable triples
`(task_spec, checker, witness)`, admits a task only when four hermetic
certificates pass on hidden evaluation instances, mines solutions under
sealed evaluation, and measures *crossings*: a task the admission-time
frontier provably failed at the frozen instrument budget is later solved by
an improved solver snapshot at the SAME budget, where the improvement is
attributable only to library growth from OTHER tasks (own-solution macros
are excluded from a task's crossing measurement). The deliverable is the
measured crossing curve and the per-lineage credit trajectory, not an
open-endedness claim. A flat or zero curve ships as-is.

The objective function, from the directive: maximize certified gate passes
per unit of logical budget, measured on frozen instruments. Capability here
IS gate passage; nothing below weakens, parametrizes, or bypasses a gate
from mutable code.

## 2. Components and the kernel/mutable split

Frozen kernel (never modifiable by synthesized or mutable code):

| Kernel piece | Implementation | Role |
| --- | --- | --- |
| K1 witness vault | `AKWitnessVault` (write-once, memory-only) | seals witnesses at emission; unreadable from mutable code (AST-audited) |
| K1 sealed instances | `AKWitnessVault` (same store, `hidden:` keys) | hidden evaluation instances per task |
| K3 ledger + replay | `SCLedger` instance + `ak_replay_verify` | append-only hash chain; replay re-derives every admission certificate |
| K4 budget meter | `AKBudgetMeter` | the only counter of logical cost (VM steps + candidate evaluations), per module |
| gate evaluators | `ak_run_checker`, `ak_gate_score`, `ak_admit`, `ak_frontier_solve`, `ak_crossing_check` | the four admission certificates and the sealed solve gate |

Mutable citizens (inside the system's own modification scope, and the
jurisdiction of later phases):

| Citizen | Implementation | Sees |
| --- | --- | --- |
| setter lineages | `AKSetterLineage` (L_A, L_B, L_D policies) | frozen units, adopted archive bodies, its own credit statistics |
| allocation policy | `ak_allocate_slots` | per-lineage credit totals only |
| miner (solver) | `ak_solve` (= `sc_solve` discipline) | canonicalized public pairs, adopted macro bodies, its budget |

Setter and solver share exactly one channel: the adopted archive
(`{"aid", "tokens"}` entries). The vault is unreadable from every mutable
citizen — enforced by `test_ak_vault_unreadable_from_mutable_code`, an AST
audit asserting no mutable component's source references any vault symbol.

The adversarial probe lineage (`AK_ADV_PROBES`, frozen data, not a citizen)
emits four pre-registered broken/trivial triples per generation so that
every admission gate demonstrably fires in the final logs. ADV probes are
credit-ineligible; an ADV probe being ADMITTED aborts the battery
(`ak_adv_canary`).

## 3. Task form

Substrate: the stack VM base ISA (`OP_IMPL`), Track A (scalar inverse) and
Track B (list pipeline) exactly as SC-1 froze them (`SC_STEPS_A`,
`SC_UNITS_B`, domains, probe batteries). Granted EXT ops stay invisible.

A setter emission is a triple:

- `task_spec`: `{"track", "g"}` — a generator program in the current ISA.
  Instances derive from the sealed seed stream: the per-task input PRNG is
  `random.Random(int(cid[:16], 16) ^ ASCK_MASTER_SEED)` with
  `cid = sha256(canon([track, g_expanded]))` — the setter cannot influence
  which instances appear beyond choosing `g` (the SC-1 I9 discipline; the
  sampler-reconstructibility boundary is inherited and disclosed in §9).
- `checker`: a deterministic, sandboxed, budget-capped VM program. Checker
  calling convention (frozen): the stack is pre-seeded with the candidate
  output `y`; `INPUT` pushes the task instance input `x`; the program must
  terminate with the single int `1` (accept) — any other terminal, any
  crash, or exceeding `ASCK_B_CHECK` executed ops is a reject. The checker
  is gate-side: the miner never reads checker tokens (hidden-expectation
  discipline; the solver-visible task surface is the public pairs only).
- `witness`: a program the setter claims solves the task. Sealed into the
  vault (K1) at emission, before any admission check runs. Track A
  witnesses are inverse chains; Track B witnesses are the generator itself.

Task instances: `m = ASCK_N_PUBLIC + ASCK_N_HIDDEN` distinct inputs drawn
from the task PRNG. The first `ASCK_N_PUBLIC` (canonically sorted) become
public pairs, labeled by witness replay inside the kernel; the remaining
`ASCK_N_HIDDEN` are sealed as hidden evaluation instances. Track A instance
inputs are image points `(G(v),)` for domain-sampled `v`; the checker
accepts any preimage (checker semantics, not label equality, is ground
truth on the hidden side).

## 4. Admission certificates (frozen order: K0, Ka, Kc, Kd, Kb)

Every candidate triple is dispositioned in the ledger with one of:

- `k0_malformed` — structural validation: token ranges, generator/checker/
  witness length caps, Track A witness presence.
- `ka_feasibility` — **(a) feasibility certificate**: the sealed witness,
  replayed from the vault, must satisfy the checker on ALL `ASCK_N_HIDDEN`
  hidden instances, every call within `ASCK_B_CHECK` ops and the whole
  certificate within `ASCK_B_EXEC` total ops. Fires on wrong witnesses,
  crashing witnesses, and budget overruns.
- `kc_null_battery` / `kc_null_sampler` / `kc_nondeterministic` — **(c)
  non-triviality certificate**. Strategy semantics (pre-registered): a
  strategy *solves* the task iff the checker accepts its output on EVERY
  hidden instance; a task is non-trivial iff (i) NONE of the five fixed
  null strategies solves it — identity, constant-0, empty output, input
  echo, reversed input — and (ii) at least `ASCK_P_NULL` = 9/10 of the
  `ASCK_NULL_PROGRAMS` seeded random programs (drawn from the task PRNG
  stream over the frozen solver vocabulary) do NOT solve it, with
  crash-on-all-instances programs excluded from the denominator and a
  vacuous pass (empty denominator) ledgered as such. (iii) The full checker
  battery is executed twice and must be bit-identical (checker determinism,
  dual-run verified).
- `kd_duplicate` / `kd_cell_occupied` — **(d) novelty certificate**: exact
  behavioral-signature dedup (sha256 of canonical generator outputs on the
  frozen SC probe battery) against every signature ever seen, then the
  task descriptor cell (§5) must be unoccupied among ADMITTED tasks.
  `d_min` is the Phase D/G archive admission threshold, i.e. cell
  distinctness: distance 0 = same cell = rejected.
- `kb_too_easy` — **(b) difficulty certificate**: the current frozen
  frontier-solver snapshot — `ak_solve` over base vocabulary plus ALL
  currently adopted macros, at exactly `ASCK_B_EVAL` candidate evaluations
  — must FAIL the task (fail = no candidate that fits the public pairs
  under the MDL cap and satisfies the checker on the hidden instances).
  The snapshot's macro ids and budget are recorded in the admission
  record.

Admitted tasks enter the task archive with their descriptor cell, lineage,
and admission generation. Witnesses stay sealed; the ledger carries
`witness_sha` only.

## 5. Task descriptor (novelty instrument)

`ak_task_descriptor(track, g_expanded)` — the Phase D descriptor recipe
applied to the task generator over the frozen SC probe battery
(`SC_PROBES_A` / `SC_PROBES_B`):

- halt bucket: `(8 * completed) // n_probes`
- entropy bucket: `min(4, (4 * distinct_outputs) // completed)` (0 when
  nothing completes)
- zero bucket / big bucket: `min(4, (4 * hits) // total_elements)` over
  all output scalar elements (zero: `== 0`; big: `abs > 15`)
- shape bucket: most common output length, capped at 8 (0 for Track A)
- order bit: 1 iff `G(reverse(x)) != G(x)` for some completed probe pair
  (Track B; 0 for Track A)
- cost bucket: `min(10, max(1, len(g_expanded).bit_length()))`
- track tag

The cell is this tuple; `explore_cell_key`-style string form in the
ledger. Cells are claimed by admitted tasks only; exact signatures are
claimed by every candidate ever checked (so re-proposals reject as
`kd_duplicate`, mirroring SC `seen_sigs`).

## 6. The loop: mining, crossing, credit, allocation

Per generation, in frozen order:

1. **Allocate**: `ak_allocate_slots` (mutable policy) splits
   `ASCK_POSE_SLOTS` = 6 among lineages: 1 base slot each, the remaining 3
   proportional to cumulative credit in exact integer arithmetic (floor of
   `bonus * credit / total_credit`, remainders to the largest remainder,
   ties to the lower lineage index; zero total credit → fixed order).
2. **Pose**: each lineage emits its slot count of triples at its current
   band (deterministic cursor enumeration, SC-1 style); ADV emits its four
   fixed probes. Witnesses are vaulted at emission.
3. **Admit**: certificates in §4 order; every disposition ledgered.
4. **Mine**: for each open task in admission order, `ak_solve` at
   `ASCK_B_LIVE` over base vocabulary + all adopted macros; a solution is
   adopted iff it fits the public pairs under the MDL cap
   (`SC_MDL_ALPHA` = 1/2, `SC_MDL_ABS_TOKENS` = 24 — the SC-1 caps,
   unchanged) AND satisfies the checker on every hidden instance. Adopted
   solutions become macros (`aid`, expanded tokens, source task, lineage).
   At most `ASCK_MAX_ATTEMPTS` = 2 mining attempts per task.
5. **Cross**: for each open task, `ak_crossing_check` runs the CURRENT
   frontier snapshot at exactly `ASCK_B_EVAL` — with every macro whose
   source task is THIS task excluded (no self-credit; the certificate
   measures library growth from other tasks) — and gate-scores the result.
   A pass is a `crossed` record carrying `{admitted_gen, crossed_gen,
   b_eval, snapshot_aids, solution_sha}`; the admission record already
   proves the admission-time snapshot failed at the same budget. Crossing
   solutions are adopted as macros too (they passed the same gate). The
   witness is revealed in the retirement record of a crossed task.
6. **Credit**: a lineage earns +1 when one of its admitted tasks crosses
   within `ASCK_H` = 5 generations of admission. Tasks uncrossed after
   `ASCK_H` generations become `frontier_marker` records: they stay
   archived (their cells stay claimed), their witnesses stay sealed
   forever (replay verifies `witness_sha` against the vault internally),
   and they earn nothing.
7. **Ratchet** (per lineage, pre-registered): if every proposal of the
   lineage this generation was rejected `kb_too_easy` → band + 1; else if
   any of its tasks crossed this generation → band + 1; else hold. Bands
   are capped at `ASCK_BAND_MAX`.
8. **Summarize**: `gen_summary` ledger record with band states, credit
   totals, allocation, archive size, open/marker counts, and the full
   budget-meter snapshot (the K4 raw signals: admission rate, crossing
   rate, passes-per-budget inputs).

## 7. Frozen constants

| Constant | Value | Meaning |
| --- | --- | --- |
| `ASCK_SPEC_VERSION` | "K-1" | |
| `ASCK_MASTER_SEED` | 872663 | task-instance seed root |
| `ASCK_GENERATIONS` | 8 | battery generations |
| `ASCK_N_PUBLIC` / `ASCK_N_HIDDEN` | 8 / 16 | instance split (m = 24) |
| `ASCK_P_NULL_NUM/DEN` | 9 / 10 | random-null rejection floor |
| `ASCK_NULL_PROGRAMS` | 24 | random-program null strategies per task |
| `ASCK_NULL_MAX_LEN` | 6 | random null program surface length |
| `ASCK_H` | 5 | learnability horizon (generations) |
| `ASCK_B_EVAL` | 1500 | frozen instrument budget (difficulty + crossing), candidate evaluations |
| `ASCK_B_LIVE` | 25000 | mining budget, candidate evaluations |
| `ASCK_B_CHECK` | 512 | per checker execution, VM ops |
| `ASCK_B_EXEC` | 4096 | per certificate total, VM ops |
| `ASCK_MAX_ATTEMPTS` | 2 | mining attempts per task |
| `ASCK_POSE_SLOTS` | 6 | non-ADV pose slots per generation |
| `ASCK_BAND_MAX` | 8 | lineage band cap |
| `ASCK_GEN_MAX_TOKENS` / `ASCK_CHK_MAX_TOKENS` / `ASCK_WIT_MAX_TOKENS` | 64 | expanded length caps (each also ≤ `SC_STEP_LIMIT`) |
| lineage bands at start | L_A 2, L_B 2, L_D 5 | deep-first L_D probes beyond the ladder |
| MDL caps | SC-1 values (α = 1/2, 24 tokens) | unchanged |
| `ASCK_MACRO_BASE` | 3000 | AK-local macro token ids (never leave AK) |
| `ASCK_PIN_SHA256` | `c9da2bbcb6a14da5acb5a3db1d2ef82e24c8735bc9e4d20131cbea5a2d594c42` | gate+harness source pin |

The pin input is the concatenated source of every kernel component plus the
canonical dump of every constant in this table (`_ak_frozen_constants_canon`
— seeds, budgets, caps, lineage starting bands, the ADV probe table, and
the null-battery definition), so seed-shopping or threshold drift flips the
pin and aborts the battery. The battery additionally asserts its
configuration against LITERAL spec values.

## 8. Metrics, digest, artifacts

- **K1 (headline)**: cumulative crossed-task count per generation — each
  crossing is a certified pass at frozen `B_eval` where the admission-time
  snapshot certifiably failed at the same budget.
- **K2**: cumulative adopted-macro count (mining + crossing adoptions).
- **K3**: per-gate rejection counts per generation (the four certificates
  each firing at least once across the final run is an acceptance
  criterion; the ADV lineage guarantees the floor honestly and is labeled
  as such in the ledger).
- **K4**: per-lineage credit and slot-allocation trajectory (the
  learnability-band reward made visible), plus the budget-meter snapshot
  per generation (certified passes per logical budget is computable from
  the ledger alone).
- **K5**: frontier-marker count (admitted, never crossed within H).

Battery digest: `sha256(ledger_head + canon(metrics))[:16]`, printed as
`ak_digest`. CI runs the battery twice and asserts equal digests and
byte-identical artifacts (`reports/evidence/ascent_k_results.json`,
`reports/evidence/ascent_k_ledger.jsonl`). `ak_replay_verify` re-derives
every admission certificate from the ledger before the digest is printed.
Final run-1 copies are committed as `docs/final_ascent_k.json` and
`docs/ascent_k_ledger_final.jsonl` with SHA-256 pins in `docs/K_RESULT.md`.

## 9. Scaled configurations (also frozen)

- `--mode ascent-k` (demo, CI-safe): generations = 3, pose_slots = 6,
  n_public = 6, n_hidden = 8, null_programs = 12, b_eval = 1500,
  b_live = 12000, H = 3.
- Test configuration (`_ak_test_cfg`): generations = 2, pose_slots = 6,
  n_public = 5, n_hidden = 6, null_programs = 8, b_eval = 1500,
  b_live = 9000, H = 2.

## 10. Isolation and anti-cheat battery (K7 extensions)

- Vault: write-once; unreadable from mutable citizens (AST audit test); no
  witness tokens in any ledger record before a crossed task's retirement;
  frontier markers never reveal witnesses.
- Self-credit: `test_ak_crossing_excludes_own_solution` constructs the
  attack — a task's own mined macro is asserted absent from its crossing
  snapshot.
- Namespace: `_ak_scan_components` is test-enforced to reference none of
  the sealed human-instrument symbols (the SC-1 I13 discipline); AK file
  I/O goes through `_sc_guarded_open` (writes confined to
  `reports/evidence/`, `frozen_holdout` paths blocked).
- ADV canary: an admitted ADV probe raises and aborts the battery.
- Determinism: two-run byte-identity is asserted in-suite on the test
  configuration and in CI on the full battery.
- Meter: mutable citizens are AST-audited not to reference meter internals;
  only kernel executors spend.
- Every anti-cheat test constructs its attack; none is a stub.

## 11. Known boundaries (disclosed at spec-freeze)

- **B_LIVE > B_EVAL is the exploration engine** (SC-1 disclosure
  inherited): mining runs at 25000 evaluations while every certificate
  (difficulty at admission, crossing later) is measured at the frozen 1500.
  The crossing claim is budget-clean by construction — both sides of the
  comparison run at the identical `ASCK_B_EVAL`; the miner only supplies
  library growth. The M1-style decomposition (crossings vs mining solves)
  is reported separately.
- **Sampler reconstructibility** (SC-1 §9 inherited): instance draws are a
  public function of the task id and the committed master seed. The v1
  setter is a fixed deterministic enumerator with no channel to exploit
  this; recorded as the standing hardening target for any learned setter
  (Phase M puts the amortizer behind its own sealed-holdout gate for this
  reason).
- **Track A compounding is structurally weak**: Track A macros embed the
  `INPUT HEAD` prefix and do not compose mid-program, so crossings are
  expected to concentrate in Track B (pipeline prefix composition). The
  per-track split is reported.
- **ADV probes share the behavioral-signature space** with real lineages;
  their four fixed behaviors are constant, pre-registered territory.
- **Checker generality is not exercised by the v1 setter**: v1 checkers
  verify `y == G(x)` (Track B) / `G(y) == x_img` (Track A) by
  recomputation. The checker calling convention supports relational tasks
  (any-preimage acceptance is already relational on Track A); richer
  checker families are a later-phase setter policy change, which after
  Phase O ships through Channel A like any other improver modification.
- **First-fit search asymmetry** (SC-1 I5 asymmetry inherited): `sc_solve`
  returns the first public-fitting candidate; a public-fitting candidate
  that fails the hidden checker gate ends that snapshot run. The asymmetry
  is identical on both sides of every crossing comparison (admission
  snapshot and crossing snapshot run the same code at the same budget), so
  the comparison stays fair.
- **Crossing supply is structurally pinched**: a task can cross only if it
  extends a band-3-scale prefix that is admitted and mined inside the
  horizon while the extension is already archived. The calibration run
  (§12) shows exactly one such window at the frozen budgets; the curve
  ships as measured, and the credit-vs-supplier gap it exposes (the
  crossing lineage is rewarded while the prefix-mining lineage is starved
  by the allocation policy) is recorded as a finding for the later phases,
  not smoothed over here.
- The file-world families are NOT packaged in Phase K (no frozen consumer;
  the no-dead-code rule from SC2 deviations applies).
- `ASCK_B_EVAL` = 1500 is the SC-1 entry rung; feasibility calibration is
  disclosed in §12.

## 12. Calibration disclosure

Budgets and starting bands were calibrated for loop liveness on prototype
runs before this freeze (the loop must have a reachable entry rung: at
`ASCK_B_EVAL` the frontier snapshot must fail band-start tasks that
`ASCK_B_LIVE` mining solves, and adopted macros must measurably enable
band+1 crossings at `ASCK_B_EVAL`). The calibration run of the loop portion
under exactly these constants was observed and is disclosed as
known-at-prediction-time in `docs/PREDICTIONS_K.md`. After this freeze, no
constant changes; the battery runs as-is and its curves ship as measured.
