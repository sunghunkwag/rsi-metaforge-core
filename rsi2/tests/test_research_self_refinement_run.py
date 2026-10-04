"""Score-blind coordinator wrapper tests; no tasks or study evidence loaded."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from rsi2.research import run as shared_run
from rsi2.research import self_refinement_run as runner


REGISTERED = Path(runner.__file__).parent / "SELF_REFINEMENT_PROTOCOL.json"


def _phase(reason=None, status="complete", exception=None):
    result = {"reason": reason,
              "results": {"coordinator": {"result": {"status": status}}}}
    if exception is not None:
        result["exception"] = exception
    return result


class _Events:
    def __init__(self):
        self.items, self.closed, self.flushed = [], False, False

    def put(self, item):
        self.items.append(item)

    def close(self):
        self.closed = True

    def join_thread(self):
        self.flushed = True


class SelfRefinementWrapperTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(REGISTERED.read_text())

    def test_reuses_watchdog_and_passes_registered_protocol_to_one_custom_worker(self):
        self.assertIs(runner.CPUController, shared_run.CPUController)
        self.assertIs(runner._run_phase, shared_run._run_phase)
        def phase(kind, keys, output, protocol, budget, workers, worker_target):
            self.assertEqual(kind, "self_refinement")
            self.assertEqual(keys, ["coordinator"])
            self.assertEqual(protocol, self.protocol)
            self.assertEqual(workers, 1)
            self.assertIs(worker_target, runner._worker)
            self.assertEqual(json.loads(Path(output, "summary.json").read_text())["status"], "running")
            runner.atomic_write(Path(output, "self_refinement.json"), {"status": "complete", "cycles": []})
            return _phase()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "_run_phase", side_effect=phase), \
                patch.object(runner, "CPUController", return_value=SimpleNamespace(spent=lambda: 12.5)), \
                redirect_stdout(io.StringIO()):
            result = runner.run(REGISTERED, Path(folder, "new"))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["cpu_seconds"], 12.5)
        self.assertEqual(result["candidate_evaluations_scope"], "all_completed_operations")

    def test_cap_preserves_completed_checkpoint_and_labels_partial_counts(self):
        evidence = {"status": "running", "cycles": [{"cycle": 1, "decision": "KEEP"}],
                    "completed_operations": [{"seed": 11, "actual_candidate_evaluations": 7}]}
        def phase(kind, keys, output, protocol, budget, workers, worker_target):
            runner.atomic_write(Path(output, "self_refinement.json"), evidence)
            return _phase("aggregate CPU ceiling reached", "partial")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "_run_phase", side_effect=phase), \
                patch.object(runner, "CPUController", return_value=SimpleNamespace(spent=lambda: 298.1)), \
                redirect_stdout(io.StringIO()):
            result = runner.run(REGISTERED, Path(folder, "new"))
            saved = json.loads(Path(folder, "new", "self_refinement.json").read_text())
        self.assertEqual(saved, evidence)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stop_reason"], "aggregate CPU ceiling reached")
        self.assertEqual(result["candidate_evaluations_scope"], "completed_operations_lower_bound")

    def test_terminal_partial_never_becomes_complete(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "_run_phase", return_value=_phase(status="partial")), \
                redirect_stdout(io.StringIO()):
            result = runner.run(REGISTERED, Path(folder, "new"))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stop_reason"], "coordinator did not complete")

    def test_terminal_success_requires_matching_completed_checkpoint(self):
        for checkpoint_status in (None, "running", "partial"):
            def phase(kind, keys, output, protocol, budget, workers, worker_target):
                if checkpoint_status is not None:
                    runner.atomic_write(Path(output, "self_refinement.json"),
                                        {"status": checkpoint_status, "cycles": []})
                return _phase()
            with self.subTest(checkpoint_status=checkpoint_status), \
                    tempfile.TemporaryDirectory() as folder, \
                    patch.object(runner, "_run_phase", side_effect=phase), \
                    redirect_stdout(io.StringIO()):
                result = runner.run(REGISTERED, Path(folder, "new"))
            self.assertEqual(result["status"], "partial")

    def test_final_measured_cpu_at_ceiling_invalidates_terminal_success(self):
        def phase(kind, keys, output, protocol, budget, workers, worker_target):
            runner.atomic_write(Path(output, "self_refinement.json"), {"status": "complete", "cycles": []})
            return _phase()
        for spent in (300.0, 301.0):
            with self.subTest(spent=spent), tempfile.TemporaryDirectory() as folder, \
                    patch.object(runner, "_run_phase", side_effect=phase), \
                    patch.object(runner, "CPUController", return_value=SimpleNamespace(spent=lambda: spent)), \
                    redirect_stdout(io.StringIO()):
                result = runner.run(REGISTERED, Path(folder, "new"))
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["candidate_evaluations_scope"], "completed_operations_lower_bound")
            self.assertIn("CPU", result["stop_reason"])

    def test_parent_exception_is_rethrown_after_partial_summary_saved(self):
        error = KeyboardInterrupt("synthetic interruption")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(runner, "_run_phase", return_value=_phase(
                    "parent interrupted", "partial", error)), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt) as caught:
                runner.run(REGISTERED, Path(folder, "new"))
            saved = json.loads(Path(folder, "new", "summary.json").read_text())
        self.assertIs(caught.exception, error)
        self.assertEqual(saved["status"], "partial")

    def test_protocol_changes_and_numeric_type_substitutions_are_rejected(self):
        variants = []
        for key, value in (("schema_version", True), ("B_eval", 64.0),
                           ("cpu_limit_seconds", 301)):
            changed = copy.deepcopy(self.protocol)
            changed[key] = value
            variants.append(changed)
        for protocol in variants:
            with self.subTest(protocol=protocol), tempfile.TemporaryDirectory() as folder, \
                    patch.object(runner, "_run_phase") as phase:
                path = Path(folder, "changed.json")
                path.write_text(json.dumps(protocol))
                with self.assertRaises(ValueError):
                    runner.run(path, Path(folder, "new"))
                phase.assert_not_called()
                self.assertFalse(Path(folder, "new").exists())

    def test_existing_output_is_rejected_without_altering_evidence(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "_run_phase") as phase:
            existing = Path(folder, "evidence.json")
            existing.write_text("preserve")
            with self.assertRaises(FileExistsError):
                runner.run(REGISTERED, folder)
            self.assertEqual(existing.read_text(), "preserve")
            phase.assert_not_called()

    def test_worker_returns_only_status_and_flushes_terminal_queue(self):
        module, events = ModuleType("rsi2.research.self_refinement"), _Events()
        calls = []
        def execute(protocol, output):
            calls.append((protocol, output))
            return {"status": "complete", "large_details": "x" * 100000}
        module.run = execute
        with patch.dict(sys.modules, {module.__name__: module}):
            runner._worker("self_refinement", "coordinator", "/tmp/synthetic", self.protocol, None, events)
        self.assertEqual(events.items, [{"key": "coordinator", "result": {"status": "complete"}}])
        self.assertEqual(calls, [(self.protocol, Path("/tmp/synthetic"))])
        self.assertTrue(events.closed and events.flushed)

    def test_worker_error_is_bounded_and_queue_is_flushed(self):
        module, events = ModuleType("rsi2.research.self_refinement"), _Events()
        def execute(protocol, output):
            raise RuntimeError("synthetic " + "x" * 100000)
        module.run = execute
        with patch.dict(sys.modules, {module.__name__: module}):
            runner._worker("self_refinement", "coordinator", "/tmp/synthetic", self.protocol, None, events)
        self.assertEqual(len(events.items), 1)
        self.assertTrue(events.items[0]["error"].startswith("RuntimeError: synthetic"))
        self.assertLessEqual(len(events.items[0]["error"]), 512)
        self.assertTrue(events.closed and events.flushed)


if __name__ == "__main__":
    unittest.main()
