import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research import coordinate_diagnostic_run as runner
from rsi2.research.compression import verify_solutions
from rsi2.research.journal_checkpoint import JournalCheckpoint, reconstruct
from rsi2.research.population_search import PopulationResult
from rsi2.types import Arrow, INT


class Budget:
    instances = []

    def __init__(self, limit):
        self.limit, self.cleanup_margin = limit, 2
        self.instances.append(self)

    def spent(self):
        return 5

    def exhausted(self):
        return False


class CoordinateDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.term = next(enumerate_programs(Arrow(INT, INT), Grammar(), max_size=12,
                                          max_expansions=20000)).term

    def tasks(self, count=2, *, hidden_failure=False):
        examples = tuple(((value,), evaluate(self.term, (value,)).value) for value in (-2, 0, 3))
        hidden = (((4,), evaluate(self.term, (4,)).value),)
        return [Task(f"task{number:02}", Arrow(INT, INT), examples,
                     (((4,), 100),) if hidden_failure and number == 1 else hidden)
                for number in range(count)]

    def source(self, tasks):
        proof = verify_solutions({tasks[0].name: self.term}, {}, [tasks[0]])
        return {"source": "TRAIN only", "seed": 11, "status": "partial",
                "evaluation_partitions_opened": False, "final_state": {
                    "raw_solutions": {tasks[0].name: self.term.to_dict()},
                    "acceptance_records": {tasks[0].name: {
                        "id": "seed11:FULL:g0:" + tasks[0].name, "task": tasks[0].name,
                        "generation": 0, "verification": proof}},
                    # These ignored synthetic fields make transfer of fitted
                    # state observable; they are never used to synthesize ASTs.
                    "library": {"unavailable": "deliberately unparsable"},
                    "grammar_weights": {"neg": 9000}, "recognition": "unused"}}

    def config(self, count=2):
        return {**copy.deepcopy(runner.REGISTERED_CONFIG), "train_tasks": count,
                "source_path": "synthetic-source.json.gz", "worker_cpu_allowance_seconds": 30}

    def solver(self, calls=None, *, candidate_bool=False):
        def solve(examples, request_type, budget, grammar, **kwargs):
            if calls is not None:
                calls.append((examples, request_type, budget, grammar, kwargs))
            outcomes = [evaluate(self.term, inputs, library=grammar.library) for inputs, _ in examples]
            result = PopulationResult(term=self.term, candidates=True if candidate_bool else 1,
                                      evaluator_calls=len(outcomes),
                                      evaluation_steps=sum(outcome.steps for outcome in outcomes),
                                      expansions=2, normalization_steps=3, termination="public_match",
                                      seed=kwargs["seed"])
            result.trials = [{"id": 0, "term": self.term.to_dict(), "raw_term": self.term.to_dict(),
                              "public_match": True, "source": "own-enumerator", "parent_id": None}]
            return result
        return solve

    def condition(self, folder, tasks, key, *, calls=None, source=None, candidate_bool=False):
        return runner.run_condition(tasks, source or self.source(tasks), key,
                                    Path(folder) / f"{key}.checkpoint.json", self.config(len(tasks)),
                                    kernels={"population": self.solver(calls, candidate_bool=candidate_bool),
                                             "coordinates": self.solver(calls, candidate_bool=candidate_bool)})

    def test_matched_allocations_fresh_grammar_and_full_independent_proofs(self):
        tasks, calls = self.tasks(), {"population": [], "coordinates": []}
        with tempfile.TemporaryDirectory() as folder:
            records = []
            for method in calls:
                key = f"bank_{method}_B64"
                result = self.condition(folder, tasks, key, calls=calls[method])
                self.assertEqual(result["status"], "complete")
                record = reconstruct(Path(folder) / f"{key}.checkpoint.json").record
                records.append(record)
                self.assertEqual(record["work"]["candidates"], 2)
                self.assertEqual(record["work"]["verification_program_evaluations"], 3)
                self.assertEqual(record["work"]["verification_example_evaluations"], 12)
                self.assertEqual(record["solved_names"], [task.name for task in tasks])
                self.assertTrue(all(row["verification"]["passed"] for row in record["tasks"]))
            self.assertEqual([row["root_allocation"] for row in records[0]["tasks"]],
                             [row["root_allocation"] for row in records[1]["tasks"]])
            grammars = []
            for method in calls:
                for examples, request_type, budget, grammar, kwargs in calls[method]:
                    self.assertIn(examples, [task.examples for task in tasks])
                    self.assertEqual(budget, 64)
                    self.assertEqual(grammar.library, {})
                    self.assertEqual(grammar.weights, {})
                    self.assertEqual(grammar.context_weights, {})
                    self.assertEqual(kwargs["accepted_seeds"][0].training_record, "seed11:FULL:g0:task00")
                    self.assertLessEqual(kwargs["max_cpu_seconds"], 10)
                    grammars.append(grammar)
            self.assertEqual(len({id(grammar) for grammar in grammars}), 4)

    def test_public_match_is_not_admitted_before_hidden_verification_and_work_is_monotone(self):
        tasks, snapshots = self.tasks(hidden_failure=True), []

        class ObservedJournal(JournalCheckpoint):
            def __call__(self, record):
                super().__call__(record)
                snapshots.append((dict(record["work"]), [row["solved"] for row in record["tasks"]]))

        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "JournalCheckpoint", ObservedJournal):
            key = "cold_coordinates_B64"
            self.condition(folder, tasks, key)
            record = reconstruct(Path(folder) / f"{key}.checkpoint.json").record
            self.assertEqual(record["solved_names"], [tasks[0].name])
            self.assertFalse(record["tasks"][1]["verification"]["passed"])
            self.assertFalse(record["tasks"][1]["solved"])
            self.assertTrue(any(solved and solved[-1] is None for _, solved in snapshots))
            for (old, _), (new, _) in zip(snapshots, snapshots[1:]):
                self.assertTrue(all(new[key] >= value for key, value in old.items()))
            self.assertEqual(record["work"]["verification_hidden_example_evaluations"], 3)
            self.assertFalse(record["rsi_success"])

    def test_source_gzip_provenance_and_failed_bank_verification_block_search(self):
        tasks, calls = self.tasks(), []
        source = self.source(tasks)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json.gz"
            with gzip.open(path, "wt") as stream:
                json.dump(source, stream)
            self.assertEqual(runner.load_source(path), source)
            source["final_state"]["raw_solutions"][tasks[0].name] = next(
                item.term for item in enumerate_programs(Arrow(INT, INT), Grammar())
                if any(evaluate(item.term, inputs).value != expected for inputs, expected in tasks[0].examples)).to_dict()
            key = "bank_population_B64"
            with self.assertRaisesRegex(ValueError, "fresh empty-library"):
                self.condition(folder, tasks, key, calls=calls, source=source)
            record = reconstruct(Path(folder) / f"{key}.checkpoint.json").record
            self.assertEqual(calls, [])
            self.assertEqual(record["status"], "failed")
            self.assertFalse(record["source_bank"]["proof"]["passed"])
            self.assertEqual(record["work"]["verification_program_evaluations"], 1)
            self.assertFalse(record["rsi_success"])

    def test_malformed_counter_retains_trace_and_cannot_publish_success(self):
        tasks = self.tasks()
        with tempfile.TemporaryDirectory() as folder:
            key = "cold_population_B64"
            with self.assertRaisesRegex(ValueError, "invalid actual search counter"):
                self.condition(folder, tasks, key, candidate_bool=True)
            record = reconstruct(Path(folder) / f"{key}.checkpoint.json").record
            self.assertEqual(record["status"], "failed")
            self.assertEqual(len(record["tasks"][0]["search"]["trials"]), 1)
            self.assertIsNone(record["tasks"][0]["solved"])
            self.assertEqual(record["work"]["candidates"], 0)
            self.assertEqual(record["work"]["evaluator_calls"], 3)

    def test_b640_selection_requires_complete_solved_set_expansion_without_loss(self):
        def conditions(cold, bank, status="complete"):
            return {f"{memory}_{method}_B64": {"status": status, "solved_names": solved}
                    for memory, pair in (("cold", cold), ("bank", bank))
                    for method, solved in zip(("population", "coordinates"), pair)}
        self.assertEqual(runner.select_b640(conditions((["a"], ["a", "b"]), (["c"], ["c", "d"])))[0], "bank")
        self.assertEqual(runner.select_b640(conditions((["a"], ["a", "b"]), (["c"], ["d", "e"])))[0], "cold")
        choice, reason = runner.select_b640(conditions((["a"], ["b", "c"]), (["d"], ["e", "f"])))
        self.assertEqual(choice, "cold")
        self.assertIn("no qualifying", reason)
        self.assertFalse(runner._comparison(conditions((["a"], ["a", "b"]), (["c"], ["c", "d"]), "partial"), "bank", 64)["strict_expansion"])

    def test_parent_gate_vetoes_missing_tasks_bool_budget_or_unverified_selected_term(self):
        tasks = self.tasks(36)
        with tempfile.TemporaryDirectory() as folder:
            key = "cold_population_B64"
            self.condition(folder, tasks, key)
            record = reconstruct(Path(folder) / f"{key}.checkpoint.json").record
            config, spec, names = self.config(36), runner.condition_spec(key), [task.name for task in tasks]
            self.assertTrue(runner._complete_record(record, config, spec, names))
            for mutate in (lambda r: r["tasks"].pop(),
                           lambda r: r["tasks"][0]["search"].update(candidates=True),
                           lambda r: r["tasks"][0].update(verification=None),
                           lambda r: r["tasks"][0]["search"].pop("evaluator_calls"),
                           lambda r: r["tasks"][0]["search"].update(seed=True),
                           lambda r: r["work"].update(candidates=0),
                           lambda r: r["work"].update(verification_hidden_example_evaluations=0),
                           lambda r: r["tasks"][0]["verification"]["cost"].update(hidden_example_evaluations=0),
                           lambda r: r.update(seed=True)):
                corrupted = copy.deepcopy(record)
                mutate(corrupted)
                self.assertFalse(runner._complete_record(corrupted, config, spec, names))
            event = {"results": {key: {"result": {"status": "complete", "tasks_completed": 36}}},
                     "reason": None, "started": [key], "observed_cpu": {}, "elapsed_wall": {}}
            self.assertEqual(runner._condition_summary(key, event, config, names, folder)["status"], "complete")
            event["reason"] = "aggregate CPU ceiling reached"
            self.assertEqual(runner._condition_summary(key, event, config, names, folder)["status"], "partial")

    def test_parent_runs_registered_order_under_one_budget_and_never_claims_rsi(self):
        tasks = self.tasks(36)
        names, seen, budgets = [task.name for task in tasks], [], []
        source = self.source(tasks)
        with tempfile.TemporaryDirectory() as folder:
            def phase(kind, keys, output, config, budget, **options):
                key = keys[0]
                seen.append(key)
                budgets.append(budget)
                self.assertEqual(kind, "coordinate_diagnostic")
                self.assertEqual(options["workers"], 1)
                result = runner.run_condition(tasks, source, key,
                    Path(output) / f"{key}.checkpoint.json", config,
                    kernels={"population": self.solver(), "coordinates": self.solver()})
                return {"results": {key: {"result": result}}, "reason": None, "started": [key],
                        "observed_cpu": {key: 1}, "elapsed_wall": {key: 1}}
            with patch.object(runner, "CPUController", Budget), patch.object(runner, "_run_phase", phase), \
                    patch.object(runner, "training_names", return_value=names):
                summary = runner.run_diagnostic("synthetic-source.json", folder)
            self.assertEqual(seen, list(runner.B64_ORDER) + ["cold_population_B640", "cold_coordinates_B640"])
            self.assertEqual(len({id(budget) for budget in budgets}), 1)
            self.assertEqual(summary["status"], "complete")
            self.assertFalse(summary["rsi_success"])
            self.assertEqual(len(summary["cycle_report"]), 11)
            self.assertEqual(summary["b640_selection"]["memory"], "cold")

    def test_aggregate_exhaustion_leaves_unstarted_conditions_unknown(self):
        class Exhausted(Budget):
            def spent(self):
                return 600

            def exhausted(self):
                return True

        with tempfile.TemporaryDirectory() as folder, patch.object(runner, "CPUController", Exhausted), \
                patch.object(runner, "training_names", return_value=[task.name for task in self.tasks(36)]), \
                patch.object(runner, "_run_phase") as phase:
            summary = runner.run_diagnostic("synthetic-source.json.gz", folder)
            phase.assert_not_called()
            self.assertEqual(summary["status"], "partial")
            self.assertTrue(all(row["status"] == "unrun" and row["work"] == "UNKNOWN"
                                for row in summary["conditions"].values()))
            self.assertFalse(summary["rsi_success"])


if __name__ == "__main__":
    unittest.main()
