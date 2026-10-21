#!/usr/bin/env python3
"""Same frozen short-feeling inputs; report terms, boundaries and actual payload cost."""
import argparse
import json
import statistics
import subprocess
import sys
from routing_policy import ROOT


def measure(case):
    cmd=[sys.executable,'-B',str(ROOT/'scripts/query-index.py'),case['query']]
    full=subprocess.check_output(cmd,text=True)
    compact=subprocess.check_output([*cmd,'--format','agent'],text=True)
    result=json.loads(full);agent=json.loads(compact)
    assert result['matches']==agent['matches'] and result['dependencies']==agent['dependencies']
    assert result['candidate_terms']==agent['candidate_terms']
    return {**case,'result':result,'agent_chars':len(compact.rstrip('\n')),'full_chars':len(full.rstrip('\n')),
            'candidate_chars':agent['output_cost']['candidate_terms_chars'],
            'explanation_chars':agent['output_cost']['explanations_chars']}


def assess(row):
    result=row['result']
    # Old CLI had no user-facing term surface; report body recall separately.
    terms=result.get('candidate_terms',[])
    directions={c['leaf_id'] for c in terms}
    loaded={m['leaf_id'] for m in result['matches']}
    expected=set(row['expected_directions'])
    return {'id':row['id'],'query':row['query'],
            'expected':sorted(expected),'directions':sorted(directions),'loaded':sorted(loaded),
            'missing_terminology':sorted(expected-directions),
            'missing_either_terms_or_bodies':sorted(expected-(directions|loaded)),
            'forbidden':sorted((directions|loaded)&set(row['forbidden_directions'])),
            'status':result['status'],'status_matches':result['status']==row['expected_status'],
            'term_count':len({t for c in terms for t in c['terms']}),
            'leaf_count':len(loaded),'entry_count':result['trace']['loaded_entry_count'],
            'body_chars':result['trace']['context_chars'],'agent_chars':row['agent_chars'],
            'candidate_chars':row.get('candidate_chars',0),'explanation_chars':row.get('explanation_chars',0),
            'routing_ms':result['trace']['routing_ms'],
            'dependencies_complete':result['delivery']['acceptance_checks']['dependencies_complete_for_emitted_bundles']}


def summarize(rows):
    positive=[r for r in rows if r['expected']]
    return {'cases':len(rows),'positive_cases':len(positive),
            'positive_with_all_expected_terms':sum(not r['missing_terminology'] for r in positive),
            'positive_with_all_expected_terms_or_bodies':sum(not r['missing_either_terms_or_bodies'] for r in positive),
            'cases_with_forbidden':sum(bool(r['forbidden']) for r in rows),
            'status_matches':sum(r['status_matches'] for r in rows),
            'mean_agent_chars':round(statistics.mean(r['agent_chars'] for r in rows),1),
            'mean_candidate_chars':round(statistics.mean(r['candidate_chars'] for r in rows),1),
            'mean_body_chars':round(statistics.mean(r['body_chars'] for r in rows),1),
            'mean_leaves':round(statistics.mean(r['leaf_count'] for r in rows),2),
            'median_routing_ms':round(statistics.median(r['routing_ms'] for r in rows),3)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extra-fixture',help='evaluate an additional frozen fixture instead of the baseline comparison')
    parser.add_argument('--extra-output',help='repository-relative output for additional observations')
    parser.add_argument('--method',default='Additional engineer-authored probes, not external independent user recruitment.')
    args=parser.parse_args()
    if args.extra_fixture:
        if not args.extra_output:parser.error('--extra-output is required with --extra-fixture')
        rows=[measure(c) for c in json.loads((ROOT/args.extra_fixture).read_text())]
        checks=[assess(row) for row in rows]
        report={'method':args.method,'summary':summarize(checks),'cases':checks,'evidence':rows}
        (ROOT/args.extra_output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report['summary'],ensure_ascii=False,indent=2))
        return
    destination=ROOT/'docs/evaluation/feelings'
    cases=json.loads((ROOT/'tests/fixtures/short-feelings.json').read_text())
    before=json.loads((destination/'before.json').read_text())
    # Expectation metadata was added after raw outputs were frozen; never regenerate the outputs.
    before=[{**row,**case} for row,case in zip(before,cases)]
    assert all(row['query']==row['result']['query'] for row in before)
    after=[measure(case) for case in cases]
    (destination/'after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n')
    first=[assess(row) for row in before];last=[assess(row) for row in after]
    result={'baseline_commit':'67987bb','kind':'CLI source execution; not complete host acceptance',
            'before':summarize(first),'after':summarize(last),'before_cases':first,'after_cases':last}
    (destination/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'before':result['before'],'after':result['after']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
