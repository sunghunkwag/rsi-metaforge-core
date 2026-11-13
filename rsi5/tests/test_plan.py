"""The run plan: what ``phase1.load_plan`` refuses. (The driver itself is run in
``test_guard.Workers.test_run_driver_itself``.)"""
import json
import tempfile
import unittest
from pathlib import Path

from rsi5 import phase1

PLAN = Path(phase1.__file__).resolve().parent / "runs" / "p1.json"


class Plan(unittest.TestCase):
    def _load(self, **changes):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        for key, value in changes.items():
            if value is None:
                plan.pop(key)
            else:
                plan[key] = value
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            return phase1.load_plan(path)

    def test_registered_plan_loads(self):
        plan = self._load()
        self.assertEqual((plan["budget"], plan["child_point_cap"], max(plan["report_budgets"])), (1000000, 64, 1000000))

    def test_point_cap_other_than_the_engines_constant_is_refused(self):
        with self.assertRaisesRegex(ValueError, "point cap"):
            self._load(child_point_cap=32)
        self.assertEqual(self._load(child_point_cap=None)["budget"], 1000000)     # absent: the constant applies

    def test_report_budget_above_the_run_budget_is_refused(self):
        with self.assertRaisesRegex(ValueError, "report budget"):
            self._load(budget=100000)
        with self.assertRaisesRegex(ValueError, "report budget"):
            self._load(report_budgets=[1000, 2000000])

    def test_missing_key_and_foreign_probe_set_are_refused(self):
        for key in ("budget", "report_budgets", "max_size", "step_budget", "partitions", "vocabularies"):
            with self.assertRaisesRegex(ValueError, "lacks"):
                self._load(**{key: None})
        with self.assertRaisesRegex(ValueError, "probe set"):
            self._load(probe_set_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
