"""Synthetic controller checks; no external TEST examples are loaded or solved."""
import copy
import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rsi2 import experiment
from rsi2.terms import Int, pretty


class ReportingOnly(float):
    def __lt__(self, other):
        raise AssertionError("TEST score selected a controller action")

    __le__ = __gt__ = __ge__ = __lt__


class SyntheticRecognition:
    def __init__(self, generation):
        self.generation = generation

    def grammar_for(self, task, grammar):
        return grammar

    def to_dict(self):
        return {"synthetic": True, "generation": self.generation}


class Harness:
    def __init__(self, testcase):
        self.testcase = testcase
        self.train = [SimpleNamespace(name=f"train_{i}") for i in range(36)]
        self.validation = [SimpleNamespace(name=f"validation_{i}") for i in range(12)]
        self.test = [SimpleNamespace(name=f"synthetic_test_{i}") for i in range(12)]
        self.wake_calls, self.heuristic_calls, self.validation_calls, self.test_calls = [], [], [], []

    def wake(self, state, tasks, config, *, library_learning, recognition_learning):
        self.testcase.assertIs(tasks, self.train)
        self.testcase.assertEqual(config, experiment.FROZEN_CONFIG)
        state.generation += 1
        if library_learning:
            name = f"learned_g{state.generation}_0"
            state.grammar.library[name] = Int(state.generation)
            state.library_history.append({"name": name, "generation": state.generation,
                                          "term_dict": Int(state.generation).to_dict(),
                                          "readable_term": pretty(Int(state.generation))})
        state.solutions["train_0"] = Int(state.generation)
        if recognition_learning:
            state.recognition = SyntheticRecognition(state.generation)
        dreams = 2 if recognition_learning else 0
        state.logical_evaluations += 10 + dreams
        self.wake_calls.append((state.generation, library_learning, recognition_learning))
        return {"generation": state.generation, "wake_candidate_evaluations": 10,
                "dream_candidate_evaluations": dreams, "wall_seconds": 0.0, "cpu_seconds": 0.0}

    def improve(self, state, tasks, config, *, primitive_only, update_state):
        self.testcase.assertIs(tasks, self.validation)
        self.testcase.assertEqual(config, experiment.FROZEN_CONFIG)
        before = experiment.final_state(state)
        incumbent = state.heuristic.to_dict()
        count = 30 if primitive_only else 24
        best = 0.25 if primitive_only else 0.5
        report = {"generation": state.generation, "seed": state.seed,
                  "primitive_only": primitive_only, "update_state": update_state,
                  "incumbent": incumbent, "best_term": Int(state.generation).to_dict(),
                  "best_full_fraction": best, "synthesis_candidate_evaluations": 6,
                  "inner_candidate_evaluations": count - 6, "candidate_evaluations": count,
                  "adopted": update_state and state.generation % 2 == 0,
                  "candidates": [{"index": i} for i in range(6)],
                  "wall_seconds": 0.0, "cpu_seconds": 0.0}
        self.heuristic_calls.append({"generation": state.generation,
                                     "primitive_only": primitive_only,
                                     "update_state": update_state, "before": before,
                                     "incumbent": incumbent})
        if update_state:
            if report["adopted"]:
                state.heuristic = Int(state.generation)
            state.heuristic_history.append(copy.deepcopy(report))
            state.logical_evaluations += count
        return report

    @staticmethod
    def assessment(tasks, budget, count, test=False):
        return {"tasks": len(tasks), "solved": 1,
                "solved_fraction": ReportingOnly(1 / len(tasks)) if test else 1 / len(tasks),
                "mean_candidates_to_solution": count, "candidate_evaluations": count,
                "budget": budget, "records": [{"name": t.name} for t in tasks]}

    def assess(self, state, tasks, budget, searchconfig):
        self.testcase.assertIs(tasks, self.validation)
        self.testcase.assertEqual(searchconfig, experiment.FROZEN_CONFIG["search"])
        self.validation_calls.append((state.generation, budget))
        return self.assessment(tasks, budget, 3 * (budget // 64))

    def sealed(self, tasks, grammar, heuristic, budget, searchconfig, *, conditioner):
        self.testcase.assertIs(tasks, self.test)
        self.testcase.assertEqual(searchconfig, experiment.FROZEN_CONFIG["search"])
        state = conditioner.__self__
        before = experiment.final_state(state)
        self.testcase.assertIs(conditioner(tasks[0], grammar), grammar)
        self.testcase.assertEqual(experiment.final_state(state), before)
        self.test_calls.append((state.generation, budget))
        return self.assessment(tasks, budget, 5 * (budget // 64), test=True)

    def run(self, arm, directory, seed=11, progress=None):
        with patch.object(experiment, "load_partitions", return_value=(self.train, self.validation, self.test)), \
                patch.object(experiment.learning, "wake_sleep", side_effect=self.wake), \
                patch.object(experiment.learning, "assess_development", side_effect=self.assess), \
                patch.object(experiment.heuristics, "improve_heuristic", side_effect=self.improve), \
                patch.object(experiment.sealed_evaluation, "report", side_effect=self.sealed):
            return experiment.run_arm(arm, seed, copy.deepcopy(experiment.FROZEN_CONFIG),
                                      directory, progress=progress)


class ExperimentTests(unittest.TestCase):
    def test_complete_full_runs_all_generations_and_charges_counterfactual(self):
        harness = Harness(self)
        progress = []
        with tempfile.TemporaryDirectory() as directory:
            result = harness.run("FULL", directory, progress=lambda *item: progress.append(item))
            persisted = json.loads(experiment.result_path(directory, "FULL", 11).read_text())
        self.assertEqual(result["status"], "complete")
        self.assertNotIn("in_progress", result)
        self.assertEqual(persisted["status"], "complete")
        self.assertEqual([r["generation"] for r in result["generations"]], list(range(9)))
        self.assertEqual(progress, [("FULL", 11, g) for g in range(9)])
        self.assertEqual(len(harness.wake_calls), 8)
        self.assertEqual(len(harness.validation_calls), 9)
        self.assertEqual(len(harness.test_calls), 9)
        self.assertEqual(len(harness.heuristic_calls), 9)
        primitive, current = harness.heuristic_calls[-2:]
        self.assertTrue(primitive["primitive_only"])
        self.assertFalse(primitive["update_state"])
        self.assertFalse(current["primitive_only"])
        self.assertTrue(current["update_state"])
        # The extra primitive-only CPU/logical work is accounted separately,
        # while task-search state and original mutation incumbent are shared.
        primitive_state = copy.deepcopy(primitive["before"])
        current_state = copy.deepcopy(current["before"])
        self.assertEqual(current_state.pop("logical_evaluations")
                         - primitive_state.pop("logical_evaluations"), 30)
        self.assertEqual(primitive_state, current_state)
        self.assertEqual(primitive["incumbent"], current["incumbent"])
        self.assertEqual(result["comparison"]["quota"], 6)
        self.assertEqual(result["comparison"]["library_best"], 0.5)
        self.assertEqual(result["comparison"]["primitives_best"], 0.25)
        self.assertEqual(result["totals"]["candidate_evaluations"], 390)
        self.assertEqual(result["final_state"]["logical_evaluations"], 390)
        self.assertEqual(len(result["final_state"]["library_history"]), 8)
        self.assertEqual([r["generation"] for r in result["final_state"]["heuristic_history"]],
                         [2, 4, 6, 8])
        self.assertTrue(all("state" in row for row in result["generations"]))
        self.assertTrue(all("cpu_seconds" in row["test"] for row in result["generations"]))

    def test_ablation_flags_disable_only_the_named_component(self):
        cases = [("NO_LIBRARY", False, True, 8, 360),
                 ("NO_RECOGNITION", True, False, 8, 344),
                 ("NO_HEURISTIC", True, True, 0, 168)]
        with tempfile.TemporaryDirectory() as directory:
            for arm, library, recognition, heuristic_calls, cost in cases:
                with self.subTest(arm=arm):
                    harness = Harness(self)
                    result = harness.run(arm, directory)
                    self.assertEqual(harness.wake_calls, [(g, library, recognition) for g in range(1, 9)])
                    self.assertEqual(len(harness.heuristic_calls), heuristic_calls)
                    self.assertEqual(result["totals"]["candidate_evaluations"], cost)
                    self.assertNotIn("comparison", result)
                    self.assertEqual(bool(result["final_state"]["library"]), library)
                    self.assertEqual(result["final_state"]["recognition"] is not None, recognition)

    def test_oneshot_executes_one_entire_round_then_freezes(self):
        harness = Harness(self)
        with tempfile.TemporaryDirectory() as directory:
            result = harness.run("ONESHOT", directory)
        self.assertEqual(harness.wake_calls, [(1, True, True)])
        self.assertEqual(len(harness.heuristic_calls), 1)
        self.assertEqual(harness.validation_calls, [(0, 64), (1, 64)])
        self.assertEqual(harness.test_calls, [(0, 64), (1, 64)])
        self.assertEqual(result["totals"]["candidate_evaluations"], 52)
        self.assertEqual(result["final_state"]["generation"], 1)
        for row in result["generations"][2:]:
            self.assertTrue(row["reused_measurement"])
            self.assertEqual(row["reuse_source_generation"], 1)
            self.assertEqual(row["test"], result["generations"][1]["test"])
            self.assertEqual(row["state"], result["generations"][1]["state"])
            self.assertIsNone(row["learning"])
            self.assertIsNone(row["heuristic"])

    def test_base_and_brute_reuse_one_measurement_and_never_train(self):
        with tempfile.TemporaryDirectory() as directory:
            for arm, budget, cost in [("BASE", 64, 8), ("BRUTE", 640, 80)]:
                harness = Harness(self)
                result = harness.run(arm, directory)
                self.assertEqual(harness.wake_calls, [])
                self.assertEqual(harness.heuristic_calls, [])
                self.assertEqual(harness.validation_calls, [(0, budget)])
                self.assertEqual(harness.test_calls, [(0, budget)])
                self.assertEqual(result["totals"]["candidate_evaluations"], cost)
                self.assertEqual(result["final_state"]["generation"], 0)
                self.assertTrue(all(r["reused_measurement"] for r in result["generations"][1:]))
                self.assertFalse(result["generations"][0]["reused_measurement"])

    def test_failure_preserves_atomic_checkpoint_and_refuses_rerun(self):
        harness = Harness(self)
        with tempfile.TemporaryDirectory() as directory:
            def stop(arm, seed, generation):
                if generation == 1:
                    raise RuntimeError("synthetic core failure")
            with self.assertRaisesRegex(RuntimeError, "synthetic core failure"):
                harness.run("FULL", directory, progress=stop)
            path = experiment.result_path(directory, "FULL", 11)
            record = json.loads(path.read_text())
            self.assertEqual(record["status"], "failed")
            self.assertEqual([row["generation"] for row in record["generations"]], [0, 1])
            self.assertEqual(record["totals"]["candidate_evaluations"], 52)
            self.assertFalse(path.with_name(path.name + ".tmp").exists())
            with self.assertRaises(FileExistsError):
                harness.run("FULL", directory)

    def test_all_frozen_numbers_and_types_are_checked(self):
        self.assertEqual(experiment.validate_config(experiment.FROZEN_CONFIG), experiment.FROZEN_CONFIG)
        paths = [(key,) for key in experiment.FROZEN_CONFIG]
        paths += [(parent, key) for parent in ("search", "heuristics")
                  for key in experiment.FROZEN_CONFIG[parent]]
        for path in paths:
            with self.subTest(path=path):
                changed = copy.deepcopy(experiment.FROZEN_CONFIG)
                container = changed if len(path) == 1 else changed[path[0]]
                value = container[path[-1]]
                container[path[-1]] = value + 1 if type(value) is int else None
                with self.assertRaises(ValueError):
                    experiment.validate_config(changed)
        changed = copy.deepcopy(experiment.FROZEN_CONFIG)
        changed["schema_version"] = True
        with self.assertRaises(ValueError):
            experiment.validate_config(changed)
        for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
            self.assertEqual(experiment.os.environ[variable], "1")

    def test_inflight_final_generation_preserves_logs_without_promoting_comparison(self):
        harness = Harness(self)
        sealed = harness.sealed

        def fail_final(*args, **kwargs):
            if kwargs["conditioner"].__self__.generation == 8:
                raise RuntimeError("synthetic final measurement interruption")
            return sealed(*args, **kwargs)

        harness.sealed = fail_final
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "synthetic final measurement interruption"):
                harness.run("FULL", directory)
            record = json.loads(experiment.result_path(directory, "FULL", 11).read_text())
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["generations"][-1]["generation"], 7)
        self.assertNotIn("comparison", record)
        self.assertEqual(record["in_progress"]["generation"], 8)
        self.assertEqual(record["in_progress"]["learning"]["generation"], 8)
        self.assertEqual(len(record["in_progress"]["heuristic"]["candidates"]), 6)
        self.assertEqual(len(record["in_progress"]["primitive_only"]["candidates"]), 6)
        self.assertEqual(record["in_progress"]["comparison"]["generation"], 8)
        self.assertIsNotNone(record["in_progress"]["validation"])
        self.assertEqual(record["totals"]["candidate_evaluations"], 385)

    def test_partition_validation_uses_separate_test_loader_without_test_values(self):
        manifest = json.loads((Path(experiment.__file__).parent / "data" / "split_manifest.json").read_text())
        partitions = [[SimpleNamespace(name=name) for name in manifest[partition]]
                      for partition in ("train", "validation", "test")]
        with patch.object(experiment, "load_train", return_value=partitions[0]), \
                patch.object(experiment, "load_validation", return_value=partitions[1]), \
                patch.object(experiment.sealed_evaluation, "load_test", return_value=partitions[2]) as sealed:
            self.assertEqual(experiment.load_partitions(), tuple(partitions))
            sealed.assert_called_once_with()
            partitions[2][0].name = "changed assignment"
            with self.assertRaisesRegex(ValueError, "test tasks"):
                experiment.load_partitions()

    def test_stop_labels_active_partial_but_keeps_unrun_and_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = [("BASE", 11), ("FULL", 11), ("FULL", 22)]
            for (arm, seed), status in zip(jobs, ("complete", "running", "unrun")):
                experiment.atomic_write(experiment.result_path(directory, arm, seed),
                                        experiment.initial_record(arm, seed, experiment.FROZEN_CONFIG, status))
            experiment.stop_unfinished(directory, jobs, "aggregate CPU limit reached",
                                       observed_cpu={("FULL", 11): 23.0},
                                       observed_wall={("FULL", 11): 42.0})
            statuses = [json.loads(experiment.result_path(directory, *job).read_text())["status"]
                        for job in jobs]
            self.assertEqual(statuses, ["complete", "partial", "unrun"])
            partial = json.loads(experiment.result_path(directory, "FULL", 11).read_text())
            self.assertEqual(partial["totals"]["cpu_seconds"], 23.0)
            self.assertEqual(partial["totals"]["wall_seconds"], 42.0)
            self.assertEqual(partial["accounting"]["candidate_evaluations_scope"],
                             "completed_operations_lower_bound")

    def test_scheduler_owns_twenty_one_runs_and_rejects_existing_output(self):
        created = []
        concurrency = {"active": 0, "peak": 0}

        class SyntheticProcess:
            def __init__(self, target, args):
                self.target, self.args, self.pid, self.exitcode = target, args, 987654, None
                created.append(self)

            def start(self):
                concurrency["active"] += 1
                concurrency["peak"] = max(concurrency["peak"], concurrency["active"])
                self.target(*self.args)
                self.exitcode = 0

            def is_alive(self):
                return False

            def join(self, timeout=None):
                concurrency["active"] -= 1

        events = queue.Queue()
        events.close = lambda: None
        context = SimpleNamespace(Queue=lambda: events, Process=SyntheticProcess)

        def synthetic_run(arm, seed, config, output, **kwargs):
            self.assertTrue(kwargs["reserved"])
            record = experiment.initial_record(arm, seed, config, "complete")
            record["totals"] = {"candidate_evaluations": 7, "wall_seconds": 0.1, "cpu_seconds": 0.1}
            experiment.atomic_write(experiment.result_path(output, arm, seed), record)
            return record

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(experiment.multiprocessing, "get_context", return_value=context), \
                patch.object(experiment, "run_arm", side_effect=synthetic_run), \
                patch.object(experiment, "process_cpu_seconds", return_value=0.0):
            result = experiment.schedule(experiment.FROZEN_CONFIG, directory, 5)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(len(created), 21)
            self.assertEqual(concurrency["peak"], 5)
            self.assertEqual(len(result["runs"]), 21)
            self.assertEqual(result["totals"]["candidate_evaluations"], 147)
            self.assertTrue(all(run["status"] == "complete" for run in result["runs"]))
            with self.assertRaises(FileExistsError):
                experiment.schedule(experiment.FROZEN_CONFIG, directory, 5)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                experiment.schedule(experiment.FROZEN_CONFIG, directory, 6)

    def test_scheduler_cpu_cap_terminates_five_workers_and_labels_queued_unrun(self):
        created = []

        class BusyProcess:
            def __init__(self, target, args):
                self.args, self.pid, self.alive, self.exitcode = args, 987654, False, None
                created.append(self)

            def start(self):
                arm, seed, config, output, _ = self.args
                experiment.atomic_write(experiment.result_path(output, arm, seed),
                                        experiment.initial_record(arm, seed, config, "running"))
                self.alive = True

            def is_alive(self):
                return self.alive

            def terminate(self):
                self.alive = False
                self.exitcode = -15

            def join(self, timeout=None):
                pass

        events = SimpleNamespace(get=lambda timeout: (_ for _ in ()).throw(queue.Empty),
                                 close=lambda: None)
        context = SimpleNamespace(Queue=lambda: events, Process=BusyProcess)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(experiment.multiprocessing, "get_context", return_value=context), \
                patch.object(experiment, "process_cpu_seconds", return_value=18000.0):
            result = experiment.schedule(experiment.FROZEN_CONFIG, directory, 5)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["stop_reason"], "aggregate CPU limit reached")
            self.assertEqual(len(created), 5)
            self.assertTrue(all(not process.is_alive() for process in created))
            self.assertEqual(sum(run["status"] == "partial" for run in result["runs"]), 5)
            self.assertEqual(sum(run["status"] == "unrun" for run in result["runs"]), 16)
            self.assertGreaterEqual(result["totals"]["cpu_seconds"], 90000.0)
            record = json.loads(experiment.result_path(directory, "BASE", 11).read_text())
            self.assertEqual(record["totals"]["cpu_seconds"], 18000.0)
            self.assertEqual(record["accounting"]["candidate_evaluations_scope"],
                             "completed_operations_lower_bound")


if __name__ == "__main__":
    unittest.main()
