# Amendment A1 — The Learned Proposal Layer

**Status: DRAFT — PROPOSED, NOT ENACTED.**
This file was drafted by a worker session under `OUTER_LOOP_CONSTITUTION.md` Article I.5 ("Sessions may draft amendment proposals; only the Owner enacts"). It has **no force** until the Owner personally fills the enactment block at the bottom of this file, outside any automated session. Per I.5 and VI.7, enactment must be committed **before any Phase R code lands**; per Article IV precondition, WO-1 cannot execute against an un-enacted A1.

---

## 1. What is amended

The inner constitution's hard constraints — cited in-repo at `docs/05_limitations.md:47-51` ("there are no model calls anywhere in the runtime (test-enforced: the dynamic-evaluator guard and the stdlib-only constraint) ... this boundary is permanent by the directive's constitution (§2.2: no LLM, embedding, or model-API calls of any kind)") — are amended as follows, and only as follows:

> A designated **PROPOSAL LAYER**, implemented in new SECTIONs outside every kernel item, may invoke **one local open-weight language model** to generate candidate artifacts. The frozen kernel (K1–K10), all gate evaluators, verification, replay, metering, and instrument code remain pure-stdlib and never invoke, import, or read the model. Model outputs enter the system exclusively as **recorded external inputs** in the R-ledger. Everything the model proposes lives or dies at the unchanged hermetic gates.

Note for enactment accuracy: the governing directive document containing the amended §2.2 is held by the Owner outside this repository (repo-wide grep at `98ff67f` finds no `METAFORGE_ASCENT_DIRECTIVE.md` or `PHASE_P_COUPLING_DIRECTIVE.md`; the in-repo citations of the constraint are `docs/05_limitations.md:47-51` and the test-enforced guards). At enactment, the Owner should confirm the exact off-repo clause text being amended, or paste it into §5 below, so the amendment record is self-contained per Article I.3.

## 2. What is NOT amended (enumerated, closed list of non-changes)

- `ak_run_tokens` (`rsi_levels_metaforge_unified.py:42077`) and the base-ISA discipline — untouched.
- K1 witness vault (`AKWitnessVault`, :42030), K3 ledger + replay, K4 budget meter (`AKBudgetMeter`, :42056), K5 MDL formula (`al_mdl`, :43764), K6 proof kernel + axiom base (`AN_AXIOMS`, :45518), K7 anti-cheat battery, K8 extension-admission gate, K9 `DORMANT_CAPABILITY_CATALOG` (:6010, pin `ASCP_CATALOG_SHA256`), K10 closure-generation ledger — all frozen exactly as their constitutions state (Article I.4).
- All gate evaluators, verification, replay, metering, and instrument code remain pure-stdlib.
- Offline discipline: no network I/O at runtime. Weights are fetched once by the Owner, outside any session (Article I.2).
- The stdlib-only and no-model-call constraints remain in force everywhere **except** the designated proposal-layer SECTIONs.

## 3. Determinism regime for model outputs (registered by this amendment's execution)

No record/replay regime for recorded external inputs is currently registered in this repository — the registered determinism regime at `98ff67f` is dual-RUN byte-identity (`docs/ASCENT_K_SPEC.md:118-121, :285-287`). Phase R therefore registers, in `docs/ASCENT_R_SPEC.md` at spec-freeze:

- **Declared nondeterminism:** live inference may vary across hardware.
- **Registered evidence arm: REPLAY.** Every prompt and completion is written to `docs/ascent_r_proposals.jsonl` with `(model_sha, prompt_sha, params, completion)`.
- **Finals are dual replays from the committed ledger, byte-identical**, with verification consuming only ledger contents (`test_ar_replay_needs_no_model`, `test_ar_dual_replay_byte_identical`).

## 4. Model requirements (capability-specified, not brand-specified)

A local open-weight code-capable model runnable on Owner hardware (examples of the class: Qwen2.5-Coder-Instruct 7B–14B, DeepSeek-Coder-V2-Lite; any equivalent is acceptable). Requirements: weights on local disk, SHA-256-pinned in the R-spec; license permitting the use; runtime fully offline; inference parameters (temperature, top-p, max tokens, seed) registered per arm.

## 5. Enactment block (Owner-only; empty until enacted)

Exact off-repo clause text being amended (Owner pastes at enactment, if adopted):

```
(empty)
```

ENACTED:
