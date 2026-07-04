# Code-Hygiene Audit — `rsi_levels_metaforge_unified.py`

**Scope:** latent-defect hygiene only — undefined names, spurious f-strings,
doc-vs-code accuracy, and duplicate/dead bindings. **No change** to synthesis
logic, gates, certificates, ISA definitions, adopted-program semantics, tests,
or any evidence artifact. Every claim below was verified against the file with
Python's `ast`/`tokenize` and `pyflakes` — not by trusting line numbers.

**Result:** **8 pyflakes findings fixed** across 5 functions + 1 docstring
(11 insertions, 5 deletions total). Two of the reviewer's five "findings" (the
exec/eval "contradiction" and the "triple `run_tests`") proved to be artifacts
of counting archived source-as-string as live code, and required **no code
change**. Both harnesses remain **156 passed / 0 failed**, and every pinned
evidence digest is **byte-identical** before and after.

---

## 0. Method and the string-archive boundary (read first)

The file is one ~38.5k-line module that concatenates the verified real-search
**runtime core** with a large **`INTEGRATED_SOURCE_ARCHIVE`**: the verbatim
source of ~a dozen constituent modules stored as `r'''...'''` **string
constants**. The big multi-line archive spans (from `tokenize`) are:

| span (lines) | size |
|---|---|
| 17168–32716 | 15 548 |
| 32720–33899 | 1 179 |
| 33903–34479 | 576 |
| 34483–36125 | 1 642 |
| 36129–37508 | 1 379 |

Everything inside those spans is *source-as-string* — never parsed or executed
as Python by this file. **Live** runtime code is everything outside them
(≈ lines 1–16659 and 37509–38569). The live `--mode test` entry point is
`main` (line 38363), which calls the single live `run_tests` (line 3359) over
the module-level `TESTS` registry.

`pyflakes` analyzes only real code (it does not parse string contents), so **all
17 of its findings are in live code**; none is a string-archive false positive.
The two findings that *were* string-archive artifacts (§4, §5) were surfaced by
the external reviewer's raw `grep`, not by `pyflakes`.

---

## 1. Baseline (before any change), commit `d007caf`

- `python3 -m py_compile` → clean, 0 syntax errors.
- **Native registry harness** `--mode test` (after the CI evidence batteries):
  `RESULT: 156 passed, 0 failed` / `ALL TESTS PASSED`.
- **pytest** `-q`: `156 passed in 1769.81s (0:29:29)`.

Both harnesses run the same 156 tests two ways and both require the evidence
artifacts produced by the battery modes (see
`.github/workflows/full-evidence.yml`), so the batteries were run first, exactly
as CI does: `file-battery`, `forge-battery`, `horizon-scan`, `cfs-battery`,
`expansion-battery`, `grammar-battery`, `grammar2-battery` (all exit 0).

Baseline evidence digests (sha256):

```
cf3272c6b1c3615a09008e04623f57c394334a5773f80cfb81abd11c3287ce8f  forge_results.json
051ef6ef423781f4bbf9fafe2b2bf59ae382b4b35d14b3525b1e2f4ab67ac274  file_world_results.json
a9243e00b8ae67961c9beb5a73bb1680ed9b76befe8b747ad9bb0dc0fb9cc363  cfs_results.json
2a1b77cf64b60162b45ee67d0da7ad4897e918a5ab17cfdb0b85c7390dfe215f  expansion_results.json
5ea8ae9d607cee90f0199e7009103266e8443c1d68e03c56d26759524e73dcdf  grammar_results.json
7376ddbdde927c23edd69f17ba27b5f5ace240702bb89bb2885e562e0e87fe58  grammar2_results.json
aaccea1f1b1d131cc95d23d8321833fc34766f391bb911a45ac206bd5eba2949  closure_scan.json
```

---

## 2. Triaged pyflakes table (all 17 findings, all in live code)

Line numbers are the pre-fix positions.

