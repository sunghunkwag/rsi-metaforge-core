"""The proof form: the kernel's reader and checker, and the search's proofs, against set.mm.

    python -m rsi6.tests.test_proof      (fetches set.mm by hash on first use)
"""
from __future__ import annotations

import os
import sys
import unittest

from rsi6 import fetch
from rsi6.kernel.metamath import Database, Rejected
from rsi6.kernel.problem import Meter
from rsi6.learner.prover import Entry, Library, Prover

HERE = os.path.dirname(os.path.abspath(__file__))
SETMM = os.path.join(os.path.dirname(HERE), "data", "setmm", "set.mm")
_DB = None


def database() -> Database:
    global _DB
    if _DB is None:
        if not os.path.exists(SETMM):
            fetch.fetch("setmm", quiet=True)
        from rsi6.experiments.dev_proof_depth import pool_text
        _DB = Database.read(pool_text(open(SETMM).read()))
    return _DB


class TestChecker(unittest.TestCase):
    def test_every_human_proof_of_the_pool_is_accepted(self):
        db = database()
        theorems = [l for l in db.order if db.assertions[l].kind == "p"]
        self.assertEqual(len(theorems), 1620)
        for label in theorems:
            self.assertTrue(db.verify(label))

    def test_a_proof_of_something_else_is_rejected(self):
        db = database()
        with self.assertRaises(Rejected):
            db.verify("mp2", db.assertions["a1i"].proof)
        with self.assertRaises(Rejected):
            db.verify("a1i", ["wph", "wps", "ax-1"])

    def test_a_corrupted_compressed_proof_is_rejected(self):
        db = database()
        proof = list(db.assertions["syl"].proof)
        k = proof.index(")") + 1
        proof[k] = proof[k].replace("C", "D", 1) if "C" in proof[k] else proof[k].replace("A", "B", 1)
        with self.assertRaises(Rejected):
            db.verify("syl", proof)

    def test_trees_round_trip(self):
        db = database()
        for label in db.order[:400]:
            a = db.assertions[label]
            if a.typecode == "|-":
                self.assertEqual(db.unparse(db.parse("wff", a.stmt[1:])), a.stmt[1:])


class TestSearch(unittest.TestCase):
    def test_proofs_from_the_axioms_are_accepted(self):
        sys.setrecursionlimit(20000)
        db = database()
        lib = Library()
        for label in db.order:
            a = db.assertions[label]
            if a.kind == "a" and a.typecode == "|-":
                lib.add(Entry(db, label))
            if label == "a1i":
                break
        for goal in ("a1i", "idi"):
            proof = Prover(db, lib).prove(goal, Meter(50000))
            self.assertIsNotNone(proof, goal)
            self.assertTrue(db.verify(goal, proof))

    def test_the_budget_is_respected(self):
        db = database()
        lib = Library()
        for label in ("ax-mp", "ax-1", "ax-2", "ax-3"):
            lib.add(Entry(db, label))
        meter = Meter(1000)
        Prover(db, lib).prove("pm2.43", meter)
        self.assertLessEqual(meter.used, 1001)


if __name__ == "__main__":
    unittest.main()
