#!/usr/bin/env python3
"""Measure review effects and full-vs-agent payloads without changing fixtures."""
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from routing_policy import ROOT


def measure(case):
    query=case['query'];opts=case.get('options',[])
    start=time.perf_counter()
    full=subprocess.check_output([sys.executable,'-B',str(ROOT/'scripts/query-index.py'),query,*opts],text=True)
    elapsed=(time.perf_counter()-start)*1000
    agent=subprocess.check_output([sys.executable,'-B',str(ROOT/'scripts/query-index.py'),query,*opts,'--format','agent'],text=True)
    result=json.loads(full);small=json.loads(agent)
    if result['matches']!=small['matches'] or result['dependencies']!=small['dependencies']:
        raise ValueError('compact format changed required source knowledge')
    ids=[match['leaf_id'] for match in result['matches']]
    return {'id':case['id'],'query':query,'leaf_ids':ids,
            'entry_ids':[entry['id'] for match in result['matches'] for entry in match['entries']],
            'status':result['status'],'missing':sorted(set(case['required'])-set(ids)),
            'forbidden':sorted(set(case['forbidden'])&set(ids)),
            'status_mismatch':bool(case.get('expected_status') and case['expected_status']!=result['status']),
            'full_output_chars':len(full),'agent_output_chars':len(agent),
            'knowledge_chars':result['trace']['context_chars'],'elapsed_ms':round(elapsed,3),
            'loaded_leaves':len(ids),'loaded_entries':result['trace']['loaded_entry_count'],
            'full_agent_knowledge_identical':True,
            'unaccounted_clauses':result['coverage']['unaccounted_clauses']}


def summary(rows):
    return {'cases':len(rows),'cases_missing_required':sum(bool(row['missing']) for row in rows),
            'cases_with_forbidden':sum(bool(row['forbidden']) for row in rows),
            'status_mismatches':sum(row['status_mismatch'] for row in rows),
            'mean_full_chars':round(statistics.mean(row['full_output_chars'] for row in rows),1),
            'mean_agent_chars':round(statistics.mean(row['agent_output_chars'] for row in rows),1),
            'agent_reduction_fraction':round(1-sum(row['agent_output_chars'] for row in rows)/sum(row['full_output_chars'] for row in rows),4),
            'median_cli_ms':round(statistics.median(row['elapsed_ms'] for row in rows),3)}


def main():
    original=json.loads((ROOT/'tests/fixtures/user-outcomes.json').read_text())['cases']
    blind=json.loads((ROOT/'tests/fixtures/review-blind.json').read_text())['cases']
    old=[measure(case) for case in original]
    new=[measure(case) for case in blind]
    examples=[]
    for query in ('页面看着太乱了，希望舒服一点。','删除后可以反悔，而且键盘也能操作。','做工业分区布局，选中物料后联动补货卡。'):
        body=subprocess.check_output([sys.executable,'-B',str(ROOT/'scripts/query-index.py'),query,'--format','agent'],text=True)
        examples.append({'query':query,'output':json.loads(body)})
    result={'review_base':'c42dd4a','method':'Same raw inputs per format, fresh process per CLI run. Size assertions deterministic; timings observational. No model-token inference from characters.',
            'original_summary':summary(old),'blind_summary':summary(new),'original_cases':old,'blind_cases':new,
            'compact_examples':examples}
    (ROOT/'docs/evaluation/review/after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'original':result['original_summary'],'review_blind':result['blind_summary']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
