# Owner directive — RSI-2: a self-improving program synthesizer (no LLM)

Owner: Sung Hun Kwag. Direct Owner directive, approved by the Owner on 2026-10-02.
This is not a work order under OUTER_LOOP_CONSTITUTION.md and needs no approval token.
It touches nothing that constitution protects: build everything in a NEW package rsi2/.
Do not modify, import from, or refactor rsi_levels_metaforge_unified.py or any existing
file under docs/.

## Mission
Build a program synthesizer whose improvements improve its own ability to make further
improvements, and measure — on tasks it did not create — whether that compounds across
generations. A measured null result is an acceptable outcome. An unmeasured, self-graded,
or tuned positive result is not.

## Why the existing runtime cannot do this
Read docs/P_RESULT.md, then verify each point below in rsi_levels_metaforge_unified.py
before building. About 20k of its ~49k lines are archived source stored as strings in
INTEGRATED_SOURCE_ARCHIVE; they are not part of the K–P loops.
- Closed language in the ascent line (Phases K–P): ak_run_tokens executes straight-line
  programs over the 34 base ops (OP_NAMES) only — no control flow, no function definitions,
  length capped by SC_STEP_LIMIT = 200. The solver vocabulary SC_SOLVER_VOCAB is 21 of those
  ops. DORMANT_CAPABILITY_CATALOG holds 2 hand-written ops and is frozen.
- Section 16 (self-forge) does synthesize new list->int primitives, but only inside a fixed
  tiny fold language (3-int state, one pass, tree depth <= 4), and the ascent-line executor
  rejects them. It is the closest existing piece to an open language; rsi2 generalizes it.
- Closed task supply: the setter only poses tasks built from the current ISA, so it never
  poses a task requiring a capability the system lacks (P_RESULT).
- No mechanism writes new search procedures. Phase O channel A evaluates 3 pre-written
  candidates once; two re-enable MOD/SELECT, which exist in the base ISA but were left out of
  the solver vocabulary, scored on 6 tasks built to need MOD. Channel B instantiates 2
  pre-proved pruning schemas. The "self-edit RSI loop" rewrites one source line
  (SELF_EDIT_CAPABILITIES) to enable 3 hand-implemented capabilities from a hardcoded target
  list. Section 24 Rule 1 selects features from a designer-written bank.
- Evaluations built together with the searcher produce structurally guaranteed successes.
rsi2 removes all of these causes.

## Hard constraints
- No language models, pretrained models, embeddings, or model APIs. No network access at
  runtime (fetching the task corpus once in Stage 2 is allowed).
- Python 3 standard library + numpy. multiprocessing allowed. No ML frameworks.
- Package rsi2/, small modules (target < 800 lines per file). Branch rsi2/open-synthesizer.
- All randomness seeded; every run reproducible from (seed, config).
- Budgets are counted in candidate evaluations (logical budget). Record wall clock separately.
- The final experiment must fit in ~24 CPU-hours total. Scale corpus size, generations, and
  budgets to fit, and state the scaling in the results.
- FREEZE RULE: the primitive set, the evaluator, and the heuristic's input format are frozen
  at the end of Stage 1. After that: no hand-written library entries, no hand-written
  heuristics, no new primitives, no hand-tuned grammar weights. Every later capability must
  come from the system's own learning. Any violation invalidates the run.

## Stage 1 — Open language
Implement a typed functional DSL:
- Types: int, bool, list[T], function types; polymorphic type inference sufficient for
  type-directed enumeration.
- Primitives: integer arithmetic and comparison, if, nil/cons/head/tail/is_empty, length,
  range, map, filter, fold, and bounded recursion (fix- or fold-based with a step budget, so
  every evaluation terminates).
- Lambda abstraction (de Bruijn indices). Programs are ASTs, not token strings.
- Evaluator with a hard step budget. Running out of budget returns a failure result; it never
  raises an escaping exception. Profile and optimize the evaluator; report candidates/second.
- Library: named, typed, parameterized abstractions (lambda terms) usable exactly like
  primitives. Library entries may call earlier library entries.
- Grammar: contextual production probabilities, P(child production | parent production,
  argument index), over primitives + library.
- Enumerator: type-directed, in decreasing probability order, under a candidate-evaluation
  budget. Use top-down enumeration (DreamCoder-style) or bottom-up with
  observational-equivalence pruning; document the choice and its measured throughput.
  Candidate priority = grammar log-probability + heuristic score (heuristic = constant 0
  until Stage 4).
- Heuristic input format (frozen here): the heuristic is a DSL program of type
  (list[int], list[int], int, int) -> int, receiving (candidate outputs flattened to ints,
  target outputs flattened to ints, candidate size, candidate depth). For partial or
  unevaluable candidates, pass an empty candidate-output list.
Tests: termination under budget, type safety of every enumerated program, enumeration order
consistent with grammar probabilities, library abstractions callable and composable.

## Stage 2 — External tasks and sealed splits
- Use a corpus not authored by the synthesizer and not shaped by the DSL. Prefer an existing
  public benchmark fetched once from GitHub: Josh Rule's 250-concept list-functions dataset,
  or the DreamCoder list-processing tasks. Only if neither can be obtained, write >= 300
  list/int tasks as plain Python reference functions with randomized input generators,
  spanning shallow to deeply compositional, committed in one commit BEFORE any learning code
  exists and never edited afterward. State which option was used.
