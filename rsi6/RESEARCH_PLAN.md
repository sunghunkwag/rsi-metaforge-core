# RSI-6 research protocol

Status: **protocol only, version 3. No experimental code exists and nothing has been run.**
Execution is not authorised: it needs a work order carrying the Owner's approval token
(section 9). Version 2 identified the shared learner as the object of the research; version 3
applies the Owner's eight corrections of 2026-11-12 (`OWNER_DIRECTIVE.md`, instruction 6):
single-use adoption environments, measurement on fresh instances, mechanism-only comparisons
across generations, an audit of adapters, matching on measured compute, the audit record of
the external code that was executed, no dependence on a model interface, and the approval
requirements of the constitution.

The four elements the Owner asked for are sections 1 to 4.

## 0. The hypothesis

> A system that modifies its own capability-acquisition mechanism, and adopts only
> independently validated modifications, becomes better at acquiring capabilities in kinds of
> environment it has never met, at matched compute; and the modified mechanism is also better
> at producing the next modification.

It fails if the modified mechanism is not better on unseen kinds of environment, or is better
only by what extra compute, retained solutions, better uninformed search or chance explain.
A second way to fail is expected and is a result: improvement stops after one round because
everything the system can express has been found (the saturation Phase P showed for
self-generated tasks, here at the level of the mechanism).

Solving a benchmark is never an endpoint. Benchmarks appear only as environments in which
acquisition is measured.

## 1. The capability-acquisition mechanism to be modified

**One program, the learner L.** The same code enters every environment. No solver for any
domain is written by a person or by a language model, anywhere in this protocol. L contains no
language model and calls none.

Contract (fixed; the kernel calls only these):

    acquire(environment, compute budget, memory) -> capability, updated memory, self-report
    apply(capability, instance, small compute budget) -> answer

**What every environment gives L** (the generic interface; L never sees an environment's name,
and entity order and labels are permuted by the kernel on every run):

1. the *shape of an answer*, as a composition of generic types: a choice from a finite set, a
   permutation, a selection, a real number in a range, a sequence of steps accepted by a state
   machine;
2. the *instance as plain relational data*: entities, their numeric attributes, weighted
   relations between them, each traceable to a field of the published instance file or to a
   quantity the public specification defines;
3. *verified feedback* on any answer L submits for a training instance: validity, a score, and
   the breakdown the public specification itself defines (which terms or constraints an answer
   component takes part in and what each contributes; for step sequences, how far the state
   machine accepted the steps and the state it reached);
4. *reference answers for training instances*, only where the published data contain them.

**One learning principle.** In every environment L does the same thing: from its own recorded
interactions it learns models that predict how the feedback terms respond to a local change of
an answer; it acts on those predictions; and it distils what worked into a fast policy that
can answer a new instance with very little search. The kinds of local change come from the
answer's generic type (set a component, exchange two, reverse a stretch, perturb a number,
append a legal step), not from the domain.

**Seven functions.** These are the parts of L, and they are what gets modified:

| | Function | What it does in any environment |
|---|---|---|
| 1 | explore | generates interactions to find out how the environment answers |
| 2 | represent | builds descriptors of situations and candidate changes by composing generic aggregation operators over the relational data and the feedback breakdown |
| 3 | model | learns to predict the feedback a change will get; its weights are updated continually |
| 4 | compose | forms larger changes and procedures out of smaller ones that worked together |
| 5 | decide | divides compute between exploring, modelling and exploiting, and chooses among its own procedures |
| 6 | consolidate and transfer | stores what was learned so that a later environment with a similar structure starts from it; detects forgetting |
| 7 | self-assess | holds back some training instances, estimates whether the capability generalises, and reports which function failed when it does not |

Three things are kept apart, because the Owner's third correction depends on it:

* A **capability** is what L stores for one environment: the descriptors it selected, the
  weights it trained, the composite changes it formed, the settings it chose. It is specific to
  that environment.
