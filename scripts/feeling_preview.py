"""Source-backed terminology suggestions; no semantic model or body fan-out."""
import re
from lexical import normalize
from text_evidence import literal_evidence, rule_evidence, positive_query
from routing_policy import (FEELING_FILLERS, MAX_FEELING_DIRECTIONS,
                            MAX_TERMS_PER_DIRECTION, MAX_TERM_DEFINITION_CHARS,
                            STATUS_UNCOVERED, STATUS_CLARIFY, STATUS_PARTIAL, FEELING_CLAUSE_SEPARATORS)


def cue_only(text, evidence, scopes=()):
    """Do not reinterpret arbitrary named objects as UI/services just for a hit."""
    remainder = normalize(text)
    for value in sorted([hit['matched_expression'] for hit in evidence] + list(scopes), key=len, reverse=True):
        remainder = remainder.replace(normalize(value), '')
    for filler in FEELING_FILLERS:
        remainder = remainder.replace(filler, '')
    return not re.sub(r'[\s，,。.!?！？、]', '', remainder)


def discover_feelings(query, records, context=None):
    found = {}
    scope_answer = (context or {}).get('answers', {}).get('feeling_scope')
    for record in records:
        # A vague feeling cannot establish a vendor/platform requirement.
        if record.get('provider') or record['scope'] == 'provider-specific':
            continue
        for rule in record['retrieval'].get('feelings', []):
            if any(word in query for word in rule.get('exclude_any', [])):
                continue
            if scope_answer and normalize(scope_answer) not in {normalize(word) for word in rule['scope_any']}:
                continue
            for part in re.split(FEELING_CLAUSE_SEPARATORS, query):
                evidence = rule_evidence(part, {k:v for k,v in rule.items() if k != 'scope_any'})
                if not evidence:
                    continue
                scope_hits = [hit for word in rule['scope_any']
                              if (hit := literal_evidence(part, word, 'feeling.scope'))]
                if not scope_hits and not cue_only(part, evidence):
                    continue
                key = (record['leaf_id'], record['entry_id'])
                item = found.setdefault(key, {'record':record, 'evidence':[], 'terms':[],
                                             'scope_confirmed':False, 'applicable_when':rule['scope_any']})
                item['scope_confirmed'] |= bool(scope_hits or scope_answer)
                for hit in evidence + scope_hits:
                    if hit not in item['evidence']:
                        item['evidence'].append(hit)
                for term in rule['terms']:
                    if term not in item['terms']:
                        item['terms'].append(term)
    return found


def terminology(candidates, feelings, matches):
    """Keep preview and loaded knowledge distinct and cap only optional previews."""
    loaded = {(match['leaf_id'],entry['id']) for match in matches for entry in match['entries']}
    keys = [key for key in candidates if key in loaded]
    preview_keys = [key for key in feelings if key not in keys]
    preview_keys.sort(key=lambda key:(not feelings[key]['scope_confirmed'], key))
    kept = preview_keys[:MAX_FEELING_DIRECTIONS]
    output = []
    for key in keys + kept:
        candidate = candidates.get(key)
        feeling = feelings.get(key)
        record = (candidate or feeling)['record']
        evidence = feeling['evidence'] if feeling else candidate['evidence']
        output.append({'leaf_id':key[0], 'entry_id':key[1],
                       'name':record['fields']['name'],
                       'terms':feeling['terms'][:MAX_TERMS_PER_DIRECTION] if feeling else [record['fields']['name']],
                       'definition':record['fields']['plain_language'][:MAX_TERM_DEFINITION_CHARS],
                       'role':candidate['role'] if candidate else 'suggestion',
                       'user_expressions':list(dict.fromkeys(hit['matched_expression'] for hit in evidence)),
                       'applicable_when':feeling['applicable_when'] if feeling else [record['fields']['when_to_use']],
                       'scope_confirmed':feeling['scope_confirmed'] if feeling else None,
                       'knowledge_loaded':key in loaded,
                       'source':record['path']+'#'+key[1]})
    return output, len(preview_keys)-len(kept)


def add_preview_delivery(result, terms, omitted):
    result['candidate_terms'] = terms
    result['terminology_preview'] = {
        'semantics':'术语方向不是用户已选方案；未加载正文的候选只能用于解释/澄清，不能用于直接实现。',
        'omitted_directions':omitted,
    }
    if not terms or result['matches']:
        return
    result['delivery']['acceptance_checks']['detected_requests_assembled'] = False
    # Preserve staging and uncovered clauses: a preview is not full task coverage.
    if result['status'] in (STATUS_UNCOVERED, STATUS_CLARIFY, STATUS_PARTIAL, FEELING_CLAUSE_SEPARATORS):
        hits = [{'matched_expression':text} for term in terms for text in term['user_expressions']]
        uncovered = [part for part in re.split(FEELING_CLAUSE_SEPARATORS,result['query'])
                     if positive_query(part).strip() and not cue_only(part,hits)]
        result['status'] = STATUS_PARTIAL if uncovered else STATUS_CLARIFY
        result['coverage']['status'] = 'partial' if uncovered else 'candidate_directions_only'
        result['coverage']['unaccounted_clauses'] = uncovered
        result['clarifications'] = [{'id':'feeling_scope',
            'question':'以上术语只是候选方向。你指的对象是什么，例如页面、按钮、后端？确认对象后再细化，不必先知道专业术语。'}]
        if uncovered:
            result['clarifications'].append({'id':'uncovered-scope',
                'question':'以下部分仍没有知识覆盖：'+'；'.join(uncovered)+'。请缩小范围或提供资料。'})
        result['delivery']['ready_for_final_prompt'] = False
        result['delivery']['acceptance_checks']['parameters_resolved'] = False