- Each task: >= 10 input/output examples for search, plus separate hidden examples.
  A task counts as solved only if the program also passes its hidden examples.
- Split once, by seed: TRAIN 60%, VALIDATION 20%, TEST 20%. Commit the split.
- TEST is sealed. Learning, library, recognition, and heuristic code never read TEST.
  Enforce structurally: TEST is loaded only by a separate evaluation entry point, and a unit
  test fails if any learning module references the TEST path or loader.
- Budget calibration, once, on VALIDATION only, before any learning code runs: choose B_wake
  and B_eval so the generation-0 synthesizer solves between 10% and 40% of VALIDATION.
  Record the values, then freeze them.

## Stage 3 — Wake–sleep loop (search trained on its own output)
Each generation g:
1. Wake: attempt every TRAIN task under B_wake, guided by the current grammar, recognition
   model, and heuristic. Unsolved tasks are retried every generation. Keep the best (most
   probable) solution per task.
2. Abstraction: propose new library entries by refactoring repeated subtrees across
   solutions into parameterized lambdas (anti-unification or corpus-guided compression).
   Adopt an entry only if it lowers total description length (library size + all solutions
   rewritten with it). Rewrite solutions with adopted entries. Refit grammar probabilities on
   the rewritten solutions.
3. Recognition: train a numpy model (task I/O example features -> contextual grammar
   weights) on TRAIN (task, solution) pairs plus "dreamed" tasks produced by running random
   programs sampled from the current grammar. Dreamed tasks are training data only, never
   evaluation.
4. Evaluate on VALIDATION and TEST at B_eval: solved fraction (hidden-example verified) and
   mean candidates-to-solution. TEST numbers are recorded for reporting only and never feed
   any decision.
Run >= 8 generations.

## Stage 4 — The improver inside the loop (the recursive step)
- The heuristic (frozen input format from Stage 1) is synthesized by the system itself, each
  generation, using its OWN enumerator and its OWN current library — the same machinery it
  uses on tasks.
- Per generation: enumerate N_h candidate heuristic programs in grammar order (current
  library included) plus N_m mutations of the incumbent (subtree replacement drawn from the
  enumerator). Screen every candidate on a fixed VALIDATION subsample at reduced budget;
  confirm the best few on full VALIDATION at B_eval. Adopt only on strict improvement in
  VALIDATION solved fraction; otherwise keep the incumbent. Never use TEST. Log every
  candidate, adopted or rejected. These candidate evaluations count toward FULL's compute.
- This closes the loop: library learned from tasks -> better heuristic synthesis -> better
  search -> more solved tasks -> better library.

## Stage 5 — Measurement: is it actually recursive?
Arms (identical seeds, identical splits, identical B_eval at evaluation):
- BASE: generation-0 grammar, no library, no recognition, heuristic = 0.
- BRUTE: same as BASE but evaluated with budget M x B_eval, where M = 10 (pre-registered).
- ONESHOT: one wake–sleep round (abstraction + recognition + one heuristic synthesis round),
  then everything frozen. This is the non-recursive learner.
- FULL: Stages 3 + 4 iterated for all generations.
- Ablations of FULL: no library learning; no recognition model; no self-heuristic.
Run every arm with >= 3 seeds. Report TEST solved fraction per generation, per arm, per seed.
Before the final runs, commit rsi2/PREDICTIONS.md with expected TEST curves for FULL,
ONESHOT, BRUTE, and BASE, in numbers.
A positive recursion claim requires ALL of:
(a) FULL beats BRUTE on TEST at the final generation, on every seed (learning beats 10x
    raw search);
(b) FULL beats ONESHOT on TEST at the final generation, on every seed (iterating the loop
    adds beyond one round of learning);
(c) FULL's mean TEST solved fraction rises in >= 3 consecutive generations after
    generation 1, with no seed decreasing over that span;
(d) removing the self-heuristic lowers FULL's final TEST solved fraction (the improver's
    improvement contributes);
(e) heuristic synthesis with the current library finds a better heuristic than heuristic
    synthesis with only the generation-0 primitives, at equal synthesis budget (task learning
    feeds improver learning).
If any criterion fails, state which one, and the generation where the curve flattens.

## Process and reporting
- Order: Stage 1 -> 2 -> 3 -> 4 -> 5, unit tests with each stage, one commit per stage.
- If a stage's core check fails, make at most one documented fix attempt, then stop and
  report. Never tune budgets, seeds, splits, features, M, N_h, N_m, or thresholds after
  seeing TEST numbers.
- Verification stays minimal but sound: sealed TEST, VALIDATION-only decisions, BRUTE and
  ONESHOT controls, multiple seeds, the freeze rule. Do NOT build hash-chained ledgers,
  artifact pinning, byte-identity CI batteries, or constitution documents.
- Deliver rsi2/RESULTS.md: per-generation tables for every arm and seed; criteria (a)-(e)
  marked pass/fail; the top learned library entries printed as readable lambda terms with
  the generation each appeared; every adopted heuristic as a readable term; candidates/second;
  wall clock per arm; and a plain statement of where improvement stopped. One results JSON
  per run.
- Make no claims beyond the measured numbers.
- When done, open a pull request to main. Do not merge it.