* **Memory** is the collection of capabilities and records L carries from earlier environments.
* A **version of L** is its code and one bounded record: which variant of each function is
  used, their parameters, and a small library of descriptor templates, composite-change
  templates and control rules written only in the generic vocabulary of the interface. A
  version has a registered size limit and contains nothing that names or encodes an
  environment. Memory and capabilities are not part of a version.

A **modification of the mechanism** is a change to a version: it names the functions it
changes. L at generation 0 has the simplest working form of each function; its code is frozen
and hashed before any environment is drawn or built.

**Outside L and not modifiable by it** (the kernel): the interface, the adapters, the
evaluators, the splits, the compute meter, the ledger, the adoption gate.

**Checks that L stays domain-independent.** (a) L is run on a scrambled copy of every
environment (names, entity order, labels, order of attributes and options permuted); its
scores must agree within seed noise. (b) L's source and every version record are scanned for
any domain's vocabulary. (c) A version must fit the size limit.

## 2. The external environments (evaluation only)

A benchmark is admitted as an environment if: (a) its tasks were defined and published by
others and are fetched as data through an allowed route; (b) a public specification says what
a valid answer is and how it is scored; (c) an independent reference exists for every task;
(d) the evaluator can be written from the specification without executing third-party code and
is shown to agree with the external reference; (e) it is not integer arithmetic, list
manipulation or a puzzle in a fixed small language, in any dressing; (f) its adapter passes
the audit of section 7.

Candidate categories (access probed on 2026-11-11 by fetching the first bytes of one file per
source; nothing executed; nothing in the repository yet). Two environments are in the same
category when they share the answer shape and the structure of the feedback.

| Category | Environment and source | Answer shape | Independent reference |
|---|---|---|---|
| C1 formal proof | Metamath `set.mm` (CC0) | steps accepted by the proof-checking machine | the checking rule; a human proof of every theorem is in the database |
| C2 planning | IPC STRIPS problems | steps accepted by the state machine the files define | plan validity under the published semantics |
| C3 routing, scheduling | TSPLIB; JSPLIB | permutation; permutations per machine | published optimal or best-known values, and optimal tours for a subset |
| C4 numerical modelling | NIST StRD certified regression; SRSD-Feynman | real parameters; predictions on unseen points | NIST certified values; held-out observations generated by the dataset's authors |
| C5 constraint satisfaction | DIMACS colouring; SATLIB | choice per entity | properness and best-known colour counts; satisfaction of every clause |
| C6 forecasting | M4 competition series | real values | the real continuation published by the competition and its naive benchmark |
| C7 allocation, packing | OR-Library knapsack, bin packing, set covering | selection; choice per entity | published optimal or best-known values |

Seven categories are not enough for the design below. Further categories of the same standing
(published instances, a public specification, published optima or certificates) are to be
vetted before registration, among them quadratic assignment (QAPLIB), network flow (DIMACS),
facility location and linear programming with published optimal values, graph partitioning
with best-known cuts, sparse linear systems from applications checked by their residual, and
tabular prediction with held-out labels.

**Roles, and why no adoption decision can overfit.**

* A seeded draw, made after L at generation 0 and the kernel are frozen and hashed, with the
  seed derived from that hash, assigns every admitted category to exactly one role.
* **Initial source** (two categories): the improvement process may use them freely.
* **Adoption sets** (two categories per round, a different pair for every round): the gate of
  round g reads only adoption set g, which no earlier round has used for anything. After the
  round its categories join the source pool. So no decision is ever taken on an environment
  that influenced an earlier decision, and there is no fixed validation set to overfit.
* **Targets** (three categories) and **reserves** (one or more): sealed. Their data are not
  fetched and their adapters are not written until the whole improvement process is complete
  and every version, arm and budget is frozen, hashed and pushed. A reserve replaces a target
  only if the target's adapter fails its audit, and the replacement is reported.
* The number of rounds follows from the number of admitted categories n by this rule:
  G = floor((n − 6) / 2). With G below 2 the recursion claim cannot be tested and the
  experiment is reported as not runnable at that size.

