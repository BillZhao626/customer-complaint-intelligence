"""Focused offline regression for audited statistics and strict first contracts."""
import unittest
from pathlib import Path
from src.application.p5b8r5_insights import R5Insights,SOURCE,store_target
from src.application.p5b8r4_contracts import parse_reply
ROOT=Path(__file__).resolve().parents[1]
class AuditedStatistics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=R5Insights(ROOT);cls.s=cls.c.snapshot(SOURCE)
    def test_coverage_and_axes(self):
        self.assertEqual((self.s['selected'],self.s['metrics']['successful']['numerator']),(90,87))
        for values in self.s['axes'].values():self.assertEqual(sum(x['numerator'] for x in values.values()),87)
    def test_mentions_not_store_complaint(self):
        i=dict(issue_kind='complaint',object_type='product',business_process='product issue')
        self.assertFalse(store_target(i,'Ningbo Tianyi Store'))
        self.assertFalse(store_target(dict(i,object_type='service',business_process='delivery/logistics issue'),'Ningbo Tianyi Store'))
    def test_praise_and_unknown_are_not_complaints(self):
        i=dict(issue_kind='praise',object_type='store',business_process='store service issue')
        self.assertFalse(store_target(i,'A'))
        self.assertFalse(store_target(dict(i,issue_kind='complaint'),None))
    def test_product_members_deduplicated(self):
        for g in self.s['groups']['product_category']:
            for key in ('count','negative','complaints'):
                m=g[key];self.assertEqual(m['numerator'],len(set(m['member_ids'])))
    def test_filter_includes_secondary_product_issue(self):
        for g in self.s['groups']['product_category']:
            category=g['values']['product_category']
            filtered=self.c.snapshot(SOURCE,product=category)
            self.assertEqual(set(g['count']['member_ids']),{m['id'] for m in filtered['members']})
    def test_unknown_store_service_complaints_are_separate(self):
        m=self.s['unattributed_store_complaints']
        self.assertEqual((m['numerator'],m['denominator']),(2,8))
        self.assertEqual({self.c.member(SOURCE,x)['email']['email_id'] for x in m['member_ids']},{'B7-079','B7-081'})
    def test_literal_evidence_and_identity(self):
        for r in self.c.records[SOURCE]:
            for i in r['issues']:
                for e in i['evidence']:self.assertEqual(r['email'][e['field']][e['start']:e['end']],e['quote'])
    def test_failed_filter_preserves_denominator(self):
        s=self.c.snapshot(SOURCE,status='failed');self.assertEqual(s['selected'],3);self.assertEqual(s['metrics']['successful']['numerator'],0)
    def test_known_false_store_attribution_not_included(self):
        nid=next(r['id'] for r in self.c.records[SOURCE] if r['email']['email_id']=='B7-036')
        g=next(g for g in self.s['groups']['store_location'] if g['values']['store_location']=='Ningbo Tianyi Store')
        self.assertNotIn(nid,g['complaints']['member_ids'])
class FirstContract(unittest.TestCase):
    def test_valid_multilingual_long_and_multi_issue_text(self):
        import json
        for text in ['您好，感谢反馈。' * 1000, 'Sorry about the damage. Please send the photos you took.\nWe can check the service charge separately.', '谢谢您的表扬。关于机器渗水，请先暂停使用。']:
            r=parse_reply(json.dumps(dict(reply=text),ensure_ascii=False),dict(finish_reason='stop'))
            self.assertEqual(r['first']['value']['reply'],text)
    def test_failures_never_become_first_success(self):
        for raw in ['{"reply":"ok","type":"json_object"}','{"reply":"ok"}{}','{"reply":"x","reply":"y"}','{"reply":"  "}','{"reply":5}']:
            with self.subTest(raw=raw):self.assertEqual(parse_reply(raw)['first']['status'],'rejected')
    def test_recovery_separate(self):
        r=parse_reply('{"reply":"完整回复"',dict(finish_reason='stop'))
        self.assertEqual(r['first']['status'],'rejected');self.assertIsNotNone(r['recovery'])
    def test_length_not_recovered(self):
        self.assertIsNone(parse_reply('{"reply":"ok"',dict(finish_reason='length'))['recovery'])
