"""Independent actual-record replay for the frozen TRAIN coordinate diagnostic.

From the repository root:
  python -m rsi2.research.coordinate_diagnostic_results.independent.replay \
    --output /tmp/coordinate-independent-new

Only TRAIN data and existing recorded candidates are loaded. This performs no
new search and never opens VALID, TEST, or external audit partitions. Every
recorded candidate output/score and derivation edge is replayed; selected
solutions are rechecked on both public and hidden TRAIN examples. Output
must be new/empty so historical measurements cannot be overwritten.
"""
import json,time,resource
from collections import Counter
from pathlib import Path
from rsi2.corpus import load_train
from rsi2.evaluator import evaluate
from rsi2.grammar import Grammar,_spine
from rsi2.heuristics import zero_heuristic
from rsi2.research.compression import verify_solutions,_same_value
from rsi2.research.coordinate_diagnostic_run import _complete_record,condition_spec,SEARCH_WORK,NEIGHBORHOOD_WORK,PROOF_WORK
from rsi2.research.derivation_neighborhood import reconstruct_neighbor
from rsi2.research.journal_checkpoint import reconstruct
from rsi2.research.proposals import canonical_term
from rsi2.research.repair_search import beta_normal_form
from rsi2.search import flatten
from rsi2.terms import Term,replace_subterm
from rsi2.types import infer,unify

folder = reports = None
train = {}

def spines(term):
    todo=[(term,False)]
    while todo:
        node,function_child=todo.pop()
        if not function_child:
            head,args=_spine(node)
            if args: yield head,len(args)
        todo.extend((child,node.tag=='app' and i==0) for i,child in enumerate(node.children))

