# Follow-up intervention: preserve equivalent evaluations

Registered before executing the intervention. The first procedure study runs
the source at commit `2562f56`. Its source, configuration and evidence remain
unchanged. This follow-up tests the evaluation method, not a new task heuristic
or a different proposal objective. Its design uses development-side repeated
evaluations and bounded-search failures; reporting-only audit results do not
choose the change.

## Bottleneck and mechanism

The first completed development cycles repeatedly assess the same fixed
grammar, recognizer, task examples and scorer in different counterfactual arms.
They also rerun failed budget-16 searches at budget 64 even when the search
stopped before consuming 16 complete-program evaluations. In that case the
candidate budget was not the stopping condition: the unchanged size or
expansion bound ended the same deterministic search. This is an evaluation
memory bottleneck. Semantic eligibility alone does not remove it or establish
task capability.

Replace whole-task-group, arm-local evaluation caches with an exactly scoped,
per-task shared store. Preserve the order of all executable grammar/library
entries, recognizer state, heuristic AST, public and hidden examples, task
type and name, and every search bound. A same-budget hit may reuse any complete
assessment. A higher-budget hit may reuse only a completed public-no-match
assessment with `exhausted=true` and `candidates < source_budget`; every other
scope field must be identical. Public-match/hidden-failure results, budget-hit
results and changed scopes cannot receive this certificate.

This certificate means exhaustion under the recorded search bounds, not
exhaustion of the language or proof that no solution exists. It does not apply
when the expansion or size bound changes. Reassemble task groups in requested
order and retain the original logical search and verifier counters. Record
actual new work separately, with source budget, reuse kind, current operation
time and per-memory actual work counters. Copies cannot mutate stored evidence.

## Fixed comparison

Keep the exact registered configuration, seeds 11/22/33, three arms, three
cycles, proposal draws, preceding-cycle model training, semantic probes,
screen/confirmation selection, strict task-adoption gates and held-out data
separation. Keep the 7,200 aggregate CPU-second watchdog, three one-thread
workers and the conservative 1,800 CPU-second per-seed selection guard. The
only changed executable dependency is evaluation reuse. Initial learning is
rerun; no measurements from the first study are injected into this store.

Within each seed, initial TRAIN and the three arm memories share one store.
Each memory counts only its own executed misses so summing counters does not
double-count shared work. Selection freezes before an isolated reporting-only
audit; no audit result trains the model or changes an accepted rule. The audit
uses the same safe store interface. Output lives in a new directory and never
overwrites the first study.

Compare every completed matched seed/arm/cycle against the first study,
including ASTs, probes, selected and confirmed indices, learned parameters,
incumbents, adoption decisions, task outcomes and logical search/verifier
counters. Ignore only timing, cache metadata and actual-work accounting.
Compare final proposal memory where both selections finish. Unmatched cycles
are new coverage, never evidence of equivalence or savings. Partial runs are
explicitly partial. Report CPU and actual task-search candidates separately;
candidate-count savings do not imply equal per-candidate costs.

## Verifiers and decision

Before launching, test live direct assessment versus decomposed assessment,
shared exact reuse, deep-copy isolation, changed scope misses, a budget-limited
failure that becomes a solution at a larger budget, public-match verifier
failure exclusion, and a failed bounded search whose larger-budget direct
assessment is identical. Test score-blind aggregate stopping and freeze before
audit. Reject an intervention that changes any matched scientific result.

KEEP the evaluation rule only if all completed matched comparisons agree,
the certificate verifiers pass, and matched work has a strict reduction in
actual task-search candidate evaluations. Report zero-candidate searches and
heuristic calls as additional workload evidence rather than ignoring their
cost. If comparisons are missing, distinguish supported matched equivalence
from unknown full-run equivalence. A CPU reduction is secondary evidence under
the same resource ceilings, not a change to the scientific acceptance gate.

Every report includes the eleven requested cycle fields. A kept rule means a
verified loop-level evaluation improvement. It does not establish increased
task-solving capability, autonomous synthesis of arbitrary improvement
algorithms, a verified learned meta-loop gain, or the original RSI criterion.
Any later change to the search policy or learning objective requires a new
development hypothesis and a separate comparison.
