# RSI-4 v3: Four-Loop Continual Learner on rsi-metaforge-core — Claude Code Directive

Nov 6, 2026 · Intelligence Research Project

## 0. Mandate

Build `rsi4/` (v3) in `sunghunkwag/rsi-metaforge-core`: a four-loop continual learner on top of the latest scored RSI-3 stack, judged by an external judge J. You implement, run and report. The Owner sets scope and merges.

| Item | Value |
| --- | --- |
| Repository | `sunghunkwag/rsi-metaforge-core` |
| Base | `rsi3/analogy` at `1e6868a` (2026-11-02), the latest scored state (FRESH and ANALOGY results). `main` is at `c4f0a86` (PR #26) and does not contain the rsi3 chain yet |
| Branch | `rsi4/four-loop`, created from the base |
| Package | `rsi4/`, sibling of `rsi2/` and `rsi3/` |
| PR base | `rsi3/analogy`, so the diff shows only this work. Retarget to `main` after the Owner merges the rsi3 chain |

**What this supersedes.** The v2 directive on `rsi4/meta-transfer-continual` (P0 skeleton only, set aside by the Owner on 2026-11-02). Copy it to `rsi4/archive/OWNER_DIRECTIVE_v2.md`. Do not reuse its arms or target numbers; they predate the rsi3 chain.

**Do not build on** the unscored work-in-progress branches `rsi3/run-compose-dev1` to `dev3`, `rsi3/run-curriculum-dev1` and `rsi3/run-analogy-dev2`, or on `swarm/adversarial-coevolution`, which is a separate line and stays untouched.

**Read-only, never edited**

- `rsi_levels_metaforge_unified.py` (the original core), `docs/`, `EVIDENCE.md`, `OUTER_LOOP_CONSTITUTION.md`, existing workflows, every frozen instrument and all committed evidence.
- `rsi2/` and `rsi3/` are imported read-only and never edited, the rule RSI-3 followed for RSI-2.
- One new file is allowed outside `rsi4/`: `.github/workflows/rsi4-runs.yml`, modelled on `rsi3-runs.yml` and triggered by branches named `rsi4/run-*`. List it under "Touched" in the PR.

**Fixed rules**

- Python standard library and NumPy only. No network at run time. No transformer or attention layers.
- RSI-2's freeze stands: no new primitives, no hand-written library entries or heuristics, no change to the evaluator or to the MDL adoption gate.
- TEST (12 tasks) is never opened, referenced or counted.
- Exposed partitions are report-only: VALIDATION, RESERVE-NEAR, RESERVE-FAR, RESERVE-FAR2, FRESH-1, FRESH-2 and COMPOSE-24. In rsi4 they never gate, tune or select anything.
- Hidden examples are read only by `rsi3.verifier.FrozenVerifier` and by J (§5). One verifier query per task per generation; every positive label needs an authentic receipt.
- `OUTER_LOOP_CONSTITUTION.md` Article VIII applies: no tuning after registration, limitations written as Target Property + Criterion, stop and report on any conflict. Like the rsi2 and rsi3 owner directives, this is a direct Owner directive, not a work order under the constitution.
- Register predictions before every final run, score misses first, and treat an honest null as a valid result.
- Claim boundary: the measured trajectory at the registered budgets, seeds and pools, stated in the form rsi3's results files use.

## 1. Starting point

The rsi3 chain took TRAIN from 6/36 to 29/36. Its best learned solvers transfer to new single routines and pipelines, but only modestly, and every held-out partition the repository owns has now been read. Read these files in full before writing code: `rsi3/ARCHITECTURE.md`, `rsi3/OWNER_DIRECTIVE.md`, every `rsi3/*RESULTS*.md` and `PREDICTIONS_*.md` on the base, `rsi3/fresh.py`, `rsi3/longrun.py`, `rsi3/metarl.py`, `rsi3/continuity.py`, `.github/workflows/rsi3-runs.yml`.

### Measured trajectory (TRAIN, of 36)

| Study (arm) | TRAIN | Learned solver on held-out VALIDATION | Results file |
| --- | --- | --- | --- |
| RSI-2 baseline | 6 | 2 / 1 / 2 (plain) | `rsi3/RESULTS.md` |
| Failure memory (UNIFORM\_FM) | 8 | unchanged | `rsi3/FAILURE_MEMORY_RESULTS.md` |
| Concept invention | 10 (vs 9, 12 generations) | unchanged | `rsi3/INVENTION_RESULTS.md` |
| Meta-RL + decomposition (META) | 17 | 4 / 12 | `rsi3/METARL_RESULTS.md` |
| Cascade (META\_CONJ) | 21 | 5 / 12 | `rsi3/CASCADE_RESULTS.md` |
| Behavioural search (META\_BEH) | 25 | 4 / 12 (library-free pool: 7 / 12) | `rsi3/BEHAVE_RESULTS.md` |
| Behavioural fold (META\_BEH\_FOLD) | 29 | 5 / 12 | `rsi3/BEHAVE_FOLD_RESULTS.md` |
| Honest practice (META\_HONEST) | 29 | 9 / 12, VALIDATION already exposed | `rsi3/HONEST_RESULTS.md` |

### Latest scored arms on exposed partitions (every seed unless noted)

| Arm | FRESH-1 (of 33) | FRESH-2 (of 100) | RESERVE-NEAR (of 100) | RESERVE-FAR2 (of 21) | COMPOSE-24 | TRAIN CPU (s) |
| --- | --- | --- | --- | --- | --- | --- |
| META\_HONEST | 7 | 9 | 56–57 | 5 | 0 | about 3,540 |
| META\_ANALOGY\_P | 7 | 14 | 61 | 6 | 2 | about 5,330 |
| META\_COMPOSE | 7 | 14 | 60 | 6 | 9 | about 7,460 |

Source: `rsi3/ANALOGY_RESULTS.md` and `rsi3/FRESH_RESULTS.md` on the base. A 30-generation study was suspended at a plateau of 10/36 and a self-continuity study was abandoned; both are unscored.

### Facts that fix this design

| # | Measured fact | Consequence here |
| --- | --- | --- |
| F1 | Gains came from new search actions and honest credit. RSI-3's learned budget controller alone was null. | Loops 1 and 4 act on how actions are chosen and credited, not on a new allocator |
| F2 | On new shapes the policy spends all 64 candidates on skeleton chunks before the action that fits (RESERVE-FAR2: `behave:filter` never got a turn on `remove-mod-k`; all 64 went to the fold skeleton on `count-k`) | This is loop 1's target: C must give a fitting action its turn when observed progress contradicts the policy's prediction |
| F3 | A learned library raised TRAIN and lowered held-out (BEHAVE: 25/36 TRAIN, 4/12 held-out vs 7/12 without the library) | Discrete sleep changes are where a J check earns its place (rsi3 D2) |
| F4 | Owner decision, 2026-10-29: a guard that only prevents losses cannot produce a capability leap; `ContinuityGuard` is off in every arm | J's sleep check is measurement, not the source of gain. Gains are expected from loops 1, 2 and 4, and an ablation prices the check |
| F5 | rsi3 D1: replay, not parameter anchoring | No anchoring term anywhere; no rollback on continuous learning (policy and value refits) |
| F6 | Every corpus partition, FRESH-1 and FRESH-2 have been read. Only 33 single routines in `list_tasks2.json` qualified for FRESH-1; the FRESH-2 pool held 5,835 two-stage pipelines, of which 100 were used | J's new pools come from unused pipeline records of `list_tasks2.json` |
| F7 | Registered runs share one TRAIN trajectory across seeds 11, 22 and 33 (`shared_seeds`); results are almost identical across seeds | Statistics are paired over tasks, not seeds |
| F8 | Plain VALIDATION (RSI-2 `assess`) never moved; held-out gains appear only with the learned solver (`longrun.agent_validation`) | J evaluates each arm's learned solver at B\_eval = 64 |
| F9 | Runs cost about an hour of CPU per arm and seed; the learned FM arm peaked at 4.5 GB RSS | Long runs go to GitHub Actions; RSS is capped per worker |

## 2. Components mapped onto the repository

Five of the seven components already exist in rsi2 and rsi3. rsi4 adds C (a surprise-driven compute controller), a fast store for F, an offer rule for G, and the `rsi4/judge/` half of J.

| Part | Repository modules | Role here | Updated by |
| --- | --- | --- | --- |
| S: slow knowledge | RSI-2 grammar and MDL library; invented concepts (`rsi3.selfmodel`, `Runtime.invent`); RSI-2 recognition model | What every search draws from | Loop 3 only, behind RSI-2's MDL gate, verifier-confirmed concept adoption, and J's sleep check |
| M: sparse memory | `rsi3.memory.EpisodicMemory` and `FailureMemory`; `rsi3.pathways.PathwayRegistry` (genesis `analog:<S>`, conjugates, behave pathways); the chunk-episode replay of `rsi3.metarl.MetaPolicy` | Verified experience and remembered failures | Loop 2, receipt-gated |
| F: fast state | `rsi3.resumable.ResumableSearch` frontiers; new `rsi4/fast_store.py` holding, per task, the actions tried, chunks spent per action, best public pass fraction and generations since progress | Within-task adaptation that persists across chunks and generations | Loop 1, every chunk; never by gradient |
| C: compute controller | New `rsi4/compute.py`, wrapping the MetaPolicy's action choice in `Runtime._meta_wake` (training) and `longrun.agent_validation` (held-out time) | Moves a task's candidate budget to an untried fitting action when observed public progress contradicts the policy's prediction | Rule θ\_C, only through loop 4 |
| E: experience | MetaPolicy chunk episodes, extended with predicted yield, observed public progress and surprise | Input to loops 2 and 3 | Loop 1 appends |
| G: write gate | rsi3's receipt guard (memory entry); the genesis rule; new `rsi4/offer.py`, which decides which verified programs are offered to concept invention and to RSI-2's abstraction step | What is written, and what sleep may consolidate | The receipt rule is fixed; offer parameters θ\_G only through loop 4 |
| J: judge | `rsi3.verifier.FrozenVerifier` for receipts on training tasks, plus new `rsi4/judge/` for pools, seed registry, evaluation, the sleep check and rule adoption | Measures; keeps or reverts discrete sleep changes; adopts rules | Never by the system |

**Surprise.** After each chunk of task t with action a: s = |p̂ − y|. p̂ is the MetaPolicy's own score for (shape of t, a), mapped to \[0, 1\]; read `rsi3/metarl.py` for the exact quantity and register it. y = 1 if the chunk raised t's best public pass fraction or produced a public match, else 0. Both inputs come from public examples and the policy; neither reads hidden examples or receipt contents.

**C's rule (default).** Keep the policy's choice unless the task's accumulated surprise on its current action exceeds θ\_C.threshold while some fitting action (one whose skeleton or behavioural problem matches the task's public shape) has had no chunk. In that case the next chunk goes to the untried fitting action with the highest policy score. At most θ\_C.floor\_chunks chunks per task are moved this way. The logical budget never changes: B\_wake per task at training time, B\_eval = 64 at held-out time.

