#!/usr/bin/env python3
"""Route feelings to bounded knowledge, assemble dependencies, and plan delivery."""
from __future__ import annotations
import argparse
import json
import re
import time
import zipfile
from pathlib import Path
from lexical import normalize, score, select_entries, positive_int
from routing_policy import ROOT, RETRIEVAL_INDEX, MAX_CONTENT_CHARS
from retrieval import context_from_file, route_query, literal_evidence, positive_query, negated
from composition import Composer, content_size
from scenario_delivery import delivery
from output_formats import agent_output, catalog
from routing_policy import CATALOG_LIMIT


class KnowledgeLoader:
    def __init__(self, root):
        self.root,self.cache,self.read_paths = root,{},[]

    def __call__(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root.resolve()) or path.suffix != '.json':
            raise ValueError('knowledge reference must be a repository JSON path')
        if relative not in self.cache:
            if self.root.is_file():
                with zipfile.ZipFile(self.root) as archive:
                    self.cache[relative] = json.loads(archive.read(relative).decode('utf-8'))
            else:
                self.cache[relative] = json.loads(path.read_text(encoding='utf-8'))
            self.read_paths.append(relative)
        return self.cache[relative]


def generic_candidate(query, route, record, value):
    evidence = []
    for term in route['keywords']:
        hit=literal_evidence(query,term,'runtime.keywords')
        if hit:
            evidence.append(hit)
        elif len(term)>=3:
            # Explain the exact prefix fragment consumed by legacy Chinese scoring.
            for size in range(len(term)-1,2,-1):
                hit=literal_evidence(query,term[:size],'runtime.keywords.prefix')
                if hit:
                    evidence.append(hit)
                    break
    return {'record':record,'score':value,'role':'suggestion', 'evidence':evidence,
            'reason':'Generic lexical fallback; candidate direction, not a committed implementation choice.'}


def resolve_membership(load, matches, routes, limits):
    domains,intents,selected = [],[],[]
    for match in matches:
        route=routes[match['leaf_id']]
        domain_path='index/domains/' + route['domain_id'] + '.json'
        domain=load(domain_path)
        subdomain=next(item for item in domain['subdomains'] if item['subdomain_id']==route['subdomain_id'])
        intent_path=subdomain['intent_index']
        intent_doc=load(intent_path)
        known=[item['id'] for item in intent_doc['intents'] if match['leaf_id'] in item['leaf_refs']]
        if not set(route['intent_ids']) <= set(known):
            raise ValueError('knowledge intent membership is inconsistent')
        if domain_path not in domains: domains.append(domain_path)
        if intent_path not in intents: intents.append(intent_path)
        for id in known[:limits['max_intents']]:
            item={'domain_id':route['domain_id'],'subdomain_id':route['subdomain_id'],'intent_id':id}
            if item not in selected:selected.append(item)
    return domains,intents,selected


