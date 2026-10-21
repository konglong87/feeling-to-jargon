#!/usr/bin/env python3
"""Check generated retrieval freshness, workflow references and dependency closure."""
import json
import re
from pathlib import Path
from retrieval_index import build_index
from routing_policy import ROOT, RETRIEVAL_INDEX


def validate():
    leaves=json.loads((ROOT/'index/leaves.json').read_text())['leaves']
    authored={}
    for ref in leaves:
        doc=json.loads((ROOT/ref['path']).read_text())
        authored[ref['leaf_id']]={**doc,'path':ref['path']}
    expected=build_index(authored,ROOT)
    actual=json.loads((ROOT/RETRIEVAL_INDEX).read_text())
    assert expected==actual,'generated retrieval projection is stale; run bootstrap'
    records={(r['leaf_id'],r['entry_id']):r for r in actual['entries']}
    assert len(records)==len(actual['entries']),'duplicate retrieval identity'
    edges={key:[] for key in records}
    for key,record in records.items():
        if record['scope']=='provider-specific':
            assert record['provider'],'provider-specific content must name its provider'
        for rule in record['retrieval'].get('rules',[]) + record['retrieval'].get('feelings',[]):
            assert rule['role'] in ('explicit','suggestion')
            assert rule['all'] and all(group and all(isinstance(v,str) and v.strip() for v in group) for group in rule['all'])
        question_ids={item['id'] for item in record['retrieval'].get('questions',[])}
        for input_rule in record['retrieval'].get('inputs',[]):
            assert input_rule['id'] in question_ids
            assert 'value' in re.compile(input_rule['pattern']).groupindex
        if record['contract_ref']:
            target=(ROOT/record['contract_ref']).resolve()
            assert target.is_relative_to(ROOT.resolve()) and target.is_file(),'unsafe or missing contract'
            json.loads(target.read_text())
        entry=next(e for e in authored[key[0]]['entries'] if e['id']==key[1])
        for feeling in record['retrieval'].get('feelings',[]):
            assert feeling['role'] == 'suggestion', 'feelings cannot decide user requirements'
            assert feeling.get('scope_any') and all(isinstance(v,str) and v.strip() for v in feeling['scope_any'])
            source = ' '.join([entry['name'],entry['plain_language'],*entry.get('parameters',[])])
            assert feeling.get('terms') and all(isinstance(v,str) and v.strip() and v in source for v in feeling['terms']), 'preview terms must quote canonical knowledge'
        assert all(entry.get(field) for field in record['required_fields']),'mandatory effect constraints missing'
        refs=list(record['composition'].get('required',[]))
        refs.extend(item['ref'] for item in record['composition'].get('conditional',[]))
        for ref in refs:
            assert ref['leaf_id'] in authored,'missing dependency leaf'
            ids=ref.get('entry_ids') or [item['id'] for item in authored[ref['leaf_id']]['entries']]
            for entry_id in ids:
                target=(ref['leaf_id'],entry_id)
                assert target in records,'missing dependency entry'
                edges[key].append(target)
    def visit(key,stack,done):
        assert key not in stack,'dependency cycle'
        if key in done:return
        for target in edges[key]:visit(target,stack|{key},done)
        done.add(key)
    done=set()
    for key in records:visit(key,set(),done)
    scene_ids=set()
    for scene in actual['scenarios']:
        assert scene['id'] not in scene_ids,'duplicate scene'
        scene_ids.add(scene['id'])
        assert set(scene['primary_leaves']) <= set(authored)
        for field in ('trigger','not_applicable','required_information','knowledge','flow','output_fields','acceptance'):
            assert scene[field], 'incomplete workflow: '+scene['id']
    print(f'routing ok: {len(records)} generated entry records, {len(scene_ids)} scenarios, dependency graph checked')


if __name__=='__main__':
    validate()