**Rules**

- S changes only in loop 3.
- MetaPolicy and the value model are still refit from scratch on full replay every generation (D1). No anchoring term and no rollback on them.
- C and the fast store read public examples, policy scores and their own history only.

## 3. The four loops

The loops run on the repository's own clock: chunks inside a task's budget, generations, and rule rounds. Every change from loops 2 to 4 passes either the frozen verifier or J.

| Loop | Runs every | What changes | Kept by |
| --- | --- | --- | --- |
| 1. Instant adaptation | chunk (meta.chunk = 16 candidates) | F, E, and which action gets the next chunk | Nothing to keep; no weights change |
| 2. Experience writing | generation | M (receipts, failures, genesis pathways); MetaPolicy and value model refit on full replay | Receipt guard only (D1, D2) |
| 3. Sleep | generation, after wake | S: library entries, invented concepts, grammar fit, recognition | RSI-2's MDL gate and the verifier, then J's sleep check on discrete changes |
| 4. Rule improvement | rule round (a block of full runs) | θ\_C, θ\_G and selected rsi3 config keys | J's select-then-confirm test |

&#91;embedded content: four loops · J decides what stays\]

Loop 1 changes no weights. Loop 2 writes only what carries a verifier receipt. A discrete change to S in loop 3, and every rule change in loop 4, stays only if J accepts it.

