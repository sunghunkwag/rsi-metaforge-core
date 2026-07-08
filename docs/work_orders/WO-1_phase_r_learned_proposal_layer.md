# WO-1 — PHASE R: THE LEARNED PROPOSAL LAYER (Stage 3)

**Issued by:** `OUTER_LOOP_CONSTITUTION.md`, Article VI (the constitution's first work order, written in full because it precedes the meta-loop's first automated draft).
**Drafted/transcribed by:** worker session, branch `claude/outer-loop-constitution-otgms4`, from Article VI verbatim, with ground-truth anchors verified against commit `98ff67f`.
**Format:** Article IV binding template, sections (1)–(10) in order.
**Preconditions (both hard):**
1. Amendment A1 is Owner-enacted in `docs/amendments/A1_learned_proposal_layer.md` (Article I.5) **before any Phase R code lands**. The committed A1 file in this repository is a session-drafted proposal and is NOT enacted until the Owner personally fills its enactment block.
2. The approval token line in section (10) is filled by the Owner (Article II.4). Absence of the token = the executing worker stops and reports.

---

## (1) Mission

Attack the wall Phase P certified: the inner loop saturates because its proposer has no prior — the setter cannot imagine extension-shaped tasks, and the solver's enumeration cannot reach deep programs. Install a learned prior as an **untrusted proposal engine** under the existing verification discipline, and measure — against pre-registered criteria, at frozen instrument budgets — whether certified capability moves. The claim, either way, is the certificate.

## (2) Ground truth (verify in code, not prose)

Read these first; verify every claim against code, not prose. Line anchors are as of commit `98ff67f` and will drift — symbols are authoritative.

| Item | Where (at `98ff67f`) | What to verify |
|---|---|---|
| RE-SATURATION structure | `docs/P_RESULT.md` (headline :7; trajectory table :23-24; ladder :33-35) | coupling cum-crossed `[0,3,3,3,3,3,3]` = frozen 3 at every rung `b_live ∈ {9000, 15000, 25000}`, `b_eval` frozen at 4000, `ext_admitted_total` = 0, 9/9 predictions hit |
| `ak_run_tokens` (frozen, base-only) | `rsi_levels_metaforge_unified.py:42077`; guard :42087-42088 | raises `VMCrash("ak_non_base_token")` on any non-base token; never modified by this WO |
| `ak_run_tokens_ext` (P3 extended executor) | `rsi_levels_metaforge_unified.py:47824` | dispatches admitted extension ids through the frozen K9 catalog view; base-ISA path byte-equivalent to `ak_run_tokens` |
| K8 extension-admission gate | `ap_extension_gate` (P2); `docs/ASCENT_P_SPEC.md:37-44` | feasibility on sealed hidden seeds + frontier-fails-at-current-ISA + null battery + novelty; byte-exact ISA rollback-on-reject |
| K9 catalog | `DORMANT_CAPABILITY_CATALOG`, `rsi_levels_metaforge_unified.py:6010`; pin `ASCP_CATALOG_SHA256` | frozen, hash-pinned; the loop selects from it, never edits it |
| K10 closure-generation ledger | `APLoopState` (`self.k10 = SCLedger()`, :48299); `ap_metrics_from_ledger` :48408 | append-only, hash-chained, replay-verifying; setter-side proposals flow **through** this machinery, never around it |
| Witness vault + AST-leakage audits | `AKWitnessVault`, `rsi_levels_metaforge_unified.py:42030` (K1) | write-once, memory-only, sealed at emission; mutable code AST-audited against vault references |
| M5 amortizer (incumbent proposal-ordering baseline) | Phase M banner :44692 "LEDGER-TRAINED AMORTIZER (ASCENT M5)"; `docs/M_RESULT.md` | v0 bigram / v1 fixed-point MLP, trained on the system's own ledger only; certified 3× passes-per-budget uplift; this is Arm OFF's ordering |
| Budget meter | `AKBudgetMeter`, `rsi_levels_metaforge_unified.py:42056` (K4) | the only counter of logical cost; `b_eval` is a frozen config budget (`ASCP_B_EVAL = 4000` in P) |
| Determinism regime actually registered in-repo | `docs/ASCENT_K_SPEC.md:118-121, :285-287` | dual-RUN byte-identity (battery run twice, digests + artifacts `cmp`-equal). **Correction to Article VI.0's citation:** no record/replay regime for "recorded external inputs" is registered anywhere in this repository (repo-wide grep at `98ff67f`: zero hits for record/replay, recorded external inputs, declared nondeterminism). The "K–O constitution §2.2" cited by VI.0 is an Owner-held document outside this repo. Phase R must therefore **register** the record/replay-from-committed-ledger regime in its own spec-freeze (`docs/ASCENT_R_SPEC.md`) — see (4) — rather than cite it as pre-existing. |
| Suite pin | `.github/workflows/full-evidence.yml:225` | the enforced pin is exactly `RESULT: 286 passed, 0 failed`. **Correction to Article VI.6's "318+":** the source contains 318 `def test_` definitions, but the collected suite passes 286; the archived integration sections are not collected. The mechanical gate in this WO uses the enforced pin, not the raw definition count. |
| Known stale doc pins (pre-existing) | `EVIDENCE.md:181` and the :185 count history stop at 270; `README.md:110, :149` say 270 | stale versus the certified 286 (`EVIDENCE.md:25`, `full-evidence.yml:225`, `docs/P_RESULT.md:68-70`). Correcting these to the certified value is in-scope for this WO's EVIDENCE/README updates. |
| House prediction-register form | `docs/PREDICTIONS_P.md` (exemplar) | frozen-protocol header; singular registered question with both outcomes pre-declared wins; expected-shape statement with reasoning; numeric criteria section; numbered predictions; calibration disclosure |

