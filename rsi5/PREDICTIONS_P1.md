# Phase 1 predictions: registered before the enumeration-only run

Registered 2026-11-09, in the commit that adds this file, before any task of the run plan
[`runs/p1.json`](runs/p1.json) was run with it. The predictions are
[OWNER_DIRECTIVE.md](OWNER_DIRECTIVE.md) §3.3's, verbatim, scored at the directive's
budget B = 10⁵. The development evidence that existed when this file was written is
stated below it, so a reader can see what was known before the run and what was not.

## The registered experiment

**Question.** On every exposed partition, how many tasks does enumeration alone solve
with RSI-2's vocabulary and with the restored DreamCoder vocabulary, at equal candidate
budgets? This separates "not expressible" from "not found" (§3.3).

**Solver.** C1's bottom-up engine ([`engine/bottomup.py`](engine/bottomup.py)), with no
learning anywhere: programs are built by size (symbols; applications free) from smaller
programs in typed contexts, one program per behaviour on the public inputs plus the
frozen probe set ([`data/probe_set.json`](data/probe_set.json), SHA-256
`0035a70ce09dc5084e86235753eed2b09628a40664f998b3c5c2c4867b0a14b1`), terms outside the
normal form of [`engine/NORMAL_FORMS.md`](engine/NORMAL_FORMS.md) never built. Within a
size level, shapes whose result type is the task's output type are built first, then the
rest, each group interleaved round-robin. Lambda bodies are enumerated to depth 2; a
body context has at most 64 evaluation points (4 int, 2 list, 2 bool, 2 pair samples per
parent point); `fix1` is instantiated at the task's own type with angelic recursion over
the public example table. Fixed: size cap 20 symbols (not binding at these budgets),
interpreter step budget 2000 per evaluation, lists capped at 1024 elements in the engine.

**Vocabularies** ([`dsl/VOCABULARY.md`](dsl/VOCABULARY.md)): `original` = RSI-2's 26
primitives and constants −1 0 1 2; `restored` = original + `unfold index fix1 is_prime
is_square zip pair fst snd` and constants 3 4 5.

**Budget.** The unit is one candidate evaluation: one constructed term evaluated on its
context's points, counted whether or not observational equivalence then discards it.
Terms the normal-form filter refuses are never built and never counted. The plan runs
every task once at B = 10⁶; because the enumeration is deterministic and a task solved
at B is solved at every larger budget by the same program, the solve counts at
B ∈ {10³, 10⁴, 10⁵, 10⁶} are read off that one run (a task counts as solved at B when
its verified program was found within the first B candidates). The directive's
predictions are scored at 10⁵; 10⁶ is reported beside them.

**Verdicts.** The engine sees public examples only. Its first public match is re-checked
with the reference interpreter, then handed once to the frozen verifier
([`verifier.py`](verifier.py)), which checks every public and hidden example. No second
query per task; a public match the verifier rejects is an unsolved task and is counted.

**Partitions** (all exposed, loaded read-only from `rsi2`/`rsi3`): FRESH-1 (33),
FRESH-2 (100), RESERVE-NEAR (100), RESERVE-FAR2 (21), COMPOSE-24 (24), VALIDATION (12);
report-only extras RESERVE-FAR (12) and TRAIN (36). TEST is never opened. J and its
pools are not used in Phase 1.

**Determinism.** FRESH-1 and RESERVE-FAR2 are run twice; the two digests of each
(SHA-256 over every record field except wall-clock) must be identical.

**Headline (§8.1, Phase-1 form).** E = tasks solved with the restored vocabulary whose
family has zero solves with the original vocabulary at the same budget.

## Registered predictions (OWNER_DIRECTIVE.md §3.3, scored at B = 10⁵)

| ID | Prediction | Expected |
| --- | --- | --- |
| P1-1 | Restored vocabulary at B=10⁵ solves ≥ 15 of 33 FRESH-1 (HONEST: 7) | PASS (moderate) |
| P1-2 | Original vocabulary at B=10⁵ solves ≤ 10 of 33 FRESH-1 — most of the gap is vocabulary, not budget | PASS (moderate) |
| P1-3 | At least 2 of the five "corpus-lacking" FRESH-1 routines (`intersperse-k`, `positions`, `uniq`, `identify-is-prime`, `replace-index-k-with-n`) are solved with the restored vocabulary | PASS (low) |
| P1-4 | RESERVE-FAR2 ≥ 10 of 21 (HONEST: 5; HONEST@256: 13) | PASS (moderate) |
| P1-5 | Throughput ≥ 10⁴ candidates/s/core | PASS (low; pure Python) |

Gate: if P1-1 and P1-3 both fail, stop and report (§3.3).

## What was known when this was registered

Development probes before registration, all on FRESH-1 (exposed), seven tasks, both
vocabularies, B up to 10⁶ (`add-k k=10`, `mult-k k=10`, `has-k k=10`, `identify-geq-k
k=7`, `identify-is-prime`, `identify-k k=3`, `positions`, `replace-all-k-with-n`):

- Throughput 20 000–50 000 candidates/s on this machine (Python 3.13, one core per task).
- At B = 10⁵ the original vocabulary completes symbol size 8 in the top context and the
  restored vocabulary size 6: the restored pools are 1.5–4× larger per level (seven
  constants, pairs, `index`), so the same budget reaches one level less.
- The restored vocabulary found `identify-is-prime` at 292 177 candidates and `add-k
  (k=10)` (as `add x (mul 2 5)`) at 260 178; neither was found at 10⁵. The original
  vocabulary found neither at 10⁶. `replace-all-k-with-n (1, 2)` was found by both
  (`add x (div 1 x)`: original 30 231, restored 263 019). `has-k`, `identify-geq-k (k=7)`,
  `identify-k (k=3)` and `positions` were found by neither at 10⁶.

On this evidence the author of this file expects **P1-1 and P1-3 to miss at 10⁵** and
P1-2 and P1-5 to hit; P1-4 is uncertain. The directive's predictions are registered as
written; they are the Owner's forecast, not revised to fit the probes.

## Secondary predictions, registered here (scored at B = 10⁶)

| ID | Prediction | Expected |
| --- | --- | --- |
| S1 | Restored vocabulary FRESH-1 at 10⁶: 10 (range 7–14) | — |
| S2 | Original vocabulary FRESH-1 at 10⁶: ≤ 8 | PASS (moderate) |
| S3 | Closure escape E ≥ 1 at 10⁶: `identify-is-prime` solved with the restored vocabulary, zero solves in that family with the original | PASS (moderate) |
| S4 | Restored ≥ original on FRESH-1 and RESERVE-FAR2 at 10⁶; on RESERVE-NEAR the sign is uncertain (the breadth cost can exceed the vocabulary gain where the original vocabulary suffices) | PASS on FRESH-1 and FAR2 (moderate) |
| S5 | Every program the engine returns passes the verifier (zero public matches rejected on hidden examples) | FAIL expected: 1–5 rejections over all partitions (short public sets, eight examples on FRESH) |
| S6 | COMPOSE-24 at 10⁶: ≤ 4 with either vocabulary (HONEST@256: 4) | PASS (moderate) |

## What this run does not do

No learning, library, recognition model, controller or heuristic. No tuning after this
registration. No J evaluation (J's pools stay sealed for Phase 2). No TEST. The results go
to [RESULTS_P1.md](RESULTS_P1.md) in the `rsi3/*RESULTS.md` form, misses first.
