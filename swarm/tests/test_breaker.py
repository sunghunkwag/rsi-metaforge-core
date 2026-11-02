"""The Breaker: a pilot generation under the kernel's certificates, regret accounting, lineages (P2 gate)."""
import tempfile
import unittest
from pathlib import Path

from swarm import latent
from swarm.breaker import programs
from swarm.breaker.agent import LINEAGES, Breaker
from swarm.kernel.admit import CERTIFICATES
from swarm.tests.helpers import Kernel

D = 1024


def view_entry(task_id, status="open", crossing_program=None, examples=None):
    return {"id": task_id, "lineage": "mutate", "input_kind": "list[int]", "status": status,
            "examples": examples or [{"inputs": [[1, 2]], "output": [2, 1]}, {"inputs": [[3]], "output": [3]}],
            "admitted_generation": 1, "crossed_generation": None if status != "crossed" else 2,
            "crossing_program": crossing_program, "crossing_term": None, "mined": False}


class PilotGenerationTests(unittest.TestCase):
    def test_pilot_generation_admits_tasks_and_ledgers_rejections(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory), b_inst=100)
            sha0 = kernel.snapshot()
            field = latent.Field(d=D)
            breaker = Breaker(field.port("breaker"), kernel.runner, seed=11, d=D)
            admitted = 0
            for generation in (1, 2):
                proposals = breaker.propose(generation, kernel.archive.public_view(), {}, n_prop=12)
                self.assertTrue(proposals)
                for proposal in proposals:
                    self.assertTrue({"lineage", "witness", "checker", "examples", "hidden"} <= set(proposal))
                    self.assertIn(proposal["lineage"], LINEAGES)
                    key = proposal.pop("key")
                    decision = kernel.admission.admit(proposal, generation, sha0)
                    breaker.observe_admission(generation, key, decision, kernel.archive.public_view())
                    admitted += decision["admitted"]
            self.assertGreaterEqual(admitted, 1)
            rejections = kernel.ledger.of_kind("rejection")
            self.assertGreaterEqual(len(rejections), 1)
            for entry in rejections:
                self.assertIn(entry["payload"]["certificate"], CERTIFICATES)
                self.assertIn(entry["payload"]["lineage"], LINEAGES)
            self.assertEqual(len(kernel.ledger.of_kind("admission")), admitted)
            self.assertEqual(len(breaker.authored), admitted)
            self.assertEqual(breaker.pending, {})
            self.assertTrue(kernel.ledger.verify())
            # Signatures of admitted tasks are written once, tagged with archive ordinals.
            view = kernel.archive.public_view()
            self.assertEqual(breaker.write_state(view), admitted + 1)
            self.assertEqual(sorted(t for t in field.breaker.tags() if t >= 0), list(range(admitted)))
            self.assertEqual(breaker.write_state(view), 1, "unchanged tasks are not rewritten")
            self.assertGreater(kernel.meter.total("kernel")["steps"], 0)
            self.assertEqual(sum(breaker.credit.values()), 0.0, "regret pays nothing at admission")


class CreditTests(unittest.TestCase):
    def _breaker(self, **kwargs):
        field = latent.Field(d=D)
        return Breaker(field.port("breaker"), lambda program, inputs: None, seed=1, d=D, **kwargs)

    def test_regret_pays_by_generations_to_crossing(self):
        breaker = self._breaker()
        view = [view_entry("t0001")]
        breaker.pending["k"] = ("mutate", ["sort", "x"])
        breaker.observe_admission(1, "k", {"admitted": True, "id": "t0001", "kb_margin": 0.0}, view)
        self.assertEqual(breaker.credit["mutate"], 0.0)
        breaker.observe_crossing("t0001", 2)
        self.assertAlmostEqual(breaker.credit["mutate"], 1 / 3)
        self.assertGreater(breaker.multiplier["mutate"], 1.0)
        breaker.pending["k2"] = ("compose", ["sort", "x"])
        breaker.observe_admission(1, "k2", {"admitted": False, "certificate": "Kb", "detail": ""}, view)
        self.assertEqual(breaker.credit["compose"], 0.0)
        self.assertEqual(breaker.wasted["compose"], 1)
        self.assertLess(breaker.multiplier["compose"], 1.0)
        breaker.observe_crossing("t9999", 1)                      # not ours: ignored
        self.assertAlmostEqual(breaker.credit["mutate"], 1 / 3)

    def test_per_admission_credit_without_regret(self):
        breaker = self._breaker(regret=False)
        view = [view_entry("t0001")]
        breaker.pending["k"] = ("analogy", ["sort", "x"])
        breaker.observe_admission(1, "k", {"admitted": True, "id": "t0001", "kb_margin": 0.0}, view)
        self.assertEqual(breaker.credit["analogy"], 1.0)
        breaker.observe_crossing("t0001", 0)
        self.assertEqual(breaker.credit["analogy"], 1.0, "a crossing pays nothing in the no-regret arm")

    def test_slots_keep_one_per_lineage_and_follow_multipliers(self):
        breaker = self._breaker()
        slots = breaker.slots(12)
        self.assertEqual(slots, {name: 3 for name in LINEAGES})
        self.assertEqual(breaker.slots(2), {name: 1 for name in LINEAGES})
        breaker.multiplier.update({"mutate": 4.0, "compose": 0.25, "analogy": 0.25, "distinguisher": 1.0})
        slots = breaker.slots(12)
        self.assertEqual(sum(slots.values()), 12)
        self.assertTrue(all(count >= 1 for count in slots.values()))
        self.assertGreater(slots["mutate"], slots["distinguisher"])
        self.assertGreater(slots["distinguisher"], slots["compose"])
        for _ in range(20):
            breaker._tune("compose", False)
        self.assertEqual(breaker.multiplier["compose"], 0.25, "multipliers are bounded")


