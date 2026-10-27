"""Small end-to-end runs of the RSI-3 loop on a TRAIN subset."""
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.search import solve

from rsi3.loop import ArmConfig, Runtime

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}
CONFIG = {"B_wake": 12, "B_eval": 12, "dreams": 4, "search": SEARCH,
          "controller": {"chunk": 6, "exploration": 0.3, "analog_neighbors": 2}}


def _subset():
    train = sorted(load_train(), key=lambda t: t.name)
    easy = [t for t in train
            if solve(t.examples, t.request_type, 12, Grammar(), **SEARCH).term is not None][:2]
    hard = [t for t in train if t not in easy][:4]
    return easy + hard


class LoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks = _subset()

    def _run(self, arm, generations=2):
        runtime = Runtime(11, self.tasks, arm, CONFIG)
        return runtime, [runtime.generation() for _ in range(generations)]

    def test_budget_and_query_caps(self):
        for arm in (ArmConfig("learned"),
                    ArmConfig("uniform", allocation="uniform", genesis=False,
                              designer_kinds=("prior",))):
            runtime, records = self._run(arm)
            for record in records:
                self.assertLessEqual(record["wake"]["spent"], CONFIG["B_wake"] * len(self.tasks))
                queried = [e["task"] for e in record["wake"]["episodes"] if e["outcome"] != "none"]
                self.assertEqual(len(queried), len(set(queried)), "one query per task per generation")
            self.assertLessEqual(runtime.verifier.queries, 2 * len(self.tasks))

    def test_solved_tasks_receive_no_budget_and_memory_is_receipted(self):
        runtime, records = self._run(ArmConfig("learned"))
        solved_after_first = {v["task"] for v in records[0]["wake"]["verified"]}
        self.assertTrue(solved_after_first, "the easy tasks should solve in generation 1")
        later = {e["task"] for e in records[1]["wake"]["episodes"]}
        self.assertFalse(solved_after_first & later)
        for episode in runtime.memory.episodes:
            if episode.outcome != "none":
                self.assertIsNotNone(episode.receipt_id)
        for name, record in runtime.memory.solutions.items():
            self.assertIn(name, runtime.state.solutions)
            self.assertIn(name, runtime.integrator.provenance)

    def test_genesis_pathways_appear_after_verified_solutions(self):
        runtime, records = self._run(ArmConfig("learned"))
        self.assertEqual(len(records[0]["genesis_created"]), records[0]["train_solved"])
        self.assertEqual(records[0]["pathways"]["genesis"], records[0]["train_solved"])
        runtime_off, records_off = self._run(ArmConfig("off", genesis=False))
        self.assertEqual(records_off[-1]["pathways"]["genesis"], 0)

    def test_uniform_arm_resumes_instead_of_restarting(self):
        arm = ArmConfig("uniform", allocation="uniform", genesis=False, designer_kinds=("prior",))
        runtime, records = self._run(arm, generations=4)
        starts = [min((e["start"] for e in r["wake"]["episodes"]), default=0) for r in records]
        # The prior is refit during sleep on the solution set. If generation k
        # added no solution, generation k+1 wakes under the same grammar and
        # every window must resume past its searched prefix.
        checked = 0
        for k in range(1, len(records) - 1):
            if records[k - 1]["train_solved"] == records[k]["train_solved"]:
                self.assertGreater(starts[k + 1], 0, f"generation {k + 2} restarted")
                checked += 1
        if not checked:
            self.skipTest("every generation added a solution; nothing to resume")


if __name__ == "__main__":
    unittest.main()