### Loop 1: instant adaptation (inside a task's budget)

At training time (`Runtime._meta_wake`) and at held-out time (`longrun.agent_validation`), each task's budget is spent in chunks. Before each chunk the MetaPolicy proposes an action from the task's public shape and its history on this task, and C may override it (§2). The chunk runs through the existing action: prior, invented, skeleton, behave, conjugate, or analogy where the arm enables it. F and E then update. Resumption and failure memory stay on.

### Loop 2: experience writing (each generation)

1. FrozenVerifier issues at most one receipt per task. Receipts enter `EpisodicMemory`; public failures enter `FailureMemory`.
2. Genesis: every verified solution creates a dormant `analog:<S>` pathway (D3), and conjugates refresh.
3. MetaPolicy and the value model refit from scratch on full replay of chunk episodes, credited by actual outcomes (honest practice).
4. The receipt guard is the only gate. No rollback, no anchoring (D1, D2).

### Loop 3: sleep (each generation, after wake)

1. G's offer rule chooses which verified programs are offered to concept invention and to RSI-2's abstraction step. Only solutions to training tasks (TRAIN and stage-train, §4) are offered, never J pool tasks.
2. Sleep runs as in the base arm: RSI-2 abstraction with its unchanged MDL gate, grammar fit, dreams and recognition. Concept invention admits a concept only through a verified solve.
3. If S changed discretely (a library entry or concept added or removed), J runs the sleep check (§5) on a snapshot taken before sleep and reverts the change when the check says so. Reuse the restore mechanics of `rsi3.continuity.ContinuityGuard` by import; do not edit it.
4. Grammar refits without a discrete change are not checked (D2).
5. Log every check: generation, change, probe solves before and after, decision.

