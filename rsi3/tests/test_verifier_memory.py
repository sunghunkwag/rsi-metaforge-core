import dataclasses
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.search import solve
from rsi2.terms import Int, Lam

from rsi3.memory import ContaminationError, Episode, EpisodicMemory, SolutionRecord
from rsi3.value_model import DIM
from rsi3.verifier import FrozenVerifier, QueryLimitExceeded, Receipt, public_view, term_digest


def _episode(task, outcome, digest=None, receipt_id=None, generation=1):
    return Episode(generation, task, "prior", "prior", "fp", 0, 8, False, outcome, digest,
                   tuple([0.0] * DIM), 0.0, receipt_id)


class VerifierAndMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = load_train()
        cls.task = cls.train[0]

    def setUp(self):
        self.verifier = FrozenVerifier(self.train)
        self.memory = EpisodicMemory(self.verifier)
        # A program that certainly fails: the constant zero function.
        self.wrong = Lam(self.task.request_type.args[0], Int(0))

    def test_public_view_strips_hidden_examples(self):
        view = public_view(self.task)
        self.assertEqual(view.hidden, ())
        self.assertEqual(view.examples, self.task.examples)

    def test_one_query_per_task_per_generation(self):
        self.verifier.verify(self.task.name, self.wrong, {}, generation=1)
        with self.assertRaises(QueryLimitExceeded):
            self.verifier.verify(self.task.name, self.wrong, {}, generation=1)
        self.verifier.verify(self.task.name, self.wrong, {}, generation=2)
        self.assertEqual(self.verifier.queries, 2)

    def test_self_reported_success_is_rejected(self):
        """A planted self-grading pathway claims success without a verdict."""
        digest = term_digest(self.wrong)
        with self.assertRaises(ContaminationError):
            self.memory.record(_episode(self.task.name, "verified", digest))
        receipt = self.verifier.verify(self.task.name, self.wrong, {}, generation=1)
        self.assertFalse(receipt.verdict)
        with self.assertRaises(ContaminationError):
            self.memory.record(_episode(self.task.name, "verified", digest, receipt.receipt_id),
                               receipt)
        self.assertEqual(self.memory.episodes, [])

    def test_forged_and_mismatched_receipts_are_rejected(self):
        digest = term_digest(self.wrong)
        forged = Receipt(999, self.task.name, 1, digest, True)
        with self.assertRaises(ContaminationError):
            self.memory.record(_episode(self.task.name, "verified", digest, 999), forged)
        genuine = self.verifier.verify(self.task.name, self.wrong, {}, generation=1)
        tampered = dataclasses.replace(genuine, verdict=True)
        with self.assertRaises(ContaminationError):
            self.memory.record(_episode(self.task.name, "verified", digest, genuine.receipt_id),
                               tampered)
        with self.assertRaises(ContaminationError):
            self.memory.record(_episode(self.task.name, "rejected", "other-digest",
                                        genuine.receipt_id), genuine)
        self.memory.record(_episode(self.task.name, "rejected", digest, genuine.receipt_id), genuine)
        self.assertEqual(len(self.memory.episodes), 1)
        self.assertEqual(self.memory.label(self.memory.episodes[0]), 0)

    def test_solution_store_requires_positive_verdict(self):
        receipt = self.verifier.verify(self.task.name, self.wrong, {}, generation=1)
        record = SolutionRecord(self.task.name, receipt.digest, "prior", "prior", "designer", 1,
                                receipt.receipt_id)
        with self.assertRaises(ContaminationError):
            self.memory.remember_solution(record, receipt)
        with self.assertRaises(ContaminationError):
            self.memory.reject_signature("another-task", "sig", receipt)

    def test_verified_label_from_genuine_success(self):
        for task in sorted(self.train, key=lambda t: t.name):
            found = solve(task.examples, task.request_type, 64, Grammar(),
                          step_budget=2000, max_size=12, max_expansions=20000)
            if found.term is None:
                continue
            receipt = self.verifier.verify(task.name, found.term, {}, generation=1)
            if not receipt.verdict:
                continue
            self.memory.record(_episode(task.name, "verified", receipt.digest,
                                        receipt.receipt_id), receipt)
            record = SolutionRecord(task.name, receipt.digest, "prior", "prior", "designer", 1,
                                    receipt.receipt_id)
            self.memory.remember_solution(record, receipt)
            self.assertEqual(self.memory.label(self.memory.episodes[0]), 1)
            self.assertIn(task.name, self.memory.solutions)
            return
        self.fail("no TRAIN task verified at budget 64")

    def test_replay_modes(self):
        for generation in (1, 1, 2):
            self.memory.record(_episode(self.task.name, "none", generation=generation))
        self.assertEqual(len(self.memory.replay("replay", 2)), 3)
        self.assertEqual(len(self.memory.replay("latest", 2)), 1)
        self.assertEqual(self.memory.slot_windows[(self.task.name, "prior")], 3)


if __name__ == "__main__":
    unittest.main()
