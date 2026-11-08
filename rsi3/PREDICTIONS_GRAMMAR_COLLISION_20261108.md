# Pre-registration: grammar-reachable finite-probe collision (synthetic TRAIN-only)
Date: 2026-11-08 (UTC). Status: pre-execution design; this file is committed before driver/results.

## Scope and immutable base
- Start from PR #50 head `30d32cfe643575953af479d3ef773f85db225f78` on a new isolated branch. No changes to `main`, PRs #48/#49/#50, RSI-4 phases, frozen verifier, archived benchmarks or workflows.
- Use the repository's existing `rsi2.terms`, `rsi2.grammar.Grammar`, `rsi2.evaluator.evaluate`, `rsi3.integrator.BindingIntegrator`, `rsi3.memory.EpisodicMemory`, and unmodified `rsi3.verifier.FrozenVerifier`.
- Construct entirely synthetic development tasks in memory. Do not call `load_train`, `load_validation`, `load_test`, or RSI-4 judge services/pools.

## Falsifiable hypothesis and witness
- Request type: `int -> int`. Oracle: `f(x) = x`.
- Public examples: ten distinct integers 10..19 in a seed-specific deterministic permutation, with outputs equal to inputs.
- Finite behavioral probes: unchanged `BindingIntegrator.probe_inputs`, which increments integers by one; all probes fall in 11..20.
- Independent synthetic oracle checks: every integer -3..3 plus five unique integers in 30..49 from a separate deterministic PRNG; all are disjoint from public examples and probes. No hidden values are read by the candidate construction code.
- Correct candidate: `lambda x:int. x`. Rejected candidate: `lambda x:int. if eq(x,t) then r else x`, where `t` is one of the default grammar literals (-1, 0, 1, 2), `r=-1` except `r=0` when `t=-1`. The terms are typed, beta-normal, distinct, and must satisfy `Grammar().log_probability(term, request_type)` with `term.size <= 12`.
- Prediction P1: both terms match every public example and have identical *actual* (unmocked) finite-probe signatures; the rejected term fails independent oracle checks, and the correct term passes.
- Prediction P2: after the rejected term receives an authentic negative verifier receipt in generation 1, signature suppression falsely skips the correct term in generation 2; exact and no-suppression controls do not.
- Prediction P3: every arm obeys one frozen-verifier query per task per generation and no false receipt is accepted.

## Controls and budgets
- Three arms in fixed order: `signature`, `exact`, `none` (none bypasses the skip callback but still records the authenticated negative receipt).
- Four triggers `[-1,0,1,2]` crossed with seeds `[11,22,33]` = 12 synthetic tasks per arm, 36 arm/task runs.
- Candidate stream and order fixed: generation 1 rejected term, generation 2 correct term; exactly one public candidate evaluation per generation, same two-candidate logical budget for all arms.
- `step_budget=2000`, `max_size=12`, same public examples and independent checks across paired arms; one verifier query per task per generation, two total allowed. Same CPU ceiling of 2.0 process seconds per arm/task, with actual CPU time and verifier queries reported. A ceiling is *not* equal CPU consumption.
- Count public logical evaluations, probe interpreter calls, false suppressions, accepted correct candidates, authentic verifier queries, CPU seconds and budget violations. A skipped candidate still counts as a public logical evaluation, as in search.
- Record deterministic JSON and a short report; no tuning or post hoc changes to conditions based on synthetic outcomes. If P1/P2 fail, report failure rather than changing the task.
- This is a targeted *existence proof* with deliberately chosen cases, not an estimate of naturally occurring collision frequency, benchmark transfer, forgetting, general RSI improvement or AGI.

## Interpretation and next gate
If P1/P2 hold, the existing finite-probe skip rule is unsound as a universal equivalence criterion, but the earlier 36-TRAIN null pilot remains unchanged. Next preregister a naturally sampled grammar-search collision-frequency study with identical search budgets and independent development tasks; do not use sealed evaluation pools for selection.
