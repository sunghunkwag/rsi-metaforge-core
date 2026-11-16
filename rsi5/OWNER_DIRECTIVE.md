# RSI-5: Two-Closure Bootstrap — Claude Code Directive

Nov 9, 2026 · Intelligence Research Project

> *"Nothing is simple. Everything has texture. Nuance."* — The Orville 3x07. Kept here as a design rule: no behaviour is collapsed to one scalar before a gate sees it (§8, Texture rule).

## 0. Mandate

Build `rsi5/` in `sunghunkwag/rsi-metaforge-core`: a program-synthesis system whose **vocabulary is the object of self-improvement**. Every previous package (RSI-2, RSI-3, the rsi4 harness) kept the grammar frozen and improved how a fixed vocabulary was searched. The repository's own ledgers show where that ends: Phase P re-saturates because *the setter never manufactures a task shaped like the capability it lacks*; RSI-3's twenty studies traded one 16-candidate slot against another; the largest gain in the whole rsi3 chain was a 4× budget increase, not a mechanism. RSI-5 attacks the two structural limits directly — **search budget** (10³–10⁴× too small) and **grammar closure** (six DreamCoder primitives missing, integer constants −1..2) — and installs the one mechanism that can leave the closure by construction: **primitives invented from the residual fingerprints of external failures**, admitted by a sealed statistical gate.

You implement, run and report. The Owner sets scope, approves predictions and merges. You are the only agent on this repository; there is no second agent to coordinate with.