| # | Line | pyflakes finding | Enclosing (live) | Triage | Action |
|---|------|------------------|------------------|--------|--------|
| 1 | 2794 | undefined name `rs` | `demo_counterfactual` | **real runtime risk** — NameError on the adaptive-only branch | **FIXED** → `a` |
| 2 | 10350 | undefined name `shutil` | `provision` (method) | **real latent** — branch unreached by tests | **FIXED** → local import |
| 3 | 13363 | undefined name `time` | `run_cmd` (nested) | **real latent** | **FIXED** → local import |
| 4 | 13370 | undefined name `time` | `run_cmd` (nested) | **real latent** | **FIXED** → local import |
| 5 | 13402 | undefined name `shutil` | `run_self_edit_rsi_loop` | **real latent** | **FIXED** → local import |
| 6 | 13403 | undefined name `shutil` | `run_self_edit_rsi_loop` | **real latent** | **FIXED** → local import |
| 7 | 10207 | f-string missing placeholders | `test_fw_skills_do_not_encode_eval_ids` | harmless (renders identically) | **REPORT ONLY — inside `def test_*`, G1** |
| 8 | 14818 | f-string missing placeholders | `grammar_battery` | harmless (renders identically) | **FIXED** → drop `f` |
| 9 | 14827 | f-string missing placeholders | `grammar_battery` | harmless (renders identically) | **FIXED** → drop `f` (+ continuation 14828) |
| 10 | 2162 | unused local `own_near` | `run_wave` | harmless | report |
| 11 | 4434 | unused local `state0` | `directive_battery` | harmless | report |
| 12 | 7325 | unused local `rs_f` | `hdc_battery` | harmless | report |
| 13 | 8524 | unused local `a_restarts` | `forge_synthesize` | harmless | report |
| 14 | 8993 | unused local `spec` | `forge_battery` | harmless | report |
| 15 | 12442 | unused local `cols` | `_sx_matrix_positive_components` | harmless | report |
| 16 | 14060 | unused local `row_v` | `cfs_battery` | harmless | report |
| 17 | 37552 | `traceback as _traceback` imported but unused | module-level | harmless (style) | report (left; minimal-diff) |

Findings 10–17 are style-level and cannot change behavior; per the ground rules
(minimal diffs; report, don't over-engineer) they are recorded, not touched.

**Post-fix pyflakes = 9 findings**: the 7 unused locals (10–16), the unused
import (17), and the single in-test f-string (7). **Zero undefined names
remain.**

---

## 3. Own sweep beyond pyflakes

- **Duplicate live top-level `def`/`class` names: NONE** (648 live top-level
  defs/classes; `ast` finds no module-scope name bound twice).
- **Bare `except:` in live code: 0.**
- **Mutable default arguments in live code: 1, and it is a false positive** —
  `def f(x, _e=expr, _m=dict(macros))` at line 4326 is the deliberate
  loop-variable-capture idiom: `dict(macros)` snapshots a fresh copy per `def`
  (per loop iteration) and is read-only in `gd_expr_eval`. Not a defect.
- **Live `eval`/`exec`/`compile` calls: NONE** (see §4).

---

## 4. Finding #4 (exec/eval "doc-vs-code contradiction") — resolved; the live doc was already accurate

- `ast.walk` over the whole module finds **zero** live `eval()`/`exec()`/
  `compile()` calls. The live test `test_no_dynamic_python_evaluator_calls`
  (line 3005) asserts exactly this over the file's own AST and passes; it is the
  CI `quick-ci` gate (`--mode test --only no_dynamic`).
- Every `eval(`/`exec(` token the reviewer cited lives **inside
  `INTEGRATED_SOURCE_ARCHIVE` strings**: `exec(` at 20749, 20768, 20943;
  `eval(` at 31902, 33400; and the "no eval(), exec(), imports…" docstring at
  35419 (the archived `ASTExecInjector` class describing itself). All are
  source-as-string, inert as Python.
- The one place archived source is executed **at all** is
  `OrganicSubsystemLoader` (≈ line 37588, `--mode organic`/`organic-test`),
  which loads baked-in embedded source through Python's **import machinery**
  (`spec.loader.exec_module`) — explicitly *not* the `eval`/`exec` builtins (see
  the live comment at line 37605). The source it loads is developer-baked
  archive text, not user-derived input.
- **Security:** no `eval`/`exec` of user-derived input on any path — nothing to
  flag.
- **Action taken (docs only):** the module-docstring line "No eval/exec anywhere
  in the runtime core" was already true; it was **sharpened** to state where the
  tokens live (archive strings) so the confusion cannot recur. The added text is
  inside the docstring literal and creates no Call nodes — the `no_dynamic` gate
  still passes. Commit `6e27d6d`.

---

## 5. Finding #5 (`run_tests` "three module-level defs") — resolved; nothing to remove

- `ast` reports exactly **one** live module-level `run_tests` (line 3359) plus
  one class **method** `run_tests` (line 10541, a different namespace — not a
  shadow).
- The other two `def run_tests` (36056, 37441) are **inside archive strings**
  (spans 34483–36125 and 36129–37508) — archived source of two constituent
  modules, not live bindings. This is also why `pyflakes` never reported a
  `run_tests` redefinition.
- The live `--mode test` entry (`main`, 38363) calls the single live
  `run_tests` (3359). There is no shadowing, no dead module-level binding,
  nothing to rename or remove. **The "dead-binding-removal" commit class is
  empty by design** — fabricating a removal would be wrong.

---

## 6. Fixes applied — per-fix proof

Full diff vs `d007caf`: **11 insertions, 5 deletions**, one file. Three staged
commits, one per defect class.

### Commit `6d3a07a` — undefined-names (6 findings)
- `demo_counterfactual` line 2794: `task_label(rs, …)` → `task_label(a, …)`.
  `a = build_adaptive()` is the adaptive run state; this mirrors `demo()` (line
  2762, where `rs = build_adaptive()`). `task_label(rs: RunState, tid)` (line
  659) takes a run state; `a` is correct. `demo_counterfactual` is called only
  by the `--mode counterfactual` dispatch (line 38398) — **no test touches it**.
- `provision` (10347), `run_cmd` (nested, 13362), `run_self_edit_rsi_loop`
  (13306): added function-local `import shutil` / `import time`, matching this
  ported layer's existing convention (`import shutil` at 9417, 9571;
  `import time as _t` at 13673).
