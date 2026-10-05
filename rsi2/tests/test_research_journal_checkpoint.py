import copy
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.corpus import Task
from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.research.journal_checkpoint import (
    JournalCheckpoint, JournalCorruption, reconstruct,
)
from rsi2.research.recursive_bootstrap import atomic_write, REGISTERED_CONFIG, run_arm
from rsi2.types import Arrow, INT


@dataclass
class Payload:
    term: object
    candidates: int
    trials: tuple


class TraversalCounter(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.traversals = 0

    def items(self):
        self.traversals += 1
        return super().items()


class JournalCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.term = next(enumerate_programs(Arrow(INT, INT), Grammar(), max_size=12,
                                          max_expansions=20000)).term

    def search(self, number=0, tracked=False):
        value = {
            "term": self.term, "candidates": 16 + number,
            "logical_evaluations": 16 + number, "evaluation_steps": 500 + number,
            "expansions": 200 + number, "normalization_steps": 30 + number,
            "trials": [{"term": self.term, "raw_term": self.term,
                        "canonical_term": self.term, "index": index,
                        "parent_record": f"seed11:FULL:g{number}:task{index}",
                        "mutation_path": [0, index], "proved": False}
                       for index in range(12)],
        }
        return TraversalCounter(value) if tracked else value

    def row(self, generation, searches):
        return {"generation": generation, "wake": {
            "status": "complete", "records": [
                {"name": f"task{index}", "search": search, "solved": index == 0,
                 "verification": {"passed": index == 0, "cost": {"evaluator_steps": 33}}}
                for index, search in enumerate(searches)]},
            "work": {"task_candidates": sum(s["candidates"] for s in searches),
                     "verification_steps": 33},
            "state": {"heuristic": self.term, "library": {},
                      "acceptance_records": {"task0": {"id": f"g{generation}:task0"}}}}

    def expected(self, path, value):
        atomic_write(path, value)
        with path.open() as stream:
            return json.load(stream)

    def test_complete_record_matches_original_serializer_values_and_key_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            first, second = self.row(0, [self.search()]), self.row(1, [self.search(1)])
            record = {"seed": 11, "arm": "FULL", "status": "complete",
                      "generations": [first, second], "work": {"task_candidates": 33},
                      "final_state": {"raw_solutions": {"t": self.term}},
                      "candidate_evaluations_scope": "exact_completed_operations"}
            original = copy.deepcopy(record)
            expected = self.expected(folder / "reference.json", record)
            with JournalCheckpoint(folder / "record.json") as writer:
                writer(record)
                recovered = reconstruct(writer.path)
                self.assertEqual(recovered.record, expected)
                self.assertEqual(json.dumps(recovered.record), json.dumps(expected))
                self.assertFalse(recovered.interrupted)
                self.assertEqual(writer.metrics["archived_searches"], 2)
                self.assertEqual(writer.metrics["archived_generations"], 2)
                self.assertGreaterEqual(writer.metrics["cpu_seconds"], 0)
                self.assertGreaterEqual(recovered.cpu_seconds, 0)
            self.assertEqual(record, original)

    def test_live_partial_row_changes_without_rewriting_search_or_completed_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            first_search, live_search = self.search(tracked=True), self.search(1, tracked=True)
            completed = TraversalCounter(self.row(0, [first_search]))
            current = self.row(1, [live_search])
            current["wake"]["status"] = "running"
            current["wake"]["in_progress"] = {"name": "task0", "stage": "independent_verification"}
            record = {"status": "running", "generations": [completed], "in_progress": current,
                      "work": {"task_candidates": 33, "verification_steps": 0},
                      "candidate_evaluations_scope": "completed_operations_lower_bound"}
            with JournalCheckpoint(folder / "record.json") as writer:
                writer(record)
                first_bytes = writer.journal_path.stat().st_size
                self.assertEqual((first_search.traversals, live_search.traversals, completed.traversals), (1, 1, 1))
                current["wake"]["records"][0]["verification"]["passed"] = True
                current["wake"]["in_progress"]["stage"] = "next_public_search"
                record["work"]["verification_steps"] = 33
                writer(record)
                self.assertEqual((first_search.traversals, live_search.traversals, completed.traversals), (1, 1, 1))
                self.assertEqual(writer.journal_path.stat().st_size, first_bytes)
                expected = self.expected(folder / "reference.json", record)
                self.assertEqual(reconstruct(writer.path).record, expected)
                current["wake"].pop("in_progress")
                current["wake"]["status"] = "complete"
                record["generations"].append(current)
                record.pop("in_progress")
                record["status"] = "partial"
                writer(record)
                self.assertEqual(writer.metrics["archived_searches"], 2)
                self.assertEqual(writer.metrics["archived_generations"], 2)
                self.assertEqual(reconstruct(writer.path).record,
                                 self.expected(folder / "reference.json", record))
                self.assertEqual([r["generation"] for r in reconstruct(writer.path).record["generations"]], [0, 1])

    def test_dataclasses_tuples_nonstring_keys_and_reserved_markers_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            record = {"status": "partial", "generations": [],
                      "search": {"payload": Payload(self.term, 7, (1, {"@rsi2-journal-ref": 9}))},
                      "markers": {"@rsi2-journal-dict": [["x", 1]]},
                      "keys": {False: "false", 3: "integer", None: "none"}}
            with JournalCheckpoint(folder / "record.json") as writer:
                writer(record)
                self.assertEqual(reconstruct(writer.path).record,
                                 self.expected(folder / "reference.json", record))

    def test_uncommitted_complete_and_truncated_suffixes_keep_committed_prefix_as_lower_bound(self):
        for suffix in (b'{"sequence":99,"kind":"search","encoding":"json","value":{}}\n',
                       b'{"sequence":99,"kind":"search"'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                record = {"status": "complete", "rsi_success": True,
                          "generations": [self.row(0, [self.search()])],
                          "work": {"task_candidates": 16, "verification_steps": 33},
                          "candidate_evaluations_scope": "exact_completed_operations"}
                with JournalCheckpoint(folder / "record.json") as writer:
                    writer(record)
                    journal = writer.journal_path
                with journal.open("ab") as stream:
                    stream.write(suffix)
                recovered = reconstruct(folder / "record.json")
                self.assertTrue(recovered.interrupted)
                self.assertEqual(recovered.ignored_bytes, len(suffix))
                self.assertEqual(recovered.record["work"], record["work"])
                self.assertEqual(recovered.record["status"], "partial")
                self.assertFalse(recovered.record["rsi_success"])
                self.assertEqual(recovered.record["candidate_evaluations_scope"],
                                 "completed_operations_lower_bound")
                self.assertEqual(len(recovered.record["generations"]), 1)

    def test_truncated_committed_line_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            with JournalCheckpoint(path) as writer:
                writer({"status": "complete", "generations": [self.row(0, [self.search()])]})
                journal = writer.journal_path
            data = journal.read_bytes()
            journal.write_bytes(data[:-2])
            with self.assertRaises(JournalCorruption):
                reconstruct(path)
            journal.write_bytes(data[:-1] + b" ")
            with self.assertRaisesRegex(JournalCorruption, "truncated committed"):
                reconstruct(path)

    def test_failed_atomic_commit_rolls_back_new_objects_then_retry_preserves_exact_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            record = {"status": "running", "generations": [self.row(0, [self.search()])],
                      "work": {"task_candidates": 16}}
            with JournalCheckpoint(folder / "record.json") as writer:
                writer(record)
                original_root, original_journal = writer.path.read_bytes(), writer.journal_path.read_bytes()
                record["generations"].append(self.row(1, [self.search(1)]))
                record["work"]["task_candidates"] = 33
                record["status"] = "complete"
                with patch.object(writer, "_commit_root", side_effect=OSError("simulated interrupted commit")):
                    with self.assertRaises(OSError):
                        writer(record)
                self.assertEqual(writer.path.read_bytes(), original_root)
                self.assertEqual(writer.journal_path.read_bytes(), original_journal)
                self.assertEqual(reconstruct(writer.path).record["status"], "running")
                writer(record)
                self.assertEqual(reconstruct(writer.path).record,
                                 self.expected(folder / "reference.json", record))
                self.assertEqual(writer.metrics["failed_commits"], 1)
                self.assertEqual(writer.metrics["successful_commits"], 2)
                self.assertEqual(writer.metrics["archived_generations"], 2)
                self.assertEqual(writer.metrics["archived_searches"], 2)
                self.assertGreater(writer.metrics["journal_entries_written"], 4)

    def test_serialization_failure_never_publishes_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            with JournalCheckpoint(path) as writer:
                with self.assertRaises(ValueError):
                    writer({"status": "complete", "generations": [],
                            "search": {"value": float("nan")}})
                self.assertFalse(path.exists())
                self.assertEqual(writer.journal_path.stat().st_size, 0)
                writer({"status": "partial", "generations": [], "work": {"candidates": 0}})
                self.assertEqual(reconstruct(path).record["status"], "partial")

    def test_directory_sync_error_does_not_truncate_published_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            with JournalCheckpoint(path) as writer:
                record = {"status": "partial", "generations": [self.row(0, [self.search()])]}
                with patch.object(writer, "_sync_directory", side_effect=OSError("sync failure")):
                    with self.assertRaises(OSError):
                        writer(record)
                self.assertEqual(reconstruct(path).record["generations"][0]["generation"], 0)
                writer(record)
                self.assertEqual(writer.metrics["archived_searches"], 1)
                self.assertEqual(writer.metrics["archived_generations"], 1)

    def test_post_publication_error_retains_prefix_and_adopts_identity_cache(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            with JournalCheckpoint(path) as writer:
                record = {"status": "partial", "generations": [self.row(0, [self.search()])]}
                writer(record)
                record["generations"].append(self.row(1, [self.search(1)]))
                record["status"] = "complete"
                original_commit = writer._commit_root

                def publish_then_fail(manifest):
                    original_commit(manifest)
                    raise OSError("failure immediately after publication")

                with patch.object(writer, "_commit_root", side_effect=publish_then_fail):
                    with self.assertRaises(OSError):
                        writer(record)
                recovered = reconstruct(path)
                self.assertFalse(recovered.interrupted)
                self.assertEqual(recovered.record["status"], "complete")
                self.assertEqual([row["generation"] for row in recovered.record["generations"]], [0, 1])
                committed_bytes = writer.journal_path.stat().st_size
                writer(record)
                self.assertEqual(writer.journal_path.stat().st_size, committed_bytes)
                self.assertEqual(writer.metrics["archived_searches"], 2)
                self.assertEqual(writer.metrics["archived_generations"], 2)

    def test_reference_sequence_and_boolean_counts_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            with JournalCheckpoint(path) as writer:
                writer({"status": "complete", "generations": [self.row(0, [self.search()])]})
            manifest = json.loads(path.read_text())
            corrupted = copy.deepcopy(manifest)
            corrupted["objects"] = True
            path.write_text(json.dumps(corrupted))
            with self.assertRaises(JournalCorruption):
                reconstruct(path)
            corrupted = copy.deepcopy(manifest)
            corrupted["root"] = {"@rsi2-journal-ref": manifest["objects"] + 1}
            path.write_text(json.dumps(corrupted))
            with self.assertRaises(JournalCorruption):
                reconstruct(path)

    def test_actual_controller_callbacks_complete_and_partial_records_remain_exact(self):
        examples = tuple(((number,), evaluate(self.term, (number,)).value) for number in (-2, 0, 3))
        hidden = tuple(((number,), evaluate(self.term, (number,)).value) for number in (4, 9))
        tasks = [Task(f"synthetic{index}", Arrow(INT, INT), examples, hidden) for index in range(4)]
        config = copy.deepcopy(REGISTERED_CONFIG)
        config["dreams"] = 0

        def factory():
            def solve(public, request_type, budget, grammar, **_):
                evaluations = [evaluate(self.term, inputs, library=grammar.library) for inputs, _ in public]
                return {"term": self.term, "candidates": 1, "logical_evaluations": 1,
                        "evaluator_calls": len(evaluations),
                        "evaluation_steps": sum(result.steps for result in evaluations),
                        "expansions": 2, "trials": [{"term": self.term, "source": "own-enumerator"}]}
            return solve

        for arm, through_generation, status in (("BASE", 8, "complete"), ("FULL", 0, "partial")):
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                with JournalCheckpoint(folder / "record.json") as writer:
                    result = run_arm(tasks, 11, arm, config, kernel_factory=factory,
                                     through_generation=through_generation, checkpoint=writer)
                    recovered = reconstruct(writer.path)
                    self.assertEqual(result["status"], status)
                    self.assertEqual(recovered.record, self.expected(folder / "reference.json", result))
                    self.assertEqual(recovered.record["work"], result["work"])
                    self.assertEqual(recovered.record["work"]["task_candidates"], 4)
                    self.assertEqual(recovered.record["work"]["verification_examples"], 20)
                    self.assertEqual([row["generation"] for row in recovered.record["generations"]],
                                     list(range(through_generation + 1)))
                    self.assertGreater(writer.metrics["successful_commits"], 12)
                    self.assertEqual(writer.metrics["archived_generations"], through_generation + 1)

    def test_existing_checkpoint_refuses_overwrite_and_closed_writer_refuses_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            writer = JournalCheckpoint(path)
            writer({"status": "partial", "generations": []})
            writer.close()
            with self.assertRaises(ValueError):
                writer({"status": "complete", "generations": []})
            with self.assertRaises(FileExistsError):
                JournalCheckpoint(path)
            self.assertEqual(reconstruct(path).record["status"], "partial")


if __name__ == "__main__":
    unittest.main()
