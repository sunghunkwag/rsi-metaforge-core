"""FRESH partitions: frozen external tasks, disjoint from RSI-2's corpus by name."""
import json
from pathlib import Path
import unittest

from rsi3.fresh import (CORPUS, DATA, PUBLIC, SOURCE_COMMIT, build, components,
                        corpus_style_name, load_fresh)

SOURCE = Path(__file__).resolve().parents[3] / "ellisk42" / "ec" / "data" / "list_tasks2.json"


class FreshTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DATA.read_text(encoding="utf-8"))
        self.corpus = {t["name"] for t in json.loads(CORPUS.read_text(encoding="utf-8"))}

    def test_partitions_are_fixed(self):
        self.assertEqual(self.data["source"]["commit"], SOURCE_COMMIT)
        self.assertEqual((len(self.data["fresh1"]), len(self.data["fresh2"])), (33, 100))
        self.assertEqual(self.data["rules"]["pipeline_pool"], 5835)

    def test_no_task_is_a_corpus_task(self):
        for record in self.data["fresh1"]:
            (routine, arguments), = components(record["name"])
            self.assertNotIn(corpus_style_name(routine, arguments), self.corpus)
        for record in self.data["fresh2"]:
            self.assertEqual(len(components(record["name"])), 2)
        names = [r["name"] for r in self.data["fresh1"] + self.data["fresh2"]]
        self.assertFalse(set(names) & self.corpus)
        self.assertEqual(len(names), len(set(names)))

    def test_public_and_hidden_examples_are_disjoint(self):
        for partition in ("fresh1", "fresh2"):
            for task in load_fresh(partition):
                self.assertEqual(len(task.examples), PUBLIC)
                self.assertTrue(task.hidden)
                public = {json.dumps(list(x)) for x, _ in task.examples}
                self.assertFalse(public & {json.dumps(list(x)) for x, _ in task.hidden})

    @unittest.skipUnless(SOURCE.exists(), "DreamCoder's list_tasks2.json is not checked out")
    def test_rules_rebuild_the_committed_records(self):
        built = build(json.loads(SOURCE.read_text(encoding="utf-8")), self.corpus)
        self.assertEqual(built["fresh1"], self.data["fresh1"])
        self.assertEqual(built["fresh2"], self.data["fresh2"])


if __name__ == "__main__":
    unittest.main()
