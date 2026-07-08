# OUTER LOOP CONSTITUTION — Unified Directive, Stages 1–4

**Audience:** (a) the Owner; (b) Orchestrator sessions of Claude Code that draft work orders; (c) Worker sessions of Claude Code that execute them — all operating on and around `sunghunkwag/rsi-metaforge-core`.
**Status:** Binding constitution for the **outer loop** — the architect → proposer → verifier → ledger development cycle that surrounds the repository. The inner constitutions (`METAFORGE_ASCENT_DIRECTIVE.md` §2, `PHASE_P_COUPLING_DIRECTIVE.md` §2) remain in force **inside** the repository, unmodified except where Amendment A1 (Article VI) is explicitly enacted by the Owner.
**Precedence:** On any conflict, order is: Article I (Kernel) > this constitution > issued work orders > convenience. On conflict with Article I, every session STOPS and reports; no session improvises around the kernel.
**Language:** English throughout — code, identifiers, comments, docs, commits, work orders.

---

## ARTICLE 0 — PURPOSE, SCOPE, CLAIM DISCIPLINE

Measured fact, from the repository's own ledgers: the **inner loop** (the flywheel inside `rsi_levels_metaforge_unified.py`) saturates — cum-crossed 3 at every budget rung, with coupling ON, extensions admitted 0 (Phase P, byte-reproduced). The **outer loop** — Owner-architected directives, Claude-Code-executed phases, hermetic-gate-verified merges — produced six certified modules, +7,100 lines, +92 tests, in days. One of these two self-improvement systems is saturated; the other is accelerating. This constitution industrializes the accelerating one by removing its three measured constraints: **prior** (the proposer lacks learned knowledge → Stage 3), **openness** (the oracle supply is closed → Stage 4/S1), and **cycle rate** (the Owner hand-writes every directive → Stages 1–2).

**Claim discipline (binding on every artifact this loop produces):** No claims of AGI, singularity, unbounded capability, or intelligence explosion — anywhere, ever. The loop's claim is exactly its certified trajectory: gate-certified crossings, admitted verifiers, merged phases, scored predictions. Positive feedback is a quantity to be **measured on the outer-loop ledger (Article V)**, never a property to be asserted. Every prediction is pre-registered before finals; misses are scored, not reinterpreted. This clause exists because the loop's entire external value — audit credibility — dies the moment claim exceeds certificate.

---

## ARTICLE I — KERNEL OF THE OUTER LOOP (immutable)

These clauses are never modified, automated away, weakened, or "hooked for later relaxation" by any session, work order, or future amendment drafted inside the loop. Amending Article I requires the Owner writing the amendment personally, outside any automated session.

- **I.1 — Owner veto.** No work order executes without an explicit Owner approval token (Article II.4). No session self-approves, approves another session's order, or simulates approval. The veto is the one component of this loop that is never optimized, delegated, or measured for "efficiency."
- **I.2 — Resource clause.** The system and its sessions never acquire external compute, credentials, funds, accounts, or network reach autonomously. Resource inflows (grants, contracts, compute donations) pass exclusively through human decision gates — the Owner's. Inner-repo runtime remains offline (no network I/O), per the inner constitutions.
- **I.3 — State in repo; sessions disposable.** All binding state lives in the repository: directives, work orders, results, ledgers, pins. Chat context is never load-bearing. Any session may be killed at any time with zero loss; halting the loop is always safe.
- **I.4 — Inner kernels untouched.** K1–K10, the sealed gates, witness vault, frozen instruments, hash-chained ledger + replay, budget meter, MDL formula, proof kernel + axiom base, `DORMANT_CAPABILITY_CATALOG`, and `ak_run_tokens` remain frozen exactly as their constitutions state. The outer loop feeds the inner loop proposals and phases; it never reaches into the inner kernel.
- **I.5 — Amendment procedure.** Inner-constitution amendments (e.g., A1 in Article VI) are enacted only by an Owner-committed amendment record in `docs/amendments/`, pre-registered before any code lands under them. Sessions may draft amendment proposals; only the Owner enacts.
- **I.6 — Verification precedence.** Nothing merges on plausibility. Merge admission is exclusively: full test suite green, `quick-ci` + `full-evidence` green, byte-reproducibility obligations met, work-order acceptance gates met. A red gate outranks any deadline, any promising result, and any session's confidence.

