"""Synthetic public traces test the preregistered failure-credit evidence."""
from dataclasses import replace
from fractions import Fraction
import json
import unittest
from unittest.mock import patch

from rsi2.grammar import Grammar
from rsi2.research.failure_preferences import (
    ExtractionWork, Preference, PreferenceMemory, PublicTask, canonical_term,
    exact_residual, extract_preferences, quality, typed_equal,
)
from rsi2.terms import Int, Lam, Prim, Ref, Term, Var, apply
from rsi2.types import Arrow, INT, ListOf, PRIMITIVE_TYPES, TVar


def trial(identifier, term, outputs, parent=None, **changes):
    record = {"id": identifier, "parent_id": parent, "term": term.to_dict(),
              "raw_term": term.to_dict(), "outputs": outputs,
              "runtime_failure": None, "incomplete": False,
              "heuristic_incomplete": False, "matched_examples": 999}
    record.update(changes)
    return record


def extract(task, trials, grammar=None, generation=0):
    return extract_preferences(task, {"trials": trials}, grammar or Grammar(),
                               fitting_names={task.name}, generation=generation)


def constant_case():
    task = PublicTask("public-constant", INT, (((), 2),))
    grammar = Grammar(primitives={}, constants=(Int(0), Int(1), Int(2)))
    trials = [trial(0, Int(0), [0]), trial(1, Int(1), [1], 0)]
    return task, trials, grammar


