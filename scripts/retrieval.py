"""Explainable, bounded text routing. This is not embedding/LLM semantics."""
from __future__ import annotations
import json
import re
from collections import Counter
from lexical import normalize, score
from routing_policy import (NEGATION_MARKERS, CLAUSE_SEPARATORS, EVIDENCE_SCORE,
                            IDENTITY_BONUS, MAX_HOST_CANDIDATES)


def clauses(query):
    return [part.strip(' ，。.!?') for part in re.split(CLAUSE_SEPARATORS, query) if part.strip()]


def negated(query, expression):
    q, term = normalize(query), normalize(expression)
    occurrences = [match.start() for match in re.finditer(re.escape(term), q)] if term else []
    pattern = '(?:' + '|'.join(re.escape(x) for x in NEGATION_MARKERS) + r')[^，。；！？;.!?]{0,8}$'
    return bool(occurrences) and all(re.search(pattern, q[:position]) for position in occurrences)


def positive_query(query):
    pattern = '(?:' + '|'.join(re.escape(x) for x in NEGATION_MARKERS) + r')[^，。；！？;.!?]*(?:但[^，。；！？;.!?]*)?'
    return re.sub(pattern, '', normalize(query))


def provider_allowed(record, query, context):
    provider = record.get('provider')
    if not provider:
        return record.get('scope') != 'provider-specific'
    if negated(query, provider):
        return False
    return (normalize(provider) in normalize(query)
            or normalize(query).strip(' 。') == normalize(record['leaf_id'])
            or normalize(provider) in [normalize(p) for p in context.get('providers', [])])


def context_from_file(path, records):
    if not path:
        return {'providers': [], 'answers': {}, 'candidates': []}
    with open(path, encoding='utf-8') as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or set(value) - {'providers', 'answers', 'candidates'}:
        raise ValueError('context accepts only providers, answers, candidates')
    value = {'providers': [], 'answers': {}, 'candidates': [], **value}
    if not isinstance(value['providers'], list) or not all(isinstance(x, str) and x.strip() for x in value['providers']):
        raise ValueError('providers must be nonempty strings')
    if not isinstance(value['answers'], dict) or not all(isinstance(x, str) and x.strip() for x in value['answers'].values()):
        raise ValueError('answers must map slot IDs to nonempty text')
    if not isinstance(value['candidates'], list) or len(value['candidates']) > MAX_HOST_CANDIDATES:
        raise ValueError('too many or invalid host candidates')
    known = {(item['leaf_id'], item['entry_id']) for item in records}
    slots = {q['id'] for record in records for q in record['retrieval'].get('questions', [])}
    slots.update('source:' + record['entry_id'] for record in records)
    if set(value['answers']) - slots:
        raise ValueError('unknown answer slot')
    providers = {normalize(record['provider']) for record in records if record.get('provider')}
    if any(normalize(provider) not in providers for provider in value['providers']):
        raise ValueError('unknown project provider')
    for candidate in value['candidates']:
        if not isinstance(candidate, dict) or set(candidate) != {'leaf_id','entry_id','evidence_text','role'}:
            raise ValueError('host candidate requires leaf_id, entry_id, evidence_text, role')
        if (candidate['leaf_id'], candidate['entry_id']) not in known:
            raise ValueError('unknown host knowledge ID')
        if candidate['role'] not in ('explicit','suggestion') or not isinstance(candidate['evidence_text'], str) or not candidate['evidence_text'].strip():
            raise ValueError('host candidate needs a role and nonempty evidence')
    return value


def literal_evidence(query, value, field):
    if value and normalize(value) in normalize(query) and not negated(query, value):
        start = normalize(query).index(normalize(value))
        return {'field':field, 'matched_expression':query[start:start+len(value)], 'origin':'local_lexical'}
    return None


def rule_evidence(query, rule):
    hits = []
    for group in rule['all']:
        group_hits = [hit for phrase in group
                      if (hit := literal_evidence(query, phrase, 'retrieval.rules.' + rule['id']))]
        if not group_hits:
            return []
        hits.extend(group_hits)
    hits.extend(hit for phrase in rule.get('also_explain', [])
                if (hit := literal_evidence(query, phrase, 'retrieval.rules.' + rule['id'])))
    return hits


