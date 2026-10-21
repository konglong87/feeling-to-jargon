"""Build actionable, bounded handoffs from recipes and composed source entries."""
from __future__ import annotations
import re
from retrieval import clauses, normalize
from routing_policy import (MAX_QUESTIONS, AMBIGUOUS_TERMS, COMPARISON_TERMS, BASE_OUTPUT_FIELDS,
                            STATUS_READY, STATUS_CLARIFY, STATUS_UNCOVERED, STATUS_PARTIAL, STATUS_STAGING, STATUS_VERIFY)


def delivery(query, candidates, matches, dependencies, recipes, records, context, deferred):
    record_by_id = {(r['leaf_id'],r['entry_id']):r for r in records}
    entry_pairs = [(match['leaf_id'],entry) for match in matches for entry in match['entries']]
    output_keys = {(leaf,entry['id']) for leaf,entry in entry_pairs}
    explanations = []
    for key,candidate in candidates.items():
        if key not in output_keys:
            continue
        explanations.append({'leaf_id':key[0],'entry_id':key[1], 'role':candidate['role'],
                             'term':candidate['record']['fields']['name'],
                             'reason':candidate['reason'], 'evidence':candidate['evidence'],
                             'source':candidate['record']['path'] + '#' + key[1]})
    questions = {}
    for leaf,entry in entry_pairs:
        record = record_by_id[(leaf,entry['id'])]
        for question in record['retrieval'].get('questions',[]):
            if question['id'] not in context['answers']:
                questions[question['id']] = question
        if entry.get('evidence',{}).get('status') == 'needs_confirmation':
            qid='source:' + entry['id']
            if qid not in context['answers']:
                questions[qid] = {'id':qid,'question':'实际实现前确认：' + '；'.join(entry['evidence'].get('missing_inputs',[]))}
    conflicts = []
    groups = {}
    for leaf,entry in entry_pairs:
        group = entry.get('composition',{}).get('exclusive_group')
        if group:
            groups.setdefault(group,[]).append({'leaf_id':leaf,'entry_id':entry['id']})
    for group,members in groups.items():
        if len(members)>1:
            comparison=any(term in query for term in COMPARISON_TERMS)
            conflicts.append({'group':group,'members':members,'resolution':'alternatives_only',
                              'requires_choice':not comparison})
            if not comparison:
                questions['choose:'+group]={'id':'choose:'+group,'question':'这些主布局是备选还是分属不同页面？不能未经确认叠加。'}
    plans=[]
    for scene in recipes:
        selected = [key for key in output_keys if key[0] in scene['primary_leaves']]
        if not selected:
            continue
        slots={q['id'] for key in selected for q in record_by_id[key]['retrieval'].get('questions',[])}
        needed=[q for id,q in questions.items() if id in slots or id.startswith('source:')]
        plans.append({'scenario_id':scene['id'],'name':scene['name'],
                      'match':'partial' if needed else 'ready',
                      'selected_knowledge':[{'leaf_id':key[0],'entry_id':key[1]} for key in sorted(selected)],
                      'not_applicable':scene['not_applicable'], 'required_information':needed,
                      'provided_information':{id:answer for id,answer in context['answers'].items() if id in slots},
                      'flow':scene['flow'],'output_fields':scene['output_fields'],'acceptance':scene['acceptance']})
    # Report unaccounted clauses, not an assertion that all possible semantics were understood.
    evidence=[item['matched_expression'] for exp in explanations for item in exp['evidence']]
    unaccounted=[]
    for clause in clauses(query):
        if any(normalize(text) in normalize(clause) for text in evidence):
            continue
        # Required dependencies can cover keyboard and their other authored expressions.
        searchable=' '.join(str(entry) for _,entry in entry_pairs)
        if any(word in clause and word in searchable for word in ('键盘','鼠标','移动端','降级','清理','React')):
            continue
        if matches:
            # Shared prose supports paraphrased linkage clauses without a second alias list.
            fragments = {clause[i:i+3] for i in range(len(clause)-2)
                         if all('\u4e00' <= ch <= '\u9fff' for ch in clause[i:i+3])}
            if any(fragment in searchable for fragment in fragments):
                continue
            if clause.startswith(('不需要', '不用', '不要')):
                continue  # continuation/exclusion, not a new covered capability claim
        if clause and (not matches or len(clauses(query))>1):
            unaccounted.append(clause)
    if not matches and re.fullmatch(r'(?:想要|想|要|有|更|更有|希望|感觉|看起来|太|不)?(?:' + '|'.join(AMBIGUOUS_TERMS) + r')(?:一点|一些|点|些|了|点儿)?[。.!?]*', query.strip()):
        questions['scope']={'id':'scope','question':'你说的是软件服务的可靠性、界面视觉，还是其他对象？请补充对象与具体不满意之处。'}
        unaccounted=[]
    elif unaccounted and matches:
        questions['uncovered-scope']={'id':'uncovered-scope','question':'这些部分尚未找到可核验覆盖：'+'；'.join(unaccounted)+'。请缩小范围或提供资料。'}
    question_list=list(questions.values())
    verification = [match['leaf_id'] for match in matches if match.get('verification',{}).get('status') == 'requires_verification']
    if deferred:
        status=STATUS_STAGING
    elif unaccounted and matches:
        status=STATUS_PARTIAL
    elif not matches and not question_list:
        status=STATUS_UNCOVERED
    elif verification:
        status=STATUS_VERIFY
    elif question_list:
        status=STATUS_CLARIFY
    else:
        status=STATUS_READY
    acceptance_sources = [{'source':record_by_id[(leaf,entry['id'])]['path'] + '#' + entry['id'],
                           'fields':[field for field in ('constraints','acceptance','state') if field in entry]}
                          for leaf,entry in entry_pairs]
    checks={
        'dependencies_complete_for_emitted_bundles':True,
        'detected_requests_assembled':not deferred and not unaccounted,
        'whole_request_semantics_verified':False,
        'parameters_resolved':not question_list,
        'conflicting_layouts_not_blended':True,
        'host_llm_workflow_verified':False,
        'provider_facts_verified':not verification,
    }
    return {'status':status,'explanations':explanations,'clarifications':question_list[:MAX_QUESTIONS],
            'deferred_clarifications':question_list[MAX_QUESTIONS:],
            'coverage':{'status':'partial' if unaccounted and matches else ('insufficient' if not matches and not question_list else 'bounded'),
                        'unaccounted_clauses':unaccounted,
                        'limitation':'有限词法/组合规则覆盖，不是完整语义理解；有结果不代表整句全部覆盖。'},
            'delivery':{'user_need':query,'explicit_needs':[{'leaf_id':e['leaf_id'],'entry_id':e['entry_id'],'explanation_index':i} for i,e in enumerate(explanations) if e['role']=='explicit'],
                        'suggested_directions':[{'leaf_id':e['leaf_id'],'entry_id':e['entry_id'],'explanation_index':i} for i,e in enumerate(explanations) if e['role']=='suggestion'],
                        'scenario_plans':plans,'output_fields':list(BASE_OUTPUT_FIELDS),
                        'prompt_outline':['保留原始需求及证据','区分已确认要求与候选术语','仅使用已加载正文及共享协议',
                                          '回答必要问题后再确定参数/风格','按所选场景验收；未知与分阶段内容明确留出'],
                        'ready_for_final_prompt':status==STATUS_READY,
                        'acceptance_checks':checks,'acceptance_sources':acceptance_sources},
            'verification_required':verification,
            'composition':{'conflicts':conflicts,'deferred':deferred,'deduplication':'stable leaf+entry IDs; shared contracts by path',
                           'related_policy':'informational_only; never loaded wholesale'}}
