"""Tests of optional forward-only public credit. No hidden examples are read."""
import unittest
from rsi3.forward_credit import output_credit, public_credit
from rsi3.loop import ArmConfig, Runtime
from rsi2.corpus import load_train

class ForwardCreditTests(unittest.TestCase):
    def test_exact_and_partial(self):
        self.assertEqual(output_credit(3, 3), 1)
        self.assertEqual(output_credit(3, 5), 1 / 3)
        self.assertEqual(output_credit([1, 9], [1, 2]), .5)
        self.assertEqual(output_credit("a", 4), 0)
        self.assertEqual(public_credit([(True, 3), (False, 0)], [3, 4]), .5)

    def test_forward_arm_is_bounded_and_optional(self):
        cfg = {"B_wake": 8, "B_eval": 8, "dreams": 2,
               "search": {"max_size": 10, "max_expansions": 1000,
                          "step_budget": 200},
               "controller": {"chunk": 8, "exploration": .3,
                              "analog_neighbors": 2}}
        tasks = load_train()[:3]
        runtime = Runtime(11, tasks, ArmConfig(
            "forward", allocation="forward", failure_memory=True,
            genesis=False, designer_kinds=("prior",), forward_credit=True), cfg)
        first = runtime.generation()
        second = runtime.generation()
        for result in (first, second):
            self.assertLessEqual(result["wake"]["spent"], 8 * len(tasks))
            self.assertEqual(result["verifier_queries"],
                             runtime.verifier.queries if result is second
                             else result["verifier_queries"])
        self.assertTrue(runtime.credit_by_task)
        self.assertTrue(all(0 <= x <= 1 for x in runtime.credit_by_task.values()))
        standard = Runtime(11, tasks, ArmConfig(
            "standard", allocation="uniform", failure_memory=True,
            genesis=False, designer_kinds=("prior",)), cfg)
        standard.generation()
        self.assertEqual(standard.credit_by_task, {})

if __name__ == "__main__":
    unittest.main()
