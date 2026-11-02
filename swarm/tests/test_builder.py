"""The Builder: self-edits judged by the kernel on the archive, scope and isolation guards, forge, wake (P3 gate)."""
import json
import tempfile
import unittest
from pathlib import Path

from swarm import latent
from swarm.builder import self_edit
from swarm.builder.agent import Builder
from swarm.builder.forge import forge, output_kind
from swarm.tests.helpers import SORT, Kernel, distinct_inputs, equality_checker, triple

D = 1024
REVERSE = ["lambda", ["x"], ["reverse", "x"]]
TAKE2 = ["lambda", ["x"], ["take", 2, "x"]]


def admit(kernel, witness, seed, generation=1, sha=None):
    inputs = distinct_inputs(seed, 14)
    return kernel.admission.admit(triple("mutate", witness, equality_checker(witness), inputs),
                                  generation, sha or kernel.snapshot())


class SelfEditJudgeTests(unittest.TestCase):
    def test_improving_edit_adopted_regressing_edit_discarded(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            kernel = Kernel(run_dir, b_inst=100)
            sha0 = kernel.snapshot()
            sort_task = admit(kernel, SORT, 5, sha=sha0)
            reverse_task = admit(kernel, REVERSE, 6, sha=sha0)
            self.assertTrue(sort_task["admitted"] and reverse_task["admitted"])
            candidates = run_dir / "candidates"
            # Improving: a sort primitive sourced from another task crosses the sort task.
            patch = {"kind": "forge", "name": "f_sort", "type": "list[int] -> list[int]", "body": SORT,
                     "sources": ["t9999"]}
            candidate = self_edit.make_candidate(kernel.live, candidates, 0, patch)
            self.assertEqual(self_edit.guard(candidate, kernel.live), [])
            decision = kernel.judge.judge(candidate / "mutable", sha0, 1, run_dir, patch)
            self.assertTrue(decision["adopted"], decision)
            self.assertEqual((decision["incumbent_solved"], decision["candidate_solved"]), (0, 1))
            self_edit.adopt(candidate, kernel.live)
            sha1 = kernel.snapshot()
            self.assertNotEqual(sha1, sha0)
            self.assertEqual(kernel.crossings.check([sort_task["id"]], sha1, 2), [sort_task["id"]])
            # Regressing: removing the primitive loses the crossed task.
            patch = {"kind": "unforge", "name": "f_sort"}
            candidate = self_edit.make_candidate(kernel.live, candidates, 1, patch)
            decision = kernel.judge.judge(candidate / "mutable", sha1, 2, run_dir, patch)
            self.assertFalse(decision["adopted"])
            self.assertEqual(decision["regressed"], [sort_task["id"]])
            # No strict gain: a parameter that changes nothing.
            patch = {"kind": "param", "path": ["allocation", "window"], "value": 32}
            candidate = self_edit.make_candidate(kernel.live, candidates, 2, patch)
            decision = kernel.judge.judge(candidate / "mutable", sha1, 2, run_dir, patch)
            self.assertFalse(decision["adopted"])
            self.assertEqual(decision["reason"], "no strict gain")
            # A primitive sourced from the very task it solves does not count (own-solution exclusion)...
            patch = {"kind": "forge", "name": "f_rev", "type": "list[int] -> list[int]", "body": REVERSE,
                     "sources": [reverse_task["id"]]}
            candidate = self_edit.make_candidate(kernel.live, candidates, 3, patch)
            decision = kernel.judge.judge(candidate / "mutable", sha1, 2, run_dir, patch)
            self.assertFalse(decision["adopted"])
            self.assertEqual(decision["candidate_solved"], decision["incumbent_solved"])
            # ...while the same primitive sourced elsewhere is adopted.
            patch = dict(patch, sources=["t9998"])
            candidate = self_edit.make_candidate(kernel.live, candidates, 4, patch)
            decision = kernel.judge.judge(candidate / "mutable", sha1, 2, run_dir, patch)
            self.assertTrue(decision["adopted"], decision)
            entries = kernel.ledger.of_kind("self_edit")
            self.assertEqual(len(entries), 5)
            self.assertEqual([e["payload"]["adopted"] for e in entries], [True, False, False, False, True])
            self.assertTrue(kernel.ledger.verify())

    def test_candidate_that_writes_outside_its_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            kernel = Kernel(run_dir, b_inst=50)
            sha0 = kernel.snapshot()
            admit(kernel, SORT, 5, sha=sha0)
            candidate = self_edit.copy_tree(kernel.tree, run_dir / "candidates" / "0" / "mutable")
            solve = candidate / "solve.py"
            solve.write_text(solve.read_text(encoding="utf-8")
                             + f"\nimport pathlib\npathlib.Path({str(run_dir / 'evil.txt')!r}).write_text('x')\n",
                             encoding="utf-8")
            self.assertTrue(self_edit.guard(candidate.parent, kernel.live), "the scope guard sees a code change")
            decision = kernel.judge.judge(candidate, sha0, 1, run_dir, {"kind": "planted"})
            self.assertFalse(decision["adopted"])
            # The executor's guard refuses the write inside the child (the
            # solver fails); the digest guard around the evaluation is the
            # second line and would report "wrote outside its tree".
            self.assertIn(decision["reason"], ("candidate evaluation failed: solver failed",
                                               "wrote outside its tree"))
            self.assertFalse((run_dir / "evil.txt").exists(), "the guard stopped the write")
            refused = kernel.judge.refuse(1, {"kind": "planted"}, "scope: solve.py: code changed")
            self.assertFalse(refused["adopted"])
            self.assertEqual(len(kernel.ledger.of_kind("self_edit")), 2)

    def test_patch_operators_stay_on_the_menu(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = self_edit.copy_tree(Kernel(Path(directory)).tree, Path(directory) / "copy" / "mutable")
            with self.assertRaises(ValueError):
                self_edit.apply_patch(tree, {"kind": "param", "path": ["search", "max_size"], "value": 1})
            with self.assertRaises(ValueError):
                self_edit.apply_patch(tree, {"kind": "rewrite", "file": "search.py"})
            self_edit.apply_patch(tree, {"kind": "param", "path": ["search", "max_size"], "value": 10})
            self.assertEqual(json.loads((tree / "params.json").read_text())["search"]["max_size"], 10)


class ForgeTests(unittest.TestCase):
    def test_forge_reproduces_public_examples_through_the_metered_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory))
            inputs = distinct_inputs(9, 8)
            sort_examples = [{"inputs": [x], "output": sorted(x)} for x in inputs]
            found = forge(sort_examples, kernel.batch_runner)
            self.assertEqual(found["body"], ["lambda", ["x"], ["sort", "x"]])
            self.assertEqual(found["type"], "list[int] -> list[int]")
            plus = [{"inputs": [x], "output": [v + 1 for v in sorted(x)]} for x in inputs]
            found = forge(plus, kernel.batch_runner)
            self.assertIsNotNone(found)
            self.assertEqual(kernel.batch_runner([found["body"]], inputs)[0], [e["output"] for e in plus])
            zeros = [{"inputs": [x], "output": x.count(0)} for x in inputs]
            self.assertEqual(output_kind(zeros), "int")
            found = forge(zeros, kernel.batch_runner, limit=600)
            self.assertIsNotNone(found)
            impossible = [{"inputs": [x], "output": i * 7919 % 13} for i, x in enumerate(inputs)]
            self.assertIsNone(forge(impossible, kernel.batch_runner, limit=300))
            self.assertGreater(kernel.meter.total("builder")["steps"], 0, "forge runs are charged to the Builder")
            self.assertEqual(kernel.meter.total("kernel")["steps"], 0)


