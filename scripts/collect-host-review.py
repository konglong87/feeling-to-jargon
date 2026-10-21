#!/usr/bin/env python3
"""Sanitize recorded real-host events; never converts synthetic inputs into live evidence."""
import argparse
import json
import re
from pathlib import Path
from routing_policy import ROOT

RUNS=(
    'repository','installed-extraction-failure','installed-turn1','installed-turn2',
    'batch-before-fix','installed-retest','installed-month',
)


def redact(text):
    consumer=str(ROOT/'.review-artifacts/consumer')
    skill=consumer+'/.agents/skills/feeling-to-jargon'
    text=text.replace(skill,'<SKILL_DIR>').replace(consumer,'<CONSUMER>').replace(str(ROOT),'<REPO>')
    text=re.sub(r'/(?:Users|home)/[^\s\"\']+', '<LOCAL_PATH>', text)
    return text


def json_payload(text):
    decoder=json.JSONDecoder()
    for index,char in enumerate(text):
        if char != '{':continue
        try:
            value,_=decoder.raw_decode(text[index:])
        except ValueError:continue
        if isinstance(value,dict) and ('matches' in value or 'mode' in value):return value
    return None


def collect(directory,name):
    path=directory/(name+'-events.jsonl')
    if not path.exists():return None
    run={'id':name,'live_host':True,'commands':[],'transport_errors':[],
         'completed':False,'tool_output_chars':0,'query_payloads':[]}
    for line in path.read_text().splitlines():
        event=json.loads(line)
        if event.get('type')=='turn.completed':
            run['completed']=True
            run['usage']=event.get('usage')
        if event.get('type')=='error':
            run['transport_errors'].append(redact(event.get('message','')))
        item=event.get('item',{})
        if event.get('type')!='item.completed' or item.get('type')!='command_execution':continue
        text=item.get('aggregated_output','')
        command=item.get('command','')
        run['tool_output_chars']+=len(text)
        payload=json_payload(text)
        row={'command':redact(command),'exit_code':item.get('exit_code'),'output_chars':len(text)}
        if payload:
            row['status']=payload.get('status')
            row['query']=payload.get('query')
            row['mode']=payload.get('mode','query')
            if 'matches' in payload:
                payload=redact(json.dumps(payload,ensure_ascii=False))
                run['query_payloads'].append(json.loads(payload))
        run['commands'].append(row)
    run['command_count']=len(run['commands'])
    final=directory/(name+'-final.txt')
    run['final_response']=redact(final.read_text()) if final.exists() else None
    return run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/evaluation/review/host-evidence.json')
    args=parser.parse_args()
    runs=[run for name in RUNS if (run:=collect(args.log_dir,name))]
    result={'kind':'Recorded real Codex CLI host execution, not prewritten context simulations',
            'host_binary_version':'codex-cli 0.154.0-alpha.6.1','model_selection':'inherited local configured model; no override',
            'installer':'skills@1.7.4, local-source --copy installation for Codex',
            'environment':'macOS, Python 3.9, actual read-only sandbox; no claim for other hosts/platforms',
            'usage_boundary':'Host usage includes user/global skills/configuration, cached input and accumulated context. Not the marginal token cost of this skill.',
            'privacy':'Local absolute paths redacted; auth/config/stderr and raw global instructions not published.',
            'runs':runs}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print([(run['id'],run['completed'],run['command_count'],run['tool_output_chars']) for run in runs])


if __name__=='__main__':main()
