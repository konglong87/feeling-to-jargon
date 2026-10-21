#!/usr/bin/env python3
"""Collect sanitized *recorded* host events, never synthesize live outcomes."""
import argparse
import json
import re
from pathlib import Path
from routing_policy import ROOT

RUNS=('short','confirmed','holdout-host','final-runtime','verified')


def redact(text):
    consumer=str(ROOT/'.feeling-review-artifacts/consumer')
    return (text.replace(consumer+'/.agents/skills/feeling-to-jargon','<SKILL_DIR>')
                .replace(consumer,'<CONSUMER>').replace(str(ROOT),'<REPO>'))


def payloads(text):
    decoder=json.JSONDecoder();position=0;found=[]
    while position<len(text):
        at=text.find('{',position)
        if at<0:break
        try:
            value,length=decoder.raw_decode(text[at:])
        except ValueError:
            position=at+1
            continue
        position=at+length
        if isinstance(value,dict) and ('matches' in value or value.get('mode')=='catalog'):
            found.append(value)
    return found


def collect(directory,name):
    path=directory/(name+'-events.jsonl')
    if not path.is_file():raise ValueError('Missing real events: '+name)
    result={'id':name,'live_host':True,'completed':False,'commands':[],'query_payloads':[]}
    for line in path.read_text().splitlines():
        event=json.loads(line)
        if event.get('type')=='thread.started':result['thread_id']=event['thread_id']
        if event.get('type')=='turn.completed':
            result['completed']=True
            result['usage_including_global_context']=event.get('usage')
        item=event.get('item',{})
        if event.get('type')!='item.completed' or item.get('type')!='command_execution':continue
        output=item.get('aggregated_output','')
        captured=payloads(output)
        result['commands'].append({'command':redact(item.get('command','')),
                                   'exit_code':item.get('exit_code'),'captured_output_chars':len(output),
                                   'captured_payload_count':len(captured)})
        result['query_payloads'].extend(captured)
    result['final_response']=redact((directory/(name+'-final.txt')).read_text())
    result['captured_tool_output_chars']=sum(c['captured_output_chars'] for c in result['commands'])
    manifest={'verified':'final-manifest.json','final-runtime':'verified-manifest.json'}.get(name)
    result['runtime_sha256']=json.loads((directory/manifest).read_text())['sha256'] if manifest else None
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir',type=Path,required=True)
    args=parser.parse_args()
    report={'kind':'Actual installed Codex host execution, not hand-authored candidate contexts',
            'host':'codex-cli 0.154.0-alpha.6.1, inherited configured model; no model override',
            'environment':'macOS; copied Skills installation via skills@1.7.4; real read-only sandbox',
            'scope':'In-session source snapshots for first four runs; verified run matches the final bundled runtime SHA256.',
            'limits':'Captured batch tool outputs sometimes omit an earlier command payload. Absence is not proof of a successful body load. Captured character counts are observations, not a strict cost ceiling. Full host tokens include global instructions/history and are NOT skill marginal cost.',
            'privacy':'Only installed-skill commands, known query payloads and final answers retained; raw private logs/config/stderr removed after review.',
            'runs':[collect(args.log_dir,name) for name in RUNS]}
    text=redact(json.dumps(report,ensure_ascii=False,indent=2))
    text=re.sub(r'/tmp/xcrun_db-[A-Za-z0-9]+','<OS_CACHE>',text)
    destination=ROOT/'docs/evaluation/feelings/host-evidence.json'
    destination.write_text(text+'\n')
    print([(r['id'],r['completed'],len(r['commands']),r['captured_tool_output_chars']) for r in report['runs']])


if __name__=='__main__':main()
