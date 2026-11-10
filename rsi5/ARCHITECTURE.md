# RSI-5 architecture

What exists on the repository now, extended at the end of every phase. The design is
[OWNER_DIRECTIVE.md](OWNER_DIRECTIVE.md) §2; this file describes the built part.

**Status.** Phase 1 built: the forked language, the bottom-up engine, the frozen verifier,
the judge copy and its guard, the registered enumeration-only run. Phases 2–3 not built.
An adversarial review of the Phase 1 pull request found defects in the engine's semantics,
in the sealing and in these documents. The sealing, the driver, the report tool and the
documents were corrected; the engine was not touched, because any repair changes the
registered numbers. Each engine finding is described where it applies below, pinned by a
test in [`tests/test_review_findings.py`](tests/test_review_findings.py) and listed in
[`RESULTS_P1.md`](RESULTS_P1.md), "Adversarial review".

## C1, the fast closure

```
task (public examples)        frozen probe set (data/probe_set.json)
          │                                │
          ▼                                ▼
   top context: variables = the inputs; points = public inputs ∪ probes
          │  size 1: variables, constants, nil
          │  size n: every primitive instance over ground types, every size split,
          │          arguments from pools of size < n; lambda arguments from the
          │          child context (binder(s) added; points = parent points × samples)
          ▼
   normal-form filter ─refuse─▶ never built, never counted
          │
          ▼
   evaluate on the context's points: vectorised (first-order) or compiled closure
   (map/filter/fold/unfold/fix1, rec e)                            ── 1 candidate
          │
          ▼
   observational equivalence: one program per behaviour per type ─dup─▶ discarded
          │
          ▼ (top context, output type, public outputs match)
   re-check with the reference interpreter ─▶ return the term
```

- **Language** ([`dsl/`](dsl/)). `types.py` adds `pair`; `PRIMITIVE_TYPES` is the union of
  RSI-2's 26 primitives and the 9 restored ones. `evaluator.py` is the reference
  interpreter (every verdict comes from it): memoised thunks, lazy `if`, a step budget
  charged for preflight, applications and list work, one step per `unfold` element and
  per `fix1` call, lists and integers capped. `vocabulary.py` names the two vocabularies.
  `grammar.py` is kept for a probability-ordered top-down control; the engine does not use it.
- **Engine** ([`engine/bottomup.py`](engine/bottomup.py)). Size = number of symbols
  (variable, constant, primitive, binder); applications are free. Within a level, shapes
  (primitive, type instance, size split) whose result type is the task's output type
  are built first, then the rest, each group round-robin, so a level cut short by the
  budget is spread across primitives. There is one child context per binder chain. A
  lambda is built only where fewer than two binders are in scope: in the top context and
  in the body of a one-binder lambda (`map`, `filter`, `unfold`). The body of a
  two-binder lambda (`fold`'s step, `fix1`'s body) holds no lambda, and contexts reach
  three binders (a `fold` inside a `map` body). The limit `max_lambda_depth` = 2 thus
  counts binders, not lambda levels, which "depth 2" in `PREDICTIONS_P1.md` did not say.
  A child context is created when a level's shapes are listed and enumerated only when a
  shape needs its programs, so the `contexts` count of a record includes contexts that
  hold nothing. A child's points pair each parent point with up to 4 int / 2 list /
  2 bool / 2 pair samples drawn from the point's own values, capped at 64 points. Pairs
  are instantiated over the task's element types only.
  `fix1` is instantiated at the task's own type and its body context binds the
  recursive variable to the public example table (angelic recursion); the `fix1`
  program is then evaluated for real. The budget unit is one constructed term evaluated
  on its context's points, counted whether or not observational equivalence keeps it.
  A public match is wrapped in one lambda per input and re-checked; the wrapper puts the
  binders in the wrong order when a task has two or more inputs of different types, so
  such a match is always rejected. Every task of the eight exposed partitions has one
  input. The search stops as "exhausted" after one size level that adds no program, which
  is not a proof that larger sizes add none; no record of the registered run has the flag
  set.
- **Closures** ([`engine/closures.py`](engine/closures.py)). A term compiles once to nested
  Python functions `f(env, budget)`; steps are charged per element visited, per `unfold`
  iteration and per `fix1` call. Any failure becomes `ERR` for that point. The closures
  are the fast semantics; a public match is re-checked by the reference interpreter
  before it is returned, so the closures can never produce a false positive.
