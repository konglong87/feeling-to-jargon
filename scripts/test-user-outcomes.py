#!/usr/bin/env python3
"""Raw-CLI user-effect tests; host context tests are protocol simulations only."""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from composition import Composer, content_size
from routing_policy import ROOT, RETRIEVAL_INDEX

CASES=json.loads((ROOT/'tests/fixtures/user-outcomes.json').read_text())['cases']
QUERY=ROOT/'scripts/query-index.py'


def run(query,*options,context=None,check=True):
    with tempfile.TemporaryDirectory(prefix='jargon-context-') as directory:
        command=[sys.executable,'-B',str(QUERY),query,*options]
        if context is not None:
            file=Path(directory)/'context.json'
            file.write_text(json.dumps(context,ensure_ascii=False))
            command.extend(['--context',str(file)])
        result=subprocess.run(command,capture_output=True,text=True)
    if not check:return result
    if result.returncode:raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def ids(result):
    return {m['leaf_id'] for m in result['matches']}


class UserEffectTests(unittest.TestCase):
    def test_fixed_cases_and_rephrasings(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                result=run(case['query'],*case['options'])
                self.assertTrue(set(case['required']) <= ids(result))
                self.assertTrue(set(case['forbidden']).isdisjoint(ids(result)))
                if case['clarify']:
                    self.assertTrue(result['clarifications'] or result['deferred_clarifications'])
                if case['coverage_insufficient']:
                    self.assertIn(result['coverage']['status'],('partial','insufficient'))
                if case['scenario']:
                    self.assertIn(case['scenario'],[s['scenario_id'] for s in result['delivery']['scenario_plans']])
                self.assertFalse(result['trace']['indexes_in_llm_context'])
                self.assertEqual(result['trace']['score_kind'],'uncalibrated_heuristic_rank')
                self.assertLessEqual(result['trace']['context_chars'],result['trace']['content_char_limit'])
                for explanation in result['explanations']:
                    for hit in explanation['evidence']:
                        self.assertIn(hit['matched_expression'],case['query'])
                for constraint in case['required_constraints']:
                    self.assertIn(constraint,json.dumps(result['matches'],ensure_ascii=False))

    def test_stability_and_audience_are_not_extra_explicit_requirements(self):
        result=run('我想做一个大型的后端，给很多人用，要稳定。')
        capacity=next(e for e in result['explanations'] if e['leaf_id']=='capacity-model')
        self.assertEqual(capacity['role'],'suggestion')
        self.assertNotIn('idempotency-contract',ids(result))
        self.assertNotIn('scaling-strategies',ids(result))
        result=run('后端要稳定')
        self.assertEqual(ids(result),{'availability-patterns'})
        result=run('很多人同时用也别卡')
        self.assertEqual(result['explanations'][0]['role'],'explicit')

    def test_vague_once_only_wording_is_not_idempotency_evidence(self):
        result=run('婚礼只办一次，不想重复折腾')
        self.assertNotIn('idempotency-contract',ids(result))
        for text in ('有质感一点','太乱了','更专业一些'):
            result=run(text)
            self.assertEqual(result['status'],'needs_clarification')
            self.assertEqual(result['matches'],[])

    def test_source_text_reuse_and_heldout_sentences_not_stored(self):
        result=run('关键组件需要跨实例部署')
        self.assertIn('availability-patterns',ids(result))
        self.assertTrue(any(h['field']=='plain_language' for e in result['explanations'] for h in e['evidence']))
        projection=(ROOT/RETRIEVAL_INDEX).read_text()
        for case in CASES:
            if case['kind']=='paraphrase':self.assertNotIn(case['query'],projection)

    def test_fast_and_generic_paths_keep_same_required_quality(self):
        for case in CASES:
            if not case['scenario']:continue
            with self.subTest(case=case['id']):
                fast=run(case['query'],*case['options'])
                generic=run(case['query'],*case['options'],'--no-fast-path')
                for result in (fast,generic):
                    self.assertTrue(set(case['required']) <= ids(result))
                    self.assertTrue(set(case['forbidden']).isdisjoint(ids(result)))
                    self.assertTrue(result['delivery']['acceptance_checks']['dependencies_complete_for_emitted_bundles'])
                self.assertEqual(fast['trace']['runtime_routes_scored'],0)
                self.assertGreater(generic['trace']['runtime_routes_scored'],0)
                self.assertEqual(fast['delivery']['scenario_plans'],generic['delivery']['scenario_plans'])

    def test_required_conditional_dependencies_and_template_dedup(self):
        result=run('删除后可以反悔')
        self.assertTrue({'undo-window','motion-accessibility','reverse-animation'} <= ids(result))
        self.assertNotIn('flip-reentry',ids(result))
        result=run('删除后可以反悔，恢复时插回原索引')
        self.assertIn('flip-reentry',ids(result))
        result=run('比较工业分区布局与暖色三栏布局')
        self.assertEqual(len(result['dependencies']),1)
        contract=result['dependencies'][0]
        self.assertEqual(len(contract['source_refs']),2)
        self.assertIn('shared_execution_contract',contract['content'])
        self.assertNotIn('style_directions',contract['content'])
        self.assertFalse(result['composition']['conflicts'][0]['requires_choice'])
        result=run('工业分区布局和暖色三栏布局放在同一页')
        self.assertTrue(result['composition']['conflicts'][0]['requires_choice'])
        self.assertFalse(result['delivery']['ready_for_final_prompt'])

    def test_atomic_budgets_never_drop_effect_constraints(self):
        for query,options in [('删除后可以反悔',['--max-leaves','1']),('删除后可以反悔',['--max-entries','1']),('液态玻璃栏',['--max-chars','100']),('液态玻璃栏',['--max-chars','1'])]:
            with self.subTest(query=query,options=options):
                result=run(query,*options)
                self.assertEqual(result['status'],'needs_staging')
                self.assertTrue(result['composition']['deferred'])
                self.assertFalse(result['delivery']['ready_for_final_prompt'])
                if 'undo-window' in ids(result):
                    self.assertTrue({'reverse-animation','motion-accessibility'} <= ids(result))
        result=run('液态玻璃栏')
        self.assertNotIn('gpui-mobile',ids(result))
        body=result['matches'][0]['entries'][0]
        for field in ('performance_budget','fallback','mobile_degradation','reduced_motion','acceptance'):
            self.assertTrue(body[field])
        self.assertEqual(content_size(result['matches'],result['dependencies']),result['trace']['context_chars'])
        for option in ('--max-chars','--max-leaves','--max-entries'):
            self.assertNotEqual(run('撤销',option,'0',check=False).returncode,0)

    def test_existing_answers_and_explicit_window_avoid_repeat_questions(self):
        result=run('删除后 5 秒内可以反悔，键盘也能操作')
        self.assertNotIn('undo_window',[q['id'] for q in result['clarifications']])
        self.assertNotEqual(run('删除后5秒内可以反悔',context={'answers':{'undo_window':'10秒'}},check=False).returncode,0)
        for text in ('页面5秒内加载完成，删除后可以反悔','删除后可以反悔，不要5秒内撤销，窗口还没定'):
            result=run(text)
            self.assertIn('undo_window',[q['id'] for q in result['clarifications']])
        result=run('我想做一个有质感的网站',context={'answers':{'visual_priority':'改善排版层级，不改变现有配色'}})
        self.assertEqual(result['clarifications'],[])
        self.assertEqual(result['delivery']['scenario_plans'][0]['match'],'ready')

    def test_context_protocol_is_validated_not_claimed_as_live_agent(self):
        result=run('网页需要更有呼吸感',context={'candidates':[{'leaf_id':'composition-patterns','entry_id':'composition-patterns','evidence_text':'呼吸感','role':'suggestion'}]})
        self.assertIn('composition-patterns',ids(result))
        self.assertIn('host_interpretation_unverified',json.dumps(result))
        self.assertFalse(result['delivery']['acceptance_checks']['host_llm_workflow_verified'])
        for context in [
            {'candidates':[{'leaf_id':'no-such-id','entry_id':'x','evidence_text':'网页','role':'explicit'}]},
            {'candidates':[{'leaf_id':'composition-patterns','entry_id':'composition-patterns','evidence_text':'并不存在的原话','role':'explicit'}]},
            {'answers':{'unrecognized':'value'}}, {'providers':['unknown']}, {'irrelevant':1},
        ]:
            self.assertNotEqual(run('网页需要更有呼吸感',context=context,check=False).returncode,0)
        result=run('React 动画',context={'providers':['GSAP']})
        self.assertIn('gsap-react-lifecycle',ids(result))
        result=run('不用 GSAP，只用 CSS 做动画',context={'providers':['GSAP']})
        self.assertFalse(any(id.startswith('gsap-') for id in ids(result)))
        result=run('GPUIX 移动端')
        self.assertEqual(result['status'],'needs_verification')
        self.assertFalse(result['delivery']['ready_for_final_prompt'])

    def test_invalid_required_constraint_and_cycle_fail_closed(self):
        index=json.loads((ROOT/RETRIEVAL_INDEX).read_text())
        runtime=json.loads((ROOT/'index/runtime.json').read_text())
        limits=json.loads((ROOT/'index/root.json').read_text())['loading_policy']
        def missing_load(path):
            data=json.loads((ROOT/path).read_text())
            if path=='terms/visual-effects/liquid-glass-bar.json':data['entries'][0].pop('reduced_motion')
            return data
        composer=Composer(missing_load,index['entries'],runtime['routes'],'液态玻璃栏',{'providers':[]},limits)
        self.assertFalse(composer.add(('liquid-glass-bar','liquid-glass-bar'),'explicit','test'))
        self.assertIn('missing_mandatory_constraints',composer.deferred[0]['reason'])
        def cycle_load(path):
            data=json.loads((ROOT/path).read_text())
            if path=='terms/interaction/undo-window.json':
                data['entries'][0]['composition']['required']=[{'leaf_id':'undo-window','entry_ids':['undo-window']}]
            return data
        composer=Composer(cycle_load,index['entries'],runtime['routes'],'撤销',{'providers':[]},limits)
        self.assertFalse(composer.add(('undo-window','undo-window'),'explicit','test'))
        self.assertIn('dependency_cycle',composer.deferred[0]['reason'])
        self.assertFalse(composer.items)


if __name__=='__main__':
    unittest.main()
