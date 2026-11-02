"""The latent field (bind/bundle/permute/similarity/analogy, ports, shuffling) and the mapper."""
import unittest

import numpy as np

from swarm import latent
from swarm.mapper import Mapper

D = 2048


class LatentTests(unittest.TestCase):
    def setUp(self):
        self.book = latent.Codebook(seed=7, d=D)

    def test_bind_is_self_inverse_and_bundle_keeps_members(self):
        a, b, c = self.book("a"), self.book("b"), self.book("c")
        self.assertTrue(np.array_equal(latent.bind(latent.bind(a, b), b), a))
        self.assertLess(abs(latent.similarity(a, b)), 0.1)
        bundled = latent.bundle([a, b, c])
        for member in (a, b, c):
            self.assertGreater(latent.similarity(bundled, member), 0.3)
        self.assertLess(abs(latent.similarity(bundled, self.book("d"))), 0.1)

    def test_permute_is_invertible_and_moves_vectors_away(self):
        a = self.book("a")
        self.assertTrue(np.array_equal(latent.permute(latent.permute(a, 3), -3), a))
        self.assertLess(abs(latent.similarity(a, latent.permute(a, 1))), 0.1)
        seq1 = latent.encode_sequence([self.book("x"), self.book("y")])
        seq2 = latent.encode_sequence([self.book("y"), self.book("x")])
        self.assertLess(latent.similarity(seq1, seq2), 0.3)

    def test_analogy(self):
        a, b, c = self.book("A"), self.book("B"), self.book("C")
        d = latent.analogy(a, b, c)
        relation = latent.bind(d, c)
        recovered, score = self.book.cleanup(latent.bind(relation, a))
        self.assertEqual(recovered, "B")
        self.assertGreater(score, 0.9)

    def test_codebook_is_deterministic_and_encodes_values(self):
        other = latent.Codebook(seed=7, d=D)
        self.assertTrue(np.array_equal(self.book("tok:map"), other("tok:map")))
        self.assertFalse(np.array_equal(self.book("tok:map"), latent.Codebook(seed=8, d=D)("tok:map")))
        examples = [{"inputs": [[1, 2]], "output": [2, 3]}, {"inputs": [[0]], "output": [1]}]
        signature = self.book.encode_examples(examples)
        self.assertEqual(signature.shape, (D,))
        similar = self.book.encode_examples(examples[:1] + [{"inputs": [[5]], "output": [6]}])
        unrelated = self.book.encode_examples([{"inputs": [[9, 9, 9]], "output": False},
                                               {"inputs": [[3]], "output": True}])
        self.assertGreater(latent.similarity(signature, similar), latent.similarity(signature, unrelated))

    def test_ports_write_own_region_and_read_the_other(self):
        field = latent.Field(d=D)
        breaker, builder = field.port("breaker"), field.port("builder")
        v = self.book("task")
        breaker.write(v, tag=1)
        self.assertEqual(len(builder.read()), 1)
        self.assertEqual(builder.read_tags(), [1])
        self.assertEqual(len(breaker.read()), 0)
        self.assertTrue(np.array_equal(builder.read()[0], v))
        with self.assertRaises(TypeError):
            breaker.write("not a vector")
        self.assertEqual(field.statistics()["breaker_items"], 1)

    def test_shuffled_field_reads_as_noise(self):
        field = latent.Field(d=D, shuffled=True, seed=3)
        breaker, builder = field.port("breaker"), field.port("builder")
        v = self.book("task")
        breaker.write(v)
        self.assertLess(abs(latent.similarity(builder.read()[0], v)), 0.1)

    def test_top_k(self):
        matrix = np.stack([self.book(f"m{i}") for i in range(5)])
        query = latent.bundle([self.book("m3"), self.book("noise")])
        self.assertEqual(latent.top_k(query, matrix, 1)[0][0], 3)


class MapperTests(unittest.TestCase):
    def test_paired_fit_aligns_two_codebooks_and_ignores_unpaired_events(self):
        tasks, programs = latent.Codebook(1, D), latent.Codebook(2, D)
        pairs = [(tasks(f"t{i}"), programs(f"p{i}")) for i in range(6)]
        mapper = Mapper(ridge=0.1)
        report = mapper.fit_from_events([{"task": a, "program": b} for a, b in pairs]
                                        + [{"task": tasks("t99"), "program": None},
                                           {"task": None, "program": programs("p99")}])
        self.assertEqual(report["pairs"], 6)
        self.assertLess(report["residual"], 0.5)
        matrix = np.stack([programs(f"p{i}") for i in range(6)])
        for i in range(6):
            predicted = Mapper.sign(mapper.task_to_program(tasks(f"t{i}")))
            self.assertEqual(latent.top_k(predicted, matrix, 1)[0][0], i)
            back = Mapper.sign(mapper.program_to_task(programs(f"p{i}")))
            self.assertEqual(latent.top_k(back, np.stack([tasks(f"t{j}") for j in range(6)]), 1)[0][0], i)
        # A new task similar to a known one maps near that task's program.
        near = latent.bundle([tasks("t2"), tasks("extra")])
        self.assertEqual(latent.top_k(Mapper.sign(mapper.task_to_program(near)), matrix, 1)[0][0], 2)
        # Refit from scratch: an empty replay forgets everything.
        self.assertEqual(mapper.fit([])["pairs"], 0)
        self.assertTrue(np.array_equal(mapper.task_to_program(tasks("t0")), tasks("t0").astype(np.float64)))


if __name__ == "__main__":
    unittest.main()
