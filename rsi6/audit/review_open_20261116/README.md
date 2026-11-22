# Reviews of the open design and of its experiment, before registration

Two rounds of independent agents, each in an isolated copy of the package with no access to the
experiment's working directory, no network and no learner run on a reserve or a target.

## First review (`review_*.json`, `verification_*.json`)

Three reviewers (the learner, the discovery, the experiment as a whole); every finding rated
blocking or major was given to a separate agent told to refute it. No finding was blocking.
What was confirmed and changed:

* **The learner.** The behaviour key merged mechanisms whose learning principle reads constants
  that no program reads (`mean`, `norm`): it now keeps every constant. Generation 0 of the open
  design was described as the first design in another machine; it differs in several ways that
  matter (one variable scored per step instead of four, so about four times the rounds of
  learning from the same units; step-size floor; three vectors compared on held-back problems;
  scaling of the hard change; fewer terms). The text says so, and comparisons with the first
  design are made at matched CPU.
* **The discovery.** The confirmation passed 41% of attempts on pure noise and re-scored the
  instances it had selected on; growth edits were not neutral (adding a constant re-rolled every
  random draw); arms were matched on steps, not on CPU; the CPU guard could compound; records
  could not be audited. Now: racing leaves the screen seed out of the promoted value;
  confirmation uses seeds used once, a margin and a t threshold; noise is drawn per coordinate
  and growth edits draw none; every lineage is charged its CPU and stops at a registered budget;
  the CPU cap is checked against generation 0 on the same runs and against the parent at
  confirmation; the records hold digests, run keys, seeds, values, t and CPU ratios.
* **The experiment.** Compute-matched controls were missing for the first design and for
  discovery's own compute; the recursion test could be empty; the held-out instances do not
  depend on the seed. Now: a `tune` arm spends the same compute tuning; a principle-swap test;
  the leaks that cannot be removed are stated in the registration.

## Second verification (`second_verification_*.json`)

Three further agents checked the rewritten code and the draft registration. What they found and
what was changed before the registration was recorded:

* **Noise was still accepted at 1 to 2% per step** (13 to 29% of lineages). The threshold is now a
  one-sided t of 2.6 over the 16 pairs; a stub whose runs are noise only gives 0.8 to 1.0% per
  step in the worst case (every candidate confirmed), recorded in the registration as
  `null_calibration`.
* **A change of principle could be a pure reseed** (a dead noise draw). The learning programs now
  have a liveness analysis: dead instructions are neither run nor counted, and a principle is
  identified by its live programs.
* **The confirming half of the fresh instances was used both to accept and to select.** Every step
  of discovery now runs on the deciding half; the confirming half is used only by the selection
  and by the swap assessment.
* **Comparisons between arms were not compute-matched.** Every control (o0, a0 and the finals of
  the frozen, uniform, shuffled and tune arms) is raised to the CPU of the recursive arm's final,
  and every registered comparison is with these; a void comparison does not meet its endpoint.
  The other lineage of every arm is evaluated too, to show the spread.
* **Development had used the registered seeds** and measured the held-out seed 7001 on bin packing.
  Every registered seed is now new, and the registration says what development measured.
* **Files the runs depend on were not hashed**, and the driver did not check them. 32 files are
  hashed, and the driver refuses to start if one differs, if generation 0 differs, or if it is
  given another registration file or ledger.
* Smaller: CPU charged once per run; the tune arm restricted to constants and numbers; arms share
  their random streams so that they differ only where their stated difference acts; confirmation
  seed windows checked; the fallback at test time cannot crash; reproduction rules registered.

Not changed, and stated: the t threshold treats the pairs of one category as independent
although they share their instances; the fitness the discoverer learns from mixes one-seed and
two-seed values; the shuffled arm controls the learning of the weights, not the recursion.
