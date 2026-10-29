"""The shared-trajectory runner reproduces separate per-seed runs, and resumes exactly."""
import json
import tempfile
import unittest
from pathlib import Path

from rsi2.corpus import load_train, load_validation

from rsi3.experiment import ARMS
from rsi3.longrun import run, shared_trajectory_ok
from rsi3.loop import Runtime

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}
CONFIG = {"seeds": [11, 22], "generations": 2, "B_wake": 12, "B_eval": 12, "dreams": 4,
          "search": SEARCH, "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2},
          "invention": {}}


def _split():
    train = sorted(load_train(), key=lambda t: t.name)[:8]
    validation = sorted(load_validation(), key=lambda t: t.name)[:4]
    return train, validation


class LongRunTests(unittest.TestCase):
    def test_only_recognition_free_arms_share_a_trajectory(self):
        self.assertTrue(shared_trajectory_ok(ARMS["RSI3_UNIFORM_FM_INVP"]))
        self.assertTrue(shared_trajectory_ok(ARMS["RSI3_UNIFORM_FM"]))
        self.assertFalse(shared_trajectory_ok(ARMS["RSI3"]))

    def test_shared_records_equal_separate_runs_and_resume_is_exact(self):
        from rsi3.experiment import _validation
        train, validation = _split()
        rsi2 = {k: CONFIG[k] for k in ("B_wake", "B_eval", "dreams", "search")}
        for arm in ("RSI3_UNIFORM_FM", "RSI3_UNIFORM_FM_INVP"):
            separate = {}
            for seed in CONFIG["seeds"]:
                runtime = Runtime(seed, train, ARMS[arm], rsi2 | {
                    "controller": CONFIG["controller"], "invention": {}})
                rows = []
                for _ in range(CONFIG["generations"]):
                    record = runtime.generation()
                    record["validation"] = _validation(runtime.state, validation, rsi2)
                    rows.append(record)
                separate[seed] = rows
            with tempfile.TemporaryDirectory() as straight, tempfile.TemporaryDirectory() as split:
                self.assertTrue(run(arm, CONFIG, Path(straight), train=train,
                                    validation=validation))
                # Stop after the first generation, then resume from the checkpoint.
                self.assertFalse(run(arm, CONFIG, Path(split), max_minutes=0, train=train,
                                     validation=validation))
                self.assertTrue(run(arm, CONFIG, Path(split), train=train, validation=validation))
                for seed in CONFIG["seeds"]:
                    a = json.loads((Path(straight) / f"{arm}_seed{seed}.json").read_text())
                    b = json.loads((Path(split) / f"{arm}_seed{seed}.json").read_text())
                    key = lambda g: (g["train_solved"], g["validation"]["solved_names"],
                                     g["sleep"]["dreams"],
                                     g["sleep"]["dream_candidate_evaluations"],
                                     [(e["task"], e["pathway"], e["start"], e["evaluated"],
                                       e["outcome"], e["digest"]) for e in g["wake"]["episodes"]])
                    self.assertEqual([key(g) for g in a["generations"]],
                                     [key(g) for g in separate[seed]], (arm, seed))
                    self.assertEqual([key(g) for g in a["generations"]],
                                     [key(g) for g in b["generations"]], (arm, seed, "resume"))
                    self.assertEqual(a["final"]["solutions"], b["final"]["solutions"])


if __name__ == "__main__":
    unittest.main()
