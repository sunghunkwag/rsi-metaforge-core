# Cumulative public-failure credit: prospective research protocol

This protocol registers a proposed loop intervention, not an implemented or
successful learner. The current frozen coordinate diagnostic must finish
unchanged. No VALID, TEST or external audit tasks are loaded for this proposal.
Original RSI criteria a–e remain failed; a new final evaluation requires a
separately frozen complete campaign and independent verification.

## Measured failure and proposed abstraction

The first recursive bootstrap generation 0 contains 2,016 own complete-candidate
trials. Of these, 1,083 report runtime failure, 1,730 match zero public examples,
and only 166 distinct ASTs occur across the task searches. The same generation
selects five independently verified TRAIN solutions. Its 1,488 descendant edges
contain 474 edges whose parent and child both finish without runtime failure.
Eighty improve the recorded exact public-match count, 37 worsen it, and 357 tie.
These 117 directional public-execution contrasts are potential preference
evidence; they are **not independently verified solutions or capability gains**.
Dense residual differences among the 357 ties have not been measured here.
Generation 1 wake again solves five tasks, with 1,070 runtime failures among
1,990 trials. The preserved source is
`recursive_bootstrap_results/FULL_seed11.json.gz`; only its stored own-search
records were read to obtain these counts.

The current recognizer learns from five verified real programs and 16 successful
self-dreams. Rejected real search programs provide no recognition supervision.
The hypothesis is a credit-assignment and memory bottleneck: shared production
decisions receive credit from a tiny positive corpus while the improvement
process discards measured consequences of alternative decisions on difficult
real tasks. Most recorded outcomes are tied or invalid, so merely adding all
failed programs as positive examples would amplify the wrong prior.

Earlier per-task adaptive sampling solved 5/36 at B64 and 7/36 at B640, below the
frozen enumeration's 6/36 and 8/36. That procedure repeatedly fitted four valid
near-miss elites within one task, then discarded its fitted proposal at the
end of the search. It had no task-conditioned cross-task memory, explicit
parent/child counterfactual credit, negative decision contrasts, or prospective
verifier gate for retaining the learned proposal. Those differences motivate
this experiment; they do not prove the new method will work. The same generic
distance can still prefer a misleading constant or identity output.

## Scope and interfaces

Add a separate research recognizer with the frozen `task_features` version1:
32 statistics computed from public examples only, plus its existing bias term.
The prediction interface remains `grammar_for(task, grammar)`. It creates no
DSL primitive, literal, handwritten scorer, target AST or library entry.
Production parameters are learned from measured own-program preferences.
Node/type visits and decision counts are recorded as training/compiler work;
they do not become task-specific handcrafted quality features.

Keep the primitive language, complete final size 12, expansions 20,000,
interpreter limit 2,000, search B64 and BRUTE640 B640, seeds 11/22/33, independent
public+hidden TRAIN root verification, and strict real-corpus MDL library gate.
Failed or near-miss ASTs remain preference records, never verified task/library
labels. Hidden examples can veto a selected complete program but supply no
residual, pair ordering, feature, gradient or proposal score.

No existing modules or coordinate diagnostic eligibility change when this
protocol is committed. Implementation and a physical campaign CPU ceiling
must be frozen before the prospective experiment starts; absence of that
registration is a reason not to launch, not evidence of success.

## Preference extraction and exact residual

Use an actual child-parent genealogy edge from a completed own search. Both
trials must have no runtime failure, no incomplete/public/scorer assessment,
and a complete public output vector of exactly the task's public-example count.
Exclude edges involving runtime errors, truncated outputs, unknown evidence or
missing parents. The error sentinel `outputs=[]` is never interpreted as an
actual empty-list prediction. No additional interpreter calls are needed to
compute preferences from already recorded complete outputs.

Recompute public exact matches with recursive type-aware equality, preserving
the distinction between bool and int. Rank a program lexicographically by:

1. More exact public-example matches.
2. Smaller exact mean normalized residual, only when match counts tie.

For scalar/list values use this single fixed generic residual:

- Different Python/DSL ground value kinds:1.
- Equal values:0; unequal booleans:1.
- Integers: `abs(actual-expected)/(1+abs(actual)+abs(expected))`.
- Lists: `(abs(len(actual)-len(expected)) + sum(d(a,b) for paired items))`
  divided by `max(len(actual),len(expected),1)`.

Use `fractions.Fraction` for integer ratios, recursive sums and task means;
comparison has no floating-point tie threshold or integer clipping. Count the
actual compared nodes and Fraction operations and include their physical CPU.
Do not award a preference for smaller AST size, a different runtime error, or
an arbitrary tie. Equal-quality edges are excluded. This residual is public
proposal evidence only; its reduction can never admit a model by itself.

Canonicalize existing type-variable annotations for stable fingerprints and
retain source generation, parent/child trial IDs, raw/current ASTs and the
whole original request type. Replay `Grammar.decisions` under that request type
and the original immutable library snapshot. Its jointly constrained
production keys and parent/argument contexts are preserved, including bound
variable indices and arities. Do not infer subexpressions in isolation or
silently change type constraints by replaying against a later library.