class FailurePreferenceTests(unittest.TestCase):
    def test_exact_residual_preserves_types_and_arbitrary_integer_precision(self):
        self.assertFalse(typed_equal([True, [False]], [1, [0]]))
        self.assertTrue(typed_equal([1, [False]], [1, [False]]))
        self.assertEqual(exact_residual(True, 1), Fraction(1))
        self.assertEqual(exact_residual(False, True), Fraction(1))
        self.assertEqual(exact_residual([], []), Fraction(0))
        self.assertEqual(exact_residual([1, [0]], [2]), Fraction(1, 2) + Fraction(1, 8))
        huge = 10 ** 1000
        self.assertEqual(exact_residual(huge + 1, huge), Fraction(1, 2 * huge + 2))
        work = ExtractionWork()
        self.assertEqual(exact_residual([1], [2], work), Fraction(1, 4))
        self.assertEqual(work.compared_value_nodes, 2)
        self.assertEqual(work.fraction_constructions, 2)
        self.assertEqual(work.fraction_operations, 4)

    def test_quality_is_exact_mean_with_no_truncation_or_error_sentinel(self):
        examples = (((), 1), ((), 2))
        self.assertEqual(quality([True, 1], examples), (0, Fraction(5, 8)))
        for outputs in ([], [1], [1, 2, 3], (1, 2)):
            with self.assertRaises(ValueError):
                quality(outputs, examples)
        with self.assertRaises(ValueError):
            quality([], ())
        with self.assertRaises(TypeError):
            quality([[0, "unknown"]], (((), []),))

    def test_extract_uses_recorded_outputs_without_interpreter_or_hidden_access(self):
        class OnlyPublic:
            name = "public-constant"
            request_type = INT
            examples = (((), 2),)

            @property
            def hidden(self):
                raise AssertionError("hidden examples accessed")

        _, trials, grammar = constant_case()
        with patch("rsi2.evaluator.evaluate", side_effect=AssertionError("interpreter call")):
            records, work = extract(OnlyPublic(), trials, grammar)
        self.assertEqual(len(records), 1)
        self.assertEqual(work.semantic_evaluator_calls, 0)
        self.assertEqual(work.eligible_preferences, 1)
        self.assertEqual(work.compiler_invocations, 2)
        self.assertEqual(work.production_queries, 2)
        self.assertEqual(work.decision_events, 2)
        self.assertGreater(work.fraction_operations, 0)
        self.assertGreater(work.cpu_seconds, 0)
        self.assertGreater(work.wall_seconds, 0)
        self.assertEqual({records[0].lo_quality[0], records[0].hi_quality[0]}, {0})

    def test_filter_runs_before_any_public_data_or_grammar_access(self):
        class Excluded:
            name = "shadow"

            @property
            def examples(self):
                raise AssertionError("filtered task read")

        records, work = extract_preferences(Excluded(), None, None, fitting_names={"fit"})
        self.assertEqual(records, [])
        self.assertEqual(work.task_filter_rejections, 1)
        self.assertEqual(work.exclusions[0]["reason"], "outside_fitting_group")

    def test_all_ineligible_edges_preserve_explicit_reasons_and_original_evidence(self):
        task, base, grammar = constant_case()
        cases = [({"runtime_failure": "limit", "outputs": []}, "runtime_failure"),
                 ({"incomplete": True}, "incomplete_assessment"),
                 ({"heuristic_incomplete": True}, "incomplete_assessment"),
                 ({"public_incomplete": True}, "incomplete_assessment"),
                 ({"outputs": []}, "invalid_outputs"),
                 ({"outputs": [1, 1]}, "invalid_outputs"),
                 ({"outputs": [1.0]}, "invalid_outputs"),
                 ({"parent_id": 99}, "missing_parent"),
                 ({"parent_id": [0]}, "missing_parent")]
        for changes, reason in cases:
            with self.subTest(changes=changes):
                child = {**base[1], **changes}
                records, work = extract(task, [base[0], child], grammar)
                self.assertEqual(records, [])
                self.assertEqual(work.exclusions[0]["reason"], reason)
                self.assertEqual(work.exclusions[0]["child"]["raw_term"], child["raw_term"])
        for key in ("runtime_failure", "incomplete", "heuristic_incomplete", "raw_term"):
            child = dict(base[1])
            del child[key]
            records, work = extract(task, [base[0], child], grammar)
            self.assertFalse(records)
            self.assertEqual(work.exclusions[0]["reason"], "unknown_evidence")

    def test_incomplete_or_untypable_terms_are_excluded(self):
        task, trials, grammar = constant_case()
        for bad in (Term("hole", INT), Var(0), Prim("nil")):
            with self.subTest(term=bad):
                records, work = extract(task, [trials[0], trial(1, bad, [1], 0)], grammar)
                self.assertFalse(records)
                self.assertEqual(work.excluded_syntax, 1)

    def test_exact_match_count_outranks_residual_and_size(self):
        task = PublicTask("lexicographic", INT, (((), 1), ((), 100)))
        grammar = Grammar(primitives={}, constants=(Int(0), Int(1)))
        records, _ = extract(task, [trial(0, Int(0), [0, 99]),
                                  trial(1, Int(1), [1, -10000], 0)], grammar)
        record = records[0]
        preferred = record.hi if record.label == 1 else record.lo
        self.assertEqual(preferred, Int(1))
        better = record.hi_quality if record.label == 1 else record.lo_quality
        worse = record.lo_quality if record.label == 1 else record.hi_quality
        self.assertEqual(better[0], 1)
        self.assertGreater(better[1], worse[1])

    def test_real_empty_list_output_is_distinct_from_missing_output_vector(self):
        task = PublicTask("empty-list", ListOf(INT), (((), []),))
        grammar = Grammar(primitives={k: PRIMITIVE_TYPES[k] for k in ("nil", "cons")},
                          constants=(Int(0),))
        cons = apply(Prim("cons"), Int(0), Prim("nil"))
        records, _ = extract(task, [trial(0, cons, [[0]]), trial(1, Prim("nil"), [[]], 0)], grammar)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].request_type, ListOf(INT))

    def test_shared_contexts_cancel_and_canonical_orientation_ignores_quality(self):
        task = PublicTask("mapped", Arrow(ListOf(INT), ListOf(INT)),
                          ((([1, 2],), [-1, -2]),))
        parent = Lam(ListOf(INT), apply(Prim("map"), Prim("abs"), Var(0)))
        child = Lam(ListOf(INT), apply(Prim("map"), Prim("neg"), Var(0)))
        grammar = Grammar(primitives={k: PRIMITIVE_TYPES[k] for k in ("map", "abs", "neg")})
        records, _ = extract(task, [trial(0, parent, [[1, 2]]), trial(1, child, [[-1, -2]], 0)], grammar)
        record = records[0]
        self.assertLess(record.lo_fingerprint, record.hi_fingerprint)
        self.assertEqual({key for _, key, _ in record.difference}, {"abs/0", "neg/0"})
        self.assertTrue(all(context == ("map", 0) for context, _, _ in record.difference))
        signed = {(c, p): n * record.label for c, p, n in record.difference}
        self.assertEqual(signed[("map", 0), "neg/0"], 1)
        self.assertEqual(signed[("map", 0), "abs/0"], -1)
        self.assertIn((("ROOT", 0), "lambda/1"), record.lo_decisions)
        self.assertEqual(record.parent_current, parent)
        self.assertEqual(record.child_current, child)

    def test_equal_quality_and_contextually_zero_differences_do_not_teach(self):
        task, trials, grammar = constant_case()
        records, work = extract(task, [trials[0], trial(1, Int(1), [0], 0)], grammar)
        self.assertFalse(records)
        self.assertEqual(work.quality_ties, 1)
        records, work = extract(task, [trials[0], trial(1, Int(0), [1], 0)], grammar)
        self.assertFalse(records)
        self.assertEqual(work.zero_differences, 1)

    def test_annotation_alpha_canonicalization_preserves_raw_ast_and_deduplicates(self):
        task = PublicTask("alpha", Arrow(INT, INT), (((2,), 3),))
        grammar = Grammar(primitives={}, constants=(Int(0),))
        traces = []
        for name in ("fresh_123", "fresh_456"):
            parent, child = Lam(TVar(name), Int(0)), Lam(TVar(name), Var(0))
            records, _ = extract(task, [trial(0, parent, [0]), trial(1, child, [2], 0)], grammar)
            traces.append(records[0])
            self.assertEqual(records[0].parent_raw, parent)
            self.assertEqual(records[0].request_type, task.request_type)
        self.assertEqual(traces[0].key, traces[1].key)
        memory = PreferenceMemory()
        self.assertEqual(memory.add(traces), 1)
        self.assertEqual(memory.duplicates, 1)
        self.assertEqual(len(memory.occurrences), 2)
        self.assertEqual(canonical_term(traces[0].parent_raw), canonical_term(traces[1].parent_raw))

    def test_original_library_snapshot_survives_source_mutation_and_roundtrip(self):
        task = PublicTask("library", INT, (((), 2),))
        library = {"entry": (INT, Int(1))}
        grammar = Grammar(library=library, primitives={}, constants=(Int(0), Int(1), Int(2)))
        records, work = extract(task, [trial(0, Int(0), [0]), trial(1, Ref("entry"), [1], 0)], grammar)
        self.assertEqual(len(records), 1)
        library["entry"] = Int(2)
        saved = json.loads(records[0].grammar_snapshot)["library"][0]
        self.assertEqual(saved["term"], Int(1).to_dict())
        self.assertEqual(saved["type"], INT.to_dict())
        memory = PreferenceMemory()
        memory.add(records, work.exclusions)
        other = PreferenceMemory.from_dict(json.loads(json.dumps(memory.to_dict())))
        self.assertEqual(other.records(), memory.records())
        self.assertEqual(other.to_dict(), memory.to_dict())
        restored = Preference.from_dict(json.loads(json.dumps(records[0].to_dict())))
        self.assertEqual(restored, records[0])

    def test_dedup_key_ignores_generation_library_snapshot_and_task_name(self):
        task, trials, grammar = constant_case()
        records, _ = extract(task, trials, grammar)
        record = records[0]
        duplicate = replace(record, generation=4, library_fingerprint="other-snapshot",
                            task_name="renamed", parent_id=90, child_id=91)
        memory = PreferenceMemory()
        self.assertEqual(memory.add([record]), 1)
        self.assertEqual(memory.add([duplicate]), 0)
        self.assertEqual(len(memory), 1)
        self.assertEqual(memory.duplicates, 1)
        self.assertEqual(memory.occurrences[1]["generation"], 4)
        with self.assertRaises(ValueError):
            memory.add([replace(record, label=-record.label)])

    def test_trial_id_ambiguity_is_rejected(self):
        task, trials, grammar = constant_case()
        with self.assertRaises(ValueError):
            extract(task, [trials[0], trials[0]], grammar)
        with self.assertRaises(ValueError):
            extract(task, [{**trials[0], "id": False}], grammar)


if __name__ == "__main__":
    unittest.main()
