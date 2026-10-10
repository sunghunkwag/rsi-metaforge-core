"""Independent parent-gate checks using synthetic, fully verified TRAIN tasks."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rsi2.research import arity_diagnostic_run as runner
from rsi2.tests import test_research_coordinate_diagnostic_run as fixtures


class Budget:
    terminal_written = False
    exhaust_after_terminal = False

    def __init__(self, limit):
        self.limit, self.cleanup_margin = limit, 2

    def spent(self):
        return 601 if self.terminal_written and self.exhaust_after_terminal else 5

    def exhausted(self):
        return self.spent() >= self.limit


class ArityDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.CoordinateDiagnosticTests.setUpClass()

    def setUp(self):
        Budget.terminal_written = False
        Budget.exhaust_after_terminal = False
        self.fixture = fixtures.CoordinateDiagnosticTests()
        self.tasks = self.fixture.tasks(36)
        self.names = [task.name for task in self.tasks]
        self.source = self.fixture.source(self.tasks)
        self.seen, self.budgets = [], []

    def phase(self, kind, keys, output, config, budget, **options):
        key = keys[0]
        self.seen.append((key, copy.deepcopy(config)))
        self.budgets.append(budget)
        self.assertEqual(kind, 'arity_diagnostic')
        self.assertEqual(options['workers'], 1)
        spec = runner.variant_spec(key)
        base_solver = self.fixture.solver()

        def solver(*args, **kwargs):
            result = base_solver(*args, **kwargs)
            result.edit_mode = 'arity_coordinates' if spec['arity_context'] else 'coordinates'
            result.neighborhood_work = {'eta_exposure': True}
            if spec['arity_context']:
                result.neighborhood_work.update(arity_context=True, production_priority=False)
            if getattr(self, 'wrong_kernel_identity', False) and spec['arity_context']:
                result.edit_mode = 'coordinates'
                result.neighborhood_work = {'eta_exposure': True}
            return result

        if getattr(self, 'omit_checkpoint', False):
            result = {'status': 'complete', 'tasks_completed': 36}
        else:
            result = runner.run_condition(self.tasks, self.source, spec['common_condition'],
                Path(output) / f'{key}.checkpoint.json', config,
                kernels={'coordinates': solver})
        return {'results': {key: {'result': result}}, 'reason': None,
                'started': [key], 'observed_cpu': {key: 1}, 'elapsed_wall': {key: 1}}

    def run_campaign(self, folder, *, writer=None):
        with patch.object(runner, 'CPUController', Budget), \
             patch.object(runner, 'training_names', return_value=self.names), \
             patch.object(runner, '_run_phase', self.phase):
            if writer is None:
                return runner.run_diagnostic('synthetic-source.json', folder)
            with patch.object(runner, 'atomic_write', writer):
                return runner.run_diagnostic('synthetic-source.json', folder)

    def test_registered_order_variants_share_one_budget_and_remain_nonrecursive(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_campaign(folder)
        self.assertEqual([key for key, _ in self.seen], list(runner.ORDER))
        self.assertEqual(len({id(budget) for budget in self.budgets}), 1)
        for key, config in self.seen:
            self.assertEqual(config['implementation_variant'], runner.variant_spec(key))
            self.assertFalse(config['production_priority'])
        self.assertEqual(result['status'], 'complete')
        self.assertFalse(result['rsi_success'])
        self.assertFalse(result['learned_improvement'])
        self.assertTrue(all(row['status'] == 'complete' for row in result['conditions'].values()))
        self.assertTrue(all(not row['strict_expansion'] for row in result['comparisons']))

    def test_terminal_event_without_persisted_checkpoint_is_partial_and_stops_followups(self):
        self.omit_checkpoint = True
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_campaign(folder)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual([key for key, _ in self.seen], ['cold_baseline'])
        self.assertEqual(result['conditions']['cold_baseline']['status'], 'partial')
        self.assertTrue(all(result['conditions'][key]['status'] == 'unrun' for key in runner.ORDER[1:]))
        self.assertTrue(all(row['status'] == 'UNKNOWN' for row in result['comparisons']))

    def test_actual_kernel_identity_must_match_registered_variant(self):
        self.wrong_kernel_identity = True
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_campaign(folder)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['conditions']['cold_arity']['status'], 'partial')
        self.assertEqual([key for key, _ in self.seen], ['cold_baseline', 'cold_arity'])

    def test_aggregate_overrun_after_terminal_write_cannot_publish_positive_admission(self):
        Budget.exhaust_after_terminal = True
        original_write = runner.atomic_write

        def writer(path, record):
            original_write(path, record)
            if path.name == 'summary.json' and record['status'] == 'complete':
                Budget.terminal_written = True

        # Simulate a genuinely positive paired comparison to ensure that the
        # aggregate campaign gate, rather than an incidental tie, vetoes it.
        def positive(conditions, memory):
            return {'memory': memory, 'status': 'complete', 'strict_expansion': True,
                    'gains': ['new-task'], 'losses': []}

        with tempfile.TemporaryDirectory() as folder, patch.object(runner, 'compare', positive):
            result = self.run_campaign(folder, writer=writer)
        self.assertEqual(result['status'], 'partial')
        self.assertGreaterEqual(result['cpu_seconds'], runner.CONFIG['cpu_limit_seconds'])
        self.assertTrue(result.get('candidate_kernel_admitted') is False or
                        all(row['status'] == 'UNKNOWN' and not row['strict_expansion']
                            for row in result['comparisons']))

    def test_pair_admission_requires_complete_strict_superset_not_larger_count(self):
        def conditions(before, after, status='complete'):
            return {'cold_baseline': {'status': 'complete', 'solved_names': before},
                    'cold_arity': {'status': status, 'solved_names': after}}
        self.assertTrue(runner.compare(conditions(['a'], ['a', 'b']), 'cold')['strict_expansion'])
        self.assertFalse(runner.compare(conditions(['a'], ['b', 'c']), 'cold')['strict_expansion'])
        self.assertFalse(runner.compare(conditions(['a'], ['a', 'b'], 'partial'), 'cold')['strict_expansion'])
        self.assertEqual(runner.compare({}, 'cold')['status'], 'UNKNOWN')

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / 'sentinel.txt'
            sentinel.write_text('historical evidence')
            with self.assertRaises(FileExistsError):
                self.run_campaign(folder)
            self.assertEqual(sentinel.read_text(), 'historical evidence')
