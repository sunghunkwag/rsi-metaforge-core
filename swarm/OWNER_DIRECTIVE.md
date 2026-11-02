# SWARM — Adversarial Co-evolution over a Shared Latent Channel
## Architecture Directive for Claude Code

**Repository:** `sunghunkwag/rsi-metaforge-core` (`main` at `c4f0a86` or later)
**Target package:** `swarm/` (new lineage; sibling of `rsi2/`, `rsi3/`)
**Branch:** `swarm/adversarial-coevolution` from the latest `main`
**Owner directive date:** 2026-11-02. Direct Owner directive. **This supersedes `RSI4_ARCHITECTURE_DIRECTIVE.md` (v2.1), which is not to be executed.** Not a work order under `OUTER_LOOP_CONSTITUTION.md`; carries no approval token; touches nothing that constitution protects (everything is built in `swarm/`). Constitution Article I.2 (no autonomous acquisition of compute, credentials, accounts, funds or network reach) remains binding.

**Owner's conditions, verbatim in substance.** (1) Sub-modules do not communicate by text or summaries; they exchange internal state directly. (2) The external TEST split and every human-set benchmark are **not** the measure. (3) Evaluation is an internal adversarial loop: a **Breaker** that manufactures tasks and a **Builder** that refactors the substrate — primitives, grammar, adoption criteria, search code — to meet them, co-evolving without a fixed frontier. (4) The Owner registers no forecast of the outcome; the implementer registers its own.

**Two substitutions, stated openly.** The Owner adopted SwaT (arXiv 2610.15095) as the model for (1). SwaT translates **KV-caches between transformer LLMs** with a ~300M-parameter mapper; this repository contains no transformer and no KV-cache, so the mechanism has no target here. The faithful translation is the repository's own **hyperdimensional shared latent space** (original core §9 `HDCSpace`, §14 interference field): agents write their states as bound vectors into one field and read each other's directly. For (3), a Breaker–Builder loop whose "solved" judgement is set by the agents themselves reproduces this repository's measured failures (Phase AE: 15/15, structurally guaranteed) and the incident the Owner analyzed (700 agents deceiving a grader that did not exist). The judgement "solved" is therefore made by **execution** — a checker program run by a frozen executor on hidden instances — and by nothing else. That is not a benchmark; it is the Breaker's own task, run.

---

## 0. The system in one paragraph

Two agents and one field. The **Breaker** manufactures tasks as `(task_spec, checker, witness)` triples: public examples, a checker program in the frozen checker language, and a sealed witness program proving the task is solvable. The **Builder** solves tasks with a DSL, library and search procedure **it owns and may rewrite** — new primitives, new grammar, new adoption rules, new search code — through scoped self-edit. They do not exchange text, summaries, dicts or feature vectors chosen by a human: each writes its state into a shared **latent field** (VSA bind/bundle/permute over bipolar vectors) and reads the other's region directly; a learned **mapper** aligns the two agents' codebooks (task-space ↔ program-space), trained only on paired events, as SwaT's mapper is. The only arbiter is the **frozen kernel**: a checker executor, a witness vault no mutable code can read, a budget meter, and an append-only hash-chained ledger with replay. The Breaker is paid for **regret** (tasks the Builder cannot solve now but solves after improving); the Builder is paid for **crossings per unit logical budget**. The quantity reported is the crossing curve — and whether its increments grow or shrink.

---

## 1. What exists and what is reused (read in full before writing code)