## (3) Binding constraints (inlined; the executing worker must not need to hunt)

From `OUTER_LOOP_CONSTITUTION.md` Article I (kernel, immutable):
- **I.1** — No execution without the Owner approval token in (10). No session self-approves or simulates approval.
- **I.2** — No autonomous acquisition of compute, credentials, funds, accounts, or network reach. Inner-repo runtime remains offline: no network I/O at run time. Model weights are fetched once by the Owner, outside any session.
- **I.3** — All binding state lands in the repository. Anything decided only in chat is extracted to the repo before the session ends or it is lost by design.
- **I.4** — K1–K10, sealed gates, witness vault, frozen instruments, hash-chained ledger + replay, budget meter, MDL formula, proof kernel + axiom base, `DORMANT_CAPABILITY_CATALOG`, and `ak_run_tokens` remain frozen exactly as their constitutions state.
- **I.6** — Merge admission is exclusively: full test suite green, `quick-ci` + `full-evidence` green, byte-reproducibility obligations met, acceptance gates in (7) met. A red gate outranks everything.

From the inner constitutions (in-repo canonical form):
- `docs/ASCENT_P_SPEC.md:32-54` — K8/K9/K10 definitions quoted in (2); "Catalog membership is an owner-pre-registered constitution amendment, never self-granted."
- `docs/ASCENT_K_SPEC.md:40, :87-89` — witnesses sealed into the vault (K1) at emission, before any admission check runs; unreadable from mutable code (AST-audited).
- `docs/05_limitations.md:47-51` — the stdlib-only and no-LLM/embedding/model-API constraints (test-enforced), amendable **only** through enacted A1, and only for the designated proposal layer.

From Amendment A1 (must be enacted before code lands; scope is exactly this):
- Only the designated PROPOSAL LAYER, implemented in new SECTIONs outside every kernel item, may invoke one local open-weight language model. The frozen kernel (K1–K10), all gate evaluators, verification, replay, metering, and instrument code remain pure-stdlib and never invoke, import, or read the model. Model outputs enter the system exclusively as recorded external inputs in the R-ledger. Everything the model proposes lives or dies at the unchanged hermetic gates.

Claim discipline (Article 0, binding on every artifact): no claims of AGI, singularity, unbounded capability, or intelligence explosion — anywhere, ever. Every prediction pre-registered before finals; misses scored, not reinterpreted.

## (4) Deliverables

