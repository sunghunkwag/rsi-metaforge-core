"""The frozen kernel: executor isolation, vault, ledger, certificates, snapshots, crossings, replay."""
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from swarm.kernel import checker_lang
from swarm.kernel.executor import Executor
from swarm.kernel.ledger import Ledger
from swarm.kernel.replay import replay
from swarm.kernel.vault import SealedError, Vault
from swarm.tests.helpers import MAP_PLUS_ONE, SORT, Kernel, distinct_inputs, equality_checker, triple


class ExecutorTests(unittest.TestCase):
    def test_runs_in_a_child_and_charges_the_meter(self):
        kernel_meter = __import__("swarm.kernel.budget", fromlist=["Meter"]).Meter()
        executor = Executor(meter=kernel_meter)
        out = executor.run_batch(SORT, [[[3, 1]], [[2]]])
        self.assertEqual([o["value"] for o in out], [[1, 3], [2]])
        self.assertGreater(kernel_meter.total("kernel")["steps"], 0)
        self.assertEqual(executor.check_batch(equality_checker(SORT), [([2, 1], [1, 2]), ([2, 1], [2, 1])]),
                         [True, False])

    def test_timeout_fails_the_batch(self):
        executor = Executor(timeout_s=0.5, step_budget=10 ** 9)
        slow = ["lambda", ["x"], ["fold", ["lambda", ["a", "b"], ["fold", "+", "a", ["range", 4000]]], 0, ["range", 4000]]]
        out = executor.run_batch(slow, [[1]])
        self.assertFalse(out[0]["ok"])
        self.assertEqual(out[0]["error"], "timeout_or_crash")
        self.assertEqual(executor.timeouts, 1)

    def test_memory_cap_stops_a_child(self):
        executor = Executor(memory_mb=256)
        with tempfile.TemporaryDirectory() as directory:
            module = Path(directory) / "boom.py"
            module.write_text(textwrap.dedent("""
                def boom(payload):
                    data = bytearray(900 * 1024 * 1024)
                    return {"ok": len(data)}
                def fine(payload):
                    return {"ok": payload["x"]}
                """), encoding="utf-8")
            self.assertIsNone(executor.isolated_call([directory], "boom", "boom", {}, 10.0))
            self.assertEqual(executor.isolated_call([directory], "boom", "fine", {"x": 3}, 10.0), {"ok": 3})


class VaultAndLedgerTests(unittest.TestCase):
    def test_vault_is_write_once(self):
        vault = Vault()
        digests = vault.seal("t1", SORT, equality_checker(SORT), [{"inputs": [[1]], "output": [1]}])
        self.assertEqual(set(digests), {"witness_sha", "checker_sha", "hidden_sha", "hidden_count"})
        with self.assertRaises(SealedError):
            vault.seal("t1", SORT, equality_checker(SORT), [{"inputs": [[2]], "output": [2]}])
        with self.assertRaises(SealedError):
            vault.seal("t2", SORT, equality_checker(SORT), [])
        self.assertEqual(Vault.load(vault.dump()).sealed_witness("t1"), SORT)

    def test_ledger_chain_detects_tampering(self):
        ledger = Ledger()
        ledger.append("a", {"x": 1})
        ledger.append("b", {"y": [1, 2]})
        self.assertTrue(ledger.verify())
        ledger.entries[0]["payload"]["x"] = 2
        self.assertFalse(ledger.verify())
        ledger.entries[0]["payload"]["x"] = 1
        ledger.entries.pop()
        self.assertTrue(ledger.verify())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger.append("c", {})
            ledger.write(path)
            self.assertEqual(Ledger.load(path).head, ledger.head)


class CertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.kernel = Kernel(Path(cls.directory.name), b_inst=100)
        cls.sha0 = cls.kernel.snapshot()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def admit(self, lineage, witness, checker, seed, generation=1, sha=None):
        inputs = distinct_inputs(seed, 14)
        return self.kernel.admission.admit(triple(lineage, witness, checker, inputs), generation,
                                           sha or self.sha0)

    def test_certificates_in_order(self):
        # K0: duplicate inputs.
        bad = triple("mutate", SORT, equality_checker(SORT), [[1, 2]] * 14)
        self.assertEqual(self.kernel.admission.admit(bad, 1, self.sha0)["certificate"], "K0")
        # Kd: a checker that crashes on short inputs.
        crashing = ["lambda", ["x", "y"], ["=", "y", ["head", ["tail", ["tail", ["tail", ["tail", ["tail", "x"]]]]]]]]
        self.assertEqual(self.admit("mutate", SORT, crashing, 2)["certificate"], "Kd")
        # Ka: the checker never accepts the witness.
        self.assertEqual(self.admit("mutate", SORT, equality_checker(MAP_PLUS_ONE), 3)["certificate"], "Ka")
        # Kb: generation 0 solves map (+1) at B_inst.
        self.assertEqual(self.admit("mutate", MAP_PLUS_ONE, equality_checker(MAP_PLUS_ONE), 4)["certificate"], "Kb")
        # Admitted: sort is beyond generation 0.
        admitted = self.admit("mutate", SORT, equality_checker(SORT), 5)
        self.assertTrue(admitted["admitted"])
        self.assertLess(admitted["kb_margin"], 1.0)
        # Kc: the same behaviour again.
        self.assertEqual(self.admit("mutate", SORT, equality_checker(SORT), 6)["certificate"], "Kc")
        kinds = [e["kind"] for e in self.kernel.ledger.entries]
        self.assertEqual(kinds.count("admission"), 1)
        self.assertGreaterEqual(kinds.count("rejection"), 5)
        self.assertTrue(self.kernel.vault.has(admitted["id"]))

    def test_kb_uses_the_snapshot_not_the_live_tree(self):
        """A sandbagging live tree cannot make an easy task look hard."""
        params = self.kernel.tree / "params.json"
        original = params.read_text(encoding="utf-8")
        settings = json.loads(original)
        settings["search"]["max_size"] = 1          # the live tree now solves nothing
        params.write_text(json.dumps(settings), encoding="utf-8")
        try:
            rejected = self.admit("mutate", MAP_PLUS_ONE, equality_checker(MAP_PLUS_ONE), 7, sha=self.sha0)
            self.assertEqual(rejected["certificate"], "Kb")
            sandbagged = self.kernel.snapshot()
            self.assertNotEqual(sandbagged, self.sha0)
            admitted = self.admit("mutate", MAP_PLUS_ONE, equality_checker(MAP_PLUS_ONE), 8, sha=sandbagged)
            self.assertTrue(admitted["admitted"], "the certificate is computed on the snapshot given")
        finally:
            params.write_text(original, encoding="utf-8")


class CrossingTests(unittest.TestCase):
    def test_crossing_requires_other_sourced_substrate_and_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=100)
            sha0 = kernel.snapshot()
            admitted = kernel.admission.admit(triple("mutate", SORT, equality_checker(SORT),
                                                     distinct_inputs(5, 14)), 1, sha0)
            task_id = admitted["id"]
            self.assertEqual(kernel.crossings.check([task_id], sha0, 2), [])
            # A forged sort sourced from the task itself is an own-solution fragment.
            kernel.forge("f_sort", "list[int] -> list[int]", SORT, [task_id])
            own = kernel.snapshot()
            self.assertEqual(kernel.crossings.check([task_id], own, 3), [])
            self.assertEqual(kernel.archive.tasks[task_id]["status"], "open")
            # The exclusion acts inside the fresh solve: with its own-sourced
            # primitive removed, the snapshot finds nothing for this task.
            results = kernel.snapshots.solve(own, [{"id": task_id, "examples": kernel.archive.tasks[task_id]["examples"]}],
                                             100, exclude={task_id: [task_id]})
            self.assertIsNone(results[0]["program"])
            self.assertIsNotNone(kernel.snapshots.solve(own, [{"id": task_id, "examples": kernel.archive.tasks[task_id]["examples"]}],
                                                        100)[0]["program"])
            # The same primitive sourced from another task crosses.
            kernel.forge("f_sort", "list[int] -> list[int]", SORT, ["t9999"])
            other = kernel.snapshot()
            self.assertEqual(kernel.crossings.check([task_id], other, 4), [task_id])
            crossing = kernel.archive.tasks[task_id]["crossing"]
            self.assertEqual(crossing["sources"], {"f_sort": ["t9999"]})
            self.assertEqual(crossing["generations_to_crossing"], 3)
            # Mined solve gate: a wake solution is judged on hidden instances only.
            self.assertFalse(kernel.crossings.mined(task_id, SORT, 4))   # already crossed: no-op
            # Replay reproduces every certificate and the crossing.
            kernel.ledger.append("generation", {"generation": 4, "crossings_cumulative": 1})
            kernel.ledger.write(Path(directory) / "ledger.jsonl")
            (Path(directory) / "vault.json").write_text(json.dumps(kernel.vault.dump()))
            (Path(directory) / "archive.json").write_text(json.dumps(kernel.archive.dump(), default=str))
            (Path(directory) / "run_config.json").write_text(json.dumps({"B_inst": 100, "probe_set_seed": 11}))
            report = replay(Path(directory), full=True)
            self.assertTrue(report["chain_ok"])
            self.assertEqual(report["disagreements"], [])
            self.assertEqual(report["crossings"], 1)


if __name__ == "__main__":
    unittest.main()
