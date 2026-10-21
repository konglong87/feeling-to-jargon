#!/usr/bin/env python3
"""Offline checks of genuine recorded host evidence; NOT a fresh model run."""
import json
from routing_policy import ROOT

report=json.loads((ROOT/'docs/evaluation/feelings/host-evidence.json').read_text())
runs={r['id']:r for r in report['runs']}
assert all(r['live_host'] and r['completed'] for r in runs.values())
assert all(c['exit_code']==0 for r in runs.values() for c in r['commands'])
manifest=json.loads((ROOT/'skills/feeling-to-jargon/assets/manifest.json').read_text())
assert runs['verified']['runtime_sha256']==manifest['sha256'],'final runtime has changed since live acceptance'
short=next(p for p in runs['verified']['query_payloads'] if p.get('query','').rstrip('。')=='太挤了')
assert not short['matches'] and short['candidate_terms']
assert {'information-hierarchy','composition-patterns'} <= {c['leaf_id'] for c in short['candidate_terms']}
assert not short['delivery']['acceptance_checks']['detected_requests_assembled']
assert '信息层级' in runs['verified']['final_response'] and '留白' in runs['verified']['final_response']
assert runs['short']['thread_id']==runs['confirmed']['thread_id'],'not a genuine resumed conversation'
assert '主任务优先' in runs['confirmed']['final_response']
assert '暗色' in runs['confirmed']['final_response']
stable=next(p for p in runs['final-runtime']['query_payloads'] if p.get('query')=='稳一点')
quality=next(p for p in runs['final-runtime']['query_payloads'] if p.get('query')=='有质感一点')
assert not stable['matches'] and not quality['matches']
assert {c['leaf_id'] for c in stable['candidate_terms']}=={'availability-patterns'}
assert {c['leaf_id'] for c in quality['candidate_terms']}=={'token-system'}
backend=next(p for p in runs['holdout-host']['query_payloads'] if p.get('query','').startswith('后台') and p.get('matches'))
assert {m['leaf_id'] for m in backend['matches']}=={'availability-patterns','capacity-model'}
assert any(hit['origin']=='host_interpretation_unverified' for e in backend['explanations'] for hit in e['evidence'])
assert '没有覆盖' in runs['holdout-host']['final_response']
print('Recorded host evidence verified: final-runtime feeling preview, real scope follow-up, bounded host recovery and honest uncovered scrolling performance. Not a universal Agent/product acceptance.')
