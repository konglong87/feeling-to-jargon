"""Small text-scope helpers; lexical evidence is not semantic certainty."""
import re
from functools import lru_cache
import unicodedata
from lexical import normalize
from routing_policy import CLAUSE_SEPARATORS, NEGATION_MARKERS, TEXT_CACHE_SIZE, NEGATION_SCOPE_CHARS


def clauses(query):
    return [part.strip(' ，,。.!?') for part in re.split(CLAUSE_SEPARATORS, query) if part.strip(' ，,。.!?')]


@lru_cache(maxsize=TEXT_CACHE_SIZE)
def occurrence_spans(query, expression):
    normalized, offsets = '', []
    for index, char in enumerate(query):
        piece = unicodedata.normalize('NFKC', char).lower()
        normalized += piece
        offsets.extend([index] * len(piece))
    term = normalize(expression)
    if not term:
        return []
    # Latin identifiers must not match arbitrary longer names (e.g. GSAPper).
    boundary = r'(?<![a-z0-9_])' if re.fullmatch(r'[a-z0-9_-]+', term) else ''
    suffix = r'(?![a-z0-9_])' if boundary else ''
    return [(offsets[m.start()], offsets[m.end()-1]+1) for m in re.finditer(boundary+re.escape(term)+suffix, normalized)]


def negated(query, expression):
    positions = occurrence_spans(query, expression)
    if not positions:
        return False
    marker = '(?:' + '|'.join(re.escape(term) for term in NEGATION_MARKERS) + ')'
    pattern = marker + rf'[^，,。；;！？!?\n]{{0,{NEGATION_SCOPE_CHARS}}}$'
    return all(re.search(pattern, normalize(query[:start])) for start, _ in positions)


@lru_cache(maxsize=TEXT_CACHE_SIZE)
def positive_query(query):
    parts=[]
    marker='(?:'+'|'.join(re.escape(term) for term in NEGATION_MARKERS)+')'
    for part in clauses(query):
        parts.append(re.sub(marker+r'.*$', '', part))
    return '，'.join(parts)


def literal_evidence(query, value, field):
    if not value or negated(query,value):
        return None
    for start,end in occurrence_spans(query,value):
        if not negated(query[:end],value):
            return {'field':field,'matched_expression':query[start:end], 'origin':'local_lexical'}
    return None


def rule_evidence(query, rule):
    """Match local action/attribute groups, with only an explicit inherited topic."""
    if any(value in query for value in rule.get('exclude_any', [])):
        return []
    active=positive_query(query)
    if rule.get('scope_any') and not any(literal_evidence(active,value,'scope') for value in rule['scope_any']):
        return []
    groups=rule['all']
    subjects=rule.get('subject_group')
    inherited=[]
    evidence=[]
    for part in clauses(query):
        if negated(part,part):
            continue
        subject_hits=[]
        if subjects is not None:
            subject_hits=[hit for phrase in groups[subjects]
                          if (hit:=literal_evidence(part,phrase,'retrieval.rules.'+rule['id']))]
            if subject_hits:
                inherited=subject_hits
            elif any(word in part for word in rule.get('topic_breakers', [])):
                inherited=[]
        hits=[]
        for index,group in enumerate(groups):
            group_hits=[hit for phrase in group if (hit:=literal_evidence(part,phrase,'retrieval.rules.'+rule['id']))]
            if not group_hits and index==subjects:
                group_hits=inherited
            if not group_hits:
                break
            hits.extend(group_hits)
        else:
            hits.extend(hit for phrase in rule.get('also_explain',[]) if (hit:=literal_evidence(query,phrase,'retrieval.rules.'+rule['id'])))
            evidence.extend(hits)
    return evidence
