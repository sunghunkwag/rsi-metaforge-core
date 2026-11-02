"""Self-curriculum: imagined tasks stay out of TRAIN, and every seed's recognition refit sees the pool."""
import unittest

import numpy as np

from rsi2.corpus import load_train

from rsi3.experiment import ARMS
from rsi3.longrun import curriculum_extra, seed_recognition
from rsi3.loop import Runtime

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}
CONFIG = {"B_wake": 12, "B_eval": 12, "dreams": 4, "search": SEARCH,
          "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2},
          "invention": {}, "meta": {"chunk": 4, "selfplay": 12}, "behave": {"max_size": 6},
          "curriculum": {"count": 6, "solve": 3, "pool": 6, "hard_chunk": 4},
          "compact_searches": True}


class CurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        train = sorted(load_train(), key=lambda t: t.name)[:8]
        cls.runtime = Runtime(11, train, ARMS["RSI3_META_CURRICULUM"], CONFIG)
        cls.record = cls.runtime.generation()

    def test_imagined_tasks_never_enter_train(self):
        names = set(self.runtime.state.solutions)
        self.assertFalse(any(n.startswith("imagined_") for n in names))
        self.assertEqual(self.record["train_solved"], len(names))
        pool = self.runtime.curriculum_pool.items
        self.assertEqual(self.record["sleep"]["curriculum"]["pool"], len(pool))
        for name, (task, program) in pool.items():
            self.assertTrue(name.startswith("imagined_"))
            self.assertNotIn(name, names)

    def test_every_seed_refit_includes_the_pool(self):
        runtime = self.runtime
        rsi2 = {k: CONFIG[k] for k in ("B_wake", "B_eval", "dreams", "search")}
        extra = curriculum_extra(runtime)
        self.assertIsNotNone(extra)
        # The primary seed's own refit reproduces the model the sleep fitted,
        # so refitted seeds are trained on the same non-dream corpus.
        model, metrics = seed_recognition(runtime.state, runtime.public, rsi2, runtime.state.seed,
                                          runtime.state.generation, extra)
        stored = runtime.state.recognition.to_dict()
        again = model.to_dict()
        self.assertEqual(again["contexts"], stored["contexts"])
        self.assertEqual(again["productions"], stored["productions"])
        np.testing.assert_allclose(again["weights"], stored["weights"])
        self.assertEqual(metrics["recognition_examples"],
                         len(runtime.state.solutions) + len(extra) + metrics["dreams"])
        # Without the pool the membership differs (the finding this test guards).
        without, metrics_without = seed_recognition(runtime.state, runtime.public, rsi2,
                                                    runtime.state.seed, runtime.state.generation)
        if extra:
            self.assertEqual(metrics_without["recognition_examples"],
                             metrics["recognition_examples"] - len(extra))

    def test_other_arms_have_no_pool(self):
        train = sorted(load_train(), key=lambda t: t.name)[:4]
        runtime = Runtime(11, train, ARMS["RSI3_META_HONEST"], CONFIG)
        self.assertIsNone(curriculum_extra(runtime))


if __name__ == "__main__":
    unittest.main()
