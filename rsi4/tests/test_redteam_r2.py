"""Red-team R2, exposure (Phase 0): every pool record is inspected.

Pass condition: no record is in FRESH-1, FRESH-2 or COMPOSE-24, and no name is
in RSI-2's corpus. Stages and pools are pairwise disjoint. The final-test pool
shows zero draws.
"""
from itertools import combinations
import json
import os
from pathlib import Path
import unittest

from rsi3.fresh import PUBLIC, components, to_task

from rsi4.judge import ledger, pools, registry

SOURCE = os.environ.get("RSI4_LIST_TASKS2")


def _all_sets():
    sets = {pool: pools.load_records(pool) for pool in pools.pool_names()}
    stages = json.loads(registry.STAGE_TRAIN_FILE.read_text(encoding="utf-8"))["stages"]
    for stage, records in stages.items():
        sets[f"stage_train_{stage}"] = records
    return sets


class ExposureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sets = _all_sets()
        cls.records = [r for records in cls.sets.values() for r in records]
        cls.fresh, cls.corpus = pools.exclusion_sets()

    def test_sizes_are_the_registered_ones(self):
        sizes = {name: len(records) for name, records in self.sets.items()}
        expected = {"probe": 60, "final_test_2": 200, "final_test_3": 100,
                    **{f"stage_eval_S{i}": 100 for i in (1, 2, 3)},
                    **{f"stage_train_S{i}": 36 for i in (1, 2, 3)},
                    **{f"selection_r{r}": 100 for r in (1, 2, 3)},
                    **{f"confirmation_r{r}": 200 for r in (1, 2, 3)}}
        self.assertEqual(sizes, expected)

    def test_no_record_is_in_fresh_or_the_corpus(self):
        for record in self.records:
            self.assertNotIn(record["name"], self.fresh)
            self.assertNotIn(record["name"], self.corpus)
            self.assertNotIn(pools.pipeline_style_name(record), self.corpus)
            self.assertGreaterEqual(len(components(record["name"])), 2)

    def test_no_record_is_a_compose24_task(self):
        for record in self.records:
            self.assertFalse(pools.matches_compose24(record), record["name"])

    def test_pairwise_disjoint_by_name(self):
        names = {k: {r["name"] for r in v} for k, v in self.sets.items()}
        for name, records in self.sets.items():
            self.assertEqual(len(names[name]), len(records), f"{name} repeats a name")
        for a, b in combinations(sorted(names), 2):
            self.assertFalse(names[a] & names[b], f"{a} and {b} share a task")

    def test_shapes_and_stage_groups(self):
        seed = registry.judge_seed()
        for name, records in self.sets.items():
            for record in records:
                shape = pools.shape_of(record)
                self.assertIsNotNone(shape)
                stages, routines = shape
                self.assertEqual(stages, 3 if name == "final_test_3" else 2)
                if name.startswith(("stage_train_S", "stage_eval_S")):
                    group = int(name[-1]) - 1
                    self.assertTrue(all(pools.group_of(r, seed) == group for r in routines))

    def test_public_hidden_split(self):
        for record in self.records:
            task = to_task(record)
            self.assertEqual(len(task.examples), PUBLIC)
            self.assertTrue(task.hidden)

    def test_final_test_shows_zero_draws(self):
        for path in [ledger.CANONICAL_LEDGER, *registry.PACKAGE_DIR.glob("runs/**/judge_log.jsonl")]:
            for entry in ledger.entries(path):
                self.assertNotEqual(entry.get("request_op"), "final_test")
                result = entry.get("result") or {}
                self.assertFalse(str(result.get("pool", "")).startswith("final_test"))

    def test_manifest_covers_every_pool(self):
        lines = registry.MANIFEST_FILE.read_text().splitlines()
        covered = {line.split("  ", 1)[1] for line in lines}
        for pool in pools.pool_names():
            self.assertIn(f"pools/{pool}.json", covered)
        self.assertIn("../data/stage_train.json", covered)
        self.assertIn("seed.json", covered)

    @unittest.skipUnless(SOURCE and Path(SOURCE).exists(),
                         "set RSI4_LIST_TASKS2 to DreamCoder's list_tasks2.json at cb0e63f")
    def test_rules_rebuild_every_file(self):
        self.assertEqual(registry.file_sha256(Path(SOURCE)), pools.SOURCE_SHA256)
        built = pools.build(json.loads(Path(SOURCE).read_text()), registry.judge_seed())
        for pool in pools.pool_names():
            self.assertEqual(built["pools"][pool], pools.load_records(pool), pool)
        stages = json.loads(registry.STAGE_TRAIN_FILE.read_text())["stages"]
        self.assertEqual(built["stage_train"], stages)


if __name__ == "__main__":
    unittest.main()