Inside every environment a seeded rule splits the instances into **training** (the only ones
passed to `acquire`) and **fresh** (never passed to `acquire`, scored once per run, never fed
back). Where the benchmark allows, the fresh part includes instances larger than any training
instance.

Not available, with the reason (section 10): real software engineering (scoring means running
third-party test suites), paper review and proof grading (a model must be called on every
task), robotics (no simulator, no GPU).

Two limits. L does not read raw files or specifications: turning a published specification
into the interface is done once per environment by builders, so "unfamiliar data formats" is
not a capability this system acquires. And the candidate categories are known by name to the
author of L at generation 0; what protects the test is that L_0 is frozen before the draw,
that it passes the three checks of section 1, and that target data do not exist on the machine
until the end.

## 3. The independently verifiable criterion

**For one environment E and one version of L**, with budgets registered in advance, three
numbers are measured **on E's fresh instances**, each answered within the same small
test-time budget:

* **untrained**: `apply` with an empty capability, which is L's uninformed behaviour;
* **acquired**: `apply` with the capability returned by `acquire`;
* **gain** = acquired − untrained.

The capability is **previously unavailable** if untrained is below E's threshold and nothing
in L's memory reaches it. It is **acquired** only if all of these hold: acquired reaches the
threshold; untrained does not; gain reaches the registered margin. Thresholds are fixed before
any run on E, from external anchors only (a stated distance from the published optimum, a
stated number of certified digits, the published naive benchmark).

What does **not** count as acquisition, and is reported under its own name: a higher score on
training instances; a higher untrained score ("better uninformed search"); a higher acquired
score with no higher gain.

**Why someone else can verify it.**

* Each evaluator is shown to agree with its external reference before use, and a second
  evaluator written independently by the auditor from the same specification must agree with
  it on a sample of random and reference answers.
* L makes no model calls and is seeded, and budgets are enforced in counted work units, so a
  whole acquisition, not only its product, can be re-run from the stored version, data hashes
  and seeds. The claim is "identical on the same machine and software, and equal within a
  stated tolerance elsewhere"; the tolerance is measured, not assumed.
* Every run, modification, gate decision, score and measured cost goes into an append-only
  hash-chained ledger in the format of the repository's existing ledger, and reports are
  computed from it.
* A separate verification pass by agents that took no part re-runs a sample, re-derives the
  reported numbers, audits adapters, and searches for any read of sealed data.

**For the hypothesis.** A version is always tested with **empty memory**, so that what is
compared is the mechanism and nothing it has accumulated.

* *Per generation, prospectively.* In round g the candidate L_g and its predecessor are each
  run, with empty memory, on adoption set g, which neither has touched. This gives one
  independent test per generation on environments new to both.
* *At the end, on the sealed targets.* Every version L_0 … L_G is run with empty memory on
  every target environment, with identical budgets and seeds.
* Primary endpoint: the mean over target environments and seeds of gain under L_G minus gain
  under L_0. The claim requires this to reach the registered margin with a paired interval
  that excludes zero, requires the acquired score not to be lower, and requires the same
  against every control of section 6.
* Across generations: the trend of gain over L_0, L_1, … L_G on the targets, with environment
  as block, and the sequence of per-generation tests.
* Reported whatever happens: negative transfer, environments where no version acquires
  anything, rejected modifications, rounds in which nothing was adopted, the self-reports of
  which function failed, and for each adopted modification the functions it changed and its
  effect when it alone is removed from L_G.

## 4. How improvements in acquisition become targets of improvement

**L is applied to itself.** The space of versions is presented through the same generic
interface as any other environment: an answer is a modified version; the verified feedback is
the result of acquisition runs of that version on the source pool, broken down per environment
and per function. L therefore acquires the capability "improve L" with the machinery it uses
everywhere: it explores modifications, builds descriptors of them, predicts their effect
before running them, composes them, decides where to spend the few expensive evaluations, and
consolidates which kinds of modification worked. The adopted version performs the next round.
An improvement to exploring, modelling or deciding is used at once in exploring, modelling and
deciding over modifications: the improver is the thing improved.

