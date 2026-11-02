"""Regression tests for the adversarial review before registration (P5): own-solution exclusion of
learned weights, transitive exclusion, kernel failures as non-verdicts, the judge's gain on open tasks,
replay's artifact digests, the executor's guard, forge accounting, the child hash seed, the crossing
check's memo, and the Builder's handling of gate outcomes."""
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from swarm import latent
from swarm.breaker.agent import Breaker
from swarm.builder import self_edit
from swarm.builder.agent import Builder
from swarm.builder.mutable import solve as solve_module
from swarm.builder.mutable.terms import Term, term_to_dict
from swarm.builder.mutable.types import INT, ListOf
from swarm.kernel.executor import ROOT, Executor
from swarm.kernel.replay import replay
from swarm.tests.helpers import MAP_PLUS_ONE, SORT, Kernel, distinct_inputs, equality_checker, triple

LEN_PLUS_ONE = ["lambda", ["x"], ["+", ["len", "x"], 1]]
D = 1024


def public(kernel, task_id):
    return {"id": task_id, "examples": kernel.archive.tasks[task_id]["examples"]}


def write_artifacts(kernel, directory: Path):
    kernel.ledger.write(directory / "ledger.jsonl")
    (directory / "vault.json").write_text(json.dumps(kernel.vault.dump()))
    (directory / "archive.json").write_text(json.dumps(kernel.archive.dump(), default=str))
    (directory / "run_config.json").write_text(json.dumps({"B_inst": kernel.runtime.b_inst, "probe_set_seed": 11}))


class OwnSolutionExclusionTests(unittest.TestCase):
    def test_weights_learned_from_the_tasks_own_solution_are_excluded(self):
        """The blocker of the review: learning from T's own mined solution must not cross T."""
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=200)
            sha0 = kernel.snapshot()
            admitted = kernel.admission.admit(triple("mutate", LEN_PLUS_ONE, equality_checker(LEN_PLUS_ONE),
                                                     distinct_inputs(21, 14)), 1, sha0)
            self.assertTrue(admitted["admitted"], admitted)
            task_id = admitted["id"]
            wake = kernel.solver("solve_many", {"tasks": [public(kernel, task_id)], "budget": 1600})
            found = wake["results"][0]
            self.assertIsNotNone(found["program"], "the wake finds len+1 within 1600 candidates")
            self.assertGreater(found["candidates"], 200)
            learned = kernel.solver("learn", {"solutions": {task_id: found["term"]}, "generation": 1})
            self.assertEqual(learned["corpus"], 1)
            sha1 = kernel.snapshot()
            self.assertNotEqual(sha1, sha0, "the fit on the corpus changed the tree")
            # Without exclusion the refit weights make the task cheap; with the
            # task excluded the grammar is the one fit without its solution.
            plain = kernel.snapshots.solve(sha1, [public(kernel, task_id)], 200)[0]
            self.assertIsNotNone(plain["program"], "the own-fitted weights find the solution within B_inst")
            excluded = kernel.snapshots.solve(sha1, [public(kernel, task_id)], 200, exclude={task_id: [task_id]})[0]
            self.assertIsNone(excluded["program"], "excluded, the solve behaves as before the learning")
            self.assertEqual(kernel.crossings.check([task_id], sha1, 2), [])
            self.assertEqual(kernel.archive.tasks[task_id]["status"], "open")

    def test_exclusion_closes_over_entries_that_reference_excluded_ones(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=50)
            sha0 = kernel.snapshot()
            admitted = kernel.admission.admit(triple("mutate", SORT, equality_checker(SORT),
                                                     distinct_inputs(5, 14)), 1, sha0)
            task_id = admitted["id"]
            tail = Term("lam", ListOf(INT), (Term("app", None, (Term("prim", "tail"), Term("var", 0))),))
            twice = Term("lam", ListOf(INT), (Term("app", None, (Term("ref", "A"),
                                                                  Term("app", None, (Term("ref", "A"), Term("var", 0))))),))
            library = {"entries": {"A": {"term": term_to_dict(tail), "sources": [task_id]},
                                   "B": {"term": term_to_dict(twice), "sources": ["t9999"]}},
                       "weights": {}, "context_weights": [], "fit_solutions": {}}
            (kernel.tree / "library.json").write_text(json.dumps(library), encoding="utf-8")
            sha1 = kernel.snapshot()
            inventory = kernel.snapshots.inventory(sha1)
            self.assertEqual(inventory["library"]["B"]["references"], ["A"])
            results = kernel.snapshots.solve(sha1, [public(kernel, task_id)], 50, exclude={task_id: [task_id]})
            self.assertIsNotNone(results, "a dependent entry no longer crashes the excluded solve")
            self.assertNotIn("grammar failed", results[0].get("reason") or "")
            self.assertEqual(kernel.crossings.check([task_id], sha1, 2), [])


