# Research Directive: Open-Ended Recursive Meta-Improvement of General-Purpose Capability Acquisition

Received from the Owner on 2026-11-11 and stored here verbatim. It supersedes the scope of
`rsi5/OWNER_DIRECTIVE.md` for the work in this package.

## PRIMARY OBJECTIVE

Develop and experimentally investigate a general-purpose recursive self-improvement system whose primary object of improvement is its own capability-acquisition mechanism.

The goal is NOT to solve more tasks inside a fixed domain.

The goal is to recursively improve the system's ability to acquire previously unavailable capabilities across heterogeneous, unfamiliar, and independently evaluated domains.

Improve the process that produces new abilities, not merely the performance of abilities already available.

## 1. FUNDAMENTAL REQUIREMENT

Move beyond conventional fixed-domain program synthesis, narrow DSL optimization, integer arithmetic, list manipulation, and benchmark-specific search.

Do not confuse any of the following with general-purpose recursive self-improvement:

* Solving additional integer or list-processing tasks.
* Adding more manually designed DSL primitives.
* Optimizing search inside a fixed task distribution.
* Generating increasingly difficult variations of already solvable tasks.
* Hardcoding domain-specific solutions or manually supplying the missing capabilities.
* Improving benchmark scores without improving the mechanism responsible for acquiring new abilities.
* Repeatedly modifying an algorithm without demonstrating independently verified improvement across generations.

These may be legitimate engineering components, but they are not sufficient evidence for the target phenomenon.

## 2. TARGET: RECURSIVE IMPROVEMENT OF CAPABILITY ACQUISITION

Build a system capable of improving how it:

1. Discovers unfamiliar problem domains and identifies missing capabilities.
2. Constructs or acquires new internal representations, abstractions, tools, and executable operations.
3. Learns new skills from interaction, experimentation, external information, and verified feedback.
4. Transfers acquired knowledge and improved learning strategies across substantially different domains.
5. Modifies its own search, learning, memory, representation, abstraction-discovery, and capability-acquisition algorithms.
6. Retains useful improvements while detecting regressions and catastrophic forgetting.
7. Uses verified improvements to increase the effectiveness of subsequent capability acquisition.

The acquisition mechanism itself must be a target of modification, selection, and improvement.

## 3. OPEN-WORLD CAPABILITY EXPANSION

The system must not be restricted to a permanently fixed task vocabulary, manually enumerated operator catalog, or self-generated task distribution.

Provide pathways for interacting with previously unseen external environments and independently defined tasks.

Potential target domains include:

* Real software engineering and repository-level code modification.
* Mathematical reasoning and formal theorem proving.
* Scientific modeling and numerical simulation.
* Graph algorithms and combinatorial optimization.
* Planning and sequential decision-making.
* Unfamiliar data formats, APIs, and computational environments.

These are evaluation domains, not a collection of handcoded specialist solvers to implement.

No individual domain should define the general improvement mechanism.

New domains must be genuinely external to the system's existing task generator and development feedback.

## 4. SELF-REFERENTIAL META-LEARNING

Implement and test recursive improvement at the level of the learning mechanism itself.

At generation N, the system possesses an acquisition mechanism M_N.

It encounters unfamiliar problems, obtains verified feedback, and proposes modifications to M_N.

Only independently validated improvements may be adopted as M_(N+1).

M_(N+1) must then be evaluated on its ability to acquire capabilities in previously unseen tasks or domains.

The key research question is:

Does a generation that has improved its learning mechanism become better at acquiring genuinely new capabilities than its predecessor, at matched computational cost?

Mere accumulation of solved tasks, cached solutions, or reusable macros does not establish meta-level improvement.

## 5. EXPERIMENTAL DESIGN AND INDEPENDENT VERIFICATION

Use externally sourced, frozen, heterogeneous tasks and strictly held-out evaluations.

Before experimental execution:

