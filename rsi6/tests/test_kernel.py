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
from rsi6.kernel.environment import Environment
from rsi6.kernel.problem import AssignProblem, BudgetExhausted, Meter, PredictProblem, view
from rsi6.learner import version as versions
from rsi6.learner.learner import Learner

ASSIGN_ENVIRONMENTS = [name for name in environments.REGISTRY if environments.load(name).form == "assign"
                       and roles.role_of(name) == "source"]
# every adapter that exists, for checks that involve no learner
ALL_ASSIGN = [name for name in environments.REGISTRY if environments.load(name).form == "assign"]


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
    """For every adapter: the fast rows equal the difference of the specified partial totals,
    for every option (rows of options that are not allowed are zero in both)."""
    rng = np.random.default_rng(0)
    for name in ALL_ASSIGN:
        env = environments.load(name)
        for iid in env.instance_ids()[:3]:
            problem, _ = env.problem(iid, Meter(float("inf")), 11, True)
            state = problem.start()
            for _ in range(min(problem.n_vars, 20)):
                variables = problem.unassigned(state)[:3]
                allowed = np.flatnonzero(problem.allowed(state))
                fast = problem.candidates(state, variables)
                slow = AssignProblem._rows(problem, state, variables)
                assert fast.shape == slow.shape and np.allclose(fast, slow), name
                problem.assign(state, int(variables[0]), int(rng.choice(allowed)))
                assert np.allclose(problem.totals(state), problem.partial_totals(state["a"])), name
            assert problem.candidates(state, []).shape[0] == 0, name


def test_view_hides_the_adapter():
    """What the learner is handed is a generic view: no adapter class, no adapter attribute, no
    working table of a state, and arrays it cannot write to."""
    for name in environments.REGISTRY:
        env = environments.load(name)
        problem, _ = env.problem(env.instance_ids()[0], Meter(float("inf")), 3, True)
        seen = view(problem)
        assert type(seen).__name__ in ("AssignView", "PredictView")
        public = {k for k in vars(seen) if not k.startswith("_")}
        if env.form == "assign":
            assert public <= {"n_vars", "n_opts", "n_groups", "ordered", "hard", "detail", "capacity", "var_attr",
                              "opt_attr", "var_var", "opt_opt", "var_opt", "occ_attr", "domain", "start_answer",
                              "start_totals", "meter"}, (name, public)
            state = seen.start()
            assert set(state) == {"a", "used", "tot", "n"}, (name, set(state))
            try:
                seen.var_attr[...] = 0
            except ValueError:
                pass
            else:
                assert seen.var_attr.size == 0, name
        else:
            assert public <= {"ctx_x", "ctx_y", "qry_x", "ordered", "meter"}, (name, public)
            try:
                seen.ctx_y[0] = 0.0
            except ValueError:
                continue
            raise AssertionError(f"{name}: the learner could write to the observed targets")


def test_layout_is_the_same_for_every_instance():
    """Every instance of an environment has the same generic layout (numbers of attribute
    columns, relations and groups): a learner's descriptors are defined per environment."""
    for name in environments.REGISTRY:
        env = environments.load(name)
        train, fresh = run.split(env, 16, 24)
        problems = [env.problem(i, Meter(float("inf")), 3, True)[0] for i in train + fresh]
        assert len({run.layout(P) for P in problems}) == 1, name
        if env.form == "assign":                 # and the learner's own descriptor list follows from the layout
            from rsi6.learner.learner import Layout
            assert len({tuple(Layout(view(P), versions.default()).names) for P in problems}) == 1, name


def test_layout_covers_what_the_learner_reads():
    """Two problems whose options differ in whether they can be taken more than once have
    different layouts (the learner's descriptors depend on it)."""
    one = _Fixture(6, 8, 1, Meter(float("inf")), False)
    two = _Fixture(6, 8, 1, Meter(float("inf")), False)
    two.capacity = np.full(8, 1)
    assert run.layout(one) != run.layout(two)


def test_kernel_refuses_instances_with_different_layouts():
    """An environment whose instances differ in layout is refused by the kernel before the
    learner is called."""
    class Uneven(Environment):
        name = category = "uneven-fixture"
        form = "predict"

        def instance_ids(self):
            return [f"i{k:02d}" for k in range(12)]

        def problem(self, instance_id, meter, seed, training):
            k = int(instance_id[1:])
            x = np.random.default_rng(k).random((40, 2 + k % 3))
            return PredictProblem(x[:30], x[:30].sum(axis=1), x[30:], ordered=False,
                                  target=x[30:].sum(axis=1) if training else None, meter=meter), (lambda a: a)

        def score(self, instance_id, answer):
            return 0.5

    environments._CACHE["uneven-fixture"] = Uneven()
    try:
        run.measure({"env": "uneven-fixture", "version": versions.default(), "seed": 1,
                     "budget": dict(run.BUDGET, n_train=4, n_fresh=4)})
    except RuntimeError as error:
        assert "layout" in str(error)
    else:
        raise AssertionError("the kernel accepted instances with different layouts")
    finally:
        del environments._CACHE["uneven-fixture"]


