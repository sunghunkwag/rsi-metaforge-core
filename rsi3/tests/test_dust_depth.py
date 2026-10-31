"""Depth-two public-practice DUST routing tests."""
import dataclasses
import unittest
import numpy as np

from rsi2.corpus import load_train
from rsi3.experiment import ARMS
from rsi3.loop import Runtime
from rsi3.metarl import shape_features


class DepthPracticeTests(unittest.TestCase):
    def test_depth_arm_differs_by_one_flag(self):
        a = dataclasses.asdict(ARMS["RSI3_META_HONEST_DUST"])
        b = dataclasses.asdict(ARMS["RSI3_META_HONEST_DUST_DEPTH"])
        self.assertFalse(a.pop("meta_dust_depth"))
        self.assertTrue(b.pop("meta_dust_depth"))
        a.pop("name")
        b.pop("name")
        self.assertEqual(a, b)

    def test_extra_public_search_is_charged_and_has_actual_outcomes(self):
        train = load_train()
        config = {
            "B_wake": 8, "B_eval": 8, "dreams": 0,
            "search": {"step_budget": 2000, "max_size": 12,
                       "max_expansions": 20000},
            "controller": {"chunk": 8, "exploration": .3, "analog_neighbors": 2},
            "meta": {"chunk": 4, "selfplay": 0},
            "behave": {"max_size": 10, "max_unroll": 6,
                       "combo_limit": 2000000},
            "compact_searches": True,
        }
        selected = next(t for t in train if t.name == "keep-mod-k with k=2")
        programs = []
        for name in ("RSI3_META_HONEST_DUST", "RSI3_META_HONEST_DUST_DEPTH"):
            runtime = Runtime(11, train[:3], ARMS[name], config)
            shape = shape_features(selected.examples, runtime.arm.meta_extended)
            evaluations = runtime._practice(selected.examples, shape, 1)
            episodes = list(runtime.metapolicy.episodes)
            self.assertTrue(all(e[3] in (0, 1) for e in episodes))
            programs.append((evaluations, episodes))
        self.assertGreaterEqual(programs[1][0], programs[0][0])
        self.assertGreaterEqual(len(programs[1][1]), len(programs[0][1]))
        second_window = [
            episode for episode in programs[1][1]
            if abs(float(episode[2][-2]) - np.log1p(1)/3) < 1e-12
        ]
        self.assertTrue(second_window,
                        "at least one actual second-window search must be recorded")

if __name__ == "__main__":
    unittest.main()
