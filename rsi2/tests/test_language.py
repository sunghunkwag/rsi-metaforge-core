"""Executable checks for the frozen typed language and evaluator contracts."""

import unittest

from rsi2.evaluator import evaluate
from rsi2.terms import App, Bool, Int, Lam, Prim, Ref, Var, apply
from rsi2.types import Arrow, BOOL, INT, ListOf, TVar, TypeInferenceError, infer


def increment():
    return Lam(INT, apply(Prim("add"), Var(0), Int(1)))


def sum_function():
    return Lam(INT, Lam(INT, apply(Prim("add"), Var(1), Var(0))))


class TypeInferenceTests(unittest.TestCase):
    def test_de_bruijn_variables_have_their_binding_types(self):
        term = Lam(INT, Lam(BOOL, Var(1)))
        self.assertEqual(infer(term), Arrow(INT, Arrow(BOOL, INT)))
        result = evaluate(term, inputs=(7, False))
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, 7)

    def test_polymorphic_list_primitives_instantiate_independently(self):
        ints = apply(Prim("cons"), Int(3), Prim("nil"))
        bools = apply(Prim("cons"), Bool(True), Prim("nil"))
        self.assertEqual(infer(ints), ListOf(INT))
        self.assertEqual(infer(bools), ListOf(BOOL))
        self.assertEqual(infer(apply(Prim("head"), ints)), INT)
        self.assertEqual(infer(apply(Prim("head"), bools)), BOOL)

    def test_polymorphic_library_reference_is_freshened_at_each_use(self):
        variable = TVar("identity_input")
        library = {"identity": Lam(variable, Var(0))}
        term = apply(
            Prim("if"),
            apply(Ref("identity"), Bool(True)),
            apply(Ref("identity"), Int(19)),
            Int(0),
        )
        self.assertEqual(infer(term, library=library), INT)
        result = evaluate(term, library=library)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, 19)

    def test_cached_polymorphic_inference_is_not_contaminated_by_evaluation(self):
        variable = TVar("cached_identity_input")
        identity = Lam(variable, Var(0))
        principal_type = infer(identity)
        values = (3, True, [1, 2], [], [True, False], -7, False, 3)
        for value in values:
            with self.subTest(value=value):
                result = evaluate(identity, inputs=(value,))
                self.assertTrue(result.ok, result.error)
                self.assertEqual(result.value, value)
                self.assertIs(type(result.value), type(value))
                self.assertEqual(infer(identity), principal_type)

    def test_ill_typed_applications_and_unbound_variables_are_rejected(self):
        terms = (
            apply(Prim("add"), Bool(True), Int(1)),
            apply(Prim("if"), Bool(True), Int(1), Bool(False)),
            apply(Prim("cons"), Bool(True), apply(Prim("range"), Int(3))),
            apply(Prim("map"), increment(),
                  apply(Prim("cons"), Bool(True), Prim("nil"))),
            App(Int(1), Int(2)),
            Var(0),
        )
        for term in terms:
            with self.subTest(term=term):
                with self.assertRaises(TypeInferenceError):
                    infer(term)


class EvaluationTests(unittest.TestCase):
    def assert_success(self, term, value, **kwargs):
        result = evaluate(term, **kwargs)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, value)
        self.assertGreater(result.steps, 0)
        return result

    def assert_budget_failure(self, term, budget, **kwargs):
        result = evaluate(term, step_budget=budget, **kwargs)
        self.assertFalse(result.ok)
        self.assertTrue(result.error.startswith("budget_exhausted"), result.error)
        self.assertLessEqual(result.steps, max(0, budget))
        return result

    def test_curried_functions_respect_de_bruijn_argument_order(self):
        subtract = Lam(INT, Lam(INT, apply(Prim("sub"), Var(1), Var(0))))
        self.assert_success(subtract, 5, inputs=(8, 3))

    def test_if_evaluates_only_the_chosen_branch(self):
        invalid = apply(Prim("div"), Int(1), Int(0))
        self.assert_success(apply(Prim("if"), Bool(True), Int(42), invalid), 42)
        selected = evaluate(apply(Prim("if"), Bool(False), Int(42), invalid))
        self.assertFalse(selected.ok)
        self.assertTrue(selected.error.startswith("runtime_error"), selected.error)

    def test_map_filter_and_fold_return_known_outputs(self):
        numbers = apply(Prim("range"), Int(6))
        self.assert_success(apply(Prim("map"), increment(), numbers), [1, 2, 3, 4, 5, 6])
        even = Lam(INT, apply(Prim("eq"), apply(Prim("mod"), Var(0), Int(2)), Int(0)))
        self.assert_success(apply(Prim("filter"), even, numbers), [0, 2, 4])
        self.assert_success(apply(Prim("fold"), sum_function(), Int(0), numbers), 15)

    def test_named_parameterized_libraries_are_callable_and_composable(self):
        twice = Lam(INT, apply(Ref("increment"), apply(Ref("increment"), Var(0))))
        library = {
            "increment": increment(),
            "twice": (Arrow(INT, INT), twice),
            "increment_all": Lam(ListOf(INT), apply(Prim("map"), Ref("increment"), Var(0))),
        }
        self.assertEqual(infer(Ref("twice"), library=library), Arrow(INT, INT))
        self.assert_success(apply(Ref("twice"), Int(5)), 7, library=library)
        self.assert_success(
            apply(Ref("increment_all"), apply(Prim("range"), Int(4))),
            [1, 2, 3, 4], library=library,
        )

    def test_zero_and_negative_budgets_return_failure(self):
        self.assert_budget_failure(Int(1), 0)
        invalid_budget = evaluate(Int(1), step_budget=-10)
        self.assertFalse(invalid_budget.ok)
        self.assertIsInstance(invalid_budget.error, str)
        self.assertEqual(invalid_budget.steps, 0)

    def test_huge_range_fails_before_allocating_the_list(self):
        self.assert_budget_failure(apply(Prim("range"), Int(10**12)), 32)

    def test_list_combinators_cannot_hide_unbounded_work(self):
        numbers = apply(Prim("range"), Int(200))
        predicate = Lam(INT, apply(Prim("gt"), Var(0), Int(100)))
        cases = (
            (apply(Prim("map"), increment(), numbers), list(range(1, 201))),
            (apply(Prim("filter"), predicate, numbers), list(range(101, 200))),
            (apply(Prim("fold"), sum_function(), Int(0), numbers), 19900),
        )
        for term, expected in cases:
            with self.subTest(term=term):
                self.assert_success(term, expected, step_budget=20000)
                self.assert_budget_failure(term, 400)

    def test_input_validation_is_also_bounded(self):
        first = Lam(ListOf(INT), apply(Prim("head"), Var(0)))
        self.assert_budget_failure(first, 32, inputs=([1] * 10000,))

    def test_runtime_and_type_failures_do_not_escape(self):
        cases = (
            (apply(Prim("div"), Int(1), Int(0)), {}),
            (apply(Prim("mod"), Int(1), Int(0)), {}),
            (apply(Prim("head"), Prim("nil")), {}),
            (apply(Prim("add"), Bool(True), Int(1)), {}),
            (Ref("missing"), {}),
            (Lam(INT, Var(0)), {"inputs": (object(),)}),
        )
        for term, kwargs in cases:
            with self.subTest(term=term):
                result = evaluate(term, **kwargs)
                self.assertFalse(result.ok)
                self.assertIsInstance(result.error, str)
                self.assertLessEqual(result.steps, 1000)


if __name__ == "__main__":
    unittest.main()