Canonically order a pair's two AST fingerprints, independently of quality,
as `lo, hi`. Form the contextual difference `D(hi)-D(lo)` and label `y=+1`
when `hi` is preferred or `y=-1` when `lo` is preferred. Thus the signed
difference is `D(preferred)-D(rejected)`. Shared decisions cancel, so an
inherited map/root does not get positive credit merely for appearing in both
alternatives. Exclude a zero difference. Normalize each nonzero difference by
its Euclidean norm for the optimizer; save the unnormalized integer counts,
canonical orientation and signed label as evidence. Deduplicate the same
task-public fingerprint and canonical AST pair across generations.

For `N` contributing fitting tasks and `n_t` retained pairs belonging to task
`t`, set each pair's weight to `alpha=1/(N*n_t)`. Weights sum to one and each
task receives equal total gradient mass. These are generic normalization
rules, not manually selected production priorities.

## Model and cumulative memory

Use the existing linear contextual model shape `(33, contexts, productions)`.
For a pair, the margin is `y` times the dot product of the standardized
public-task feature vector, model parameters and the normalized difference.
Minimize `sum(alpha*logaddexp(0,-margin))` plus the existing ridge penalty.
Use the frozen Recognition defaults: 80 full-batch steps, ridge 1e-3, seeded
initialization scale 0.01, standardized clipping 10 and log-factor clipping 20.
Derive the covariance `C=sum(alpha*x*x.T)` from these same weighted contrast
rows, using the same `1/(largest_eigenvalue(C)+ridge)` formula as the existing
optimizer. Unit-norm differences bound the logistic Hessian by
`0.25*largest_eigenvalue(C)+ridge`, so this rate is conservative. Do not reuse
unrelated positive-corpus decision weights for the contrastive covariance.
Do not tune steps, rates, losses, feature definitions or production weights
against shadow or final evaluation results.

Persist all eligible own preference records and their exclusion reasons.
Refit on cumulative replay after genuinely new pairs arrive. Never multiply a
repeated failed trace's influence by retaining identical copies from later
generations. A proposed contrastive update and its predecessor share the same
positive-label fit, dreamed examples, raw verified bank, grammar/library,
incumbent DSL scorer and budgets. The contrastive update acts only through
learned candidate-generation probabilities. Record pair counts, task counts,
contexts/productions, node/type/decision visits, residual operations, optimizer
steps, matrix sizes, objectives and actual training/prediction CPU.

Align both model states to the same sorted union of contexts and production
keys from the fitting group's own records and common positive/dream corpus.
Use identical initial parameters for that union and align any retained prior
state by its existing keys. Newly introduced keys have neutral zero offsets;
these zero offsets are generic initialization, not supplied production
preferences. No candidate or shadow performance selects that initialization.
Freeze one common feature mean/scale transform for the matched probe using
only fitting-group public-task/common-dream features. Every arm uses that same
transform; arm-specific standardization cannot explain an apparent gain.

The positive-only comparison receives an equal 80-step additional update on
the same positive/dream corpus from this common initial recognition state.
Optimizer loss or a different generated prefix is diagnostic evidence only.
Different matrix/sample costs remain reported; equal candidate/step ceilings
do not imply equal physical training/search effort.

## Required connection to actual candidate generation

The current coordinate provider iterates `Grammar.productions` in definition
order. Its head/insertion order therefore ignores learned log probabilities;
recognition currently influences the initial roots. Before claiming coordinate
improvement from learned recognition, independently verify an explicit route
from learned priorities to **future coordinate candidates**.

The smallest proposed route is stable ordering by the returned production log
probability, using the replayed source's parent/argument grammar context where
available. Uniform cold priorities must preserve original tie order exactly.
Charge ordering/query/compiler CPU and work. Keep a uniform-order ablation
with the same roots, parents, scorer and operator set. This is a separately
registered implementation change; it must not be applied to the currently
frozen coordinate diagnostic. A synthetic test must show two own learned
weight states select different actual future ASTs, with both zero and no DSL
scorer still giving the same sequence under one fixed weight state.

The coordinate operator set also has a **predicted**, presently unmeasured
coverage limitation: same-arity head replacement, permutations and unary
contexts cannot directly create a binary arithmetic spine from a unary scalar
spine. Generic eta views expose its bound input but do not supply a missing
second operand. In the older generation 0 population's 2,016 trial ASTs, the
five frozen integer-binary signatures occur in 132 one-argument spines,
120 zero-argument spines, and only 12 complete two-argument spines. Those 12
occurrences belong to two distinct whole candidate ASTs; none contains a
variable in either arithmetic argument. This measured old-kernel coverage
gap supports a prediction; it does not establish that the current coordinate
diagnostic fails for the same reason.

