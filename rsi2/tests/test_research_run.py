"""Score-blind orchestration checks using synthetic checkpoints and CPU work."""
import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rsi2.research import run as runner


def _cpu_worker(kind, key, output, config, records, events):
    """Spawn-safe CPU fixture; it never loads any research task capability."""
    if kind == "selection":
        runner.atomic_write(Path(output) / f"seed{key}.json", {
            "seed": key, "config": config, "status": "running", "arms": {},
            "initial_learning": {"wake_candidate_evaluations": 7,
                                 "dream_candidate_evaluations": 2}})
    else:
        Path(output, "synthetic_audit_opened").write_text("opened")
        for record in records:
            record["arms"] = {"original": {"cycles": [],
                "audit": {"actual_candidate_evaluations": 5}}}
            runner.atomic_write(Path(output) / f"seed{record['seed']}.json", record)
    started = time.process_time()
    value = 1
    while time.process_time() - started < 10:
        value = (value * 1664525 + 1013904223) % (2 ** 32)
    events.put({"key": key, "result": {"status": "selection_frozen", "seed": key}})
    events.close()
    events.join_thread()


def _error_worker(kind, key, output, config, records, events):
    events.put({"key": key, "error": "RuntimeError: synthetic failure"})
    events.close()
    events.join_thread()


def _late_failure_worker(kind, key, output, config, records, events):
    events.put({"key": key, "result": {"status": "selection_frozen", "seed": key}})
    events.close()
    events.join_thread()
    raise SystemExit(7)


def _phase_result(started=(), reason=None, results=None):
    return {"started": list(started), "reason": reason, "results": results or {},
            "observed_cpu": {}, "elapsed_wall": {}}


