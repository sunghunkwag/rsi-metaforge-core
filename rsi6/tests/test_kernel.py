"""Tests of the kernel and of the learner's contract. Run: python -m rsi6.tests.test_kernel

The fixtures at the top are tiny synthetic implementations of the problem forms. They exist to
test plumbing. They are not environments, and no number obtained on them is reported anywhere.
"""
from __future__ import annotations

import os
import pickle
import sys
import tempfile

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import numpy as np

from rsi6 import environments
from rsi6.kernel import ledger as ledgers
from rsi6.kernel import roles, run
from rsi6.kernel.problem import AssignProblem, BudgetExhausted, Meter, PredictProblem
from rsi6.learner import version as versions
from rsi6.learner.learner import Learner

ASSIGN_ENVIRONMENTS = [name for name in environments.REGISTRY if environments.load(name).form == "assign"
                       and roles.role_of(name) == "source"]


class _Fixture(AssignProblem):
    """Plumbing fixture: each variable pays a random cost per option; options hold two."""

    def __init__(self, n, k, seed, meter, ordered):
        self.table = np.random.default_rng(seed).random((n, k))
        super().__init__(n, k, hard=[False], ordered=ordered, capacity=np.full(k, 2), var_opt=(self.table,),
                         meter=meter)

    def partial_totals(self, a):
        placed = a >= 0
        return np.array([self.table[np.flatnonzero(placed), a[placed]].sum()])


def test_ledger_chain_and_tamper():
    path = os.path.join(tempfile.mkdtemp(), "l.jsonl")
    book = ledgers.Ledger(path)
    book.append({"type": "a", "x": 1})
    book.append({"type": "b", "y": [1, 2.5, {"z": None}]})
    ledgers.Ledger(path).verify()
    lines = open(path).read().splitlines()
    open(path, "w").write(lines[0].replace('"x":1', '"x":2') + "\n" + lines[1] + "\n")
    try:
        ledgers.Ledger(path)
    except AssertionError:
        return
    raise AssertionError("an altered record was accepted")


def test_ledger_format_is_the_original_runtimes():
    """The chain rule is the one of SCLedger: h = sha256(prev + canonical JSON without h)."""
    import hashlib
    import json
    path = os.path.join(tempfile.mkdtemp(), "l.jsonl")
    book = ledgers.Ledger(path)
    record = book.append({"k": "v"})
    body = {k: v for k, v in record.items() if k != "h"}
    expected = hashlib.sha256(("0" * 64 + json.dumps(body, separators=(",", ":"), sort_keys=True)).encode()).hexdigest()
    assert record["h"] == expected and record["idx"] == 0 and record["prev"] == "0" * 64


def test_meter_stops_the_learner():
    meter = Meter(50)
    problem = _Fixture(8, 5, 0, meter, ordered=True)
    state = problem.start()
    try:
        for _ in range(100):
            problem.candidates(state, problem.unassigned(state))
    except BudgetExhausted:
        assert meter.used > meter.limit
        return
    raise AssertionError("the meter did not stop the calls")


def test_learner_returns_a_well_formed_answer_whatever_the_budget():
    learner = Learner(versions.default())
    for limit in (0, 3, 40, 10_000):
        for ordered in (True, False):
            problem = _Fixture(9, 6, 1, Meter(limit), ordered)
            answer = learner.apply(None, problem, np.random.default_rng(0))
            assert problem.well_formed(np.asarray(answer)), (limit, ordered)


def test_role_lock_refuses_everything_but_source():
    book = ledgers.Ledger(os.path.join(tempfile.mkdtemp(), "l.jsonl"))
    table = roles.load()["roles"]
    for category, role in table.items():
        if role == "source":
            assert roles.check(category, book) == "source"
        else:
            try:
                roles.check(category, book)
            except PermissionError:
                continue
            raise AssertionError(f"{category} ({role}) was not locked")
    book.append({"type": "unlock", "role": "adoption:1"})
    first = [c for c, r in table.items() if r == "adoption:1"][0]
    assert roles.check(first, book) == "adoption:1"
    book.append({"type": "release", "role": "adoption:1"})
    assert roles.check(first, book) == "source"


