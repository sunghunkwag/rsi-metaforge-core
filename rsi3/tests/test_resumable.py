import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.search import solve

from rsi3.resumable import ResumableSearch

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}


def _tasks():
    tasks = {task.name: task for task in load_train()}
    # Two tasks RSI-2 solves within 64 candidates and two it does not.
    solved = [name for name in sorted(tasks)
              if solve(tasks[name].examples, tasks[name].request_type, 64, Grammar(),
                       **SEARCH).term is not None][:2]
    unsolved = [name for name in sorted(tasks) if name not in solved][:2]
    return tasks, solved + unsolved


class ResumableSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tasks, cls.names = _tasks()

    def test_single_window_equals_rsi2_solve(self):
        grammar = Grammar()
        for name in self.names:
            task = self.tasks[name]
            reference = solve(task.examples, task.request_type, 48, grammar, **SEARCH)
            window = ResumableSearch(task.examples, task.request_type, grammar, **SEARCH).run(48)
            self.assertEqual(reference.term, window.term, name)
            self.assertEqual(reference.candidates, window.evaluated, name)

    def test_windows_compose_to_one_search(self):
        grammar = Grammar()
        for name in self.names:
            task = self.tasks[name]
            reference = solve(task.examples, task.request_type, 48, grammar, **SEARCH)
            search = ResumableSearch(task.examples, task.request_type, grammar, **SEARCH)
            first = search.run(20)
            if first.term is not None:
                self.assertEqual(first.term, reference.term)
                continue
            second = search.run(28)
            self.assertEqual(second.start, 20)
            self.assertEqual(second.term, reference.term, name)
            self.assertEqual(first.evaluated + second.evaluated, reference.candidates, name)

    def test_resumed_window_never_reevaluates_prefix(self):
        task = self.tasks[self.names[-1]]
        search = ResumableSearch(task.examples, task.request_type, Grammar(), **SEARCH)
        search.run(16)
        evaluated_terms = set(search._seen)
        search.run(16)
        self.assertEqual(len(search._seen), 32)
        self.assertTrue(evaluated_terms < search._seen)

    def test_skip_match_continues_past_the_match(self):
        name = self.names[0]
        task = self.tasks[name]
        first = ResumableSearch(task.examples, task.request_type, Grammar(), **SEARCH).run(64)
        self.assertIsNotNone(first.term)
        skipping = ResumableSearch(task.examples, task.request_type, Grammar(), **SEARCH)
        result = skipping.run(64, skip_match=lambda term: term == first.term)
        self.assertEqual(result.skipped_matches, 1)
        self.assertNotEqual(result.term, first.term)
        self.assertGreater(result.evaluated, first.evaluated)

    def test_exhaustion_is_reported(self):
        task = self.tasks[self.names[-1]]
        search = ResumableSearch(task.examples, task.request_type, Grammar(),
                                 step_budget=2000, max_size=3, max_expansions=20000)
        result = search.run(10_000)
        self.assertTrue(result.exhausted)
        self.assertTrue(search.exhausted)
        self.assertEqual(search.run(5).evaluated, 0)


if __name__ == "__main__":
    unittest.main()
