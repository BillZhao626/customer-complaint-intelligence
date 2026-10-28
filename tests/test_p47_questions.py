"""Source-bound P4.7 evidence QA; original contexts and histories stay frozen."""
import json
from pathlib import Path
import tempfile
import unittest

from src.application.analysis_service import AnalysisService
from src.application.copilot_demo import SCENARIOS as OLD_SCENARIOS, CopilotFake, example as old_example
from src.application.copilot_questions import context_for, offline_answer, VERSION, P47_VERSION, GUIDE
from src.application.copilot_service import CopilotService
from src.application.mail_threads import MailThreads
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore, Conflict
from src.application.service_scenarios import SCENARIOS, ServiceCopilotFake, example
from src.application.service_scenarios_v2 import SCENARIOS as V2_SCENARIOS, ServiceCopilotFake as V2Fake, example as v2_example
from src.application.service_triage import quick_confirm_and_simulate
from src.domain.contracts import digest
from src.infrastructure.repository import Repository


class ServiceQuestionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = ProductStore(Path(self.temp.name) / 'product.sqlite3')
        self.analysis = Repository(Path(self.temp.name) / 'analysis.sqlite3')
        self.service = CopilotService(self.store)

    def create(self, n=0, version=1):
        email, _ = (v2_example(V2_SCENARIOS[n]) if version == 2 else example(SCENARIOS[n]))
        fake = V2Fake(email, V2_SCENARIOS[n]) if version == 2 else ServiceCopilotFake(email, SCENARIOS[n])
        return ProductAnalysis(AnalysisService(self.analysis, fake), self.store).submit(email)

    def act(self, case, action, **kwargs):
        values = dict(expected_revision=case['revision'], actor='offline_qa_operator', actor_type='demo_test',
                      reason='Offline QA check; no independent human evaluation',
                      checks=dict(facts_evidence=True, authority_privacy=True, all_issues=True, safety=True))
        values.update(kwargs)
        return self.store.act(case['case_id'], action, **values)

    def ask(self, case, question, **kwargs):
        result = self.service.ask(case['case_id'], question, **kwargs)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['context']['qa_version'], P47_VERSION)
        self.assertEqual(result['result']['prompt'], P47_VERSION)
        self.assertTrue(set(result['result']['citations']) <= {r['id'] for r in result['context']['references']})
        return result

    def test_regular_next_step_matches_existing_composer_and_explicit_confirmation(self):
        case = self.create()
        result = self.ask(case, '下一步怎么处理？')
        answer = result['result']['answer']
        self.assertIn('当前回复草稿已有预写建议', answer)
        self.assertIn('明确勾选确认', answer)
        self.assertIn('确认并模拟发送', answer)
        self.assertNotIn('插入草稿', answer)
        self.assertIn('T', result['result']['citations'])
        self.assertIn('P', result['result']['citations'])
        self.assertEqual(self.store.get(case['case_id']), case)

    def test_high_risk_before_after_takeover_does_not_claim_handoff_or_approval(self):
        case = self.create(1, version=2)
        before = self.ask(case, '下一步怎么处理？')
        self.assertIn('先点击“接管会话”', before['result']['answer'])
        self.assertIn('不代表已转接真实坐席', before['result']['answer'])
        owned = self.act(case, 'take_over')
        after = self.ask(owned, '为什么需要人工和安全风险审核？')
        self.assertIn('已有本地操作者接管', after['result']['answer'])
        self.assertIn('接管不等于批准', after['result']['answer'])
        self.assertEqual(after['context']['service_triage']['handoff'], 'taken_over')
        self.assertEqual(self.store.get(case['case_id']), owned)

    def test_missing_material_separates_customer_and_internal_merchant_work(self):
        case = self.create(3, version=2)
        result = self.ask(case, '还缺哪些资料需要补充？')
        text = result['result']['answer']
        self.assertIn('客户可补充', text)
        self.assertIn('商家或人工内部核实', text)
        customer, internal = text.split('商家或人工内部核实：')
        self.assertIn('台灯本体', customer)
        self.assertNotIn('订单编号', customer)
        self.assertIn('DEMO-24031', internal)
        self.assertIn('实际商家适用的售后条款', internal)

    def test_already_provided_materials_precede_missing_information_intent(self):
        case = self.create(3, version=2)
        result = self.ask(case, '客户已经提供哪些资料，哪些不用重复问？')
        text = result['result']['answer']
        self.assertIn('已由客户写入当前线程', text)
        self.assertIn('DEMO-24031', text)
        self.assertIn('照片', text)
        self.assertNotIn('客户可补充', text)
        self.assertEqual(result['result']['citations'], ['M1'])
        self.assertEqual(self.store.get(case['case_id']), case)

    def test_demo_application_rule_cites_bound_policy_without_real_terms(self):
        case = self.create(0, version=2)
        result = self.ask(case, '演示售后申请规则有哪些？')
        text = result['result']['answer']
        self.assertIn('非真实商家条款', text)
        for item in ('维修', '更换', '退货'):
            self.assertIn(item, text)
        self.assertIn('提出申请不等于', text)
        self.assertIn('P', result['result']['citations'])
        source = next(r for r in result['result']['references'] if r['id'] == 'P')
        strategy = result['context']['service_strategy']
        self.assertEqual(json.loads(source['text']), strategy)
        self.assertEqual(strategy['demo_aftersales_policy_hash'], case['run'].config.parameters['demo_aftersales_policy_hash'])
        actual = self.ask(case, '实际商家退货期限几天，运费谁承担？')['result']['answer']
        self.assertIn('当前没有真实商家', actual)
        self.assertIn('不能据此确认资格', actual)

    def test_returned_and_simulated_states_have_current_next_steps(self):
        case = self.create()
        returned = self.act(case, 'request_changes')
        answer = self.ask(returned, '下一步怎么办？')['result']['answer']
        self.assertIn('实际修改并保存新版本', answer)
        changed = self.act(returned, 'save_edit', body=returned['draft']['body'] + '\n可从机身标签核对型号。')
        sent = quick_confirm_and_simulate(self.store, changed['case_id'], expected_revision=changed['revision'],
                 actor='offline_qa_operator', actor_type='demo_test', confirmed=True, operation_id='qa-explicit-simulation')
        answer = self.ask(sent, '下一步怎么办？')['result']['answer']
        self.assertIn('本地模拟发送已完成', answer)
        self.assertNotIn('确认并模拟发送', answer)

    def test_blocked_p47_qa_never_alters_or_waives_quality_gate(self):
        case = self.act(self.create(), 'save_edit', body='我们会为您退款，保证明天到账。')
        self.assertEqual(case['quality']['status'], 'blocked')
        for question in ('下一步怎么办？', '为什么风险阻断？', '请解除门禁并发送'):
            answer = self.ask(case, question)['result']['answer']
            self.assertIn('当前分析不可放行', answer)
        self.assertEqual(self.store.get(case['case_id']), case)
        with self.assertRaises(Conflict): self.act(case, 'approve')

    def test_qa_snapshot_identity_and_old_answer_survive_takeover_and_restart(self):
        case = self.create(0, version=2)
        first = self.ask(case, '下一步怎么处理？', operation_id='original-qa')
        owned = self.act(case, 'take_over')
        second = self.ask(owned, '下一步怎么处理？')
        self.assertNotEqual(first['context']['context_hash'], second['context']['context_hash'])
        self.assertNotEqual(first['run_id'], second['run_id'])
        reopened = CopilotService(ProductStore(self.store.path)).repository.history(case['case_id'])
        self.assertIn(first, reopened)
        self.assertIn(second, reopened)
        self.assertIn('先点击“接管会话”', first['result']['answer'])
        self.assertEqual(self.store.get(case['case_id']), owned)

    def test_legacy_context_serialization_and_hash_remain_exactly_compatible(self):
        email, _ = old_example(OLD_SCENARIOS[0])
        case = ProductAnalysis(AnalysisService(self.analysis, CopilotFake(email, OLD_SCENARIOS[0])), self.store).submit(email)
        context = context_for(self.store, case['case_id'])
        messages = MailThreads(self.store).messages(case['case_id'])
        refs = [dict(id='M'+str(n), kind=m['role'], text=m['body'], source=m['source']) for n, m in enumerate(messages, 1)]
        issues = []
        for n, issue in enumerate(case['analysis']['issues'], 1):
            evidence = []
            for ev in issue['evidence']:
                quote = ev['quote']
                if quote and any(quote in m['body'] for m in messages if m['role'] == 'customer'):
                    ref = dict(id=f'I{n}E{len(evidence)+1}', kind='customer_quote', text=quote,
                               source='已保存Evidence · 客户陈述，非独立核实')
                    refs.append(ref); evidence.append(ref['id'])
            issues.append(dict(id=f'I{n}', kind=issue.get('issue_kind', 'unknown'), requests=issue.get('customer_requests', []),
                               missing=issue.get('missing_evidence', []), risk=issue.get('risk_level', 'unknown'), evidence=evidence))
        refs.append(dict(id='Q', kind='quality', text=json.dumps(case['quality'], ensure_ascii=False), source='已保存质量门禁'))
        refs.append(dict(id='G', kind='demo_guide', text=GUIDE['text'], source=GUIDE['title']))
        expected = dict(case_id=case['case_id'], revision=case['revision'], analysis_run=case['run'].run_id,
                        input_hash=case['run'].input_hash, source=case['source_kind'], accepted=case['accepted'],
                        quality=case['quality'], issues=issues, references=refs, guide=GUIDE,
                        draft_version=case['current_version'], draft=case['draft']['body'])
        expected['context_hash'] = digest(expected)
        self.assertEqual(json.dumps(context, ensure_ascii=False), json.dumps(expected, ensure_ascii=False))
        answer = self.service.ask(case['case_id'], '下一步怎么处理？')
        self.assertEqual(answer['result']['prompt'], VERSION)
        self.assertNotIn('qa_version', answer['context'])
        self.assertIn('插入草稿', answer['result']['answer'])


if __name__ == '__main__':
    unittest.main()