1. **`docs/ASCENT_R_SPEC.md`** — the frozen spec (house form of `docs/ASCENT_P_SPEC.md`), containing at minimum: architecture R-A/R-B/R-C below; model requirements from VI.3 (weights SHA-256-pinned; license recorded; inference params per arm; offline runtime); **registration of the record/replay determinism regime** — declared nondeterminism: live inference may vary across hardware; the registered evidence arm is REPLAY; every prompt and completion written to `docs/ascent_r_proposals.jsonl` with `(model_sha, prompt_sha, params, completion)`; finals are dual replays from the committed ledger, byte-identical; verification consumes only ledger contents.
2. **New SECTIONs** appended after Phase P (house convention: banner `# PHASE R: <TITLE> (ASCENT M7)` following `# PHASE P: ... (ASCENT M6)` at :47680), containing:
   - **R-A: Solver-side proposer.** Per generation, conditions on PUBLIC task data (public instances, checker source) + ledger-adopted artifacts (solutions, macros, lineage) and emits ≤ `n_prop` candidate programs (fixed per registration, identical across arms). Candidates enter the same sealed evaluation path as enumerated candidates — same `b_eval`, same hidden seeds, same gates. Sampling never sees hidden instances, witnesses, or holdouts.
   - **R-B: Setter-side proposer.** Drafts `(task_spec, checker, witness)` triples — including extension-shaped ones whose witnesses use catalog ops — submitted through the P coupling machinery: witness sealed at emission, K-admission gates unchanged, K8 judging any resulting extension request. **Triple anti-self-reference guard (mandatory):** (1) *state separation* — the K8/admission judge reads no proposer state; proposer code AST-audited to reference no vault/K8/K9 symbols; (2) *holdout cross-proof* — an extension admitted off a proposer-authored marker must additionally cross ≥ 1 task from a kernel-seeded holdout family the proposer never conditioned on; (3) *impossibility pre-certificate* — base-ISA failure on the target family certified before admission (the O/P protocol, unchanged). A proposer that manufactures tasks to justify its own preferred extension dies at guard (2).
   - **R-C: Provenance & accounting.** Every proposal carries provenance (`model_sha, prompt_sha, params_sha, gen`); a K10-style R-ledger records per generation: proposals emitted, gate-certified adoptions, extension requests/admissions, conversion rate. Logical budget (`b_eval`, VM steps) stays the kernel meter; model inference cost recorded as wall-clock + token counts but never enters gate comparisons.
3. **`docs/ascent_r_proposals.jsonl`** — the committed prompt/completion ledger (the replay source).
4. **`docs/PREDICTIONS_R.md`** — house register form, committed before finals; see (6).
5. **`docs/R_RESULT.md`** — every prediction scored, misses included.
6. **R-ledgers + pins committed** — final ledgers, `ASCR_PIN_SHA256`-style source pin per house convention, model weights SHA-256 recorded in the spec.
7. **CI:** R red-team guards + demo added to `quick-ci` (house pattern: `--mode test --only test_ar_` + `--mode ascent-r`); `ascent-r-battery` added to `full-evidence` run twice with digest + artifact `cmp` equality asserted; the full-suite pin at `full-evidence.yml:225` moved from 286 to the exact new count; `EVIDENCE.md` count history extended (and the stale 270 pins at `EVIDENCE.md:181/:185` and `README.md:110/:149` corrected to certified values).

## (5) Tests-first list (minimum set; write before implementation)

- `test_ar_kernel_never_imports_model` — AST audit: no kernel/gate/replay SECTION references the model client.
- `test_ar_proposer_sees_public_only` — prompt-assembly audit: hidden seeds/witnesses/holdouts unreachable.
- `test_ar_replay_needs_no_model` — finals replay with the model absent from the machine.
- `test_ar_dual_replay_byte_identical` — two replays from the committed ledger produce byte-identical finals.
- `test_ar_guard_state_separation`, `test_ar_guard_holdout_crossproof`, `test_ar_guard_impossibility_precert` — each guard demonstrably rejects a planted self-referential candidate.
- `test_ar_catalog_and_kernels_pinned` — K9 hash, `ak_run_tokens` untouched, prior pins intact.
- `test_ar_arms_equal_budgets` — identical `b_eval` and `n_prop` across arms.
- `test_ar_prior_suite_green` — the pre-R suite still passes in full: the enforced pin (`RESULT: 286 passed, 0 failed` at the pre-R commit) holds, and the post-R pin equals 286 + the exact number of new `test_ar_*` tests, pinned exactly per house convention (`EVIDENCE.md:185`: "The count is pinned exactly on purpose").

