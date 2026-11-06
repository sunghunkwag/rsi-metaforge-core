# RSI-4 — Architecture Directive for Claude Code (v2, revised after reading the repository)

**Repository:** `sunghunkwag/rsi-metaforge-core` (`main` at `c4f0a86`, after PR #26)
**Target package:** `rsi4/` (new; sibling of `rsi2/` and `rsi3/`)
**Branch:** `rsi4/meta-transfer-continual` from the latest `main`
**Owner directive date:** 2026-11-02. Like `rsi2/OWNER_DIRECTIVE.md` and `rsi3/OWNER_DIRECTIVE.md`, this is a direct Owner directive, **not** a work order under `OUTER_LOOP_CONSTITUTION.md`, carries no approval token, and touches nothing that constitution protects. Article VIII prohibitions apply to it anyway (see §11).

**One-line goal.** On RSI-2's frozen synthesizer and RSI-3's measured memory layer (resumption + failure memory), build and measure three things: **(1) meta-reinforcement learning** (fast adaptation inside a run with frozen weights), **(2) transfer** (a VALIDATION gain attributable to library growth from *other* tasks), and **(3) continual learning** (a sequence of task families without forgetting). Each is measured against pre-registered criteria with controls that can make the claim fail.

---

## 0. Mandate, scope, and claim boundary

You are the **implementer**. The Owner sets scope and merges. Build to this spec and make the result self-auditing.

- All code, comments, docs, commit messages, and the PR in **English**.
- Read-only, never edited and never imported from: `rsi_levels_metaforge_unified.py` (the original 2026-06 core, 49,316 lines on `main`), `docs/`, `EVIDENCE.md`, `OUTER_LOOP_CONSTITUTION.md`, CI workflows, all frozen instruments, pins, and prior committed evidence. `rsi2/` and `rsi3/` are imported read-only and never edited (same rule RSI-3 followed for RSI-2).
- Python standard library + NumPy only (RSI-2/RSI-3 stack). No model, no embedding, no network at run time.
- RSI-2's freeze rule stands: no new primitives, no hand-written library entries, no hand-written heuristics, no change to the evaluator, **no change to RSI-2's MDL library-adoption gate**.
- The sealed **TEST** split (12 tasks) is never opened, referenced, or counted. VALIDATION is measured for reporting and for the registered comparisons only; it never feeds a decision inside a run.
- The only reader of hidden examples is `rsi3/verifier.py` (`FrozenVerifier`). One query per task per generation; every label in memory needs an authentic receipt (`rsi3/memory.py` guard).
- Claim boundary (Article 0): *bounded adaptive improvement of how a fixed synthesizer spends a fixed budget, plus whether its library grows from other tasks, measured on an external corpus.* No claim of recursive self-improvement, AGI, singularity, or unbounded capability anywhere.
- Honest-negative by default. Limitations are written as Target Property + Criterion (Article VIII.6), never deleted or softened. The RSI-3 results stand as written.

---

## 1. What exists — read these in full before writing code

### 1.1 The original core (the file the repository was born with)

`rsi_levels_metaforge_unified.py` — first commit `3cfc329` (2026-06-13, 33,879 lines), now 49,316 lines. A typed stack-VM program synthesizer with a **meta-gate** (every proposed searcher improvement is A/B-tested against the incumbent on the unsolved frontier at equal budget and seeds; regressions rejected and logged) and a frozen counterfactual arm. Sections relevant to RSI-4, because they already contain the *disciplines* this directive reuses:

| Original section | What it already does | What RSI-4 takes from it |
|---|---|---|
| §11 General-domain directive layer, **S1 PRM** | `StepScorer`, a process scorer trained only from self-verified episodes, persisting across tasks and waves ("learning-to-learn"); ablated, negative deltas reported | A learned component that persists across tasks is prior art here; its ablation discipline is the template for A3/A4 |
| §11 **S4 meta-learning** | An orchestration config is chosen on task family **A** by an oracle-free self-score and **audited on held-out family B (Goodhart check)** | The Family A / Family B split in §4.3 is this discipline, not a new idea |
| §12 Reflection tower **R2 lesson transfer** | Lessons keyed substrate-neutrally and applied across substrates, measured by ablation | Cross-family transfer must be measured by ablation, never asserted |
| §12 **R3 reflection calibration** | Second-look budget per lesson type reallocated multiplicatively from the ratio of validated retractions to wasted second looks | The surprise-weighted replay priority in §4.5 is the same move: budget follows measured yield |
| §13 Capability horizon | A **dormant catalog** of primitives outside the searcher's vocabulary; activation system-triggered, designer-stocked, stated not hidden | RSI-3's dormant analog pathways descend from this; RSI-4's lifecycle rules (§4.6) keep "stated, not hidden" |
| §21 Persistent long-horizon cycle | Checkpointed improvement cycles with save/load state | The continual stream (§5.3) checkpoints after every stage |
| Ascent Phase K (`docs/ASCENT_K_SPEC.md`) | Self-manufactured tasks as `(task_spec, checker, witness)` triples; witness vault unreadable from mutable code (AST-audited); **crossings** credited only to library growth from *other* tasks, own-solution macros excluded | The dream-task generator (§4.3) emits triples; transfer credit (§5.2) uses the crossing rule |
| Levels system (file tail, "stack of adopted levels over the bare base") | `evaluate_candidates` adopts a level iff it strictly contributes against the last wake's misses without regressing held-out gate coverage; `PredictorLevel` is a per-capability logistic ordering model with a 1-in-3 audit split | Precedent that an allocation/ordering level is adoptable only by measured gain; the audit split is reused for `φ` |
| Embedded `transfer_bench` / `compute_transfer_metrics` (first commit, line ~19888–20149) | Trains on task A then task B and scores hold-out **AUC, regret, gap, recovery_time** — the repository's own transfer metric suite | §5.2 reports regret and recovery time alongside solve counts |
| Embedded `ReplayBuffer` / `PolicyModel` (first commit, line ~26104; torch-optional) | A generic RL scaffold inside the embedded cognitive region; not wired to any registered, gate-measured experiment that this directive could find | Prior art only. RSI-4 does **not** import or revive it; RSI-4's policy is NumPy and allocation-only |

**What the original core did and did not have, at implementation level** (read, not inferred): its "meta-learning" is `gd_meta_select` — a self-scored pick among a small discrete config grid on family A, audited on family B — plus a cross-task averaged-perceptron PRM and a self-minted curriculum with a per-generation drift audit. It has **no recurrent, reward-trained allocation policy** and no fast-adaptation inner loop; that is what RSI-4 adds. Its "transfer" is `transfer_bench`, the R2 lesson book (two boolean flags that widen probe generation across substrates), and an HDC bind/unbind analogy demo; later phases added Phase K crossings. Its "continual" element is PRM persistence across waves, R0 retraction with PRM replay from the clean remainder, and `longcycle` checkpointing; it has **no forgetting metric**. RSI-4 adds BWT/FWT.

RSI-2 and RSI-3 were built **without importing** this file. RSI-4 follows the same rule: reuse the disciplines above by reference, never the code.

### 1.2 The constitution

`OUTER_LOOP_CONSTITUTION.md` — Article I (kernel, immutable), Article VIII (prohibitions). Binding points for this package: no result tuning after pre-registration (VIII.7), no merging on red (I.6: full suite + `quick-ci` + `full-evidence` green + byte-reproducibility), limitations in Target-Property + Criterion form (VIII.6), no autonomous resource acquisition (I.2), stop and report on any conflict (VIII.9).

### 1.3 RSI-2 (frozen)

`rsi2/`: `abstraction.py`, `benchmark.py`, `calibrate.py`, `corpus.py`, `enumeration.py`, `evaluator.py`, `experiment.py`, `grammar.py`, `heuristics.py`, `learning.py`, `measurement.py`, `recognition.py`, `report.py`, `sampling.py`, `sealed_evaluation.py`, `search.py`, `terms.py`, `types.py`. External corpus: 60 DreamCoder list tasks, TRAIN 36 / VALIDATION 12 / sealed TEST 12. Measured: TEST 2/12 on every arm and seed, **no library entry ever adopted, no heuristic adopted** (`rsi2/RESULTS.md`). Depth matters: plain enumeration verifies 6/36 at B64 and 8/36 at B640 (`rsi2/research/BOOTSTRAP_RESULTS.md`). 99.1 % of wake candidates went to tasks left unsolved (`rsi2/research/FAILURE_ANALYSIS.md`). Full suite: `python -m unittest discover -s rsi2/tests` (470 tests per the root README).

### 1.4 RSI-3 (merged: PR #24 memory-feedback core, PR #26 failure memory)

Modules: `verifier.py`, `memory.py` (`EpisodicMemory`, `FailureMemory`), `resumable.py`, `pathways.py` (`PathwayRegistry`: `prior`, `recognized`, `analog:<S>`), `value_model.py`, `controller.py` (value model + UCB), `integrator.py`, `loop.py`, `experiment.py`, `report.py`, `studies/regulation_toy.py`. Docs: `OWNER_DIRECTIVE.md`, `ARCHITECTURE.md`, `PREDICTIONS.md`, `RESULTS.md`, `PREDICTIONS_FAILURE_MEMORY.md`, `FAILURE_MEMORY_RESULTS.md`. Suite: `python -m unittest discover -s rsi3/tests -t .` (39 tests). Config: B_wake = B_eval = 64, 8 generations, seeds 11/22/33, search limits AST ≤ 12 / 20,000 expansions / 2,000 steps, `workers: 2`.

**Design decisions RSI-4 inherits (with their evidence):**
- **D1 — Replay, not anchoring.** `studies/regulation_toy.py`: replay alone kept a beneficial change and repaired a harmful one; *every* parameter-anchor variant (fixed reference, strong reference, evidence-gated reference) lost old capability, new capability, or both. The value model is refit from scratch on full replay every generation. **Consequence for RSI-4: no EWC/SI-style anchoring in the main design** (an earlier draft of this directive proposed it; it is withdrawn). Continual learning here is replay-based.
- **D2 — Gates only where they earn their place.** Two gates: memory entry (receipt required) and RSI-2's unchanged MDL gate on library adoption. No rollback or reference gate on continuous learning. RSI-4 adds exactly one more discrete gate — pathway retention (§4.6) — and no gate on the policy's learning.

---

## 2. Measured state of the art in this repository (the numbers RSI-4 must beat)

| Arm | TRAIN g8 (seeds 11/22/33) | VALIDATION g8 | CPU/run | Source |
|---|---|---|---|---|
| RSI2 (unchanged `wake_sleep`) | 6 / 6 / 6 | 2 / 1 / 2 | 241 s | `rsi3/RESULTS.md` |
| RSI3 (learned allocation, replay, genesis) | 6 / 6 / 6 | 2 / 1 / 2 | 419 s | `rsi3/RESULTS.md` |
| RSI3_UNIFORM (resumption, even split) | 7 / 7 / 7 | 2 / 1 / 1 | 376 s | `rsi3/RESULTS.md` |
| **RSI3_UNIFORM_FM** (resumption + failure memory, even split) | **8 / 8 / 8** | 2 / 1 / 2 | 470 s | `rsi3/FAILURE_MEMORY_RESULTS.md` |
| RSI3_FM (learned allocation + failure memory) | 7 / 8 / 7 | 1 / 2 / 2 | 1,065 s, **4.5 GB peak RSS** | `rsi3/FAILURE_MEMORY_RESULTS.md` |

Facts that fix the design:

| # | Measured fact | Consequence |
|---|---|---|
| F1 | Every gain so far came from **hard memory rules** (resume the enumeration; skip known public failures), not from learning. The learned arm still loses to the even split (−1 on 2 of 3 seeds). | Resumption + failure memory are the fixed primitive layer. RSI-4 learns *where to spend*, never *whether to restart* or *whether to re-charge a known failure*. |
| F2 | Six positive labels in the first study (all generation 1); the learned arm's allocation "still spreads over about a hundred slots, so no single order gets that deep" (`index-k (k=3)` needs rank ≈ 273). | A dense, non-self-graded signal and a separate meta-training task supply are required (§4.3, §4.4); the policy needs a hard cap on live slots and must be able to learn commitment (§4.2). |
| F3 | The learned arm **restarts the recognized pathway every generation** (both studies). | Per-task adaptation state must persist across generations; restarts become a counted event (§4.1, C8). |
| F4 | A genesis pathway (`analog:prepend-k (k=0)`) produced a verified solve on every seed in the FM study — the first system-created pathway to do so. | Genesis stays; retention becomes evidence-gated (§4.6). |
| F5 | **No library entry was ever adopted** in any RSI-2 or RSI-3 arm; VALIDATION never moved. The repository's own stated target property: *a VALIDATION gain on every seed at B_eval = 64, which requires RSI-2's abstraction step to adopt at least one library entry.* | This is the transfer problem in the repository's own words. Allocation alone cannot produce it; §4.7 defines what RSI-4 may do about it without touching the MDL gate. |
| F6 | The learned FM arm peaked at ~4.5 GB on a 7 GB machine and cost 4.42× RSI-2's CPU. | Hard resource caps are registered (§8): ≤ 3 GB RSS per worker, learned arms run sequentially, live slots capped. |
| F7 | RSI-3's open problem 3: no verifier signal denser than one bit per solved task. | RSI-4 does **not** claim to solve this; it adds a *public-example* channel (§4.4), which is a different signal, and says so. |

---

## 3. Design responses (R1–R6)

- **R1 — Two-timescale memory.** A *fast store* (per-task adaptation state + policy hidden state; persists across windows and generations; never reset inside a run) and a *slow store* (policy weights `θ`, surprise model `φ`, pathway metadata) written **only** in a consolidation step. Memory feedback = fast store → policy at every window; slow store ← replay of the fast store at consolidation.
- **R2 — The processor is a recurrent allocation policy with an allocation-only action space.** It chooses which `(task, pathway)` slot resumes next. It never produces programs, never touches the grammar, never reads hidden examples or receipts' contents. This is what removes the self-grading surface.
- **R3 — Dense, legitimate reward from public examples; sparse verified bonus from receipts.** Public-example pass fraction is what RSI-2's search already computes; the policy only reads it. Verified receipts come only from `FrozenVerifier` at the generation boundary.
- **R4 — Outer loop trained on a frozen, witness-sealed dream-task supply; measured on held-out dreams and the external corpus.** The generator is committed and hashed before any policy code exists and is never edited afterwards (the Phase-AE lesson: a task generator co-designed with the searcher yields structurally guaranteed results). Generated tasks are `(task_spec, checker, witness)` triples in the Phase K sense, with the witness (the generating program) sealed from every mutable component.
- **R5 — Replay-based consolidation with surprise-weighted priority; no anchoring, no gate on learning (D1, D2).** Step size is modulated continuously by measured surprise (R3-style calibration), which is not a gate and not an anchor.
- **R6 — Evidence-gated pathway lifecycle, stated not hidden.** Create only from a verified solution; retain only on participation in a verified solve within `K_retain` generations; archive (never delete); re-wake on a later verified behavioural match; every transition logged.

---

## 4. Architecture of `rsi4/`

### 4.1 Fast store (`rsi4/fast_store.py`)
Per task `t` and pathway `p`: `cursor[t,p]` (enumeration rank reached; monotone unless an `invalidation` event is logged), `fingerprint[t,p]` (grammar fingerprint, via `rsi3.pathways`), `best_public[t]` ∈ [0,1], `last_progress_gen[t]`, `windows_spent[t]`, `gens_since_progress[t]`, `receipts[t]` (via `rsi3.memory.EpisodicMemory`), `failures` (via `rsi3.memory.FailureMemory`, always on), and `policy_hidden` (one vector per run, persisting across windows **and** generations).

Invalidation on grammar change: attempt cursor translation through the pathway; if impossible, log `invalidation(t, p, old_rank, reason)` and restart only that cursor. Known public failures are **never** re-charged (RSI-3 open problem 2's criterion, now a test).

### 4.2 Inner loop: memory-conditioned allocation policy (`rsi4/policy.py`)
- Input per candidate slot: normalized cursor depth, `best_public`, log-scaled `gens_since_progress`, pathway class and age, log budget remaining this generation, surprise-model estimate for the task, and the slot's live/dormant flag.
- Core: GRU-style recurrent cell, hidden size `H ≤ 32`, NumPy. Hidden state is never reset inside a run (A3 resets it).
- Output: logits over slots that are **live**. `max_live_slots` (registered; pilot value 12) caps how many `(task, pathway)` slots may hold an open search window at once; opening a new slot requires closing one. This is the structural fix for "a hundred live searches".
- Action: sample one live slot; run exactly one window of `W` candidates through `rsi3.resumable.ResumableSearch`; update the fast store; repeat until the generation cap (B_wake × |TRAIN|, unchanged) is spent.
- Static test: `policy.py` imports nothing from `rsi2`/`rsi3` except type definitions; its outputs are slot indices.

### 4.3 Outer loop: meta-training (`rsi4/dreams.py`, `rsi4/meta_train.py`)
- `dreams.py` — **frozen generator**, Phase-K style. Samples a program from RSI-2's *initial* grammar, samples inputs, computes outputs with `rsi2.evaluator`, emits a triple: `task_spec` (public examples), `checker` (hidden examples, routed through `FrozenVerifier` so receipts and the one-query rule hold), `witness` (the generating program, sealed: an AST-audit test asserts no `rsi4` module other than `dreams.py` references the witness store, mirroring Phase K's vault test). Deterministic per `(family_seed, task_index)`.
  - Family **A** (meta-train): `family_seed = 1001`. Family **B** (held-out): `family_seed = 2002`, disjoint program set, plus a registered primitive-subset shift. Stages **S1–S3** (continual): seeds 3001–3003, partitioned by the primitive signature of the generating program (define from `rsi2/terms.py`; register it).
  - Commit `dreams.py` and record `sha256` in `experiment_config.json` **before** `policy.py` exists. Tests: hash matches; output byte-identical across two processes with different controller states.
- Meta-episode (kept cheap on purpose): fresh fast store, `N_meta = 12` dream tasks, `G_meta = 3` generations, `B_meta = 32`. Return `J = Σ r_w` (§4.4). Pilot timing decides the final sizes; register them.
- Optimizer: antithetic ES (population 16, `σ = 0.05`, Adam on the ES gradient) over `θ`; REINFORCE-with-baseline as the registered fallback if the 30-minute pilot shows ES > 2× slower per unit improvement. Register the choice and the pilot numbers.
- Budget: meta-training wall-clock is a registered hard ceiling (pilot-derived; absolute ceiling 6 h on 2 cores), reported separately from evaluation compute.

### 4.4 Reward (`rsi4/reward.py`)
`r_w = max(0, Δ best_public[t]) + λ_solve · 1[verified receipt for t credited to this window]`, `λ_solve = 1.0`. Receipts are issued only by `FrozenVerifier` at the generation boundary and credited to the window that produced the public match. Nothing else is reward: no depth reward, no pathway-creation reward, nothing derived from the policy's or the surprise model's own predictions. A reward-purity test replays recorded traces and rejects any trace whose `best_public` did not come from `rsi2.evaluator`.

### 4.5 Surprise model and consolidation (`rsi4/surprise.py`, `rsi4/consolidate.py`)
- `φ`: logistic predictor of "task `t` receives a receipt this generation" from fast-store features (successor of `rsi3.value_model`), **refit from scratch on full replay** at every consolidation (D1).
- Surprise `s_t = |p̂_φ(t) − outcome_t|` at each generation boundary.
- Consolidation (every `C = 2` generations, inside the sleep phase, after RSI-2's own sleep): (i) prioritized replay from the fast store with weight ∝ `s_t + ε`; (ii) one outer-loop update of `θ` on the replayed episodes with step `η · mean(s)`; (iii) refit `φ`. **No anchoring term, no reference pull, no rollback.** Only `consolidate.py` writes the slow store (single-writer test).

### 4.6 Pathway lifecycle (`rsi4/pathways_lifecycle.py`, wraps `rsi3.pathways.PathwayRegistry`)
States `designer`, `genesis_active`, `genesis_archived`. Creation requires a receipt. Active → archived after `K_retain = 3` generations without participation in a verified solve. Archived → active on a later verified behavioural match. Archived pathways keep their cursors (nothing deleted). The policy sees active slots only. All transitions logged with generation and reason.

### 4.7 Transfer mechanism — what RSI-4 may do about F5 without touching the MDL gate
The library never grew because the abstraction step never saw enough structurally related verified solutions. RSI-4 may change **what the abstraction step is offered**, never **how it decides**:
- (a) deeper, more committed search on TRAIN (§4.2) yields more verified TRAIN solutions — the primary route;
- (b) **registered arm only:** verified solutions to Family-A dream tasks are offered to `rsi2.abstraction` as *candidate* fragments. Rule: the MDL compression that the unchanged gate measures is computed over **TRAIN solutions only**; dream solutions may propose fragments but are never part of the set whose compression is scored (otherwise self-similar dreams would force adoption — the structural-guarantee failure). A test enforces this partition.
- Attribution ledger: every adopted library entry records which tasks' solutions it was mined from. A VALIDATION solve is credited as **transfer** only if the entry it uses was mined from *other* tasks (Phase K crossing rule; own-solution exclusion).

### 4.8 Binding integrator — conditional retention
Define its input as verifier rejections ∪ public near-misses (`best_public ≥ 0.75`, no receipt). Count inputs in the pilot; if zero, remove the component from the module map and record that in `RESULTS.md`.

### 4.9 Module map

```
rsi4/
  __init__.py
  OWNER_DIRECTIVE.md        # this file, verbatim
  README.md
  ARCHITECTURE.md           # components, data flow, the D1/D2 inheritance, the §1.1 prior-art table
  PREDICTIONS.md            # pre-registered, committed before final runs
  experiment_config.json    # registered config incl. generator sha256 and resource caps
  RESULTS.md                # measured outcome, all comparisons, misses first
  dreams.py                 # frozen generator (hash registered first; witness store sealed)
  fast_store.py
  policy.py                 # allocation-only recurrent policy
  reward.py
  surprise.py
  consolidate.py            # single writer of the slow store
  pathways_lifecycle.py
  library_offer.py          # §4.7(b): candidate fragments to rsi2.abstraction; TRAIN-only MDL partition
  attribution.py            # library-entry provenance; crossing credit
  meta_train.py
  continual.py              # S1→S2→S3; ACC/BWT/FWT; checkpoint per stage
  loop.py                   # one generation
  experiment.py             # registered arms, seeds, stages, resource caps
  report.py
  pilot/                    # pilot timing, optimizer choice, integrator input count
  tests/
```

---

## 5. The three capabilities — definitions, metrics, protocols

Seeds `11, 22, 33` (add `44, 55` only if the registered wall-clock allows; register the list).

### 5.1 Meta-RL
With `θ` frozen after meta-training, performance on fresh tasks improves with experience *inside the run* through the fast store and hidden state only. Protocol: Family B, `G = 8`, same caps as RSI-3. Metrics: `solves_B@g8`; adaptation slope over generations 2–8; same on external TRAIN/VALIDATION. Passes only if the memory-ablated arm is worse (C1).

### 5.2 Transfer
- Held-out dream family: `solves_B@g8` vs UNIFORM_FM and vs the untrained policy.
- Per-generation curves on Family B and on external TRAIN, scored with the original core's metric suite (`compute_transfer_metrics`): **AUC** of the solve curve, **regret** against the best generation, and **recovery time** (first generation within 10 % of the best). Report them next to the solve counts; the pass rules in §6 use solve counts.
- External corpus: TRAIN g8 vs **8 / 8 / 8**; VALIDATION g8 vs RSI2's 2 / 1 / 2.
- Library transfer (the repository's target property): ≥ 1 library entry adopted through the unchanged MDL gate, and a VALIDATION solve credited by the crossing rule.
- Negative-transfer check: VALIDATION never below 2 / 1 / 2 on any seed.

### 5.3 Continual learning
Stages S1 → S2 → S3 presented sequentially; consolidation runs within each stage; checkpoint after each stage (§21 discipline). After stage `i`, evaluate with `θ` frozen on stages `1..i` and on external TRAIN/VALIDATION. GEM metrics with `R[i,j]` = solves on stage `j` after training through stage `i`, `b_j` = UNIFORM_FM's solves on stage `j`: `ACC = mean_j R[T,j]`, `BWT = mean_{j<T}(R[T,j] − R[j,j])`, `FWT = mean_{j>1}(R[j−1,j] − b_j)`. Report invalidation and archive counts per stage.

---

## 6. Arms, controls, decisive comparisons

### Arms (failure memory ON in every arm; same caps, seeds, corpus, verifier)

| Arm | Description | Isolates |
|---|---|---|
| A0 `RSI2` | unchanged `wake_sleep` | baseline |
| A1 `RSI3_UNIFORM_FM` | resumption + failure memory, even split | **the number to beat: 8 / 8 / 8** |
| A1′ `RSI3_FM` | RSI-3's learned controller + failure memory | the learned baseline (7 / 8 / 7) |
| A2 `RSI4_FULL` | recurrent policy, meta-trained on A, replay consolidation, evidence-gated pathways, live-slot cap, library offer OFF | the full design |
| A2L `RSI4_FULL_LIB` | A2 + §4.7(b) library offer | the transfer mechanism |
| A3 `RSI4_NO_MEMORY` | A2 with hidden state reset every window | meta-RL |
| A4 `RSI4_NO_METATRAIN` | A2 architecture, random `θ`, no outer loop | the outer loop |
| A5 `RSI4_SHUFFLED` | A2 meta-trained with rewards shuffled across windows | leakage / structural-gain null |
| A6 `RSI4_NAIVE_SEQ` | A2 on the continual stream with no replay prioritisation and consolidation on every generation | the continual mechanism |

### Decisive comparisons (register direction and Owner prior; score PASS/FAIL; any single-seed PASS is a FAIL)

| # | Comparison | Pass rule | Owner prior |
|---|---|---|---|
| C1 | A2 vs A3, Family B `solves_B@g8` | A2 > A3 on every seed | PASS |
| C2 | A2 vs A4, Family B | A2 > A4 on every seed | PASS |
| C3 | A2 vs A5, Family B | A2 > A5 on every seed | PASS (if FAIL: the gain is structural, say so) |
| C4 | A2 vs A1, external TRAIN g8 | A2 ≥ 9 / 9 / 9 | PASS at ~40 % |
| C5 | A2 vs A1, external VALIDATION g8 | A2 ≥ 2 / 1 / 2 on every seed | PASS |
| C6 | A2L, library transfer (F5 target property) | ≥ 1 entry adopted by the unchanged MDL gate on every seed **and** VALIDATION g8 > 2 / 1 / 2 on every seed with crossing credit | **FAIL at ~60 %** (registered as the honest prior; a PASS is the headline) |
| C7 | A2 vs A6, continual stream | `BWT(A2) > BWT(A6)` and `ACC(A2) ≥ ACC(A6)` on every seed | PASS |
| C8 | persistence | `invalidation` events per run < number of generations (RSI-3: restarts every generation) | PASS |
| C9 | commitment (F2) | A2 reaches enumeration rank ≥ 273 in the `prior` pathway on `index-k (k=3)` by generation ≤ 4 on every seed (UNIFORM_FM did at g4) | PASS |
| C10 | lifecycle | every retained genesis pathway has ≥ 1 verified solve; archive count reported | PASS (mechanism check) |

**Interpretation rules (verbatim into `PREDICTIONS.md`):**
- C1–C3 PASS, C4 FAIL → "meta-RL demonstrated on held-out dreams; no external-corpus gain over the even split."
- C4 PASS, C3 FAIL → "external gain exists but is not attributable to learning; treat as a structural gain."
- C6 FAIL → "the library did not grow; the repository's transfer target property remains open" — report adoption attempts, MDL deltas, and the attribution ledger.
- C7 FAIL → "replay consolidation did not reduce forgetting at this scale" — report BWT for both arms.
- C9 FAIL with C4 PASS → report which tasks supplied the gain; commitment was not the mechanism.

---

## 7. Pre-registration and honest-negative rules

1. Commit order, each its own commit: (a) `dreams.py` + hash; (b) scaffold + tests; (c) `pilot/` results; (d) `PREDICTIONS.md` + final `experiment_config.json` **before** any final run; (e) results + `RESULTS.md`.
2. `PREDICTIONS.md`: every arm, every comparison, pass rule, Owner prior, your own numeric prediction per comparison, interpretation rules, registered resource caps.
3. After the final runs, `RESULTS.md` scores every prediction, misses first, and restates open problems as Target Property + Criterion.
4. Re-runs: reason logged, original kept in `rsi4/results_archive/`. Determinism: each registered `(arm, seed, config)` re-run once must be byte-identical (RSI-3's standard; I.6).
5. No post-hoc arms; no tuning of budgets, seeds, thresholds or caps after (d) (VIII.7).

---

## 8. Resource caps (registered in `experiment_config.json`)

- Machine assumption: 2 CPU cores, 7 GB RAM (the FM study's machine).
- `max_rss_gb_per_worker = 3.0` (enforced by a watchdog; a run that exceeds it is stopped, logged, and re-run sequentially — never silently continued).
- Learned arms run **sequentially**; uniform arms may use `workers: 2`.
- `max_live_slots = 12` (pilot may change it before (d); frozen afterwards).
- Meta-training wall-clock ceiling: pilot-derived, ≤ 6 h absolute.
- Report CPU seconds and peak RSS per run, meta-training compute separately.

---

## 9. Implementation phases and done-gates

| Phase | Deliverable | Done-gate |
|---|---|---|
| P0 | Read §1 documents incl. the §1.1 sections of the original core; write `rsi4/OWNER_DIRECTIVE.md` (this file); branch from `main` | Branch exists; nothing outside `rsi4/` modified |
| P1 | `dreams.py` + hash + witness-seal AST audit + independence tests | Hash registered; tests pass; family/stage sample sizes logged |
| P2 | `fast_store.py`, `policy.py`, `reward.py`, `loop.py`; reproduce A1 | A1 reproduces **8 / 8 / 8** TRAIN and 2 / 1 / 2 VALIDATION exactly; persistence, no-restart, no-recharge, allocation-only tests pass |
| P3 | `surprise.py`, `consolidate.py`, `pathways_lifecycle.py`, `library_offer.py`, `attribution.py` | Single-writer test; lifecycle log; TRAIN-only MDL partition test; attribution test |
| P4 | `meta_train.py` pilot (30 min) + resource watchdog | Optimizer registered; caps registered; integrator input count measured |
| P5 | `PREDICTIONS.md` + `experiment_config.json` pushed | Commit hash recorded for the PR body |
| P6 | Final runs; `continual.py`; `RESULTS.md`; `report.py` | All comparisons scored; byte-identical re-run check; `quick-ci` and `full-evidence` green |
| P7 | `rsi4/README.md`, `rsi4/ARCHITECTURE.md`, **root `README.md` section "RSI-4"**; PR opened | PR matches the RSI-3 template; Owner review requested |

No P5 before P2–P4 gates pass; no P6 before P5 is pushed.

---

## 10. Tests required (`rsi4/tests/`)

- Sealed TEST: grep test — no file under `rsi4/` references the TEST split, its paths or task ids.
- Hidden examples: only `rsi3/verifier.py` reads them (reuse RSI-3's pattern against `rsi4/`).
- Generator frozen: hash matches; output identical across processes with different controller states.
- Witness seal: AST audit — no `rsi4` module except `dreams.py` references the witness store.
- Allocation-only policy: import audit; outputs are slot indices.
- Fast-store persistence: hidden state and cursors survive a generation boundary; cursors monotone per `(t,p)` unless an `invalidation` was logged.
- No-restart / no-recharge: `ResumableSearch` never called at rank 0 on a slot with a valid cursor; no program in `FailureMemory` is ever charged again, including across a grammar change (RSI-3 open problem 2).
- Live-slot cap: never more than `max_live_slots` open windows.
- Slow-store single writer: only `consolidate.py` mutates `θ`, `φ`, pathway metadata.
- No anchoring: `consolidate.py` contains no term that pulls `θ` toward a stored reference (source audit).
- Reward purity: formula check on recorded traces; a trace with `best_public` not produced by `rsi2.evaluator` is rejected.
- Receipt guard: forged, tampered, self-issued receipts rejected (reuse RSI-3 tests).
- MDL partition: the compression the gate scores is computed over TRAIN solutions only, with dream fragments present as candidates.
- Attribution: a VALIDATION solve using an entry mined only from its own task is **not** credited as transfer.
- Metrics: ACC/BWT/FWT match a hand-computed 3×3 example.
- Optimizer sanity: ES (or REINFORCE) improves a 10-arm toy bandit in ≤ 50 iterations.
- Resource watchdog: a synthetic over-cap allocation is stopped and logged.
- Untouched: `git diff main -- rsi2 rsi3 docs rsi_levels_metaforge_unified.py EVIDENCE.md OUTER_LOOP_CONSTITUTION.md .github` is empty; RSI-2's 470 and RSI-3's 39 tests still pass.

---

## 11. Delivery and prohibitions

- Branch `rsi4/meta-transfer-continual`; commits ordered as in §7; every commit message states what changed and what was not touched; attribution lines as the session's git reminder prescribes.
- PR to `main` in the RSI-3 template: *What this adds* (module table), *Not touched*, *Pre-registration* (commit hash), *Measured outcome* (arm table, C1–C10 scores, misses first), *Test plan* (commands and counts), the line "No claim of recursive self-improvement is made."
- **Update the root `README.md` in the same PR** (section "RSI-4" under the RSI-2/RSI-3 section; update the test-count line and the quick-start block). Do not leave it for a follow-up PR.
- **Do not merge.** Request Owner review and stop; merge only on the Owner's explicit instruction in chat.
- Prohibitions (cumulative with Article VIII): no self-grading; no modification of `dreams.py` after `policy.py` exists; no deletion of pathways, receipts, traces or archived results; no new reward terms or information channels; no post-hoc arms or tuning; no anchoring term in consolidation; no autonomous resource acquisition; forbidden phrases in code, docs, README and PR: "recursive self-improvement achieved", "AGI", "singularity", "unbounded"; on any conflict with the constitution or an inner directive, stop and report.

---

## Appendix A — `experiment_config.json` schema

```json
{
  "schema_version": 1,
  "generator_sha256": "<hash of rsi4/dreams.py>",
  "families": { "A": {"seed": 1001, "n_tasks": 36}, "B": {"seed": 2002, "n_tasks": 36, "primitive_shift": "<registered>"} },
  "stages": { "S1": {"seed": 3001, "signature": "<registered>"}, "S2": {"seed": 3002, "signature": "<registered>"}, "S3": {"seed": 3003, "signature": "<registered>"} },
  "generations": 8, "B_wake": 64, "B_eval": 64, "dreams": 16,
  "search": {"max_size": 12, "max_expansions": 20000, "step_budget": 2000},
  "failure_memory": true,
  "policy": {"hidden_size": 32, "reset_hidden_each_window": false, "max_live_slots": 12, "window_W": "<pilot>"},
  "reward": {"lambda_solve": 1.0, "clip_negative_delta": true},
  "consolidation": {"every_C_generations": 2, "eta": "<registered>", "replay_eps": 0.05, "anchoring": false},
  "pathways": {"K_retain": 3},
  "library_offer": {"enabled_in_arms": ["RSI4_FULL_LIB"], "mdl_scored_over": "TRAIN_only"},
  "meta_train": {"optimizer": "ES|REINFORCE", "population": 16, "sigma": 0.05, "N_meta": 12, "G_meta": 3, "B_meta": 32, "wallclock_cap_minutes": "<pilot, ≤ 360>"},
  "resources": {"max_rss_gb_per_worker": 3.0, "learned_arms_sequential": true, "workers_uniform": 2},
  "seeds": [11, 22, 33],
  "arms": ["RSI2", "RSI3_UNIFORM_FM", "RSI3_FM", "RSI4_FULL", "RSI4_FULL_LIB", "RSI4_NO_MEMORY", "RSI4_NO_METATRAIN", "RSI4_SHUFFLED", "RSI4_NAIVE_SEQ"]
}
```

## Appendix B — Why the three capabilities map to this architecture (for `rsi4/README.md`)

- **Meta-RL** is the inner loop: a fixed-weight recurrent policy whose hidden state and fast store carry the run's history, so adaptation happens in activations, not weights; the outer loop across Family A is what makes those activations useful (S4 discipline: select on A, audit on B). Ablating the hidden state (A3) is the test.
- **Transfer** has two parts here. Policy transfer: A → B and A → external corpus, against UNIFORM_FM, against an untrained policy, and against a shuffled-reward null. Library transfer: the repository's own target property — an entry adopted by the unchanged MDL gate and a VALIDATION solve credited under the Phase K crossing rule (library growth from other tasks only).
- **Continual learning** is the slow store's discipline under D1: writes only at consolidation, replay prioritized by measured surprise, no anchoring, no gate on learning; the naive sequential arm is the test and BWT is the number.
- The single principle under all three, inherited from the original core's meta-gate and from RSI-3: **the signal that permits a write comes from outside the loop that benefits from it** — a frozen verifier's receipts, a frozen generator's sealed witnesses, a public-example evaluator the policy cannot influence, and an MDL gate the library offer cannot tilt.
