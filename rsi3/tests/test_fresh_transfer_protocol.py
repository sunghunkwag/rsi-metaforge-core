"""Protocol-level checks for FRESH-COMPOSE-20261031-V1.

These tests check deterministic construction and isolation, NEVER solving or
scoring the withheld benchmark, to prevent development-phase score peeking.
"""
import json
import unittest

from rsi3.research_fresh.suite import (
    BENCHMARK_ID, FAMILIES, PARAMETERS, HIDDEN_COUNT, PUBLIC_COUNT,
    frozen_records, load_frozen_tasks, suite_sha256,
)


class FreshHoldoutProtocolTests(unittest.TestCase):
    def test_fixed_family_count_and_no_duplicate_names(self):
        records = frozen_records()
        self.assertEqual(BENCHMARK_ID, "FRESH-COMPOSE-20261031-V1")
        self.assertEqual(len(FAMILIES), 4)
        self.assertEqual(len(PARAMETERS), 6)
        self.assertEqual(len(records), 24)
        self.assertEqual(len({r["name"] for r in records}), 24)
        self.assertTrue(all(r["name"].startswith("fresh20261031::") for r in records))

    def test_fixed_split_and_disjoint_input_sets(self):
        for record in frozen_records():
            public = record["examples"]
            hidden = record["hidden"]
            self.assertEqual(len(public), PUBLIC_COUNT)
            self.assertEqual(len(hidden), HIDDEN_COUNT)
            a = {json.dumps(x["inputs"]) for x in public}
            b = {json.dumps(x["inputs"]) for x in hidden}
            self.assertEqual(len(a), PUBLIC_COUNT)
            self.assertEqual(len(b), HIDDEN_COUNT)
            self.assertFalse(a & b)

    def test_digest_and_parser_deterministic(self):
        self.assertEqual(suite_sha256(), suite_sha256())
        tasks = load_frozen_tasks()
        self.assertEqual(len(tasks), 24)
        self.assertEqual(len({t.name for t in tasks}), 24)
        self.assertTrue(all(len(t.hidden) == HIDDEN_COUNT for t in tasks))


if __name__ == "__main__":
    unittest.main()
