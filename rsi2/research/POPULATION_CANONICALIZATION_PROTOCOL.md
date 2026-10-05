# Pre-pilot canonicalization and actual-pop correction

Independent synthetic review found two concrete implementation bottlenecks
before any TRAIN population trial. A shared expansion cap could allow one
extra frozen-queue pop before its proxy noticed exhaustion. Separately, a
64-attempt polymorphic population contained only 22 alpha-normal ASTs: 42
attempts differed only in generated type-variable names, wasting novelty and
evaluation quotas.

Use the live shared cap comparator before every frozen heap pop, including
interleaved paused replacement streams. Debit a completed pop even if a
following CPU check interrupts. Verify actual heap removal counts directly;
do not claim correct accounting solely from the proxy's own counter.

Canonicalize alpha-equivalent type annotations before candidate novelty,
typing and grammar scoring. This generic syntax transformation uses no task
data, primitive additions, handwritten scorer or target program. Keep raw
root/replacement provenance and record the canonical candidate so descendant
reconstruction includes alpha renaming. Charge transformation work against
the explicit normalization-node budget and actual CPU, with post-transform
deadline checks. Do not merge distinct value syntax or dependent type
relationships.

Retain the existing no-scorer/zero-scorer equivalence and nonzero causal future
candidate tests. Add scope/type/evaluator preservation, alpha-duplicate and
strict real-pop accounting regressions. Independent source review and commit
precede the registered 600 CPU-second TRAIN pilot. These compiler and
accounting repairs are object-level implementation fixes; a recursive gain
still requires measured learned-procedure improvements and sealed evaluation.