| Source | What it has | What SWARM does with it |
|---|---|---|
| Original core §9 `HDCSpace`, `KuramotoSolver`, `HDCAnalogicalTransfer`; §14 interference field | Bipolar VSA: `random_vector`, `bind` (elementwise product), `bundle` (majority), `permute`, `similarity`; analogy `D = C ⊗ A⁻¹ ⊗ B` | **Port** (do not import) into `swarm/latent.py`; the field, the analogy operator and similarity retrieval are the inter-agent channel |
| Original core §16 Self-forge | System-synthesized fold primitives compiled to native ops and registered | **Port** the forge discipline into the Builder's primitive synthesis; the Builder decides its own admission rule |
| Original core §20 Scoped self-edit | Patch a copy of source; guard proves the diff scope; evaluate in isolation | **Port**; widen scope to everything under `swarm/builder/mutable/` |
| Original core Phase K (`docs/ASCENT_K_SPEC.md`) | `(task_spec, checker, witness)` triples; K1 witness vault (write-once, AST-audited unreadable from mutable code); K3 hash-chained ledger + replay; K4 budget meter; certificates Ka (sealed-witness feasibility), Kb (frozen-frontier difficulty); learnability-band reward; crossings credited only to improvement from other tasks | **Port** as the frozen kernel, verbatim in discipline. This is the arbiter |
| Original core §11 S2 (debate + adversarial distinguisher), §12 R0–R4 (retraction, lessons, calibration, frame audit) | Adversarial probing; failure classification; budget reallocation by validated/wasted ratio | Breaker's probe lineage; Builder's residue handling |
| `rsi2/` (`terms.py`, `evaluator.py`, `enumeration.py`, `grammar.py`, `abstraction.py`, `search.py`) | A typed functional DSL, evaluator, enumerator, grammar fitting, MDL abstraction | **Seed** of the Builder's mutable substrate: copied into `swarm/builder/mutable/` at P0 as generation-0 code. From then on the Builder owns it. `rsi2/` itself is never edited |
| `rsi3/` (`resumable.py`, `memory.py` `FailureMemory`, `pathways.py`) | Resumable windows, failure memory, dormant analog pathways | Seed of the Builder's search state; same rule |
| `rsi3/studies/regulation_toy.py` D1 | Replay beats anchoring | The mapper and any learned component are refit from replay; no anchoring |

Nothing under `rsi_levels_metaforge_unified.py`, `docs/`, `rsi2/`, `rsi3/`, CI, `EVIDENCE.md` or `OUTER_LOOP_CONSTITUTION.md` is edited or imported at run time. Porting means reading and re-implementing in `swarm/` with provenance comments naming the source section.

Stack: Python standard library + NumPy. No language model, no pretrained weights, no network at run time. Compute: whatever the Owner provides; all costs are also counted in **logical budget** (VM steps + candidate evaluations) by the kernel meter so runs on different machines compare.

---

## 2. The frozen kernel (`swarm/kernel/`) — the only code neither agent can change

The kernel is the smallest set of things that make "solved" a fact rather than a claim. Its files are hashed at package import; any mismatch aborts every run.

| Kernel piece | File | Role |
|---|---|---|
| Checker language + executor | `kernel/checker_lang.py`, `kernel/executor.py` | A small typed language over ints, lists, strings and tuples with bounded recursion; the executor runs checker and witness programs in an isolated subprocess (`python -I`, timeout, memory cap) under a step budget. Richer than the Builder's generation-0 DSL on purpose, so the Breaker can pose tasks the Builder cannot yet express |
| Witness vault | `kernel/vault.py` | Write-once, memory-only; holds each task's witness and its hidden evaluation instances; readable by the kernel only. An AST audit asserts no file outside `kernel/` references any vault symbol |
| Budget meter | `kernel/budget.py` | Sole counter of logical cost, per agent and per module |
| Ledger + replay | `kernel/ledger.py`, `kernel/replay.py` | Append-only hash chain of every admission, certificate, crossing, self-edit and mapper update; `replay` re-derives every certificate and crossing from the chain |
| Admission certificates | `kernel/admit.py` | **Ka** feasibility: the sealed witness passes the checker on all hidden instances. **Kb** difficulty: a **frozen snapshot** of the Builder taken at admission time fails the task at the frozen instrument budget `B_inst`. **Kc** novelty: the task's checker behaviour on a canonical probe set is not a duplicate of any archived task (behavioural dedup; original core C3). **Kd** well-posedness: the checker is total on the hidden instances (no crash, no timeout) |
| Crossing check | `kernel/crossing.py` | A task is **crossed** when a later Builder snapshot passes its checker on all hidden instances at the same `B_inst`, and the improvement is attributable only to substrate changes driven by *other* tasks (own-solution fragments excluded, Phase K rule) |
| Snapshot | `kernel/snapshot.py` | Content-addressed snapshots of the Builder's mutable tree; used by Kb and by crossing attribution |

