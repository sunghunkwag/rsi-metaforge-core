# Preregistered final experiment

These predictions and parameters are committed before any TEST performance
measurement. Development evidence available now is generation-zero VALIDATION
2/12, seed-11 one-round VALIDATION 1/12, no real library adoption in that smoke
generation, and no strictly better heuristic in its six-candidate search.

The final study uses the sealed 60-task subset (TRAIN 36, VALIDATION 12, TEST 12),
seeds **11, 22, 33**, generations **0 through 8**, and the unchanged calibrated
budgets **B_wake = B_eval = 64**. BRUTE uses **M = 10**, hence 640 evaluations.
Each FULL generation synthesizes four grammar-order heuristics and two seeded
mutations. Every valid proposal is screened on the same first four sorted
VALIDATION tasks at budget 16; the first two by screen solved fraction, with
proposal order breaking ties, are confirmed on all VALIDATION at 64. Duplicates
are screened and charged. Adoption requires strictly higher full VALIDATION
solved fraction. Other parameters are recorded in `experiment_config.json`.

Expected mean TEST solved fractions (not observations):

| Generation | BASE | BRUTE | ONESHOT | FULL |
| --- | --- | --- | --- | --- |
| 0 | 0.1667 | 0.2500 | 0.1667 | 0.1667 |
| 1 | 0.1667 | 0.2500 | 0.0833 | 0.0833 |
| 2 | 0.1667 | 0.2500 | 0.0833 | 0.0833 |
| 3 | 0.1667 | 0.2500 | 0.0833 | 0.1667 |
| 4 | 0.1667 | 0.2500 | 0.0833 | 0.1667 |
| 5 | 0.1667 | 0.2500 | 0.0833 | 0.1667 |
| 6 | 0.1667 | 0.2500 | 0.0833 | 0.1667 |
| 7 | 0.1667 | 0.2500 | 0.0833 | 0.1667 |
| 8 | 0.1667 | 0.2500 | 0.0833 | 0.1667 |

The forecast is a null recursion result, with FULL improvement stopping near
generation 3. These are modest guesses informed only by development partitions;
none may be used to tune the final runs.

Every arm runs with each seed: BASE, BRUTE, ONESHOT, FULL, NO_LIBRARY,
NO_RECOGNITION, NO_HEURISTIC. ONESHOT completes one entire wake–sleep and
heuristic round then freezes. Ablations retain all other FULL components.
Generation zero for learning arms is the BASE state. Frozen deterministic BASE,
BRUTE and post-round ONESHOT measurements may be reused across generations;
artifacts must identify reuse and count actual computation only once.

TEST is loaded only by the separate evaluation entry point. Its search examples
can condition a frozen recognizer during inference, but labels or measurements
never enter training or adoption. Every reported solve must pass its separate
hidden examples. Reporting does not change search parameters or stop an arm
based on performance.

The final-generation heuristic vocabulary comparison screens/confirms the same
six proposal slots with identical seeds, incumbent mutation paths, shared
production weights and task-search state. Only the heuristic-synthesis library
vocabulary is removed in the primitive comparison. Retained incumbent refs are
inlined with independently freshened polymorphic schemes. This comparison does
not update the learner. Both its inner searches and proposals are charged to
FULL computation. Shared task-search state isolates library access during
improver synthesis rather than removing library use from the task solver.

A positive claim requires every Owner criterion:

- (a) FULL final fraction exceeds BRUTE on every seed.
- (b) FULL final fraction exceeds ONESHOT on every seed.
- (c) mean FULL rises on three consecutive generation transitions after
  generation 1, with no seed decreasing on those transitions.
- (d) removing the heuristic lowers final TEST performance; conservatively
  require this on every seed and report both seed values and the mean.
- (e) current-library heuristic synthesis achieves strictly better full
  VALIDATION fraction than primitive-only synthesis at equal six-slot proposal
  budget; conservatively require this on every seed.

At most five worker processes and one NumPy thread each are used. Logical
candidate evaluations, expansions/caps, wall time and process CPU time are
reported separately. The final study stops at approximately 24 aggregate
CPU-hours if that limit prevents completion; incomplete arms must be labeled
unrun/partial, not interpreted as failed scientific criteria. No budget, seed,
split, feature, M, synthesis quota or threshold changes follow TEST exposure.

AST size 12 and expansion limit 20,000 are resource restrictions on this study,
not a claim about the unrestricted DSL. The external corpus has only one to
five hidden examples per selected task, and parameter variants may cross split
boundaries. Conclusions apply to these tasks, limits and observed examples.
