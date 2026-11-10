"""The engine findings of the Phase 1 adversarial review, pinned.

Each test builds the case a finding describes and asserts what the engine does today next
to what the reference interpreter does. None of these can turn a wrong program into a
solve (every returned program is re-checked by the interpreter and judged by the frozen
verifier); each loses programs the language has, or contradicts a document.

The repairs change which programs the engine enumerates, so they change the registered
numbers: they are deferred to a new registration (``RESULTS_P1.md``, "Adversarial review").
A test here fails when its finding is repaired; delete it together with the limitation it
pins. The findings on sealing and on the run driver were corrected instead: ``test_guard.py``
and ``test_sealing.py``.
"""
from types import SimpleNamespace
import unittest

from rsi5 import probes
from rsi5.dsl.evaluator import evaluate
from rsi5.dsl.terms import App, Int, Lam, Prim, Var, apply
from rsi5.dsl.types import Arrow, BOOL, INT, ListOf, arrows
from rsi5.dsl.vocabulary import ORIGINAL, RESTORED, Vocabulary
from rsi5.engine import closures
from rsi5.engine.bottomup import VECTOR, Engine
from rsi5.engine.closures import compile_term, run_closure
from rsi5.engine.normal_forms import COMMUTATIVE, normal
from rsi5.engine.oe import ERR

LIST = ListOf(INT)
STEPS = 2000                     # the registered step budget


def fast(program, *inputs):
    """The compiled closure of ``program`` applied to ``inputs``: (value, error)."""
    value, error = run_closure(compile_term(program), ())
    for argument in inputs:
        if error is None:
            value, error = run_closure(lambda env, budget, f=value, x=argument: f(x, budget), (), STEPS)
    return value, error


def literal(value):
    return SimpleNamespace(kind="const", head=value, args=(), ident=0, uses=frozenset())


