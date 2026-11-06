"""The stream driver: TRAIN reproduces rsi3.longrun exactly; stages switch; runs resume.

The stage tasks here are TRAIN tasks (no stage-train or pool task is run),
and the config is the registered HONEST config with 16 self-play tasks.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from rsi2.corpus import load_train, load_validation
from rsi3 import longrun

from rsi4.stages import Driver, STAGES, strip_timing
from rsi4.tests import fixtures

ARM = "RSI3_META_HONEST"


def _setup():
    tmp = Path(tempfile.mkdtemp(dir=fixtures.scratch()))
    config = json.loads(fixtures.CONFIG.read_text())
    config["meta"] = dict(config["meta"], selfplay=16)
    config_path = tmp / "config.json"
    config_path.write_text(json.dumps(config))
    train = load_train()
    stages = {name: train[6 + 3 * k: 9 + 3 * k] for k, name in enumerate(STAGES)}
    plan = {"name": "test", "arms": {ARM: str(config_path)}, "seeds": [11, 22, 33],
            "train_generations": 2, "stage_generations": 1, "evaluate_stage_eval": False}
    return tmp, config, plan, train[:6], stages, load_validation()[:2]


def _names(record) -> str:
    """The record as JSON with rsi2's fresh type-variable names replaced by one label."""
    text = json.dumps(record, sort_keys=True)
    return re.sub(r"\b(_prim_|t)\d+\b", r"\1#", text)


def _child(side: str, out: str) -> None:
    """One side of the reproduction check, run in its own interpreter."""
    tmp, config, plan, train, stages, validation = _setup()
    if side == "longrun":
        longrun.run(ARM, dict(config, generations=2), Path(out), train=train,
                    validation=validation)
    else:
        Driver(dict(plan, stage_generations=0), ARM, Path(out), train=train,
               stage_tasks=stages, validation=validation).run()


class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.config, cls.plan, cls.train, cls.stages, cls.validation = _setup()
        cls.out = cls.tmp / "whole"
        cls.done = Driver(cls.plan, ARM, cls.out, train=cls.train, stage_tasks=cls.stages,
                          validation=cls.validation).run()

    def test_train_phase_reproduces_rsi3_longrun(self):
        """Each side in a fresh process, as on Actions: rsi2 numbers fresh type
        variables with a process-wide counter, so a second run in the same
        process would name them differently."""
        ours_dir, reference = self.tmp / "fresh_driver", self.tmp / "fresh_longrun"
        for side, out in (("driver", ours_dir), ("longrun", reference)):
            subprocess.run([sys.executable, "-c",
                            f"from rsi4.tests.test_stages import _child; _child({side!r}, {str(out)!r})"],
                           cwd=fixtures.REPO, check=True, capture_output=True)
        for seed in (11, 22, 33):
            ours = json.loads((ours_dir / f"{ARM}_seed{seed}.json").read_text())
            theirs = json.loads((reference / f"{ARM}_seed{seed}.json").read_text())
            self.assertEqual(json.dumps(strip_timing(ours["generations"]), sort_keys=True),
                             json.dumps(strip_timing(theirs["generations"]), sort_keys=True))
            self.assertEqual(strip_timing(ours["final"]), strip_timing(theirs["final"]))

    def test_stages_switch_and_complete(self):
        self.assertTrue(self.done)
        status = json.loads((self.out / "STATUS.json").read_text())
        self.assertTrue(status["complete"])
        self.assertTrue(status["run_end"]["valid"])
        stream = json.loads((self.out / f"{ARM}_stream.json").read_text())
        records = [e for e in stream["stream"] if e.get("phase")]
        self.assertEqual([r["phase"] for r in records], list(STAGES))
        for record, name in zip(records, STAGES):
            names = {t.name for t in self.stages[name]}
            self.assertEqual(record["wake"]["budget"], 64 * len(names))
            self.assertTrue({e["task"] for e in record["wake"]["episodes"]} <= names)
        begins = [e for e in stream["stream"] if e.get("event") == "begin_stage"]
        self.assertEqual([b["known_tasks"] for b in begins], [9, 12, 15])
        for phase in ("TRAIN",) + STAGES:
            self.assertTrue((self.out / f"{ARM}.after_{phase}.pkl").exists())

    def test_interrupted_run_resumes_to_the_same_result(self):
        out = self.tmp / "interrupted"
        segments = 0
        while not Driver(self.plan, ARM, out, train=self.train, stage_tasks=self.stages,
                         validation=self.validation).run(max_minutes=0):
            segments += 1
            self.assertLess(segments, 20)
        self.assertGreaterEqual(segments, 1)          # it was stopped and resumed
        for name in [f"{ARM}_seed11.json", f"{ARM}_stream.json"]:
            a = json.loads((self.out / name).read_text())
            b = json.loads((out / name).read_text())
            # rsi2 names fresh type variables from a process-wide counter, so
            # names differ between runs in one process; the rest must not.
            self.assertEqual(_names(strip_timing(a)), _names(strip_timing(b)), name)

    def test_report_reads_a_run(self):
        from rsi4 import report
        self.assertEqual(report.plasticity(self.out, ARM).keys(), set(STAGES))
        self.assertEqual(report.score_matrix(self.out), {})        # stage-eval not asked here
        cost = report.cost(self.out)
        self.assertEqual(cost["breaches"], 0)
        check = report.base_check(self.out, ARM)
        self.assertEqual(set(check["train"]), {11, 22, 33})
        self.assertFalse(check["train"][11]["generations_identical"])   # a 2-generation subset

    def test_a_stage_may_not_repeat_a_known_task(self):
        from rsi4.stages import StageRuntime
        import pickle
        saved = pickle.loads((self.out / f"{ARM}.after_TRAIN.pkl").read_bytes())
        runtime = saved["runtime"]
        self.assertIsInstance(runtime, StageRuntime)
        with self.assertRaises(ValueError):
            runtime.begin_stage("S1", self.train[:1])


if __name__ == "__main__":
    unittest.main()
