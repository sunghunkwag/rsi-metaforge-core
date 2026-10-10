"""Synthetic checks for independently switched production-priority edits."""
import unittest
from dataclasses import asdict

from rsi2.grammar import Grammar, ROOT_CONTEXT
from rsi2.research.derivation_neighborhood import (
    NeighborhoodLimit, NeighborhoodMeter, derivation_neighbors, reconstruct_neighbor,
)
from rsi2.research.priority_neighborhood import (
    _production_contexts, priority_derivation_neighbors,
)
from rsi2.terms import Int, Lam, Prim, Ref, Var, apply
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, infer, unify


class PriorityNeighborhoodTests(unittest.TestCase):
    def grammar(self, names=("sub", "mod", "neg", "abs"), **kwargs):
        return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in names},
                       constants=(Int(0), Int(1), Int(2)), **kwargs)

    def collect(self, parent, request, grammar, *, priority=True, **kwargs):
        meter = kwargs.pop("meter", NeighborhoodMeter(compiler_limit=200000))
        records = list(priority_derivation_neighbors(
            parent, request, grammar, meter=meter,
            production_priority=priority, **kwargs))
        return records, meter

    def test_disabled_delegates_with_identical_records_and_work(self):
        grammar = self.grammar(weights={"mod": 100, "int:2": 20})
        parent, request = apply(Prim("sub"), Int(1)), Arrow(INT, INT)
        old_meter = NeighborhoodMeter(compiler_limit=200000)
        old = list(derivation_neighbors(parent, request, grammar, meter=old_meter))
        new, new_meter = self.collect(parent, request, grammar, priority=False)
        self.assertEqual(new, old)
        before, after = asdict(old_meter), asdict(new_meter)
        before.pop("_cpu_started")
        after.pop("_cpu_started")
        self.assertEqual(after, before)

    def test_uniform_probabilities_preserve_exact_order_and_charge_extra_work(self):
        grammar = self.grammar()
        # fit([]) is the learned uniform distribution, including arity keys.
        grammar.fit([])
        parents = (
            (apply(Prim("sub"), Int(1)), Arrow(INT, INT)),
            (Lam(INT, apply(Prim("sub"), Var(0), Int(1))), Arrow(INT, INT)),
        )
        for parent, request in parents:
            with self.subTest(parent=str(parent)):
                old, old_meter = self.collect(parent, request, grammar, priority=False)
                new, new_meter = self.collect(parent, request, grammar)
                self.assertEqual(new, old)
                self.assertEqual(new_meter.structural_states, old_meter.structural_states)
                self.assertGreater(new_meter.compiler_steps, old_meter.compiler_steps)
                self.assertGreater(new_meter.grammar_queries, old_meter.grammar_queries)

    def test_fitted_grammar_probabilities_change_descendant_order(self):
        grammar = self.grammar(())
        grammar.fit([Int(2)] * 5)
        old, _ = self.collect(Int(0), INT, grammar, priority=False)
        ordered, _ = self.collect(Int(0), INT, grammar)
        self.assertEqual([record.term for record in old], [Int(1), Int(2)])
        self.assertEqual([record.term for record in ordered], [Int(2), Int(1)])

    def test_argument_context_overrides_global_weights_at_correct_spine_path(self):
        grammar = self.grammar(("sub",), weights={"int:1": 100}, context_weights={
            ("sub", 0): {"int:2/0": 1000},
            ("sub", 1): {"int:1/0": 1000},
        })
        parent = apply(Prim("sub"), Int(0), Int(0))
        records, _ = self.collect(parent, INT, grammar, eta_exposure=False)
        for path, expected in (((0, 1), [Int(2), Int(1)]),
                               ((1,), [Int(1), Int(2)])):
            edits = [r.replacement for r in records if r.path == path and
                     r.metadata["operator"] == "head"]
            self.assertEqual(edits, expected)

    def test_eta_body_queries_lambda_context(self):
        grammar = self.grammar(("abs", "neg"), weights={"abs/1": 100},
                               context_weights={("lambda", 0): {"neg/1": 1000}})
        records, _ = self.collect(Prim("neg"), Arrow(INT, INT), grammar)
        insertions = [r.metadata["production_head"]["value"] for r in records
                      if r.path == () and r.metadata["operator"] == "unary_insert"
                      and r.metadata["eta_parameters"]]
        self.assertEqual(insertions, ["neg", "abs"])

    def test_replay_preserves_library_and_bound_variable_contexts(self):
        library = {"identity": Lam(INT, Var(0))}
        grammar = self.grammar(("sub",), library=library,
                               context_weights={("identity", 0): {"var:0": 40}})
        parent = Lam(INT, apply(Ref("identity"), Var(0)))
        request = Arrow(INT, INT)
        contexts = _production_contexts(parent, request, grammar, NeighborhoodMeter())
        self.assertEqual(contexts, {(): ROOT_CONTEXT, (0,): ("lambda", 0),
                                    (0, 1): ("identity", 0)})
        records, _ = self.collect(parent, request, grammar)
        self.assertTrue(records)
        for record in records:
            self.assertEqual(reconstruct_neighbor(parent, request, grammar, record.metadata),
                             record.term)
            unify(infer(record.term, library=library), request)

    def test_polymorphic_replay_and_reconstruction_keep_joint_types(self):
        grammar = self.grammar(("map", "filter", "eq", "not"), weights={"filter": 100})
        parent = apply(Prim("map"), apply(Prim("eq"), Int(1)))
        request = Arrow(ListOf(INT), ListOf(BOOL))
        records, _ = self.collect(parent, request, grammar)
        self.assertTrue(records)
        for record in records:
            unify(infer(record.term), request)
            self.assertEqual(reconstruct_neighbor(parent, request, grammar, record.metadata),
                             record.term)

    def test_priority_work_obeys_compiler_cap_and_flag_validation(self):
        meter = NeighborhoodMeter(compiler_limit=0)
        with self.assertRaises(NeighborhoodLimit) as caught:
            self.collect(Int(0), INT, self.grammar(()), meter=meter)
        self.assertEqual(caught.exception.reason, "normalization_budget")
        self.assertEqual(meter.compiler_steps, 0)
        with self.assertRaisesRegex(TypeError, "production_priority"):
            self.collect(Int(0), INT, self.grammar(()), priority=1)


if __name__ == "__main__":
    unittest.main()