L's model function, applied here, is a model of its own improvement dynamics, as in arXiv
2610.13991: it forecasts the effect of a modification before the modification is run, and its
forecast error on later records is in the ledger.

**Adoption.** In each round the improver may nominate a registered, small number of candidates
to the gate. A candidate replaces the current version only if, on that round's adoption set,
with empty memory, at the same budgets and seeds, its gain exceeds the current version's by
the registered margin and its acquired score is not lower. Otherwise the current version stays
and the rejection is recorded. Rollback is a pointer to the previous version.

**The test that the recursion matters.** In every round after the first, the same measured
compute is also given to L_0 as improver and to a uniform random proposer, from the same
starting version and seeds, and their nominees go through the same gate. If the current
version's nominees do not validate better than L_0's, the improved mechanism gives no
advantage in the next round, and the finding is "one level of meta-improvement at most". If
neither beats the random proposer, the finding is that the mechanism does not acquire the
capability of improving itself.

**What this path cannot reach.** It can only find versions that L's own parts can express. A
proposer with outside knowledge, such as a language model writing new code for the seven
functions, is **not part of this experiment**: it would be a learned proposal layer, which is
what Amendment A1 would govern, and A1 is not enacted. If the Owner later wants it tested, it
is a separate work order.

## 5. What runs without an external model interface

Everything in this protocol. L, the kernel, the improvement rounds, every arm, the target test
and the replay run on the session's four CPU cores with no model of any kind. The session's
own sub-agents are used only as authors in the outer loop, exactly as sessions already are in
this repository: builders write adapters and evaluators, auditors audit them, reviewers review
the protocol and verify the results. No model output enters a run.

A programmable model interface would be needed only for things this protocol does not attempt:
environments whose tasks need a model call per task, and a mechanism with a language model
inside it. No credential is requested.

## 6. Arms and the matching of compute

All arms share the kernel, the target environments, the budgets and the seeds, and every
version is run with empty memory unless the arm says otherwise.

| Arm | What is run on the targets | What it controls for |
|---|---|---|
| Recursive | L_G, each round performed by the newest version | the hypothesis |
| Frozen original | L_0 | whether anything improved |
| Skills only | L_0's code with its memory filled by its own acquisitions on every source and adoption environment | gains from retained capabilities rather than from the mechanism |
| Recursive with memory | L_G with the memory it accumulated | what accumulation adds on top of the mechanism (reported, never the primary comparison) |
| More compute, no recursion | L_0 given, on each target, its budget plus an equal share of all compute the recursive arm spent on improving itself | gains that compute alone gives |
| Improver frozen | every round performed by L_0 | whether the improved improver matters |
| Random improver | every round performed by uniform random proposals | whether L acquires self-improvement at all |

**Compute is matched on what was actually spent.** The kernel's meter records, for every run,
the CPU-seconds of the whole process tree, wall-clock time, peak memory, evaluator calls and
L's own counted work units, with numerical libraries pinned to one thread and compared arms
interleaved in time on the same machine. Budgets are enforced in work units, which keeps runs
repeatable; arms are matched on measured CPU-seconds. A non-recursive baseline must have
received at least the CPU-seconds of the arm it is compared with, counting the improvement
rounds and gate runs of the recursive arm; a registered rule raises the baseline's work-unit
budget in fixed steps until its measured CPU reaches that amount, and only the first run that
reaches it is scored. A comparison in which the ledger does not show this is void and is
reported as void. The three improvers of the recursion test receive equal measured
CPU-seconds for their whole round, not equal numbers of evaluations.

**A gate before the test.** A pilot on the initial source categories only measures seed-to-seed
variance, the headroom between untrained and acquired, and cost per run. From these the number
of seeds needed for the registered margin is computed. If it cannot be run here, the test is
not run on a weaker design: the shortfall is reported and the targets stay sealed.

