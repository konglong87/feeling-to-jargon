"""Generate a disposable retrieval projection from authored entry metadata."""
import re
from copy import deepcopy
from collections import Counter
from routing_policy import COMPOSITION_FIELDS, SCENARIO_SOURCE

def project_retrieval(entry):
    """Existing scoped rules can also supply feeling cues; never copy their lists."""
    retrieval = deepcopy(entry.get('retrieval', {}))
    rules = {rule['id']:rule for rule in retrieval.get('rules',[])}
    for feeling in retrieval.get('feelings',[]):
        if 'rule_ref' not in feeling:
            continue
        rule = rules[feeling['rule_ref']]
        subject = rule['subject_group']
        feeling.update({'all':[group for i,group in enumerate(rule['all']) if i != subject],
                        'scope_any':rule['all'][subject],
                        'exclude_any':rule.get('exclude_any',[]), 'role':'suggestion'})
    return retrieval


def build_index(leaf_defs, root):
    import json
    records = []
    for leaf_id, leaf in sorted(leaf_defs.items()):
        for entry in leaf['entries']:
            records.append({
                'leaf_id': leaf_id, 'entry_id': entry['id'], 'path': leaf['path'],
                'domain_id': leaf['domain_id'], 'subdomain_id': leaf['subdomain_id'],
                'intent_ids': leaf['intent_ids'], 'scope': leaf.get('scope', 'general'),
                'provider': leaf.get('provider') or entry.get('provider'),
                'fields': {key: entry.get(key, [] if key == 'aliases' else '')
                           for key in ('name', 'aliases', 'plain_language', 'when_to_use')},
                'retrieval': project_retrieval(entry),
                'source_question': entry.get('evidence',{}).get('missing_inputs',[]) if entry.get('evidence',{}).get('status') == 'needs_confirmation' else [],
                'reusable_fields': [key for key in ('termSkill','agentExec','state','tokens') if entry.get(key)],
                'contract_ref': entry.get('contract_ref'),
                'composition': entry.get('composition', {}),
                'required_fields': list(COMPOSITION_FIELDS) if leaf['subdomain_id'] == 'visual-effects' else [],
            })
    # Only unique source phrases are strong routing evidence; boilerplate is not.
    phrases = {}
    for record in records:
        key = (record['leaf_id'],record['entry_id'])
        phrases[key] = [(field, phrase.strip()) for field in ('plain_language','when_to_use')
                        for phrase in re.split(r'[，。；、,/;]',record['fields'][field])
                        if len(phrase.strip()) >= 3]
    frequency = Counter(phrase.casefold() for values in phrases.values() for phrase in {p for _,p in values})
    for record in records:
        record['search_phrases'] = [{'field':field,'text':phrase} for field,phrase in phrases[(record['leaf_id'],record['entry_id'])]
                                    if frequency[phrase.casefold()] == 1]
    return {'schema_version':'1.0.0', 'generated_by':'scripts/bootstrap-progressive-content.py',
            'source_of_truth':'Authored leaf entries; generated search projection, not a second knowledge store.',
            'entries':records, 'scenarios':json.loads((root / SCENARIO_SOURCE).read_text())['scenarios']}