def audit(key):
    started=time.process_time()
    r=reconstruct(folder/f'{key}.checkpoint.json').record
    assert r['status']=='complete'
    assert _complete_record(r,r['config'],condition_spec(key),sorted(train))
    expected_work={f:0 for f in SEARCH_WORK}
    for f in NEIGHBORHOOD_WORK: expected_work['neighborhood_'+f]=0
    for f in PROOF_WORK: expected_work['verification_'+f]=0
    programs={p['task']:Term.from_dict(p['term']) for p in r['source_bank']['programs']}
    bank_proof=verify_solutions(programs,{},train.values(),step_budget=2000)
    assert bank_proof['passed']
    for f in PROOF_WORK:
        assert bank_proof['cost'][f]==r['source_bank']['proof']['cost'][f]
        expected_work['verification_'+f]+=bank_proof['cost'][f]
    total_trials=total_edges=coordinate_edges=public_calls=public_steps=actual_hcalls=actual_hsteps=0
    interrupted=[]; operations=Counter(); task_coverage=[]; solves=[]
    for row in r['tasks']:
        task=train[row['name']]; s=row['search']; h=zero_heuristic(); grammar=Grammar()
        for f in SEARCH_WORK: expected_work[f]+=s.get('logical_evaluations',s[f]) if f=='candidates' else s[f]
        for f in NEIGHBORHOOD_WORK: expected_work['neighborhood_'+f]+=s.get('neighborhood_work',{}).get(f,0)
        assert s['candidates']==len(s['trials']) and s['seed_candidates']+s['repair_candidates']==s['candidates']
        assert s['canonicalization_steps']<=s['normalization_steps']<=20000 and s['expansions']<=20000
        assert len({json.dumps(t['term'],sort_keys=True) for t in s['trials']})==s['candidates']
        trialmap={t['id']:t for t in s['trials']}; roots={z['trial_id']:z for z in s['seed_records']}
        cache={}; local_calls=local_steps=local_hcalls=local_hevals=local_hsteps=local_hfails=0
        target=flatten([out for _,out in task.examples]); root_arities=Counter(); all_arities=Counter(); heads=Counter()
        for trial in s['trials']:
            total_trials+=1; term=Term.from_dict(trial['term']); raw=Term.from_dict(trial['raw_term'])
            assert term.size<=12 and raw.size<=12 and canonical_term(term)==term
            unify(infer(term,library={}),task.request_type)
            normalized=beta_normal_form(raw); assert normalized.complete and canonical_term(normalized.term)==term
            assert trial['root_id'] in roots
            for head,arity in spines(term):
                all_arities[arity]+=1
                if head.tag=='prim': heads[head.value]+=1
                if trial['parent_id'] is None: root_arities[arity]+=1
            if trial['parent_id'] is not None:
                parent=trialmap[trial['parent_id']]
                assert trial['parent_id']<trial['id'] and parent['root_id']==trial['root_id'] and trial['depth']==parent['depth']+1
                rebuilt=replace_subterm(Term.from_dict(parent['term']),tuple(trial['path']),Term.from_dict(trial['replacement']))
                assert rebuilt==raw
                if 'edit_provenance' in trial:
                    metadata=trial['edit_provenance']
                    reconstructed=reconstruct_neighbor(Term.from_dict(parent['term']),task.request_type,grammar,metadata)
                    assert reconstructed==raw and metadata['replacement']==trial['replacement']
                    coordinate_edges+=1; operations[metadata['operator']]+=1
                total_edges+=1
            else:
                assert trial['root_id']==trial['id'] and trial['depth']==0 and roots[trial['id']]['term']==trial['raw_term']
            outputs=[]; matched=0; failure=None
            examples=task.examples if not trial['incomplete'] else task.examples[:len(trial['outputs'])]
            if trial['incomplete'] and trial['runtime_failure'] is not None: examples=task.examples
            for inputs,expected in examples:
                assessment=evaluate(term,inputs,library={},step_budget=2000); local_calls+=1; local_steps+=assessment.steps
                if not assessment.ok: failure=assessment.error; outputs=[]; break
                outputs.append(assessment.value); matched+=assessment.value==expected
            assert _same_value(outputs,trial['outputs']) and matched==trial['matched_examples'] and failure==trial['runtime_failure']
            assert trial['public_match']==(not trial['incomplete'] and matched==len(task.examples))
            if trial['incomplete'] or trial['heuristic_incomplete']:
                interrupted.append({'task':task.name,'trial':trial['id'],'public_incomplete':trial['incomplete'],'heuristic_incomplete':trial['heuristic_incomplete']})
                continue
            if trial['public_match']: assert trial['heuristic_score'] is None; continue
            local_hcalls+=1; keyh=(tuple(flatten(outputs)),term.size,term.depth)
            if keyh not in cache:
                assessment=evaluate(h,(list(keyh[0]),target,term.size,term.depth),library={},step_budget=2000)
                local_hevals+=1; local_hsteps+=assessment.steps
                valid=assessment.ok and type(assessment.value) is int and assessment.value.bit_length()<=1023
                local_hfails+=not valid
                cache[keyh]=(assessment.value if valid else 0,None if valid else assessment.error or 'heuristic must return a bounded integer')
            assert cache[keyh]==(trial['heuristic_score'],trial['heuristic_failure'])
        assert (local_calls,local_steps)==(s['evaluator_calls'],s['evaluation_steps'])
        if not any(x['task']==task.name for x in interrupted):
            assert (local_hcalls,local_hevals,local_hsteps,local_hfails)==(s['heuristic_calls'],s['heuristic_evaluations'],s['heuristic_steps'],s['heuristic_failures'])
        public_calls+=local_calls; public_steps+=local_steps; actual_hcalls+=local_hevals; actual_hsteps+=local_hsteps
        if s['term'] is not None:
            selected=Term.from_dict(s['term']); proof=verify_solutions({task.name:selected},{},[task],step_budget=2000)
            assert proof['passed']==row['verification']['passed']
            for f in PROOF_WORK:
                assert proof['cost'][f]==row['verification']['cost'][f]
                expected_work['verification_'+f]+=proof['cost'][f]
            assert row['solved']==(proof['passed'] and not row['policy_deadline_exceeded'])
            if row['solved']: solves.append(task.name)
        else: assert not row['solved']
        task_coverage.append({'task':task.name,'solved':row['solved'],'termination':s['termination'],'roots':s['seed_candidates'],'descendants':s['repair_candidates'],
            'attempted_application_arities':dict(sorted(all_arities.items())),'root_application_arities':dict(sorted(root_arities.items())),
            'attempted_primitive_spine_heads':dict(heads),'new_high_arity_support':sorted(set(a for a in all_arities if a>=2)-set(root_arities)),
            'neighborhood_work':s.get('neighborhood_work'), 'compiler_steps':s['normalization_steps'],'expansions':s['expansions']})
    for f,total in expected_work.items(): assert r['work'][f]==total,(key,f,r['work'][f],total)
    assert sorted(solves)==r['solved_names']
    result={'status':'PASS','condition':key,'scope':'independent actual TRAIN evidence replay; no search/proposal/heldout loading',
        'task_searches':36,'candidate_trials':total_trials,'reconstructed_edges':total_edges,'reconstructed_coordinate_edges':coordinate_edges,
        'public_example_calls':public_calls,'public_evaluator_steps':public_steps,'actual_heuristic_evaluations_replayed':actual_hcalls,'actual_heuristic_steps_replayed':actual_hsteps,
        'proof_cost_and_work_reconciliation':'exact','solved_names':sorted(solves),'interrupted_trials':interrupted,
        'coordinate_operators':dict(operations),'task_coverage':task_coverage,'audit_verification_cpu_seconds':time.process_time()-started}
    (reports/(key+'.json')).write_text(json.dumps(result,indent=2)+'\n');return result