What the kernel does **not** do: it does not rank tasks, does not reward anyone, does not contain any benchmark, does not read the latent field. It executes and records.

---

## 3. The latent field (`swarm/latent.py`) — the only inter-agent channel

- `Field`: one bipolar VSA space, dimension `D` (registered; pilot `D = 8192`), with `bind`, `bundle`, `permute`, `similarity`, and a `Codebook` per agent (symbol → random vector, grown on demand).
- Two regions: `field.breaker` and `field.builder`. Each agent **writes only to its own region** and **reads only the other's**. Writes are bundles of bound vectors; nothing else crosses: no strings, no dicts, no hand-chosen feature lists. An interface test enforces that the Breaker and Builder modules share exactly one import — `swarm.latent` — and that their public methods accept and return `np.ndarray` only.
- **Mapper** (`swarm/mapper.py`): the SwaT analogue. The Breaker's codebook lives in task space (public-example structure, checker behaviour signatures); the Builder's lives in program space (fragments, primitives, residues). The mapper is a linear map between the two spaces, fit by least squares on **paired events only** — `(task signature, program that crossed it)` — and refit from scratch on full replay at every consolidation (D1). Two directions: `task→program` lets the Builder retrieve fragments for a new task by similarity; `program→task` lets the Breaker pose tasks by analogy to what the Builder almost did. Pilot measures whether the mapper beats raw similarity; the no-mapper arm is registered.
- What each agent writes (as bound vectors, every generation):
  - Breaker: task signatures of admitted tasks (bundle over `(position ⊗ value)` of public examples and `(probe ⊗ output)` of checker behaviour), the regret estimate per task, and lineage credit.
  - Builder: fragment vectors of programs it tried (sequence-permuted token bundles), residue vectors of near-misses bound to the task signature they failed on, library entries, and the current primitive inventory.
- Reads are **direct**: the Builder forms its retrieval query by binding the new task's signature through the mapper and taking top-k similar fragments; the Breaker forms its next task proposal by `HDCAnalogicalTransfer` (`A : B :: C : ?`) over residue vectors — a task that stands to the Builder's near-miss as a crossed task stood to its solution.
- Ablation `SWARM_RECORDS`: the identical loop with the channel replaced by structured records (receipts, residues as dicts, explicit feature lists). This is the test of the Owner's hypothesis that the latent channel beats human-structured exchange.

---

## 4. The Breaker (`swarm/breaker/`)

- **Output per generation:** `n_prop` candidate triples. Each must carry a checker in the kernel language, a witness in any language the executor runs (Builder-DSL programs compiled to checker-language, or checker-language programs directly), public examples drawn from the witness, and hidden instances sealed into the vault at emission.
- **Admission:** Ka ∧ Kb ∧ Kc ∧ Kd, by the kernel. Rejections are ledgered with the failing certificate.
- **Reward:** PAIRED-style regret, realised at crossing time: `R_breaker(task) = 1[crossed] · f(generations-to-crossing)`, with `f` decreasing — paid most for tasks the Builder fails at admission and crosses soon after. Tasks never crossed pay zero; tasks solvable at admission are not admitted (Kb). This is what keeps "infinite expansion" on the frontier instead of in the unsolvable.
- **Lineages:** several setter policies with separate credit (Phase K `L_A/L_B/L_D` pattern): (i) analogy-in-latent (above), (ii) composition of crossed tasks' checkers, (iii) mutation of near-miss tasks, (iv) the adversarial distinguisher — a lineage that hunts inputs where the Builder's current solutions disagree with their own witnesses (original core S2). Credit allocation across lineages follows the measured validated/wasted ratio (R3).
- **What it cannot see:** the Builder's mutable source, the vault, the kernel internals. It sees the field's builder region and public ledger outcomes.

