"""Replay the retained, partial generation-1 TRAIN population pilot evidence.

This auditor accepts explicit JSON or gzip-compressed JSON files. It supports
only the frozen pilot record shape: completed generation 0, partial generation
1, and six completed B16 heuristic screens. It does not audit future controller
formats or rerun a search frontier. It opens only the unchanged TRAIN corpus.

Example:
    python -m rsi2.research.recursive_pilot_audit \
        --artifact rsi2/research/recursive_bootstrap_results/FULL_seed11.json.gz \
        --summary rsi2/research/recursive_bootstrap_results/summary.json \
        --output /tmp/recursive-pilot-audit.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import time

from ..abstraction import description_length
from ..corpus import load_train
from ..evaluator import evaluate
from .proposals import canonical_term
from .repair_search import _normalize_beta
from ..search import flatten
from ..terms import Term, replace_subterm
from ..types import infer, unify


def same(a, b):
    return type(a) is type(b) and (
        len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if isinstance(a, (list, tuple)) else a == b)


def term_map(value):
    return {name: Term.from_dict(v) for name, v in value.items()}


def read_json(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def validate_scope(record, summary):
    """Fail closed rather than silently claim compatibility with new engines."""
    generations = record.get("generations", [])
    current = record.get("in_progress") or {}
    screens = (current.get("heuristic") or {}).get("candidates", [])
    config = record.get("config") or {}
    wake = (generations[0].get("wake") or {}) if len(generations) == 1 else {}
    wake_records = wake.get("records", [])
    limits = config.get("search") or {}
    frozen_limits = {"max_size": 12, "max_expansions": 20000, "step_budget": 2000,
                     "beta_normalize": True, "max_normalization_steps": 20000,
                     "force_wrapper_lambdas": True}
    names = [r.get("name") for r in wake_records]
    if (record.get("source") != "TRAIN only" or summary.get("source") != "TRAIN only"
            or record.get("status") != "partial" or summary.get("status") != "partial"
            or [r.get("generation") for r in generations] != [0]
            or current.get("generation") != 1
            or config.get("schema_version") != 1 or config.get("kernel") != "population"
            or config != summary.get("config")
            or any(type(limits.get(key)) is not type(value) or limits.get(key) != value
                   for key, value in frozen_limits.items())
            or wake.get("status") != "complete" or wake.get("budget") != 64
            or wake.get("tasks") != 36 or wake.get("tasks_completed") != 36
            or len(wake_records) != 36 or len(set(names)) != 36
            or any(type(r.get("solved")) is not bool for r in wake_records)
            or len(screens) != 6
            or any((c.get("screen") or {}).get("status") != "complete"
                   or c["screen"].get("budget") != 16
                   or c["screen"].get("tasks") != 4
                   or c["screen"].get("tasks_completed") != 4
                   or len(c["screen"].get("records", [])) != 4
                   or [r.get("name") for r in c["screen"].get("records", [])] != names[:4]
                   or any(type(r.get("solved")) is not bool
                          for r in c["screen"].get("records", [])) for c in screens)):
        raise ValueError("unsupported artifact: requires the retained partial generation-1 TRAIN pilot")
    if record.get("evaluation_partitions_opened") is not False:
        raise ValueError("pilot record does not assert sealed heldout partitions")


def audit(artifact, summary_path):
    started = time.process_time()
    x, summary = read_json(artifact), read_json(summary_path)
    validate_scope(x, summary)
    train = {t.name: t for t in load_train()}
    if sorted(r["name"] for r in x["generations"][0]["wake"]["records"]) != sorted(train):
        raise ValueError("generation-0 task coverage differs from the original TRAIN corpus")
    errors, kernel_rows, proofs = [], [], []
    work = Counter()
    row_kernel_cost = Counter()
    measurement_rows = []
    generations = x['generations'] + [x.get('in_progress', {})]
    for row in generations:
        if not row:
            continue
        generation = row['generation']
        pre_library = {} if generation == 0 else term_map(x['generations'][-1]['state']['library'])
        post_library = term_map((row.get('state') or x['final_state'])['library'])
        heuristic = row.get('heuristic') or {}
        phases = [('wake', row.get('wake'), pre_library),
                  ('same_state_zero', row.get('same_state_zero'), pre_library),
                  ('incumbent', heuristic.get('incumbent_full'), post_library)]
        for candidate in heuristic.get('candidates', []):
            phases += [(f'screen:{candidate["index"]}', candidate.get('screen'), post_library),
                       (f'full:{candidate["index"]}', candidate.get('full'), post_library)]
        for label, measurement, library in phases:
            if not measurement:
                continue
            measurement_rows.append({'generation': generation, 'phase': label,
                'status': measurement['status'], 'solved': measurement['solved'],
                'tasks_completed': measurement['tasks_completed'], 'persisted_records': len(measurement['records']),
                'budget': measurement['budget']})
            heuristic_term = Term.from_dict(measurement['heuristic'])
            for record in measurement['records']:
                context = [generation, label, record['name']]
                search = record['search']
                trials = search['trials']
                n = search['candidates']
                if n != len(trials) or [trial['id'] for trial in trials] != list(range(n)):
                    errors.append(context + ['trial_ids/count'])
                if n > measurement['budget'] or search['expansions'] > 20000 or search['normalization_steps'] > 20000:
                    errors.append(context + ['budget_bound'])
                if search['canonicalization_steps'] > search['normalization_steps']:
                    errors.append(context + ['canonicalization_quota'])
                if search['seed_candidates'] + search['repair_candidates'] != n:
                    errors.append(context + ['root_descendant_accounting'])
                if len({json.dumps(trial['term'], sort_keys=True) for trial in trials}) != n:
                    errors.append(context + ['duplicate_actual_terms'])
                replay = Counter()
                heuristic_cache = {}
                task = train[record['name']]
                target = flatten([expected for _, expected in task.examples])
                for trial in trials:
                    term = Term.from_dict(trial['term'])
                    raw_term = Term.from_dict(trial['raw_term'])
                    try:
                        unify(infer(term, library=library), task.request_type)
                    except Exception as exc:
                        errors.append(context + [trial['id'], 'type', str(exc)])
                    if term.size > 12 or raw_term.size > 12:
                        errors.append(context + [trial['id'], 'size'])
                    normalized = canonical_term(_normalize_beta(raw_term, lambda: None, lambda: None))
                    if normalized != term:
                        errors.append(context + [trial['id'], 'normalization_reconstruction'])
                    if trial['parent_id'] is not None:
                        parent_id = trial['parent_id']
                        if not 0 <= parent_id < trial['id']:
                            errors.append(context + [trial['id'], 'parent_id'])
                        else:
                            parent = trials[parent_id]
                            if trial['root_id'] != parent['root_id'] or trial['depth'] != parent['depth'] + 1:
                                errors.append(context + [trial['id'], 'genealogy'])
                            reconstructed = replace_subterm(Term.from_dict(parent['term']), tuple(trial['path']),
                                                           Term.from_dict(trial['replacement']))
                            if reconstructed != raw_term:
                                errors.append(context + [trial['id'], 'edit_reconstruction'])
                    elif trial['root_id'] != trial['id'] or trial['depth'] != 0:
                        errors.append(context + [trial['id'], 'root_genealogy'])
                    outputs, matched, failure = [], 0, None
                    for inputs, expected in task.examples:
                        assessment = evaluate(term, inputs, library=library, step_budget=2000)
                        replay['evaluator_calls'] += 1
                        replay['evaluation_steps'] += assessment.steps
                        if not assessment.ok:
                            failure, outputs = assessment.error, []
                            break
                        outputs.append(assessment.value)
                        matched += assessment.value == expected
                    if trial['incomplete']:
                        # A CPU-interrupted assessment can contain an unknown public prefix.
                        errors.append(context + [trial['id'], 'interrupted_trial_requires_prefix_replay'])
                        continue
                    if not same(outputs, trial['outputs']) or matched != trial['matched_examples'] or failure != trial['runtime_failure']:
                        errors.append(context + [trial['id'], 'public_evaluator_replay'])
                    if trial['public_match'] != (matched == len(task.examples)):
                        errors.append(context + [trial['id'], 'public_match_flag'])
                    if trial['public_match']:
                        continue
                    if trial['heuristic_incomplete']:
                        errors.append(context + [trial['id'], 'interrupted_heuristic_requires_prefix_replay'])
                        continue
                    replay['heuristic_calls'] += 1
                    flat_outputs = flatten(outputs)
                    key = (tuple(flat_outputs), term.size, term.depth)
                    if key not in heuristic_cache:
                        assessment = evaluate(heuristic_term, (flat_outputs, target, term.size, term.depth),
                                              library=library, step_budget=2000)
                        replay['heuristic_evaluations'] += 1
                        replay['heuristic_steps'] += assessment.steps
                        valid = assessment.ok and type(assessment.value) is int and assessment.value.bit_length() <= 1023
                        if not valid:
                            replay['heuristic_failures'] += 1
                        heuristic_cache[key] = (assessment.value if valid else 0,
                            None if valid else assessment.error or 'heuristic must return a bounded integer')
                    score, hfailure = heuristic_cache[key]
                    if score != trial['heuristic_score'] or hfailure != trial['heuristic_failure']:
                        errors.append(context + [trial['id'], 'heuristic_replay'])
                for field in ['evaluator_calls', 'evaluation_steps', 'heuristic_calls', 'heuristic_evaluations',
                              'heuristic_steps', 'heuristic_failures']:
                    if replay[field] != search[field]:
                        errors.append(context + [field, 'kernel_replay_counter', search[field], replay[field]])
                for origin, target_field in [('candidates', 'task_candidates'), ('evaluator_calls', 'task_example_evaluations'),
                            ('evaluation_steps', 'task_evaluator_steps')]:
                    work[target_field] += search[origin]
                for field in ['heuristic_calls', 'heuristic_evaluations', 'heuristic_steps', 'heuristic_failures',
                              'expansions', 'normalization_steps', 'beta_reductions']:
                    work[field] += search[field]
                row_kernel_cost[generation] += search['cpu_seconds']
                kernel_rows.append({'generation': generation, 'phase': label, 'task': record['name'],
                    'candidates': n, 'roots': search['seed_candidates'], 'descendants': search['repair_candidates'],
                    'expansions': search['expansions'], 'normalization_steps': search['normalization_steps'],
                    'termination': search['termination'], 'cpu_seconds': search['cpu_seconds']})
                proof = record.get('verification')
                if proof:
                    proofs.append(proof)
        learning = row.get('learning') or {}
        compression = learning.get('compression') or {}
        if compression:
            proofs.append({'cost': compression['cost']})
        for candidate in heuristic.get('candidates', []):
            for name in ['semantic_probe', 'train_probe']:
                probe = candidate.get(name)
                if probe:
                    for origin, target_field in [('program_evaluations', 'probe_programs'),
                            ('example_evaluations', 'probe_examples'), ('evaluator_steps', 'probe_steps')]:
                        work[target_field] += probe[origin]
        if heuristic.get('provider'):
            provider_work = heuristic['provider']['work']
            for origin, target_field in [('frontier_pops', 'proposal_frontier_pops'),
                        ('generated_full_candidates', 'proposal_raw_terms'), ('replayed_ast_draws', 'proposal_replayed_terms'),
                        ('normalization_steps', 'proposal_normalization_steps'), ('beta_reductions', 'proposal_beta_reductions')]:
                work[target_field] += provider_work[origin]
            work['proposal_slots'] += len(heuristic['candidates'])
            work['proposal_terms'] += sum(c.get('term') is not None for c in heuristic['candidates'])
    for proof in proofs:
        for origin, target_field in [('program_evaluations', 'verification_programs'),
                    ('example_evaluations', 'verification_examples'), ('evaluator_steps', 'verification_steps')]:
            work[target_field] += proof['cost'][origin]

    reconciliation = {}
    unreplayable_fields = ['dream_sampling_calls', 'dream_programs', 'dream_examples', 'dream_steps']
    for field, actual in x['work'].items():
        if field in unreplayable_fields:
            reconciliation[field] = {'artifact': actual, 'independent': None,
                'scope': 'aggregate only; sampled dream ASTs and per-call outcomes are not persisted'}
        else:
            reconciliation[field] = {'artifact': actual, 'independent': work[field], 'exact': actual == work[field]}
            if actual != work[field]:
                errors.append(['aggregate_work_counter', field, actual, work[field]])
    if summary['work'] != x['work']:
        errors.append(['summary_work_mismatch'])

    checks = []
    states = [(f'g{r["generation"]}', r['state']) for r in x['generations']]
    states.append(('final_state', x['final_state']))
    for label, state in states:
        library = term_map(state['library'])
        for bank in ['solutions', 'raw_solutions']:
            for name, v in state[bank].items():
                term, task = Term.from_dict(v), train[name]
                unify(infer(term, library=library), task.request_type)
                failures, steps = [], 0
                for part, examples in [('public', task.examples), ('hidden', task.hidden)]:
                    for index, (inputs, expected) in enumerate(examples):
                        result = evaluate(term, inputs, library=library, step_budget=2000)
                        steps += result.steps
                        if not result.ok or not same(result.value, expected):
                            failures.append([part, index, result.error or 'output_mismatch'])
                checks.append({'state': label, 'bank': bank, 'name': name,
                    'examples': len(task.examples) + len(task.hidden), 'steps': steps,
                    'passed': not failures, 'failures': failures})

    screens = x['in_progress']['heuristic']['candidates']
    screen_sequences, screen_details = [], []
    for candidate in screens:
        seq = [(r['name'], [trial['term'] for trial in r['search']['trials']])
               for r in candidate['screen']['records']]
        serial = json.dumps(seq, sort_keys=True, separators=(',', ':')).encode()
        screen_sequences.append(serial)
        screen_details.append({'index': candidate['index'],
            'candidates': sum(r['search']['candidates'] for r in candidate['screen']['records']),
            'descendants': sum(r['search']['repair_candidates'] for r in candidate['screen']['records']),
            'parent_selections': sum(len(r['search']['parent_selections']) for r in candidate['screen']['records']),
            'solved': candidate['screen']['solved']})

    original_solutions = term_map(x['generations'][0]['state']['solutions'])
    final_solutions = term_map(x['final_state']['solutions'])
    final_library = term_map(x['final_state']['library'])
    mdl = {'before_independent': description_length(original_solutions, {}),
           'after_independent': description_length(final_solutions, final_library),
           'steps_before_independent': sum(c['steps'] for c in checks if c['state'] == 'g0' and c['bank'] == 'solutions'),
           'steps_after_independent': sum(c['steps'] for c in checks if c['state'] == 'final_state' and c['bank'] == 'solutions'),
           'entry_identity': all(t.tag == 'lam' and t.children[0].tag == 'var' and t.children[0].value == 0
                                 for t in final_library.values()),
           'new_task_capability_claim': False}

    equal_screens = all(seq == screen_sequences[0] for seq in screen_sequences)
    root_only_screens = all(d['descendants'] == d['parent_selections'] == 0
                            for d in screen_details)
    blindness = ('For this record, all screen sequences are identical and contain no descendants or parent selections; root-only B16 screening cannot observe scorer-guided edits.'
                 if equal_screens and root_only_screens else
                 'Screen blindness is not established by the observed sequences and descendant/parent-selection counts.')
    evidence = {'artifact': str(artifact), 'summary': str(summary_path),
        'terminal_status': summary['status'], 'stop_reason': summary['stop_reason'],
        'aggregate_cpu_seconds': summary['cpu_seconds'], 'worker_checkpoint_cpu_seconds': x['cpu_seconds'],
        'completed_generations': [r['generation'] for r in x['generations']],
        'in_progress_generation': x['in_progress']['generation'], 'measurement_rows': measurement_rows,
        'kernel_rows': kernel_rows, 'kernel_cpu_sum': sum(row_kernel_cost.values()),
        'unattributed_worker_controller_cpu_upper_bound': x['cpu_seconds'] - sum(row_kernel_cost.values()),
        'all_validation_errors': errors, 'aggregate_work_reconciliation': reconciliation,
        'retained_solution_replay': checks, 'all_retained_solution_replay_pass': all(c['passed'] for c in checks),
        'screen_sequences': screen_details, 'all_six_screen_ast_sequences_exactly_equal': equal_screens,
        'all_screens_zero_descendants_and_parent_selections': root_only_screens,
        'screen_blindness_mechanism': blindness,
        'compression_replay': mdl, 'heuristic_history': x['final_state']['heuristic_history'],
        'heldout_partitions_opened': False, 'rsi_success': False,
        'supported_artifact_scope': 'original partial generation-1 population pilot; later controller formats require a separately reviewed auditor',
        'audit_limits': [
            'No search frontier replay: expansion counts are reconciled to recorded rows and caps, not independent heap-pop execution.',
            'Four dream counters are grouped only: individual sampled ASTs/outcomes are absent from this retained artifact.',
            'Interrupted physical work can exceed persisted completed-operation totals.',
            'Unattributed controller CPU is an upper bound; this replay does not profile its components.'],
        'audit_cpu_seconds': time.process_time() - started,
        'independence_scope': 'TRAIN-only interpreter replay and evidence consistency; no heldout corpus and no rerun of the full synthesis frontier'}
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    evidence = audit(args.artifact, args.summary)
    output = Path(args.output)
    if output.resolve() in (Path(args.artifact).resolve(), Path(args.summary).resolve()):
        raise ValueError("audit output must not overwrite an input artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: evidence[key] for key in (
        "terminal_status", "aggregate_cpu_seconds", "completed_generations",
        "all_validation_errors", "all_retained_solution_replay_pass",
        "all_six_screen_ast_sequences_exactly_equal",
        "all_screens_zero_descendants_and_parent_selections", "audit_cpu_seconds")}))
    return 1 if (evidence["all_validation_errors"] or
                 not evidence["all_retained_solution_replay_pass"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
