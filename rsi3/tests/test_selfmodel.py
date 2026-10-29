"""Self-model concept invention: proposals, behaviour filter, and verified adoption."""
import json
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.search import solve
from rsi2.terms import App, Lam, Prim, Var, pretty
from rsi2.types import INT, Arrow, ListOf, infer

from rsi3.loop import ArmConfig, Runtime
from rsi3.selfmodel import SelfModel, is_eta_atom, normalize, references
from rsi3.verifier import public_view

SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}
LIST = ListOf(INT)


def _train():
    return {task.name: task for task in load_train()}


def _solve(task, budget=3000):
    return solve(task.examples, task.request_type, budget, Grammar(), heuristic=None,
                 **SEARCH).term


class NormalFormTests(unittest.TestCase):
    def test_beta_and_eta(self):
        tail_twice = Lam(LIST, App(Prim("tail"), App(Prim("tail"), Var(0))))
        composed = Lam(LIST, App(tail_twice, App(tail_twice, Var(0))))
        self.assertEqual(pretty(normalize(composed)),
                         pretty(Lam(LIST, App(Prim("tail"), App(Prim("tail"), App(
                             Prim("tail"), App(Prim("tail"), Var(0))))))))
        self.assertEqual(normalize(Lam(LIST, App(Prim("tail"), Var(0)))), Prim("tail"))
        self.assertTrue(is_eta_atom(Lam(INT, Lam(INT, App(App(Prim("add"), Var(1)), Var(0))))))
        self.assertFalse(is_eta_atom(Lam(INT, Lam(INT, App(App(Prim("add"), Var(0)), Var(1))))))


class InventionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = _train()
        cls.public = [public_view(t) for t in cls.train.values()]
        names = ["index-k with k=3", "prepend-k with k=4", "prepend-k with k=0"]
        cls.solutions = {n: _solve(cls.train[n]) for n in names}

    def test_concepts_come_from_its_own_programs(self):
        model = SelfModel(self.public)
        concepts = model.invent(self.solutions, {})
        bodies = {pretty(c.term): c for c in concepts}
        # A power of a part of head (tail (tail x)): drop four elements.
        drop4 = "(lambda x0: list[int]. (tail (tail (tail (tail x0)))))"
        self.assertIn(drop4, bodies)
        self.assertEqual(bodies[drop4].kind, "power")
        self.assertEqual(bodies[drop4].sources, ("index-k with k=3",))
        # Integers the frozen grammar cannot name, from add 2 inside cons (add 2 2).
        values = {c.value for c in concepts if c.kind == "constant"}
        self.assertTrue({3, 4} <= values)
        self.assertFalse(values & {-1, 0, 1, 2})
        for concept in concepts:
            self.assertFalse(is_eta_atom(concept.term))
            self.assertTrue(concept.name.startswith("c_"))
            self.assertTrue(set(concept.sources) <= set(self.solutions))

    def test_no_concept_behaves_like_a_primitive_or_the_identity(self):
        model = SelfModel(self.public)
        concepts = model.invent(self.solutions, {})
        tail_behaviour = model.behaviour(Prim("tail"), Arrow(LIST, LIST), {})
        identity = json.dumps(list(model.pool["list[int]"]), default=str)
        signatures = set()
        for concept in concepts:
            behaviour = model.behaviour(concept.term, infer(concept.term), {})
            if behaviour is None:
                continue
            self.assertNotEqual(behaviour, tail_behaviour)
            self.assertNotEqual(behaviour, identity)
            self.assertNotIn(behaviour, signatures, "behaviourally equal concepts are one")
            signatures.add(behaviour)

    def test_names_are_stable_and_existing_entries_are_not_reproposed(self):
        first = SelfModel(self.public).invent(self.solutions, {})
        again = SelfModel(self.public).invent(self.solutions, {})
        self.assertEqual([c.name for c in first], [c.name for c in again])
        library = {first[0].name: first[0].term}
        later = SelfModel(self.public).invent(self.solutions, library)
        self.assertNotIn(pretty(first[0].term), {pretty(c.term) for c in later})

    def test_model_reads_only_public_views(self):
        model = SelfModel(self.public)
        for task in self.public:
            self.assertEqual(task.hidden, ())
        self.assertTrue(model.pool["list[int]"])


class AdoptionTests(unittest.TestCase):
    """A concept joins the language only through a verified program that uses it."""

    def test_invented_concept_is_adopted_by_a_verified_solve(self):
        train = _train()
        tasks = [train["index-k with k=3"], train["index-k with k=5"]]
        config = {"B_wake": 64, "B_eval": 64, "dreams": 4, "search": SEARCH,
                  "controller": {"chunk": 32, "exploration": 0.3, "analog_neighbors": 2},
                  "invention": {}}
        arm = ArmConfig("inv", allocation="uniform", genesis=False, designer_kinds=("prior",),
                        failure_memory=True, invention=True)
        runtime = Runtime(11, tasks, arm, config)
        runtime.state.solutions["index-k with k=3"] = _solve(train["index-k with k=3"])
        record = runtime.generation()
        self.assertIn("index-k with k=5", runtime.state.solutions)
        used = references(runtime.state.solutions["index-k with k=5"])
        adopted = set(record["wake"]["adopted"])
        self.assertTrue(adopted)
        self.assertTrue(adopted <= used)
        proposed = {c["name"] for c in record["wake"]["invention"]["proposed"]}
        self.assertTrue(adopted <= proposed)
        library = runtime.state.grammar.library
        self.assertTrue(adopted <= set(library))
        self.assertFalse((proposed - adopted) & set(library),
                         "concepts that earned nothing leave with the generation")
        # The verifier accepted it on hidden examples (one receipt per task per generation).
        self.assertEqual(runtime.verifier.queries, 1)

    def test_unadopted_concepts_enter_the_search_at_a_tenth_of_the_pseudocount(self):
        train = _train()
        config = {"B_wake": 8, "B_eval": 8, "dreams": 2, "search": SEARCH,
                  "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2},
                  "invention": {}}
        arm = ArmConfig("inv", allocation="uniform", genesis=False, designer_kinds=("prior",),
                        failure_memory=True, invention=True)
        runtime = Runtime(11, [train["index-k with k=3"], train["index-k with k=5"]], arm, config)
        runtime.state.solutions["index-k with k=3"] = _solve(train["index-k with k=3"])
        runtime.invent(1)
        grammar = runtime.registry.base_grammar(runtime.state)
        self.assertTrue(runtime.registry.extra_library)
        for name in runtime.registry.extra_library:
            self.assertEqual(grammar.weights[name], 0.1)
            self.assertNotIn(name, runtime.state.grammar.library)
        runtime.state.solutions["prepend-k with k=0"] = _solve(train["prepend-k with k=0"])
        parts = {c["body"] for c in runtime.invent(1)["proposed"] if c["kind"] == "part"}
        # A non-trivial solved program is a building block; a trivial one is not.
        self.assertIn(pretty(runtime.state.solutions["index-k with k=3"]), parts)
        self.assertNotIn(pretty(runtime.state.solutions["prepend-k with k=0"]), parts)

    def test_without_invention_the_prior_grammar_is_the_state_grammar(self):
        train = _train()
        config = {"B_wake": 8, "B_eval": 8, "dreams": 2, "search": SEARCH,
                  "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2}}
        arm = ArmConfig("plain", allocation="uniform", genesis=False, designer_kinds=("prior",),
                        failure_memory=True)
        runtime = Runtime(11, [train["index-k with k=3"]], arm, config)
        self.assertIsNone(runtime.selfmodel)
        self.assertIs(runtime.registry.base_grammar(runtime.state), runtime.state.grammar)


if __name__ == "__main__":
    unittest.main()


class InventedPathwayTests(unittest.TestCase):
    """Concepts in their own pathway: the prior pathway stays undiluted."""

    def test_split_arm_keeps_the_prior_grammar_and_solves_through_the_invented_pathway(self):
        from rsi3.experiment import ARMS
        train = _train()
        config = {"B_wake": 64, "B_eval": 64, "dreams": 4, "search": SEARCH,
                  "controller": {"chunk": 32, "exploration": 0.3, "analog_neighbors": 2},
                  "invention": {}}
        runtime = Runtime(11, [train["index-k with k=3"], train["index-k with k=5"]],
                          ARMS["RSI3_UNIFORM_FM_INVP"], config)
        runtime.state.solutions["index-k with k=3"] = _solve(train["index-k with k=3"])
        record = runtime.generation()
        episodes = record["wake"]["episodes"]
        self.assertEqual([e["pathway"] for e in episodes], ["prior", "invented"])
        self.assertEqual(episodes[1]["outcome"], "verified")
        self.assertTrue(record["wake"]["adopted"])
        # One verification per task per generation, even with two pathways.
        self.assertEqual(runtime.verifier.queries, 1)
        runtime.registry.begin_generation()
        runtime.invent(2)
        self.assertIs(runtime.registry.grammar("prior", "index-k with k=5", runtime.state),
                      runtime.state.grammar)

    def test_other_arms_have_no_invented_pathway(self):
        from rsi3.experiment import ARMS
        train = _train()
        config = {"B_wake": 8, "B_eval": 8, "dreams": 2, "search": SEARCH,
                  "controller": {"chunk": 8, "exploration": 0.3, "analog_neighbors": 2}}
        for arm in ("RSI3_UNIFORM_FM", "RSI3_UNIFORM_FM_INV", "RSI3"):
            runtime = Runtime(11, [train["index-k with k=3"]], ARMS[arm], config)
            self.assertNotIn("invented", runtime.registry.pathways)


class AbstractionTests(unittest.TestCase):
    def test_the_system_abstracts_a_skeleton_from_its_own_program(self):
        from rsi3.selfmodel import _abstractions
        from rsi2.types import ListOf
        L = ListOf(INT)
        reverse = App(App(Prim("fold"), Lam(L, Lam(INT, App(App(Prim("cons"), Var(0)),
                                                             Var(1))))), Prim("nil"))
        bodies = [pretty(c) for c in _abstractions(reverse, {})]
        self.assertIn("(lambda x0: list[int] -> int -> list[int]. ((fold x0) nil))", bodies)
        off = SelfModel([public_view(t) for t in load_train()]).invent({"reverse": reverse}, {})
        self.assertFalse([c for c in off if c.kind == "abstract"], "off unless its cap is set")
