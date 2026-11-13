# WO-5 — RSI-6, PART ONE: THE SHARED LEARNER, ITS KERNEL, AUDITED ENVIRONMENTS, AND A PILOT

**Status: DRAFT. Not issued.** Section (10) is empty; under Article I.1 and II.4 of
`OUTER_LOOP_CONSTITUTION.md` nothing in this order may be executed until the Owner fills it.
**Drafted by:** an orchestrator session on branch `claude/awesome-maxwell-bzw2bj`, on the
Owner's research directive of 2026-11-11 and the Owner's corrections of 2026-11-12
(`rsi6/OWNER_DIRECTIVE.md`, verbatim). It drafts only; it does not execute and does not
approve.
**Numbering:** WO-2 to WO-4 are reserved by Article VII for the conditional track after WO-1.
This order does not belong to that track and does not depend on WO-1 or on Amendment A1.
**Format:** Article IV binding template, sections (1) to (10) in order.
**Companion:** `rsi6/RESEARCH_PLAN.md` (protocol, version 3) gives the reasons. Everything
binding is copied below, so a worker needs no other document to know what is allowed.
**Part two** (the registered improvement rounds and the test on sealed targets) is a separate
work order, drafted from this one's result, with its own approval.

---

## (1) Mission

Build what is needed to test one hypothesis, and run only the pilot: *a system that modifies
its own capability-acquisition mechanism, adopting only independently validated modifications,
becomes better at acquiring capabilities in kinds of environment it has never met, at matched
compute, and the modified mechanism is better at producing the next modification.* The object
under study is one domain-independent learner, L, that enters every environment with the same
code and acquires what it can there by interaction. No solver is written for any domain. This
order delivers the kernel, L at generation 0, audited adapters for external environments, a
pilot on the initial source categories, and the draft of part two. It makes no claim about the
hypothesis: nothing in it can confirm or refute it. The claim of this order is its
certificates: tests, audits, a scored pilot.

## (2) Ground truth (verify in code and files, not prose)

| Item | Where | What to verify |
|---|---|---|
| The Owner's directive and all later instructions | `rsi6/OWNER_DIRECTIVE.md` | read in full before anything else; the prohibitions in (8) are taken from it |
| The protocol | `rsi6/RESEARCH_PLAN.md` | sections 1 to 7 define L, the interface, the roles, the three numbers, the audit, the matching of compute |
| The constitution | `OUTER_LOOP_CONSTITUTION.md` | Articles 0, I, II.4, IV, VIII |
| Amendment A1 | `docs/amendments/A1_learned_proposal_layer.md` | status is DRAFT, not enacted; this order builds no proposal layer |
| The saturation this work starts from | `docs/P_RESULT.md` | cum-crossed 3 at every rung, 0 extensions admitted |
| The existing ledger format | `SCLedger` in `rsi_levels_metaforge_unified.py` (class at line 38577 at commit `ebfb6c3`; the symbol is authoritative) | append-only, each record carries the SHA-256 of the previous one; the new ledger must verify under the same rule |
| The existing budget meter | `AKBudgetMeter` in the same file | logical counts, no wall clock; the new meter adds measured CPU-seconds beside counted units |
| The record of external code executed on 2026-11-11 | `rsi6/audit/external_code_execution_20261111/README.md` | what was run, what was denied; nothing under `workdirs/` may be run |
| What is set aside | `rsi6/set_aside_p3/README.md` | the puzzle suite, its sandbox and the restricted interpreter are not used |

## (3) Binding constraints (inlined)

From the constitution:

* **I.1, II.4.** No execution without the Owner's line `APPROVED: WO-5 <date>` in section (10).
  A worker that does not find it stops and reports.
* **I.2.** No acquisition of compute, credentials, accounts or network reach. Runs are offline.
* **I.3.** All state in the repository; the session is disposable.
* **I.4.** Inner kernels untouched. The original runtime file is not edited; its SHA-256 at the
  start of the work is recorded and must be the same at the end.
* **I.6.** Nothing merges on plausibility: suite green, CI green, reproducibility obligations
  met, the gates of section (7) met.
* **Article 0.** No claim beyond certificates.
* **A1 not enacted.** No language model is invoked by any code delivered under this order.

From the Owner's instructions (2026-11-11 and 2026-11-12):

* The object of the research is the mechanism that acquires capabilities. External benchmarks
  are evaluation environments, never targets of solver optimisation.
* No integer arithmetic, list manipulation, fixed small-language puzzles or disguised
  equivalents as an experimental domain.
