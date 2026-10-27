"""Failure memory: public failures carried across grammar changes and pathways."""
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.search import solve

from rsi3.loop import ArmConfig, Runtime
from rsi3.memory import FailureMemory
from rsi3.resumable import ResumableSearch

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}
CONFIG = {"B_wake": 12, "B_eval": 12, "dreams": 4, "search": SEARCH,
          "controller": {"chunk": 6, "exploration": 0.3, "analog_neighbors": 2}}
SHIFTED = Grammar(weights={"map": 4.0, "fold": 3.0, "add": 2.0})


def _tasks():
    train = sorted(load_train(), key=lambda t: t.name)
    found = [t for t in train
             if solve(t.examples, t.request_type, 96, SHIFTED, **SEARCH).term is not None]
    unsolved = [t for t in train if t not in found]
    return found, unsolved


class FailureMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.found, cls.unsolved = _tasks()

    def test_failures_are_skipped_after_a_grammar_change_without_budget(self):
        task = self.unsolved[0]
        failures = FailureMemory().for_task(task.name)
        first = ResumableSearch(task.examples, task.request_type, Grammar(), **SEARCH,
                                known_failures=failures)
        first.run(40)
        self.assertEqual(len(failures), 40)
        before = set(failures)
        second = ResumableSearch(task.examples, task.request_type, SHIFTED, **SEARCH,
                                 known_failures=failures)
        result = second.run(40)
        self.assertEqual(result.evaluated, 40)
        self.assertGreater(result.skipped_known, 0, "the two orders should overlap")
        newly = failures - before
        self.assertEqual(len(newly), 40, "every charged candidate is a new program")
        self.assertEqual(second.position, 40 + result.skipped_known)

    def test_same_solution_as_plain_search_with_fewer_evaluations(self):
        """Known failures never match, so skipping them cannot change the first match."""
        self.assertTrue(self.found, "need at least one task solvable under the shifted grammar")
        total_skipped = 0
        for task in self.found[:3]:
            plain = solve(task.examples, task.request_type, 96, SHIFTED, **SEARCH)
            failures = FailureMemory().for_task(task.name)
            ResumableSearch(task.examples, task.request_type, Grammar(), **SEARCH,
                            known_failures=failures).run(min(30, plain.candidates - 1))
            carried = ResumableSearch(task.examples, task.request_type, SHIFTED, **SEARCH,
                                      known_failures=failures)
            result = carried.run(96)
            self.assertEqual(result.term, plain.term, task.name)
            self.assertEqual(result.evaluated + result.skipped_known, plain.candidates, task.name)
            self.assertLessEqual(result.evaluated, plain.candidates, task.name)
            total_skipped += result.skipped_known
        self.assertGreater(total_skipped, 0, "the comparison must exercise at least one skip")

    def test_off_by_default_and_runtime_wiring(self):
        tasks = self.found[:2] + self.unsolved[:4]
        off = Runtime(11, tasks, ArmConfig("off"), CONFIG)
        self.assertIsNone(off.failures)
        record = off.generation()
        self.assertEqual(record["wake"]["skipped_known"], 0)
        self.assertEqual(record["failure_memory"]["programs"], 0)
        on = Runtime(11, tasks, ArmConfig("on", failure_memory=True), CONFIG)
        records = [on.generation() for _ in range(2)]
        self.assertGreater(records[-1]["failure_memory"]["programs"], 0)
        for record in records:
            self.assertLessEqual(record["wake"]["spent"], CONFIG["B_wake"] * len(tasks))
        # The set never holds a program that matched: solved tasks' solutions are absent.
        for name, term in on.state.solutions.items():
            self.assertNotIn(term, on.failures.for_task(name))


if __name__ == "__main__":
    unittest.main()
