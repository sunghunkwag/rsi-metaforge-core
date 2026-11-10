"""Tests for non-audit domain-policy engineering preflight."""
import hashlib
import unittest
from research import domain_policy_dev_20261110 as m


class DomainPolicyDevTests(unittest.TestCase):
    def test_manifest_uses_train_only_and_pinned_blobs(self):
        manifest = m.validate_manifest()
        self.assertEqual(len(manifest["task_ids"]), 29)
        self.assertEqual(manifest["source_blob_sha"],
                         "2816d1ee51ff2f523704c1930d8736eb99711036")

    def test_candidate_pool_unique(self):
        self.assertEqual(len(m.POOL), len(set(m.POOL)))

    def test_task_semantics(self):
        self.assertEqual(m.run_op(m.task_op("prepend-k with k=4"), [1, 2]), [4, 1, 2])
        self.assertEqual(m.run_op(m.task_op("slice-k-n with k=2 and n=4"),
                                  [1, 2, 3, 4, 5]), [2, 3, 4, 5])
        self.assertEqual(m.run_op(m.task_op("reverse"), [1, 2, 3]), [3, 2, 1])

    def test_shifted_examples_have_varied_lengths(self):
        public, shifted = m.examples("reverse")
        self.assertEqual((len(public), len(shifted)), (8, 32))
        self.assertGreaterEqual(len({len(x) for x in shifted}), 24)
        self.assertEqual(m.examples("reverse"), (public, shifted))

    def test_task_split_deterministic(self):
        tasks = m.validate_manifest()["task_ids"]
        evals = [t for t in tasks if hashlib.sha256(t.encode()).digest()[0] % 3 == 0]
        self.assertGreater(len(evals), 0)
        self.assertLess(len(evals), len(tasks))

    def test_choose_unique_and_deterministic(self):
        pool = [i for i, op in enumerate(m.POOL) if op[3] == "listint"]
        a = m.choose(pool, [], "preserve", 3, 1, 0, 2, 0, "frozen_mutation")
        b = m.choose(pool, [], "preserve", 3, 1, 0, 2, 0, "frozen_mutation")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)
        self.assertEqual(len(set(a)), 16)

    def test_negative_feedback_is_distinct(self):
        pool = [i for i, op in enumerate(m.POOL) if op[3] == "listint"]
        episodes = [("preserve", "reverse", True)] * 10
        good = m.choose(pool, episodes, "preserve", 3, 3, 1, 2, 0, "persistent_domain")
        bad = m.choose(pool, episodes, "preserve", 3, 3, 1, 2, 0, "inverted_feedback")
        self.assertNotEqual(good, bad)


if __name__ == "__main__":
    unittest.main()
