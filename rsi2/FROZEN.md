# Stage 1 freeze

Stage 1 accepted after 33 tests passed in 2.321 seconds. The primitive signatures
in `types.py`, interpreter semantics in `evaluator.py`, and four-argument
heuristic input contract in `search.py` are now frozen. Later stages may learn
lambda abstractions and contextual production weights, but may not introduce
handwritten library entries, primitives, heuristics, or tuned grammar weights.

The grammar starts with uniform contextual weights and integer literals
`-1, 0, 1, 2`, plus boolean literals. Programs are typed de Bruijn ASTs. Curried
head applications and lambda productions support higher-order expressions.
Top-down best-first search uses accumulated log probabilities as admissible
completion bounds. Zero-heuristic complete candidates have decreasing grammar
probabilities. Learned partial scores direct the frontier; arbitrary learned
scores do not promise a global exhaustive ordering over ungenerated programs.

Bounded recursion is provided by fold. Integer arithmetic uses floor division
and Python remainder; unary range produces `[0, ..., n-1]` for positive n.
Head and tail of an empty list fail. Integer values are limited to 4096 bits.
AST preflight, host-input validation, applications and list work consume the
hard interpreter step budget. All ordinary interpreter exceptions become
structured failures. Lazy memoized arguments make if evaluate one branch.

Libraries are named, typed lambda ASTs and can reference preceding entries.
Their use follows the same type-directed production mechanism as primitives.
The heuristic type is `(list[int], list[int], int, int) -> int`: flattened
candidate outputs, flattened target outputs, AST size and AST depth. Partial
and failed candidates have empty output lists. Non-finite queue scores are
treated as failed heuristic evaluations and contribute zero.

Each complete task program attempted counts once, including failures. Output
probes for heuristic priorities count and are cached. Completed programs are
probed only on first dequeue; changing a score from literal zero to a computed
zero preserves the baseline evaluated prefix. Expansion and wall-clock limits
are separate from logical candidate evaluations. Search never receives hidden
examples; selected programs are verified separately.

One Stage 1 correction was used. Initial 31 unit tests passed, but independent
audit found that complete-program score probes at queue insertion let a
computed-zero heuristic see candidates outside BASE's budgeted prefix. Probes
were moved to first dequeue, nonzero priorities reinserted once, and two
independent regressions added. All 33 tests and the exact audit reproduction
then passed. No external corpus had been fetched or learning code introduced.

Profiling identified repeated type substitution/allocation as the main cost.
Immutable concrete type subtrees are reused and empty-library inference has a
bounded 8192-entry cache; charged preflight remains unchanged. Final Stage 1
throughput measurement: 256 candidates, 3072 example evaluations, size bound
12, 3.084529376 seconds, **82.9948 candidates/second**. This measures the
search/evaluator pipeline, not scientific task performance. Larger AST bounds
significantly increase frontier cost; study resource limits must be specified
before final experiments.
