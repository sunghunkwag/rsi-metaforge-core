"""The bottom-up engine: observational equivalence prunes equal behaviours, the
normal-form filter refuses exactly the documented rewrite set, searches are
deterministic, and known programs are found."""
import unittest

from rsi5 import probes
from rsi5.dsl.types import Arrow, BOOL, INT, ListOf
from rsi5.dsl.vocabulary import ORIGINAL, RESTORED
from rsi5.engine import normal_forms
from rsi5.engine.bottomup import Engine, Expr
from rsi5.engine.oe import ERR, OETable, key_of

LIST = Arrow(ListOf(INT), ListOf(INT))


def _expr(kind, head, args=(), uses=frozenset(), ident=0):
    return Expr(kind, head, tuple(args), INT, 1, [], (), uses, ident, False)


class ObservationalEquivalence(unittest.TestCase):
    def test_oe_prunes_equal_outputs(self):
        table = OETable()
        a = _expr("var", 0)
        self.assertTrue(table.admit(INT, key_of([1, 2, 3]), a))
        b = _expr("prim", "add")
        self.assertFalse(table.admit(INT, key_of([1, 2, 3]), b))       # same behaviour: pruned
        self.assertTrue(table.admit(INT, key_of([1, 2, 4]), b))
        self.assertTrue(table.admit(ListOf(INT), key_of([[1], [2], [3]]), b))
        self.assertEqual(table.pruned, 1)
        self.assertIs(table.lookup(INT, key_of([1, 2, 3])), a)

    def test_lists_and_errors_key_distinctly(self):
        self.assertNotEqual(key_of([[1, 2]]), key_of([[1], [2]]))
        self.assertNotEqual(key_of([ERR]), key_of([None]))
        self.assertEqual(key_of([[1, [2]]]), ((1, (2,)),))

    def test_engine_pool_holds_one_program_per_behaviour(self):
        engine = Engine(ORIGINAL, max_size=5)
        examples = [(([1, 2, 3],), [99]), (([],), [99])]
        engine.search(examples, LIST, [([4],)], budget=5000)
        top = engine.top
        for type_, pool in top.pools.items():
            keys = [expr.key for expr in pool]
            self.assertEqual(len(keys), len(set(keys)), str(type_))
        self.assertGreater(sum(c.oe.pruned for c in engine.contexts), 0)