- **The fast paths are not the reference semantics.** Observational equivalence keys
  programs by what the vectorised operations and the closures compute, and these differ
  from the interpreter: the vectorised `and` and `or` are strict where the interpreter
  and the closures skip the right side; `add` and `sub` have no 4096-bit limit in either
  fast path; the closures charge fewer steps, cap lists at 1024 elements against 4096, and
  evaluate `fix1`'s seed before it is needed; the vectorised `is_prime` charges no step
  and refuses integers above 64 bits. A program
  that the interpreter accepts can therefore carry a failure in its key and miss its
  match, or be pruned as a duplicate of a program the re-check rejects. The loss is in
  completeness only. No record of the registered run has a rejected re-check.
- **Normal forms** ([`engine/NORMAL_FORMS.md`](engine/NORMAL_FORMS.md)). β-normal and η-long
  by construction; commutative arguments in canonical order; a shallow rewrite set
  refused before evaluation. Three rules lose programs the language has (`and`/`or`
  ordering, `neg` of a literal, `fix1` without recursion); the document lists them.
- **Determinism.** No randomness anywhere in a search; iteration orders are sorted names,
  insertion-ordered pools and lexicographic size splits. The same task, vocabulary and
  budget give the same program and the same counts on any worker count (the Phase 1
  files carry a digest over every record field except wall-clock).

## The verifier and the sealing

- [`verifier.py`](verifier.py): a fork of `rsi3/verifier.py`'s `FrozenVerifier` on RSI-5's
  reference interpreter, checking every public and hidden example, one query per task
  per generation, receipts. It is the only module outside `judge/` that reads hidden
  examples; J's static audit, run over `rsi5/` in `tests/test_sealing.py`, reports
  exactly that and nothing else.
- [`guard.py`](guard.py): a PEP 578 audit hook, a tripwire and not a wall. It started as
  `rsi4/guard.py` and refuses a superset of what that hook refuses. Sealed paths: J's
  directory, any file named `list_tasks2.json`, a process's memory file under `/proc`,
  and RSI-2's task-file directory except the four files an exposed-partition loader
  reads, so TEST's file cannot be opened without this package naming it. A sealed path
  cannot be opened, listed, entered, linked or renamed, however it is named: absolute,
  relative, through a symbolic link, as a descriptor, relative to a directory descriptor,
  or as the working directory. Starting another program is refused, because a new
  interpreter would carry no hook; `os.fork` is allowed because the child inherits it.
  J's package cannot be imported in any form. The module's docstring lists what the hook
  does not stop. [`tests/test_guard.py`](tests/test_guard.py) constructs each route on a
  decoy tree.
- **The static half** ([`tests/test_sealing.py`](tests/test_sealing.py)). A solver module
  imports only this package's solver modules, twenty standard-library modules, and in
  `partitions.py` and `audit_p1.py` the read-only loaders. That keeps `ctypes`, native
  modules and `_posixsubprocess` out of the solver's source. It cannot close the unaudited
  process start `multiprocessing.util.spawnv_passfds`: the worker pool needs
  `multiprocessing`, so that package is held to one imported name and one attribute, and
  no solver module spells the identifiers of the unaudited routes; an alias or `getattr`
  gets around both. No solver module imports J in any form, relative forms included, and
  none names RSI-2's sealed loader or its file.
- [`partitions.py`](partitions.py): the exposed partitions through `rsi2`/`rsi3` loaders,
  imported inside `load()` so that a process which loads nothing holds no loader.
  Everything it loads is exposed and report-only; nothing gates or selects on it. The
  RESERVE loaders parse DreamCoder's source file, which holds every record, TEST's twelve
  among them, and keep only names outside the sixty selected tasks; no TEST record
  becomes a task.