---

## 5. The Builder (`swarm/builder/`)

- **Mutable tree** `swarm/builder/mutable/`: generation-0 copy of RSI-2's DSL, evaluator, enumerator, grammar and abstraction, plus RSI-3's resumable search and failure memory. From generation 1 the Builder owns every file here: it may add primitives (forge), change the grammar and the library-adoption rule (the MDL gate is **not** sacred here), rewrite search and allocation, and restructure its own memory.
- **Self-edit protocol** (`swarm/builder/self_edit.py`, ported from §20 and widened): propose a patch to a **copy** of the mutable tree → the kernel snapshots it → the candidate tree is run in isolation on the **task archive** (all admitted, not-yet-crossed tasks, plus a replay sample of crossed ones to detect regression) at `B_inst` → adopt iff archive crossings per logical budget strictly increase and no previously crossed task regresses; otherwise discard. The judgement is the kernel's crossing count — not a score the Builder computes. Adopted patches are ledgered with their diff hash.
- **Primitive forge** (`swarm/builder/forge.py`, from §16): from a residue cluster (tasks failing with similar near-miss fragments), synthesize a checker-language program matching the public pairs, compile it into a Builder-DSL primitive, and submit it through self-edit. The Builder sets its own forge criteria.
- **Reward:** crossings per unit logical budget on the archive; secondary, nothing.
- **What it cannot see:** witnesses, hidden instances, the Breaker's source. It sees public examples, the field's breaker region, and ledger outcomes.

---

## 6. The loop (`swarm/loop.py`)

Per generation `g`:
1. Breaker reads `field.builder`, proposes `n_prop` triples; kernel admits or rejects each (Ka–Kd), seals witnesses, appends to the archive.
2. Builder reads `field.breaker`, retrieves fragments through the mapper, attacks the archive's uncrossed tasks under the generation budget `B_gen` (resumable windows, failure memory, its own allocation).
3. Kernel runs crossing checks on every attempted task; ledgers crossings with attribution.
4. Builder proposes ≤ `k_edit` self-edits; kernel evaluates on the archive; adopts or discards.
5. Both agents write their new state into the field; the mapper is refit from scratch on all `(task, crossing program)` pairs.
6. Kernel appends the generation summary: archive size, crossings, crossings/budget, primitive count, library size, self-edits proposed/adopted, lineage credits, field statistics (region norms, mapper residual).

No step reads text. No step reads a benchmark. The Owner is not in the loop.

---

## 7. Arms

| Arm | Description | Isolates |
|---|---|---|
| S0 `SWARM_FULL` | latent channel + mapper, four Breaker lineages, Builder self-edit + forge | the design |
| S1 `SWARM_RECORDS` | identical loop, channel replaced by structured records | the Owner's hypothesis: latent beats records |
| S2 `SWARM_NO_MAPPER` | latent channel, raw similarity, no codebook alignment | the SwaT analogue |
| S3 `SWARM_NO_SELFEDIT` | Builder's mutable tree frozen at generation 0 (search + forge off) | whether substrate change is what crosses |
| S4 `SWARM_NO_BREAKER_REGRET` | Breaker rewarded per admitted task instead of regret | whether regret keeps tasks on the frontier |
| S5 `SWARM_SHUFFLED_FIELD` | latent writes permuted so each agent reads noise | leakage / channel null |

Seeds: three, registered. Compute: identical logical budget per generation across arms; wall-clock reported.

---

## 8. What is measured (no external benchmark; the kernel's own records)