### Loop 4: rule improvement (each round)

A (1+λ) evolution strategy with λ = 4 proposes rule vectors inside fixed bounds. J rejects any candidate outside them and alone decides adoption (§5). Rules come in two classes:

- **Held-out-time rules** change only how the learned solver spends B\_eval. No retraining is needed, so they are cheap.
- **Training-time rules** need a full retrain per candidate, about one CPU-hour per seed for the base arm. Run them only within the registered budget (§8).

| Rule | Class | Range | Default (base arm) |
| --- | --- | --- | --- |
| θ\_C.threshold | both | 0.5 to 3.0 | 1.5 |
| θ\_C.floor\_chunks | both | 0 to 3 | 1 |
| meta.chunk | held-out, if `agent_validation` reads it; otherwise training | 8, 16, 32 | 16 |
| controller.exploration | training | 0.1 to 0.6 | 0.3 |
| meta.selfplay | training | 128, 256, 512 | 256 |
| invention.concept\_weight | training | 0.05 to 0.3 | 0.1 |
| dreams | training | 8, 16, 32 | 16 |
| θ\_G.offer\_min\_solves (verified uses before a program is offered to sleep) | training | 1, 2, 3 | 1 |

Never in the search space: B\_wake, B\_eval, search limits, the verifier, the MDL gate, the pools, δ\_sleep, the adoption α, the regression budget and the seeds.

### Pseudocode

```
for each task t (training: this generation's tasks; held-out: each pool task):
    budget = B_wake share if training else B_eval            # 64 at held-out time
    while budget > 0:                                        # loop 1
        a = policy.propose(shape(t), fast_store[t])
        a = C.maybe_override(a, fast_store[t], theta_C)      # surprise floor
        y = run_chunk(t, a, size=meta.chunk)                 # public examples only
        fast_store[t].update(a, y); E.append(t, a, p_hat, y)
        budget -= meta.chunk

end of generation:                                           # loop 2
    receipts = FrozenVerifier.verify(one_program_per_task)
    memory.write(receipts); failure_memory.write(public_failures)
    pathways.genesis(receipts); pathways.refresh_conjugates()
    policy.refit_from_scratch(E); value_model.refit_from_scratch(memory)

sleep:                                                       # loop 3
    snap = S.snapshot()
    offered = G.offer(verified_training_programs, theta_G)
    S = base_sleep(S, offered)    # MDL gate, grammar fit, dreams, recognition, invention
    if S.discrete_change(snap) and J.sleep_check(snap, S) == "revert":
        S = snap

every rule round:                                            # loop 4, decided by J
    cands = ES.propose(theta, lam=4, bounds=RULE_BOUNDS)
    best  = J.select(cands, selection_pool)
    if J.confirm(best, incumbent=theta, pool=confirmation_pool):
        theta = best
    J.burn(confirmation_pool)                                # never reused
```

## 4. Task streams and pools

Every new task comes from DreamCoder's `data/list_tasks2.json` (`ellisk42/ec` at `cb0e63f`, MIT, 174,258 records), the file and commit FRESH used. Build every pool with the rules in `rsi3/fresh.py`: RSI-2-supported declared types, at least 9 distinct inputs, the first 8 distinct inputs public and the rest hidden.

**Exclusions, applied before any draw.** Every record in FRESH-1, FRESH-2 or COMPOSE-24, and every record whose corpus-style name is a name in RSI-2's corpus, matched by name as `fresh.py` does. TEST content is never read.

**Shapes.** Two-stage pipelines (5,835 in the FRESH-2 pool, 100 already used) and three-stage pipelines (count them in Phase 0). Single routines are exhausted (F6).

### Training stream

1. TRAIN (36 tasks), 16 generations, exactly as the base arm. This reproduces the registered base checkpoint (Gate 0).
2. Continual stages S1 → S2 → S3. Split the routine names that occur in eligible two-stage pipelines into three disjoint groups by a registered rule: group = sha256(name + J seed) mod 3. Stage i holds pipelines whose two routines both lie in group i.
   - Each stage has 36 stage-train tasks, which the system learns on with one verifier query per task per generation, and 100 stage-eval tasks, which only J runs.
   - 8 generations per stage.
   - If a group cannot supply 136 tasks, shrink every stage by the same amount before registration and record the counts.

