# RSI-5 architecture

What exists on the repository now, extended at the end of every phase. The design is
[OWNER_DIRECTIVE.md](OWNER_DIRECTIVE.md) §2; this file describes the built part.

**Status.** Phase 1 built: the forked language, the bottom-up engine, the frozen verifier,
the judge copy and its guard, the registered enumeration-only run. Phases 2–3 not built.

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
  budget is spread across primitives. Child contexts are created and enumerated on
  demand, one per binder chain, to depth 2; their points pair each parent point with up
  to 4 int / 2 list / 2 bool / 2 pair samples drawn from the point's own values, capped
  at 64 points. Pairs are instantiated over the task's element types only.
  `fix1` is instantiated at the task's own type and its body context binds the
  recursive variable to the public example table (angelic recursion); the `fix1`
  program is then evaluated for real. The budget unit is one constructed term evaluated
  on its context's points, counted whether or not observational equivalence keeps it.
- **Closures** ([`engine/closures.py`](engine/closures.py)). A term compiles once to nested
  Python functions `f(env, budget)`; steps are charged per element visited, per `unfold`
  iteration and per `fix1` call. Any failure becomes `ERR` for that point. The closures
  are the fast semantics; a public match is re-checked by the reference interpreter
  before it is returned, so the closures can never produce a false positive.
- **Normal forms** ([`engine/NORMAL_FORMS.md`](engine/NORMAL_FORMS.md)). β-normal and η-long
  by construction; commutative arguments in canonical order; a shallow rewrite set
  refused before evaluation.
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
- [`guard.py`](guard.py): PEP 578 audit hook; the solver process cannot open, list or
  import `rsi5/judge/` or `list_tasks2.json`. `phase1.py` installs it first.
- [`partitions.py`](partitions.py): the exposed partitions through `rsi2`/`rsi3` loaders.
  Everything it loads is exposed and report-only; nothing gates or selects on it.

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
verdict from the verifier. [`report_p1.py`](report_p1.py) computes the tables;
[`audit_p1.py`](audit_p1.py) re-executes every verified program (parsed back from its
readable form by [`dsl/pretty_parse.py`](dsl/pretty_parse.py)) on fresh random inputs
against a reference oracle, report-only, to count coincidental solutions;
[`RESULTS_P1.md`](RESULTS_P1.md) reads them. [`.github/workflows/rsi5-runs.yml`](../.github/workflows/rsi5-runs.yml)
runs the same driver one (vocabulary, partition) per job on Actions for branches named
`rsi5/run-*`.

## Not built

Residuals, fingerprints, clustering, the wide closure C2, gates G1–G3, the vocabulary
ledger, IOU primitives, reverse dreaming, the curriculum, the audits of §8 beyond the
Phase 1 determinism and verifier checks. No learned component exists anywhere.