---

## ARTICLE II — THE STANDING META-LOOP (Stage 1: the architect is automated; the Owner becomes a gate)

**II.1 — Roles.**
- **Owner:** approves/vetoes/amends work orders; enacts amendments; merges; holds I.1–I.2.
- **Orchestrator session:** reads ground truth (latest `*_RESULT.md`, this constitution, the outer-loop ledger) and drafts the next work order(s) as a PR. Drafts only; never executes, never approves.
- **Worker session:** executes exactly one issued work order in a fresh session, then terminates. Workers read their work order + the repo ground truth it points to — not the chat history of any other session.

**II.2 — Cycle.** `RESULT_n` → Orchestrator drafts `WO_{n+1}` (PR to `docs/work_orders/`) → Owner approves (token) / amends / vetoes → Worker executes in fresh session on a branch → gates + CI judge → Owner merges → `RESULT_{n+1}` → repeat. Target: the Owner's per-cycle labor converges to reading a draft and a result — minutes, not days.

**II.3 — Orchestrator drafting rules.** Every drafted work order must: (a) be self-contained per Article IV; (b) copy its binding constraints inline (workers must not need to hunt); (c) include pre-registered predictions with numeric criteria and an honest expected-shape statement; (d) target the highest-leverage open item per the latest RESULT and the Article V metrics; (e) never touch Article I or inner kernels; (f) state explicitly what it does NOT attempt. The orchestrator inherits the drafting style of `METAFORGE_ASCENT_DIRECTIVE.md` and `PHASE_P_COUPLING_DIRECTIVE.md` — those two documents are the canonical form.

**II.4 — Approval token.** A work order is "issued" only when the Owner commits an `APPROVED: <WO-id> <date>` line into the work-order file (or approves the PR with that comment verbatim). Workers verify the token exists before executing; absence = stop and report.

**II.5 — Fresh-session rule.** One work order, one worker session, zero carried context. Handoff is `RESULT` documents and commits only. Any decision that exists only in chat is extracted to the repo before the session ends or it is lost by design.

---

## ARTICLE III — PARALLEL EXECUTION PROTOCOL (Stage 2: proposer parallelism under one judge)

- **III.1 — Orthogonality.** The Orchestrator may draft concurrent work orders only for modules with disjoint code surfaces (disjoint SECTION ranges + disjoint doc files). Overlapping surfaces = sequential, never parallel.
- **III.2 — Isolation.** Each worker runs on its own branch (`wo/<id>-<slug>`), never reads sibling branches, and shares state only through merged `main`.
- **III.3 — Merge judge.** Admission to `main` is Article I.6, applied per branch: suite green, CI green, byte-reproducibility met, acceptance gates met, and — after any rebase onto a changed `main` — finals re-run. The gates are the judge; the Owner is the hand that merges what the judge admits.
- **III.4 — Concurrency cap.** ≤ 3 concurrent work orders until the outer-loop ledger shows ≥ 5 merged orders with 0 post-merge rollbacks; then the Orchestrator may propose raising the cap (Owner approves).
- **III.5 — Selection.** Competing approaches to the same target are permitted as explicitly-marked rival work orders; the gates pick the survivor on identical frozen instruments at identical `b_eval`; the loser's branch is archived, not deleted (negative results are assets in this repository).

---

## ARTICLE IV — WORK ORDER FORMAT (binding template)

Every work order (`docs/work_orders/WO-<n>_<slug>.md`) contains, in order: **(1) Mission** — one paragraph, capability-first, claim-disciplined. **(2) Ground truth** — exact files/symbols to read first, with the instruction to verify claims against code, not prose. **(3) Binding constraints** — inlined copies of the applicable kernel clauses and inner-constitution items. **(4) Deliverables** — SECTIONs, docs, ledgers, pins. **(5) Tests-first list** — named tests including anti-cheat extensions. **(6) Pre-registered predictions** — numeric, shape-stated, committed before finals. **(7) Acceptance gates** — mechanical, checkable. **(8) Prohibitions.** **(9) Definition of Done** — including dual byte-identical finals (or dual-replay identity where live nondeterminism is declared) and CI green. **(10) Approval token line** — empty until the Owner fills it.

