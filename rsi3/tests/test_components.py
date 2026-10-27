"""Pathway registry, value model, controller, and integrator unit tests."""
import unittest

import numpy as np

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.learning import State
from rsi2.search import solve
from rsi2.terms import Prim, apply

from rsi3.controller import Controller, Slot
from rsi3.integrator import BindingIntegrator, probe_inputs
from rsi3.loop import standardized_features
from rsi3.memory import EpisodicMemory
from rsi3.pathways import PathwayRegistry, grammar_fingerprint
from rsi3.value_model import DIM, ValueModel, slot_features
from rsi3.verifier import FrozenVerifier, public_view

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}


class PathwayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = load_train()
        cls.public = [public_view(t) for t in cls.train]
        cls.features = standardized_features(cls.public)
        # Find two tasks the generation-zero prior solves, for genesis.
        cls.solved = {}
        for task in sorted(cls.train, key=lambda t: t.name):
            result = solve(task.examples, task.request_type, 64, Grammar(), **SEARCH)
            if result.term is not None:
                cls.solved[task.name] = result.term
            if len(cls.solved) == 2:
                break

    def _registry(self, genesis=True):
        return PathwayRegistry(self.public, self.features, genesis=genesis, neighbors=1,
                               search_config=SEARCH)

    def test_genesis_creates_dormant_pathways_without_search_state(self):
        registry, state = self._registry(), State(11)
        state.solutions.update(self.solved)
        created = registry.genesis(state, generation=1)
        self.assertEqual(sorted(created), sorted(f"analog:{n}" for n in self.solved))
        for pid in created:
            self.assertEqual(registry.pathways[pid].status, "dormant")
            self.assertEqual(registry.pathways[pid].origin, "genesis")
        self.assertEqual(registry.genesis(state, generation=2), [])
        self.assertEqual(self._registry(genesis=False).genesis(state, 1), [])

    def test_awakening_and_resumption_under_unchanged_grammar(self):
        registry, state = self._registry(), State(11)
        state.solutions.update(self.solved)
        registry.genesis(state, generation=1)
        unsolved = next(t.name for t in self.public if t.name not in self.solved)
        analogs = [pid for pid, _ in registry.applicable(unsolved, state) if pid.startswith("analog")]
        self.assertLessEqual(len(analogs), 1)
        if not analogs:
            self.skipTest("no type-compatible analog for this task")
        pid = analogs[0]
        registry.begin_generation()
        _, search = registry.search(unsolved, pid, state, generation=2)
        self.assertEqual(registry.pathways[pid].status, "active")
        self.assertEqual(registry.pathways[pid].awakened_generation, 2)
        search.run(8)
        registry.begin_generation()
        self.assertEqual(registry.peek(unsolved, pid, state)[0], 8)
        _, again = registry.search(unsolved, pid, state, generation=3)
        self.assertIs(again, search)

    def test_grammar_change_resets_the_frontier(self):
        registry, state = self._registry(), State(11)
        task = self.public[0].name
        registry.begin_generation()
        _, search = registry.search(task, "prior", state, generation=1)
        search.run(4)
        state.grammar = Grammar(weights={"map": 5.0})
        registry.begin_generation()
        self.assertEqual(registry.peek(task, "prior", state), (0, False))
        _, fresh = registry.search(task, "prior", state, generation=2)
        self.assertIsNot(fresh, search)

    def test_fingerprint_is_stable_and_sensitive(self):
        self.assertEqual(grammar_fingerprint(Grammar()), grammar_fingerprint(Grammar()))
        self.assertNotEqual(grammar_fingerprint(Grammar()),
                            grammar_fingerprint(Grammar(weights={"add": 2.0})))


class ValueModelTests(unittest.TestCase):
    def test_priors_without_signal(self):
        model = ValueModel()
        self.assertTrue(np.allclose(model.predict(np.zeros((2, DIM))), 0.5))
        model.fit(np.zeros((4, DIM)), [0, 0, 0, 0])
        self.assertTrue(np.allclose(model.predict(np.zeros((1, DIM))), 1 / 6))

    def test_learns_and_is_deterministic(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(200, DIM))
        y = (X[:, 0] > 0.5).astype(int)
        a, b = ValueModel(), ValueModel()
        a.fit(X, y)
        b.fit(X, y)
        self.assertTrue(np.array_equal(a.predict(X), b.predict(X)))
        p = a.predict(X)
        self.assertGreater(p[y == 1].mean(), p[y == 0].mean() + 0.3)

    def test_slot_features_encode_kind_and_depth(self):
        base = np.zeros(32)
        prior = slot_features(base, "prior", 0.0, 0, 32)
        analog = slot_features(base, "analog", 0.9, 640, 32)
        self.assertEqual(prior.shape, (DIM,))
        self.assertFalse(np.array_equal(prior, analog))


class ControllerTests(unittest.TestCase):
    def _slot(self, task, pathway):
        return Slot(task, pathway, "prior", 0, 0.0, np.zeros(DIM))

    def test_unexplored_slot_wins_on_equal_value(self):
        controller = Controller(chunk=32, exploration=0.3, seed=1)
        slots = [self._slot("a", "prior"), self._slot("a", "analog:x")]
        windows = {("a", "prior"): 5}
        self.assertEqual(controller.choose(slots, [0.1, 0.1], windows, 5), 1)

    def test_value_dominates_when_exploration_is_even(self):
        controller = Controller(chunk=32, exploration=0.3, seed=1)
        slots = [self._slot("a", "prior"), self._slot("b", "prior")]
        self.assertEqual(controller.choose(slots, [0.05, 0.6], {}, 10), 1)

    def test_tiebreak_is_deterministic(self):
        slots = [self._slot(t, "prior") for t in "abcdef"]
        picks = {Controller(chunk=8, exploration=0.3, seed=7).choose(slots, [0.2] * 6, {}, 0)
                 for _ in range(3)}
        self.assertEqual(len(picks), 1)

    def test_uniform_split_preserves_total(self):
        split = Controller.uniform_split(2304, [f"t{i}" for i in range(30)])
        self.assertEqual(sum(split.values()), 2304)
        self.assertLessEqual(max(split.values()) - min(split.values()), 1)


class IntegratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = load_train()
        cls.task = next(t for t in cls.train if "list" in str(t.request_type))

    def test_probes_preserve_types_and_are_deterministic(self):
        probes = probe_inputs(self.task.examples)
        self.assertEqual(probes, probe_inputs(self.task.examples))
        for probe, (inputs, _) in zip(probes, self.task.examples):
            self.assertEqual(len(probe), len(inputs))
            for new, old in zip(probe, inputs):
                self.assertIs(type(new), type(old))

    def test_rejected_behaviour_is_skipped(self):
        verifier = FrozenVerifier(self.train)
        memory = EpisodicMemory(verifier)
        integrator = BindingIntegrator([public_view(t) for t in self.train])
        self.assertIsNone(integrator.skip_callback(self.task.name, {}, memory))
        wrong = apply(Prim("map"), apply(Prim("add"), apply(Prim("length"), Prim("nil"))))
        receipt = verifier.verify(self.task.name, wrong, {}, generation=1)
        self.assertFalse(receipt.verdict)
        integrator.bind_rejected(self.task.name, wrong, {}, receipt, memory)
        skip = integrator.skip_callback(self.task.name, {}, memory)
        self.assertTrue(skip(wrong))
        self.assertEqual(integrator.skipped_equivalent, 1)
        self.assertGreater(integrator.probe_evaluations, 0)


if __name__ == "__main__":
    unittest.main()