| Item | Value |
| --- | --- |
| Repository | `sunghunkwag/rsi-metaforge-core` |
| Base | `rsi3/fresh` at `34795a0` (merge of PR #47, 2026-11-04). `main` is at `c4f0a86` (PR #26). Step 0 squashes `rsi3/fresh` into `main` first; if the Owner has not merged by the time Phase 1 code lands, PR base is `rsi3/fresh` and is retargeted to `main` afterwards |
| Branch | `rsi5/two-closure`, created from the base |
| Package | `rsi5/`, sibling of `rsi2/`, `rsi3/`, `rsi4/` |
| Judge | `rsi4/judge/` (J) **as committed on `rsi4/run-p1` at `c48c820`**, copied into `rsi5/judge/` byte for byte, with its seed, manifest, pools and ledger. J is never edited; its pools are never opened by anything but J |
| Compute | Local CPU for development; GitHub Actions for every registered run (`.github/workflows/rsi5-runs.yml`, triggered by branches named `rsi5/run-*`, matrix over seeds × arms, within the account's Actions limits) |

**What this supersedes.** The rsi4 four-loop plan (Phases 1–4 of `rsi4/OWNER_DIRECTIVE.md`) is set aside unbuilt; only its Phase 0 harness (J) is kept. The rsi3 line is closed by Step 0. The RSI-2 freeze on primitives is **lifted for `rsi5/` only** — that freeze is exactly the constraint this directive removes.

**Read-only, never edited.** `rsi_levels_metaforge_unified.py`, `docs/`, `EVIDENCE.md`, `OUTER_LOOP_CONSTITUTION.md`, every frozen instrument and committed evidence, `rsi2/`, `rsi3/`, `rsi4/`. RSI-5 **forks** what it needs from `rsi2/` (types, terms, evaluator, grammar) into `rsi5/dsl/` and changes the fork; the originals keep their evidence intact.

**Fixed rules**

- Python standard library and NumPy only. No network at run time. **No transformer or attention layers anywhere**, including in any learned component of later phases.
- TEST (12 tasks of RSI-2) is never opened, referenced or counted. J's pools are read by J only; the solver process cannot import, open or list them (rsi4 `guard.py` audit hook stays installed).
- Hidden examples are read only by the frozen verifier and by J. Every positive label needs an authentic receipt.
- `OUTER_LOOP_CONSTITUTION.md` Article VIII applies: no tuning after registration, limitations written as Target Property + Criterion, stop and report on any conflict. This is a direct Owner directive, not a work order under the constitution.
- Register predictions before every final run, score misses first, and treat an honest null as a valid result.
- **Claim discipline in reports, ambition in design.** Reports state exactly the measured trajectory at the registered budgets, seeds and pools, in the form `rsi3/*RESULTS.md` use. The *design* is allowed to aim at the self-sustaining tier (§9, T3) and to say so in the directive and predictions; the *report* says only what J measured.
- All copyright and attribution: Intelligence Research Project. No personal names anywhere in the package, commits or docs.
- Language: English throughout — code, identifiers, comments, docs, commits.

## 1. Facts that fix this design

Every row is measured in this repository or in the 2026 literature read for this directive. Verify each against the file named before building on it.

| # | Measured fact | Source | Consequence here |
| --- | --- | --- | --- |
| F1 | Evaluator throughput 10–83 candidates/s; per-task budget 64 candidates (4 chunks × 16) | `rsi2/FROZEN.md` (82.99/s, size 12), `rsi2/RESULTS.md` compute table (FULL arm ≈10/s), `rsi3/experiment_config_honest.json` (`B_wake`/`B_eval` 64) | Phase 1 replaces the engine before any mechanism is added. Target ≥10⁴ cand/s/core, 10⁵–10⁶ candidates per task |
| F2 | 64→256 candidates alone: TRAIN 29→31, NEAR 57→67, FAR2 5→13, COMPOSE 0→4 — larger than any rsi3 mechanism | PR #47 description, `rsi3/ANALOGY_DEVELOPMENT_NOTE.md` | Budget is the first-order variable; every mechanism is compared at **equal evaluations** against a budget-only control |
| F3 | DSL primitives: add sub mul div mod neg abs eq lt le gt ge and or not if nil cons head tail is_empty length range map filter fold; constants −1 0 1 2; max_size 12 | `rsi2/types.py` `PRIMITIVE_TYPES`, `rsi2/grammar.py` constants | DreamCoder's own list sets include `unfold`, `index`, `fix1`, `is-prime`, `is-square`, constants 0–5 (`bootstrapTarget_extra`, `basePrimitives`). None are here |
| F4 | On FRESH-1, no arm solved any routine the corpus lacks (`intersperse-k`, `positions`, `uniq`, `identify-is-prime`, `replace-index-k-with-n`); every solve was a known routine with a new constant read off the data by `behave:map` | `rsi3/FRESH_RESULTS.md` | These are closure failures, not search failures. The headline metric of RSI-5 is **closure escape** (§8) |
| F5 | Phase P: with an open closure and a self-driven ISA extender, the trajectory re-saturates at the frozen-K ceiling because the setter never poses a task shaped like the missing capability | `README.md` §Domains (Phase P), `docs/P_RESULT.md` | The shape of the missing capability must come from **outside** the system's closure: external failures (§4) and reverse dreams (§6) |
| F6 | A learned proposal-action controller lost to a frozen parameter-mutation baseline on an externally pre-registered, independently audited pool: 649/760 vs 690/760, −5.39 pp, seed-cluster bootstrap 95% CI [−8.82, −2.11] | `research/RESULTS_EXTERNAL_METACONTROL_20261108.md` on `research/external-preregistered-metacontrol-20261108` | **No learned controller, value model or policy in Phases 1–3.** Hill-climbing and frequency statistics only |
| F7 | rsi3 learned controller null (6/36 = RSI-2); failure memory +1–2; invention +1; each new action displaced a behavioural action's slot | `rsi3/RESULTS.md`, `FAILURE_MEMORY_RESULTS.md`, `INVENTION_RESULTS.md`, `ANALOGY_RESULTS.md` | 36 binary outcomes per generation carry no learnable signal. Learning returns only after the budget is ×1000 |
| F8 | Phase AE 15/15 was structurally guaranteed by co-design of the task generator and the search engine | Owner record, 2026-10 | Task admission needs an anti-co-design filter (§5.2); verifier structure is never visible to the solver |
| F9 | 2026 audits of harness-level RSI: all 16 evolved champions gained uncovered tasks while losing covered ones; the original selection rules picked the best parent below a random baseline; highest score never gave the largest subsequent gain | arXiv 2611.07624 (full text) | Report task turnover and G0 retention explicitly; test every selection rule against random (§8) |
| F10 | 95,993 synthetic generator tasks did not beat 1,920 real tasks for any checkpoint; task admission there = behavioural distinctness on a probe set + refuting nearest competing rules + defeating shortcut solvers | arXiv 2611.06827 | External tasks are the headline source; self-generated tasks are for vocabulary only; admission filter in §5.2 |
| F11 | Exposing the verifier's criteria to a learner: 51.6% vs 27.8% under the original criteria, 45.0% vs 47.2% under re-expressed criteria | arXiv 2611.08318 | Re-expressed-verifier audit (§8.6) |
| F12 | Behind a lenient (partial-credit) gate, 4× search budget bought ≈0; behind an exact gate, +1.62 pp | arXiv 2607.09709 | Admission into library, replay or vocabulary is **exact-gate only**; no partial credit anywhere |
| F13 | Retrospective MDL (DreamCoder/Stitch/LILO) picks abstractions that compress past tasks; human abstraction tracks the *future* task distribution | arXiv 2605.09985 | Candidate primitives are scored by **prospective** value on unsolved external tasks (§4.4), never by compression of the generator's own output |
| F14 | A statistical self-modification gate using e-values / Hoeffding with a global error budget is model-free and CPU-trivial | arXiv 2510.10232 | Admission gate G3 (§5.3) |
| F15 | Mastery-throttled benchmark co-evolution with single-anchor recalibration took held-out from 12.7% to 45.1% (single run) with a frozen verifier only | arXiv 2607.17352 | Curriculum rule on J's stage pools (§7) |
| F16 | Learning-progress reward (gradient alignment with the learner's recent movement) produced an adaptive curriculum that discovered Fibonacci/geometric/quadratic programs; difficulty-based reward was gamed by noise | arXiv 2609.30063 | Generator reward in §6 is closure growth per CPU-second, never difficulty |
| F17 | ~30% of lines added by evolutionary coding agents were byte-identical re-introductions of previously deleted lines | arXiv 2605.20086 | Cycle detector on the vocabulary ledger (§8.8) |
| F18 | Success-only gates silently prune redundant components; larger evaluation batches made it worse | arXiv 2610.38392 | One-layer ablation audit before every admission (§8.9) |

## 2. Architecture: two closures, one judge

```
                 external tasks (J stage pools; list_tasks2.json, 174,258 records)
                                   │
            ┌──────────────────────▼──────────────────────┐
            │  C1  fast closure  (rsi5/dsl, rsi5/engine)  │  bottom-up, observational equivalence,
            │  restored vocabulary + admitted primitives  │  normal forms, compiled closures,
            │  10^5–10^6 candidates / task                │  ≥10^4 cand/s/core
            └──────┬──────────────────────────────┬───────┘
         solved    │                              │ failed: nearest miss p, residual (p(x) → y)
                   ▼                              ▼
         library compression              ┌───────────────────────────┐
         (Stitch-style, frequency,        │ residual fingerprints     │  behaviour of the missing
          no learned scorer)              │ on the frozen probe set   │  correction on probe inputs
                                          └─────────────┬─────────────┘
                                                        │ cluster (exact hash → VSA near-match)
                                                        ▼
                                          ┌───────────────────────────┐
                                          │ C2  wide closure          │  fix, unfold, index, zip, pairs,
                                          │ (rsi5/wide)               │  higher-order, slow; searched only
                                          │ synthesises a witness f   │  for cluster centroids
                                          └─────────────┬─────────────┘
                                                        │ candidate primitive f : τ
                                                        ▼
                      ┌─────────────────────────────────────────────────────┐
                      │ admission gates  G1 contract · G2 novelty · G3 e-value │
                      │ (sealed; J measures closure escape on its own pools)   │
                      └───────────────┬─────────────────────────────────────┘
                                      │ admitted → f joins C1's vocabulary (hash name)
                                      ▼
                      closure ledger: tasks newly expressible, families unlocked
```

Two closures because speed and reach are in tension: C1 must be fast enough to run 10⁵+ candidates on thousands of external tasks; C2 must be wide enough to express what C1 cannot, and is affordable only because it is searched for a few dozen cluster centroids per generation, never per task. The judge J is the rsi4 harness unchanged.

## 3. Phase 1 — Engine (the precondition for everything)

### 3.1 `rsi5/dsl/` — the forked DSL

Fork `rsi2/types.py`, `terms.py`, `evaluator.py`, `grammar.py` into `rsi5/dsl/` and change:

- **Restored vocabulary** (DreamCoder `bootstrapTarget_extra` ∪ `basePrimitives`, minus nothing): add `unfold : (a→bool)→(a→b)→(a→a)→a→list b`, `index : int→list a→a`, `fix1` (bounded primitive recursion with the step budget as the only terminator), `is_prime : int→bool`, `is_square : int→bool`, integer constants `0 1 2 3 4 5` (keep `-1`), and `zip : list a→list b→list (a,b)` with pairs `pair/fst/snd` as a type. Record the exact list in `rsi5/dsl/VOCABULARY.md` with each symbol's type and a one-line justification pointing to the DreamCoder set.
- **Step-budget totality**: every primitive terminates under the interpreter's step budget; `fix1` and `unfold` charge steps per unrolling. No primitive may raise an escaping exception.
- **Admitted primitives** live in `rsi5/dsl/admitted/<hash>.py` as (type, C2 witness term, probe-set I/O table, admission record). Names are the first 12 hex characters of the SHA-256 of the witness term. **No human-readable name is required or invented.** Illegible vocabulary is allowed by design.

### 3.2 `rsi5/engine/` — bottom-up search

- **Bottom-up enumeration with observational equivalence** over the task's public examples plus the frozen probe set: programs of size n are built from programs of size <n; any program whose output vector on (examples ∪ probe set) equals an existing program's is discarded. This is the standard pruning rsi2's directive offered and did not take.
- **Normal-form filter**: skip terms that are not in β-normal, η-long form (no redex, no `(λx. f x)`, no `if True`, no `head (cons a b)` etc.); state the rewrite rules in `rsi5/engine/NORMAL_FORMS.md`.
- **Compiled closures**: a term is compiled to a Python closure once and applied to all examples; type inference runs once per term at construction, never per example.
- **Budget unit**: *candidate evaluations* (one term × one example set). Registered budgets: B = 10⁵ per task for stage pools, B = 10⁶ for the invention queue. Wall-clock caps are secondary and recorded.
- **Throughput test**: `rsi5/tests/test_throughput.py` asserts ≥10⁴ candidates/s/core on the standard micro-benchmark (`rsi2/benchmark.py`'s example set) and records the number in the PR. If the target is not met in pure Python, report the measured figure and the profile before touching anything else; do not add dependencies.

### 3.3 Phase 1 measurement (no learning anywhere)

Run C1 **by enumeration only** on every exposed partition the repository owns (FRESH-1, FRESH-2, RESERVE-NEAR, RESERVE-FAR2, COMPOSE-24, VALIDATION) at B = 10⁵ with (a) the original vocabulary and (b) the restored vocabulary. This is the cheapest decisive experiment in the directive: it separates "not expressible" from "not found".

Pre-registered predictions (commit `rsi5/PREDICTIONS_P1.md` before the run):

| ID | Prediction | Expected |
| --- | --- | --- |
| P1-1 | Restored vocabulary at B=10⁵ solves ≥ 15 of 33 FRESH-1 (HONEST: 7) | PASS (moderate) |
| P1-2 | Original vocabulary at B=10⁵ solves ≤ 10 of 33 FRESH-1 — i.e. most of the gap is vocabulary, not budget | PASS (moderate) |
| P1-3 | At least 2 of the five "corpus-lacking" FRESH-1 routines (F4) are solved with the restored vocabulary | PASS (low) |
| P1-4 | RESERVE-FAR2 ≥ 10 of 21 (HONEST: 5; HONEST@256: 13) | PASS (moderate) |
| P1-5 | Throughput ≥ 10⁴ cand/s/core | PASS (low; pure Python) |

If P1-1 and P1-3 both fail, **stop and report**: the C1 design is wrong and §4 must not be built on it.

## 4. Phase 2 — The invention loop

### 4.1 Nearest miss and residual

For every external task t that C1 fails at budget B, record the **nearest miss** p* = argmin over evaluated programs of D(p(x), y) summed over public examples, where D is a registered distance: type mismatch = 1; for lists, normalised Levenshtein over elements; for ints, 1 − exp(−|a−b|); for bools, 0/1. Ties broken by MDL size. The **residual table** of t is {(p*(x_i), y_i)} over public examples, plus p*'s outputs on the frozen probe set.

The residual is the shape of the capability C1 lacks for t. It is computed from public examples only.

### 4.2 Residual fingerprints and clustering

- **Fingerprint**: the residual's required correction, expressed as the I/O table (p*(x) → y) **and** the structural signature (input type, output type, length delta pattern, element-permutation flag, value-shift flag). Keep all fields; do not collapse to one number (Texture rule).
- **Exact clustering**: hash of the normalised I/O table. Two tasks with the same hash share a missing capability exactly.
- **Near clustering**: encode each fingerprint as a bipolar hypervector (10,000 dims; bind type/position/value roles, bundle rows) and cluster by cosine ≥ θ_near (registered). The unified runtime's HDC/VSA code (Section 14) may be imported read-only or re-implemented minimally in `rsi5/hdc.py`.
- A cluster is **eligible for invention** when it holds residuals from ≥ k_min tasks in ≥ 2 distinct name families (k_min registered; default 3).

### 4.3 `rsi5/wide/` — the wide closure C2

C2 = C1's vocabulary ∪ {`fix` (general bounded recursion), `unfold`, `zip`, `pair/fst/snd`, `index`, `append`, `reverse`, `last`, `count`, `take/drop`, `sort`, function-valued arguments and results (higher-order primitives are allowed)}, same step budget. C2 is searched only for **cluster centroids**: the target is a term f : τ whose behaviour reproduces the residual table of every member of the cluster on their public examples. Search is bottom-up with observational equivalence as in C1, at B₂ = 10⁶ per centroid. C2 may also return f as a *composition* f = g ∘ h where h ∈ C1; only the part not expressible in C1 becomes the candidate.

### 4.4 Prospective scoring (which centroid to attempt first)

For each eligible cluster, estimate **prospective value** V(cluster) = number of still-unsolved external tasks (across the invention queue, never J's pools) whose nearest-miss residual lies within θ_near of the centroid, weighted by 1/size of the required f. The queue is ordered by V, not by cluster size and not by past compression. This replaces retrospective MDL as the selection principle for vocabulary (F13).

### 4.5 Learning-progress reward for the invention queue (the only "reward" in RSI-5)

The learner is the closure itself; it has no parameters. Define the generator's reward for attempting centroid c as the realised **closure growth per CPU-second**: ΔE(c) / T(c), where ΔE is the number of tasks in the invention queue that became expressible after f_c was admitted and T is the CPU time spent. The queue ordering is re-fit each generation from these realised values by a frequency estimate (no gradient, no network). Difficulty is never used as a reward (F16).

## 5. Admission gates

A candidate primitive f : τ joins C1 only through all three gates, in order. Gate results and the full candidate record are appended to `rsi5/ledger/vocabulary.jsonl` (hash-chained like J's ledger).

### 5.1 G1 — Construction contract (hermetic, in-process)

- f is well-typed, β-normal, terminates on every probe input under the step budget, and is total on the probe set (no runtime failure).
- f's witness term is in C2; its probe-set I/O table is committed beside it.
- f is not a constant function and not the identity on any probe type.

### 5.2 G2 — Behavioural novelty and anti-co-design

- **Novelty**: f's output vector on the probe set differs from every existing symbol's and every size-≤4 C1 composition's output vector (computed by the same bottom-up engine). An f that equals an existing composition is a *macro*, not a primitive, and is routed to the library instead.
- **Discrimination**: the cluster's tasks must **refute** the nearest competing C1 programs (each member's p* fails ≥ 1 public example) and must **defeat the shortcut solvers**: constant output, copy-input, nearest-neighbour over the training set, length-only and sum-only predictors (`rsi5/shortcuts.py`, 12 solvers registered before any run). A cluster whose tasks a shortcut solver passes is discarded as degenerate.
- The solver and the invention loop never read verifier or J code; the rsi4 audit hook enforces it.

### 5.3 G3 — Statistical closure-escape gate (sealed, J decides)

- J evaluates C1 ∪ {f} and C1 at the registered budget on the **current stage-eval pool** (single-use per generation; J burns it), paired over tasks.
- Admission statistic: an e-value for "solves(C1 ∪ {f}) > solves(C1)" from the paired wins/losses (sign test e-process), tested against a **global error budget** α = 0.05 over the whole run (e-values multiply across generations; the budget is spent, not reset). Equivalently, Hoeffding at the registered confidence with Bonferroni over the generation's candidates — state which, once, in `rsi5/judge_rules.md`.
- **Noise floor**: a candidate whose paired gain lies inside the measured seed-to-seed variance of C1 on the same pool is rejected regardless of sign (F9, RRSI).
- Rejected candidates and their e-values are recorded; **a refuted hypothesis is never retried** in its exact form (hash of f's I/O table).

### 5.4 IOU primitives (experimental arm, report-only)

When a cluster is eligible and prospectively valuable but C2 finds no witness within B₂, admit the centroid **provisionally** as an *extensional* primitive: a lookup table over the probe domain, usable **only** inside the invention queue and reverse dreaming to measure what the capability would be worth (V under the IOU). IOUs never enter J's evaluation, never count toward any headline, and are **revoked** if no C2 witness discharges them within G_iou generations (default 4). This measures the value of a capability before the system can build it, and tells the C2 search where to spend. Reported as a separate column; never merged with measured solves.

## 6. Phase 3 — Reverse dreaming (self-generated tasks from what the system cannot do)

DreamCoder dreams from solved programs; that is why dreams stay inside the closure (F5). RSI-5 dreams **from residual clusters**:

- During sleep, for each eligible cluster, C2 samples programs that *use* the cluster's candidate f (or IOU) composed with C1 terms, executes them on sampled inputs, and emits (input, output) tasks. Such a task is, by construction, outside C1's current closure.
- Dream tasks pass the §5.2 admission filter (refute nearest C1 programs; defeat shortcut solvers; behavioural distinctness from existing tasks on the probe set) before entering the invention queue.
- Dream tasks never enter J's pools and never count toward any headline. Their only purpose is to keep the invention queue non-empty when external failures are exhausted — the mechanism by which Tier 3 (§9) could become self-sustaining.
- Report the share of the invention queue that is dream-sourced each generation.

## 7. Phase 3 — Curriculum on J's stage pools

Use rsi4's stage structure (S1–S3 stage-train/stage-eval, probe, selection ×3, confirmation ×3, final test) unchanged, with the **mastery-throttled** rule (F15): the active stage advances only when C1's solve rate on the current stage-train exceeds θ_mastery (registered); at most k_retire tasks solved in every one of the last 3 generations are retired per generation and replaced from the next stage; newly inserted tasks count as unsolved. **Single-anchor recalibration**: after each replacement, C1 is re-run on the new pool and a difficulty coefficient is updated multiplicatively so that C1's normalised score is preserved, making generations comparable. Refresh timing is read from training logs (fraction of tasks whose repeated attempts still differ in outcome), never from eval pools (A-RSI). Difficulty-targeted replacement is **not** used — random replacement within the stage, since difficulty targeting did not beat random (arXiv 2610.38568).

## 8. Measurement and audits (all registered before Phase 2 runs)

1. **Headline — closure escape.** E = number of J-pool tasks solved whose *name family* has zero solved members under the original rsi2 vocabulary at the same budget. Reported per generation, with the admitted primitive(s) each escape is attributed to (the primitive whose removal un-solves the task).
2. **Closure ledger.** For every admitted primitive: tasks newly expressible at size ≤ n (computed by re-enumeration on the invention queue), families unlocked, CPU spent to invent, generation admitted, e-value. This is the quantity that can show a step function.
3. **Generalisation ladder G0–G4** (arXiv 2611.02797): G0 retention on previously solved pool tasks (regressions counted), G1 unseen two-stage pipelines at the same stage, G2 three-stage pipelines (rsi4 `final_test_3`), G3 single routines from families absent from TRAIN, G4 the file-world battery of the unified runtime run read-only as an out-of-domain probe. Every result table has all five columns.
4. **Turnover and reliability.** Tasks gained / lost per generation; deterministic runs replace Avg@8 with a **seeds × budget grid** (3 seeds × B ∈ {10⁴, 10⁵, 10⁶}) and the expected-best-of-k frontier (arXiv 2609.19799).
5. **Selection vs random.** Each generation, the chosen centroid's realised ΔE is compared with the ΔE of a randomly drawn eligible centroid attempted in a shadow run; report the fraction of generations the rule beat random. Below 50% over 8 generations → the rule is replaced by random and the change is recorded.
6. **Re-expressed verifier audit.** Once per phase, a second implementation of the frozen verifier's checks (same semantics, different code and example ordering) re-scores every positive; disagreements are reported as such (F11).
7. **Hill-climbing control.** Every mechanism arm is paired with a control that spends the identical candidate budget on best-so-far-conditioned random mutation of C1 programs (arXiv 2609.25510). A mechanism that does not beat its control on E and G1 is reported as null.
8. **Cycle detector.** Vocabulary ledger entries whose I/O table hash equals a previously rejected or revoked entry are flagged; the count is reported (F17).
9. **One-layer ablation.** Before admission, C1 ∪ {f} is re-evaluated with each *other* admitted primitive removed one at a time; if f's gain exists only when another primitive is absent, both are flagged redundant and neither is pruned by score alone (F18).
10. **Objective audit (the system may question its own headline).** Each generation C1's invention loop may *propose* a revision of E (e.g. family definition, size bound) with a one-paragraph justification generated from the ledger. A proposal is adopted only if it does not change the ranking of the last 3 generations on a frozen 20-task anchor set that the loop never sees (arXiv 2610.11464). Proposals and verdicts are logged. This is the measured form of a system checking whether its goal is wrong; it never bypasses the Owner's approval for registered predictions.

**Texture rule.** No gate, cluster or queue consumes a scalar summary of a behaviour where the full I/O table or fingerprint is available. Scalars appear only at the final e-value, computed from paired outcomes. Any PR that introduces a learned or hand-tuned scalar score upstream of G3 is out of scope.

## 9. Take-off tiers and pre-registered predictions

The directive's ambition is stated as three tiers. Each is a measurable event on J's sealed pools; none is a claim until J records it.

| Tier | Definition | Prediction | Expected |
| --- | --- | --- | --- |
| **T1 — first escape** | ≥ 1 J-pool task solved at the registered budget whose family had zero solves under the original vocabulary, attributable to an **invented** (not restored) primitive that passed G1–G3 | by generation 8 | PASS (moderate) |
| **T2 — family unlock** | one admitted invented primitive raises sealed-pool solves by ≥ 5 tasks spanning ≥ 2 name families, in the same generation it is admitted (closure ledger) | by generation 16 | PASS (low) |
| **T3 — self-sustaining** | for 3 consecutive generations: ≥ 1 primitive admitted per generation, ≥ 50% of the invention queue is dream-sourced (§6), and sealed-pool solves rise each generation (sign test, Holm, p < 0.05) — invention outpaces the external task source | within the registered run | **FAIL expected** (no precedent in the 2026 literature, CPU or GPU). Achieving it would be the historic result; failing it is an informative null that bounds how far an external-failure-driven ratchet goes before dreams must carry it |

Additional registered predictions for Phase 2: P2-1 restored vocabulary alone accounts for ≥ 60% of the Phase-2 gain over HONEST (budget and vocabulary dominate invention early); P2-2 at least one invented primitive is **not** expressible in C1 at size ≤ 12 (a true closure extension, not a macro); P2-3 the hill-climbing control ties or beats the invention arm on G1 at generation 4 and loses by generation 12; P2-4 no learned component is present and the budget-only control at B = 10⁵ already exceeds every rsi3 number. Score misses first.

## 10. Step 0 — Repository hygiene (do this first, in one PR)

1. `gh pr list --state all` and record the status of #48–#56 in the PR description (the Owner's session could not read them).
2. Close #23 and #36–#45 (the DUST / Q Labs credit-estimator line) with a one-line comment pointing to this directive.
3. Squash-merge `rsi3/fresh` into `main` as one commit, "RSI-3 studies record (20 PRs, pre-registered, misses scored)". Update the root `README.md`: replace the rsi3 row with the FRESH / FAR2 / HONEST@256 numbers and one sentence stating that a 4× budget exceeded every mechanism. Run rsi2's 470 and rsi3's 39 tests and Quick CI before merging. Then close #27–#35 if GitHub has not.
4. Move `research/RESULTS_EXTERNAL_METACONTROL_20261108.md` and its prereg files to `docs/external/` on `main` (the negative result is kept); then delete the four `research/*-20261108` branches, and any remaining `swarm/*` or `rsi3/induce` branch.
5. Leave `rsi4/run-p1` untouched; RSI-5 copies J from it (§0).

## 11. Deliverables, tests first, Definition of Done

**Package layout**

```
rsi5/
  OWNER_DIRECTIVE.md (this file)  README.md  ARCHITECTURE.md  VOCABULARY.md
  dsl/      types.py terms.py evaluator.py grammar.py admitted/<hash>.py
  engine/   bottomup.py oe.py normal_forms.py compile.py NORMAL_FORMS.md
  wide/     c2.py
  residual.py fingerprints.py hdc.py clusters.py prospective.py queue.py
  gates/    g1_contract.py g2_novelty.py g3_evalue.py shortcuts.py
  dream.py  curriculum.py  ledger/vocabulary.jsonl  judge/ (copied from rsi4)
  runs/<name>.json  PREDICTIONS_P1.md PREDICTIONS_P2.md RESULTS_P1.md RESULTS_P2.md
  tests/
```

**Tests first** (named before implementation; each anti-cheat test constructs the attack):
`test_throughput`, `test_oe_prunes_equal_outputs`, `test_normal_forms_rewrite_set`, `test_vocabulary_matches_VOCABULARY_md`, `test_fix1_terminates_under_budget`, `test_residual_distance_registered`, `test_fingerprint_keeps_all_fields`, `test_cluster_eligibility`, `test_c2_witness_reproduces_cluster`, `test_g1_rejects_constant_identity_partial`, `test_g2_routes_macro_to_library`, `test_g2_shortcut_solvers_discard_cluster`, `test_g3_evalue_budget_is_spent_not_reset`, `test_g3_noise_floor_rejects_inside_variance`, `test_refuted_hash_never_retried`, `test_iou_never_reaches_judge`, `test_dream_tasks_outside_c1_closure`, `test_dream_tasks_never_in_pools`, `test_guard_blocks_pool_access`, `test_objective_audit_anchor_ranking_preserved`, `test_cycle_detector_flags_rehash`, `test_ablation_flags_redundant_pair`, `test_two_runs_byte_identical`.

**Definition of Done** (per phase): all tests green; Quick CI green; registered run on Actions with two byte-identical digests (or dual-replay identity where nondeterminism is declared); `RESULTS_P<n>.md` in the rsi3 results format with every prediction scored, misses first, G0–G4 columns, closure ledger, turnover, selection-vs-random fraction, hill-climbing control, and the audits of §8; PR description lists Touched files and states what the phase did **not** attempt.

## 12. Prohibitions

- No learned controller, value model, recognition network or policy in Phases 1–3. (Re-opened only by a new Owner directive after the budget is ≥ 10⁵ per task and T1 is recorded.)
- No partial-credit admission anywhere (library, replay, vocabulary, curriculum).
- No difficulty-based reward or difficulty-targeted task replacement.
- No human-authored primitives beyond the restored DreamCoder set in §3.1; everything else enters through G1–G3.
- No reading of J's pools, seed, code or ledgers by the solver process; no retargeting of the ledger path.
- No retry of a refuted candidate in its exact form; no tuning after registration.
- No mechanism merged without its equal-budget hill-climbing control.
- No transformer or attention layer, anywhere, ever, in this package.
- No personal names in the package.

## 13. Order of work

1. Step 0 (§10) — one PR.
2. Phase 1 (§3): fork, vocabulary, engine, throughput test, `PREDICTIONS_P1.md`, registered enumeration-only run on Actions, `RESULTS_P1.md`. **Gate**: P1-1 or P1-3 must pass, else stop and report.
3. Phase 2 (§4–5, §8): residuals, fingerprints, C2, gates, ledger, audits, `PREDICTIONS_P2.md`, registered run (16 generations, 3 seeds, B = 10⁵), `RESULTS_P2.md`. T1 is scored here.
4. Phase 3 (§6–7): reverse dreaming, curriculum, IOU arm; registered run; T2 and T3 scored.
5. Report to the Owner after each phase with the one-paragraph form: what J measured, what was predicted, what missed, what is not claimed.