- **Behavior-neutral proof:** every currently-passing test proves these lines
  are unreached — they would raise `NameError` if executed, and the baseline is
  all-pass. Specifically, `provision`'s `shutil.rmtree` is inside
  `if work.exists():`, and all four callers (10935/10966/10983/11008) provision
  into a fresh `tempfile.TemporaryDirectory`, so the branch never runs.
  `run_self_edit_rsi_loop` is **unreferenced** by any live entry point or test.
- **Live proof of the `rs`→`a` fix:** running `--mode counterfactual` on the
  fixed code completes with **0 NameError**, and
  `solved_only_by_adaptive = [T11, T12, T27, T28]` is non-empty, so the
  previously-broken loop (`for tid in only_a: print(name(tid))`) is actually
  executed and now prints `T11 sumx4_sq`, `T12 sum_x8`, `T27 sum_x16`,
  `T28 sum_x32`. Before the fix this run raised `NameError: name 'rs' is not
  defined`.
- **pyflakes:** 0 remaining "undefined name" findings.

### Commit `4b43110` — f-strings (2 of 3 findings)
- `grammar_battery` lines 14818 and 14827/14828: dropped the `f` prefix from two
  placeholder-free header labels. With no `{}` fields, `f"…" == "…"` (verified),
  so stdout and `grammar_results.json` are byte-identical.
- The third f-string (line 10207) is inside `def
  test_fw_skills_do_not_encode_eval_ids` and was **left untouched** (G1 — tests
  read-only). It is likewise harmless.

### Commit `6e27d6d` — doc-fix (exec/eval)
- See §4. Documentation only; `no_dynamic` gate still PASS.

---

## 7. Before/after harness outputs — identical

| harness | before (`d007caf`) | after (fixes) |
|---|---|---|
| native `--mode test` | `RESULT: 156 passed, 0 failed` / `ALL TESTS PASSED` | `RESULT: 156 passed, 0 failed` / `ALL TESTS PASSED` |
| pytest `-q` | `156 passed in 1769.81s` | `156 passed in 1782.34s` |
| evidence JSON digests | see §1 | **all 7 byte-identical** |

After-run evidence digests (identical to §1):