## 7. Audit of every adapter

An adapter may do four things only: parse the published files, state the answer shape, expose
the instance as relational data, and evaluate (for step sequences: list the legal steps as the
specification defines them, exhaustively and without ranking, and apply a step). Before an
environment is admitted, an auditor that did not build it checks, and the report is stored:

1. **No hidden solver or heuristic.** The source contains no search over answers, no ordering
   or pruning by objective, no call to an optimisation routine, no table beyond the instance.
   Listings of legal steps are complete and are permuted by the kernel.
2. **No privileged information.** Everything L can observe (shape, relational data, feedback on
   a fixed panel of answers) is byte-identical whether the reference values and reference
   answers are present, absent or replaced by random ones.
3. **Traceability.** Every attribute and relation exposed is mapped, line by line, to a field
   of the instance file or to a quantity the public specification defines. Anything else is
   removed.
4. **No information in order or names.** Relabelling entities gives isomorphic data and equal
   evaluation.
5. **Evaluator agreement.** Published reference answers score as published; corrupted ones are
   rejected; the auditor's independent evaluator agrees with the builder's on random answers.
6. **Leak scan of the task files.** Anything in a published file that states the answer (for
   example certified values printed beside the data) is stripped before L sees the instance,
   and the stripping is tested.

An adapter with a confirmed finding is rejected until fixed and re-audited. The audit reports
are part of the evidence.

## 8. Rules that keep the objective from being replaced

Every experiment is written in this form before any code for it exists, and is rejected if a
line cannot be filled:

1. Which of the seven functions of L does it modify?
2. On which kinds of environment, unseen by that modification, is the effect measured?
3. Which comparison separates "the mechanism got better at acquiring" from "known tasks got
   solved", from "search got better without learning", and from "skills accumulated"?
4. What observation would count against it?

Standing rejections: an endpoint on an environment the mechanism was modified on; any solver,
operator or heuristic written for a domain, in L, in an adapter or anywhere else; any
environment made of integer arithmetic, list manipulation or a fixed small language; a
comparison without the frozen-original and skills-only arms; a comparison whose compute is not
matched in the ledger; a claim from an evaluator whose agreement with its external reference
has not been demonstrated; the word "recursive" for a result that the test at the end of
section 4 does not support.

The earlier RSI-6 material (the frozen Python Programming Puzzles suite, its loader, the
sandbox, the restricted interpreter) is set aside under `rsi6/set_aside_p3/`.

## 9. Governance

* **Approval.** Under Article I.1 and II.4 of `OUTER_LOOP_CONSTITUTION.md` no work order
  executes without the line `APPROVED: <WO-id> <date>` committed by the Owner. This session
  drafts; it does not execute and does not approve. The work is split into two work orders so
  that the Owner approves twice: `docs/work_orders/WO-5_rsi6_build_and_pilot.md` (kernel, L at
  generation 0, adapters with their audits, the pilot on initial source categories), and a
  second one, drafted from the first one's result, for the registered rounds and the target
  test with their numeric predictions.
* **Amendment A1 is not enacted.** No language model is invoked by any code of this
  experiment, and no learned proposal layer is built.
* **Inner kernels untouched** (Article I.4). All code is new, under `rsi6/`. The original
  runtime file is not edited.
* **Resources** (Article I.2). No credential, no external compute and no permission is
  requested. Runs are offline.
* **Verification precedence** (Article I.6). The suite and CI must be green for anything to
  merge. The baseline run of the full suite made on 2026-11-11 (276 passed, 10 failed) was made
  while another process was being killed for lack of memory and is not usable; it is to be
  repeated on a quiet machine as the first step of the first work order.
* **Claim discipline** (Article 0). Section 12.

## 10. Blockers, and the external code that was executed