class Semantics(unittest.TestCase):
    """The fast paths against the reference interpreter."""

    def test_and_or_short_circuit_in_the_reference_only(self):
        xs = Var(0)
        non_empty = apply(Prim("not"), apply(Prim("is_empty"), xs))
        head_is_one = apply(Prim("eq"), apply(Prim("head"), xs), Int(1))
        guarded = Lam(LIST, apply(Prim("and"), non_empty, head_is_one))
        swapped = Lam(LIST, apply(Prim("and"), head_is_one, non_empty))
        self.assertEqual(evaluate(guarded, ([],)).value, False)       # the reference skips the right side
        self.assertFalse(evaluate(swapped, ([],)).ok)                 # so `and` does not commute
        self.assertIs(VECTOR["and"]([False], [ERR])[0], ERR)          # the vectorised `and` is strict
        self.assertIs(VECTOR["or"]([True], [ERR])[0], ERR)
        self.assertIn("and", COMMUTATIVE)                             # and the filter orders its arguments
        self.assertIn("or", COMMUTATIVE)
        # Consequence: without `if`, a task whose solution is the guarded conjunction is lost.
        examples = [(([],), False), (([1],), True), (([2],), False), (([1, 2],), True), (([0, 1],), False)]
        for inputs, expected in examples:
            self.assertEqual(evaluate(guarded, inputs).value, expected)
        tiny = Vocabulary("tiny", ("and", "or", "not", "is_empty", "eq", "head"), (1,), ())
        result = Engine(tiny, max_size=9).search(examples, Arrow(LIST, BOOL), probes.inputs_for((LIST,)),
                                                 budget=3000)
        self.assertIsNone(result.term)
        self.assertTrue(result.exhausted)
        # With `if` in the vocabulary (both registered vocabularies) the behaviour stays reachable.
        with_if = Vocabulary("tiny_if", tiny.primitives + ("if",), (1,), (False, True))
        found = Engine(with_if, max_size=9).search(examples, Arrow(LIST, BOOL), probes.inputs_for((LIST,)),
                                                   budget=3000)
        self.assertIn("if", str(found.term))

    def test_add_and_sub_have_no_bit_limit_in_the_fast_paths(self):
        square = Lam(INT, Lam(INT, apply(Prim("mul"), Var(1), Var(1))))
        big = apply(Prim("fold"), square, Int(2), apply(Prim("range"), Int(11)))        # 2 ** 2048
        most = apply(Prim("mul"), big, apply(Prim("div"), big, Int(2)))                 # 2 ** 4095: allowed
        doubled = Lam(INT, apply(Prim("add"), most, most))                              # 2 ** 4096: too wide
        reference = evaluate(doubled, (0,), step_budget=STEPS)
        self.assertFalse(reference.ok)
        self.assertIn("bit limit", reference.error)
        value, error = fast(doubled, 0)
        self.assertIsNone(error)
        self.assertEqual(value.bit_length(), 4097)
        self.assertEqual(VECTOR["add"]([1 << 4095], [1 << 4095])[0].bit_length(), 4097)
        self.assertEqual(VECTOR["sub"]([1 << 4095], [-(1 << 4095)])[0].bit_length(), 4097)

    def test_closures_charge_fewer_steps_than_the_reference(self):
        body = Lam(INT, apply(Prim("add"), apply(Prim("mul"), Var(0), Var(0)), Int(1)))
        program = Lam(LIST, apply(Prim("map"), body, Var(0)))
        xs = list(range(200))
        reference = evaluate(program, (xs,), step_budget=STEPS)
        self.assertEqual((reference.ok, reference.error), (False, "budget_exhausted"))
        self.assertEqual(fast(program, xs), ([x * x + 1 for x in xs], None))

    def test_closure_list_cap_is_below_the_reference_cap(self):
        program = Lam(INT, apply(Prim("length"), apply(Prim("range"), Var(0))))
        self.assertEqual(closures.LIST_CAP, 1024)
        self.assertEqual(evaluate(program, (1025,), step_budget=STEPS).value, 1025)
        self.assertEqual(fast(program, 1025), (None, "Fail"))

    def test_fix1_seed_is_strict_in_the_closures(self):
        # fix1 (head xs) (λrec. λy. if (is_empty xs) 0 (rec y)): on [] the seed is never needed.
        body = Lam(Arrow(INT, INT), Lam(INT, apply(Prim("if"), apply(Prim("is_empty"), Var(2)), Int(0),
                                                   App(Var(1), Var(0)))))
        program = Lam(LIST, apply(Prim("fix1"), apply(Prim("head"), Var(0)), body))
        self.assertEqual(evaluate(program, ([],), step_budget=STEPS).value, 0)
        self.assertEqual(fast(program, []), (None, "Fail"))

    def test_vectorised_is_prime_is_not_charged(self):
        program = Lam(INT, apply(Prim("is_prime"), Var(0)))
        prime = 1_000_000_007                    # about 15,800 trial divisions: over the step budget
        reference = evaluate(program, (prime,), step_budget=STEPS)
        self.assertEqual((reference.ok, reference.error), (False, "budget_exhausted"))
        self.assertEqual(VECTOR["is_prime"]([prime]), [True])         # answered, no step charged
        wide = (1 << 65) + 1                     # divisible by 3
        self.assertEqual(evaluate(program, (wide,), step_budget=STEPS).value, False)
        self.assertIs(VECTOR["is_prime"]([wide])[0], ERR)             # refused above 64 bits


class NormalForms(unittest.TestCase):
    """Rules of ``NORMAL_FORMS.md`` whose refused form has no equivalent the engine builds."""

    def test_neg_of_a_literal_is_refused_without_an_equivalent_literal(self):
        for vocabulary, lost in ((ORIGINAL, (2,)), (RESTORED, (2, 3, 4, 5))):
            for k in lost:
                self.assertIn(k, vocabulary.integer_constants)
                self.assertNotIn(-k, vocabulary.integer_constants)
                self.assertFalse(normal("neg", (literal(k),)))
        # -2 is therefore built from three symbols where `neg 2` would be two.
        examples = [(([1, 2],), [-2, 1, 2]), (([],), [-2]), (([5],), [-2, 5]), (([0, 0, 3],), [-2, 0, 0, 3])]
        result = Engine(ORIGINAL).search(examples, Arrow(LIST, LIST), probes.inputs_for((LIST,)), budget=20000)
        self.assertEqual(str(result.term), "(lambda x0: list[int]. ((cons ((add -1) -1)) x0))")

    def test_fix1_without_recursion_is_refused_although_it_binds_a_value(self):
        # fix1 x (λrec. λy. body) with rec unused is `let y = x in body`: when y occurs several
        # times and x is large, the substituted body is longer, and it may not be built at all.
        body = SimpleNamespace(kind="prim", head="add", args=(), ident=3, uses=frozenset({0}))
        function = SimpleNamespace(kind="lam", head=(Arrow(LIST, INT), LIST), args=(body,), ident=4,
                                   uses=frozenset())
        seed = SimpleNamespace(kind="prim", head="tail", args=(), ident=2, uses=frozenset({0}))
        self.assertFalse(normal("fix1", (seed, function)))
        recursive = SimpleNamespace(kind="prim", head="add", args=(), ident=3, uses=frozenset({0, 1}))
        function.args = (recursive,)
        self.assertTrue(normal("fix1", (seed, function)))


