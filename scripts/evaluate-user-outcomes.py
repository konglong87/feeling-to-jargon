#!/usr/bin/env python3
"""Measure the same raw CLI inputs; timings include process startup."""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from routing_policy import ROOT

KEY_CASES={'backend-technical','backend-vague','quality','industrial-title','capacity','idempotency','undo','effects'}

def measure(case,extra):
    start=time.perf_counter()
    process=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/query-index.py'),case['query'],*case['options'],*extra],capture_output=True,text=True,check=True)
    elapsed=(time.perf_counter()-start)*1000
    output=json.loads(process.stdout)
    ids=[item['leaf_id'] for item in output['matches']]
    row={'case_id':case['id'],'query':case['query'],'leaf_ids':ids,
         'entry_ids':[entry['id'] for match in output['matches'] for entry in match['entries']],
         'loaded_leaves':len(ids),'loaded_entries':sum(len(m['entries']) for m in output['matches']),
         'output_chars':len(process.stdout),'context_chars':output['trace']['context_chars'],
         'cli_elapsed_ms':round(elapsed,3),'routing_ms':output['trace']['routing_ms'],
         'runtime_routes_scored':output['trace']['runtime_routes_scored'],'status':output['status'],
         'clarification_count':len(output['clarifications'])+len(output['deferred_clarifications']),
         'coverage':output['coverage']['status'],'scenario_ids':[s['scenario_id'] for s in output['delivery']['scenario_plans']],
         'dependencies':[d['path'] for d in output['dependencies']],
         'constraints_preserved':all(s in json.dumps(output['matches'],ensure_ascii=False) for s in case['required_constraints']),
         'missing_required':sorted(set(case['required'])-set(ids)),
         'forbidden_loaded':sorted(set(case['forbidden'])&set(ids))}
    if case['id'] in KEY_CASES:row['output']=output
    return row


def summarize(rows,cases):
    by_id={c['id']:c for c in cases}
    required=sum(len(c['required']) for c in cases)
    recalled=sum(len(set(by_id[r['case_id']]['required'])&set(r['leaf_ids'])) for r in rows)
    positive=[r for r in rows if by_id[r['case_id']]['required']]
    return {'cases':len(rows),'required_candidates_recalled':recalled,'required_candidates_total':required,
            'positive_cases_fully_recalled':sum(not r['missing_required'] for r in positive),'positive_cases_total':len(positive),
            'cases_with_prohibited_recall':sum(bool(r['forbidden_loaded']) for r in rows),
            'clarification_cases_handled':sum(bool(r.get('clarification_count')) for r in rows if by_id[r['case_id']]['clarify']),
            'clarification_cases_total':sum(c['clarify'] for c in cases),
            'coverage_cases_handled':sum(r.get('coverage') in ('partial','insufficient') for r in rows if by_id[r['case_id']]['coverage_insufficient']),
            'coverage_cases_total':sum(c['coverage_insufficient'] for c in cases),
            'mean_leaves':round(statistics.mean(r['loaded_leaves'] for r in rows),3),
            'mean_entries':round(statistics.mean(r['loaded_entries'] for r in rows),3),
            'mean_output_chars':round(statistics.mean(r['output_chars'] for r in rows),1),
            'median_cli_ms':round(statistics.median(r['cli_elapsed_ms'] for r in rows),3)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='docs/evaluation/after.json')
    args=parser.parse_args()
    cases=json.loads((ROOT/'tests/fixtures/user-outcomes.json').read_text())['cases']
    rows=[measure(case,[]) for case in cases]
    generic=[measure(case,['--no-fast-path']) for case in cases]
    # Additional blind rephrasings; not added to authored retrieval mappings.
    holdouts=['系统别动不动就宕机。','一大批用户一起进来时，还能快点响应吗？','点了两次保存也只执行一次。',
              '让网页的层次清楚些。','删掉之后能恢复吗，能不能用键盘完成？','网站像赶集，眼睛没地方落。']
    heldout=[measure({'id':'heldout-'+str(i+1),'query':q,'options':[],'required':[],'forbidden':[],'required_constraints':[]},[]) for i,q in enumerate(holdouts)]
    result={'implementation_base':'4b18825','boundary':'Raw CLI only; host JSON tests simulate an interface, not a live LLM. One fresh process/input/mode; timings are observational, not a controlled speed claim.',
            'summary':summarize(rows,cases),'generic_summary':summarize(generic,cases),
            'results':rows,'generic_results':generic,'blind_rephrasings':heldout}
    (ROOT/args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['summary'],ensure_ascii=False,indent=2))
    print('blind:',[(r['query'],r['leaf_ids'],r['status']) for r in heldout])


if __name__=='__main__':main()
