#!/usr/bin/env python3
"""Check actual recorded host tool outcomes, never fabricate model execution."""
import json
from routing_policy import ROOT


def main():
    evidence=json.loads((ROOT/'docs/evaluation/review/host-evidence.json').read_text())
    runs={run['id']:run for run in evidence['runs']}
    def completed(name):
        run=runs[name]
        assert run['live_host'] and run['completed'] and run['final_response'],name
        assert all(command['exit_code']==0 for command in run['commands']),name
        return run
    first=completed('installed-turn1')
    assert any(not output['matches'] for output in first['query_payloads'])
    assert any('information-hierarchy' in {m['leaf_id'] for m in output['matches']} for output in first['query_payloads'])
    followup=completed('installed-turn2')
    ready=followup['query_payloads'][-1]
    assert ready['status']=='ready' and not ready['clarifications']
    assert '订单状态' in followup['final_response'] and '配色' in followup['final_response']
    retest=completed('installed-retest')
    for leaf in ('press-and-hold-confirm','snap-card-timeline'):
        assert any(output['status']=='ready' and leaf in {m['leaf_id'] for m in output['matches']} for output in retest['query_payloads'])
    month=completed('installed-month')
    month_output=month['query_payloads'][-1]
    assert any(entry['id']=='glass-dot-matrix-dashboard' for match in month_output['matches'] for entry in match['entries'])
    assert month_output['explanations'][0]['role']=='suggestion'
    assert len([command for command in month['commands'] if command.get('mode')=='catalog'])<=2
    batch=completed('batch-before-fix')
    budget=[output for output in batch['query_payloads'] if output.get('status')=='needs_staging']
    assert budget and all(not output['matches'] and output['composition']['deferred'] for output in budget)
    platform=[output for output in batch['query_payloads'] if '不依赖 GSAP' in output['query']]
    assert platform
    assert all(not any((match.get('provider') or '').lower() in ('gsap','gpuix') for match in output['matches']) for output in platform)
    assert '并非完全合规' in retest['final_response'] or '超预算' in retest['final_response']
    print('live-host evidence checked: installed read-only use, semantic fallback, multi-turn answers, hold/timeline, monthly reuse, scope exclusions, atomic budget. Budget-overrun observation retained.')


if __name__=='__main__':main()
