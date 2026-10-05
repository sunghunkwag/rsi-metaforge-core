"""Own-grammar proposal provenance, scope, novelty and complete cost accounting."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.research import heuristic_proposals as proposals
from rsi2.research.heuristic_proposals import HeuristicProposalProvider, candidate_dependencies
from rsi2.research.proposals import canonical_term
from rsi2.research.repair_search import beta_normal_form
from rsi2.search import HEURISTIC_TYPE
from rsi2.terms import Int, Lam, Prim, Ref, Var, apply, replace_subterm, subterms
from rsi2.types import INT, ListOf, PRIMITIVE_TYPES, infer, unify


LIMITS = {"max_size": 12, "max_expansions": 20000, "step_budget": 2000}
BODY = (0, 0, 0, 0)


def heuristic(body):
    return replace_subterm(zero_heuristic(), BODY, body)


class HeuristicProposalTests(unittest.TestCase):
    def grammar(self):
        return Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("neg", "length")},
                       constants=(Int(0),))

    def test_fixed_six_slots_are_typed_wrapped_and_use_own_grammar(self):
        report = HeuristicProposalProvider().propose(None, self.grammar(), 11, 1, LIMITS)
        self.assertEqual(len(report["records"]), 6)
        self.assertEqual([r["origin"] for r in report["records"]], ["enumeration"] * 4 + ["mutation"] * 2)
        self.assertEqual(report["termination"], "completed_slots")
        for record in report["records"]:
            self.assertIsNotNone(record["term"])
            unify(infer(record["term"]), HEURISTIC_TYPE)
            self.assertLessEqual(record["term"].size, 12)
            self.assertTrue(set(candidate_dependencies(record["term"])) & {0, 1, 3})
            self.assertTrue(all(node.value in ("neg", "length") for _, node in subterms(record["term"])
                                if node.tag == "prim"))
        self.assertEqual(report["heuristic_evaluations"], 0)
        self.assertEqual(report["heuristic_evaluation_steps"], 0)

    def test_provider_calls_no_interpreter_or_partition_loader(self):
        forbidden = AssertionError("proposal generation must not evaluate or load tasks")
        with patch("rsi2.evaluator.evaluate", side_effect=forbidden), \
                patch("rsi2.research.repair_search.evaluate", side_effect=forbidden), \
                patch("rsi2.corpus.load_train", side_effect=forbidden), \
                patch("rsi2.corpus.load_validation", side_effect=forbidden):
            report = HeuristicProposalProvider().propose(None, self.grammar(), 11, 1, LIMITS)
        self.assertEqual(len(report["records"]), 6)

    def test_target_only_and_closed_bodies_are_filtered_with_full_raw_asts(self):
        report = HeuristicProposalProvider().propose(None, self.grammar(), 11, 1, LIMITS)
        rejected = [raw for raw in report["work"]["raw_draws"] if raw["rejection"] == "candidate_independent"]
        self.assertTrue(rejected)
        self.assertTrue(any(raw["dependencies"] == [2] for raw in rejected))
        self.assertTrue(any(raw["dependencies"] == [] for raw in rejected))
        self.assertTrue(all("enumerated_term" in raw and "candidate" in raw for raw in rejected))
        self.assertEqual(report["work"]["frontier_pops"],
                         report["work"]["partial_frontier_pops"] + report["work"]["complete_frontier_pops"])
        self.assertEqual(report["work"]["enumerator_terms"], report["work"]["complete_frontier_pops"])
        self.assertEqual(report["work"]["generated_full_candidates"], len(report["work"]["raw_draws"]))

    def test_inner_bound_variable_is_not_mistaken_for_candidate_depth(self):
        target_only = heuristic(apply(Prim("head"), apply(Prim("map"), Lam(INT, Var(0)), Var(2))))
        captures_depth = heuristic(apply(Prim("head"), apply(Prim("map"), Lam(INT, Var(1)), Var(2))))
        self.assertEqual(candidate_dependencies(target_only), (2,))
        self.assertEqual(candidate_dependencies(captures_depth), (0, 2))
        inputs = ([5, 6], [9, 10], 7, 3)
        self.assertEqual(evaluate(target_only, inputs).value, 9)
        self.assertEqual(evaluate(captures_depth, inputs).value, 3)

    def test_global_novelty_survives_current_grammar_weight_refit(self):
        provider, grammar = HeuristicProposalProvider(), self.grammar()
        first = provider.propose(None, grammar, 11, 1, LIMITS)
        previous = {record["term"] for record in first["records"] if record["term"] is not None}
        grammar.fit([(record["term"], HEURISTIC_TYPE) for record in first["records"] if record["term"] is not None])
        second = provider.propose(None, grammar, 11, 2, LIMITS)
        current = {record["term"] for record in second["records"] if record["term"] is not None}
        self.assertTrue(current)
        self.assertTrue(previous.isdisjoint(current))
        self.assertGreater(second["work"]["replayed_ast_draws"], 0)
        self.assertGreater(second["work"]["frontier_pops"], 0)
        self.assertTrue(all("first_generation" in raw for raw in second["work"]["raw_draws"]
                            if raw["rejection"] == "replayed_ast"))

    def test_seeded_draws_repeat_exact_syntax_and_work(self):
        left = HeuristicProposalProvider().propose(None, self.grammar(), 22, 3, LIMITS)
        right = HeuristicProposalProvider().propose(None, self.grammar(), 22, 3, LIMITS)
        self.assertEqual(left["records"], right["records"])
        self.assertEqual(left["work"], right["work"])

    def test_zero_expansion_cap_never_generates_or_normalizes(self):
        report = HeuristicProposalProvider().propose(None, self.grammar(), 11, 1,
                                                     {**LIMITS, "max_expansions": 0})
        self.assertEqual(len(report["records"]), 6)
        self.assertTrue(all(record["term"] is None for record in report["records"]))
        self.assertEqual(report["work"]["frontier_pops"], 0)
        self.assertEqual(report["work"]["enumerator_terms"], 0)
        self.assertEqual(report["work"]["normalization_steps"], 0)
        self.assertEqual(report["termination"], "expansion_budget")

    def test_small_cap_counts_wrapper_and_complete_pops_without_extra_pop(self):
        grammar = Grammar(primitives={}, constants=(Int(0),))
        five = HeuristicProposalProvider().propose(None, grammar, 11, 1,
                                                   {**LIMITS, "max_expansions": 5})
        self.assertEqual(five["work"]["frontier_pops"], 5)
        self.assertEqual(five["work"]["partial_frontier_pops"], 5)
        self.assertEqual(five["work"]["complete_frontier_pops"], 0)
        six = HeuristicProposalProvider().propose(None, grammar, 11, 1,
                                                  {**LIMITS, "max_expansions": 6})
        self.assertEqual(six["work"]["frontier_pops"], 6)
        self.assertEqual(six["work"]["partial_frontier_pops"], 5)
        self.assertEqual(six["work"]["complete_frontier_pops"], 1)
        self.assertIsNotNone(six["records"][0]["term"])
        self.assertTrue(all(record["term"] is None for record in six["records"][1:]))
        self.assertEqual(six["termination"], "expansion_budget")

    def test_normalization_failure_still_records_constructed_full_candidate(self):
        report = HeuristicProposalProvider().propose(None, self.grammar(), 11, 1,
                                                     {**LIMITS, "max_normalization_steps": 0})
        self.assertEqual(report["termination"], "normalization_budget")
        self.assertEqual(report["work"]["normalization_steps"], 0)
        self.assertGreater(report["work"]["mutation_wrapper_terms"], 0)
        self.assertEqual(report["work"]["generated_full_candidates"], len(report["work"]["raw_draws"]))
        interrupted = report["work"]["raw_draws"][-1]
        self.assertEqual(interrupted["rejection"], "normalization_budget")
        self.assertIn("raw_candidate", interrupted)
        self.assertTrue(all(record["term"] is None for record in report["records"][4:]))

    def test_local_wrapper_opening_and_beta_reduction_preserve_binding_values(self):
        grammar = Grammar(primitives={"sub": PRIMITIVE_TYPES["sub"]}, constants=())
        incumbent = heuristic(apply(Prim("sub"), Var(1), Var(0)))
        report = HeuristicProposalProvider().propose(incumbent, grammar, 1, 1, LIMITS)
        self.assertGreater(report["work"]["beta_reductions"], 0)
        for raw in report["work"]["raw_draws"]:
            if raw["origin"] != "mutation" or "candidate" not in raw:
                continue
            original = proposals.Term.from_dict(raw["raw_candidate"])
            normalized = proposals.Term.from_dict(raw["candidate"])
            independently_normalized = beta_normal_form(original)
            self.assertEqual(canonical_term(independently_normalized.term), normalized)
            self.assertEqual(independently_normalized.steps, raw["normalization_steps"])
            unify(infer(normalized), HEURISTIC_TYPE)
            for inputs in (([1, 2], [8, 9], 7, 2), ([-4], [3], 2, 8)):
                first, second = evaluate(original, inputs), evaluate(normalized, inputs)
                self.assertEqual((first.ok, first.value), (second.ok, second.value))
        self.assertEqual(report["work"]["normalization_steps"],
                         sum(raw.get("normalization_steps", 0) for raw in report["work"]["raw_draws"]))

    def test_old_library_entries_remain_valid_when_current_library_grows(self):
        old = Lam(ListOf(INT), apply(Prim("length"), Var(0)))
        provider = HeuristicProposalProvider()
        first_grammar = Grammar(library={"own_count": old})
        provider.propose(None, first_grammar, 11, 1, LIMITS)
        growing = Grammar(library={"own_count": old, "own_neg": Lam(INT, apply(Prim("neg"), Var(0)))})
        second = provider.propose(None, growing, 11, 2, LIMITS)
        for record in second["records"]:
            if record["term"] is not None:
                unify(infer(record["term"], library=growing.library), HEURISTIC_TYPE)
        with self.assertRaises(ValueError):
            provider.propose(None, Grammar(), 11, 3, LIMITS)
        changed = Grammar(library={"own_count": Lam(ListOf(INT), apply(Prim("head"), Var(0))),
                                  "own_neg": growing.library["own_neg"]})
        with self.assertRaises(ValueError):
            provider.propose(None, changed, 11, 3, LIMITS)

    def test_controller_adapter_logs_primitive_only_inlining_cost(self):
        own_count = Lam(ListOf(INT), apply(Prim("length"), Var(0)))
        grammar = Grammar(library={"own_count": own_count},
                          primitives={"length": PRIMITIVE_TYPES["length"]}, constants=(Int(0),))
        state = SimpleNamespace(grammar=grammar, heuristic=heuristic(apply(Ref("own_count"), Var(3))),
                                seed=11, generation=1)
        provider = HeuristicProposalProvider()
        records = provider.draw(state, {"search": LIMITS}, primitive_only=True)
        self.assertEqual(records, provider.last_report["records"])
        self.assertEqual(provider.last_report["work"]["incumbent_inline_calls"], 1)
        self.assertGreater(provider.last_report["work"]["incumbent_inline_output_size"],
                           provider.last_report["work"]["incumbent_inline_input_size"])
        self.assertGreaterEqual(provider.last_report["cpu_seconds"],
                                provider.last_report["work"]["incumbent_inline_cpu_seconds"])
        for record in records:
            if record["term"] is not None:
                self.assertFalse(any(node.tag == "ref" for _, node in subterms(record["term"])))

    def test_cpu_boundary_after_normalization_cannot_report_completed(self):
        clock = [0.0]

        def normalization(*args, **kwargs):
            result = beta_normal_form(*args, **kwargs)
            clock[0] = 1.0
            return result

        with patch.object(proposals.time, "process_time", side_effect=lambda: clock[0]), \
                patch.object(proposals, "beta_normal_form", side_effect=normalization):
            report = HeuristicProposalProvider().propose(None, self.grammar(), 11, 1,
                                                         {**LIMITS, "max_cpu_seconds": 0.5})
        self.assertEqual(report["termination"], "cpu_budget")
        self.assertGreater(report["work"]["normalization_steps"], 0)
        self.assertEqual(report["work"]["raw_draws"][-1]["rejection"], "cpu_budget")
        self.assertEqual(report["cpu_seconds"], 1.0)
        self.assertTrue(all(record["term"] is None for record in report["records"][4:]))


if __name__ == "__main__":
    unittest.main()
