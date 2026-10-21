#!/usr/bin/env python3
"""Regression evidence for real-host review defects, distribution and cost."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from routing_policy import ROOT
from text_evidence import literal_evidence

CASES=json.loads((ROOT/'tests/fixtures/review-blind.json').read_text())['cases']


def run(query,*options,context=None):
    command=[sys.executable,'-B',str(ROOT/'scripts/query-index.py'),query,*options]
    if context is not None:command.extend(['--context','-'])
    completed=subprocess.run(command,input=json.dumps(context,ensure_ascii=False) if context is not None else None,
                             capture_output=True,text=True)
    if completed.returncode:raise AssertionError(completed.stderr)
    return json.loads(completed.stdout),len(completed.stdout)


class ReviewTests(unittest.TestCase):
    def test_new_blind_inputs_keep_scope_and_negation(self):
        for case in CASES:
            with self.subTest(case=case['id']):
                result,_=run(case['query'])
                leaves={item['leaf_id'] for item in result['matches']}
                self.assertTrue(set(case['required'])<=leaves)
                self.assertTrue(set(case['forbidden']).isdisjoint(leaves))
                if case['expected_status']:
                    self.assertEqual(result['status'],case['expected_status'])

    def test_negated_layout_is_not_returned_as_positive(self):
        result,_=run('不要工业分区布局，想比较暖色三栏布局')
        entries=[entry['id'] for match in result['matches'] for entry in match['entries']]
        self.assertNotIn('industrial-zones-dashboard',entries)
        self.assertIn('warm-three-column-dashboard',entries)

    def test_non_scene_request_is_not_lost_behind_scene_shortcut(self):
        for mode in ([],['--no-fast-path']):
            result,_=run('我想做一个有质感的网站，还要毛绒玩偶',*mode)
            self.assertTrue({'token-system','character-ip'}<={item['leaf_id'] for item in result['matches']})
            self.assertGreater(result['trace']['runtime_routes_scored'],0)

    def test_layout_choice_and_required_answers_can_roundtrip(self):
        query='工业分区布局和暖色三栏布局放在同一页'
        first,_=run(query)
        slots={q['id'] for q in first['clarifications']+first['deferred_clarifications']}
        self.assertIn('choose:dashboard-primary-layout',slots)
        second,_=run(query,context={'answers':{'choose:dashboard-primary-layout':'industrial-zones-dashboard','dashboard_data':'使用现有物料列表与补货集合'}})
        entries=[entry['id'] for match in second['matches'] for entry in match['entries']]
        self.assertEqual(entries,['industrial-zones-dashboard'])
        self.assertFalse(second['clarifications'])
        self.assertTrue(second['delivery']['ready_for_final_prompt'])

    def test_source_questions_do_not_pollute_other_scenarios(self):
        result,_=run('暖色三栏布局和有质感的网站')
        visual=next(scene for scene in result['delivery']['scenario_plans'] if scene['scenario_id']=='visual-brief')
        self.assertFalse(any(q['id'].startswith('source:') for q in visual['required_information']))
        for context in ({'answers':{'source:availability-patterns':'已确认'}},
                        {'answers':{'choose:dashboard-primary-layout':'not-an-entry'}},
                        {'candidates':[{'leaf_id':[],'entry_id':'x','role':'suggestion','evidence_text':'网站'}]}):
            command=[sys.executable,'-B',str(ROOT/'scripts/query-index.py'),'网站','--context','-']
            proc=subprocess.run(command,input=json.dumps(context),text=True,capture_output=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertNotIn('Traceback',proc.stderr)

    def test_host_may_explain_another_clause_of_an_already_found_entry(self):
        result,_=run('网页东西挤，像赶集',context={'candidates':[{'leaf_id':'composition-patterns','entry_id':'composition-patterns','evidence_text':'像赶集','role':'suggestion'}]})
        evidence=[hit for explanation in result['explanations'] for hit in explanation['evidence']]
        self.assertTrue(any(hit['origin']=='host_interpretation_unverified' and hit['matched_expression']=='像赶集' for hit in evidence))
        self.assertFalse(result['coverage']['unaccounted_clauses'])

    def test_host_evidence_may_quote_a_complete_multi_clause_request(self):
        query='按住不放才执行，提前松手就取消'
        result,_=run(query,context={'candidates':[{'leaf_id':'press-and-hold-confirm','entry_id':'press-and-hold-confirm','evidence_text':query,'role':'suggestion'}]})
        self.assertFalse(result['coverage']['unaccounted_clauses'])
        self.assertEqual(result['status'],'ready')
        self.assertFalse(result['delivery']['acceptance_checks']['whole_request_semantics_verified'])

    def test_normalized_evidence_quotes_real_source_and_provider_boundaries(self):
        self.assertEqual(literal_evidence('用ＦＬＩＰ恢复','FLIP','test')['matched_expression'],'ＦＬＩＰ')
        self.assertIsNone(literal_evidence('GSAPper is a different identifier','GSAP','test'))

    def test_agent_format_preserves_entire_knowledge_and_lowers_cost(self):
        original=json.loads((ROOT/'tests/fixtures/user-outcomes.json').read_text())['cases']
        full_total=agent_total=0
        for case in original:
            full,full_chars=run(case['query'],*case['options'])
            agent,agent_chars=run(case['query'],*case['options'],'--format','agent')
            with self.subTest(case=case['id']):
                self.assertEqual(full['matches'],agent['matches'])
                self.assertEqual(full['dependencies'],agent['dependencies'])
                self.assertEqual(full['status'],agent['status'])
                self.assertEqual(full['clarifications'],agent['clarifications'])
                self.assertEqual(full['composition'],agent['composition'])
                self.assertEqual(full['coverage'],agent['coverage'])
                self.assertEqual(full['delivery']['acceptance_checks'],agent['delivery']['acceptance_checks'])
                for before,after in zip(full['delivery']['scenario_plans'],agent['delivery']['scenario_plans']):
                    for field in ('flow','not_applicable','provided_information','output_fields','acceptance'):
                        self.assertEqual(before[field],after[field])
            full_total+=full_chars;agent_total+=agent_chars
        # Deterministic payload size, not an elapsed-time gate.
        self.assertLess(agent_total,full_total*0.75)

    def test_catalog_is_bounded_and_not_presented_as_semantic_evidence(self):
        result,_=run('信息 留白','--catalog','--catalog-limit','2')
        self.assertEqual(len(result['candidates']),2)
        self.assertGreater(result['omitted'],0)
        monthly,_=run('图表 联动 月份 切换 数据 重算 刷新','--catalog','--catalog-domain','digital-product-uiux','--catalog-limit','3')
        self.assertIn('glass-dot-matrix-dashboard',[item['entry_id'] for item in monthly['candidates']])
        natural,_=run('仪表盘 月份筛选 图表 联动 更新','--catalog','--catalog-domain','digital-product-uiux','--catalog-limit','3')
        item=next(item for item in natural['candidates'] if item['entry_id']=='glass-dot-matrix-dashboard')
        self.assertIn('月份切换',item['summary'])
        self.assertIn('state',item['reusable_fields'])
        self.assertIn('not evidence',result['semantics'])
        bounded,_=run('信息 留白','--catalog','--catalog-domain','digital-product-uiux')
        self.assertTrue(all(item['domain_id']=='digital-product-uiux' for item in bounded['candidates']))

    def test_installed_copy_runs_without_repository_or_cwd_assumptions(self):
        with tempfile.TemporaryDirectory(prefix='jargon-install-review-') as folder:
            target=Path(folder)/'consumer/.agents/skills/feeling-to-jargon'
            shutil.copytree(ROOT/'skills/feeling-to-jargon',target)
            launch=[sys.executable,'-B',str(target/'scripts/query.py')]
            proc=subprocess.run([*launch,'网站像赶集，眼睛没地方落','--format','agent','--context','-'],
                input=json.dumps({'candidates':[{'leaf_id':'composition-patterns','entry_id':'composition-patterns',
                    'evidence_text':'网站像赶集','role':'suggestion'}]}),cwd=folder,text=True,capture_output=True,check=True)
            result=json.loads(proc.stdout)
            self.assertIn('composition-patterns',[m['leaf_id'] for m in result['matches']])
            resource=subprocess.run([*launch,'--resource','templates/aigc/base-ip.json','--format','agent'],cwd=folder,text=True,capture_output=True,check=True)
            self.assertIn('content',json.loads(resource.stdout))
            bad=subprocess.run([*launch,'--resource','../../other.json'],cwd=folder,text=True,capture_output=True)
            self.assertNotEqual(bad.returncode,0)
            bundle=target/'assets/runtime.zip'
            bundle.write_bytes(bundle.read_bytes()+b'changed')
            failed=subprocess.run([*launch,'网站'],cwd=folder,text=True,capture_output=True)
            self.assertNotEqual(failed.returncode,0)
            self.assertIn('checksum',failed.stderr)

    def test_generated_distribution_and_projection_are_current(self):
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/build-skill.py'),'--check'],check=True,capture_output=True)
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts/validate-routing.py')],check=True,capture_output=True)


if __name__=='__main__':unittest.main()