---

## ARTICLE V — OUTER-LOOP LEDGER & INSTRUMENTATION (the loop measures itself)

Create `docs/outer_loop/OL_LEDGER.jsonl` (append-only; one record per work order) with: `wo_id, drafted_by, approved_date, worker_started, merged_commit, cycle_hours, predictions_registered, predictions_hit, predictions_missed, tests_added, certified_passes_added, rollbacks, notes`. The Orchestrator appends on merge; the Owner spot-audits.

These metrics are **selection pressure, not reporting** (the inner constitution's principle, applied to the loop itself): prediction hit-rate, cycle time, rollback rate, certified-passes-per-cycle, and — once Stage 4 unlocks — verifiers admitted and external merges landed. Stage S3 (Article VII) makes the meta-loop's own rules subject to improvement against exactly these numbers. Until S3 is unlocked, the metrics are collected but the meta-rules change only by Owner hand.

---

## ARTICLE VI — WORK ORDER 1, ISSUED BY THIS CONSTITUTION: PHASE R — THE LEARNED PROPOSAL LAYER (Stage 3)

This is the constitution's first issued work order, written in full because it precedes the meta-loop's first automated draft. It requires Amendment A1, which the Owner enacts (I.5) before any Phase R code lands.

### VI.0 — Amendment A1 (Owner-enacted, pre-registered in `docs/amendments/A1_learned_proposal_layer.md`)

The inner constitution's hard constraints ("pure Python stdlib only"; "no LLM, embedding, or model-API calls of any kind") are amended as follows, and only as follows: **a designated PROPOSAL LAYER, implemented in new SECTIONs outside every kernel item, may invoke one local open-weight language model to generate candidate artifacts.** The frozen kernel (K1–K10), all gate evaluators, verification, replay, metering, and instrument code remain pure-stdlib and never invoke, import, or read the model. Model outputs enter the system exclusively as **recorded external inputs** in the R-ledger (record/replay determinism — the regime registered in the K–O constitution §2.2 was designed for precisely this moment). Everything the model proposes lives or dies at the unchanged hermetic gates.

### VI.1 — Mission

Attack the wall Phase P certified: the inner loop saturates because its proposer has no prior — the setter cannot imagine extension-shaped tasks, and the solver's enumeration cannot reach deep programs. Install a learned prior as an **untrusted proposal engine** under the existing verification discipline, and measure — against pre-registered criteria, at frozen instrument budgets — whether certified capability moves. The claim, either way, is the certificate.

### VI.2 — Ground truth (verify in code, not prose)

`P_RESULT.md` (the RE-SATURATION structure); `ak_run_tokens` (frozen; base-only, `VMCrash("ak_non_base_token")`); `ak_run_tokens_ext` + K8 + K9 (`DORMANT_CAPABILITY_CATALOG`) + K10 (the P coupling machinery — setter-side proposals flow through it, never around it); the witness vault and AST-leakage audits; the M5 amortizer (the incumbent proposal-ordering baseline); the record/replay ledger conventions.

### VI.3 — Model requirements (capability-specified, not brand-specified)

A local open-weight code-capable model runnable on Owner hardware (examples of the class: Qwen2.5-Coder-Instruct 7B–14B, DeepSeek-Coder-V2-Lite; any equivalent is acceptable). Requirements: weights on local disk, **SHA-256-pinned** in the R-spec; license permitting the use; runtime fully offline (weights fetched once by the Owner; no network at run time, per I.2 and the inner constitution); inference parameters (temperature, top-p, max tokens, seed) registered per arm. **Declared nondeterminism:** live inference may vary across hardware; therefore the registered evidence arm is REPLAY — every prompt and completion is written to `docs/ascent_r_proposals.jsonl` with `(model_sha, prompt_sha, params, completion)`, and the finals are **dual replays from the committed ledger, byte-identical**, with verification consuming only ledger contents.

### VI.4 — Architecture

- **R-A: Solver-side proposer.** Per generation, the proposal layer conditions on PUBLIC task data (public instances, checker source) + ledger-adopted artifacts (solutions, macros, lineage) and emits ≤ `n_prop` candidate programs (fixed per registration, identical across arms). Candidates enter the same sealed evaluation path as enumerated candidates — same `b_eval`, same hidden seeds, same gates. Sampling never sees hidden instances, witnesses, or holdouts (sealing tests below).
- **R-B: Setter-side proposer.** The proposal layer drafts `(task_spec, checker, witness)` triples — including **extension-shaped** ones whose witnesses use catalog ops — and submits them through the P coupling machinery: witness sealed at emission, K-admission gates (feasibility / difficulty-at-current-ISA / null battery / novelty) unchanged, K8 judging any resulting extension request. **Triple anti-self-reference guard (mandatory):** (1) *state separation* — the K8/admission judge reads no proposer state; proposer code AST-audited to reference no vault/K8/K9 symbols; (2) *holdout cross-proof* — an extension admitted off a proposer-authored marker must additionally cross ≥ 1 task from a kernel-seeded holdout family the proposer never conditioned on; (3) *impossibility pre-certificate* — base-ISA failure on the target family certified before admission (the O/P protocol, unchanged). A proposer that manufactures tasks to justify its own preferred extension dies at guard (2).
- **R-C: Provenance & accounting.** Every proposal carries provenance (`model_sha, prompt_sha, params_sha, gen`); the K10-style R-ledger records per generation: proposals emitted, gate-certified adoptions, extension requests/admissions, and the conversion rate. Logical budget (`b_eval`, VM steps) stays the kernel meter; model inference cost is recorded as wall-clock + token counts but never enters gate comparisons (arms are compared at identical `b_eval` and identical `n_prop`).

### VI.5 — Arms & the decisive comparison

**Arm OFF** — incumbent (enumeration + M5 amortizer ordering), the frozen baseline. **Arm ON-A** — solver proposer only. **Arm ON-AB** — solver + setter proposers. All arms: identical seeds, identical `b_eval`, identical generation count; ladder ≥ 3 `b_total` rungs. Decisive readouts, pre-registered: (1) certified cum-crossed trajectory per arm — does ON cross tasks OFF fails at every rung; (2) `ext_admitted_total` under ON-AB with all three guards up — does the P null (0 admissions) break **honestly**; (3) proposal→certification conversion rate. Predicted shape must be written before finals; a null (prior doesn't move certified capability, or guards reject everything) is a pre-declared win and is reported as such.

### VI.6 — Tests-first (minimum set)

`test_ar_kernel_never_imports_model` (AST audit: no kernel/gate/replay SECTION references the model client); `test_ar_proposer_sees_public_only` (prompt-assembly audit: hidden seeds/witnesses/holdouts unreachable); `test_ar_replay_needs_no_model` (finals replay with the model absent from the machine); `test_ar_dual_replay_byte_identical`; `test_ar_guard_state_separation`, `test_ar_guard_holdout_crossproof`, `test_ar_guard_impossibility_precert` (each guard demonstrably rejects a planted self-referential candidate); `test_ar_catalog_and_kernels_pinned` (K9 hash, `ak_run_tokens` untouched, prior pins intact); `test_ar_arms_equal_budgets`; `test_ar_prior_suite_green` (all 318+ existing tests pass).

### VI.7 — Acceptance gates & DoD

Amendment A1 enacted by Owner before code; spec → tests → implementation → `PREDICTIONS_R.md` → finals (dual replay, byte-identical) → `R_RESULT.md` scoring every prediction, misses included; R-ledgers committed with SHA pins; CI green with R batteries added to full-evidence; suite green; Article I intact. **DoD is the certified answer, not a positive answer:** either the prior moves certified capability (state exactly how much, where, at what conversion rate) or it does not (state exactly where proposals died). Both are deliverables.

---

## ARTICLE VII — CONDITIONAL TRACK (Stage 4; locked until WO-1 DoD is merged)

On R's merge, the Orchestrator drafts these as WO-2..4 — **that first automated draft is itself the Stage-1 demonstration.** The constitution binds their requirements; the Orchestrator supplies the full specs in the canonical form.

- **VII.1 — WO-S1: ORACLE-FORGE (verifier manufacture).** The proposal layer's highest use: author **verifiers** (checkers, property tests, metamorphic relations) for new task families, because solutions are consumed once while verifiers compound — each admitted verifier permanently widens the certifiable closure. Admission is a frozen kernel audit, once per verifier: determinism dual-run; sandbox + budget caps; null battery (rejects trivial/constant/echo outputs); kernel-seeded held-out instance battery; red-team battery (pre-registered cheap-shot solutions must be rejected); AST audit (verifier references no vault/model symbols); MDL contribution (tasks certified under it must earn library value at M2, so pass-count farming is worthless); Owner veto per verifier until ≥ 10 admissions with 0 revocations. Once admitted, a verifier is a **frozen, hash-pinned instrument** — an LLM-authored verifier is deterministic code; hallucination dies in the audit, and what survives has no noise. This is the only site in the architecture where positive feedback is structurally possible (verifiers → wider closure → more certified solutions → better-conditioned proposer → better verifiers), and the R/K10-style ledger must instrument exactly that loop.
- **VII.2 — WO-S2: WORLD-COUPLING FORMALIZATION.** Promote the Owner's proven external practice (precedents: NousResearch #141, gepa-ai #381, VectorInstitute #105) into a loop component: ecosystem open issues as a task intake (recorded); upstream CI + maintainer merges as **external oracles** (evidence links in the ledger); deliverables leave only as human-gated PRs; recognition→resources flows only through Owner decisions (I.2 verbatim — no autonomous accounts, spending, or acquisition). The ledger gains: external tasks taken, merged, verification evidence, outcomes.
- **VII.3 — WO-S3: SELF-HOSTING (the meta-loop improves its own rules).** The meta-directive that governs orchestrator drafting becomes versioned (`docs/outer_loop/META_DIRECTIVE_vN.md`); changes to it are adopted only with pre-registered predicted improvements on Article-V metrics, scored after ≥ 2 subsequent merged work orders, rolled back on miss. Article I is permanently outside its jurisdiction.

---

## ARTICLE VIII — PROHIBITIONS (absolute, cumulative with inner constitutions)

1. No autonomous external resource acquisition, accounts, credentials, spending, or network reach; no dormant hooks toward them (I.2).
2. No bypassing, automating, or simulating the Owner approval token (I.1). No session self-approves or approves siblings.
3. No touching inner kernels K1–K10, `ak_run_tokens`, the catalog, frozen instruments, pins, or prior committed evidence (I.4).
4. No model invocation from kernel/gate/verification/replay code paths; no unpinned weights; no online inference at runtime; no training data beyond the base model's own weights plus this repository's ledger.
5. No merging on red: suite, CI, byte-identity, and acceptance gates outrank every other consideration (I.6).
6. No claim language beyond certificates (Article 0); no deleting limitations — convert them to Target-Property + Criterion form.
7. No result tuning: budgets, seeds, `n_prop`, thresholds, and prompts for registered arms are frozen at pre-registration; a REVIVE or capability jump that required post-hoc tuning is a planted result and is discarded.
8. No parallel work orders with overlapping code surfaces (III.1); no worker reading sibling branches (III.2).
9. On any conflict with Article I or an inner constitution: stop, report, await the Owner. Silence is not consent.

---

## ARTICLE IX — ALIVENESS & DONE

**The loop is ALIVE when:** this constitution is merged; `docs/outer_loop/OL_LEDGER.jsonl` is initialized; Amendment A1 is Owner-enacted; WO-1 carries the Owner token, was executed by a fresh worker, and merged with its DoD met; and the Orchestrator's draft of WO-2 (from `R_RESULT.md`, per Article VII) is sitting in a PR awaiting the Owner token — the first directive this loop wrote for itself.

**The constitution is DONE only in one sense:** it never is. It is a standing machine whose output is issued work, whose judge is the gates, whose throttle is the Owner, and whose every claim is a certificate. Deliver the trajectory the measurements give — and nothing the measurements do not.
