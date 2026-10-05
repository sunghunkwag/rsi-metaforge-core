"""Typed coordinate edits, capture protection, provenance and real work caps."""
import copy
import unittest
from unittest.mock import patch

from rsi2.enumeration import enumerate_programs
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar, _spine
from rsi2.research.derivation_neighborhood import (
    NeighborhoodLimit, NeighborhoodMeter, derivation_neighbors, reconstruct_neighbor,
)
from rsi2.terms import Int, Prim, Term, apply
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, infer, unify


class DerivationNeighborhoodTests(unittest.TestCase):
    def grammar(self, names=("sub", "mod", "neg", "abs"), constants=(1, 2)):
        return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in names},
                       constants=tuple(Int(value) for value in constants))

    def own_partial(self, grammar, name="sub"):
        request = Arrow(INT, INT)
        return next(candidate.term for candidate in enumerate_programs(
            request, grammar, max_size=3, max_expansions=20000)
            if _spine(candidate.term)[0].tag == "prim" and
            _spine(candidate.term)[0].value == name and
            _spine(candidate.term)[1] == (Int(1),))

    def collect(self, parent, request, grammar, **kwargs):
        meter = kwargs.pop("meter", NeighborhoodMeter())
        records = list(derivation_neighbors(parent, request, grammar, meter=meter, **kwargs))
        return records, meter

    def test_same_arity_head_substitution_retains_existing_argument_asts(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        records, _ = self.collect(parent, request, grammar)
        matching = [record for record in records if record.metadata["operator"] == "head"
                    and not record.metadata["eta_parameters"] and record.path == ()]
        self.assertTrue(matching)
        self.assertTrue(any(_spine(record.term)[0].value == "mod" for record in matching))
        for record in matching:
            self.assertEqual(_spine(record.term)[1], _spine(parent)[1])
            unify(infer(record.term), request)

    def test_eta_argument_permutation_changes_behavior_without_evaluated_intermediate(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        records, meter = self.collect(parent, request, grammar)
        swaps = [record for record in records if record.path == () and
                 record.metadata["eta_parameters"] and
                 record.metadata["operator"] == "permutation"]
        self.assertTrue(swaps)
        self.assertEqual(evaluate(parent, (9,)).value, -8)
        self.assertTrue(any(evaluate(record.term, (9,)).value == 8 for record in swaps))
        self.assertGreater(meter.eta_views, 0)
        # Equivalent eta views are only compiler states, never emitted children.
        self.assertFalse(any(record.metadata["operator"] == "eta" for record in records))

    def test_eta_exposure_keeps_outer_and_new_binders_distinct(self):
        grammar, request = self.grammar(("sub",), ()), Arrow(INT, Arrow(INT, INT))
        parent = next(candidate.term for candidate in enumerate_programs(
            request, grammar, max_size=4, max_expansions=20000)
            if candidate.term.tag == "lam" and
            _spine(candidate.term.children[0])[1] and
            _spine(candidate.term.children[0])[1][0].tag == "var")
        records, _ = self.collect(parent, request, grammar)
        swaps = [record for record in records if record.path == (0,) and
                 len(record.metadata["eta_parameters"]) == 1 and
                 record.metadata["operator"] == "permutation"]
        self.assertTrue(swaps)
        self.assertEqual(evaluate(parent, (7, 10)).value, -3)
        self.assertTrue(any(evaluate(record.term, (7, 10)).value == 3 for record in swaps))
        for record in records:
            unify(infer(record.term), request)

    def test_joint_polymorphic_constraints_reject_incompatible_preserved_siblings(self):
        grammar = self.grammar(("map", "filter", "eq", "not"), (1,))
        request = Arrow(ListOf(INT), ListOf(BOOL))
        parent = next(candidate.term for candidate in enumerate_programs(
            request, grammar, max_size=5, max_expansions=20000)
            if _spine(candidate.term)[0].value == "map")
        records, meter = self.collect(parent, request, grammar)
        self.assertTrue(records)
        self.assertGreater(meter.ill_typed, 0)
        for record in records:
            unify(infer(record.term), request)
        # A filter retaining the old int->bool predicate returns list[int].
        self.assertFalse(any(record.path == () and
                             _spine(record.term)[0].tag == "prim" and
                             _spine(record.term)[0].value == "filter" for record in records))

    def test_unary_insert_and_remove_use_only_current_grammar_productions(self):
        grammar, request = self.grammar(("abs", "neg"), ()), Arrow(INT, INT)
        parent = next(candidate.term for candidate in enumerate_programs(
            request, grammar, max_size=4, max_expansions=20000)
            if candidate.term.tag == "lam" and candidate.term.children[0].tag == "app")
        records, _ = self.collect(parent, request, grammar)
        self.assertTrue(any(record.metadata["operator"] == "unary_remove" and
                            record.path == (0,) for record in records))
        inserts = [record for record in records
                   if record.metadata["operator"] == "unary_insert"]
        self.assertTrue(inserts)
        for record in inserts:
            head = Term.from_dict(record.metadata["production_head"])
            self.assertIn(head.value, grammar.primitives)

    def test_every_edge_reconstructs_from_source_production_and_mapping(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        records, _ = self.collect(parent, request, grammar)
        self.assertGreater(len(records), 5)
        self.assertEqual(len({record.term for record in records}), len(records))
        for record in records:
            recovered = reconstruct_neighbor(parent, request, grammar, record.metadata)
            self.assertEqual(recovered, record.term)

    def test_provenance_reconstruction_rejects_forged_result_and_permutation(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        records, _ = self.collect(parent, request, grammar)
        swap = next(record for record in records
                    if record.metadata["operator"] == "permutation")
        forged = copy.deepcopy(swap.metadata)
        forged["argument_mapping"] = [0, 0]
        with self.assertRaisesRegex(ValueError, "permutation"):
            reconstruct_neighbor(parent, request, grammar, forged)
        forged = copy.deepcopy(swap.metadata)
        forged["candidate"] = parent.to_dict()
        with self.assertRaisesRegex(ValueError, "reconstructed"):
            reconstruct_neighbor(parent, request, grammar, forged)

    def test_reconstruction_rejects_globally_typed_heads_excluded_by_source_grammar(self):
        grammar, request = self.grammar(("sub", "mod")), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        records, _ = self.collect(parent, request, grammar)
        head_change = next(record for record in records if record.path == () and
                           record.metadata["operator"] == "head" and
                           not record.metadata["eta_parameters"])
        forged = copy.deepcopy(head_change.metadata)
        forged["production_head"] = Prim("add").to_dict()
        illegal = apply(Prim("add"), *_spine(parent)[1])
        forged["replacement"] = illegal.to_dict()
        forged["candidate"] = illegal.to_dict()
        unify(infer(illegal), request)  # Typing alone cannot authenticate origin.
        with self.assertRaisesRegex(ValueError, "unavailable"):
            reconstruct_neighbor(parent, request, grammar, forged)

    def test_structural_and_compiler_zero_caps_stop_before_first_charged_operation(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        structural = NeighborhoodMeter(structural_limit=0)
        with self.assertRaises(NeighborhoodLimit) as context:
            list(derivation_neighbors(parent, request, grammar, meter=structural))
        self.assertEqual(context.exception.reason, "expansion_budget")
        self.assertEqual(structural.structural_states, 0)
        compiler = NeighborhoodMeter(compiler_limit=0)
        with self.assertRaises(NeighborhoodLimit) as context:
            list(derivation_neighbors(parent, request, grammar, meter=compiler))
        self.assertEqual(context.exception.reason, "normalization_budget")
        self.assertEqual(compiler.compiler_steps, 0)

    def test_shared_meter_caps_interleaved_parent_iterators_without_an_extra_state(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        meter = NeighborhoodMeter(structural_limit=17)
        first = derivation_neighbors(parent, request, grammar, meter=meter)
        second = derivation_neighbors(parent, request, grammar, meter=meter)
        with self.assertRaises(NeighborhoodLimit) as context:
            while True:
                next(first)
                next(second)
        self.assertEqual(context.exception.reason, "expansion_budget")
        self.assertEqual(meter.structural_states, 17)

    def test_shared_callbacks_match_actual_metered_operations(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        counts = {"structural": 0, "compiler": 0, "checks": 0}

        def debit(name):
            counts[name] += 1

        meter = NeighborhoodMeter(structural_callback=lambda: debit("structural"),
                                  compiler_callback=lambda: debit("compiler"),
                                  check_callback=lambda: debit("checks"))
        records, meter = self.collect(parent, request, grammar, meter=meter)
        self.assertTrue(records)
        self.assertEqual(counts["structural"], meter.structural_states)
        self.assertEqual(counts["compiler"], meter.compiler_steps)
        self.assertGreater(counts["checks"], meter.structural_states + meter.compiler_steps)

    def test_cpu_guard_vetoes_generation_and_preserves_preceding_work(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        meter = NeighborhoodMeter(max_cpu_seconds=1)
        with patch("rsi2.research.derivation_neighborhood.time.process_time",
                   return_value=meter._cpu_started + 1.01):
            with self.assertRaises(NeighborhoodLimit) as context:
                next(derivation_neighbors(parent, request, grammar, meter=meter))
        self.assertEqual(context.exception.reason, "cpu_budget")
        self.assertEqual(meter.structural_states, 0)
        self.assertEqual(meter.compiler_steps, 0)

    def test_final_size_limit_applies_after_eta_transform_and_all_reconstructions(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        records, meter = self.collect(parent, request, grammar, max_size=3)
        self.assertTrue(records)
        self.assertTrue(all(record.term.size <= 3 for record in records))
        self.assertTrue(all(not record.metadata["eta_parameters"] for record in records))
        self.assertGreater(meter.oversized, 0)

    def test_eta_can_be_disabled_without_changing_direct_head_proposals(self):
        grammar, request = self.grammar(), Arrow(INT, INT)
        parent = self.own_partial(grammar)
        complete, _ = self.collect(parent, request, grammar)
        direct, meter = self.collect(parent, request, grammar, eta_exposure=False)
        self.assertEqual({r.term for r in direct},
                         {r.term for r in complete if not r.metadata["eta_parameters"]})
        self.assertEqual(meter.eta_views, 0)


if __name__ == "__main__":
    unittest.main()