def query_knowledge(query, args):
    started=time.perf_counter()
    load=KnowledgeLoader(ROOT)
    root=load('index/root.json')
    runtime=load('index/runtime.json')
    index=load(RETRIEVAL_INDEX)
    context=context_from_file(args.context,index['entries'])
    limits=dict(root['loading_policy'])
    for key,value in [('max_leaf_packages',args.max_leaves),('max_entries_per_leaf',args.max_entries),('max_content_chars',args.max_chars)]:
        if value is not None:limits[key]=min(value,limits.get(key,MAX_CONTENT_CHARS))
    route_started=time.perf_counter()
    ranked,candidates,route_trace=route_query(query,runtime,index,context,limits,not args.no_fast_path)
    routing_ms=(time.perf_counter()-route_started)*1000
    for candidate in candidates.values():
        for rule in candidate['record']['retrieval'].get('inputs', []):
            match = re.search(rule['pattern'],query)
            if match and not negated(query,match.group('value')):
                existing = context['answers'].get(rule['id'])
                if existing and normalize(existing) != normalize(match.group('value')):
                    raise ValueError('context answer conflicts with explicit query value: ' + rule['id'])
                context['answers'][rule['id']] = match.group('value')
    record_by_key={(r['leaf_id'],r['entry_id']):r for r in index['entries']}
    composer=Composer(load,index['entries'],runtime['routes'],query,context,limits)
    composer.scores={route['leaf_id']:value for value,route in ranked}
    for value,route in ranked:
        leaf=load(route['path'])
        selected=[candidate for key,candidate in candidates.items() if key[0]==route['leaf_id']]
        if selected:
            selected.sort(key=lambda candidate:(-candidate['score'],candidate['record']['entry_id']))
        else:
            terms=select_entries(positive_query(query),leaf['entries'],len(leaf['entries']),limits['route_score_margin'],leaf.get('default_entry_id'))
            selected=[generic_candidate(query,route,record_by_key[(route['leaf_id'],term['id'])],value) for term in terms]
        for candidate in selected:
            group=candidate['record']['composition'].get('exclusive_group')
            choice=context['answers'].get('choose:'+group) if group else None
            if choice and choice != candidate['record']['entry_id']:
                continue
            key=(route['leaf_id'],candidate['record']['entry_id'])
            candidates.setdefault(key,candidate)
            composer.add(key,candidate['role'],candidate['reason'])
    matches,dependencies=composer.export()
    routes={route['leaf_id']:route for route in runtime['routes']}
    domain_paths,intent_paths,selected_intents=resolve_membership(load,matches,routes,limits)
    result=delivery(query,candidates,matches,dependencies,index['scenarios'],index['entries'],context,composer.deferred)
    selected_subdomains=[]
    for intent in selected_intents:
        key={field:intent[field] for field in ('domain_id','subdomain_id')}
        if key not in selected_subdomains:selected_subdomains.append(key)
    trace={
        'levels':['root','subdomain','intent','leaf','entry'],
        'execution_order':['read_generated_routing_indexes','match_scene_or_generic_route','assemble_atomic_knowledge_bundles','validate_membership','check_delivery'],
        'root_loaded':'index/root.json','runtime_router_loaded':'index/runtime.json',
        'domain_index_paths':domain_paths,'intent_index_paths':intent_paths,'selected_intents':selected_intents,
        'selected_subdomains':selected_subdomains,'loaded_leaf_paths':[m['path'] for m in matches],
        'loaded_leaf_count':len(matches),'entry_limit':limits['max_entries_per_leaf'],
        'loaded_entry_count':sum(len(m['entries']) for m in matches),
        'internal_read_paths':load.read_paths,'internal_index_chars':sum(len(json.dumps(load.cache[p],ensure_ascii=False)) for p in load.cache if p.startswith('index/')),
        'indexes_in_llm_context':False,'context_chars':content_size(matches,dependencies),'content_char_limit':limits['max_content_chars'],
        'content_budget_scope':'Canonical JSON of matches+dependencies; explanation/delivery envelope reported separately.',
        'routing_ms':round(routing_ms,3),'total_processing_ms':round((time.perf_counter()-started)*1000,3),**route_trace,
    }
    return {'query':query,'strategy':'progressive','trace':trace,'matches':matches,'dependencies':dependencies,
            **result,'network_search':'not_requested'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query',nargs='*',help='raw user request')
    parser.add_argument('--max-leaves',type=positive_int)
    parser.add_argument('--max-entries',type=positive_int)
    parser.add_argument('--max-chars',type=positive_int,help='knowledge body budget, not model tokens; may only lower policy limit')
    parser.add_argument('--no-fast-path',action='store_true',help='audit with generic route scan while retaining composition contracts')
    parser.add_argument('--format', choices=('full','agent'), default='full', help='agent removes diagnostic duplication, not required knowledge')
    parser.add_argument('--resource', help='read one exact terms/ or templates/ JSON reference from installed knowledge')
    parser.add_argument('--catalog', action='store_true', help='bounded lexical discovery of known IDs for host interpretation')
    parser.add_argument('--catalog-domain', help='optional existing domain ID to bound catalog discovery')
    parser.add_argument('--catalog-limit', type=positive_int, default=CATALOG_LIMIT)
    parser.add_argument('--context',help='optional host JSON: providers, answers, evidence-grounded candidates; no model is called')
    args=parser.parse_args()
    try:
        if args.resource:
            if not args.resource.startswith(('terms/','templates/')):
                raise ValueError('resource must name an exact terms/ or templates/ reference')
            output={'source':args.resource,'content':KnowledgeLoader(ROOT)(args.resource)}
        elif args.catalog:
            index=KnowledgeLoader(ROOT)(RETRIEVAL_INDEX)
            if args.catalog_domain and args.catalog_domain not in {record['domain_id'] for record in index['entries']}:
                raise ValueError('unknown catalog domain ID')
            output=catalog(index,' '.join(args.query),args.catalog_limit,args.catalog_domain)
        else:
            if not args.query:
                parser.error('a raw query is required unless using --catalog or --resource')
            output=query_knowledge(' '.join(args.query),args)
            if args.format=='agent':
                output=agent_output(output)
    except (ValueError,KeyError,StopIteration,OSError) as error:
        parser.error(str(error))
    print(json.dumps(output,ensure_ascii=False,**({'separators':(',',':')} if args.format=='agent' or args.catalog else {'indent':2})))


if __name__=='__main__':
    main()
