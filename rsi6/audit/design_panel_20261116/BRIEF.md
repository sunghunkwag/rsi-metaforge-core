# Brief for the design panel: what limits measurable recursive self-improvement here, in numbers

Everything below was measured on this machine (4 CPU cores) in this repository. The package copy
is at `../repo/rsi6` (read-only for you). The Owner's instructions are in
`../repo/rsi6/OWNER_DIRECTIVE.md` (read instructions 9 to 13 at the end; they govern the goal).

## The goal (Owner's instruction 13, abridged)

Treat learning, representation, exploration and mechanism discovery as mutable objects of
recursive experimentation; let each discovered mechanism alter how later mechanisms are
generated, evaluated and improved; establish experimentally a learner that improves its own
ability to discover new learning principles; distinguish genuine capability acquisition from
benchmark specialisation, compute scaling and noise; evaluate on independent held-out tasks with
strong baselines, negative controls and reproducible records. Instruction 12: unconventional,
self-discovered mechanisms are welcome; interpretability is not required; reproducibility,
independent verification and measurable gains are.

## The system (read the code)

* Kernel: `rsi6/kernel/` (problem forms, the meter of counted units, the run: acquire on training
  problems of one category, then answer fresh instances untrained and acquired; scores against
  published references; `run.py`, `problem.py`, `environment.py`).
* Learner designs: `rsi6/learner/learner.py` + `version.py` (design a, a 38-field version),
  `design_b.py`, `design_o.py` (design o: score/pick programs and a learning principle written
  as programs of a vector machine; the learning principle sees one scalar fitness per candidate
  constant vector), `design_q.py` (design q: design o plus a search over the score/pick programs
  inside acquisition).