class NormalForms(unittest.TestCase):
    """Each documented left-hand side is refused; a nearby normal term is accepted."""

    def setUp(self):
        self.x = _expr("var", 0, ident=1)
        self.y = _expr("var", 1, ident=2)
        self.zero = _expr("const", 0, ident=3)
        self.one = _expr("const", 1, ident=4)
        self.true = _expr("const", True, ident=5)
        self.nil = _expr("prim", "nil", ident=6)
        self.notx = _expr("prim", "not", (self.x,), ident=7)
        self.negx = _expr("prim", "neg", (self.x,), ident=8)
        self.consxy = _expr("prim", "cons", (self.x, self.y), ident=9)
        self.headx = _expr("prim", "head", (self.x,), ident=10)
        self.tailx = _expr("prim", "tail", (self.x,), ident=11)
        self.pairxy = _expr("prim", "pair", (self.x, self.y), ident=12)
        self.fstp = _expr("prim", "fst", (self.pairxy,), ident=13)
        self.sndp = _expr("prim", "snd", (self.pairxy,), ident=14)
        self.lam_true = Expr("lam", (INT,), (self.true,), None, 2, None, None, frozenset(), 15, False)
        self.lam_x = Expr("lam", (INT,), (self.x,), None, 2, None, None, frozenset(), 16, False)
        acc = _expr("var", 1, uses=frozenset([1]), ident=17)
        self.lam_acc = Expr("lam", (INT, INT), (acc,), None, 3, None, None, frozenset(), 18, False)
        body_no_rec = _expr("var", 0, uses=frozenset([0]), ident=19)
        self.fix_body_no_rec = Expr("lam", (Arrow(INT, INT), INT), (body_no_rec,), None, 3, None,
                                    None, frozenset(), 20, False)
        body_rec = _expr("vapp", 1, (self.x,), uses=frozenset([0, 1]), ident=21)
        self.fix_body_rec = Expr("lam", (Arrow(INT, INT), INT), (body_rec,), None, 3, None, None,
                                 frozenset(), 22, False)

    def test_normal_forms_rewrite_set(self):
        n = normal_forms.normal
        x, y, zero, one, true, nil = self.x, self.y, self.zero, self.one, self.true, self.nil
        refused = [
            ("if", (true, x, y)), ("if", (self.notx, x, y)), ("if", (x, y, y)),
            ("not", (self.notx,)), ("not", (true,)), ("neg", (self.negx,)), ("neg", (one,)),
            ("abs", (self.negx,)), ("abs", (one,)),
            ("add", (x, zero)), ("add", (zero, x)), ("add", (y, x)),
            ("sub", (x, zero)), ("sub", (x, x)),
            ("mul", (x, one)), ("mul", (one, x)), ("mul", (x, zero)), ("mul", (y, x)),
            ("div", (x, one)), ("div", (x, zero)), ("div", (x, x)),
            ("mod", (x, one)), ("mod", (x, zero)), ("mod", (x, x)),
            ("eq", (x, x)), ("lt", (x, x)), ("le", (x, x)), ("gt", (x, x)), ("ge", (x, x)), ("eq", (y, x)),
            ("and", (x, x)), ("or", (x, x)), ("and", (true, x)), ("or", (x, true)), ("and", (y, x)),
            ("cons", (self.headx, self.tailx)),
            ("head", (self.consxy,)), ("tail", (self.consxy,)), ("is_empty", (self.consxy,)),
            ("is_empty", (nil,)), ("length", (nil,)), ("length", (self.consxy,)),
            ("head", (nil,)), ("tail", (nil,)),
            ("map", (self.lam_x, nil)), ("filter", (self.lam_x, nil)), ("fold", (self.lam_acc, zero, nil)),
            ("filter", (self.lam_true, x)), ("fold", (self.lam_acc, zero, x)),
            ("zip", (nil, x)), ("zip", (x, nil)), ("index", (one, nil)),
            ("unfold", (self.lam_true, self.lam_x, self.lam_x, x)),
            ("fix1", (x, self.fix_body_no_rec)),
            ("fst", (self.pairxy,)), ("snd", (self.pairxy,)), ("pair", (self.fstp, self.sndp)),
        ]
        for name, args in refused:
            self.assertFalse(n(name, args), f"{name} {[str(a.head) for a in args]} should be refused")
        accepted = [
            ("if", (x, y, zero)), ("not", (x,)), ("neg", (x,)), ("abs", (x,)),
            ("add", (x, y)), ("add", (x, one)), ("sub", (x, y)), ("sub", (zero, x)),
            ("mul", (x, y)), ("div", (x, y)), ("mod", (x, y)), ("eq", (x, y)), ("lt", (x, y)),
            ("and", (x, y)), ("cons", (x, y)), ("cons", (self.headx, y)),
            ("head", (x,)), ("tail", (x,)), ("is_empty", (x,)), ("length", (x,)),
            ("map", (self.lam_x, x)), ("filter", (self.lam_x, x)), ("fold", (self.lam_true, zero, x)),
            ("zip", (x, y)), ("index", (one, x)), ("unfold", (self.lam_x, self.lam_x, self.lam_x, x)),
            ("fix1", (x, self.fix_body_rec)), ("fst", (x,)), ("pair", (x, y)), ("pair", (self.fstp, x)),
        ]
        for name, args in accepted:
            self.assertTrue(n(name, args), f"{name} {[str(a.head) for a in args]} should be accepted")

    def test_documented_rules_are_implemented(self):
        """Every refused form in NORMAL_FORMS.md names a primitive the filter handles."""
        from pathlib import Path
        doc = Path(normal_forms.__file__).with_name("NORMAL_FORMS.md").read_text(encoding="utf-8")
        table = doc[doc.index("## Rewrite rules"):]
        heads = set()
        for line in table.splitlines():
            if line.startswith("| `"):
                for cell in line.split("|")[1].split(","):
                    cell = cell.strip().strip("`")
                    if cell:
                        heads.add(cell.split()[0])
        handled = {"if", "not", "neg", "abs", "add", "sub", "mul", "div", "mod", "eq", "lt", "le",
                   "gt", "ge", "and", "or", "cons", "head", "tail", "is_empty", "length", "map",
                   "filter", "fold", "zip", "index", "unfold", "fix1", "fst", "snd", "pair"}
        self.assertTrue(heads <= handled, heads - handled)
        self.assertTrue(handled <= heads, handled - heads)