If actual completed coordinate trials confirm this obstruction,
register a separate generic arity-changing context operator. It may select any
own-grammar production returning the local goal, retain the existing subtree
in each jointly compatible argument role, and fill all remaining typed holes
with its own budgeted enumerator/donor ASTs. Shared polymorphic constraints,
binder origins, final size, generated-state/compiler caps and all semantic
attempts must be accounted. No primitive-specific target pattern is supplied.

Test the weight connection and the structural extension as separate factors;
otherwise their gains cannot be assigned to learned failure credit. A learner
cannot receive credit for an operator that was unavailable to its control.

## Prospective causal verification

Before execution, freeze a name-only internal TRAIN grouping manifest. The
evaluation family identifier is the task name before the first ` with `;
assign its SHA-256 value modulo 3 to a group. Names/group IDs are evaluation
bookkeeping only and never enter model features or candidate generation.
Publish the resulting IDs/hash before reading group performance. Related
parameter variants stay together. Empty or inadequate groups are reported as
unknown; no post-result regrouping is permitted.

Use only designated fitting groups for gradients and replay. The shadow group
supplies prospective public search and independent hidden root verification,
never preference gradients. Because a shadow group participates in admission,
it is development evidence, not a final untouched generalization test. Keep
final VALID/TEST/audit sealed until a complete implementation and campaign
are frozen independently of their outcomes.

The common bank, grammar fit, library, positive labels and dreamed examples
for **every generation** of this grouped transfer probe must derive from
fitting groups only. Do not initialize it with the previous all-TRAIN
recognizer or copied shadow task solution records. Independently verified
shadow solutions remain evaluation records and never enter later fitting
banks, libraries, dreams or gradients. An unrestricted all-TRAIN same-state component
probe may be reported separately, but it is not a held-out-group transfer
result. Partition bookkeeping never changes the candidate language.

Under exactly the same per-generation bank, grammar, library, scorer, seeds
and complete/helper budgets, compare:

- Cumulative contrastive failure credit.
- Cumulative positive/dream-only recognition with the matched extra 80 steps.
- Contrastive recognition frozen after its first update (one-shot).
- Neutral/uniform recognition in the same candidate kernel.
- Fixed-seed permutation of the signed labels across all canonically oriented
  fitting-group pairs, as a credit-assignment control. Sort pair keys before
  the seeded permutation and record the resulting mapping. If labels lack
  variance or the permutation changes no labels, report this control as
  uninformative; do not select a different seed from evaluation outcomes.

Every selected complete program in every arm is independently checked on all
public and hidden TRAIN examples of its task. Record all verifier calls/steps
and rejected selections. Evaluate actual future searches after the admitted
update, not only a reranking of an already evaluated candidate list.

An admission requires a strict independently verified shadow solved-set
expansion without losing previously solved tasks at the fixed limits. An
eligible learned update must improve over its same-state predecessor and the
positive-only/uniform controls on all registered seeds. Reuse that admitted
update in the next generation; compare a subsequent cumulative update against
the retained one-shot state under the next same-state causal probe. Equality,
proxy-only improvement, unrun controls or a partial campaign cannot establish
loop improvement. A failed verifier gate rejects model parameters while
preserving the raw preferences and diagnosis.

Only this prospective chain—public failures produce a learned generative
update, independent hidden verification admits it, and the retained update
improves later production—can support a loop-level result. Human-designed
contrastive loss, ordering hooks and arity extensions are engineering changes.
Original a–e, learned-library benefit, eight-generation progression and final
generalization require their separate complete common-kernel campaign.

## Eleven-field cycle record

- **Current performance:** five verified wake tasks; new method unimplemented.
- **Failure clusters:** repeated candidate syntax, runtime-invalid outputs,
  zero-match plateaus, discarded directional parent/child feedback.
- **Bottleneck abstraction:** insufficient cross-task/cross-generation credit
  for the decisions that change public behavior; possible operator coverage
  disconnect is a prediction awaiting actual coordinate evidence.
- **Prior insufficiency:** local elite count fitting lacked cumulative negative
  contrasts, conditional features and a prospective verifier admission gate.
- **Intervention:** a separately implemented cumulative contrastive recognizer
  and an independently tested generative-priority connection.
- **Expected mechanism:** common decisions cancel; credited local differences
  change which future typed derivations are produced on similar public tasks.
- **Verification plan:** prospective grouped TRAIN, all seeds, matched controls,
  independent complete-root public+hidden checks and next-generation reuse.
- **Regression risks:** misleading near-miss distances, sparse/tied feedback,
  runtime-output sentinels, correlated task variants, prior collapse, extra
  training/search cost, inactive priority wiring and structural coverage gaps.
- **Result after testing:** unrun; 117 measured public directional contrasts
  justify a falsifiable experiment and establish no model/RSI improvement.
- **Keep/revert/revise:** retain this protocol; do not activate a model rule.
- **Updated rule:** public trajectory preferences may propose a generator
  change; preserve it only after independent exact prospective verification
  improves the same-state solved set and the next generation reuses the gain.
