import unittest
from unittest.mock import patch

from rsi2.abstraction import description_length
from rsi2.corpus import Task
from rsi2.evaluator import evaluate
from rsi2.research import compression
from rsi2.terms import Int, Lam, Prim, Ref, Term, Var, apply
from rsi2.types import Arrow, INT, ListOf


def map_program():
    return apply(Prim("map"), apply(Prim("sub"), Int(1)))


def map_tasks():
    return [Task(name, Arrow(ListOf(INT), ListOf(INT)),
                 ((([],), []), (([2, 4],), [-1, -3])),
                 ((([-1, 3],), [2, -2]),)) for name in ("first", "second")]


def identity_tasks(count):
    return [Task(str(index), Arrow(INT, INT), (((0,), 0),), (((3,), 3),))
            for index in range(count)]


class ResearchCompressionTests(unittest.TestCase):
    def test_closed_application_is_extracted_and_outperforms_frozen_compressor(self):
        tasks = map_tasks()
        solutions = {task.name: map_program() for task in tasks}
        untouched = dict(solutions)
        result = compression.compare_compressors(solutions, {}, 2, tasks)
        self.assertEqual(solutions, untouched)
        self.assertEqual(result["original"]["records"], [])
        improved = result["improved"]
        self.assertEqual(improved["status"], "complete")
        self.assertEqual(improved["description_length_before"], 10)
        self.assertEqual(improved["description_length_after"], 7)
        self.assertEqual(len(improved["records"]), 1)
        record = improved["records"][0]
        self.assertEqual(record["delta"], 3)
        self.assertTrue(record["closed_callable_application"])
        self.assertFalse(record["identity_macro"])
        self.assertEqual(improved["library"][record["name"]], map_program())
        self.assertEqual(record["claim_scope"], compression.CLAIM_SCOPE)
        for task in tasks:
            for inputs, expected in task.examples + task.hidden:
                checked = evaluate(improved["solutions"][task.name], inputs,
                                   library=improved["library"])
                self.assertTrue(checked.ok)
                self.assertEqual(checked.value, expected)

    def test_every_profitable_proposal_checks_all_tasks_and_exact_costs_add(self):
        tasks = map_tasks()
        result = compression.compress_verified(
            {t.name: map_program() for t in tasks}, {}, 1, tasks)
        proofs = [result["baseline_verification"]] + [
            proposal["verification"] for proposal in result["proposals"]]
        self.assertGreater(len(proofs), 1)
        for proof in proofs:
            self.assertEqual(proof["cost"]["program_evaluations"], 2)
            self.assertEqual(proof["cost"]["example_evaluations"], 6)
            self.assertEqual(proof["cost"]["public_example_evaluations"], 4)
            self.assertEqual(proof["cost"]["hidden_example_evaluations"], 2)
            self.assertEqual([row["name"] for row in proof["tasks"]], ["first", "second"])
            self.assertEqual(proof["cost"]["evaluator_steps"],
                             sum(row["evaluator_steps"] for row in proof["tasks"]))
        for field in compression._WORK_FIELDS:
            self.assertEqual(result["cost"][field], sum(p["cost"][field] for p in proofs))
        record = result["records"][0]
        self.assertGreater(record["evaluator_steps_after"], record["evaluator_steps_before"])
        self.assertLess(description_length(result["solutions"], result["library"]), 10)

    def test_tiny_identity_strict_mdl_is_compression_only(self):
        term = Lam(INT, Var(0))
        tied = identity_tasks(2)
        no_gain = compression.compress_verified({t.name: term for t in tied}, {}, 1, tied)
        self.assertEqual(no_gain["records"], [])
        self.assertEqual(no_gain["description_length_after"], 4)
        tasks = identity_tasks(3)
        result = compression.compare_compressors({t.name: term for t in tasks}, {}, 1, tasks)
        self.assertEqual(result["original"]["records"], [])
        record = result["improved"]["records"][0]
        self.assertTrue(record["identity_macro"])
        self.assertTrue(record["tiny_entry"])
        self.assertEqual(record["delta"], 1)
        self.assertIn("RSI gains unmeasured", record["claim_scope"])

    def test_wrong_baseline_hidden_results_block_compression_without_early_exit(self):
        tasks = map_tasks()
        invalid = Task(tasks[0].name, tasks[0].request_type, tasks[0].examples,
                       ((([-1, 3],), [99, 99]), (([5],), [-4])))
        result = compression.compress_verified(
            {t.name: map_program() for t in tasks}, {}, 1, [invalid, tasks[1]])
        self.assertEqual(result["status"], "invalid_baseline")
        self.assertEqual(result["records"], [])
        self.assertEqual(result["proposals"], [])
        self.assertEqual(result["cost"]["example_evaluations"], 7)
        self.assertEqual(result["cost"]["hidden_example_evaluations"], 3)
        rows = result["baseline_verification"]["tasks"]
        self.assertFalse(rows[0]["passed"])
        self.assertTrue(rows[1]["passed"])

    def test_rewrite_resource_regression_is_vetoed_on_public_and_hidden(self):
        tasks = map_tasks()
        solutions = {t.name: map_program() for t in tasks}
        budget = max(evaluate(solutions[t.name], inputs).steps for t in tasks
                     for inputs, _ in t.examples + t.hidden)
        result = compression.compress_verified(solutions, {}, 1, tasks, step_budget=budget)
        self.assertTrue(result["baseline_verification"]["passed"])
        self.assertEqual(result["solutions"], solutions)
        self.assertEqual(result["library"], {})
        self.assertTrue(result["proposals"])
        for proposal in result["proposals"]:
            self.assertEqual(proposal["decision"], "rejected_verification")
            self.assertEqual(proposal["verification"]["cost"]["example_evaluations"], 6)
            failures = [failure for row in proposal["verification"]["tasks"]
                        for failure in row["failures"]]
            self.assertTrue(any(f["partition"] == "hidden" for f in failures))
            self.assertTrue(any(f["partition"] == "public" for f in failures))

    def test_independent_gate_rejects_a_semantically_corrupted_plan(self):
        tasks = map_tasks()
        solutions = {t.name: map_program() for t in tasks}
        original_plan = compression._plan

        def corrupt(term):
            return Int(2) if term == Int(1) else Term(
                term.tag, term.value, tuple(corrupt(child) for child in term.children))

        def faulty_plan(*args):
            planned = original_plan(*args)
            if planned is None:
                return None
            rewritten, entries, record = planned
            return rewritten, {**entries, record["name"]: corrupt(entries[record["name"]])}, record

        with patch.object(compression, "_plan", side_effect=faulty_plan):
            result = compression.compress_verified(solutions, {}, 1, tasks)
        self.assertEqual(result["solutions"], solutions)
        self.assertEqual(result["records"], [])
        self.assertTrue(result["proposals"])
        for proposal in result["proposals"]:
            proof = proposal["verification"]
            self.assertFalse(proof["passed"])
            self.assertEqual(proof["cost"]["example_evaluations"], 6)
            self.assertTrue(all(any(f["partition"] == "hidden" for f in row["failures"])
                                for row in proof["tasks"]))

    def test_lifted_open_subtrees_keep_outer_binders_and_task_types_distinct(self):
        def square_successor(index):
            successor = apply(Prim("add"), Var(index), Int(1))
            return apply(Prim("mul"), successor, successor)

        first = Lam(INT, apply(Prim("add"), square_successor(0), Int(10)))
        second = Lam(INT, Lam(INT, apply(Prim("sub"), square_successor(1), Var(0))))
        tasks = [Task("first", Arrow(INT, INT), (((-4,), 19), ((0,), 11)), (((8,), 91),)),
                 Task("second", Arrow(INT, Arrow(INT, INT)),
                      (((-4, 3), 6), ((0, 3), -2)), (((8, 3), 78),))]
        result = compression.compress_verified({"first": first, "second": second}, {}, 3, tasks)
        self.assertTrue(result["records"])
        self.assertTrue(result["final_verification"]["passed"])
        self.assertLess(result["description_length_after"], result["description_length_before"])
        self.assertTrue(any(r["source_tasks"] == ["first", "second"] for r in result["records"]))

    def test_existing_library_and_inputs_remain_unchanged(self):
        earlier = Lam(INT, apply(Prim("add"), Var(0), Int(1)))
        previous = {"earlier": earlier}
        invocation = apply(Ref("earlier"), Var(0))
        term = Lam(INT, apply(Prim("mul"), invocation, invocation))
        tasks = [Task(str(i), Arrow(INT, INT), (((5,), 36),), (((3,), 16),)) for i in range(4)]
        solutions = {t.name: term for t in tasks}
        result = compression.compress_verified(solutions, previous, 4, tasks)
        self.assertTrue(result["records"])
        self.assertEqual(previous, {"earlier": earlier})
        self.assertIs(result["library"]["earlier"], earlier)
        self.assertEqual(solutions, {t.name: term for t in tasks})
        self.assertTrue(result["final_verification"]["passed"])

    def test_missing_tasks_duplicate_ids_and_missing_evidence_fail_closed(self):
        task = identity_tasks(1)[0]
        solution = {task.name: Lam(INT, Var(0))}
        with self.assertRaisesRegex(ValueError, "lack supplied TRAIN"):
            compression.compress_verified(solution, {}, 1, [])
        with self.assertRaisesRegex(ValueError, "duplicate TRAIN"):
            compression.compress_verified(solution, {}, 1, [task, task])
        missing = Task(task.name, task.request_type, task.examples, ())
        result = compression.compress_verified(solution, {}, 1, [missing])
        self.assertEqual(result["status"], "invalid_baseline")
        self.assertFalse(result["final_verification"]["passed"])

    def test_bool_int_output_equality_is_not_accepted(self):
        task = Task("typed", Arrow(INT, INT), (((1,), True),), (((3,), 3),))
        proof = compression.verify_solutions({"typed": Lam(INT, Var(0))}, {}, [task])
        self.assertFalse(proof["passed"])
        self.assertEqual(proof["cost"]["example_evaluations"], 2)

    def test_explicit_proposal_limits_preserve_verified_source_and_empty_input(self):
        tasks = map_tasks()
        solutions = {t.name: map_program() for t in tasks}
        result = compression.compress_verified(solutions, {}, 1, tasks, max_proposals=0)
        self.assertEqual(result["solutions"], solutions)
        self.assertEqual(result["records"], [])
        self.assertEqual(result["cost"]["example_evaluations"], 6)
        capped = compression.compress_verified(solutions, {}, 1, tasks, max_proposals=1)
        self.assertEqual(capped["distinct_entries_examined"], 1)
        self.assertEqual(len(capped["records"]), 1)
        empty = compression.compress_verified({}, {}, 1, [])
        self.assertEqual(empty["status"], "complete")
        self.assertEqual(empty["cost"]["example_evaluations"], 0)
        self.assertEqual(empty["records"], [])


if __name__ == "__main__":
    unittest.main()
