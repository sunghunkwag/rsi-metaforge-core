# TRAIN-only bootstrap search comparison

The original registered study and its null outcome remain unchanged. This
development comparison tests fundamentally different search methods against
the repeated-prefix bottleneck before proposing a new recursive learner.
It cannot establish original criteria a–e or a held-out capability gain.

Only the original 36 TRAIN tasks are available to search and diagnosis. Public
examples guide search; their separate hidden examples verify a selected full
program and never guide candidate proposals. No original TEST, research audit,
or validation examples are loaded. Seeds are 11, 22 and 33. Every method starts
from the same frozen primitive grammar, with no library, recognizer or heuristic.

Methods: frozen best-first enumeration; current-prior stochastic sampling;
near-miss cross-entropy sampling; generic typed subtree repair; observational
equivalence bottom-up search; data-derived pointwise decomposition. These are
human-designed candidate kernels, not automatically accepted loop improvements.
No task names, handwritten target ASTs, new primitives, new literals or manual
library/heuristic entries may affect proposals. Partial language coverage must
be stated rather than called exhaustive search.

The first comparison uses 64 logical program attempts per task. Complete and
auxiliary program attempts share this cap. A second development comparison, if
needed, uses 640 under the same accounting. AST size stays 12, expansion cap
20,000, interpreter step cap 2,000. We record all public interpreter calls and
steps, hidden verification calls/steps, draws, generated/filtered candidates,
typed expansions, CPU/wall seconds and the exact admitted solution. Root-only
budget comparisons with uncharged semantic fragments are forbidden. Different
expansion definitions are explicit and cannot support an equal-work claim.

Each method/task has a 10 CPU-second guard; the entire comparison has a 1,800
CPU-second ceiling. Budget exhaustion and partial coverage remain failures or
unknown outcomes. All results, including failures and regressions, are retained.
Kernel selection requires verified TRAIN solution coverage and evidence that
the additional solutions can bootstrap strict real-corpus MDL compression.
Neither a lower surrogate loss nor speed alone supports RSI success.

Each completed comparison produces the requested eleven-field cycle report:
performance, failure clusters, bottleneck abstraction, prior insufficiency,
intervention, mechanism, verification, regression risks, measured result,
keep/revert/revise, and a rule for the next cycle. Promising kernels must next
be tested with common-kernel BASE/BRUTE/ONESHOT/FULL and causal ablations;
synthesized scores must change future candidate generation, and retained
library entries must come from verifier-accepted real TRAIN programs.

Adaptive development may use only TRAIN. A new final evaluation must be
registered and frozen before its examples are opened; it does not replace the
original a–e failure. TEST is never a repeatedly queried optimization objective.