class Search(unittest.TestCase):
    """The search loop."""

    def test_two_input_match_is_wrapped_with_its_binders_reversed(self):
        request = arrows(INT, LIST, LIST)                             # f(n, xs) = cons n xs
        examples = [((7, [1, 2]), [7, 1, 2]), ((0, []), [0]), ((3, [3]), [3, 3])]
        body = apply(Prim("cons"), Var(1), Var(0))
        correct = Lam(INT, Lam(LIST, body))
        for inputs, expected in examples:
            self.assertEqual(evaluate(correct, inputs).value, expected)
        result = Engine(ORIGINAL).search(examples, request, [], budget=3000)
        self.assertIsNone(result.term)             # the match was found, mis-annotated and rejected
        self.assertEqual(result.spurious, 1)       # and its behaviour class is never re-checked
        self.assertEqual(result.candidates, 3000)
        # Every task of the eight exposed partitions has one input; the registered run is unaffected.

    def test_lambda_nesting_limit_counts_binders(self):
        """A lambda is built only where fewer than two binders are in scope: at the top and in
        the body of a one-binder lambda. A two-binder body (`fold`, `fix1`) holds none, and
        contexts reach three binders (a `fold` inside a `map` body)."""
        examples = [((list(range(n)),), [-999]) for n in range(6)]    # unreachable target
        engine = Engine(ORIGINAL)
        result = engine.search(examples, Arrow(LIST, LIST), probes.inputs_for((LIST,)), budget=20000)
        higher_order = {context.depth for context in engine.contexts for pool in context.pools.values()
                        for program in pool if program.kind == "prim" and program.head in ("map", "filter", "fold")}
        self.assertEqual(higher_order, {0, 1})
        self.assertEqual(max(context.depth for context in engine.contexts), 3)
        self.assertTrue(any(context.depth >= 2 and context.oe.size() for context in engine.contexts))
        # Child contexts are created when a level's shapes are listed, before any program needs
        # them: the `contexts` count of a record includes contexts that hold nothing.
        self.assertEqual(result.contexts, len(engine.contexts))
        self.assertTrue(any(context.completed_size == 0 for context in engine.contexts))

    def test_exhausted_flag_fires_on_one_empty_level(self):
        tiny = Vocabulary("tiny", ("add",), (1,))
        examples = [((1,), 3), ((2,), 6), ((5,), 15)]                 # add (add x x) x: 5 symbols
        triple = Lam(INT, apply(Prim("add"), apply(Prim("add"), Var(0), Var(0)), Var(0)))
        for inputs, expected in examples:
            self.assertEqual(evaluate(triple, inputs).value, expected)
        result = Engine(tiny, max_size=12).search(examples, Arrow(INT, INT), [], budget=3000)
        self.assertTrue(result.exhausted)          # size 2 adds nothing: `add` builds odd sizes only
        self.assertIsNone(result.term)
        self.assertEqual(result.completed_size, 2)
        # No record of the registered run has the flag set (test below): every search without
        # a public match spent its whole budget.


class RegisteredRun(unittest.TestCase):
    """What the findings above did to the registered files, read from the files."""

    def test_registered_records_show_no_exhaustion_no_spurious_match_and_one_input(self):
        import json
        from pathlib import Path
        files = sorted((Path(__file__).resolve().parents[1] / "results_p1").glob("*_*.json"))
        self.assertEqual(len(files), 16)
        records = 0
        for path in files:
            result = json.loads(path.read_text(encoding="utf-8"))
            for record in result["records"]:
                records += 1
                self.assertFalse(record["exhausted"], record["name"])
                self.assertEqual(record["spurious"], 0, record["name"])
                self.assertTrue(record["request_type"].startswith("list[int] -> "), record["name"])
                if not record["public_match"]:
                    self.assertEqual(record["candidates"], result["plan"]["budget"], record["name"])
        self.assertEqual(records, 676)


if __name__ == "__main__":
    unittest.main()