class BoostTests(unittest.TestCase):
    def test_boosts_reach_fitted_and_contextual_weight_keys(self):
        fitted = {"entries": {}, "sources": {}, "fit_solutions": {},
                  "weights": {"add/2": 3.0, "add": 2.0, "sub/2": 1.0},
                  "context_weights": {("ROOT", 0): {"add/2": 5.0, "sub/2": 1.0}}}
        grammar = solve_module.grammar_for(fitted, set(), {"add": 4.0})
        self.assertEqual((grammar.weights["add/2"], grammar.weights["add"], grammar.weights["sub/2"]), (12.0, 8.0, 1.0))
        self.assertEqual(grammar.context_weights[("ROOT", 0)]["add/2"], 20.0)
        plain = solve_module.grammar_for({"entries": {}, "sources": {}, "fit_solutions": {},
                                          "weights": {}, "context_weights": {}}, set(), {"add": 4.0})
        self.assertEqual(plain.weights["add"], 4.0)


class KernelFailureTests(unittest.TestCase):
    def test_executor_failure_during_kb_is_not_a_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=100)
            sha0 = kernel.snapshot()
            original = kernel.executor.accepts
            kernel.executor.accepts = lambda *args, **kwargs: (False, True)
            try:
                decision = kernel.admission.admit(triple("mutate", MAP_PLUS_ONE, equality_checker(MAP_PLUS_ONE),
                                                         distinct_inputs(3, 14)), 1, sha0)
            finally:
                kernel.executor.accepts = original
            self.assertFalse(decision["admitted"])
            self.assertEqual(decision["certificate"], "K!")
            self.assertTrue(decision["kernel_failed"])
            kinds = [e["kind"] for e in kernel.ledger.entries]
            self.assertIn("kernel_failed", kinds)
            self.assertNotIn("rejection", kinds)
            self.assertNotIn("admission", kinds)
            # The Breaker treats it as neither validated nor wasted.
            breaker = Breaker(latent.Field(d=D).port("breaker"), kernel.runner, seed=11, d=D)
            breaker.pending["k"] = ("mutate", MAP_PLUS_ONE)
            breaker.observe_admission(1, "k", decision, [])
            self.assertEqual(sum(breaker.wasted.values()), 0)
            self.assertEqual(sum(breaker.validated.values()), 0)
            # A genuine Kb rejection still counts as wasted.
            decision = kernel.admission.admit(triple("mutate", MAP_PLUS_ONE, equality_checker(MAP_PLUS_ONE),
                                                     distinct_inputs(4, 14)), 1, sha0)
            self.assertEqual(decision["certificate"], "Kb")
            breaker.pending["k2"] = ("mutate", MAP_PLUS_ONE)
            breaker.observe_admission(1, "k2", decision, [])
            self.assertEqual(sum(breaker.wasted.values()), 1)

    def test_crossing_check_skips_same_generation_tasks_and_memoizes_verdicts(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=100)
            sha0 = kernel.snapshot()
            task_id = kernel.admission.admit(triple("mutate", SORT, equality_checker(SORT),
                                                    distinct_inputs(5, 14)), 1, sha0)["id"]
            spent = lambda: kernel.meter.total("kernel")["evaluations"]
            before = spent()
            self.assertEqual(kernel.crossings.check([task_id], sha0, 1), [])
            self.assertEqual(spent(), before, "Kb ran on this snapshot this generation: no second solve")
            self.assertEqual(kernel.crossings.check([task_id], sha0, 2), [])
            after_first = spent()
            self.assertGreater(after_first, before)
            self.assertEqual(kernel.crossings.check([task_id], sha0, 3), [])
            self.assertEqual(spent(), after_first, "an unchanged snapshot is not judged twice")


