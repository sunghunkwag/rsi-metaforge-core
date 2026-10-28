"""Self-continuity: audits, restoration, budget charging, and passivity of measure mode."""
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.learning import State
from rsi2.search import solve

from rsi3.continuity import ContinuityGuard, SelfSnapshot, audit, snapshot
from rsi3.integrator import BindingIntegrator
from rsi3.loop import ArmConfig, Runtime
from rsi3.verifier import public_view

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}
CONFIG = {"B_wake": 12, "B_eval": 12, "dreams": 4, "search": SEARCH,
          "controller": {"chunk": 6, "exploration": 0.3, "analog_neighbors": 2},
          "continuity": {"audit_budget": 12, "rehearsal": 3}}


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
        previous_charge = 0
        for _ in range(3):
            record = runtime.generation()
            self.assertEqual(record["wake"]["budget"], max(0, cap - previous_charge))
            c = record["continuity"]
            if "old" in c:
                # The chosen self never retains less than the unmodified new self,
                # and is charged at least the two audits it ran.
                self.assertGreaterEqual(c["retained"], c["new"]["count"])
                self.assertGreaterEqual(c["charged"], c["old"]["spent"] + c["new"]["spent"])
                if not c["lost"]:
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
        self.assertGreater(record["retained"], record["new"]["count"])
        self.assertGreater(record["charged"], 0)


if __name__ == "__main__":
    unittest.main()
