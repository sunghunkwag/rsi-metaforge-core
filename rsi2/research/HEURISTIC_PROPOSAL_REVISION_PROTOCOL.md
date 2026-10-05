# Own-grammar proposal revision for population search

Existing failure evidence already rejects restarting the same four raw scorer
programs: 144 original proposal slots yielded six distinct ASTs; tied full
confirmations repeatedly chose invalid typed-bottom programs. Repeating this
candidate generator would ignore the diagnosis even though the task kernel
now gives a scorer a causal role in future edits.

Before the recursive TRAIN pilot, replace only the proposal provider with
generic binder-aware own-grammar enumeration. Force the declared four lambda
binders through structural production constraints; retain all original body
productions and their probabilities. Reject syntactically candidate-independent
bodies without interpretation: a body must use an output, size or depth binder;
target-only or constant bodies cannot rank this task's parents. This test is
conservative eligibility, not a hand-authored scorer or performance claim.

Emit four novel own-enumerated scorer programs and two seeded typed-subtree
mutations per generation. Maintain global AST novelty across weight changes,
under immutable append-only library semantics. Rebuilding a stream is allowed
only with every replay/filter expansion charged. Mutation replacements come
from the current enumerator in their correct local binder environments, with
generic capture-safe beta normalization and final type/size verification.

One 20,000 frontier-pop/structural-query cap covers the provider's rebuilt
enumeration and mutation streams; normalization has its own 20,000 AST-visit
cap. Final AST size stays12. Preserve incomplete/empty quota slots explicitly.
The provider performs no evaluator calls or task loading. The controller must
charge validity/informativeness probes and fixed TRAIN screens/confirmations;
strict hidden-verified solved-set expansion with no loss is still necessary
for adoption. Those scores must then control next-generation parent selection.

Synthetic tests must verify binding scope, exact expansion/normalization
accounting, deterministic novelty, immutable library semantics and four+two
slot limits. Independent review and source freeze precede TRAIN execution.
This is a human-designed loop intervention. Its value remains unproven until
the registered causal pilot, ablations and a later sealed evaluation succeed.
