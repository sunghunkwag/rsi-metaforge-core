"""Regression tests for the opt-in public-behavior novelty pilot."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from rsi4 import novelty


class PublicTask:
    def __init__(self, name, outputs):
        self.name = name
        self.examples = tuple(
            ((([1, 2, 3, 4],), output) for output in outputs))

    def __getattr__(self, name):
        raise AssertionError("Unexpected access to a nonpublic field: " + name)


class NoveltyTests(TestCase):
    def test_descriptor_uses_only_public_behavior(self):
        a = PublicTask("a", [[4, 3, 2, 1], [1, 3]])
        b = PublicTask("different_name", [[4, 3, 2, 1], [1, 3]])
        c = PublicTask("c", [[1, 2, 3, 4], [1, 2]])
        self.assertEqual(novelty.behavior_descriptor(a),
                         novelty.behavior_descriptor(b))
        self.assertNotEqual(novelty.behavior_descriptor(a),
                            novelty.behavior_descriptor(c))
        self.assertTrue(all(-1.0 <= x <= 1.0
                            for x in novelty.behavior_descriptor(a)))

    def test_knn_uses_population_and_archive(self):
        self.assertEqual(novelty.novelty_scores([(0.0,)], k=3), [0.0])
        self.assertEqual(novelty.novelty_scores(
            [(0.0,), (0.0,), (1.0,)], k=1), [0.0, 0.0, 1.0])
        self.assertEqual(novelty.novelty_scores(
            [(0.0,), (1.0,)], [(0.0,)], k=1), [0.0, 1.0])
        with self.assertRaises(ValueError):
            novelty.novelty_scores([(1,)], k=0)

    def test_archive_is_deterministic_deduplicated_and_bounded(self):
        archive = novelty.NoveltyArchive(capacity=2)
        self.assertTrue(archive.add((0, 1)))
        self.assertFalse(archive.add((0, 1)))
        archive.add((1, 0))
        archive.add((1, 1))
        self.assertEqual(archive.items, [(1.0, 0.0), (1.0, 1.0)])
        with self.assertRaises(ValueError):
            archive.add((0, 1, 2))

    def test_runtime_keeps_existing_verifier_backed_solutions_only(self):
        candidates = [
            PublicTask("a", [[1, 2], [3, 4]]),
            PublicTask("b", [[4, 3], [2, 1]]),
            PublicTask("c", [[2, 2], [2, 2]]),
        ]
        runtime = novelty.NoveltyCurriculumRuntime.__new__(
            novelty.NoveltyCurriculumRuntime)
        runtime.config = {
            "curriculum": {"pool": 3, "count": 3, "solve": 2, "hard_chunk": 4},
            "novelty": {"archive": 4, "k": 2},
        }
        solved = {}
        def pretend_solve(self, chosen, generation):
            self.assertEqual(generation, 1)
            self.assertEqual(len(chosen), 2)
            solved["selected"] = [t.name for t in chosen]
            return {chosen[0].name: "verified-program"}, 7

        with patch.object(novelty, "imagine", return_value=candidates), \
             patch.object(novelty, "select_hard", return_value=(candidates, 9)), \
             patch.object(novelty, "solve", side_effect=lambda r, ts, g:
                          pretend_solve(self, ts, g)), \
             patch.object(novelty, "pretty", return_value="verified-program"):
            report = runtime._curriculum(1)
        self.assertEqual(report["imagined"], 3)
        self.assertEqual(report["hard_candidates"], 3)
        self.assertEqual(report["hard"], 2)
        self.assertEqual(report["solved"], 1)
        self.assertEqual(report["curriculum_evaluations"], 16)
        self.assertEqual(set(runtime.curriculum_pool.items), {solved["selected"][0]})
        self.assertEqual(report["novelty_archive"], 2)

    def test_zero_candidate_generation(self):
        runtime = novelty.NoveltyCurriculumRuntime.__new__(
            novelty.NoveltyCurriculumRuntime)
        runtime.config = {"curriculum": {"count": 0, "solve": 2, "pool": 2}}
        with patch.object(novelty, "imagine", return_value=[]), \
             patch.object(novelty, "select_hard", return_value=([], 0)), \
             patch.object(novelty, "solve", return_value=({}, 0)):
            result = runtime._curriculum(1)
        self.assertEqual(result["novelty_mean"], 0.0)
        self.assertEqual(result["solved"], 0)


if __name__ == "__main__":
    main()
