# REPORT — repository code-repair self-improvement agent

This report documents the upgrade from a VM/bytecode-only synthesis engine to a
**real, source-editing code-repair agent** with adaptive (skill-reusing) vs.
frozen counterfactual evaluation, plus the structural-mutation guarantees
requested. It separates the distinct subsystems honestly and states limits.

Everything is deterministic under fixed seeds. There is **no** task→solution
lookup, **no** oracle/hidden data given to the solver, and unsolved tasks are
reported as **OPEN**, not faked.

## Subsystems (kept separate, not conflated)

| Subsystem | Entry point | What it actually demonstrates |
| --------- | ----------- | ----------------------------- |
| VM program synthesis | `--mode rsi-code` | Evolves real Python functions from primitives (no LLM) and composes them into a deep call chain. A full run yields a **213-line, 31-function** emergent program (`largest_emergent_lines`). |
| Synthetic artifact RSI (8 symbolic layers) | `--mode asi-*-test`, `--mode general-domain-test` | Kernel-judged symbolic self-improvement: learning lowers search cost, abstraction lineage ≥ 3, compression, Socratic-gated operator promotion, and a cross-domain meta-gate (self-proposed macro validates 8 held-out cross-domain tasks the cold baseline cannot; `delta=8`). |
| **Real repository patch-agent** | `--mode repo-rsi-demo`, `repo_rsi.py` | Edits actual `.py` source files to fix real bugs, verified in disposable workspaces by public tests + fuzz regression + canary; learns repair skills; adaptive beats frozen. |
| Verification (all of the above) | `python verify_rsi.py` | Gate 1 (8 layers), Gate 2 (meta-gate), Gate 3 (repo patch-agent). Exits 0 only if all pass. |

## Repository patch-agent architecture (`repo_rsi.py`)

- **`RepoTask`** — a SWE-style task: module file, description, allowed files,
  public test command, a SEALED reference (verifier-only), a fuzz input sampler,
  baseline/patched results, patch diff, verdict.
- **Patch generator** — operates **only on the AST** of the allowed source file.
  Task-agnostic, single-site, minimal-diff operators: comparison / binop /
  boolop / min-max swaps, constant and index adjustment, empty-input guards,
  range-bound adjustment, plus two evolutionary operators — **directed
  structural mutation** and **genetic splicing** (combining two functions' AST
  bodies into a hybrid). The generator receives *only* `(source, op_order)` — it
  never sees the task name, the reference, or any expected output.
- **Verifier harness (ungameable)** — fresh disposable workspace per attempt;
  runs the real public test, then **fuzz-generated regression** + **canary**
  tests derived from the sealed reference on randomized inputs the solver cannot
  predict. Static anti-cheat rejects: editing/weakening/skipping tests,
  special-casing observed inputs, and oversized diffs (patch minimization).
- **Skill library (adaptive memory)** — operator success counts, recency,
  reusable edit templates, file-local pattern memory, and verifier
  counterexamples. The adaptive search tries recently-successful operators first;
  the frozen arm never learns.
- **Counterfactual** — the SAME tasks, seed, and budget run twice (frozen vs.
  adaptive). The reported **recursive gain** is exactly the measured delta.

## Benchmark (6 solvable + 1 OPEN, real source edits)

Six small but real mini-projects, each fixed by a *general* operator (no
task-specific shortcut); two share the deliberately-late `swap_compare` operator
so skill reuse measurably pays off. A seventh task (even-length `median`) needs a
structural rewrite no single operator can synthesise, so it is reported OPEN.

| Task | Project | Bug class | Fixing operator |
| ---- | ------- | --------- | --------------- |
| `rpn_eval` | minilang | interpreter `*` branch wrong | `swap_binop` |
| `second_largest` | collections | data-structure index | `adjust_const` |
| `first_token` | textutils | empty-string edge case | `guard_empty` |
| `count_at_least` | filters | boundary comparison | `swap_compare` |
| `clamp` | api | API behavior (min/max) | `swap_minmax` |
| `is_sorted` | ordering | regression from a prior patch | `swap_compare` |
| `median` | stats | even-length averaging | **OPEN** (structural) |

### Measured result (seed 1234, deterministic)

```
FROZEN   : solved 6/7   total_evals=60
ADAPTIVE : solved 6/7   total_evals=44   skill_reuse=1
recursive_gain: eval_savings=16 (26.67%)   adaptive_beats_frozen=True
OPEN: ['median']
```

The 2nd comparison bug (`is_sorted`) is repaired by the adaptive arm in **1
evaluation** (vs. 15 for frozen) because `swap_compare` was promoted after the
first comparison bug — a genuine, measured search-cost reduction from learning.

## Anti-cheat protections (enforced + tested in `test_repo_rsi.py`, 15 tests)

- baselines genuinely fail (real bugs, not pre-passing);
- the generator's signature is `(source, op_order)` — no task name / oracle;
- the reference is never invoked during candidate generation;
- renaming a task does not change its solution (no name→solution mapping);
- patches that special-case observed inputs are rejected;
- patches that weaken/skip tests, or oversized diffs, are rejected;
- public tests are immutable to the solver (it may edit only non-test files);
- "self-improvement" is reported **only** with an adaptive-vs-frozen delta;
- learned skills are demonstrably reused on a later task;
- the OPEN task is genuinely unsolvable by the operators (not faked);
- structural mutations are **non-trivial**: ≥ 30 % AST-topology divergence while
  remaining functionally isomorphic under fuzzing (a rename/whitespace/wrapper
  change is flagged as a *failure to mutate*); genetic splicing produces a
  functionally-correct hybrid from two incorrect parents;
- the whole run is deterministic (two runs produce identical JSON).

## Structural-mutation contract (the "no trivial mutation" rule)

`directed_structural_mutation` rewrites an accumulation loop
(`acc=0; for x in it: acc=acc+EXPR; return acc`) into
`return sum(map(lambda x: EXPR, it))` — dissolving the `For`/`Assign`/`Store`
loop machinery into a higher-order pipeline. Measured AST-topology divergence is
**0.333 (≥ 0.30)**, it is **not** a trivial rename/`for`→`while` reskin, and it
is verified functionally isomorphic on 512 fuzz inputs.

## How to run

```bash
python verify_rsi.py                              # all three gates
python rsi_metaforge_core.py --mode repo-rsi-demo # patch-agent + counterfactual
python rsi_metaforge_core.py --mode repo-rsi-test # 15 anti-cheat tests
python rsi_metaforge_core.py --mode rsi-code --code-phase base       # base funcs
python rsi_metaforge_core.py --mode rsi-code --code-phase composite  # composites
```

## Honest limitations / open failures

- The benchmark is small and in-repo; mini-projects are tiny. This is a
  reference harness for *honest* repair + skill-reuse measurement, **not** a
  general SWE-bench agent.
- The patch operators are a fixed, general but bounded set. Bugs needing genuine
  multi-line structural synthesis (e.g., even-length `median`) are correctly
  reported **OPEN** rather than faked.
- "Recursive self-improvement" here means: learned repair skills measurably
  reduce future search cost (adaptive < frozen), and abstractions built from the
  system's own solutions extend what it can solve. It is **not** a claim of
  unbounded or general intelligence, and no AGI/ASI flag is set.
- `--mode test` (the 192-test legacy suite) expects the evidence batteries to run
  first for the artifact-backed tests; the heavy `forge-battery` is compute-bound
  in constrained sandboxes (it completes in the Full Evidence CI budget).