class JudgeTests(unittest.TestCase):
    def test_gain_counts_open_tasks_only_and_failures_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            kernel = Kernel(run_dir, b_inst=100)
            sha0 = kernel.snapshot()
            sort_task = kernel.admission.admit(triple("mutate", SORT, equality_checker(SORT),
                                                      distinct_inputs(5, 14)), 1, sha0)["id"]
            # Cross the sort task through a primitive sourced elsewhere, then take it away again.
            kernel.forge("f_sort", "list[int] -> list[int]", SORT, ["t9999"])
            self.assertEqual(kernel.crossings.check([sort_task], kernel.snapshot(), 2), [sort_task])
            forged = kernel.tree / "forged.json"
            forged.write_text("{}", encoding="utf-8")
            incumbent = kernel.snapshot()
            patch = {"kind": "forge", "name": "f_sort", "type": "list[int] -> list[int]", "body": SORT,
                     "sources": ["t9999"]}
            candidate = self_edit.make_candidate(kernel.live, run_dir / "candidates", 0, patch)
            decision = kernel.judge.judge(candidate / "mutable", incumbent, 3, run_dir, patch)
            self.assertEqual((decision["incumbent_solved"], decision["candidate_solved"]), (0, 1))
            self.assertEqual((decision["incumbent_open_solved"], decision["candidate_open_solved"]), (0, 0))
            self.assertFalse(decision["adopted"], "re-solving a crossed task is not a gain")
            self.assertEqual(decision["reason"], "no strict gain")
            # An executor failure while the incumbent is evaluated refuses the candidate and caches nothing.
            original = kernel.snapshots.solve_excluded
            kernel.snapshots.solve_excluded = lambda *args, **kwargs: None
            kernel.judge._cache.clear()
            try:
                failed = kernel.judge.judge(candidate / "mutable", incumbent, 4, run_dir, patch)
            finally:
                kernel.snapshots.solve_excluded = original
            self.assertFalse(failed["adopted"])
            self.assertTrue(failed["reason"].startswith("incumbent evaluation failed"))
            self.assertFalse(any(key[0] == incumbent and "failed" in str(value)
                                 for key, value in kernel.judge._cache.items()))


class ReplayTests(unittest.TestCase):
    def test_replay_detects_tampered_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            kernel = Kernel(run_dir, b_inst=100)
            sha0 = kernel.snapshot()
            task_id = kernel.admission.admit(triple("mutate", SORT, equality_checker(SORT),
                                                    distinct_inputs(5, 14)), 1, sha0)["id"]
            kernel.forge("f_sort", "list[int] -> list[int]", SORT, ["t9999"])
            self.assertEqual(kernel.crossings.check([task_id], kernel.snapshot(), 2), [task_id])
            kernel.ledger.append("generation", {"generation": 2, "crossings_cumulative": 1})
            write_artifacts(kernel, run_dir)
            self.assertEqual(replay(run_dir)["disagreements"], [])
            vault = json.loads((run_dir / "vault.json").read_text())
            vault[task_id]["checker"] = ["lambda", ["x", "y"], True]
            (run_dir / "vault.json").write_text(json.dumps(vault))
            report = replay(run_dir)
            self.assertIn({"id": task_id, "artifact": "checker_sha"}, report["disagreements"])
            write_artifacts(kernel, run_dir)
            archive = json.loads((run_dir / "archive.json").read_text())
            archive["tasks"][task_id]["examples"][0]["output"] = [99]
            archive["tasks"][task_id]["crossing"]["program"] = ["lambda", ["x"], "x"]
            (run_dir / "archive.json").write_text(json.dumps(archive))
            report = replay(run_dir)
            self.assertIn({"id": task_id, "artifact": "examples_key"}, report["disagreements"])
            self.assertIn({"id": task_id, "archive": "crossing record"}, report["disagreements"])


