"""Independent tests for uncertainty-scaled routing of DUST action predictions."""
import dataclasses
import unittest
import numpy as np
from rsi3.dust_metapolicy import DustMetaPolicy
from rsi3.experiment import ARMS

class DustUncertaintyTests(unittest.TestCase):
    def test_control_policy_exactly_preserves_original_choice(self):
        from rsi3.metarl import MetaPolicy
        actions = ["behave:filter", "decompose:filter", "prior"]
        shape = np.zeros(11)
        normal = MetaPolicy()
        control = DustMetaPolicy(seed=11)
        control.models = dict(normal.models)
        for total in (0, 1, 3, 10):
            spent = {"prior": 2, "behave:filter": 1}
            self.assertEqual(normal.choose(actions, shape, spent, total),
                             control.choose(actions, shape, spent, total))

    def test_uncertainty_scaled_action_selection_is_deterministic(self):
        actions = ["a", "b", "c"]
        policy = DustMetaPolicy(uncertainty_exploration=True, seed=11)
        policy.probability = lambda action, x: {"a": 0.92, "b": 0.53, "c": 0.20}[action]
        shape = np.zeros(11)
        selected = policy.choose(actions, shape, {"a": 2, "b": 0, "c": 0}, 2)
        self.assertIn(selected, actions)
        self.assertEqual(selected, policy.choose(actions, shape, {"a": 2, "b": 0, "c": 0}, 2))

    def test_registered_arm_is_single_flag_ablation(self):
        a = dataclasses.asdict(ARMS["RSI3_META_HONEST_DUST"])
        b = dataclasses.asdict(ARMS["RSI3_META_HONEST_DUST_UNCERTAINTY"])
        self.assertFalse(a.pop("meta_dust_uncertainty"))
        self.assertTrue(b.pop("meta_dust_uncertainty"))
        a.pop("name")
        b.pop("name")
        self.assertEqual(a, b)

if __name__ == "__main__":
    unittest.main()