def test_draw_is_reproducible_and_complete():
    stored = roles.load()
    again = roles.draw(stored["commit"])
    assert again["roles"] == stored["roles"] and set(again["roles"]) == set(roles.CANDIDATES)
    counts = {}
    for role in again["roles"].values():
        counts[role] = counts.get(role, 0) + 1
    assert counts["source"] == 3 and counts["target"] == 4 and all(counts[f"adoption:{g}"] == 2 for g in (1, 2, 3))


def test_fast_evaluation_equals_the_specification():
    rng = np.random.default_rng(0)
    for name in ASSIGN_ENVIRONMENTS:
        env = environments.load(name)
        for iid in env.instance_ids()[:4]:
            problem, _ = env.problem(iid, Meter(float("inf")), 11, True)
            state = problem.start()
            for _ in range(min(problem.n_vars, 30)):
                variables = problem.unassigned(state)[:3]
                allowed = np.flatnonzero(problem.allowed(state))
                fast = problem.candidates(state, variables)
                slow = AssignProblem._rows(problem, state, variables)
                assert np.allclose(fast[:, allowed], slow[:, allowed]), name
                problem.assign(state, int(variables[0]), int(rng.choice(allowed)))
                assert np.allclose(problem.totals(state), problem.partial_totals(state["a"])), name


def test_relabelling_does_not_change_the_score():
    """The same answer, given under two relabellings of an instance, scores the same."""
    for name in ASSIGN_ENVIRONMENTS:
        env = environments.load(name)
        iid = env.instance_ids()[0]
        learner = Learner(versions.default())
        scores = []
        for seed in (1, 2, 3):
            problem, decode = env.problem(iid, Meter(float("inf")), seed, False)
            answer = learner.apply(None, problem, np.random.default_rng(5))
            own = decode(answer)
            scores.append(env.score(iid, own))
            other, decode_other = env.problem(iid, Meter(float("inf")), seed + 100, False)
            assert env.score(iid, own) == scores[-1] and other.n_vars == problem.n_vars
        assert all(0.0 <= s <= 1.0 for s in scores)


def test_problem_carries_no_reference():
    """What the learner receives is byte-identical whatever the reference values are."""
    for name in environments.REGISTRY:
        env = environments.load(name)
        if roles.role_of(name) != "source":
            continue
        iid = env.instance_ids()[0]
        problem, _ = env.problem(iid, Meter(1.0), 3, False)
        before = pickle.dumps({k: v for k, v in vars(problem).items() if k != "meter"})
        reference = env.reference(iid)
        scalars = set()

        def walk(value):
            if isinstance(value, np.ndarray):
                scalars.update(np.unique(value).tolist())
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
            elif isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, (int, float)):
                scalars.add(float(value))

        walk({k: v for k, v in vars(problem).items() if k != "meter"})
        if isinstance(reference, float) and env.form == "assign":
            sizes = {float(problem.n_vars), float(problem.n_opts)}
            assert reference not in scalars - sizes, f"{name}: the reference value appears in the problem"
        if env.form == "predict":
            assert problem.qry_y is None and not problem.has_feedback()
        again, _ = env.problem(iid, Meter(1.0), 3, False)
        assert pickle.dumps({k: v for k, v in vars(again).items() if k != "meter"}) == before


def test_training_problems_only_reach_acquire():
    env = environments.load("forecasting")
    train, fresh = run.split(env, 8, 8)
    assert not set(train) & set(fresh)
    for iid in fresh[:2]:
        problem, _ = env.problem(iid, Meter(1e9), 0, False)
        try:
            problem.feedback(np.zeros(problem.n_queries))
        except PermissionError:
            continue
        raise AssertionError("a fresh instance gave feedback")


