"""Synthetic proposal/controller checks without corpus, network, or TEST access."""
import copy
from itertools import islice
import json
import unittest
from unittest.mock import patch

import numpy as np

from rsi2.enumeration import Candidate, enumerate_programs
from rsi2 import enumeration as enumeration_module
from rsi2.grammar import Grammar
from rsi2.heuristics import zero_heuristic
from rsi2.research import proposals
from rsi2.search import HEURISTIC_TYPE
from rsi2.terms import Int, Lam, Prim, Var, apply
from rsi2.types import INT, PRIMITIVE_TYPES, TVar


SEARCH = {"max_size": 12, "max_expansions": 4000, "step_budget": 2000}


class ProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grammar = Grammar(primitives={name: PRIMITIVE_TYPES[name] for name in ("neg", "abs", "add")},
                              constants=(Int(-1), Int(0), Int(1)))
        cls.terms = [candidate.term for candidate in islice(
            enumerate_programs(HEURISTIC_TYPE, cls.grammar, max_size=12, max_expansions=4000), 100)]
        if len(cls.terms) != 100:
            raise AssertionError("real typed fixture enumeration was unexpectedly exhausted")

    def enumeration(self, request, grammar, **kwargs):
        self.assertEqual(request, HEURISTIC_TYPE)
        self.assertEqual(kwargs, {"max_size": SEARCH["max_size"],
                                  "max_expansions": SEARCH["max_expansions"]})
        return iter(Candidate(term, -index) for index, term in enumerate(self.terms))

    def mutation(self, incumbent, grammar, rng, searchconfig, **kwargs):
        self.assertEqual(searchconfig, SEARCH)
        self.assertFalse(kwargs["primitive_only"])
        self.assertIs(kwargs["template_library"], grammar.library)
        index = rng.randrange(len(self.terms))
        return self.terms[index], (index % 3,), None

    @staticmethod
    def audits(records, informative=True):
        return [{"valid": record["term"] is not None,
                 "informative": informative and record["term"] is not None}
                for record in records]

    def patches(self):
        return (patch.object(proposals, "enumerate_programs", side_effect=self.enumeration),
                patch.object(proposals, "mutate", side_effect=self.mutation))

    def finish(self, pool, records, audits=None):
        audits = self.audits(records) if audits is None else audits
        selection = pool.select(records, audits)
        report = pool.observe(records, audits)
        return selection, report

    def test_actual_typed_enumeration_and_original_mutations_are_used(self):
        pool = proposals.ProposalPool(self.grammar, 11, "static")
        with patch.object(proposals, "enumerate_programs", wraps=enumerate_programs) as enumerator, \
                patch.object(proposals, "mutate", wraps=proposals.mutate) as mutator:
            records = pool.draw(None, 1, SEARCH)
        self.assertEqual(len(records), 34)
        self.assertEqual([row["origin"] for row in records], ["enumeration"] * 32 + ["mutation"] * 2)
        self.assertEqual(enumerator.call_count, 1)
        self.assertEqual(mutator.call_count, 2)
        self.assertEqual(records[0]["term"], proposals.canonical_term(self.terms[0]))
        self.assertEqual([row["term"] for row in records[:32]],
                         [proposals.canonical_term(term) for term in self.terms[:32]])
        self.assertEqual(pool.draw_report["new_raw_draws"], 34)
        self.assertEqual(pool.draw_report["replay_draws"], 0)
        self.assertGreater(pool.draw_report["partial_expansion_calls"]["enumeration"], 0)
        self.assertGreater(pool.draw_report["partial_expansion_calls"]["mutation"], 0)
        self.assertEqual(pool.draw_report["mutation_complete_frontier_pops_bounds"], [0, 2])

    def test_exact_frontier_telemetry_preserves_order_and_separates_resume_replay(self):
        heap_pop = enumeration_module.heapq.heappop
        failed_mutation = lambda *args, **kwargs: (None, (), "fixture_no_replacement")
        with patch.object(proposals, "mutate", side_effect=failed_mutation):
            pool = proposals.ProposalPool(self.grammar, 11, "static")
            with patch.object(enumeration_module.heapq, "heappop", wraps=heap_pop) as popped:
                first = pool.draw(None, 1, SEARCH)
                first_work = copy.deepcopy(pool.draw_report)
                self.assertEqual(popped.call_count, first_work["enumeration_frontier_pops"])
            self.finish(pool, first)
            checkpoint = pool.to_dict()
            continuous = pool.draw(None, 2, SEARCH)
            continuous_work = copy.deepcopy(pool.draw_report)
            restored = proposals.ProposalPool(self.grammar, 11, "static", state=checkpoint)
            with patch.object(enumeration_module.heapq, "heappop", wraps=heap_pop) as popped:
                resumed = restored.draw(None, 2, SEARCH)
                resumed_work = restored.draw_report
                self.assertEqual(popped.call_count, resumed_work["enumeration_frontier_pops"])
            self.assertEqual(continuous, resumed)
            self.assertEqual(resumed_work["replay_draws"], 32)
            self.assertEqual(continuous_work["replay_frontier_pops"], 0)
            self.assertEqual(resumed_work["replay_frontier_pops"], first_work["enumeration_frontier_pops"])
            self.assertEqual(resumed_work["new_enumeration_frontier_pops"],
                             continuous_work["new_enumeration_frontier_pops"])
            self.assertEqual(resumed_work["partial_expansion_calls"]["replay"],
                             first_work["partial_expansion_calls"]["enumeration"])
            self.assertEqual(resumed_work["partial_expansion_calls"]["mutation"], 0)
            self.assertEqual(resumed_work["enumeration_frontier_pops"],
                             resumed_work["new_enumeration_frontier_pops"]
                             + resumed_work["replay_frontier_pops"])

    def test_original_restarts_prefix_and_selects_four_plus_two_ignoring_outcomes(self):
        first, second = self.patches()
        with first as enum, second:
            pool = proposals.ProposalPool(self.grammar, 11, "original")
            one = pool.draw(zero_heuristic(), 1, SEARCH)
            invalid = [{"valid": False, "informative": False} for _ in one]
            selected, report = self.finish(pool, one, invalid)
            two = pool.draw(zero_heuristic(), 2, SEARCH)
        self.assertEqual(selected, [0, 1, 2, 3, 32, 33])
        self.assertEqual([row["term"] for row in one[:32]], [row["term"] for row in two[:32]])
        self.assertEqual(enum.call_count, 2)
        self.assertEqual(pool.offset, 0)
        self.assertEqual(report["trained_count"], 0)
        self.assertEqual(report["training_steps"], 0)
        self.assertEqual(report["observed_count"], 34)
        self.assertEqual(pool.draw_report["expansion_limit_scope"], "per_cycle_restart")

    def test_static_persists_cursor_and_filters_invalid_constant_and_duplicate_slots(self):
        first, second = self.patches()
        with first as enum, second:
            pool = proposals.ProposalPool(self.grammar, 11, "static")
            records = pool.draw(None, 1, SEARCH)
            audits = self.audits(records)
            audits[0] = {"valid": True, "informative": False}  # constant proxy is ineligible
            audits[1] = {"valid": False, "informative": True}
            selected, _ = self.finish(pool, records, audits)
            later = pool.draw(None, 2, SEARCH)
        self.assertEqual(selected, [2, 3, 4, 5, 6, 7])
        self.assertEqual(later[0]["term"], proposals.canonical_term(self.terms[32]))
        self.assertEqual(enum.call_count, 1)
        self.assertEqual(pool.offset, 64)
        self.assertEqual(pool.draw_report["replay_draws"], 0)
        self.assertEqual(pool.draw_report["expansion_limit_scope"], "cumulative_persistent_stream")

    def test_learned_ranks_with_previous_labels_and_observes_all_raw_terms_after_selection(self):
        first, second = self.patches()
        with first, second:
            pool = proposals.ProposalPool(self.grammar, 22, "learned")
            initial = pool.draw(None, 1, SEARCH)
            labels = [{"valid": True, "informative": bool(proposals.features(row["term"])[
                proposals.FEATURE_NAMES.index("lambda")] >= 4)} for row in initial]
            with self.assertRaisesRegex(ValueError, "observe must follow selection"):
                pool.observe(initial, labels)
            _, model = self.finish(pool, initial, labels)
            self.assertEqual(model["trained_count"], 34)
            self.assertEqual(model["training_steps"], 80)
            self.assertEqual(model["regularization"], 1e-3)
            self.assertEqual(model["objective"], proposals.OBJECTIVE)
            self.assertGreater(float(np.linalg.norm(pool.coefficients)), 0)
            self.assertEqual([row["label"] for row in pool.samples],
                             [int(row["informative"]) for row in labels])
            next_records = pool.draw(None, 2, SEARCH)
            next_audits = self.audits(next_records)
            before = pool.coefficients.copy()
            seen = set(pool.selected)
            eligible, unique = [], set(seen)
            for row in next_records:
                key = proposals._term_key(row["term"])
                if key not in unique:
                    eligible.append(row["index"])
                    unique.add(key)
            expected = sorted(eligible, key=lambda i: (-pool.predict(next_records[i]["term"]), i))[:6]
            with patch.object(pool, "_fit", wraps=pool._fit) as fitting:
                selected = pool.select(next_records, next_audits)
                self.assertEqual(fitting.call_count, 0)
                np.testing.assert_array_equal(pool.coefficients, before)
                self.assertEqual(pool.selection_report["model_trained_count"], 34)
                self.assertEqual(selected, expected)
                pool.observe(next_records, next_audits)
                self.assertEqual(fitting.call_count, 1)
            self.assertEqual(len(pool.samples), 68)

    def test_neutral_model_uses_index_ties_and_selected_ast_novelty_across_cycles(self):
        repeated = [self.terms[0]] * 32
        stream = lambda *args, **kwargs: iter(Candidate(term, 0) for term in repeated)
        mutation = lambda *args, **kwargs: (self.terms[0], (), None)
        with patch.object(proposals, "enumerate_programs", side_effect=stream), \
                patch.object(proposals, "mutate", side_effect=mutation):
            pool = proposals.ProposalPool(self.grammar, 11, "learned")
            first = pool.draw(None, 1, SEARCH)
            self.assertEqual(pool.select(first, self.audits(first)), [0])
            pool.observe(first, self.audits(first))
            second = pool.draw(None, 2, SEARCH)
            self.assertEqual(pool.select(second, self.audits(second)), [])
            self.assertEqual(len(second), 34)

    def test_exhausted_stream_logs_failed_slots_and_never_retries_completed_iterator(self):
        stream = lambda *args, **kwargs: iter(Candidate(term, 0) for term in self.terms[:3])
        mutation = lambda *args, **kwargs: (None, (), "replacement_space_exhausted")
        with patch.object(proposals, "enumerate_programs", side_effect=stream) as enum, \
                patch.object(proposals, "mutate", side_effect=mutation):
            pool = proposals.ProposalPool(self.grammar, 11, "static")
            first = pool.draw(None, 1, SEARCH)
            self.assertEqual(sum(row["term"] is None for row in first), 31)
            self.assertEqual(pool.draw_report["enumerated_candidates"], 3)
            self.assertEqual(self.finish(pool, first)[0], [0, 1, 2])
            restored = proposals.ProposalPool(self.grammar, 11, "static", state=pool.to_dict())
            second = restored.draw(None, 2, SEARCH)
            self.assertTrue(all(row["term"] is None for row in second))
            self.assertTrue(restored.exhausted)
            self.assertEqual(enum.call_count, 1)
            self.assertEqual(restored.draw_report["replay_draws"], 0)
            self.assertEqual(restored.draw_report["new_raw_draws"], 34)

    def test_checkpoint_resume_matches_cursor_terms_labels_coefficients_and_selection(self):
        first, second = self.patches()
        with first, second:
            for mode in proposals.MODES:
                with self.subTest(mode=mode):
                    uninterrupted = proposals.ProposalPool(self.grammar, 33, mode)
                    for cycle in (1, 2):
                        records = uninterrupted.draw(None, cycle, SEARCH)
                        self.finish(uninterrupted, records)
                    checkpoint = json.loads(json.dumps(uninterrupted.to_dict()))
                    restored = proposals.ProposalPool(self.grammar, 33, mode, state=checkpoint)
                    one = uninterrupted.draw(None, 3, SEARCH)
                    two = restored.draw(None, 3, SEARCH)
                    self.assertEqual(one, two)
                    self.assertEqual(restored.draw_report["replay_draws"], 0 if mode == "original" else 64)
                    self.assertEqual(uninterrupted.draw_report["replay_draws"], 0)
                    self.assertEqual(self.finish(uninterrupted, one)[0], self.finish(restored, two)[0])
                    self.assertEqual(uninterrupted.samples, restored.samples)
                    self.assertEqual(uninterrupted.model_report, restored.model_report)
                    self.assertEqual(list(uninterrupted.selected), list(restored.selected))
                    self.assertEqual(uninterrupted.offset, restored.offset)
                    self.assertEqual(restored.raw_draws_total, 102)
                    self.assertEqual(restored.replay_draws_total, 0 if mode == "original" else 64)

    def test_pending_selection_and_audits_survive_json_resume_without_relabeling(self):
        first, second = self.patches()
        with first, second:
            pool = proposals.ProposalPool(self.grammar, 11, "learned")
            records = pool.draw(None, 1, SEARCH)
            audits = self.audits(records)
            selected = pool.select(records, audits)
            saved = json.loads(json.dumps(pool.to_dict()))
            restored = proposals.ProposalPool(self.grammar, 11, "learned", state=saved)
            self.assertEqual(restored.pending_records, records)
            self.assertEqual(restored.selection_indices, selected)
            changed = copy.deepcopy(audits)
            changed[0]["informative"] = False
            with self.assertRaisesRegex(ValueError, "labels changed"):
                restored.observe(records, changed)
            self.assertEqual(restored.samples, [])
            self.assertEqual(pool.observe(records, audits), restored.observe(records, audits))
            self.assertEqual(pool.model_report, restored.model_report)

    def test_frozen_scope_rejects_library_weights_constants_order_and_search_changes(self):
        state = proposals.ProposalPool(self.grammar, 11, "static").to_dict()
        changes = [Grammar(primitives=self.grammar.primitives, constants=self.grammar.constants, weights={"abs": 2}),
                   Grammar(primitives=dict(reversed(list(self.grammar.primitives.items()))), constants=self.grammar.constants),
                   Grammar(primitives=self.grammar.primitives, constants=(Int(-1), Int(0))),
                   Grammar(library={"saved": Int(0)}, primitives=self.grammar.primitives, constants=self.grammar.constants),
                   Grammar(primitives=self.grammar.primitives, constants=self.grammar.constants,
                           context_weights={("ROOT", 0): {"lambda": 2}})]
        for changed in changes:
            with self.assertRaisesRegex(ValueError, "frozen grammar"):
                proposals.ProposalPool(changed, 11, "static", state=state)
        first, second = self.patches()
        with first, second:
            pool = proposals.ProposalPool(self.grammar, 11, "static")
            self.finish(pool, pool.draw(None, 1, SEARCH))
            with self.assertRaisesRegex(ValueError, "search bounds changed"):
                pool.draw(None, 2, {**SEARCH, "max_size": 13})
            pool.grammar.weights["abs"] = 3
            with self.assertRaisesRegex(ValueError, "scope was frozen"):
                pool.draw(None, 2, SEARCH)

    def test_fixed_features_and_annotation_canonicalization(self):
        term = Lam(INT, apply(Prim("add"), Var(0), Int(-1)))
        vector = proposals.features(term)
        values = dict(zip(proposals.FEATURE_NAMES, vector))
        self.assertEqual(values["primitive:add"], 1)
        self.assertEqual(values["lambda"], 1)
        self.assertEqual(values["var"], 1)
        self.assertEqual(values["int"], 1)
        self.assertEqual(values["negative_int"], 1)
        self.assertEqual(values["positive_int"], 0)
        self.assertEqual(values["size"], term.size)
        self.assertEqual(values["depth"], term.depth)
        self.assertEqual(proposals.canonical_term(Lam(TVar("fresh_7"), Var(0))),
                         proposals.canonical_term(Lam(TVar("fresh_194"), Var(0))))
        self.assertEqual(len([name for name in proposals.FEATURE_NAMES if name.startswith("primitive:")]),
                         len(PRIMITIVE_TYPES))

    def test_malformed_checkpoint_and_current_round_training_are_rejected(self):
        first, second = self.patches()
        with first, second:
            pool = proposals.ProposalPool(self.grammar, 11, "learned")
            records = pool.draw(None, 1, SEARCH)
            self.finish(pool, records)
            saved = pool.to_dict()
            for change in ("features", "cycle", "count", "offset"):
                corrupted = copy.deepcopy(saved)
                if change == "features":
                    corrupted["samples"][0]["features"][0] += 1
                elif change == "cycle":
                    corrupted["samples"][0]["cycle"] = 2
                elif change == "count":
                    corrupted["model"]["trained_count"] += 1
                else:
                    corrupted["offset"] = -1
                with self.subTest(change=change), self.assertRaises(ValueError):
                    proposals.ProposalPool(self.grammar, 11, "learned", state=corrupted)
            pending = pool.draw(None, 2, SEARCH)
            with self.assertRaisesRegex(ValueError, "pending round"):
                pool.draw(None, 3, SEARCH)
            current = pool.to_dict()
            current["samples"][0]["cycle"] = 2
            with self.assertRaisesRegex(ValueError, "overlaps observed"):
                proposals.ProposalPool(self.grammar, 11, "learned", state=current)
            with self.assertRaisesRegex(ValueError, "fixed at six"):
                pool.select(pending, self.audits(pending), quota=7)


if __name__ == "__main__":
    unittest.main()