class ResearchCPUControllerTests(unittest.TestCase):
    def test_proc_parser_handles_spaces_and_parentheses_in_command(self):
        fields = ["S"] + ["0"] * 20
        fields[11], fields[12] = "123", "45"
        stat = "42 (a command (with parentheses)) " + " ".join(fields)
        with patch.object(Path, "read_text", return_value=stat), \
                patch.object(runner.os, "sysconf", return_value=100):
            self.assertEqual(runner.process_cpu_seconds(42), 1.68)
        with patch.object(Path, "read_text", side_effect=FileNotFoundError):
            self.assertEqual(runner.process_cpu_seconds(42), 0.0)
        with patch.object(Path, "read_text", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                runner.process_cpu_seconds(42)

    def test_parent_reaped_and_live_cpu_are_counted_without_double_count(self):
        with patch.object(runner.time, "process_time", side_effect=[10, 11, 11.1]), \
                patch.object(runner, "_children_cpu_seconds", side_effect=[5, 7, 7.5]), \
                patch.object(runner, "process_cpu_seconds", return_value=0.5):
            budget = runner.CPUController(100)
            self.assertEqual(budget.spent([SimpleNamespace(pid=42)]), 3.5)
            # Once reaped, the same .5 s is in RUSAGE_CHILDREN, not live CPU.
            self.assertAlmostEqual(budget.spent(), 3.6)
            self.assertEqual(budget.live_observations[42], 0.5)

    def test_low_limit_interrupts_cpu_workers_and_preserves_checkpoints(self):
        config = {"seeds": [11, 22], "arms": [], "cpu_limit_seconds": 1.2}
        with tempfile.TemporaryDirectory() as folder:
            budget = runner.CPUController(config["cpu_limit_seconds"])
            started = time.perf_counter()
            phase = runner._run_phase("selection", config["seeds"], folder, config,
                budget, 2, worker_target=_cpu_worker)
            records = runner._records_after_selection(Path(folder), config, phase)
            self.assertEqual(phase["reason"], "aggregate CPU ceiling reached")
            self.assertLess(time.perf_counter() - started, 8)
            self.assertGreater(budget.spent(), 0.4)
            self.assertLess(budget.spent(), 3)
            self.assertTrue(any(record["actual_candidate_evaluations"] == 9
                                for record in records))
            self.assertTrue(all(record["status"] == "partial" for record in records))
            self.assertTrue(all(record["candidate_evaluations_scope"] ==
                                "completed_operations_lower_bound" for record in records))
            self.assertTrue(any(record["cpu_seconds"] > 0 for record in records))
            self.assertFalse(Path(folder, "synthetic_audit_opened").exists())

    def test_worker_error_stops_phase_without_waiting_for_all_pending_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            phase = runner._run_phase("selection", [11, 22, 33], folder, {},
                runner.CPUController(10), 1, worker_target=_error_worker)
            self.assertEqual(phase["started"], [11])
            self.assertIn("synthetic failure", phase["reason"])

    def test_nonzero_exit_rejects_previously_sent_success(self):
        with tempfile.TemporaryDirectory() as folder:
            phase = runner._run_phase("selection", [11], folder, {},
                runner.CPUController(10), 1, worker_target=_late_failure_worker)
        self.assertIn("exited with status 7", phase["reason"])

    def test_sampling_failure_still_terminates_and_reaps_workers(self):
        budget = runner.CPUController(10)
        real_spent = budget.spent
        failed = False
        def spent(processes=()):
            nonlocal failed
            processes = tuple(processes)
            if processes and not failed:
                failed = True
                raise OSError("synthetic CPU sampling failure")
            return real_spent(processes)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(budget, "spent", side_effect=spent):
            phase = runner._run_phase("selection", [11], folder,
                {"arms": []}, budget, 1, worker_target=_cpu_worker)
        self.assertIsInstance(phase["exception"], OSError)
        self.assertIn("sampling failure", phase["reason"])
        self.assertFalse(runner.multiprocessing.active_children())


class ResearchRunIsolationTests(unittest.TestCase):
    def setUp(self):
        self.config = {"seeds": [11, 22], "arms": ["original"],
                       "max_workers": 2, "cpu_limit_seconds": 30}

    def _seed_records(self, output, config, status):
        records = []
        for seed in config["seeds"]:
            record = {"seed": seed, "config": config, "status": status,
                      "cpu_seconds": 0.0, "actual_candidate_evaluations": 9,
                      "arms": {"original": {"cycles": []}}}
            runner.atomic_write(Path(output) / f"seed{seed}.json", record)
            records.append(record)
        return records

    def test_partial_selection_never_starts_audit(self):
        phases = []
        def phase(kind, keys, output, config, budget, workers, records=None):
            phases.append(kind)
            self._seed_records(output, config, "partial")
            return _phase_result(keys, "selection incomplete")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "load_config", return_value=self.config), \
                patch.object(runner, "_run_phase", side_effect=phase), \
                patch.object(runner, "load_audit", side_effect=AssertionError("sealed")):
            summary = runner.run(Path(folder) / "new", 2)
        self.assertEqual(phases, ["selection"])
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["audit"]["status"], "unrun")
        self.assertFalse(summary["selection_frozen_before_audit"])
        self.assertEqual(summary["actual_candidate_evaluations"], 18)

    def test_cap_before_selection_never_opens_audit_and_marks_unrun(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "load_config", return_value=self.config), \
                patch.object(runner.CPUController, "exhausted", return_value=True), \
                patch.object(runner, "load_audit", side_effect=AssertionError("sealed")):
            summary = runner.run(Path(folder) / "new", 2)
            records = [json.loads(Path(folder, "new", f"seed{s}.json").read_text())
                       for s in self.config["seeds"]]
        self.assertEqual(summary["audit"]["status"], "unrun")
        self.assertTrue(all(record["status"] == "unrun" for record in records))

    def test_freeze_is_saved_before_isolated_audit_phase(self):
        phases = []
        def phase(kind, keys, output, config, budget, workers, records=None):
            phases.append(kind)
            if kind == "selection":
                self._seed_records(output, config, "selection_frozen")
                return _phase_result(keys)
            saved = json.loads(Path(output, "summary.json").read_text())
            self.assertTrue(saved["selection_frozen_before_audit"])
            self.assertTrue(all(r["status"] == "selection_frozen" for r in records))
            self._seed_records(output, config, "complete")
            return _phase_result(keys, results={"audit": {"result": {
                "status": "complete", "cpu_seconds": 0.0, "candidate_evaluations": 6}}})
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "load_config", return_value=self.config), \
                patch.object(runner, "_run_phase", side_effect=phase):
            summary = runner.run(Path(folder) / "new", 2)
            with self.assertRaises(FileExistsError):
                runner.run(Path(folder) / "new", 2)
        self.assertEqual(phases, ["selection", "audit"])
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["actual_candidate_evaluations"], 24)

    def test_cap_after_freeze_skips_audit(self):
        def phase(kind, keys, output, config, budget, workers, records=None):
            self.assertEqual(kind, "selection")
            self._seed_records(output, config, "selection_frozen")
            return _phase_result(keys)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "load_config", return_value=self.config), \
                patch.object(runner, "_run_phase", side_effect=phase), \
                patch.object(runner.CPUController, "exhausted", return_value=True), \
                patch.object(runner, "load_audit", side_effect=AssertionError("sealed")):
            summary = runner.run(Path(folder) / "new", 2)
        self.assertTrue(summary["selection_frozen_before_audit"])
        self.assertEqual(summary["status"], "partial")
        self.assertIn("before audit", summary["audit"]["reason"])

    def test_mid_audit_cap_preserves_frozen_selection_and_audit_lower_bound(self):
        config = copy.deepcopy(self.config)
        config["cpu_limit_seconds"] = 1.2
        real_phase = runner._run_phase
        def phase(kind, keys, output, config, budget, workers, records=None):
            if kind == "selection":
                self._seed_records(output, config, "selection_frozen")
                return _phase_result(keys)
            return real_phase(kind, keys, output, config, budget, workers, records,
                              worker_target=_cpu_worker)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "load_config", return_value=config), \
                patch.object(runner, "_run_phase", side_effect=phase):
            summary = runner.run(Path(folder) / "new", 2)
            self.assertTrue(Path(folder, "new", "synthetic_audit_opened").exists())
            records = [json.loads(Path(folder, "new", f"seed{s}.json").read_text())
                       for s in config["seeds"]]
        self.assertTrue(all(r["status"] == "selection_frozen" for r in records))
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["audit"]["status"], "partial")
        self.assertEqual(summary["audit"]["candidate_evaluations"], 10)
        self.assertEqual(summary["actual_candidate_evaluations"], 28)
        self.assertGreater(summary["audit_cpu_seconds"], 0)

    def test_lower_bound_uses_latest_cumulative_memory_and_counts_replay(self):
        record = {"initial_learning": {"wake_candidate_evaluations": 7,
                    "dream_candidate_evaluations": 2},
                  "baseline_training": {"actual_candidate_evaluations": 3},
                  "arms": {"original": {"evaluation_memory": {
                    "actual_candidate_evaluations": 11}, "cycles": [
                        {"draw": {"new_raw_draws": 34, "replay_draws": 5},
                         "probe_program_evaluations": 4},
                        {"draw": {"new_raw_draws": 34, "replay_draws": 0},
                         "probe_program_evaluations": 4}]}}}
        self.assertEqual(runner._selection_candidates(record), 104)


if __name__ == "__main__":
    unittest.main()
