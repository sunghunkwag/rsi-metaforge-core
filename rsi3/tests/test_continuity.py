"""Self-continuity: audits, restoration, budget charging, and passivity of measure mode."""
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.learning import State
from rsi2.search import solve

import random

from rsi3.continuity import (ContinuityGuard, Exam, SelfSnapshot, audit, sit_exams, snapshot,
                             write_exams)
from rsi3.integrator import BindingIntegrator
from rsi3.loop import ArmConfig, Runtime
from rsi3.verifier import public_view

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}
CONFIG = {"B_wake": 12, "B_eval": 12, "dreams": 4, "search": SEARCH,
          "controller": {"chunk": 6, "exploration": 0.3, "analog_neighbors": 2},
          "continuity": {"audit_budget": 12, "rehearsal": 3, "exams_per_generation": 2,
                         "exam_attempts": 32, "exam_author": "self"}}


def _subset():
    train = sorted(load_train(), key=lambda t: t.name)
    easy = [t for t in train
            if solve(t.examples, t.request_type, 12, Grammar(), **SEARCH).term is not None][:3]
    hard = [t for t in train if t not in easy][:3]
    return easy, hard


def _arm(mode):
    return ArmConfig(mode, allocation="uniform", genesis=False, designer_kinds=("prior",),
                     failure_memory=True, continuity=mode)


class ContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.easy, cls.hard = _subset()
        cls.tasks = cls.easy + cls.hard
        cls.public = {t.name: public_view(t) for t in cls.tasks}

    def test_audit_retains_own_solutions_and_rejects_a_different_behaviour(self):
        integrator = BindingIntegrator(list(self.public.values()))
        self_ = SelfSnapshot("g0", Grammar(), None)
        solutions = {}
        for task in self.easy:
            solutions[task.name] = solve(task.examples, task.request_type, 12, Grammar(),
                                         **SEARCH).term
        result = audit(self_, self.public, solutions, integrator, 12, SEARCH, {})
        self.assertEqual(result["count"], len(self.easy))
        # Pretend the stored "solution" of one task is another task's program:
        # rediscovery finds the right program, which behaves differently.
        a, b = self.easy[0].name, self.easy[1].name
        swapped = dict(solutions, **{a: solutions[b]})
        if integrator.signature(a, solutions[a], {}) != integrator.signature(a, solutions[b], {}):
            result = audit(self_, self.public, swapped, integrator, 12, SEARCH, {})
            self.assertNotIn(a, result["retained"])

    def test_measure_mode_is_passive(self):
        """Auditing without restoring must not change the run in any way."""
        off = Runtime(11, self.tasks, _arm("off"), CONFIG)
        on = Runtime(11, self.tasks, _arm("measure"), CONFIG)
        for _ in range(3):
            a, b = off.generation(), on.generation()
            self.assertEqual(b["continuity"]["charged"], 0)
            self.assertEqual(a["train_solved"], b["train_solved"])
            strip = lambda r: [(e["task"], e["start"], e["evaluated"], e["outcome"])
                               for e in r["wake"]["episodes"]]
            self.assertEqual(strip(a), strip(b))
        self.assertEqual(off.state.grammar.weights, on.state.grammar.weights)
        self.assertEqual(off.integrator.stats(), on.integrator.stats())

    def test_restore_charges_the_next_wake_and_never_loses_against_old(self):
        runtime = Runtime(11, self.tasks, _arm("restore"), CONFIG)
        cap = CONFIG["B_wake"] * len(self.tasks)
        previous_charge, bank = 0, 0
        for _ in range(3):
            record = runtime.generation()
            self.assertEqual(record["wake"]["budget"], max(0, cap - previous_charge))
            c = record["continuity"]
            # Exams join the bank only after the comparison that preceded them.
            self.assertEqual(c["exams_sat"], bank)
            bank += len(c["exams_written"])
            # The chosen self never scores less than the unmodified new self,
            # and is charged at least the two judgements and the exam writing.
            self.assertGreaterEqual(c["score"], c["new"]["score"])
            self.assertGreaterEqual(c["charged"], c["old"]["spent"] + c["new"]["spent"]
                                    + c["exam_writing_spent"])
            if not c["lost"] and not c["lost_exams"]:
                self.assertEqual(c["decision"], "accept_new")
            previous_charge = c["charged"]

    def test_guard_reverts_when_the_new_self_forgets(self):
        """Plant a forgetful rewrite: the new self cannot re-derive anything."""
        integrator = BindingIntegrator(list(self.public.values()))
        guard = ContinuityGuard("restore", budget=12, rehearsal=3, search_config=SEARCH,
                                integrator=integrator)
        state = State(11)
        for task in self.easy:
            state.solutions[task.name] = solve(task.examples, task.request_type, 12, Grammar(),
                                               **SEARCH).term
        old = snapshot(state, "old")
        # A rewrite that makes every solved program improbable: heavily weight
        # an irrelevant production so the budget is spent elsewhere first.
        state.grammar = Grammar(weights={"range": 1e6, "mod": 1e6, "filter": 1e6})
        record = guard.after_sleep(state, old, self.public, (), generation=1)
        self.assertTrue(record["lost"], "the planted rewrite should lose abilities")
        self.assertIn(record["decision"], ("rehearse", "revert"))
        self.assertGreater(record["score"], record["new"]["score"])
        self.assertGreater(record["charged"], 0)

    def _self_exams(self, author, keep=3):
        integrator = BindingIntegrator(list(self.public.values()))
        templates = [self.public[name] for name in sorted(self.public)]
        exams, spent = write_exams(author, templates, random.Random(5), generation=1, keep=keep,
                                   attempts=64, integrator=integrator, budget=12,
                                   search_config=SEARCH, library={}, known=set(),
                                   require_author_pass=True)
        return integrator, exams, spent

    def test_exams_have_answer_keys_the_author_passes_and_the_searcher_never_sees(self):
        author = SelfSnapshot("old", Grammar(), None)
        integrator, exams, spent = self._self_exams(author)
        self.assertTrue(exams)
        self.assertGreater(spent, 0)
        for exam in exams:
            self.assertEqual(exam.task.hidden, ())
            self.assertEqual(integrator.signature(exam.template, exam.answer, {}), exam.signature)
            outputs = {repr(value) for _, value in exam.task.examples}
            self.assertGreater(len(outputs), 1, "constant exams are excluded")
        self.assertEqual(sit_exams(author, exams, integrator, 12, SEARCH, {})["count"],
                         len(exams))
        # A program with the same public outputs but other behaviour fails the key.
        wrong = Exam("x", exams[0].template, exams[0].task, exams[0].answer, "different", 1)
        self.assertEqual(sit_exams(author, [wrong], integrator, 12, SEARCH, {})["count"], 0)

    def test_an_exam_loss_alone_reverts_the_rewrite(self):
        """No TRAIN task is lost (none is solved); only the exams detect the loss."""
        old = SelfSnapshot("old", Grammar(), None)
        integrator, exams, _ = self._self_exams(old)
        guard = ContinuityGuard("restore", budget=12, rehearsal=3, search_config=SEARCH,
                                integrator=integrator)
        guard.bank = list(exams)
        state = State(11)
        forgetful = Grammar(weights={"range": 1e6, "mod": 1e6, "filter": 1e6})
        state.grammar = forgetful
        record = guard.after_sleep(state, old, self.public, (), generation=2)
        self.assertEqual(record["lost"], [])
        self.assertTrue(record["lost_exams"])
        self.assertEqual(record["decision"], "revert")
        self.assertNotIn("rehearsed", record, "exams are never rehearsed")
        self.assertEqual(state.grammar.weights, old.grammar.weights)
        self.assertIsNot(state.grammar, forgetful)


if __name__ == "__main__":
    unittest.main()