def discover_candidates(query, records, routes, context):
    route_by_id = {item['leaf_id']:item for item in routes}
    frequencies = Counter(normalize(word) for route in routes for word in set(route['keywords']))
    found = {}
    for record in records:
        if not provider_allowed(record, query, context):
            continue
        fields = record['fields']
        identities = [('name', fields['name']), ('entry_id',record['entry_id'])]
        identities.extend(('aliases', alias) for alias in fields['aliases'])
        identities.extend(('runtime.keywords', word) for word in route_by_id[record['leaf_id']]['keywords']
                          if frequencies[normalize(word)] == 1 and len(normalize(word)) >= 3
                          and (route_by_id[record['leaf_id']]['entry_count'] == 1 or normalize(word) in normalize(' '.join([record['entry_id'], fields['name'], *fields['aliases'], fields['plain_language']]))))
        evidence = [hit for field, word in identities
                    if normalize(word) != normalize(record.get('provider') or '')
                    if (hit := literal_evidence(query, word, field))]
        role = 'explicit' if evidence else 'suggestion'
        for phrase in record.get('search_phrases', []):
            hit = literal_evidence(query,phrase['text'],phrase['field'])
            if hit:
                evidence.append(hit)
        for rule in record['retrieval'].get('rules', []):
            hits = rule_evidence(query, rule)
            if hits:
                evidence.extend(hits)
                if rule['role'] == 'explicit':
                    role = 'explicit'
        if evidence:
            key = (record['leaf_id'],record['entry_id'])
            found[key] = {'record':record, 'role':role, 'evidence':evidence,
                          'score':EVIDENCE_SCORE + score(positive_query(query), [word for _, word in identities]),
                          'match_kind':'source_phrase' if all(hit['field'] in ('plain_language','when_to_use') for hit in evidence) else 'specific',
                          'reason':'Matched authored identity or bounded conjunctive evidence; parameters are not inferred.'}
    specific_leaves = {key[0] for key,item in found.items() if item['match_kind'] == 'specific'}
    found = {key:item for key,item in found.items() if key[0] not in specific_leaves or item['match_kind'] == 'specific'}
    for hint in context['candidates']:
        if normalize(hint['evidence_text']) not in normalize(query):
            raise ValueError('host evidence_text must quote the original query')
        key = (hint['leaf_id'],hint['entry_id'])
        record = next(item for item in records if (item['leaf_id'],item['entry_id']) == key)
        if not provider_allowed(record, query, context):
            raise ValueError('host candidate violates provider scope or explicit exclusion')
        if negated(query, hint['evidence_text']):
            raise ValueError('host candidate evidence is explicitly excluded')
        if key not in found:
            found[key] = {'record':record,'role':hint['role'],'score':EVIDENCE_SCORE,
                          'evidence':[{'field':'host.candidates','matched_expression':hint['evidence_text'],
                                       'origin':'host_interpretation_unverified'}],
                          'reason':'Host-supplied interpretation, structurally validated but not semantically verified by CLI.'}
    return found


def route_query(query, runtime, index, context, limits, fast=True):
    candidates = discover_candidates(query,index['entries'],runtime['routes'],context)
    scene_leaves = {leaf for scene in index['scenarios'] for leaf in scene['primary_leaves']}
    seeded_leaves = {key[0] for key in candidates}
    shortcut = fast and bool(seeded_leaves) and seeded_leaves <= scene_leaves
    if any(route.get('provider') and normalize(route['provider']) in positive_query(query) for route in runtime['routes']):
        shortcut = False
    # A non-scene explicit technical term must still get the generic path.
    active_query = positive_query(query)
    ranked = []
    scanned = 0
    if not shortcut:
        for route in runtime['routes']:
            scanned += 1
            if not provider_allowed(route, query, context):
                continue
            value = score(active_query, route['keywords'])
            if route.get('title') and normalize(route['title']) in active_query:
                value += IDENTITY_BONUS
            if value >= limits['min_route_score']:
                ranked.append((value, route))
        ranked.sort(key=lambda pair:(-pair[0],pair[1]['leaf_id']))
        strongest = {}
        for value, route in ranked:
            key = route['domain_id'], route['subdomain_id']
            strongest[key] = max(strongest.get(key,0),value)
        ranked = [(value,route) for value,route in ranked
                  if value >= strongest[(route['domain_id'],route['subdomain_id'])] - (
                      limits['high_confidence_margin'] if strongest[(route['domain_id'],route['subdomain_id'])] >= limits['high_confidence_score']
                      else limits['route_score_margin'])]
    routes = {r['leaf_id']:r for r in runtime['routes']}
    by_leaf = {route['leaf_id']:(value,route) for value,route in ranked}
    for candidate in candidates.values():
        id = candidate['record']['leaf_id']
        by_leaf[id] = max(by_leaf.get(id,(0,routes[id])),(candidate['score'],routes[id]),key=lambda item:item[0])
    ranked = sorted(by_leaf.values(),key=lambda pair:(-pair[0],pair[1]['leaf_id']))
    return ranked,candidates,{'route_mode':'scenario_fast_path' if shortcut else 'generic',
                              'runtime_routes_scored':scanned, 'retrieval_entries_checked':len(index['entries']),
                              'score_kind':'uncalibrated_heuristic_rank'}
