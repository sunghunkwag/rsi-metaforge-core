"""Efficient replication orchestration, using mocked cycles and toy evidence."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.learning import State
from rsi2.research import efficient_memory, efficient_run, engine, run as source_run
from rsi2.research.memory import snapshot
from rsi2.types import Arrow, INT


def _task(name):
    return Task(name, Arrow(INT, INT), (((2,), 2),), (((3,), 3),))


def _assessment(tasks, grammar, heuristic, budget, searchconfig, conditioner=None):
    """Completed fabricated evidence; no task search or evaluator is called."""
    records = [{"name": task.name, "solved": True, "public_matched": True,
                "candidates": 1, "candidates_to_solution": 1,
                "wall_seconds": 0.0, "evaluation_steps": 2, "heuristic_calls": 3,
                "heuristic_evaluations": 4, "heuristic_steps": 5,
                "exhausted": False, "verification_examples": 1,
                "verification_steps": 2, "failure": None} for task in tasks]
    return {"tasks": len(records), "solved": len(records), "solved_fraction": 1.0,
            "mean_candidates_to_solution": 1.0, "candidate_evaluations": len(records),
            "budget": budget, "wall_seconds": 0.0, "records": records}


class _Pool:
    def __init__(self, grammar, seed, mode):
        self.grammar, self.seed, self.mode = grammar, seed, mode

    def to_dict(self):
        return {"seed": self.seed, "mode": self.mode}


def _phase(started=(), reason=None, results=None):
    return {"started": list(started), "reason": reason, "results": results or {},
            "observed_cpu": {}, "elapsed_wall": {}}


class EfficientSeedTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(engine.REGISTERED_CONFIG)
        self.train, self.validation, self.confirmation = ([_task(name)] for name in
                                                          ("train", "validation", "confirmation"))

    def _setup(self, stack, cycle):
        stack.enter_context(patch.object(efficient_run, "load_config", return_value=self.config))
        stack.enter_context(patch.object(efficient_run, "load_train", return_value=self.train))
        stack.enter_context(patch.object(efficient_run, "load_validation", return_value=self.validation))
        stack.enter_context(patch.object(efficient_run, "load_confirmation", return_value=self.confirmation))
        stack.enter_context(patch.object(efficient_run, "load_calibration", return_value={"test": True}))
        wake = stack.enter_context(patch.object(efficient_run, "wake_sleep", return_value={
            "wake_candidate_evaluations": 2, "dream_candidate_evaluations": 3}))
        stack.enter_context(patch.object(efficient_run, "ProposalPool", _Pool))
        stack.enter_context(patch.object(efficient_run, "cycle", side_effect=cycle))
        assess = stack.enter_context(patch.object(efficient_memory, "assess", side_effect=_assessment))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return wake, assess

    def test_seed_keeps_cycle_order_settings_and_independent_shared_clients(self):
        self.assertIs(efficient_run.cycle, engine.cycle)
        calls, clients = [], []
        def create_client(store):
            client = efficient_memory.EfficientEvaluationMemory(store)
            clients.append(client)
            return client
        def cycle(state, pool, memory, validation, confirmation, number, config):
            self.assertIs(validation, self.validation)
            self.assertIs(confirmation, self.confirmation)
            self.assertIs(config, self.config)
            self.assertEqual(pool.seed, 11)
            calls.append((number, pool.mode, state, memory))
            # Cross-arm measurements reuse completed evidence without charging
            # the first client's work to the later clients.
            measurement = memory.measure(state, validation, state.heuristic,
                                         config["B_eval"], config["search"])
            memory.measure(state, self.train, state.heuristic, config["B_eval"], config["search"])
            return {"cycle": number, "arm": pool.mode, "seed": state.seed,
                    "validation": measurement, "proposal_productivity": {"verified": 0},
                    "adopted_index": None, "draw": {"new_raw_draws": 34, "replay_draws": 0},
                    "probe_program_evaluations": 0, "memory": memory.summary()}
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            wake, assess = self._setup(stack, cycle)
            stack.enter_context(patch.object(efficient_run, "EfficientEvaluationMemory",
                                            side_effect=create_client))
            result = efficient_run.run_seed(11, folder)
            record = json.loads(Path(folder, "seed11.json").read_text())
            with self.assertRaises(FileExistsError):
                efficient_run.run_seed(11, folder)
        self.assertEqual([(number, arm) for number, arm, _, _ in calls],
                         [(number, arm) for number in range(1, 4) for arm in self.config["arms"]])
        self.assertEqual(len(clients), 4)
        self.assertEqual(len({id(client.store) for client in clients}), 1)
        self.assertEqual([client.actual_candidate_evaluations for client in clients], [1, 1, 0, 0])
        self.assertEqual(assess.call_count, 2)
        self.assertEqual(wake.call_args.args[1], self.train)
        self.assertEqual(wake.call_args.args[2], {"test": True, "dreams": 16})
        self.assertEqual(len({id(state) for _, _, state, _ in calls}), 3)
        self.assertEqual(record["actual_candidate_evaluations"], 5 + 2 + 9 * 34)
        self.assertEqual(record["shared_evaluation_store"]["entries"], 2)
        self.assertEqual(record["status"], "selection_frozen")
        self.assertEqual(result["status"], "selection_frozen")
        self.assertEqual(record["config"], self.config)
        self.assertEqual(record["source_commit"], efficient_run.SOURCE_COMMIT)

    def test_original_per_seed_guard_stops_before_next_cycle(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            self._setup(stack, lambda *args: self.fail("cap must precede cycle"))
            stack.enter_context(patch.object(efficient_run.time, "process_time",
                                            side_effect=[0, 1801, 1802]))
            result = efficient_run.run_seed(11, folder)
            record = json.loads(Path(folder, "seed11.json").read_text())
        self.assertEqual(result["status"], "partial")
        self.assertEqual(record["stop_reason"], "per-seed share of aggregate CPU cap")
        self.assertTrue(all(target["cycles"] == [] for target in record["arms"].values()))
        self.assertEqual(record["actual_candidate_evaluations"], 6)


class EfficientAuditTests(unittest.TestCase):
    def test_incomplete_selection_never_opens_audit_capability(self):
        with patch.object(efficient_run, "load_audit", side_effect=AssertionError("sealed")):
            result = efficient_run.reporting_audit(None, [{"status": "partial"}], {})
        self.assertEqual(result["status"], "unrun")

    def test_audit_uses_shared_backend_without_learning_or_cycle_calls(self):
        config = copy.deepcopy(engine.REGISTERED_CONFIG)
        initial = snapshot(State(11))
        record = {"seed": 11, "status": "selection_frozen", "arms": {
            arm: {"final_state": initial, "cycles": []} for arm in config["arms"]}}
        clients = []
        def create_client(store):
            client = efficient_memory.EfficientEvaluationMemory(store)
            clients.append(client)
            return client
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(efficient_run, "load_audit", return_value=[_task("toy audit")]), \
                patch.object(efficient_run, "load_train", return_value=[_task("toy train")]), \
                patch.object(efficient_memory, "assess", side_effect=_assessment) as assess, \
                patch.object(efficient_run, "EfficientEvaluationMemory", side_effect=create_client), \
                patch.object(efficient_run, "cycle", side_effect=AssertionError("frozen")), \
                patch.object(efficient_run, "wake_sleep", side_effect=AssertionError("frozen")), \
                redirect_stdout(io.StringIO()):
            result = efficient_run.reporting_audit(folder, [record], config)
            saved = json.loads(Path(folder, "seed11.json").read_text())
        self.assertEqual(len(clients), 1)
        self.assertEqual(assess.call_count, 2)
        self.assertEqual(result["candidate_evaluations"], 2)
        self.assertEqual(result["memory"]["task_cache_hits"], 4)
        self.assertEqual(saved["status"], "complete")
        self.assertTrue(saved["arms"]["static"]["audit"]["cache_hit"])


class EfficientControllerTests(unittest.TestCase):
    def setUp(self):
        self.config = copy.deepcopy(engine.REGISTERED_CONFIG)

    def _records(self, output, status):
        for seed in self.config["seeds"]:
            engine.atomic_write(Path(output) / f"seed{seed}.json", {
                "seed": seed, "config": self.config, "status": status, "arms": {},
                "cpu_seconds": 0.0, "actual_candidate_evaluations": 9})

    def test_reuses_original_watchdog_and_freezes_before_custom_audit_worker(self):
        self.assertIs(efficient_run.CPUController, source_run.CPUController)
        self.assertIs(efficient_run._run_phase, source_run._run_phase)
        self.assertIs(efficient_run._records_after_selection, source_run._records_after_selection)
        phases = []
        def phase(kind, keys, output, config, budget, workers, records=None, worker_target=None):
            self.assertIs(worker_target, efficient_run._phase_worker)
            self.assertEqual(config, self.config)
            phases.append((kind, workers))
            if kind == "selection":
                self._records(output, "selection_frozen")
                return _phase(keys)
            summary = json.loads(Path(output, "summary.json").read_text())
            self.assertTrue(summary["selection_frozen_before_audit"])
            self.assertEqual(summary["intervention"], efficient_run.INTERVENTION)
            self.assertTrue(all(record["status"] == "selection_frozen" for record in records))
            self._records(output, "complete")
            return _phase(keys, results={"audit": {"result": {
                "status": "complete", "candidate_evaluations": 2, "cpu_seconds": 0.0}}})
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(efficient_run, "load_config", return_value=self.config), \
                patch.object(efficient_run, "_run_phase", side_effect=phase), \
                redirect_stdout(io.StringIO()):
            summary = efficient_run.run(Path(folder) / "new", 3)
            with self.assertRaises(FileExistsError):
                efficient_run.run(Path(folder) / "new", 3)
        self.assertEqual(phases, [("selection", 3), ("audit", 1)])
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["actual_candidate_evaluations"], 29)

    def test_partial_selection_skips_audit_and_preserves_lower_bound(self):
        def phase(kind, keys, output, config, budget, workers, records=None, worker_target=None):
            self.assertEqual(kind, "selection")
            self._records(output, "partial")
            return _phase(keys, "selection incomplete")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(efficient_run, "load_config", return_value=self.config), \
                patch.object(efficient_run, "_run_phase", side_effect=phase), \
                patch.object(efficient_run, "load_audit", side_effect=AssertionError("sealed")), \
                redirect_stdout(io.StringIO()):
            summary = efficient_run.run(Path(folder) / "new", 3)
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["audit"]["status"], "unrun")
        self.assertEqual(summary["candidate_evaluations_scope"], "completed_operations_lower_bound")

    def test_aggregate_cap_after_freeze_prevents_audit_spawn(self):
        def phase(kind, keys, output, config, budget, workers, records=None, worker_target=None):
            self.assertEqual(kind, "selection")
            self._records(output, "selection_frozen")
            return _phase(keys)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(efficient_run, "load_config", return_value=self.config), \
                patch.object(efficient_run, "_run_phase", side_effect=phase), \
                patch.object(efficient_run.CPUController, "exhausted", return_value=True), \
                patch.object(efficient_run, "load_audit", side_effect=AssertionError("sealed")), \
                redirect_stdout(io.StringIO()):
            summary = efficient_run.run(Path(folder) / "new", 3)
        self.assertTrue(summary["selection_frozen_before_audit"])
        self.assertEqual(summary["status"], "partial")
        self.assertIn("before audit", summary["audit"]["reason"])

    def test_partial_audit_reconstructs_persisted_work_without_new_selection(self):
        def phase(kind, keys, output, config, budget, workers, records=None, worker_target=None):
            if kind == "selection":
                self._records(output, "selection_frozen")
                return _phase(keys)
            records[0]["arms"] = {"original": {"cycles": [],
                "audit": {"actual_candidate_evaluations": 5}}}
            engine.atomic_write(Path(output) / "seed11.json", records[0])
            return _phase(keys, "aggregate CPU ceiling reached")
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(efficient_run, "load_config", return_value=self.config), \
                patch.object(efficient_run, "_run_phase", side_effect=phase), \
                redirect_stdout(io.StringIO()):
            summary = efficient_run.run(Path(folder) / "new", 3)
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["audit"]["candidate_evaluations"], 5)
        self.assertEqual(summary["actual_candidate_evaluations"], 32)


if __name__ == "__main__":
    unittest.main()