- **Process layout** ([`phase1.py`](phase1.py)). The driver installs the guard, forks the
  search workers and only then loads a partition. A worker inherits no task and no
  loader module, seals the `rsi2` and `rsi3` packages for itself (one of their modules
  generates a partition's hidden examples in code) and receives `PublicTask` values: a
  name, a request type and the public examples. The driver holds the tasks and the
  verifier and never searches. The pool never replaces a worker: one that dies breaks the
  pool and the run fails at once. A worker forked after a task was loaded refuses to
  search.
  The driver that produced the registered files built the tasks and the verifier before
  it forked, so its workers held every hidden example in memory; the engine was passed
  the public examples only, and the layout now keeps the rest out of the worker. The
  driver as it stands reproduces the registered digests
  ([`results_p1/replay_sealed/`](results_p1/replay_sealed/); `RESULTS_P1.md` says for
  which partitions).

## J, the judge: copied, unchanged, and a conflict to report

`rsi5/judge/` is `rsi4/judge/` at `c48c820` byte for byte (every file's SHA-256 is
checked against that commit in `tests/test_sealing.py`), with `rsi4/data/stage_train.json`
as `rsi5/data/stage_train.json` because J's manifest covers it; `verify_manifest` passes
in place. J is not used in Phase 1. Two facts about the unchanged copy matter for Phase 2:

1. **J verifies with RSI-2's evaluator and runs RSI-3 solvers.** `judge/evaluate.py`
   checks programs with `rsi2.search.verify` and loads checkpoints through
   `rsi3.longrun.agent_validation`. A program that uses any restored or invented primitive
   is a type error to RSI-2's evaluator, so J as committed cannot count it as solved.
   The directive's G3 ("J evaluates C1 ∪ {f} and C1 ... J is never edited") therefore
   cannot run on this J without one of: (a) an Owner-approved J′ whose verifier is RSI-5's
   reference interpreter and whose solver interface is C1's, kept under the same
   manifest, audit and ledger discipline; or (b) lowering every C1 program to RSI-2's
   language before J sees it, which is impossible for `fix1`, `unfold` and pairs. This is
   reported in the Phase 1 PR as a stop-and-report item for Phase 2; Phase 1 is unaffected.
2. **Package-level strings still say `rsi4`.** `judge/__main__.py` imports
   `rsi4.judge.service` (absent on this branch), and `judge/audit.py` forbids the literal
   `"rsi4.judge"`. The static audit's other rules (dynamic importers, `hidden`
   attributes, pool and seed literals, path parts) apply to `rsi5/` unchanged because
   they are relative to the package directory. The `rsi5.judge` import check is added in
   `tests/test_sealing.py`; a Phase 2 client would start J through `rsi5.judge.service`.

## Phase 1 run

[`phase1.py`](phase1.py) runs the plan [`runs/p1.json`](runs/p1.json): both vocabularies, the
exposed partitions, B = 10⁶ per task, 4 worker processes, one record per task, the
verdict from the verifier. The plan's child-context point cap must equal the engine's
constant and no report budget may exceed the run budget; the driver refuses a plan that
says otherwise. [`report_p1.py`](report_p1.py) computes the tables;
[`audit_p1.py`](audit_p1.py) re-executes every verified program (parsed back from its
readable form by [`dsl/pretty_parse.py`](dsl/pretty_parse.py)) on fresh random inputs
against a reference oracle, report-only, to count coincidental solutions;
[`RESULTS_P1.md`](RESULTS_P1.md) reads them. [`.github/workflows/rsi5-runs.yml`](../.github/workflows/rsi5-runs.yml)
runs the same driver one (vocabulary, partition) per job on Actions for branches named
`rsi5/run-*`.

## Layout against the directive's §11 sketch

- `dsl/VOCABULARY.md`, where §3.1 says to record the list; §11 draws it at the package root.
- `engine/closures.py` holds what §11 calls `compile.py`. `engine/throughput.py` holds the
  micro-benchmark, so that no solver module imports from `tests/`.
- `test_vocabulary_matches_VOCABULARY_md` exists under that name; the per-section tests
  it runs sit beside it.
- `dsl/admitted/` exists and is empty: a static loader with no admitted primitive.
  `wide/`, `gates/`, the ledger and the Phase 2 modules do not exist.

## Not built

Residuals, fingerprints, clustering, the wide closure C2, gates G1–G3, the vocabulary
ledger, IOU primitives, reverse dreaming, the curriculum, the audits of §8 beyond the
Phase 1 determinism and verifier checks. No learned component exists anywhere.