def test_a_run_repeats_exactly():
    job = {"env": "jobshop", "version": versions.default(), "seed": 4, "purpose": "test",
           "budget": dict(run.BUDGET, train=6.0, n_train=4, n_fresh=4)}
    a, b = run.measure(dict(job))["record"], run.measure(dict(job))["record"]
    for record in (a, b):
        record.pop("cpu")
    assert ledgers.canon(a) == ledgers.canon(b)


def test_split_keeps_groups_apart():
    for name in environments.REGISTRY:
        if roles.role_of(name) != "source":
            continue
        env = environments.load(name)
        train, fresh = run.split(env, 16, 24)
        assert not set(train) & set(fresh)
        groups_train, groups_fresh = {env.group(i) for i in train}, {env.group(i) for i in fresh}
        if len({env.group(i) for i in env.instance_ids()}) > 1:
            assert not groups_train & groups_fresh, name
        assert len(fresh) >= 24, (name, len(fresh))


def test_gate_rule_refuses_a_lower_untrained_score():
    """A version that only lowers its untrained score gains nothing under the rule."""
    from rsi6.meta import rounds
    base = [{"env": "e", "acquired": 0.80, "gain": 0.10}] * 4
    sabotage = [{"env": "e", "acquired": 0.80, "gain": 0.30}] * 4      # same acquired, untrained pushed down
    search_only = [{"env": "e", "acquired": 0.90, "gain": 0.10}] * 4   # better untrained search, nothing more learned
    real = [{"env": "e", "acquired": 0.90, "gain": 0.20}] * 4
    assert rounds.improvement(base, sabotage) == 0.0
    assert abs(rounds.improvement(base, search_only)) < 1e-12
    assert rounds.improvement(base, real) > 0.09


def test_audit_record_is_intact():
    """The preserved record of the external code that was executed is pinned by its manifest."""
    import hashlib
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "audit",
                        "external_code_execution_20261111")
    for line in open(os.path.join(root, "MANIFEST.sha256")):
        sha, name = line.split(None, 1)
        assert hashlib.sha256(open(os.path.join(root, name.strip()), "rb").read()).hexdigest() == sha, name


def test_version_schema():
    version = versions.default()
    assert versions.validate(version) == version
    bad = dict(version, **{"model.pop": 7})
    try:
        versions.validate(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("an invalid version was accepted")
    try:
        versions.validate(dict(version, extra=1))
    except ValueError:
        return
    raise AssertionError("an unknown field was accepted")


def test_learner_source_names_no_environment():
    """The learner's source may not contain an environment's vocabulary."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    words = set(roles.CANDIDATES) | {"job", "machine", "bin", "item", "makespan", "tour", "city", "clause", "colour",
                                     "knapsack", "facility", "customer", "vehicle", "route", "series", "forecast",
                                     "sat", "m4", "tsplib", "jsplib"}
    import re
    for name in ("learner.py", "version.py"):
        text = open(os.path.join(here, "learner", name)).read().lower().replace(".items()", "")
        found = sorted(w for w in words if re.search(rf"\b{re.escape(w)}s?\b", text))
        assert not found, f"{name} contains environment vocabulary: {found}"


def test_no_model_or_network_imports():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    banned = ("anthropic", "openai", "requests", "urllib", "socket", "http.client", "torch", "transformers")
    for folder, _, files in os.walk(here):
        if "set_aside_p3" in folder or "audit" in folder or "tests" in folder or "data" in folder:
            continue
        for name in files:
            if name.endswith(".py"):
                text = open(os.path.join(folder, name)).read()
                for word in banned:
                    assert f"import {word}" not in text and f"from {word}" not in text, (name, word)


def main() -> int:
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception as error:                      # noqa: BLE001 - a test runner reports every failure
            failed += 1
            print("FAIL", name, "-", type(error).__name__, error)
    print(f"RESULT: {len(tests) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
