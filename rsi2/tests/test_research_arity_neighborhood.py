"""Synthetic mechanism/provenance checks; no TRAIN or heldout corpus loading."""
import copy
from itertools import islice
import unittest

from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.terms import Bool, Int, Lam, Prim, Term, Var, apply
from rsi2.types import Arrow, BOOL, INT, ListOf, PRIMITIVE_TYPES, arrows, infer, unify
from rsi2.research.arity_neighborhood import (
    application_context_neighbors, arity_neighbors, reconstruct_application_context)
from rsi2.research.arity_population import solve_arity_population
from rsi2.research.coordinate_population import solve_coordinate_population
from rsi2.research.derivation_neighborhood import NeighborhoodLimit, NeighborhoodMeter, derivation_neighbors
from rsi2.research.repair_search import RepairSeed


def fragment(*names, constants=()):
    return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in names}, constants=constants)


class ArityNeighborhoodTests(unittest.TestCase):
    def test_disabled_factors_exact_legacy_records_and_work(self):
        parent, request, grammar = Lam(INT, Var(0)), Arrow(INT, INT), Grammar()
        first, second = NeighborhoodMeter(), NeighborhoodMeter()
        baseline = list(islice(derivation_neighbors(parent, request, grammar, meter=first), 16))
        actual = list(islice(arity_neighbors(parent, request, grammar, meter=second), 16))
        self.assertEqual(baseline, actual)
        for key, value in vars(first).items():
            if key != '_cpu_started':
                self.assertEqual(value, getattr(second, key), key)

    def test_generic_contexts_reach_binary_both_roles_under_real_caps(self):
        parent, request, grammar = Lam(INT, Var(0)), Arrow(INT, INT), Grammar()
        meter = NeighborhoodMeter()
        neighbors = list(islice(application_context_neighbors(parent, request, grammar, meter=meter), 18))
        self.assertLess(meter.compiler_steps, 20000)
        self.assertIn(Lam(INT, apply(Prim('sub'), Var(0), Int(-1))), [n.term for n in neighbors])
        self.assertIn(Lam(INT, apply(Prim('sub'), Int(-1), Var(0))), [n.term for n in neighbors])
        self.assertEqual({0, 1}, {n.metadata['retained_argument'] for n in neighbors})
        for n in neighbors:
            self.assertEqual(n.term, reconstruct_application_context(parent, request, grammar, n.metadata))

    def test_map_eta_retains_bound_source_and_builds_new_binary_context(self):
        parent = apply(Prim('map'), Prim('neg'))
        request, grammar = Arrow(ListOf(INT), ListOf(INT)), fragment('map', 'neg', 'add', constants=(Int(1),))
        neighbors = list(islice(application_context_neighbors(parent, request, grammar), 10))
        target = apply(Prim('map'), Lam(INT, apply(Prim('add'), apply(Prim('neg'), Var(0)), Int(1))))
        self.assertIn(target, [n.term for n in neighbors])
        for n in neighbors:
            self.assertEqual(n.term, reconstruct_application_context(parent, request, grammar, n.metadata))

    def test_polymorphic_branch_constraints_and_all_compatible_roles(self):
        parent, request = Lam(INT, Var(0)), Arrow(INT, INT)
        grammar = fragment('if', constants=(Int(0), Bool(False), Bool(True)))
        neighbors = list(islice(application_context_neighbors(parent, request, grammar), 12))
        local = [n for n in neighbors if n.path == (0,)]
        self.assertTrue(local)
        self.assertEqual({1, 2}, {n.metadata['retained_argument'] for n in local})
        for n in local:
            unify(infer(n.term), request)
            self.assertEqual(n.term, reconstruct_application_context(parent, request, grammar, n.metadata))
            args = [Term.from_dict(arg) for arg in n.metadata['arguments']]
            self.assertEqual(BOOL, infer(args[0]))

    def test_nested_binder_origins(self):
        parent, request = Lam(INT, Lam(INT, Var(1))), arrows(INT, INT, INT)
        grammar = fragment('add')
        neighbors = list(islice(application_context_neighbors(parent, request, grammar), 8))
        target = Lam(INT, Lam(INT, apply(Prim('add'), Var(1), Var(0))))
        self.assertIn(target, [n.term for n in neighbors])
        for n in neighbors:
            self.assertEqual(n.term, reconstruct_application_context(parent, request, grammar, n.metadata))

    def test_nonatomic_filler_derivations_remain_reachable(self):
        parent, request = Lam(INT, Var(0)), Arrow(INT, INT)
        grammar = fragment('add', 'neg')
        neighbors = list(islice(application_context_neighbors(parent, request, grammar, max_size=8), 10))
        self.assertTrue(any(any(Term.from_dict(a).tag == 'app' for a in n.metadata['arguments'])
                            for n in neighbors))
        for n in neighbors:
            self.assertLessEqual(n.term.size, 8)
            self.assertEqual(n.term, reconstruct_application_context(parent, request, grammar, n.metadata))

    def test_provenance_tampering_rejected(self):
        parent, request, grammar = Lam(INT, Var(0)), Arrow(INT, INT), fragment('add', constants=(Int(1),))
        neighbor = next(application_context_neighbors(parent, request, grammar))
        for field, value in [('source', Int(42).to_dict()), ('retained_argument', 8),
                             ('context', ['wrong', 0]), ('production_arity', 9),
                             ('argument_mapping', ['enumerated', 'enumerated'])]:
            altered = copy.deepcopy(neighbor.metadata)
            altered[field] = value
            with self.assertRaises((ValueError, KeyError)):
                reconstruct_application_context(parent, request, grammar, altered)

    def test_forged_out_of_inventory_filler_rejected_even_when_well_typed(self):
        parent, request = Lam(INT, Var(0)), Arrow(INT, INT)
        grammar = fragment('add', constants=(Int(1),))
        neighbor = next(application_context_neighbors(parent, request, grammar))
        altered = copy.deepcopy(neighbor.metadata)
        role = altered['retained_argument']
        arguments = [Term.from_dict(arg) for arg in altered['arguments']]
        arguments[1 - role] = Int(42)
        altered['arguments'] = [arg.to_dict() for arg in arguments]
        replacement = apply(Prim('add'), *arguments)
        altered['replacement'] = replacement.to_dict()
        altered['candidate'] = Lam(INT, replacement).to_dict()
        with self.assertRaises(ValueError):
            reconstruct_application_context(parent, request, grammar, altered)

    def test_exact_structural_and_compiler_caps(self):
        for field, maximum, reason in [('structural_limit', 1, 'expansion_budget'),
                                       ('compiler_limit', 5, 'normalization_budget')]:
            meter = NeighborhoodMeter(**{field: maximum})
            with self.assertRaises(NeighborhoodLimit) as caught:
                list(application_context_neighbors(Lam(INT, Var(0)), Arrow(INT, INT), Grammar(), meter=meter))
            self.assertEqual(reason, caught.exception.reason)
            self.assertEqual(maximum, getattr(meter, 'structural_states' if field == 'structural_limit' else 'compiler_steps'))

    def test_adapter_disabled_sequence_and_counters(self):
        args = ((((0,), 99), ((1,), 99)), Arrow(INT, INT), 12, fragment('neg', 'add', constants=(Int(0),)))
        kwargs = dict(seed_prefix=1, beta_normalize=True)
        baseline = solve_coordinate_population(*args, **kwargs)
        actual = solve_arity_population(*args, **kwargs)
        self.assertEqual(baseline.trials, actual.trials)
        self.assertEqual(baseline.expansions, actual.expansions)
        self.assertEqual(baseline.normalization_steps, actual.normalization_steps)

    def test_zero_and_absent_scorer_identical_with_contexts(self):
        parent = Lam(INT, Var(0))
        args = ((((0,), 99), ((1,), 99)), Arrow(INT, INT), 12, fragment('neg', 'add', constants=(Int(0),)))
        kwargs = dict(seed_prefix=0, accepted_seeds=(RepairSeed(parent, 'synthetic-own-seed'),),
                      beta_normalize=True, arity_context=True)
        none = solve_arity_population(*args, **kwargs)
        zero = solve_arity_population(*args, heuristic=zero_heuristic(), **kwargs)
        self.assertEqual([t['term'] for t in none.trials], [t['term'] for t in zero.trials])
        self.assertEqual(none.expansions, zero.expansions)
        self.assertEqual(none.normalization_steps, zero.normalization_steps)
        self.assertTrue(any(t.get('edit_provenance', {}).get('operator') == 'application_context' for t in none.trials))


if __name__ == '__main__':
    unittest.main()