* Freeze evaluation sets and computational budgets.
* Pre-register expected improvements and failure thresholds.
* Prevent access to hidden evaluation cases.
* Establish reproducible baselines and negative controls.

Compare at minimum:

1. The recursively modified acquisition mechanism.
2. The original frozen acquisition mechanism.
3. A system that retains skills but cannot modify its acquisition mechanism.
4. A system whose learned state is reset between generations.
5. A nonrecursive system receiving equivalent total compute.

Measure:

* Acquisition success on genuinely unseen domains.
* Computational cost and evaluation calls per acquired capability.
* Adaptation efficiency on previously unfamiliar tasks.
* Cross-domain transfer.
* Retention and regressions.
* Improvements attributable specifically to changes in the acquisition mechanism.
* Whether gains persist through multiple independently evaluated generations.

Report failures, negative transfer, regressions, and stalled improvement trajectories.

A claimed improvement must be able to fail the evaluation.

## 6. ARCHITECTURAL FREEDOM

Do not assume that a fixed symbolic DSL, genetic algorithm, transformer, or any existing algorithm is necessarily the correct foundation.

Investigate alternative approaches when justified, including:

* Open-ended evolutionary search.
* Novelty and quality-diversity search.
* Self-modifying program synthesis.
* Meta-learning and learning-to-learn.
* Representation learning and world models.
* Continual learning and persistent memory.
* Automated tool and abstraction discovery.
* Hybrid symbolic and learned systems.

Use empirical evidence to select mechanisms.

Do not assemble these techniques superficially merely to claim architectural novelty.

## 7. EXISTING REPOSITORY

Continue development from:

https://github.com/sunghunkwag/rsi-metaforge-core

First inspect the actual implementation and its recorded successes, failures, and limitations.

Pay particular attention to the Phase P saturation result:

The self-driven system failed to generate tasks requiring capabilities absent from its existing closure, even though externally supplied extension-requiring tasks could be solved.

Treat this as a central research problem:

How can an acquisition system discover, represent, and pursue capabilities that its current task-generation and representation machinery cannot already express?

Do not repeat Phase P with additional manually supplied primitives and present that as a solution.

Preserve the existing independent verification, immutable evidence, reproducibility, and rollback mechanisms.

## 8. REQUIRED EXECUTION

Do not stop at a conceptual proposal or architectural diagram.

Implement the smallest credible experimental system capable of testing the target hypothesis on genuinely heterogeneous external tasks.

Prefer modifications to the general acquisition mechanism over domain-specific code.

Run experiments, compare against falsifiable baselines, inspect failures, and revise the mechanism when evidence justifies revision.

If a proposed architecture fails, record the failure and investigate a different mechanism.

If the desired generality cannot be achieved, identify the exact limiting assumption or mechanism. Do not replace the objective with an easier toy demonstration.

## SUCCESS CRITERION

The decisive observation would be a sequence of independently verified generations in which:

* The system modifies its own capability-acquisition mechanism.
* The modifications improve acquisition of capabilities not previously available.
* Gains transfer to genuinely unfamiliar tasks or domains.
* The improvements cannot be explained solely by additional compute, retained task-specific solutions, or manually added domain knowledge.
* The improved mechanism itself provides a measurable advantage in subsequent generations.

Treat this as a research hypothesis to test, not an outcome to assume.

FINAL PRIORITY: Recursive improvement of the ability to acquire new abilities, across independently evaluated domains, rather than recursive optimization within a fixed problem space.

## Instructions given in the same session, recorded for the repository

These were given by the Owner in chat on 2026-11-11, before the directive above:

* The original runtime file `rsi_levels_metaforge_unified.py` may be edited where it stands in
  the way, its kernel sections included, without asking first. The directive above then asks to
  preserve the existing independent verification, immutable evidence, reproducibility and
  rollback mechanisms; where the two meet, the later text is followed: mechanisms that verify,
  record or roll back are kept working.
