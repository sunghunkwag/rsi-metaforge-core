# Conservative typed replay: exact-budget cross-substrate experiment

Date: 2026-11-08.
Immutable baseline main: `c4f0a8627a1c9f37dd3aa6291b0eee0c78648210`.
Frozen previous research source: PR #55 commit `dbb7ba9600534e1578198d45bc58a4d99893fdf1`.
Final experimental run before this report: https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42470419392

## Falsifiable hypothesis
Replacing **only repeated identical type-valid candidate programs** in a typed-uniform incumbent stream with fresh programs can improve program discovery in multiple data substrates at *exactly equal training VM interpreter-call budgets*, while preserving every previously solved incumbent task by making the first incumbent train-perfect program the final choice if one exists.

Five interventions were tested: uniform replacement, structural novelty using an archive of observed training behaviors, failure memory using zero-hit token penalties, novelty+failure hybrid, and type-valid AST mutation around the current best publicly scored program. All algorithms are research-only; no independent test labels are used by proposal generation.

## Experimental protocol (frozen before independent audit)
- Three **distinct input substrates**: integer lists, strings, directed graphs; a shared small typed DSL translates programs for each substrate, so this is not unrestricted cross-domain intelligence.
- Six **new** development tasks and six **new** independent-audit tasks per substrate. Each target program is disjoint from PR #55's development and independent-audit targets. Target programs are not passed to search; the search receives only public input/output examples and the substrate name.
- 32 paired seeds per task, 48 candidate program evaluations per task/seed/arm, 12 public training examples and 24 independent shifted examples.
- Six arms: typed uniform incumbent, and the five conservative interventions above.
- Each stage has 18 tasks × 32 seeds = **576 cases per arm**, 27,648 candidate evaluations, **331,776 candidate-training VM interpreter calls** and 331,776 charged public-input probe slots **per arm**.
- Duplicate baseline proposals are only replaced after every originally present *distinct* typed program is reserved. Evaluation of every original distinct incumbent candidate is asserted. The first train-exact incumbent program has priority over all new candidates, preventing new overfit candidates from replacing incumbent successes.
- This input-evaluation call budget is *exactly matched*, unlike the preceding PR #55 comparison with the untyped legacy arm. Proposal generation and OOD verification CPU costs still differ, and are recorded separately.
- Development selection: a strict positive improvement over the incumbent in **each of three substrates**, zero regression on **every individual** development task's shifted-input success count, exact candidate and training-interpreter budget parity, and no per-case CPU-ceiling breach. Choose the arm with best minimum substrate gain, then total gain and lower CPU. The policy is frozen **before** independent audit.
- Independent audit requires the same per-substrate and per-task nonregression, with a positive net gain per substrate.

## Development: 576 task-seed cases
| Arm | TRAIN-perfect cases | OOD-pass cases |
|---|---:|---:|
| Typed uniform incumbent | 343 | 327 |
| Conservative uniform | 385 | 367 |
| Conservative novelty | 372 | 352 |
| Conservative failure memory | 394 | 377 |
| Conservative novelty + failure | 389 | 371 |
| **Conservative AST mutation** | **425** | **407** |

The development gate selected **conservative AST mutation**. All policies evaluated 27,648 valid candidate programs and made exactly 331,776 training VM calls, with the incumbent and conservative policies differing only in which duplicated candidate slots were recovered.

## Independent audit: 576 fresh task-seed cases
| Arm | TRAIN-perfect cases | OOD-pass cases |
|---|---:|---:|
| Typed uniform incumbent | 257 | 243 |
| Conservative uniform | 295 | 280 |
| Conservative novelty | 275 | 261 |
| Conservative failure memory | 307 | 292 |
| Conservative novelty + failure | 292 | 278 |
| **Conservative AST mutation** | **347** | **331** |

Independent audit gain for development-selected AST mutation: **+88 OOD-pass task/seed cases** relative to the exact interpreter-query-matched typed incumbent (331 vs 243; +36.2% relative, +15.3 percentage points over 576 cases).

Per-substrate OOD:
- Integer lists: selected minus incumbent **+23/192**.
- Strings: **+31/192**.
- Directed graphs: **+34/192**.

Per-task independent OOD deltas, all **nonnegative**:
- Integer lists: [0, +8, +6, 0, 0, +9].
- Strings: [+3, +6, +6, +2, 0, +14].
- Directed graphs: [+8, +10, +6, +3, +4, +3].

The preregistered finite independent gate returned `pass=true`. This is a bounded empirical success **only on the specified synthetic benchmark**, not proof of general recursive self-improvement or universal all-domain superiority.

## Evidence and actual cost
- CI run: https://github.com/sunghunkwag/rsi-metaforge-core/actions/runs/42470419392
- The workflow archive includes all per-seed program choices, incumbent-preservation checks, successes, failed experiments and CPU accounting.

Independent-audit measured CPU totals: incumbent **1.392279 seconds**; selected AST mutation **1.537930 seconds** (around 10.5% more). The selected arm had **8,328** additional OOD candidate verification calls versus **6,168** for the incumbent because it produced more train-perfect candidate winners. Both use **331,776** training-candidate VM calls. Every case had the same CPU ceiling, but this does NOT mean equal CPU consumption. Resource efficiency should be re-evaluated using per-instance time-limited search.

Incumbent-preservation is a deterministic program-set invariant, not a proof that the selected policy generalizes to arbitrary programs or workloads. The independent verification examples are separate from training but finite. The increase is driven partly by reclaiming exact duplicate program evaluations. The primitive searcher, task grammar, meta-optimizer, continual-learning behavior, and any cross-generation self-improvement remain unvalidated.

## Honest disposition and next experiment
- **Result:** A real, reproducible, strictly nonregressing finite transfer improvement vs a typed-uniform incumbent across three constructed substrates under equal candidate-training VM calls.
- **Not established:** General RSI, autonomously improving the search algorithm itself over generations, unconstrained domain generalization, matched end-to-end CPU, or no forgetting on realistic continual-learning streams.
- **No production merge.** Existing frozen verifier, TEST/J pools, RSI-4 Phase 1 and other PRs were never altered. This audit is now **spent**: do not tune the next intervention on these independent cases.
- **Next falsifiable study:** With clean tasks and at least one additional substrate, compare two or more *generations* of search-policy modifications, retaining the incumbent candidate set and matched actual CPU caps. Test whether a learned mutation policy retains improvements on a new task stream and whether cross-generation transfer and forgetting are genuinely better than frozen-policy and placebo controls. Use a separate PR, retain full per-generation receipts and negative cases.
