"""Presentation only: compact host handoff never drops source knowledge."""
from copy import deepcopy
import re
from lexical import normalize
from routing_policy import (CATALOG_LIMIT, CATALOG_MAX_LIMIT, CATALOG_SUMMARY_CHARS,
                            CATALOG_PREFIX_CHARS, CATALOG_IDENTITY_BONUS, CATALOG_BODY_WEIGHT)


def agent_output(result):
    output={key:deepcopy(result[key]) for key in (
        'query','status','matches','dependencies','clarifications','deferred_clarifications',
        'coverage','composition','verification_required','network_search')}
    explanations=[]
    for item in result['explanations']:
        evidence=[]
        seen=set()
        for hit in item['evidence']:
            key=(hit['matched_expression'],hit['origin'])
            if key not in seen:
                seen.add(key)
                evidence.append(hit)
        explanations.append({key:item[key] for key in ('leaf_id','entry_id','role','source')} | {'evidence':evidence})
    output['explanations']=explanations
    plans=[]
    for plan in result['delivery']['scenario_plans']:
        plans.append({key:plan[key] for key in (
            'scenario_id','match','provided_information','not_applicable','flow','output_fields','acceptance')})
    output['delivery']={'scenario_plans':plans,
                        'ready_for_final_prompt':result['delivery']['ready_for_final_prompt'],
                        'acceptance_checks':result['delivery']['acceptance_checks']}
    output['usage']={key:result['trace'][key] for key in (
        'loaded_leaf_count','loaded_entry_count','context_chars','content_char_limit')}
    output['format']='agent'
    return output


def catalog(index,query,limit=CATALOG_LIMIT,domain=None):
    terms=normalize(query).split()
    matches=[]
    for record in index['entries']:
        if domain and record['domain_id'] != domain:
            continue
        fields=record['fields']
        searchable=normalize(' '.join([record['leaf_id'],record['entry_id'],fields['name'],
                                      fields['plain_language'],*fields['aliases']]))
        probes=[term if term in searchable else term[:CATALOG_PREFIX_CHARS] for term in terms
                if term in searchable or (len(term)>CATALOG_PREFIX_CHARS and re.fullmatch(r'[\u4e00-\u9fff]+',term) and term[:CATALOG_PREFIX_CHARS] in searchable)]
        if terms and not probes:
            continue
        identity=normalize(' '.join([record['leaf_id'],record['entry_id'],fields['name'],*fields['aliases']]))
        rank=sum(CATALOG_IDENTITY_BONUS+len(term) if term in identity else CATALOG_BODY_WEIGHT for term in probes)
        matches.append({'_rank':rank,'leaf_id':record['leaf_id'],'entry_id':record['entry_id'],
                        'name':fields['name'],'summary':fields['plain_language'][:CATALOG_SUMMARY_CHARS],
                        'reusable_fields':record.get('reusable_fields',[]),'domain_id':record['domain_id'],'subdomain_id':record['subdomain_id'],'source':record['path']+'#'+record['entry_id'],
                        'provider':record.get('provider'),'scope':record['scope']})
    matches.sort(key=lambda item:(-item['_rank'],item['leaf_id'],item['entry_id']))
    for item in matches:
        item.pop('_rank')
    count=min(limit,CATALOG_MAX_LIMIT)
    return {'mode':'catalog','query':query,'candidates':matches[:count],
            'total_matches':len(matches),'omitted':max(0,len(matches)-count),
            'semantics':'Lexical ID discovery only; not evidence that these candidates fit the original request.'}