### J pools

J draws every pool after the stages, from the remaining eligible records, with its own seed. Pools are disjoint, written to `rsi4/judge/pools/` with a sha256 manifest, and committed in Phase 0 before any rsi4 agent code exists.

| Pool | Size | Used for | Reuse |
| --- | --- | --- | --- |
| Stage-eval S1 to S3 | 3 × 100 | The R\[i\]\[j\] metrics (§6) | Fixed; never tunes anything |
| Probe | 60 two-stage | Loop 3 sleep check | Fixed per run. It feeds a decision, so it never produces a reported result |
| Selection | 100 per round | Loop 4 screening | Fresh each round |
| Confirmation | 200 per round | Loop 4 adoption | Single use, then burned |
| Final test | 200 two-stage + 100 three-stage | One run at the end of Phase 4 | Single use |

With 3 rule rounds this uses about 1,570 two-stage records of roughly 5,700 eligible, plus 100 three-stage records.

**Exposed partitions, report-only.** Keep evaluating VALIDATION (learned solver), RESERVE-NEAR, RESERVE-FAR2, FRESH-1, FRESH-2 and COMPOSE-24 with `rsi3.reserve_eval` so results stay comparable with rsi3. They never enter a decision.

**Solved** means the program passes every public and hidden example of the task, as checked by J.

## 5. The judge J

J has two halves, and nothing the system controls can reach either of them. `rsi3.verifier.FrozenVerifier` issues receipts on training tasks, unchanged. `rsi4/judge/` owns the pools, the seed registry, every evaluation that produces a reported number, the sleep check and rule adoption.

### Isolation

- `rsi4/judge/` runs in its own process (`multiprocessing`, spawn start method). Agent-side code sends it a checkpoint path and a request. J loads a read-only copy, runs the evaluation itself with `longrun.agent_validation` semantics, and returns counts and per-task outcomes.
- No module under `rsi4/` outside `judge/` may import `rsi4.judge` or open `rsi4/judge/pools/`. Extend rsi3's sealing-test pattern (`rsi3/tests/test_sealing.py`) into an AST and path audit for this.
- J's seed lives in a file only the judge process opens. The agent process environment never holds it.
- At run start and end, J hashes `rsi4/judge/**` and the registered config. A mismatch voids the run.
- Every J decision is appended to a hash-chained `judge_log.jsonl`, the ledger pattern of Phase K and swarm.

### Sleep check (loop 3)

