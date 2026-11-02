"""The frozen checker language: values, primitives, bounds, determinism."""
import unittest

from swarm.kernel import checker_lang as cl


class CheckerLanguageTests(unittest.TestCase):
    def run_ok(self, program, *args):
        result = cl.run(program, list(args))
        self.assertTrue(result.ok, result.error)
        return result.value

    def test_arithmetic_lists_strings_tuples(self):
        self.assertEqual(self.run_ok(["lambda", ["x"], ["map", ["lambda", ["v"], ["*", "v", 2]], "x"]], [1, 2]), [2, 4])
        self.assertEqual(self.run_ok(["lambda", ["x"], ["fold", "+", 0, "x"]], [1, 2, 3]), 6)
        self.assertEqual(self.run_ok(["lambda", ["x"], ["sort", "x"]], [3, 1, 2]), [1, 2, 3])
        self.assertEqual(self.run_ok(["lambda", ["s"], ["str-join", ["reverse", ["chars", "s"]]]], "abc"), "cba")
        self.assertEqual(self.run_ok(["lambda", ["x"], ["fst", ["head", ["zip", "x", "x"]]]], [7, 8]), 7)
        self.assertEqual(self.run_ok(["lambda", ["x"], ["take", 2, ["drop", 1, "x"]]], [1, 2, 3, 4]), [2, 3])
        self.assertEqual(self.run_ok(["lambda", ["x"], ["if", ["empty?", "x"], 0, ["head", "x"]]], []), 0)
        self.assertEqual(self.run_ok(["lambda", ["x"], ["let", "n", ["len", "x"], ["*", "n", "n"]]], [1, 2, 3]), 9)

    def test_bounded_recursion(self):
        factorial = ["rec", "f", ["n"], ["if", ["<=", "n", 1], 1, ["*", "n", ["f", ["-", "n", 1]]]]]
        self.assertEqual(self.run_ok(factorial, 6), 720)
        loop = cl.run(["rec", "f", ["n"], ["f", ["+", "n", 1]]], [0])
        self.assertFalse(loop.ok)
        self.assertIn("depth", loop.error)

    def test_strict_types_and_errors(self):
        for program, args in ((["lambda", ["x"], ["+", "x", True]], [1]),
                              (["lambda", ["x"], ["head", "x"]], [[]]),
                              (["lambda", ["x"], ["div", "x", 0]], [1]),
                              (["lambda", ["x"], ["<", "x", ["str", "a"]]], [1]),
                              (["lambda", ["x"], ["unknown-prim", "x"]], [1]),
                              (["lambda", ["x"], ["nth", "x", 5]], [[1]])):
            self.assertFalse(cl.run(program, args).ok, program)

    def test_budget_and_size_limits(self):
        big = ["lambda", ["n"], ["range", "n"]]
        self.assertFalse(cl.run(big, [cl.MAX_LENGTH + 1]).ok)
        slow = ["lambda", ["x"], ["fold", ["lambda", ["a", "b"], ["+", "a", "b"]], 0, ["range", "x"]]]
        self.assertFalse(cl.run(slow, [4000], step_budget=100).ok)
        self.assertTrue(cl.run(slow, [40], step_budget=100000).ok)
        huge = ["lambda", ["x"], ["*", "x", "x"]]
        self.assertFalse(cl.run(huge, [2 ** 400]).ok)

    def test_checker_must_return_bool(self):
        self.assertFalse(cl.check(["lambda", ["x", "y"], 1], 1, 1).ok)
        self.assertTrue(cl.check(["lambda", ["x", "y"], ["=", "x", "y"]], 1, 1).value)

    def test_canonical_digest_and_validation(self):
        program = ["lambda", ["x"], ["+", "x", 1]]
        self.assertEqual(cl.digest(program), cl.digest(["lambda", ["x"], ["+", "x", 1]]))
        self.assertEqual(cl.size(program), 8)
        with self.assertRaises(cl.CheckerError):
            cl.validate(["lambda", "x", 1])
        with self.assertRaises(cl.CheckerError):
            cl.validate(["str", 5])
        deep = 1
        for _ in range(cl.MAX_AST_DEPTH + 2):
            deep = ["+", deep, 1]
        with self.assertRaises(cl.CheckerError):
            cl.validate(deep)

    def test_json_round_trip_of_tuples(self):
        value = (1, [2, (3, True)])
        self.assertEqual(cl.from_jsonable(cl.to_jsonable(value)), value)


if __name__ == "__main__":
    unittest.main()