## (6) Pre-registered predictions

**Arms.** **OFF** — incumbent (enumeration + M5 amortizer ordering), the frozen baseline. **ON-A** — solver proposer only. **ON-AB** — solver + setter proposers. All arms: identical seeds, identical `b_eval`, identical generation count; ladder ≥ 3 `b_total` rungs.

**Decisive readouts (register numeric criteria for each in `PREDICTIONS_R.md` before finals):**
1. Certified cum-crossed trajectory per arm — does ON cross tasks OFF fails, at every rung.
2. `ext_admitted_total` under ON-AB with all three guards up — does the P null (0 admissions) break **honestly**.
3. Proposal→certification conversion rate.

The predicted shape must be written before finals, in the house register form (`docs/PREDICTIONS_P.md` is the exemplar: singular question, both outcomes pre-declared wins, expected-shape statement with reasoning, numeric criteria never reinterpreted, calibration disclosure). A null (prior doesn't move certified capability, or guards reject everything) is a pre-declared win and is reported as such. Budgets, seeds, `n_prop`, thresholds, and prompts for registered arms are frozen at pre-registration.

## (7) Acceptance gates (mechanical, checkable)

1. Amendment A1 carries the Owner's enactment block, committed before any Phase R code commit (verify by commit order in `git log`).
2. Commit order within the phase: spec → tests → implementation → `PREDICTIONS_R.md` → finals → `R_RESULT.md`.
3. Finals: dual replays from `docs/ascent_r_proposals.jsonl`, byte-identical (digest equality + `cmp`-equal artifacts), with the model absent.
4. All tests in (5) present and green; full suite green at the new exact pin.
5. `quick-ci` and `full-evidence` green with the R batteries added; no existing workflow step weakened or removed.
6. R-ledgers and SHA pins (source pin, model weights SHA, catalog pin unchanged) committed.
7. Every prediction in `PREDICTIONS_R.md` scored in `R_RESULT.md`, misses included.
8. Article I intact — no diff touches K1–K10 symbols, `ak_run_tokens`, the catalog, frozen instruments, prior pins, or prior committed evidence.

## (8) Prohibitions

- No model invocation from kernel/gate/verification/replay code paths; no unpinned weights; no online inference at runtime; no training data beyond the base model's own weights plus this repository's ledger.
- No touching K1–K10, `ak_run_tokens`, `DORMANT_CAPABILITY_CATALOG`, frozen instruments, pins, or prior committed evidence.
- No result tuning: a REVIVE or capability jump that required post-hoc tuning of budgets, seeds, `n_prop`, thresholds, or prompts is a planted result and is discarded.
- No claim language beyond certificates; no deleting limitations — convert them to Target-Property + Criterion form (`docs/05_limitations.md` house form).
- No merging on red. No reading sibling branches. On any conflict with Article I or an inner constitution: stop, report, await the Owner.

**What this work order does NOT attempt (Article II.3f):** no verifier manufacture (that is WO-S1, locked until this WO's DoD merges); no external-world coupling (WO-S2); no meta-directive changes (WO-S3); no catalog membership changes; no new axioms; no kernel refactors "while we're in there"; no fine-tuning or training of the local model.

## (9) Definition of Done

Amendment A1 enacted by Owner before code; spec → tests → implementation → `PREDICTIONS_R.md` → finals (dual replay, byte-identical) → `R_RESULT.md` scoring every prediction, misses included; R-ledgers committed with SHA pins; CI green with R batteries added to full-evidence; suite green at the exact new pin; Article I intact. **DoD is the certified answer, not a positive answer:** either the prior moves certified capability (state exactly how much, where, at what conversion rate) or it does not (state exactly where proposals died). Both are deliverables.

## (10) Approval token

APPROVED:
