"""Analogical repair: edits of verified programs, best-first cost order, resumable windows."""
import unittest

from rsi2.corpus import load_train
from rsi2.grammar import Grammar
from rsi2.terms import App, Int, Lam, Prim, Var, pretty
from rsi2.types import INT, Arrow, ListOf

from rsi3.analogy import AnalogySearch, SourceIndex, edits, similarity
from rsi3.verifier import FrozenVerifier, public_view

LIST = ListOf(INT)
REQUEST = Arrow(LIST, LIST)
SEARCH = {"step_budget": 2000, "max_size": 12, "max_expansions": 20000}


def prepend(k):
    return Lam(LIST, App(App(Prim("cons"), Int(k)), Var(0)))


def examples_of(function, inputs):
    return tuple(((x,), function(x)) for x in inputs)


INPUTS = [[], [1], [2, 3], [4, 0, 4], [7, 7, 1, 2], [9], [3, 1], [5, 6, 7]]


class AnalogyTests(unittest.TestCase):
    def test_edits_cover_replace_wrap_pre_and_post(self):
        source = Lam(LIST, App(App(Prim("cons"), Int(3)), App(Prim("tail"), Var(0))))
        kinds = {e.mode for e in edits(source, REQUEST)}
        self.assertEqual(kinds, {"replace", "wrap", "pre", "post"})
        replaced = [e for e in edits(source, REQUEST) if e.mode == "replace"
                    and e.path == (0, 0, 1)]
        self.assertEqual(len(replaced), 1)
        self.assertEqual(replaced[0].hole_type, INT)       # a constant becomes an int hole
        self.assertEqual(pretty(replaced[0].compose(Int(5))), pretty(
            Lam(LIST, App(App(Prim("cons"), Int(5)), App(Prim("tail"), Var(0))))))
        self.assertFalse(any(e.mode == "replace" and len(e.path) < 2
                             for e in edits(source, REQUEST)))

    def test_a_constant_edit_solves_a_new_parameter(self):
        examples = examples_of(lambda x: [-1] + x, INPUTS)
        search = AnalogySearch(examples, REQUEST, {"prepend-3": prepend(3)}, Grammar(), **SEARCH)
        result = search.run(16)
        self.assertIsNotNone(result.term)
        self.assertEqual(pretty(result.term), pretty(App(Prim("cons"), Int(-1))))

    def test_a_source_that_already_fits_costs_one_unit(self):
        examples = examples_of(lambda x: [3] + x, INPUTS)
        result = AnalogySearch(examples, REQUEST, {"p": prepend(3)}, Grammar(), **SEARCH).run(10)
        self.assertEqual(result.evaluated, 1)
        self.assertIsNotNone(result.term)

    def test_windows_resume_exactly(self):
        examples = examples_of(lambda x: [5] + list(reversed(x)), INPUTS)
        sources = {"p": prepend(3), "q": prepend(1)}
        whole = AnalogySearch(examples, REQUEST, sources, Grammar(), **SEARCH)
        first = whole.run(25)
        split = AnalogySearch(examples, REQUEST, sources, Grammar(), **SEARCH)
        a = split.run(10)
        rebuilt = AnalogySearch(examples, REQUEST, sources, Grammar(), **SEARCH)
        rebuilt.fast_forward(split.position, split.evaluated, split.skipped_known,
                             split.evaluation_steps)
        b = rebuilt.run(15)
        self.assertEqual(a.evaluated + b.evaluated, first.evaluated)
        self.assertEqual(None if first.term is None else pretty(first.term),
                         None if b.term is None else pretty(b.term))

    def test_similarity(self):
        self.assertEqual(similarity([1, 2], [1, 2]), 1.0)
        self.assertEqual(similarity(None, [1]), 0.0)
        self.assertAlmostEqual(similarity([1, 2, 3], [1, 2, 4]), 2 / 3)
        self.assertEqual(similarity(True, False), 0.0)
        self.assertEqual(similarity(3, 3), 1.0)

    def test_sources_are_same_typed_and_exclude_the_task(self):
        train = [public_view(t) for t in load_train()]
        index = SourceIndex(train)
        lookup = {t.name: t for t in train}
        target = lookup["append-k with k=4"]
        solutions = {"append-k with k=1": prepend(1), "append-k with k=4": prepend(4),
                     "index-k with k=3": Lam(LIST, App(Prim("head"), Var(0)))}
        sources = index.sources(solutions, target.request_type, target.examples,
                                exclude=target.name)
        self.assertEqual(list(sources), ["append-k with k=1"])

    def test_found_programs_pass_the_verifier_on_a_train_task(self):
        train = {t.name: t for t in load_train()}
        task = train["prepend-k with k=0"]
        public = public_view(task)
        result = AnalogySearch(public.examples, public.request_type, {"p": prepend(2)},
                               Grammar(), **SEARCH).run(16)
        self.assertIsNotNone(result.term)
        self.assertTrue(FrozenVerifier([task]).verify(task.name, result.term, {}, 1).verdict)


if __name__ == "__main__":
    unittest.main()