class LineageTests(unittest.TestCase):
    def test_compose_substitutes_a_list_valued_inner_body(self):
        self.assertEqual(programs.compose(["sum", "x"], ["sort", "x"]), ["sum", ["sort", "x"]])
        self.assertEqual(programs.compose(["map", ["lambda", ["v"], ["+", "v", 1]], "x"], ["tail", "x"]),
                         ["map", ["lambda", ["v"], ["+", "v", 1]], ["tail", "x"]])
        field = latent.Field(d=D)
        breaker = Breaker(field.port("breaker"), lambda program, inputs: None, seed=2, d=D)
        for _ in range(30):
            body = breaker._compose([])
            inner = [node for node in programs._paths(body) if node[1] == "x"]
            self.assertTrue(inner, body)

    def test_distinguisher_targets_inputs_where_the_crossing_program_disagrees(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory))
            field = latent.Field(d=D)
            breaker = Breaker(field.port("breaker"), kernel.runner, seed=3, d=D)
            body = ["sort", "x"]
            breaker.authored["t0001"] = {"body": body, "lineage": "mutate", "generation": 1}
            view = [view_entry("t0001", "crossed", crossing_program=["lambda", ["x"], ["reverse", "x"]])]
            found, inputs = breaker._distinguisher(view, {})
            self.assertEqual(found, body)
            self.assertTrue(inputs)
            for x in inputs:
                self.assertNotEqual(sorted(x), list(reversed(x)))
            proposal = breaker._triple("distinguisher", found, inputs)
            self.assertIsNotNone(proposal)
            instance_inputs = [i["inputs"][0] for i in proposal["examples"] + proposal["hidden"]]
            for x in inputs:
                self.assertIn(list(x), instance_inputs)
            # Agreement everywhere: nothing to distinguish.
            view = [view_entry("t0001", "crossed", crossing_program=["lambda", ["x"], ["sort", "x"]])]
            self.assertEqual(breaker._distinguisher(view, {}), (None, ()))

    def test_analogy_reads_the_builders_residue_and_picks_the_nearest_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory))
            field = latent.Field(d=D)
            breaker = Breaker(field.port("breaker"), kernel.runner, seed=4, d=D)
            breaker.authored["t0001"] = {"body": ["sort", "x"], "lineage": "mutate", "generation": 1}
            breaker.authored["t0002"] = {"body": ["reverse", "x"], "lineage": "mutate", "generation": 1}
            view = [view_entry("t0001", "crossed", crossing_program=["lambda", ["x"], ["sort", "x"]]),
                    view_entry("t0002")]
            for task in view:
                breaker.signatures[task["id"]] = breaker.book.encode_examples(task["examples"])
            field.port("builder").write(latent.random_vector(D, 77), tag=1)      # a residue for t0002
            body = breaker._analogy(view)
            self.assertIsNotNone(breaker._analogy_choice)
            self.assertEqual(breaker._analogy_choice["body"], body)
            self.assertEqual(breaker._analogy_choice["lineage"], "analogy")

    def test_records_arm_uses_text_and_writes_no_vectors(self):
        with tempfile.TemporaryDirectory() as directory:
            kernel = Kernel(Path(directory))
            field = latent.Field(d=D)
            breaker = Breaker(field.port("breaker"), kernel.runner, seed=5, d=D, records=True)
            self.assertFalse(breaker.latent_channel)
            breaker.authored["t0001"] = {"body": ["sort", "x"], "lineage": "mutate", "generation": 1}
            breaker.authored["t0002"] = {"body": ["reverse", "x"], "lineage": "mutate", "generation": 1}
            view = [view_entry("t0001", "crossed", crossing_program=["lambda", ["x"], ["sort", "x"]]),
                    view_entry("t0002")]
            breaker.records_in = {"residues": {"t0002": {"best_public": 0.5, "best_dsl": "(sort x)"}}}
            body = breaker._analogy(view)
            self.assertIsNotNone(body)
            self.assertEqual(breaker.write_state(view), 0)
            self.assertEqual(len(field.breaker), 0)
            records = breaker.state_records(view)
            self.assertEqual(records["tasks"]["t0001"]["output_kind"], "list[int]")


if __name__ == "__main__":
    unittest.main()
