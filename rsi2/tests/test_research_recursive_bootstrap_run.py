import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.research import recursive_bootstrap_run as runner


class Budget:
    cleanup_margin = 2

    def __init__(self, limit):
        self.limit = limit

    def spent(self):
        return 5


class RecursivePilotGateTests(unittest.TestCase):
    def fixture(self, output, *, status="complete", rows=None, altered=False):
        config = copy.deepcopy(runner.REGISTERED_CONFIG)
        if altered:
            config["B_eval"] = 65
        Path(output, "FULL_seed11.json").write_text(json.dumps({
            "status": status, "config": config, "work": {},
            "generations": [{"generation": gen} for gen in
                            (range(9) if rows is None else rows)]}))
        return {"reason": None, "results": {11: {"result": {"status": "complete"}}},
                "started": [11], "observed_cpu": {}, "elapsed_wall": {}}

    def execute(self, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            def phase(kind, keys, output, config, budget, **options):
                self.assertEqual(kind, "recursive_bootstrap")
                self.assertEqual(keys, [11])
                self.assertEqual(options["workers"], 1)
                return self.fixture(output, **kwargs)
            with patch.object(runner, "CPUController", Budget), patch.object(runner, "_run_phase", phase):
                return runner.run_pilot(directory)

    def test_completed_solo_pilot_never_claims_rsi(self):
        result = self.execute()
        self.assertEqual(result["status"], "complete")
        self.assertFalse(result["rsi_success"])
        self.assertEqual(result["other_seeds_and_controls"], "unrun")

    def test_event_success_cannot_replace_missing_generations(self):
        self.assertEqual(self.execute(rows=range(3))["status"], "partial")

    def test_config_mismatch_vetoes_completed_event(self):
        self.assertEqual(self.execute(altered=True)["status"], "partial")

    def test_partial_checkpoint_vetoes_completed_event(self):
        self.assertEqual(self.execute(status="running")["status"], "partial")

    def test_generation_bool_cannot_stand_for_integer(self):
        rows = list(range(9))
        rows[1] = True
        self.assertEqual(self.execute(rows=rows)["status"], "partial")


if __name__ == "__main__":
    unittest.main()