* No solver, operator or heuristic written for a domain, anywhere: not in L, not in an
  adapter, not in the kernel.
* Adoption decisions use single-use environments; sealed target categories are untouched until
  the whole improvement process is complete. Under this order **no learner run touches an
  adoption, target or reserve category, and no data of a target or reserve category are
  fetched or written.**
* Performance after learning is measured on fresh instances. Training-instance scores and
  untrained scores are never reported as acquisition.
* Every adapter is audited for hidden solvers, heuristics and privileged information.
* Compute is matched on measured CPU-seconds, not on evaluation counts.
* The denial of external code execution stands. No permission is requested. No third-party
  code is executed.
* No model interface is required and no credential is requested.

## (4) Deliverables

All new code under `rsi6/`; nothing outside it changes except this directory and CI wiring for
the new tests.

1. `rsi6/kernel/`: the generic interface (answer shapes, relational instance data, feedback
   with its breakdown, state machines); the runner that calls `acquire` and `apply` in a
   process without network; the meter (CPU-seconds of the process tree, wall-clock, peak
   memory, evaluator calls, counted work units); the ledger (append-only, hash-chained, in the
   format `SCLedger.verify` accepts); the role lock (a learner run on a category is refused
   unless the registration on file unlocks that role); the scrambler; the split rule
   (training and fresh); the version store with a pointer and rollback; the scans (domain
   vocabulary, version size limit, imports).
2. `rsi6/learner/`: L at generation 0, with the seven functions in their simplest working
   form, the contract of the protocol's section 1, and no domain vocabulary. Developed against
   **contract fixtures only**: tiny synthetic implementations of the interface that exist to
   test the plumbing. Fixtures are not environments, and no number obtained on them is
   reported anywhere.
3. The pre-draw hash of L_0 and the kernel, and the seeded draw of roles derived from it,
   committed before any adapter is written.
4. `rsi6/environments/<name>/` for every category drawn as initial source or adoption set:
   data manifest (source, SHA-256, licence), adapter, evaluator, the traceability map, the
   auditor's independent evaluator, and the audit report of the protocol's section 7. Data
   whose licence does not allow redistribution are fetched by hash and not committed.
5. `rsi6/PILOT_PREDICTIONS.md`: section (6) of this order, committed before the pilot.
6. The pilot on the initial source categories only, in the ledger: for each environment and
   seed, untrained, acquired and gain on fresh instances, the training-instance scores beside
   them, L's self-report of which function failed, measured cost.
7. `rsi6/PILOT_RESULT.md`: every prediction scored, misses first; the map of what L_0 cannot
   acquire and why; variance; the power computation; go or no-go for part two.
8. The draft of part two as a work order with an empty approval line, with numeric predictions,
   margins, budgets, seeds, the number of rounds from the number of admitted categories, and
   the conditions that count as failure.
9. The repeated baseline of the repository's full suite on a quiet machine, recorded.

## (5) Tests first (minimum set; written and failing before the code they test)

Kernel: `test_ledger_verifies_under_core_rule`; `test_meter_records_cpu_and_units`;
`test_role_lock_refuses_adoption_target_reserve`; `test_runner_has_no_network`;
`test_learner_never_receives_environment_name`; `test_acquire_receives_training_instances_only`;
`test_fresh_instances_scored_once_and_not_returned`; `test_scrambler_preserves_evaluation`;
`test_version_size_limit`; `test_vocabulary_scan_rejects_domain_words`;
`test_no_model_or_network_imports_under_rsi6`; `test_core_file_hash_unchanged`;
`test_same_machine_replay_is_identical`.

Per adapter: `test_reference_answers_score_as_published`;
`test_corrupted_answers_rejected`; `test_two_evaluators_agree_on_random_answers`;
`test_observable_bytes_identical_without_references`;
`test_traceability_map_covers_every_exposed_field`; `test_relabelling_gives_equal_evaluation`;
`test_answer_leaks_stripped_from_task_files`.

Red-team (each constructs the attack and must see it rejected): an adapter that leaks a
reference value through an attribute; an adapter that lists legal steps in a helpful order; an
adapter with a search loop; a version record that encodes an instance; a learner that reads an
environment name from the process environment; a run that tries to open a fresh instance
during `acquire`; a learner run on an adoption category.

## (6) Pre-registered predictions (committed before the pilot; misses are scored, not explained away)

