"""RESERVE partitions: fixed, disjoint from every split, built by RSI-2's normalizer."""
import json
from pathlib import Path
import unittest

from rsi3.reserve import MANIFEST, RESEARCH, load_reserve, reserve_names


class ReserveTests(unittest.TestCase):
    def test_partitions_are_fixed_and_disjoint_from_every_split(self):
        names = reserve_names()
        self.assertEqual((len(names["near"]), len(names["far"])), (100, 12))
        manifest = json.loads(Path(MANIFEST).read_text(encoding="utf-8"))
        splits = set(manifest["train"]) | set(manifest["validation"]) | set(manifest["test"])
        self.assertFalse((set(names["near"]) | set(names["far"])) & splits)
        self.assertFalse(set(names["near"]) & set(names["far"]))

    def test_far_excludes_the_research_sets_families(self):
        research = json.loads(Path(RESEARCH).read_text(encoding="utf-8"))
        used = set(research["confirmation_families"]) | set(research["audit_families"])
        self.assertFalse({n.split(" with ", 1)[0] for n in reserve_names()["far"]} & used)

    def test_records_have_ten_public_examples_and_separate_hidden_ones(self):
        for task in load_reserve("far") + load_reserve("near")[:10]:
            self.assertEqual(len(task.examples), 10)
            self.assertTrue(task.hidden)


if __name__ == "__main__":
    unittest.main()