* Discovery: `rsi6/open/discovery.py`, `edits.py` (43 edit cells), `experiment.py` (the
  registered experiment of design o), `evaluate.py` (compute-matched controls: a control's
  training budget is raised until its measured CPU reaches the arm's), `report.py`; the
  registration `rsi6/registry/registration_o.json`; the forks for design q
  (`discovery_q.py`, `experiment_q.py`).
* Earlier processes and their results: `rsi6/RESULTS.md` and `report_main_4505.txt` here.

## Measured facts

1. Earlier processes (designs a and b; three registered rounds, then process c): improvements
   found on source categories were specific to the categories searched (mean correlation of
   per-category effects over candidates about 0); six nominees, none adopted in the first
   rounds; process c adopted one version provisionally (gate +0.0176, lower bound +0.0066,
   confirmation +0.0035); single-field random changes came closest to passing gates.
2. Registered experiment of design o, discovery stage, 29 steps so far over 10 lineages
   (`diagnose_open_discovery.txt` here):
   * a step costs about 400 to 800 CPU-seconds (six candidates, screened on one seed and four
     categories, the best half promoted to two more seeds, the best confirmed on four new seeds);
     a lineage has 6,000 CPU-seconds, so about 10 steps;
   * confirmation: 0 of 4 passed; t values -1.1, 0.5, 1.06, 1.1; the rule needs a mean of about
     0.013 over 16 (category, seed) pairs at the measured paired sd 0.021 (t >= 2.6);
   * winner's curse: confirmed candidates were worth +0.0089 on the discovery seeds and +0.0012
     on the confirmation seeds; correlation of a candidate's value on the screening seed with its
     value on the two promotion seeds: 0.10;
   * the effects of single edits are wide and skewed negative: sd of screening values 0.034
     against 0.011 of noise; mean -0.009; by edit cell, score/replace -0.28, score/mutop -0.15,
     pick/swap -0.059, propose/replace -0.040, score/swap -0.037, scalar/shortlist -0.027, while
     a few cells are mildly positive on average (scalar/batch +0.0045, theta/perturb +0.003,
     score/delete +0.008, propose/swap +0.011, n small);
   * run noise of one mechanism over seeds (sd of the acquired score): job shop 0.033,
     quadratic assignment 0.046, p-median 0.019, bin packing 0.0045, knapsack 0.0 (knapsack's
     acquired score is the same for every mechanism tried: it carries no signal);
   * paired noise (candidate minus parent on the same seed): job shop 0.021, quadratic
     assignment 0.039, p-median 0.006.
3. Design o's acquisition at the registered training budget gets 5 to 8 rounds of its population
   search (16 candidates, batches of 4 problems); gains acquired-minus-untrained: quadratic
   assignment +0.05 to +0.10, job shop +0.005 to +0.07, bin packing +0.05, p-median about 0.
4. Design q (representation search inside acquisition) in development: q0 minus o0, acquired,
   -0.003 over 12 runs (programs switched on noise), then -0.002 over 16 runs with a switch
   confirmed on a second batch (`q_compare1.txt`, `q_compare2.txt`): the inner search is starved
   in the same way (few rounds, noisy 4-problem batches).
5. A measurement of edit effects and paired noise at training budgets 40 and 200 is running
   (results may be added here as `budget_scaling.json`).

## Constraints that cannot be relaxed

* 4 CPU cores; the next registered experiment gets about one day of machine time (roughly
  300,000 CPU-seconds in all, every arm and control included); CPU per run 2 to 35 seconds at the
  registered budget (bin packing is the most expensive of the cheap categories; partitioning and
  set covering cost 100 to 300 seconds per run).
* Registration before the run, predictions on record, compute-matched controls, held-out
  categories that no process has used: four are being built and audited (single-machine
  weighted tardiness, unconstrained binary quadratic programming, resource-constrained project
  scheduling, maximum clique), all in the assignment form. Development only on source categories.
* No language model is called by any code of the experiment; no third-party code is executed;
  the kernel, the meter and the published references are not changed; scores are against
  external references only.
* The acceptance of a mechanism must keep its false-acceptance rate controlled (the registered
  design o rule has about 1% per step under a null calibration).

## Added during the panel: the budget measurement (budget_scaling.json)

Eight single edits of generation 0 of design o (cells init/mutarg, pick/mutarg, score/replace,
score/swap, propose/replace, update/replace, score/replace, pick/mutop), on job shop, p-median and
quadratic assignment, four seeds, at training budget 40 (the registered search budget) and 200:

* CPU per run 7.1 and 27.5 seconds (3.9 times); generation 0's acquired score 0.640 and 0.645, its
  gain +0.021 and +0.027: five times the training budget buys almost nothing for generation 0;
* four of the eight edits changed nothing measurable at either budget (identical runs), although
  the behaviour key took them as changes;
* the harmful edits stay harmful at 200 (score/replace -0.129 and -0.123 over the categories,
  p-median -0.39 and -0.37; score/swap -0.096 and -0.042), none of the eight is beneficial at
  either budget;
* the sd of a 12-pair mean from noise is 0.015 at 40 and 0.006 at 200 (heteroscedastic: harmful
  edits are also noisier).

## Added during the panel: the Owner's instruction 14 (now at the end of OWNER_DIRECTIVE.md)

The Owner sent instruction 14 while the panel was designing. It governs the design that is
implemented. Its requirements, in its own terms: computational representations, reusable
primitives, learning dynamics AND discovery operators must be able to change across generations;
investigate whether discoveries can transform the mechanism that produces subsequent discoveries;
compare joint evolution of representation and discovery operators against fixed, partially
mutable, randomized and equal-compute controls; sealed external evaluation tasks, no leakage, no
evaluator modification, no self-reported success; measure new capability acquisition, transfer,
m_net, computational efficiency, retention and discovery efficiency over successive generations;
the seven learner functions and their boundaries are themselves mutable; if a hypothesis fails,
investigate a substantively different mechanism, not a renamed one. "m_net" is not defined in
the record: a definition must be stated.

## Added during the panel: the correlation of true edit effects across categories (transfer_bound.json)

From the registered discovery's screening runs (439 non-zero candidates): the noise-corrected
correlation of true effects between categories is positive (0.15 to 0.80), but it is carried by
harmful edits, which harm every category at once (an edit that breaks the construction breaks it
everywhere). Over the cells chosen in advance as mild, the estimate is degenerate (noise variance
above the observed variance for quadratic assignment; raw correlations 0.2 to 0.9 driven by a few
joint harms). So the data show that harm transfers; whether benefit transfers is not determined.