| | Unavailable | Consequence | Position |
|---|---|---|---|
| B1 | Running third-party code (denied by the session's permission classifier, "Code from External") | no software-engineering environment; no benchmark defined by code | the denial stands; no permission is requested; nothing here needs it |
| B2 | A model interface that programs can call | no judgement environments; no language model inside the mechanism | not requested; not a prerequisite of anything here |
| B3 | GPU and a physics simulator | no robotics environment | not requested |
| B4 | A separate machine for sealed data | sealing is by not creating target data until the end, plus audit | stated as a limit |
| B5 | Compute: four cores | bounds rounds, seeds and candidate evaluations | the pilot gate of section 6 |

The record of the external verifier code that was executed on 2026-11-11 is preserved and
audited in `rsi6/audit/external_code_execution_20261111/`: the one command of the
orchestrating session that was denied, every command and output of the two sub-agents that had
been started two minutes earlier and that executed development-split verifiers natively until
they were stopped, a classification of each command, and the side effects (one out-of-memory
kill; one unrequested probe of system calls inside a sandbox, with no damage found). No number
from those runs is used.

The restricted interpreter (`set_aside_p3/interp.py`) has not been run on any external
verifier and does not preserve the verifiers' semantics: it is a partial re-implementation
with at least six known differences from CPython, one of which can turn a failing verdict into
a passing one, and equivalence could only be shown by the execution that is blocked. No result
may be drawn from it and it is not used.

## 11. Order of work

Under the first work order, after approval:

1. Repeat the baseline run of the repository's full suite on a quiet machine.
2. Freeze the contract of L, the generic interface and the kernel; write L at generation 0;
   hash; make the seeded draw of roles. No environment exists yet.
3. Builders write, for the initial source categories and the adoption sets only, the data
   manifest (source, hash, licence), the adapter and the evaluator; auditors audit them
   (section 7). Data whose licence does not allow redistribution are fetched by hash, not
   committed. Nothing is fetched or written for target or reserve categories.
4. Pilot on the initial source categories only: what L_0 acquires and what it cannot, which
   function fails, variance, measured cost. Power computation; go or no-go.
5. Result document, and the draft of the second work order with its numeric predictions,
   margins, budgets, seeds and failure conditions.

Under the second work order, after approval:

6. The rounds with their gates, together with the improver-frozen and random-improver arms.
7. Freeze, hash and push every version, arm and budget. Only then: build and audit the target
   environments; run the target test once.
8. Independent verification pass and replay. Report: misses first, then what was measured,
   what was predicted, what is not claimed.

## 12. What will not be claimed

No claim of general intelligence or open-ended growth. No claim about software engineering,
robotics or judgement domains. No claim that solving a benchmark is progress on the
hypothesis. No claim that L acquires the reading of new formats or specifications. No claim of
recursion unless the test at the end of section 4 shows it. No claim from an environment the
mechanism was modified on, from training instances, or from untrained scores. If the
improvement saturates, that is reported as the limit of a mechanism that can only recombine
its own parts, with the evidence.

## 13. Relation to the reference designs

HyperAgents (arXiv 2603.19461) makes the part that proposes modifications itself modifiable.
"Predict Before You Modify" (arXiv 2610.13991), which the Owner pointed to, adds an editable
model that forecasts the effect of a modification before it is evaluated, replaced only when
it forecasts later records better, and tests whether what was learned transfers to a new
domain under matched budgets.

Taken from them: the improver is inside what is improved; a learned forecast of a
modification's effect, checked on later records; measurement with the mechanism frozen, on
domains outside its evolution, at matched cost.

Different here, and why: in both papers a frozen language model writes the task agent and the
modifications. Here the object is a learner with no language model in it, which acquires each
capability by interaction, so that no solver is written for a domain, an acquisition can be
repeated exactly, and the test runs on authorised local compute without Amendment A1. Adoption
is an explicit gate on single-use environments of other kinds rather than selection inside one
archive, and the controls for retained skills, extra compute, a frozen improver and a random
improver are run side by side.
