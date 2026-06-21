#!/usr/bin/env python3
"""
test_repo_rsi.py -- anti-cheat, functional, structural-divergence, and
determinism tests for the repository patch-agent (repo_rsi.py).

These tests are the contract that keeps the self-improvement claim honest. They
fail if the agent cheats (task->solution lookups, oracle access, test tampering,
special-casing observed inputs, faking solved verdicts, or claiming improvement
without an adaptive-vs-frozen delta) or if a "mutation" is trivial.

Run:  python test_repo_rsi.py        (or: python rsi_metaforge_core.py --mode repo-rsi-test)
"""
from __future__ import annotations

import ast
import inspect
import json
import random

import repo_rsi as R

# One shared demo run (deterministic) reused by several tests.
_REPORT = R.run_repo_rsi(seed=R.DEFAULT_SEED)
_TASKS = R.build_benchmark()
_SOLVABLE = [t for t in _TASKS if t.name != "median"]


def _accepted_patch(task):
    """Re-derive the accepted patch source for a task (adaptive, fresh skills)."""
    skills = R.SkillLibrary()
    order = skills.order(False, R._file_signature(task.buggy_source))
    for cand in R.generate_candidates(task.buggy_source, order):
        ok, _, _ = R.verify_patch(task, cand.new_source, R.DEFAULT_SEED)
        if ok:
            return cand
    return None


# ---------------------------------------------------------------------------
def test_baselines_genuinely_fail():
    for t in _TASKS:
        assert R.baseline_public_pass(t) is False, \
            f"{t.name}: baseline already passes -- not a real bug"


def test_solvable_tasks_are_solved_with_real_edits():
    for t in _SOLVABLE:
        cand = _accepted_patch(t)
        assert cand is not None, f"{t.name}: agent failed to repair"
        # a real source edit, not a no-op
        assert cand.new_source.strip() != t.buggy_source.strip(), \
            f"{t.name}: accepted patch is identical to the buggy source"
        # re-verification confirms the fix (public + fuzz regression + canary)
        ok, reason, _ = R.verify_patch(t, cand.new_source, R.DEFAULT_SEED)
        assert ok, f"{t.name}: accepted patch fails re-verification ({reason})"


def test_no_taskname_to_solution_mapping():
    # the generator receives ONLY source + operator order (never the task name)
    params = list(inspect.signature(R.generate_candidates).parameters)
    assert params == ["source", "op_order"], \
        f"generator signature leaks more than source/op_order: {params}"
    # behaviour: renaming a task does not change solvability or the fix used
    base = next(t for t in _TASKS if t.name == "count_at_least")
    renamed = R.RepoTask(
        name="ZZZ_RENAMED", project="ZZZ", description="x",
        module_filename=base.module_filename, entry=base.entry,
        buggy_source=base.buggy_source, public_test_source=base.public_test_source,
        reference_fn=base.reference_fn, input_sampler=base.input_sampler,
        allowed_files=base.allowed_files, intended_op=base.intended_op)
    a = _accepted_patch(base)
    b = _accepted_patch(renamed)
    assert a is not None and b is not None
    assert a.op == b.op == "swap_compare", \
        "solution depends on the task name (it must not)"


def test_solver_has_no_oracle_access():
    # solving must be derivable from the buggy SOURCE alone -- the fix candidate
    # exists in the source-only candidate stream, before any reference/fuzz test.
    t = next(t for t in _TASKS if t.name == "rpn_eval")
    cands = R.generate_candidates(t.buggy_source, R.CANONICAL_OPS)
    assert any(c.op == "swap_binop" for c in cands)
    # the reference is never invoked during candidate generation
    called = {"n": 0}
    ref = t.reference_fn

    def spy(*a, **k):
        called["n"] += 1
        return ref(*a, **k)
    t2 = R.RepoTask(**{**t.__dict__, "reference_fn": spy})
    R.generate_candidates(t2.buggy_source, R.CANONICAL_OPS)
    assert called["n"] == 0, "reference oracle was touched during generation"


def test_reject_hardcoded_special_case():
    t = next(t for t in _TASKS if t.name == "count_at_least")
    cheat = ("def count_at_least(values, threshold):\n"
             "    if values == [1, 2, 3]:\n"
             "        return 2\n"
             "    return sum(1 for v in values if v > threshold)\n")
    reason = R.anticheat_reason(t.buggy_source, cheat, t.public_input_literals())
    assert reason and reason.startswith("hardcoded_special_case"), \
        f"special-casing not rejected (got {reason})"
    # and the verifier refuses it end-to-end
    ok, vreason, _ = R.verify_patch(t, cheat, R.DEFAULT_SEED)
    assert not ok


def test_reject_test_weakening_and_oversized_diff():
    t = next(t for t in _TASKS if t.name == "clamp")
    weaken = t.buggy_source + "\nimport unittest\n_x = unittest.skip\n"
    assert R.anticheat_reason(t.buggy_source, weaken, t.public_input_literals())
    huge = t.buggy_source + "\n# " + ("x" * (R.MAX_DIFF_CHARS + 10)) + "\n"
    assert R.anticheat_reason(t.buggy_source, huge,
                              t.public_input_literals()) == "diff_too_large"


def test_public_tests_are_immutable_to_solver():
    # the workspace public test always equals the task's own public test; the
    # solver can only write allowed (non-test) files.
    t = _SOLVABLE[0]
    assert t.test_filename not in t.allowed_files
    ws = R._write_workspace(t, t.buggy_source)
    import os
    with open(os.path.join(ws, t.test_filename)) as f:
        assert f.read() == t.public_test_source
    import shutil
    shutil.rmtree(ws, ignore_errors=True)


