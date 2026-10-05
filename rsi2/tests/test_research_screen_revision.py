"""A frozen-state comparison must preserve learning and proof provenance."""
import unittest

from rsi2.enumeration import enumerate_programs
from rsi2.grammar import Grammar
from rsi2.research.recursive_bootstrap import RecursiveState, jsonable, state_record
from rsi2.research.screen_revision_run import complete_screen_record, restore_state
from rsi2.types import Arrow, INT


class ScreenRevisionTests(unittest.TestCase):
    def source(self):
        state = RecursiveState(11, "FULL", 1)
        term = next(enumerate_programs(Arrow(INT, INT), Grammar(),
                                      max_size=3, max_expansions=100)).term
        state.raw_solutions = {"own_generated": term}
        state.solutions = dict(state.raw_solutions)
        state.acceptance_records = {"own_generated": {
            "id": "TRAIN:verified:1", "verification": {"passed": True}}}
        state.grammar.fit([(term, Arrow(INT, INT))])
        return {"final_state": jsonable(state_record(state))}

    def test_restore_preserves_actual_programs_and_fitted_grammar(self):
        source = self.source()
        restored = restore_state(source)
        self.assertEqual(jsonable(state_record(restored)), source["final_state"])

    def test_missing_bank_provenance_is_rejected(self):
        source = self.source()
        source["final_state"]["acceptance_records"] = {}
        with self.assertRaises(ValueError):
            restore_state(source)

    def test_failed_or_missing_verification_is_not_an_accepted_bank(self):
        for verification in ({}, {"passed": False}, {"passed": 1}):
            source = self.source()
            source["final_state"]["acceptance_records"]["own_generated"]["verification"] = verification
            with self.assertRaises(ValueError):
                restore_state(source)

    def test_completion_requires_every_persisted_screen_and_task(self):
        record = {"status": "complete", "screens": [
            {"candidate": label, **{method: {
                "status": "complete", "tasks_completed": 4,
                "records": [{"name": f"task{number}", "solved": False} for number in range(4)]}
                for method in ("original", "reserved")}}
            for label in ("incumbent", "0", "1", "2", "3", "4", "5")]}
        self.assertTrue(complete_screen_record(record))
        record["screens"][-1]["reserved"]["records"].pop()
        self.assertFalse(complete_screen_record(record))


if __name__ == "__main__":
    unittest.main()