Honest expected shape: L at generation 0 is the simplest form of each function and is expected
to be weak. The pilot is expected to show that it learns something measurable in at least one
kind of environment and nothing in at least one other, and that audits find defects in
first-submitted adapters. A pilot in which L_0 acquires everywhere would mean the thresholds or
the test-time budget are too lenient, and is a miss.

| | Prediction | Numeric criterion | A miss means |
|---|---|---|---|
| P1 | The repeated baseline of the full suite is green on a quiet machine | 286 passed, 0 failed | the repository has failures unrelated to this work; reported before anything else is built |
| P2 | Audits find defects | at least 1 first-submitted adapter has a confirmed finding under section 7 of the protocol | either builders are better than expected or the audit is too weak; the red-team tests decide which |
| P3 | Every admitted evaluator reproduces its external references | 100% of tested reference answers score as published (exact for integer objectives; within the stated tolerance for real ones) | the adapter is not admitted |
| P4 | L_0's scores do not depend on names or order | for every initial source environment, the difference between scrambled and unscrambled mean scores is within two standard errors over seeds | L or the interface leaks identity; stop and fix before the pilot counts |
| P5 | L_0 learns something somewhere | in at least 1 initial source environment, gain on fresh instances is positive with a 95% interval over seeds that excludes zero | the mechanism is too weak to study; no-go, reported with the self-reports |
| P6 | L_0 does not acquire everywhere | in at least 1 initial source environment the three conditions for acquisition are not all met | thresholds or the test-time budget are too lenient; they are re-derived from the external anchors before part two |
| P7 | Learning generalises imperfectly | in every environment with positive gain, gain on training instances is at least gain on fresh instances | an error in the split or the scoring; investigate |
| P8 | Work units predict cost | across seeds, CPU-seconds per work unit vary by a coefficient of variation of at most 0.10 within an environment | matching on measured CPU needs more calibration runs than planned |
| P9 | Runs repeat | two runs of the same version, environment and seed give identical ledger records apart from the measured-cost fields | a source of nondeterminism; found and removed before the pilot counts |
| P10 | The test is feasible here | the number of seeds needed to detect the margin proposed for part two, at 80% power with the number of target environments implied by the draw, is at most 10 | no-go for part two at this size; the shortfall is reported and the targets stay sealed |

## (7) Acceptance gates (mechanical)

1. Every test of section (5) passes; the repository's quick CI is green; the original runtime
   file's SHA-256 is unchanged.
2. The ledger verifies under the existing chain rule and every number in `PILOT_RESULT.md` is
   recomputed from it by a committed script.
3. Each admitted environment has a stored audit report with all six checks of the protocol's
   section 7 passed, written by an auditor that did not build it.
4. The ledger shows no learner run on any adoption, target or reserve category, and the
   repository and the manifests contain no data of a target or reserve category.
5. L_0's pre-draw hash, the draw and its seed derivation are committed before the first
   adapter commit. Any change to L_0 after the draw is a recorded bug fix needed for the
   contract (crash, budget violation, nondeterminism) with its diff and reason; a change made
   to raise a score is not allowed. L_0's final hash is recorded at the end of the pilot.
6. `PILOT_PREDICTIONS.md` is committed before the first pilot record in the ledger.
7. Dual run of the pilot finals: identical records apart from measured-cost fields.

## (8) Prohibitions

1. No execution without the approval token; no self-approval.
2. No learner run on an adoption, target or reserve category; no fetching or writing of target
   or reserve data.
3. No solver, operator or heuristic for a domain in L, in an adapter or in the kernel.
4. No environment of integer arithmetic, list manipulation or a fixed small language.
5. No language-model invocation from any delivered code; no network at run time; no
   third-party code executed; nothing under `rsi6/audit/**/workdirs/` or `rsi6/set_aside_p3/`
   is run or imported.
6. No request for execution permissions or credentials.
7. No edit of the original runtime file, of prior committed evidence, or of sealed material of
   earlier packages.
8. No reporting of training-instance scores, untrained scores or fixture results as
   acquisition; no claim about the hypothesis.
9. No tuning after registration: thresholds, budgets, seeds and margins named in
   `PILOT_PREDICTIONS.md` are frozen when it is committed.
10. On any conflict with Article I: stop, report, await the Owner.

## (9) Definition of Done

All gates of section (7) met; `PILOT_RESULT.md` scores every prediction of section (6), misses
first, and states go or no-go; the draft of part two is committed with an empty approval line;
CI green. Done is the certified answer, not a positive answer: "L_0 is too weak to study, and
here is which function fails" and "the test cannot be powered on this machine" are both
deliverables.

## (10) Approval token

APPROVED:
