# Owner directive — RSI-3: a memory-feedback adaptive core

Owner: Sung Hun Kwag. Direct Owner directive, given in a chat session on 2026-10-27.
Like `rsi2/OWNER_DIRECTIVE.md`, this is not a work order under
`OUTER_LOOP_CONSTITUTION.md` and carries no approval token. It touches nothing
that constitution protects: everything is built in a NEW package `rsi3/`.

## The request (translated from Korean)

> Integrate all of the work so far with my existing repository into a unified
> architecture, and write the design and the code. All code in English.

Owner choices made in the same session: integrate with `rsi-metaforge-core`;
deliver on a branch with a pull request; do not commit to `main`.

## What "all of the work so far" refers to

The session produced four pieces of work, each integrated here:

1. A conceptual architecture: dormant pathways that are activated by
   conditions, a dynamic pathway activator, and a binding integrator that
   combines the outputs of several pathways into one record with provenance.
2. A requirement: the software must learn and adapt, with a memory-feedback
   algorithm regulating the processor along each pathway.
3. A measured toy study (`studies/regulation_toy.py`) comparing ways of using
   memory to regulate a learner. Experience replay retained beneficial changes
   and repaired harmful ones; every parameter-anchor variant (fixed or
   evidence-gated reference) lost both old and new capability.
4. A critique of an externally proposed design (a per-pathway Q-value router
   with an independent verifier): gates belong only at discrete expensive
   changes and at memory entry; a router over fixed modules keeps the design
   space closed; a continuous-context Q function needs replay; and the verifier
   must stay outside the loop it judges.

## Constraints

- Do not modify, import from, or refactor `rsi_levels_metaforge_unified.py`,
  any file under `docs/`, or any file under `rsi2/`. RSI-3 imports RSI-2's
  frozen DSL, evaluator, enumerator, corpus and sleep-phase learners read-only.
- Python standard library + NumPy. No language model, pretrained model,
  embedding, or model API. No network access at runtime.
- RSI-2's freeze rule stands: no new primitives, no hand-written library
  entries, no hand-written heuristics, no change to the evaluator.
- TEST stays sealed and unopened. VALIDATION is measured for reporting only and
  never feeds a decision.
- Predictions are registered before the final runs; misses are scored, not
  reinterpreted. No claim beyond the measured numbers (Article 0).
- Every run reproducible from (seed, config); budgets counted in candidate
  evaluations, wall clock and CPU recorded separately.