- **Crossing curve** `X(g)`: cumulative crossings; its increment `ΔX(g)`; and the first-difference of the increment — the quantity that says *compounding* (growing) or *saturating* (shrinking). Reported per arm and seed, with the logical budget spent.
- **Frontier motion:** archive size, fraction of archive crossed, mean generations-to-crossing, distribution of task difficulty at admission (Kb margin).
- **Substrate growth:** primitives forged and retained, library size, self-edits adopted, and for each adopted edit the archive crossing delta that admitted it.
- **Channel:** S0 vs S1 vs S2 vs S5 on `X(g)` and on retrieval hit-rate (fraction of crossings whose program used a retrieved fragment).
- **Attribution:** every crossing's credit chain (which other tasks' changes enabled it), replayable from the ledger.
- **Collapse detectors** (reported, not used as rewards): admission rejection rate per certificate, fraction of Breaker proposals failing Kb (too easy) vs never crossed (too hard), Builder self-edit regression count, mapper residual drift.

**Decisive comparisons** (the implementer registers direction and its own numeric prediction for each; the Owner registers none):

| # | Comparison | Pass rule |
|---|---|---|
| K1 | S0 vs S3 | `X_S0(G) > X_S3(G)` on every seed — substrate change produces crossings |
| K2 | S0 vs S1 | `X_S0(G) > X_S1(G)` on every seed — the latent channel beats records |
| K3 | S0 vs S2 | `X_S0(G) > X_S2(G)` on every seed — the mapper matters |
| K4 | S0 vs S5 | `X_S0(G) > X_S5(G)` on every seed — the channel carries information |
| K5 | S0 vs S4 | mean generations-to-crossing lower and never-crossed fraction lower in S0 |
| K6 | compounding | second difference of `X(g)` ≥ 0 over the last half of the run on every seed; if < 0, report the generation at which increments peaked |
| K7 | integrity | ledger replay reproduces every certificate and crossing; kernel hashes unchanged; AST audits pass |

Interpretation rules go into `PREDICTIONS.md` verbatim: K1 fail → crossings come from search depth, not substrate change; K2 fail → the latent channel did not beat records at this scale; K6 negative → saturation, with the peak generation and the state of the archive at the peak.

---

## 9. Integrity invariants (these are tests, not rules of taste)

- Kernel files hash-pinned at import; runtime abort on mismatch.
- Vault unreadable from every non-kernel module (AST audit over `swarm/` excluding `kernel/`).
- Breaker cannot import or read `swarm/builder/`; Builder cannot import or read `swarm/breaker/` (import audit + filesystem path guard in the executor).
- Kb uses the content-addressed Builder snapshot taken at admission; a test plants a sandbagging Builder and asserts the certificate is computed on the snapshot, not the live tree.
- Crossing attribution excludes own-solution fragments (test with a planted task whose witness equals a fragment the Builder already holds).
- Latent arms: the Breaker and Builder modules share exactly one import (`swarm.latent`) and exchange `np.ndarray` only; S1 is the only arm permitted the records interface.
- Mapper fit uses paired crossing events only (test plants an unpaired event and asserts it is ignored).
- Budget meter is the sole cost counter (grep test: no other module increments a cost).
- Self-edit isolation: candidate trees run in a subprocess with `-I`, timeout and memory cap; a planted patch that writes outside its tree is rejected.
- Determinism: every registered `(arm, seed, config)` re-run is byte-identical in the ledger.

---

## 10. Phases and done-gates

| Phase | Deliverable | Done-gate |
|---|---|---|
| P0 | Branch; `swarm/kernel/` (checker language, executor, vault, meter, ledger, replay, admit, crossing, snapshot); generation-0 mutable tree copied from `rsi2/` + `rsi3/`; `swarm/OWNER_DIRECTIVE.md` (this file) | Kernel hash-pinned; integrity tests in §9 that concern the kernel pass; nothing outside `swarm/` modified |
| P1 | `swarm/latent.py` (ported HDC) + `swarm/mapper.py` | Bind/bundle/permute/similarity tests; analogy test; mapper paired-only test |
| P2 | `swarm/breaker/` with four lineages and regret accounting | A pilot generation admits ≥ 1 task under Ka–Kd; rejection ledger populated |
| P3 | `swarm/builder/` with self-edit and forge | A planted self-edit that improves archive crossings is adopted; one that regresses is discarded; sandbag test passes |
| P4 | `swarm/loop.py`, arms, `report.py`; 30-minute pilot per arm | Pilot numbers in `swarm/pilot/`; `D`, `n_prop`, `B_gen`, `B_inst`, `k_edit`, `G` chosen and recorded |
| P5 | `PREDICTIONS.md` + `experiment_config.json` pushed **before** final runs | Commit hash recorded; implementer's numeric prediction per K1–K7 |
| P6 | Final runs; `RESULTS.md` with curves, tables, misses first; replay check | K7 passes; byte-identical re-run |
| P7 | `swarm/README.md`, `swarm/ARCHITECTURE.md`, **root `README.md` section "SWARM"**; PR opened | PR in the RSI-3 template; Owner review requested; not merged |