class GuardTests(unittest.TestCase):
    def test_child_cannot_read_the_run_directory_or_import_agents(self):
        executor = Executor()
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            (run_dir / "vault.json").write_text("{}")
            tree = run_dir / "live"
            tree.mkdir()
            (tree / "probe.py").write_text(textwrap.dedent("""
                import importlib, os
                def attempt(payload):
                    out = {}
                    try:
                        open(payload["vault"]).read(); out["read"] = "allowed"
                    except Exception as exc:
                        out["read"] = str(exc)[:60]
                    try:
                        importlib.import_module("swarm.breaker"); out["import"] = "allowed"
                    except Exception as exc:
                        out["import"] = str(exc)[:60]
                    try:
                        open(payload["outside"], "w").write("x"); out["write"] = "allowed"
                    except Exception as exc:
                        out["write"] = str(exc)[:60]
                    try:
                        os.listdir(payload["run_dir"]); out["list"] = "allowed"
                    except Exception as exc:
                        out["list"] = str(exc)[:60]
                    try:
                        import subprocess; out["subprocess"] = "allowed"
                    except Exception as exc:
                        out["subprocess"] = str(exc)[:60]
                    open(os.path.join(os.path.dirname(__file__), "inside.txt"), "w").write("ok")
                    out["inside"] = "allowed"
                    return out
                """), encoding="utf-8")
            out = executor.isolated_call([tree, ROOT], "probe", "attempt",
                                         {"vault": str(run_dir / "vault.json"), "outside": str(run_dir / "evil.txt"),
                                          "run_dir": str(run_dir)}, 30.0)
            self.assertIsNotNone(out, executor.last_error)
            for key in ("read", "import", "write", "list", "subprocess"):
                self.assertTrue(out[key].startswith("guard:"), (key, out[key]))
            self.assertEqual(out["inside"], "allowed")
            self.assertTrue((tree / "inside.txt").exists())
            self.assertFalse((run_dir / "evil.txt").exists())

    def test_child_hash_seed_is_fixed(self):
        executor = Executor()
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            (tree / "probe.py").write_text("def h(payload):\n    return {'h': hash('swarm-seed'), 'order': sorted({'b', 'a', 'c'})}\n",
                                           encoding="utf-8")
            first = executor.isolated_call([tree], "probe", "h", {}, 30.0)
            second = executor.isolated_call([tree], "probe", "h", {}, 30.0)
            self.assertEqual(first, second)


class AccountingTests(unittest.TestCase):
    def test_forge_checks_are_builder_candidate_evaluations(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=100)
            before = kernel.meter.total("builder")["evaluations"]
            outputs = kernel.batch_runner([SORT, MAP_PLUS_ONE], [[3, 1], [2]])
            self.assertEqual(outputs, [[[1, 3], [2]], [[4, 2], [3]]])
            self.assertEqual(kernel.meter.total("builder")["evaluations"] - before, 2)

    def test_timed_out_batch_charges_no_steps(self):
        from swarm.kernel.budget import Meter
        meter = Meter()
        executor = Executor(timeout_s=0.5, step_budget=10 ** 9, meter=meter)
        slow = ["lambda", ["x"], ["fold", ["lambda", ["a", "b"], ["fold", "+", "a", ["range", 4000]]], 0, ["range", 4000]]]
        executor.run_batch(slow, [[1]])
        self.assertEqual(meter.total("kernel")["steps"], 0)


class BuilderGateTests(unittest.TestCase):
    def test_gate_outcomes_resubmit_or_skip(self):
        captured = {}

        def solver(function, payload):
            if function == "inventory":
                return {"library": {}, "forged": {}, "params": {"allocation": {"strategy": "even"}}}
            captured.update(payload)
            return {"results": [], "meter": {"candidates": 0}}

        builder = Builder(latent.Field(d=D).port("builder"), solver, lambda p, i: [None] * len(p),
                          Path("/nonexistent/mutable"), seed=11, d=D)
        solution = {"program": SORT, "term": {"tag": "prim", "value": "sort"}, "dsl": "sort", "fragments": []}
        builder.wake_solutions = {"t0001": solution}
        builder.observe_mined("t0001", None)
        self.assertEqual(builder.pending, {"t0001": solution})
        task = {"id": "t0001", "examples": [{"inputs": [[2, 1]], "output": [1, 2]}], "status": "open"}
        wake = builder.attack(2, [task], 100)
        self.assertEqual(wake["solved"], {"t0001": solution}, "a failed check resubmits the solution")
        builder.observe_mined("t0001", False)
        self.assertEqual(builder.pending, {})
        self.assertEqual(builder.rejected, {"t0001": [solution["term"]]})
        builder.attack(3, [task], 100)
        self.assertEqual(captured["skip"], {"t0001": [solution["term"]]})


if __name__ == "__main__":
    unittest.main()