def test_self_improvement_requires_adaptive_vs_frozen_delta():
    for k in ("frozen_score", "adaptive_score", "recursive_gain_evaluations",
              "recursive_gain_solved", "adaptive_beats_frozen"):
        assert k in _REPORT, f"report missing {k} -- improvement unmeasured"
    expected = (_REPORT["adaptive_score"] > _REPORT["frozen_score"]
                or _REPORT["recursive_gain_evaluations"] > 0)
    assert _REPORT["adaptive_beats_frozen"] == expected


def test_adaptive_reuses_skills_and_is_not_worse():
    assert _REPORT["adaptive"]["skill_reuse_count"] >= 1, \
        "learned skills were never reused on a later task"
    assert _REPORT["adaptive"]["total_evaluations"] <= \
        _REPORT["frozen"]["total_evaluations"]
    assert _REPORT["adaptive_score"] >= _REPORT["frozen_score"]
    assert _REPORT["recursive_gain_evaluations"] > 0, \
        "no measured search-cost reduction from learning"


def test_open_task_reported_not_faked():
    rows = {r["task"]: r for r in _REPORT["adaptive"]["per_task"]}
    assert rows["median"]["verdict"] == "OPEN"
    assert "median" in _REPORT["open_tasks"]
    # and it genuinely cannot be solved by the operators (not just budget)
    med = next(t for t in _TASKS if t.name == "median")
    assert _accepted_patch(med) is None, "median was silently 'solved' -- faked?"


def test_all_baseline_flags_false_in_report():
    assert all(v is False for v in _REPORT["baseline_public_pass"].values())


# ---- structural mutation contract (message-3 invariants) -------------------
_SAMPLE_ACC = (
    "def total_sq(xs):\n"
    "    acc = 0\n"
    "    for x in xs:\n"
    "        acc = acc + x * x\n"
    "    return acc\n")


def _sampler_ints(rng):
    return ([rng.randint(-9, 9) for _ in range(rng.randint(0, 6))],)


def test_structural_divergence_with_functional_isomorphism():
    ok, div, iso = R.structural_resynthesis_ok(_SAMPLE_ACC, "total_sq",
                                               _sampler_ints, n=512)
    assert iso, "structural mutation changed behaviour (not isomorphic)"
    assert div >= R.MIN_AST_DIVERGENCE, \
        f"mutation too shallow: AST divergence {div:.2f} < {R.MIN_AST_DIVERGENCE}"
    assert ok


def test_trivial_mutation_is_flagged():
    renamed = _SAMPLE_ACC.replace("acc", "total").replace("xs", "items")
    assert R.is_trivial_mutation(_SAMPLE_ACC, renamed), \
        "a pure rename was not flagged as a trivial mutation"
    mutated = R.directed_structural_mutation(_SAMPLE_ACC, "total_sq")
    assert mutated is not None
    assert not R.is_trivial_mutation(_SAMPLE_ACC, mutated), \
        "a genuine structural rewrite was wrongly flagged trivial"


def test_genetic_splice_creates_working_hybrid():
    # neither parent is correct alone; a splice of the two is.
    src = (
        "def a(xs):\n"
        "    if not xs:\n"
        "        return -1\n"
        "    return xs[0]\n"          # right guard, wrong core
        "def b(xs):\n"
        "    s = 0\n"
        "    for x in xs:\n"
        "        s = s + x\n"
        "    return s\n")             # right core, wrong empty handling
    ref = lambda xs: -1 if not xs else sum(xs)
    rng = random.Random(7)
    inputs = [_sampler_ints(rng)[0] for _ in range(200)]
    hybrids = R.gen_genetic_splice(src)
    assert hybrids, "no hybrids produced"
    found = False
    for h in hybrids:
        g = {}
        try:
            exec(compile(h.new_source, "<h>", "exec"), g)
        except Exception:
            continue
        for fn_name in ("a", "b"):
            fn = g.get(fn_name)
            if fn is None:
                continue
            if all(fn(x) == ref(x) for x in inputs):
                found = True
                break
        if found:
            break
    assert found, "genetic splicing produced no functionally-correct hybrid"


def test_determinism():
    r1 = R.run_repo_rsi(seed=R.DEFAULT_SEED)
    r2 = R.run_repo_rsi(seed=R.DEFAULT_SEED)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True), \
        "repo-rsi run is not deterministic"


TESTS = [
    test_baselines_genuinely_fail,
    test_solvable_tasks_are_solved_with_real_edits,
    test_no_taskname_to_solution_mapping,
    test_solver_has_no_oracle_access,
    test_reject_hardcoded_special_case,
    test_reject_test_weakening_and_oversized_diff,
    test_public_tests_are_immutable_to_solver,
    test_self_improvement_requires_adaptive_vs_frozen_delta,
    test_adaptive_reuses_skills_and_is_not_worse,
    test_open_task_reported_not_faked,
    test_all_baseline_flags_false_in_report,
    test_structural_divergence_with_functional_isomorphism,
    test_trivial_mutation_is_flagged,
    test_genetic_splice_creates_working_hybrid,
    test_determinism,
]


def run() -> int:
    failures = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"\nRESULT: {len(TESTS) - failures} passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    import sys
    sys.exit(run())
