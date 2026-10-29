"""Meta-RL policy: learning across tasks, transfer to unseen shapes, wiped-memory control,
and the transfer measurement's consistency with VALIDATION."""
import unittest

import numpy as np

from rsi2.corpus import load_train, load_validation

from rsi3.experiment import ARMS, _validation
from rsi3.longrun import agent_validation
from rsi3.loop import Runtime
from rsi3.metarl import MetaPolicy, context, shape_features
from rsi3.verifier import FrozenVerifier

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}


class PolicyTests(unittest.TestCase):
    def test_shapes_follow_public_examples(self):
        train = {t.name: t for t in load_train()}
        keep = shape_features(train["keep-mod-k with k=2"].examples)
        has = shape_features(train["has-k with k=3"].examples)
        self.assertEqual(keep[7], 1.0)       # ordered subsequence: filter-shaped
        self.assertEqual(has[3], 1.0)        # boolean output
        self.assertEqual(has[7], 0.0)

    def test_reward_on_one_task_transfers_to_an_unseen_task_of_the_same_shape(self):
        policy = MetaPolicy(exploration=0.0)
        filter_shape = np.zeros(11); filter_shape[[0, 7, 8]] = 1.0
        bool_shape = np.zeros(11); bool_shape[[3, 10]] = 1.0
        for generation in (1, 2):
            for _ in range(6):
                policy.record(generation, "decompose:filter", context(filter_shape, 0, 0), 1)
                policy.record(generation, "decompose:filter", context(bool_shape, 0, 0), 0)
                policy.record(generation, "decompose:any", context(bool_shape, 0, 0), 1)
                policy.record(generation, "decompose:any", context(filter_shape, 0, 0), 0)
                policy.record(generation, "prior", context(filter_shape, 0, 0), 0)
                policy.record(generation, "prior", context(bool_shape, 0, 0), 0)
        policy.fit(2)
        actions = ["prior", "decompose:filter", "decompose:any"]
        # A task it never acted on: only its public shape is known.
        self.assertEqual(policy.choose(actions, filter_shape, {}, 0), "decompose:filter")
        self.assertEqual(policy.choose(actions, bool_shape, {}, 0), "decompose:any")

    def test_wiped_memory_refits_on_the_current_generation_only(self):
        kept, wiped = MetaPolicy(), MetaPolicy(wipe=True)
        shape = np.zeros(11)
        for policy in (kept, wiped):
            policy.record(1, "prior", context(shape, 0, 0), 1)
            policy.record(2, "prior", context(shape, 0, 0), 0)
        self.assertEqual(kept.fit(2)["replayed"], 2)
        self.assertEqual(wiped.fit(2)["replayed"], 1)

    def test_untried_actions_are_explored(self):
        policy = MetaPolicy()
        policy.record(1, "prior", context(np.zeros(11), 0, 0), 0)
        policy.fit(1)
        self.assertEqual(policy.choose(["prior", "decompose:map"], np.zeros(11),
                                       {"prior": 3}, 3), "decompose:map")


class RuntimeTests(unittest.TestCase):
    def test_meta_wake_spends_the_task_share_and_verifies_once(self):
        train = sorted(load_train(), key=lambda t: t.name)[:10]
        config = {"B_wake": 16, "B_eval": 16, "dreams": 4, "search": SEARCH,
                  "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2},
                  "invention": {}, "meta": {"chunk": 8}, "compact_searches": True}
        runtime = Runtime(11, train, ARMS["RSI3_META"], config)
        for _ in range(2):
            record = runtime.generation()
            wake = record["wake"]
            self.assertLessEqual(wake["spent"], wake["budget"])
            self.assertLessEqual(runtime.verifier.queries, len(train) * record["generation"])
            for episode in wake["episodes"]:
                self.assertTrue(episode["pathway"] == "prior" or episode["pathway"] == "invented"
                                or episode["pathway"].startswith("decompose:"))
            self.assertIsNotNone(wake["meta"])

    def test_agent_validation_equals_validation_for_a_prior_only_arm(self):
        train = sorted(load_train(), key=lambda t: t.name)[:8]
        validation = sorted(load_validation(), key=lambda t: t.name)
        config = {"B_wake": 16, "B_eval": 16, "dreams": 4, "search": SEARCH,
                  "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2}}
        runtime = Runtime(11, train, ARMS["RSI3_UNIFORM_FM"], config)
        runtime.generation()
        rsi2 = {k: config[k] for k in ("B_wake", "B_eval", "dreams", "search")}
        plain = _validation(runtime.state, validation, rsi2)
        agent = agent_validation(runtime, runtime.state.recognition, validation, rsi2,
                                 FrozenVerifier(validation, step_budget=2000), 1)
        self.assertEqual(plain["solved_names"], agent["solved_names"])


if __name__ == "__main__":
    unittest.main()