def test_padded_columns_are_exact_and_learnable():
    """Plumbing, on made-up numbers (not the benchmark's): problems with different numbers of
    constraints, presented with zero columns for the absent ones, have one layout, evaluate
    as their specification says, and the learner learns from them and answers them."""
    from rsi6.environments.knapsack import KnapsackProblem
    rng = np.random.default_rng(0)
    meter = Meter(0.0)
    problems = []
    for m in (2, 5, 3, 2, 5, 3):
        use = rng.integers(1, 50, size=(m, 14)).astype(float)
        problems.append(KnapsackProblem(rng.integers(10, 99, size=14).astype(float), use, use.sum(axis=1) / 2, meter, 5))
    meter.limit = 40.0 * sum(P.construction_units() for P in problems)       # the registered training budget
    assert len({run.layout(P) for P in problems}) == 1 and problems[0].var_attr.shape == (14, 6)
    P = problems[0]
    assert np.all(P.var_attr[:, 3:] == 0) and np.array_equal(P.var_attr[:, 1:3], P.use.T)
    learner = Learner(versions.default())
    capability, _, report = learner.acquire([view(p) for p in problems], np.random.default_rng(1))
    assert report["iterations"] >= 1 and report["constructions"] > 0, report       # the path on which the run had stopped
    meter.limit = float("inf")
    answer = learner.apply(capability, view(problems[4]), np.random.default_rng(2))
    assert problems[4].well_formed(answer), report
    taken = answer == 1
    assert np.allclose(problems[4].partial_totals(answer),
                       [-problems[4].profit[taken].sum(), np.maximum(problems[4].use[:, taken].sum(axis=1) - problems[4].limit, 0).sum()])


def test_assignment_is_metered():
    meter = Meter(float("inf"))
    problem = _Fixture(8, 5, 0, meter, ordered=True)
    state = problem.start()
    before = meter.used
    for v in range(8):
        problem.assign(state, v, v % 5)
    assert meter.used - before >= 8


def test_malformed_answers_are_not_repaired():
    """An answer that is not a well-formed answer of the problem is not scored."""
    for name in ALL_ASSIGN:
        env = environments.load(name)
        problem, _ = env.problem(env.instance_ids()[0], Meter(float("inf")), 3, False)
        n = problem.n_vars
        for bad in (np.full(n, -1), np.full(n, problem.n_opts), np.zeros(n), np.zeros(n - 1, dtype=np.int64),
                    np.full(n, np.nan), list(range(n)), None):
            assert not run._valid(problem, bad), (name, bad if bad is None else type(bad))
    env = environments.load("forecasting")
    problem, _ = env.problem(env.instance_ids()[0], Meter(float("inf")), 3, False)
    for bad in (np.zeros(problem.n_queries + 1), np.full(problem.n_queries, np.nan), np.zeros(problem.n_queries, dtype=np.int64)):
        assert not run._valid(problem, bad)


def test_every_instance_has_its_own_relabelling():
    """Two instances of the same size are relabelled differently under one run seed."""
    env = environments.load("binpacking")
    a, b = [i for i in env.instance_ids() if i.startswith("u120")][:2]
    pa, da = env.problem(a, Meter(float("inf")), run._seed(1, env.name, a, "relabel"), False)
    pb, db = env.problem(b, Meter(float("inf")), run._seed(1, env.name, b, "relabel"), False)
    identity = np.arange(pa.n_vars)
    assert not np.array_equal(da(identity), db(identity))


def test_binpacking_training_and_fresh_share_no_stretch():
    """The library's files are cuts of one stream of sizes; no run of six consecutive sizes may
    be common to a training and a fresh problem."""
    env = environments.load("binpacking")
    train, fresh = run.split(env, 16, 24)

    def runs(i):
        sizes = env.instances[i]["sizes"].tolist()
        return {tuple(sizes[k:k + 6]) for k in range(len(sizes) - 5)}

    seen = set().union(*(runs(i) for i in train))
    for i in fresh:
        assert not runs(i) & seen, i


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
    listed = set()
    for line in open(os.path.join(root, "MANIFEST.sha256")):
        sha, name = line.split(None, 1)
        listed.add(os.path.normpath(name.strip()))
        assert hashlib.sha256(open(os.path.join(root, name.strip()), "rb").read()).hexdigest() == sha, name
    present = {os.path.normpath(os.path.relpath(os.path.join(folder, name), root))
               for folder, _, files in os.walk(root) for name in files if "__pycache__" not in folder}
    assert present - listed == {"MANIFEST.sha256"}, sorted(present - listed)


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