class Searches(unittest.TestCase):
    def test_finds_map_add_one(self):
        engine = Engine(ORIGINAL)
        examples = [(([1, 2, 3],), [2, 3, 4]), (([],), []), (([5],), [6]), (([0, 0],), [1, 1])]
        result = engine.search(examples, LIST, probes.inputs_for((ListOf(INT),)), budget=20000)
        self.assertIsNotNone(result.term)
        self.assertEqual(str(result.term), "(lambda x0: list[int]. ((map (lambda x1: int. ((sub x1) -1))) x0))")
        self.assertEqual(result.candidates, result.candidates_to_solution)

    def test_two_runs_byte_identical(self):
        examples = [(([3, 1, 2],), [1, 2, 3]), (([],), []), (([5, 4],), [4, 5]), (([1, 1, 0],), [0, 1, 1])]
        results = []
        for _ in range(2):
            engine = Engine(RESTORED)
            result = engine.search(examples, LIST, probes.inputs_for((ListOf(INT),)), budget=6000)
            results.append((str(result.term), result.candidates, result.candidates_to_solution,
                            result.pruned, result.pool_size, result.completed_size,
                            [(tuple(d[0]), d[1], d[2]) for d in result.detail["pool_by_context"]]))
        self.assertEqual(results[0], results[1])

    def test_budget_is_respected_and_monotone(self):
        examples = [(([1, 2, 3],), [3, 2, 1]), (([],), []), (([5, 4],), [4, 5])]
        small = Engine(ORIGINAL).search(examples, LIST, [], budget=500)
        self.assertEqual(small.candidates, 500)
        self.assertIsNone(small.term)
        large = Engine(ORIGINAL).search(examples, LIST, [], budget=30000)
        if large.term is not None:
            self.assertGreater(large.candidates_to_solution, 500)

    def test_restored_vocabulary_reaches_is_prime(self):
        engine = Engine(RESTORED)
        examples = [(([10, 13, 2, 4, 4, 14],), [0, 1, 1, 0, 0, 0]), (([8, 5, 5, 5, 13, 5, 3],), [0, 1, 1, 1, 1, 1, 1]),
                    (([],), []), (([1, 14],), [0, 0]), (([7, 9, 11],), [1, 0, 1])]
        result = engine.search(examples, LIST, [], budget=40000)
        self.assertIsNotNone(result.term)
        self.assertIn("is_prime", str(result.term))

    def test_public_match_is_rechecked_by_reference(self):
        """A term the closures accept but the interpreter rejects is never returned."""
        engine = Engine(ORIGINAL)
        examples = [(([1, 2, 3],), [2, 3, 4])]
        result = engine.search(examples, LIST, [], budget=3000)
        self.assertIsNotNone(result.term)
        from rsi5.dsl.evaluator import evaluate
        self.assertEqual(evaluate(result.term, ([1, 2, 3],)).value, [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
