"""Opt-in exact rejection tests: preserve behaviorally distinct candidates.

These tests exercise receipt-anchored structural identity, not any claim of
held-out performance. The legacy signature filter remains the default.
"""
import unittest
from unittest.mock import patch

from rsi2.corpus import load_train
from rsi2.terms import Int, Lam, Prim, apply
from rsi3.integrator import BindingIntegrator
from rsi3.memory import ContaminationError, EpisodicMemory
from rsi3.verifier import FrozenVerifier, Receipt, public_view, term_digest


class ExactRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = load_train()
        cls.task = next(t for t in cls.train if "list" in str(t.request_type))
        cls.public = [public_view(t) for t in cls.train]

    def setUp(self):
        self.verifier = FrozenVerifier(self.train)
        self.memory = EpisodicMemory(self.verifier)
        # This malformed/incomplete term fails the selected list task's
        # frozen hidden verifier, as in the existing component regression.
        self.rejected = apply(Prim("map"), apply(
            Prim("add"), apply(Prim("length"), Prim("nil"))))
        self.distinct = Lam(self.task.request_type.args[0], Int(-123456))
        self.assertNotEqual(term_digest(self.rejected), term_digest(self.distinct))
        self.receipt = self.verifier.verify(
            self.task.name, self.rejected, {}, generation=1)
        self.assertFalse(self.receipt.verdict)

    def test_exact_skip_does_not_conflate_same_probe_signature(self):
        integrator = BindingIntegrator(self.public, skip_mode="exact")
        self.assertIsNone(integrator.skip_callback(self.task.name, {}, self.memory))
        # Force a genuine hash collision in the finite behavioral signature.
        # The exact mode must not use that signature for its skip decision.
        with patch.object(integrator, "signature", return_value="collision") as signature:
            integrator.bind_rejected(
                self.task.name, self.rejected, {}, self.receipt, self.memory)
            skip = integrator.skip_callback(self.task.name, {}, self.memory)
            self.assertTrue(skip(self.rejected))
            self.assertFalse(skip(self.distinct))
            self.assertEqual(signature.call_count, 1)  # only binding, not skip
        self.assertEqual(integrator.skipped_equivalent, 1)
        self.assertEqual(integrator.probe_evaluations, 0)
        self.assertTrue(self.memory.is_rejected_program(
            self.task.name, term_digest(self.rejected)))
        self.assertFalse(self.memory.is_rejected_program(
            self.task.name, term_digest(self.distinct)))

    def test_legacy_mode_reproduces_signature_collision(self):
        integrator = BindingIntegrator(self.public)  # historic default
        with patch.object(integrator, "signature", return_value="collision"):
            integrator.bind_rejected(
                self.task.name, self.rejected, {}, self.receipt, self.memory)
            skip = integrator.skip_callback(self.task.name, {}, self.memory)
            self.assertTrue(skip(self.distinct))
        self.assertEqual(integrator.skip_mode, "signature")

    def test_receipt_guard_blocks_forged_rejections(self):
        forged = Receipt(
            99999, self.task.name, 1, term_digest(self.distinct), False)
        with self.assertRaises(ContaminationError):
            self.memory.reject_signature(self.task.name, "collision", forged)
        self.assertEqual(self.memory.rejected_digests, {})

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            BindingIntegrator(self.public, skip_mode="guess")

    def test_exact_memory_is_per_task(self):
        integrator = BindingIntegrator(self.public, skip_mode="exact")
        integrator.bind_rejected(
            self.task.name, self.rejected, {}, self.receipt, self.memory)
        other = next(t for t in self.public if t.name != self.task.name)
        self.assertIsNone(integrator.skip_callback(other.name, {}, self.memory))


if __name__ == "__main__":
    unittest.main()