```
cf3272c6…87ce8f  forge_results.json          (identical)
051ef6ef…7ac274  file_world_results.json     (identical)
a9243e00…fb9cc363 cfs_results.json           (identical)
2a1b77cf…e215f    expansion_results.json     (identical)
5ea8ae9d…3dcdf    grammar_results.json       (identical)
7376ddbd…7fe58    grammar2_results.json      (identical)
aaccea1f…ba2949   closure_scan.json          (identical)
```

The touched batteries were re-run from the fixed code and produced byte-identical
artifacts: `file-battery` (touches `provision`) → `file_world_results.json`
identical; `grammar-battery` (touches the f-strings) → `grammar_results.json`
identical. The untouched batteries (`forge`, `horizon-scan`, `cfs`, `expansion`,
`grammar2`) are byte-identical by construction — the diff touches none of their
functions.

**`fileworld/` scratch tree — note.** A raw `find fileworld | sha256sum` differs
run-to-run, but this is **not** a behavior change: two clean runs of the *same*
code differ only in `__pycache__/*.pyc` bytecode caches (which embed source
mtimes — standard Python non-determinism, and `.gitignore`d). Excluding `.pyc`,
the `fileworld/` tree is byte-identical across runs (51 files, 0 non-`.pyc`
differences), and `file_world_results.json` — the pinned evidence — is identical
every time. This non-determinism is pre-existing and independent of this change.

**Determinism (G5):** no fix touches a seeded run path; the deterministic
artifacts match bit-for-bit before and after.

---

## 8. Out-of-scope items found and deliberately NOT touched

- **f-string at 10207** inside `def test_fw_skills_do_not_encode_eval_ids` — G1
  keeps tests read-only. Cosmetic only; renders identically.
- **Seven unused locals** (findings 10–16) and the **unused `traceback as
  _traceback` import** (finding 17) — style, no runtime effect; left under the
  minimal-diff rule.
- **`run_self_edit_rsi_loop`** is defined but **unreferenced** by any live entry
  point or test. The import fix removes a latent `NameError`, but the function
  was **not** removed — removal is out of scope and it may be intended for a
  self-edit mode not wired into `main`.
- No security redesign, no research-logic change, no test-semantics change, and
  no edits inside `INTEGRATED_SOURCE_ARCHIVE` strings (that would change archived
  source and its digests).

---

## 9. Regression test — G1↔G2 tension surfaced, not papered over

G1 permits **adding** a regression test; G2 requires the harness pass count to
be **identical** before/after, and CI pins `RESULT: 156 passed, 0 failed`
exactly (`full-evidence.yml`), with a documented `147→156` pin history. Adding
any module-level `test_*` (or `TESTS` entry) would make the count 157 and turn
CI red — violating G2, the hard gate. So **no registry test was added.** Each
fix is proven instead by (a) the pyflakes finding disappearing, (b) direct
exercise of the previously-broken path (§6, the live `--mode counterfactual`
run), and (c) identical before/after counts and digests.

A ready-to-adopt regression test for the `demo_counterfactual` fix is provided
below for a maintainer who also bumps the pinned count `156 → 157` in the same
change (mirroring the repo's prior "add tests + bump pin" commits):

```python
def test_demo_counterfactual_runs_without_nameerror() -> None:
    # Regression: demo_counterfactual referenced an undefined `rs` in its label
    # lambda; the adaptive-only branch raised NameError. build_adaptive/
    # build_frozen are cached, so this reuses the suite's run states.
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        demo_counterfactual()
    _assert("COUNTERFACTUAL" in buf.getvalue(),
            "demo_counterfactual did not produce its report")
```

---

## 10. Could-not-confirm / open items (honest uncertainties)

- **`run_self_edit_rsi_loop` reachability:** I could not find any live caller or
  `--mode` that invokes it (grep of all call sites + the `main` dispatch). It
  appears to be a latent / future path. The import fix is safe regardless; I did
  **not** remove the function, because "unreferenced today" is not proof of
  "never intended."
- **`fileworld/` raw tree hash** is non-deterministic (bytecode caches, §7). I
  confirmed the cause (only `__pycache__/*.pyc` differ) but did not change any
  behavior to make it deterministic — that would be out of scope, and the pinned
  evidence (`file_world_results.json`) is already deterministic.
- Everything else is confirmed empirically: syntax, both harness counts (156/0),
  and all seven evidence-JSON digests are byte-identical before and after.