* A learned component whose weights are updated continually is wanted (learning, adaptation,
  continual learning, transfer, meta-reinforcement learning). The weights of the language model
  that writes this code cannot be changed from inside a session; a learned component is a model
  inside the system.

## Further instructions of 2026-11-11, verbatim, in the order received

### 1

Stop treating external puzzle solving as the primary research objective.
The actual goal is Open-Ended Recursive Meta-Improvement of General-Purpose Capability Acquisition.
Do not replace the main objective with another puzzle-solving framework, restricted DSL, or fixed-domain search optimizer.
The permission denial must be handled without bypassing security controls. Report the blocked operation, the applicable limitation, and whether the proposed restricted interpreter preserves the original verifier's semantics. Do not claim independent verification without demonstrating equivalence.
Then redirect the research toward the following:

1. Establish access to multiple genuinely heterogeneous external problem environments through permitted interfaces.
2. Identify capabilities that the current acquisition mechanism cannot obtain.
3. Design and implement a general mechanism for acquiring previously unavailable representations, tools, abstractions, and skills.
4. Make the capability-acquisition mechanism itself modifiable and subject to independent selection.
5. Test whether those modifications improve adaptation to previously unseen domains across successive generations.
6. Compare against nonrecursive, frozen, memory-only, and compute-matched baselines.

Do not count puzzle completion, additional DSL operators, or fixed-distribution policy improvements as evidence of general-purpose recursive capability acquisition.
If the environment cannot support the required experiments, report precisely which capabilities are unavailable and what authorized infrastructure is required. Do not silently substitute easier experiments.
The primary research object must remain the mechanism that acquires new capabilities, not the tasks it already knows how to solve.

### 2

CRITICAL DIRECTIVE: PREVENT OBJECTIVE SUBSTITUTION
You repeatedly regress from open-ended, general-purpose recursive capability acquisition to familiar, fixed-domain optimization problems.
This is a failure of objective preservation, not an acceptable simplification.
Effective immediately:

1. Do not initiate integer arithmetic, list manipulation, small DSL synthesis, or fixed-distribution puzzle optimization as the primary research activity.
2. Do not substitute familiar benchmark improvements for the requested capability-acquisition research.
3. Before implementing an experiment, explicitly identify which component of the capability-acquisition mechanism it modifies and how the result will be tested on previously unseen external domains.
4. Reject experiments that cannot distinguish improvement of the acquisition mechanism from improvement on previously known tasks.
5. Do not reuse the existing repository architecture merely because it is convenient. Replace components when they impose a fixed-domain restriction.
6. If you cannot discover a credible new mechanism, state the specific unsolved research obstacle. Do not conceal that failure by implementing another toy benchmark.
7. Treat repeated return to fixed-domain optimization without a demonstrated cross-domain causal link as an objective-preservation failure.

Your objective is not to produce working code at any cost. Your objective is to discover and test mechanisms that recursively improve the acquisition of genuinely new capabilities.
A failed experiment addressing the correct research question is more valuable than a successful experiment addressing the wrong question.

### 3

Before writing any new experimental code, produce a concrete research plan identifying:

1. The exact capability-acquisition mechanism to be modified.
2. The genuinely external, heterogeneous domains used to evaluate it.
3. The independently verifiable criterion for successful acquisition of previously unavailable capabilities.
4. The mechanism by which improvements in capability acquisition will themselves become targets of subsequent improvement.

Do not start implementation until these four elements are explicitly defined.
Hard constraint: Do not use integer arithmetic, list manipulation, fixed DSL puzzles, or their disguised equivalents as the primary experimental domain.
If the required external environments or verification infrastructure are unavailable, report the blocker rather than reverting to toy tasks.
Do not interpret this restriction as a request to abandon rigorous testing. Use real, independently specified tasks and authorized verification mechanisms.
Do not claim progress toward recursive capability acquisition unless the experiment directly tests that hypothesis.

### 4

https://arxiv.org/abs/2610.13991 ->참조하라