class BuilderAgentTests(unittest.TestCase):
    def test_wake_mined_gate_learning_and_edit_proposals(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=100)
            sha0 = kernel.snapshot()
            sort_task = admit(kernel, SORT, 5, sha=sha0)["id"]
            take_task = admit(kernel, TAKE2, 7, sha=sha0)["id"]
            field = latent.Field(d=D)
            builder = Builder(field.port("builder"), kernel.solver, kernel.batch_runner, kernel.tree,
                              seed=11, d=D)
            view = kernel.archive.public_view()
            self.assertEqual(builder.read_state(view), {}, "nothing in the Breaker's region yet")
            wake = builder.attack(1, [t for t in view if t["status"] == "open"], total_budget=200)
            self.assertFalse(wake["failed"])
            self.assertEqual(wake["solved"], {})
            self.assertEqual(set(wake["residues"]), {sort_task, take_task})
            with_dsl = sum(1 for r in wake["residues"].values() if r["best_dsl"])
            self.assertEqual(builder.fragments, {}, "generation 0 holds no library entry and no forged primitive")
            self.assertEqual(builder.write_state(view), with_dsl, "one residue vector per near miss, no fragments yet")
            self.assertGreater(kernel.meter.total("builder")["evaluations"], 0)
            # A sort primitive appears in the live tree (as an adopted self-edit would leave it).
            kernel.forge("f_sort", "list[int] -> list[int]", SORT, ["t9999"])
            builder.inventory(refresh=True)
            self.assertIn("f_sort", builder.fragments)
            wake = builder.attack(2, [t for t in view if t["status"] == "open"], total_budget=200)
            self.assertIn(sort_task, wake["solved"])
            accepted = kernel.crossings.mined(sort_task, wake["solved"][sort_task]["program"], 2)
            self.assertTrue(accepted)
            builder.observe_mined(sort_task, accepted)
            self.assertIn(sort_task, builder.solutions)
            self.assertEqual(builder.learn(2, kernel.archive.public_view())["offered"], 1,
                             "the generation-0 rule learns from kernel-verified wake solutions")
            kernel.forge("f_sort", "list[int] -> list[int]", SORT, ["t9999"])
            self.assertEqual(kernel.crossings.check([sort_task], kernel.snapshot(), 3), [sort_task])
            learned = builder.learn(3, kernel.archive.public_view())
            self.assertEqual(learned["offered"], 1, "the crossing term and the mined solution are one task")
            patches = builder.propose_edits(3, kernel.archive.public_view(), k_edit=2)
            self.assertTrue(patches)
            self.assertLessEqual(len(patches), 2)
            self.assertEqual(patches[0]["kind"], "forge", "the top residue is forged first")
            self.assertEqual(patches[0]["sources"], [take_task])
            for patch in patches:
                candidate = self_edit.make_candidate(kernel.live, Path(directory) / "candidates", 0, patch)
                self.assertEqual(self_edit.guard(candidate, kernel.live), [])
            fresh = sum(1 for r in wake["residues"].values() if r["best_dsl"])
            self.assertEqual(builder.write_state(kernel.archive.public_view()), fresh + 2,
                             "the fresh residues, the solution once, and the fragment bundle")
            self.assertEqual(builder.write_state(kernel.archive.public_view()), fresh + 1,
                             "the solution is not rewritten")
            self.assertEqual(builder.summary()["forged"], 1)

    def test_records_arm_boosts_by_explicit_features_and_writes_no_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=100)
            sha0 = kernel.snapshot()
            sort_task = admit(kernel, SORT, 5, sha=sha0)["id"]
            kernel.forge("f_sort", "list[int] -> list[int]", SORT, ["t0100"])
            field = latent.Field(d=D)
            builder = Builder(field.port("builder"), kernel.solver, kernel.batch_runner, kernel.tree,
                              seed=11, d=D, records=True)
            # A task the Breaker's records do not carry yet is not boosted (the
            # same one-generation lag as the latent arms); once recorded, it is.
            builder.records_in = {"tasks": {"t0100": {"output_kind": "list[int]"}}}
            self.assertEqual(builder.read_state(kernel.archive.public_view()), {})
            builder.records_in = {"tasks": {"t0100": {"output_kind": "list[int]"},
                                            sort_task: {"output_kind": "list[int]"}}}
            boosts = builder.read_state(kernel.archive.public_view())
            self.assertEqual(boosts, {sort_task: {"f_sort": 4.0}})
            self.assertEqual(builder.write_state(kernel.archive.public_view()), 0)
            self.assertEqual(len(field.builder), 0)
            self.assertIn("fragments", builder.state_records())


if __name__ == "__main__":
    unittest.main()
