"""Generate a disposable retrieval projection from authored entry metadata."""
import re
from collections import Counter
from routing_policy import COMPOSITION_FIELDS, SCENARIO_SOURCE

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
                'retrieval': entry.get('retrieval', {}),
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