(The Owner's pointer to "Predict Before You Modify: Learning Improvement Dynamics for
Self-Evolving Agents" as a reference; the tracking parameter of the link is dropped.)

### 5

Do not confuse access to ten external datasets with general-purpose capability acquisition.

Metamath, TSPLIB, and JSPLIB are useful independent test environments, but solving their benchmarks is not the primary objective.

Your primary task is to develop a **domain-independent mechanism that improves its own ability to acquire new capabilities**.

Treat external datasets as evaluation environments, not as targets for isolated solver optimization.

The absence of model API credentials is an infrastructure limitation, not justification for reverting to integer, list, DSL, or puzzle-solving experiments.

Use available authorized computational resources. Clearly distinguish experiments that can proceed without external model APIs from those that genuinely require them.

Before implementing domain-specific solvers, identify the shared acquisition mechanism that can learn across these environments, modify that mechanism, and measure whether the modifications improve subsequent acquisition on unseen domains.

Do not begin another fixed-domain optimization project disguised as recursive self-improvement.

## Further instruction of 2026-11-12, verbatim

### 6

The revised research direction is substantially closer to the objective. However, correct the following issues before experimental implementation.

1. Prevent repeated selection against the same adoption-validation categories from causing meta-level overfitting. Keep the final sealed categories untouched until the entire improvement process is complete.
2. Measure post-learning performance on fresh, previously unseen instances. Improvement in training performance or pre-learning search efficiency alone must not count as new capability acquisition.
3. Demonstrate that modifications to L improve the effectiveness of subsequent capability acquisition across generations, rather than merely accumulating skills, memories, or task-specific optimizations.
4. Audit all environment adapters for hidden domain-specific solvers, heuristics, and privileged information.
5. Match actual computational costs across recursive and nonrecursive baselines, not merely evaluation-call counts.
6. Preserve and audit the previously executed external-verifier commands and their outputs. Do not request unrestricted execution permissions or bypass existing controls.
7. Continue using available CPU resources and authorized interfaces. External model API credentials are not a prerequisite for the proposed core experiments.
8. Respect the existing Owner approval requirements and the fact that Amendment A1 remains unenacted.

The decisive research target remains recursive improvement of the general capability-acquisition mechanism itself. Do not downgrade this objective to isolated benchmark optimization.
Proceed with independent design reviews and correct the research protocol before implementing experiments.

### 7

Stop planning and start implementing the actual general-purpose recursive capability-acquisition mechanism.

The four architectural requirements have already been defined. Do not repeatedly restart the planning process.

Implement the learner L, its self-modification mechanism, independent evaluation infrastructure, and multi-generation experiments.

Run the permitted experiments, examine failures, improve the implementation, and report measured results.

Do not substitute toy puzzles or additional planning documents for executable research

(Received in the session on 2026-11-12, after the draft work order WO-5 had been presented
with an empty approval line and the Owner had been told that execution was waiting for it.
Implementation started on this instruction. The approval line of WO-5 was not filled by the
session and stays the Owner's to fill.)

## Instruction 8 (2026-11-12, about 18:30 and 23:25 UTC), verbatim

> 현재 작업 중이냐?

> 그래서 작업 완료 했냐? rsi 성공 했냐?

Answered at the time: the work was not complete and no recursive self-improvement had been
observed (three rounds, six nominees, no adoption).

## Instruction 9 (2026-11-12, about 23:26 UTC), verbatim

> 성공할떄 까지 여러 기법 번갈아서 시도해서 성공 시켜라

How it is carried out (amendment 3): several techniques of self-modification are tried in
turn, generation after generation. What it does not license, under the directive and
instructions 1 to 7, which stay in force: counting a result on categories that were used to
find or to select a modification, lowering a registered rule, opening the sealed targets before
the process is frozen, or reporting as success anything the final test on unseen categories
does not show. A technique is judged on categories its search did not see; success is decided
once, on the reserve categories and the sealed targets.
