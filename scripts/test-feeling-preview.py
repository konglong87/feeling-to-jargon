#!/usr/bin/env python3
"""Feeling-first outcomes: terms before questions, no extra body fan-out."""
import json
import subprocess
import sys
import unittest
from routing_policy import ROOT, MAX_FEELING_DIRECTIONS, MAX_TERMS_PER_DIRECTION
from retrieval_index import project_retrieval


def run(query, *options, context=None, installed=False):
    entry = ROOT/('skills/feeling-to-jargon/scripts/query.py' if installed else 'scripts/query-index.py')
    cmd = [sys.executable,'-B',str(entry),query,*options]
    if context:
        cmd += ['--context','-']
    proc = subprocess.run(cmd,input=json.dumps(context,ensure_ascii=False) if context else None,
                          text=True,capture_output=True,check=True)
    return json.loads(proc.stdout)


class FeelingPreviewTests(unittest.TestCase):
    def test_frozen_short_inputs(self):
        cases = json.loads((ROOT/'tests/fixtures/short-feelings.json').read_text())
        for case in cases:
            with self.subTest(query=case['query']):
                result = run(case['query'])
                directions = {item['leaf_id'] for item in result['candidate_terms']}
                self.assertTrue(set(case['expected_directions']) <= directions)
                self.assertTrue(set(case['forbidden_directions']).isdisjoint(directions))
                self.assertEqual(result['status'],case['expected_status'])
                for item in result['candidate_terms']:
                    self.assertTrue(item['terms'])
                    self.assertLessEqual(len(item['terms']),MAX_TERMS_PER_DIRECTION)
                    self.assertIn('#'+item['entry_id'],item['source'])
                    self.assertTrue(all(text in case['query'] for text in item['user_expressions']))

    def test_short_feelings_offer_multiple_terms_without_loading_bodies(self):
        for query in ('太挤了','有质感一点','稳一点','顺滑一点'):
            result = run(query)
            self.assertGreaterEqual(len({term for c in result['candidate_terms'] for term in c['terms']}),2)
            self.assertFalse(result['matches'])
            self.assertFalse(result['delivery']['acceptance_checks']['detected_requests_assembled'])
            self.assertEqual(result['trace']['context_chars'],0)
            self.assertEqual(len(result['clarifications']),1)
            self.assertTrue(all(c['role']=='suggestion' and not c['knowledge_loaded'] for c in result['candidate_terms']))

    def test_candidate_preview_does_not_hide_an_uncovered_second_request(self):
        result=run('高级一点，帮我修一台核磁共振仪')
        self.assertEqual(result['status'],'partial_coverage')
        self.assertIn('帮我修一台核磁共振仪',result['coverage']['unaccounted_clauses'])
        self.assertTrue(any(q['id']=='uncovered-scope' for q in result['clarifications']))
        self.assertFalse(result['delivery']['ready_for_final_prompt'])

    def test_scope_confirmation_roundtrip_uses_same_composer(self):
        for query,scope,expected in [('太挤了','页面',{'composition-patterns','information-hierarchy'}),
                                     ('稳一点','后端',{'availability-patterns'}),
                                     ('像弹簧一样','按钮',{'spring-press'})]:
            result = run(query,context={'answers':{'feeling_scope':scope}})
            self.assertEqual({m['leaf_id'] for m in result['matches']},expected)
            self.assertTrue(all(c['scope_confirmed'] and c['knowledge_loaded'] for c in result['candidate_terms']))
        # A choice of object must not establish another sense.
        result=run('稳一点',context={'answers':{'feeling_scope':'页面'}})
        self.assertFalse(result['candidate_terms'])
        self.assertFalse(result['matches'])

    def test_cross_topics_negation_and_nonmatching_named_objects(self):
        for query in ('办公室太挤了','办公室想要再透气一些','椅子能不能再稳一点','椅子稳一点','论文的页面看着乱，需要理清论证而非网站设计',
                      '不要有呼吸感','不需要高级','后端要稳定，餐厅太挤了','页面有质感，椅子稳一点'):
            result=run(query)
            directions={item['leaf_id'] for item in result['candidate_terms']}
            if query.startswith('后端'):
                self.assertEqual(directions,{'availability-patterns'})
            elif query.startswith('页面有质感'):
                self.assertEqual(directions,{'token-system'})
            else:
                self.assertFalse(directions)
        unsupported=run('后台别在大家一起来的时候趴窝')
        self.assertFalse(unsupported['matches'])
        self.assertIn('后台',unsupported['trace']['ambiguous_generic_scopes_ignored'])
        result=run('网站要质感但不要玻璃渐变')
        self.assertNotIn('liquid-glass',{item['leaf_id'] for item in result['candidate_terms']})

    def test_preview_and_body_budgets_are_independent_and_explain_clipping(self):
        result=run('太挤了，高级一点，稳一点，像弹簧一样，顺滑一点')
        self.assertEqual(len(result['candidate_terms']),MAX_FEELING_DIRECTIONS)
        self.assertGreater(result['terminology_preview']['omitted_directions'],0)
        self.assertFalse(result['matches'])
        staged=run('页面太挤了','--max-chars','1')
        self.assertEqual(staged['status'],'needs_staging')
        self.assertTrue(staged['composition']['deferred'])
        self.assertTrue(staged['candidate_terms'])
        self.assertFalse(staged['delivery']['ready_for_final_prompt'])
        required=run('删除后可以反悔，而且键盘也能操作')
        self.assertTrue({'undo-window','motion-accessibility','reverse-animation'} <= {m['leaf_id'] for m in required['matches']})

    def test_formats_distribution_and_cost_agree(self):
        for query in ('太挤了','页面没重点','稳一点','做工业分区布局，选中物料后联动补货卡'):
            full=run(query);agent=run(query,'--format','agent');installed=run(query,'--format','agent',installed=True)
            self.assertEqual(agent,installed)
            for key in ('candidate_terms','matches','dependencies','status'):
                self.assertEqual(full[key],agent[key])
            cost=agent.pop('output_cost')
            self.assertEqual(cost['compact_payload_chars_without_cost'],len(json.dumps(agent,ensure_ascii=False,separators=(',',':'))))
            self.assertEqual(cost['candidate_terms_chars'],len(json.dumps(agent['candidate_terms'],ensure_ascii=False,separators=(',',':'))))

    def test_feeling_rules_reuse_the_original_rule_and_source_terms(self):
        for path in ('terms/design-tokens/token-system.json','terms/visual-layout/composition-patterns.json',
                     'terms/software-engineering/availability-patterns.json'):
            entry=json.loads((ROOT/path).read_text())['entries'][0]
            feeling=entry['retrieval']['feelings'][0]
            self.assertIn('rule_ref',feeling)
            self.assertNotIn('all',feeling)
            projection=project_retrieval(entry)
            source=next(r for r in entry['retrieval']['rules'] if r['id']==feeling['rule_ref'])
            self.assertEqual(projection['feelings'][0]['all'],[g for i,g in enumerate(source['all']) if i != source['subject_group']])


if __name__=='__main__':
    unittest.main()
