"""Small, atomic dependency composer; no implicit loading of loose `related`."""
from __future__ import annotations
import copy
import json
from retrieval import provider_allowed, literal_evidence
from routing_policy import CONTRACT_SECTIONS


def content_size(matches, dependencies):
    if not matches and not dependencies:
        return 0
    return len(json.dumps({'matches':matches,'dependencies':dependencies},ensure_ascii=False,separators=(',',':')))


class CompositionError(ValueError):
    pass


class Composer:
    def __init__(self, load, records, routes, query, context, limits):
        self.load, self.query, self.context, self.limits = load, query, context, limits
        self.records = {(r['leaf_id'],r['entry_id']):r for r in records}
        self.routes = {r['leaf_id']:r for r in routes}
        self.items, self.contracts, self.deferred = {}, {}, []
        self.scores = {}

    def add_reference(self, reference, source, items, contracts, visiting):
        leaf_id = reference['leaf_id']
        if leaf_id not in self.routes:
            raise CompositionError('unknown_required_leaf:' + leaf_id)
        leaf = self.load(self.routes[leaf_id]['path'])
        wanted = reference.get('entry_ids') or [entry['id'] for entry in leaf['entries']]
        for entry_id in wanted:
            self.expand((leaf_id,entry_id),source,'required_dependency',items,contracts,visiting)

    def expand(self, key, source, role, items, contracts, visiting):
        if key in visiting:
            raise CompositionError('dependency_cycle:' + ':'.join(key))
        if key not in self.records:
            raise CompositionError('unknown_required_entry:' + ':'.join(key))
        record = self.records[key]
        if not provider_allowed(record,self.query,self.context):
            raise CompositionError('provider_scope_blocked:' + key[0])
        if key in items:
            if source not in items[key]['sources']:
                items[key]['sources'].append(source)
            if role != 'required_dependency':
                items[key]['role'] = role
            return
        leaf = self.load(record['path'])
        entry = next(item for item in leaf['entries'] if item['id'] == key[1])
        missing = [field for field in record['required_fields'] if not entry.get(field)]
        if missing:
            raise CompositionError('missing_mandatory_constraints:' + ','.join(missing))
        items[key] = {'entry':entry,'role':role,'sources':[source]}
        visiting = visiting | {key}
        source_ref = record['path'] + '#' + key[1]
        contract = entry.get('contract_ref')
        if contract:
            doc = self.load(contract)
            if contract not in contracts:
                content = {field:doc[field] for field in CONTRACT_SECTIONS if field in doc}
                contracts[contract] = {'path':contract,'required':True,'source_refs':[],
                                       'content':content or doc}
            if source_ref not in contracts[contract]['source_refs']:
                contracts[contract]['source_refs'].append(source_ref)
        for reference in entry.get('composition',{}).get('required',[]):
            self.add_reference(reference,source_ref,items,contracts,visiting)
        for rule in entry.get('composition',{}).get('conditional',[]):
            expressions = [word for word in rule['when_any'] if literal_evidence(self.query,word,'composition.conditional')]
            if expressions:
                self.add_reference(rule['ref'],source_ref,items,contracts,visiting)

    def export(self, items=None, contracts=None):
        items = self.items if items is None else items
        contracts = self.contracts if contracts is None else contracts
        grouped = {}
        for (leaf_id,entry_id),item in items.items():
            route = self.routes[leaf_id]
            if leaf_id not in grouped:
                leaf = self.load(route['path'])
                grouped[leaf_id] = {key:route[key] for key in ('leaf_id','knowledge_type','scope','do_not_generalize','path')}
                grouped[leaf_id].update(score=self.scores.get(leaf_id,0),entries=[],entry_sources=[],provider=route.get('provider'))
                if route['scope'] == 'provider-specific':
                    grouped[leaf_id]['verification'] = {
                        'verified_at':leaf.get('verified_at'),
                        'status':'requires_verification' if not leaf.get('verified_at') else 'source_recorded',
                        'do_not_generalize':True,
                    }
            grouped[leaf_id]['entries'].append({key:value for key,value in item['entry'].items() if key != 'retrieval'})
            grouped[leaf_id]['entry_sources'].append({'entry_id':entry_id,'role':item['role'],'source_refs':item['sources']})
        return list(grouped.values()), list(contracts.values())

    def over_budget(self, items, contracts):
        matches,deps = self.export(items,contracts)
        if len(matches) > self.limits['max_leaf_packages']:
            return 'max_leaf_packages'
        if any(len(match['entries']) > self.limits['max_entries_per_leaf'] for match in matches):
            return 'max_entries_per_leaf'
        subdomains = {(self.routes[item['leaf_id']]['domain_id'],self.routes[item['leaf_id']]['subdomain_id']) for item in matches}
        if len(subdomains) > self.limits['max_subdomains']:
            return 'max_subdomains'
        intent_groups = {}
        for match in matches:
            route = self.routes[match['leaf_id']]
            key = (route['domain_id'],route['subdomain_id'])
            intent_groups.setdefault(key,set()).update(route['intent_ids'])
        if any(len(ids)>self.limits['max_intents'] for ids in intent_groups.values()):
            return 'max_intents'
        if content_size(matches,deps) > self.limits['max_content_chars']:
            return 'max_content_chars'
        return None

    def add(self, key, role, reason):
        items,contracts = copy.deepcopy(self.items),copy.deepcopy(self.contracts)
        try:
            self.expand(key,'user_query',role,items,contracts,set())
            exceeded = self.over_budget(items,contracts)
        except CompositionError as error:
            exceeded = str(error)
        if exceeded:
            self.deferred.append({'leaf_id':key[0],'entry_id':key[1], 'reason':exceeded,
                                  'required_bundle':[{'leaf_id':k[0],'entry_id':k[1]} for k in items if k not in self.items],
                                  'required_contracts':list(contracts),
                                  'next_step':'缩小范围或分阶段完整加载；不得只取外观而省略约束。'})
            return False
        self.items,self.contracts = items,contracts
        return True
