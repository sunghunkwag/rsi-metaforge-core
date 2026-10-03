import unittest

from rsi2.abstraction import description_length, free_variables, learn_abstractions, lift_subtree
from rsi2.evaluator import evaluate
from rsi2.terms import Bool, Int, Lam, Prim, Ref, Var, apply, term_from_dict
from rsi2.types import INT, infer, unify


def polynomial(constant):
    x = Var(0)
    return Lam(INT, apply(Prim("add"), apply(Prim("mul"), x, Int(5)),
                          apply(Prim("add"), apply(Prim("mul"), x, Int(3)), Int(constant))))


class AbstractionTests(unittest.TestCase):
    def test_lift_keeps_internal_and_outer_binders_distinct(self):
        subtree = Lam(INT, apply(Prim("add"), Var(0), Var(2)))
        self.assertEqual(free_variables(subtree), (1,))
        entry, arguments = lift_subtree(subtree, (INT, INT))
        self.assertEqual(arguments, (Var(1),))
        original = Lam(INT, Lam(INT, subtree))
        rewritten = Lam(INT, Lam(INT, apply(Ref("lifted"), *arguments)))
        for first, second, third in ((7, 100, 4), (-3, 9, 2), (0, -10, 0)):
            before = evaluate(original, (first, second, third), step_budget=1000)
            after = evaluate(rewritten, (first, second, third), library={"lifted": entry}, step_budget=1000)
            self.assertTrue(before.ok and after.ok, (before, after))
            self.assertEqual(before.value, after.value)
        self.assertEqual(evaluate(entry, (7, 4)).value, 11)

    def test_lift_parameter_order_tracks_first_use(self):
        subtree = apply(Prim("sub"), Var(2), Var(0))
        entry, arguments = lift_subtree(subtree, (INT, INT, INT))
        self.assertEqual(free_variables(subtree), (2, 0))
        self.assertEqual(arguments, (Var(2), Var(0)))
        self.assertEqual(evaluate(entry, (20, 3)).value, 17)

    def test_literal_hole_under_lambda_avoids_capture(self):
        subtree = Lam(INT, apply(Prim("sub"), Var(0), Int(7)))
        entry, arguments = lift_subtree(subtree, (), ((0, 1),))
        self.assertEqual(arguments, (Int(7),))
        self.assertEqual(evaluate(entry, (7, 12)).value, 5)

    def test_literal_antiunification_reduces_full_cost_and_preserves_outputs(self):
        solutions = {f"task_{i}": polynomial(i) for i in range(8)}
        saved = dict(solutions)
        rewritten, library, records = learn_abstractions(solutions, {}, generation=3)
        self.assertEqual(solutions, saved)
        self.assertTrue(records)
        self.assertLess(description_length(rewritten, library), description_length(solutions, {}))
        self.assertLessEqual(len(records), 8)
        for record in records:
            self.assertEqual(record["generation"], 3)
            self.assertEqual(record["delta"], record["cost_before"] - record["cost_after"])
            self.assertGreater(record["delta"], 0)
            self.assertGreaterEqual(record["support"], 2)
            self.assertEqual(term_from_dict(record["term_dict"]), library[record["name"]])
            self.assertEqual(library[record["name"]].tag, "lam")
        for name, original in solutions.items():
            unify(infer(original), infer(rewritten[name], library=library))
            for value in (-7, 0, 13):
                before = evaluate(original, (value,), step_budget=10000)
                after = evaluate(rewritten[name], (value,), library=library, step_budget=10000)
                self.assertTrue(before.ok and after.ok, (before, after))
                self.assertEqual(before.value, after.value)
        self.assertTrue(any(len(r["source_tasks"]) >= 8 for r in records))

    def test_existing_library_dependency_is_preserved(self):
        old_entry = Lam(INT, apply(Prim("add"), Var(0), Int(1)))
        previous = {"earlier": old_entry}
        application = apply(Ref("earlier"), Var(0))
        program = Lam(INT, apply(Prim("mul"), application, application))
        solutions = {f"task_{i}": program for i in range(4)}
        rewritten, library, records = learn_abstractions(solutions, previous, generation=4)
        self.assertTrue(records)
        self.assertEqual(previous, {"earlier": old_entry})
        self.assertIs(library["earlier"], old_entry)
        self.assertIn("earlier", records[0]["readable_term"])
        preceding = {}
        for name, term in library.items():
            infer(term, library=preceding)
            preceding[name] = term
        for name, term in rewritten.items():
            self.assertEqual(evaluate(term, (5,), library=library).value, 36)

    def test_learning_shares_body_across_different_outer_indices(self):
        def square_successor(index):
            successor = apply(Prim("add"), Var(index), Int(1))
            return apply(Prim("mul"), successor, successor)

        first = Lam(INT, apply(Prim("add"), square_successor(0), Int(10)))
        second = Lam(INT, Lam(INT, apply(Prim("sub"), square_successor(1), Var(0))))
        solutions = {"first": first, "second": second}
        rewritten, library, records = learn_abstractions(solutions, {}, 1)
        self.assertTrue(records)
        self.assertIn("first", records[0]["source_tasks"])
        self.assertIn("second", records[0]["source_tasks"])
        for value in (-4, 0, 8):
            self.assertEqual(evaluate(rewritten["first"], (value,), library=library).value,
                             (value + 1) ** 2 + 10)
            self.assertEqual(evaluate(rewritten["second"], (value, 3), library=library).value,
                             (value + 1) ** 2 - 3)

    def test_insufficient_savings_does_not_add_library_cost(self):
        solutions = {"one": polynomial(2)}
        rewritten, library, records = learn_abstractions(solutions, {}, generation=0)
        self.assertEqual(rewritten, solutions)
        self.assertEqual(library, {})
        self.assertEqual(records, [])

    def test_empty_solutions_and_deterministic_adoption(self):
        self.assertEqual(learn_abstractions({}, {}, 0), ({}, {}, []))
        solutions = {str(i): polynomial(i) for i in range(6)}
        first = learn_abstractions(solutions, {}, 2)
        second = learn_abstractions(dict(reversed(list(solutions.items()))), {}, 2)
        self.assertEqual(first, second)

    def test_polymorphic_record_types_do_not_depend_on_fresh_inference_ids(self):
        term = Lam(INT, apply(Prim("if"), Bool(True),
                               Prim("nil"), apply(Prim("tail"), Prim("nil"))))
        solutions = {str(i): term for i in range(4)}
        first = learn_abstractions(solutions, {}, 2)
        second = learn_abstractions(solutions, {}, 2)
        self.assertTrue(first[2])
        self.assertEqual(first, second)
        self.assertEqual(evaluate(first[0]["0"], (5,), library=first[1]).value, [])


if __name__ == "__main__":
    unittest.main()