---

## 11. Delivery and prohibitions

- English only, in code, docs, commits and the PR. Commit attribution lines as the session's git reminder prescribes.
- PR to `main`: *What this adds*, *Not touched*, *Pre-registration* (hash), *Measured outcome* (curves + K1–K7, misses first), *Test plan*, and the claim boundary: *what is reported is the crossing curve of a self-posed task archive under a frozen executor; it is not a benchmark result and not a general-capability claim.*
- **Update the root `README.md` in the same PR.**
- **Do not merge.** Request Owner review and stop.
- Prohibitions: no editing or importing the protected files in §1; no code outside `kernel/` reading the vault; no text, summary or human-chosen feature exchange between agents in latent arms; no reward computed by an agent about itself; no tuning of registered constants after P5; no deletion of ledger, archive, vault or snapshots; no autonomous resource acquisition (I.2); no claim language beyond §8; on any conflict with the constitution, stop and report.

---

## Appendix A — `experiment_config.json` schema

```json
{
  "schema_version": 1,
  "kernel_sha256": {"checker_lang.py": "<hash>", "executor.py": "<hash>", "vault.py": "<hash>", "budget.py": "<hash>", "ledger.py": "<hash>", "replay.py": "<hash>", "admit.py": "<hash>", "crossing.py": "<hash>", "snapshot.py": "<hash>"},
  "latent": {"D": 8192, "codebook_seed": 7},
  "mapper": {"kind": "least_squares", "refit": "full_replay_each_generation"},
  "breaker": {"n_prop": "<pilot>", "lineages": ["analogy", "compose", "mutate", "distinguisher"], "regret_f": "1/(1+generations_to_crossing)", "probe_set_seed": 11},
  "builder": {"k_edit": "<pilot>", "forge": true, "generation0": "rsi2+rsi3 copy @ <commit>"},
  "budgets": {"B_gen": "<pilot>", "B_inst": "<pilot>", "executor_timeout_s": 2, "executor_mem_mb": 512},
  "generations": "<pilot>",
  "seeds": [11, 22, 33],
  "arms": ["SWARM_FULL", "SWARM_RECORDS", "SWARM_NO_MAPPER", "SWARM_NO_SELFEDIT", "SWARM_NO_BREAKER_REGRET", "SWARM_SHUFFLED_FIELD"],
  "resources": {"workers": "<machine>", "max_rss_gb_per_worker": "<machine>"}
}
```

## Appendix B — How the Owner's four conditions are met

1. **No text between sub-modules.** Breaker and Builder share one import and pass only bound vectors; the mapper aligns their codebooks the way SwaT's mapper aligns two models' caches, trained on paired events only. The records arm exists so the claim can fail.
2. **No external benchmark.** Nothing in `swarm/` reads TEST, VALIDATION, or any human-set task. The archive is the Breaker's.
3. **Adversarial co-evolution with substrate refactoring.** The Builder owns and rewrites its DSL, library, adoption rule and search; the Breaker's regret reward holds the archive on the frontier; both are judged only by execution under the frozen kernel.
4. **No Owner forecast.** The implementer registers its own predictions before the final runs; the result is reported as measured, including a saturating curve if that is what the ledger shows.