if __name__ == '__main__':
    import argparse
    from rsi2.research.coordinate_diagnostic_run import REGISTERED_CONFIG, B64_ORDER, select_b640
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folder, reports = args.source.resolve(), args.output.resolve()
    if reports.exists() and any(reports.iterdir()):
        raise FileExistsError('Independent replay requires a new/empty output directory')
    reports.mkdir(parents=True, exist_ok=True)
    train = {task.name: task for task in load_train()}
    summary = json.loads((folder / 'summary.json').read_text())
    assert summary['status'] == 'complete'
    assert summary['evaluation_partitions_opened'] is False
    assert summary['rsi_success'] is False
    assert summary['cpu_seconds'] < REGISTERED_CONFIG['cpu_limit_seconds']
    for field, value in REGISTERED_CONFIG.items():
        assert summary['config'][field] == value, field
    memory, reason = select_b640(summary['conditions'])
    assert summary['b640_selection'] == {'memory': memory, 'reason': reason}
    expected_order = [*B64_ORDER, f'{memory}_population_B640', f'{memory}_coordinates_B640']
    assert list(summary['conditions']) == expected_order
    assert [phase['condition'] for phase in summary['phases']] == expected_order
    results = []
    for key, recorded in summary['conditions'].items():
        recovery = reconstruct(folder / f'{key}.checkpoint.json')
        record = recovery.record
        replay = audit(key)
        assert recovery.interrupted is False and recovery.ignored_bytes == 0
        assert replay['solved_names'] == recorded['solved_names']
        assert record['work'] == recorded['work']
        assert len(record['tasks']) == recorded['tasks_completed'] == 36
        assert recorded['status'] == record['status'] == 'complete'
        for field, value in REGISTERED_CONFIG.items():
            assert record['config'][field] == value, (key, field)
        row = {
            'condition': key,
            'recovery': {'interrupted': recovery.interrupted,
                         'committed_bytes': recovery.committed_bytes,
                         'ignored_bytes': recovery.ignored_bytes,
                         'objects': recovery.journal_objects},
            'status': replay['status'], 'solved_names': replay['solved_names'],
            'trials': replay['candidate_trials'], 'edges': replay['reconstructed_edges'],
            'coordinate_edges': replay['reconstructed_coordinate_edges'],
            'work': record['work'], 'public_calls_replayed': replay['public_example_calls'],
            'heuristic_evaluations_replayed': replay['actual_heuristic_evaluations_replayed'],
            'termination': dict(Counter(task['search']['termination'] for task in record['tasks'])),
            'interrupted_trials': replay['interrupted_trials'],
            'audit_cpu_seconds': replay['audit_verification_cpu_seconds'],
        }
        results.append(row)
        print(json.dumps({field: row[field] for field in
              ('condition', 'status', 'solved_names', 'trials', 'edges', 'termination',
               'interrupted_trials', 'audit_cpu_seconds')}), flush=True)
    output = {
        'scope': 'independent replay of complete registered TRAIN-only coordinate diagnostic; no search or heldout partitions',
        'status': 'PASS', 'registered_total_cpu_seconds': summary['cpu_seconds'],
        'registered_total_wall_seconds': summary['wall_seconds'],
        'diagnostic_status': summary['status'], 'b640_selection': summary['b640_selection'],
        'conditions': results, 'audit_total_cpu_seconds': time.process_time(),
    }
    (reports / 'summary.json').write_text(json.dumps(output, indent=2) + '\n')