- Runs only when sleep changed S discretely.
- J evaluates the learned solver with S before and S after on the 60 probe tasks at B\_eval = 64, with the same seeds. The runtime is deterministic, so the comparison has no sampling noise; red-team test R3 confirms this.
- Per probe task, a win is solved only after the change and a loss is solved only before. Revert when losses − wins ≥ 2; otherwise keep.
- Also log, for reporting only, whether the solver can still re-derive the receipted training tasks (reuse `ContinuityGuard`'s re-derivation check).
- State its purpose in `rsi4/ARCHITECTURE.md`: it prices discrete changes; it is not the mechanism expected to produce gains (F4). Ablation A4 (§7) measures what it costs.

### Rule adoption (loop 4): select, then confirm

Selection and confirmation use different tasks, because the best of several candidates looks better than it is.

1. **Selection.** The candidates and the incumbent run the round's 100 selection tasks. The candidate with the most solves moves on. If none beats the incumbent, the round ends without a confirmation test.
2. **Confirmation.** The selected candidate and the incumbent run the round's 200 confirmation tasks. Each task is one pair: (incumbent solved, candidate solved), where solved means solved on at least 2 of the 3 seeds (F7). J adopts the candidate only if all three hold:
   1. All 200 pairs were evaluated.
   2. An exact one-sided sign test on the discordant pairs gives p ≤ 0.05. For example, 8 wins against 1 loss gives p = 0.020; 7 against 2 gives p = 0.090.
   3. Regression budget: at most 5 losses.
3. **Burn.** The confirmation tasks are marked used and never drawn again.

This is the test in the EGRL prototype's `promote_only_on_paired_evidence`, with one task as one canary pair. Re-implement it in `rsi4/judge/adopt.py`; do not import the prototype.

Training-time candidates are trained through the same stream (TRAIN, then S1 to S3) as the incumbent before they are evaluated. Each round can falsely adopt with probability up to 0.05, so report every round and adoption. The claim that loop 4 helps rests on the final test (Gate 4), not on the adoption count.

## 6. Metrics and gates

Every threshold below goes into `rsi4/PREDICTIONS_P<k>.md`, committed before that phase's final runs, together with your own numeric prediction for each comparison. Scoring follows rsi3's results files: misses first, no reinterpretation.

### Score matrix

R\[i\]\[j\] = stage-eval tasks of stage j (of 100) solved by the learned solver at B\_eval = 64 after training through stage i. i = 0 is the checkpoint after TRAIN only, the base arm's registered checkpoint. A task counts as solved when at least 2 of the 3 seeds solve it (F7); per-seed counts are reported beside it.

| Metric | Definition | Good direction |
| --- | --- | --- |
| ACC | Mean over j of R\[3\]\[j\] | Higher |
| BWT | Mean over j in {1, 2} of R\[3\]\[j\] − R\[j\]\[j\]; negative means forgetting | Higher |
| FGT | Mean over j in {1, 2} of max(0, max over i in \[j, 2\] of R\[i\]\[j\] − R\[3\]\[j\]) | Lower |
| FWT | Mean over j in {2, 3} of R\[j−1\]\[j\] − R\[0\]\[j\]: the gain on a stage before training on it | Higher |
| Plasticity | Stage-train receipts per stage | Not below baseline |
| TRAIN retention | Receipted TRAIN tasks the final solver re-derives at B\_eval | Reported |
| Floor events | Per task: chunks C moved, and whether the moved action produced the solve | Mechanism check of F2 |
| Final-test effect | Final-test solves, θ\* against θ₀, as task pairs | Higher |

### Gates

**Gate 0, end of Phase 0: the harness works.**

- The pools are built, disjoint and hashed, and the exclusion audit passes.
- Red-team tests R1 to R3 (§9) pass.

**Gate 1, end of Phase 1: the base reproduces and forgetting is measurable.**

- META\_HONEST under its registered config reproduces TRAIN 29/36 and FRESH-1 7/33 on every seed, byte-identical to the base's registered result files.
- B1, the base arm continued unchanged through S1 to S3, is measured. If its mean FGT is at least 3 tasks, forgetting is live and the FGT and BWT comparisons below gate. If FGT is under 3, record "no measurable forgetting in this substrate": the FGT and BWT comparisons become report-only and the continual claim rests on FWT. This contingency is registered now, before any stage run.

**Gate 2, end of Phase 2: loops 1 and 2 (arm L12).**

- G2a, primary: on the 300 stage-eval tasks after S3, L12 beats B1 under the exact one-sided sign test on task pairs, p ≤ 0.05.
- G2b: L12's TRAIN is at least 28/36 on every seed.
- G2c, mechanism: report floor events. Register a prediction for the number of solves produced by moved chunks.

**Gate 3, end of Phase 3: does the sleep check pay? (arm L123)**

- Red-team test R4 passes before L123's final runs. The sleep check stays on for Phase 4 only if L123 beats L12 on the 300 stage-eval tasks (sign test, p ≤ 0.05), or, when forgetting is live, lowers FGT by at least 2 tasks.
- Otherwise turn it off for Phase 4 and record why. A guard that does not pay is not kept (F4).

**Gate 4, end of Phase 4: loop 4.**

- Red-team tests R5 to R7 pass before the first real round.
- On the 300 final-test tasks, θ\* beats θ₀ under the exact one-sided sign test on task pairs, p ≤ 0.05, with at most 8 losses.
- If loop 4 adopted nothing, the result is the null "loop 4 adopted no rule". Report it; do not rerun with changed settings.

## 7. Arms, ablations, compute parity, statistics

Every arm starts from META\_HONEST's registered config (`rsi3/experiment_config_honest.json`) with failure memory, resumption and honest practice on, and runs the same stream: TRAIN, then S1 to S3.

### Arms

| Arm | What it is | What it isolates |
| --- | --- | --- |
| B0 BASE | META\_HONEST after TRAIN only (R\[0\]\[·\]) | Reference for FWT |
| B1 BASE\_SEQ | META\_HONEST continued through S1 to S3, unchanged | Naive continual baseline; the number to beat |
| B2 ANALOGY\_SEQ | META\_ANALOGY\_P continued through S1 to S3 | Strongest scored arm on pipelines (FRESH-2 14/100). Reported, not gating, because it costs 1.5× the CPU |
| L12 | B1 + C + fast store | Loops 1 and 2 |
| L123 | L12 + sleep check | Loop 3 |
| FULL | L123, or L12 if Gate 3 turned the check off, with θ\* from loop 4 | Loop 4 |

### Ablations

| Ablation | Change | Phase |
| --- | --- | --- |
| A1 Fixed floor | C moves the same number of chunks at a fixed point (after the second chunk), ignoring surprise | 2 |
| A2 C held-out only | C off during training, on at held-out time | 2 |
| A3 No fast store | Fast store reset every generation | 2 |
| A4 Placebo revert | Discrete sleep changes reverted at random, at L123's measured revert rate | 3 |
| A7 Placebo adoption | Confirmation on a candidate identical to the incumbent | 4 (red team R5) |

### Compute parity

- Logical budgets are identical across arms: B\_wake = B\_eval = 64, meta.chunk, search limits, and 16 + 3 × 8 generations.
- C moves chunks between actions; it never adds candidates.
- J's evaluations are excluded from the budgets and logged separately.
- Report CPU seconds and peak RSS per run (D5). Cap RSS at 3 GB per worker; a watchdog stops and logs any breach rather than letting the run continue.
- Long runs go to GitHub Actions through `rsi4-runs.yml` with the `shared_seeds` protocol and plan files `rsi4/runs/<name>.json`, as rsi3 does.

### Statistics

- The unit is the task. Primary comparisons are exact one-sided sign tests on task pairs, with the direction registered.
- Holm correction across each gate's primary comparisons.
- ACC, BWT, FGT and FWT carry 95% bootstrap CIs over tasks (10,000 resamples).
- Per-seed results are always reported beside the pooled ones.
- No task or seed is excluded after the draw. A crashed run is rerun on the same seed and the crash is logged.

## 8. Build order and gates

Build in five phases. Each ends with its gate (§6) and a results file, and the next phase starts only after that file is committed. If a gate fails, write the failure report with every number and stop. The Owner decides what happens next; do not retry with changed thresholds, pools or seeds.

1. **Phase 0: harness before agent**
   1. Read the files listed in §1. Create `rsi4/four-loop` from `rsi3/analogy` at `1e6868a`. Archive the v2 directive and commit this directive verbatim as `rsi4/OWNER_DIRECTIVE.md`.
   2. Fetch `list_tasks2.json` once at `cb0e63f` and check that it has 174,258 records. Build the stages and J pools by the rules in §4, count the three-stage pipelines, and commit the pools, the sha256 manifest and the builder `rsi4/judge/pools.py`.
   3. Build `rsi4/judge/`: process isolation, seed registry, evaluation, sleep check, adoption test, ledger, and the AST and path audit.
   4. Add `.github/workflows/rsi4-runs.yml`.
   5. Run red-team tests R1 to R3 and Gate 0. Commit `rsi4/RESULTS_P0.md`.
2. **Phase 1: reproduce the base, measure forgetting**
   1. Commit `rsi4/PREDICTIONS_P1.md`.
   2. Run B0, B1 and B2 on Actions. Run Gate 1. Commit `rsi4/RESULTS_P1.md`.
3. **Phase 2: loops 1 and 2**
   1. Write `fast_store.py`, `compute.py` and `loop.py`. `loop.py` wraps rsi3's `Runtime` by composition or subclassing; it never edits rsi3. Add unit tests.
   2. Commit `rsi4/PREDICTIONS_P2.md`. Run L12 and A1 to A3. Run Gate 2. Commit `rsi4/RESULTS_P2.md`.
4. **Phase 3: loop 3**
   1. Write `offer.py` and the sleep-check client in `loop.py`.
   2. Commit `rsi4/PREDICTIONS_P3.md`. Run red-team test R4, then L123 and A4. Run Gate 3. Commit `rsi4/RESULTS_P3.md`.
5. **Phase 4: loop 4**
   1. Write `rules.py`: the evolution-strategy proposer and the rule bounds.
   2. Run red-team tests R5 to R7.
   3. Commit `rsi4/PREDICTIONS_P4.md`. Run 3 rule rounds, held-out-time rules first.
   4. Run the final test exactly once. Run Gate 4. Commit `rsi4/RESULTS_P4.md`.

**Commit order.** Each in its own commit, as rsi3 did: directive; pools and manifest; judge and its tests; workflow. Then per phase: code and tests; predictions; run plan; results. Each phase's results commit also updates the root `README.md`.

**Runtime limits.** A GitHub-hosted job stops at 6 hours. One arm through TRAIN and three stages is several CPU-hours per seed. Checkpoint after TRAIN and after every stage, and chain jobs from the checkpoints when a run would exceed the limit.

## 9. Red-team tests

A safeguard that has never caught a planted fault is not trusted. Each test plants a fault or a null and states what must happen. Tests live in `rsi4/tests/` and run in the package suite.

| Test | Planted fault or null | Pass condition | Phase |
| --- | --- | --- | --- |
| R1 Sealing | (a) A module under `rsi4/`, outside `judge/`, imports `rsi4.judge` or opens `judge/pools/`. (b) A judge file is modified during a run. (c) A self-issued or tampered receipt | (a) The audit fails the build. (b) The hash check voids the run. (c) The receipt is rejected, reusing rsi3's verifier-memory tests | 0 |
| R2 Exposure | Inspect every pool record | No record is in FRESH-1, FRESH-2 or COMPOSE-24, and no name is in RSI-2's corpus. Stages and pools are pairwise disjoint. The final-test pool shows zero draws | 0 |
| R3 Instruments | (a) The same checkpoint and request sent to J twice. (b) A synthetic worker over the RSS cap | (a) Byte-identical outputs, so the sleep check has no sampling noise. (b) The watchdog stops it and logs the breach | 0 |
| R4 Sleep check | (a) A planted library entry with high weight that pushes a frequently used primitive down the enumeration order. (b) A planted entry no probe solution uses | (a) Reverted. (b) Kept | 3 |
| R5 Placebo adoption | (a) A candidate identical to the incumbent. (b) 10,000 simulated null rounds at the observed discordance rate | (a) Every pair ties and nothing is adopted. (b) Adoption rate of 0.05 or less | 4 |
| R6 Positive control | An incumbent restricted to the `prior` action at held-out time, against θ₀. The restriction is outside the rule bounds and exists only in this test | J adopts θ₀ | 4 |
| R7 Pool hygiene | Request a burned confirmation pool; replay the ledger | J refuses the pool. Selection and confirmation pools are disjoint. Replaying `judge_log.jsonl` reproduces every decision | 4 |

R4 runs in Phase 3, before L123's final runs, so the sleep check has caught a planted fault before anything relies on it. If any red-team test fails, fix the harness and rerun every red-team test of that phase, not only the failed one, and record both in the phase results file.

## 10. Layout, delivery, prohibitions

All new code lives under `rsi4/`, with J's code physically separate from what it judges.

```
rsi4/
  OWNER_DIRECTIVE.md              this directive, verbatim
  archive/OWNER_DIRECTIVE_v2.md   set aside 2026-11-02
  README.md, ARCHITECTURE.md
  PREDICTIONS_P1.md .. P4.md, RESULTS_P0.md .. P4.md
  experiment_config_*.json        one per arm family
  runs/<name>.json                Actions run plans
  fast_store.py                   F
  compute.py                      C
  offer.py                        G's offer rule
  loop.py                         wraps rsi3's Runtime; loops 1 to 3
  rules.py                        loop 4 proposer and bounds
  stages.py                       continual stream driver and checkpoints
  experiment.py, report.py
  judge/
    pools.py, registry.py, evaluate.py, sleep_check.py, adopt.py, ledger.py
    pools/, MANIFEST.sha256
  tests/
.github/workflows/rsi4-runs.yml   the one new file outside rsi4/
```

### Delivery

- Open the PR from `rsi4/four-loop` with base `rsi3/analogy`, in rsi3's PR template: what this adds (module table), not touched, pre-registration (commit hashes), measured outcome (gate table, misses first), test plan (commands and counts).
- Update the root `README.md` in the same PR: an RSI-4 row in the program-synthesis package table, the test-count line and the quick-start commands.
- `git diff rsi3/analogy -- rsi2 rsi3 docs rsi_levels_metaforge_unified.py EVIDENCE.md OUTER_LOOP_CONSTITUTION.md` must be empty, and existing workflow files unchanged. The rsi2 and rsi3 suites still pass at their committed counts.
- Every author, copyright or attribution line in files, docs and package metadata reads "Intelligence Research Project". Do not add personal names.
- **Do not merge.** Request the Owner's review and stop.

### Prohibitions

- No self-grading. Only FrozenVerifier and J read hidden examples, issue receipts or make keep, revert and adopt decisions.
- No edits to `rsi2/` or `rsi3/`. No edits to `rsi4/judge/` after its Phase 0 commit, except as a new registered version with a written reason.
- No deletion of receipts, traces, ledger entries or archived results.
- No anchoring term, and no gate on continuous learning beyond the receipt guard.
- No post-hoc arms, tuning, pool redraws or seed changes after registration.
- No decision of any kind from an exposed partition.
- No autonomous resource acquisition (Article I.2): runs use the Owner's repository Actions only.
- On any conflict with the constitution or this directive, stop and report.
