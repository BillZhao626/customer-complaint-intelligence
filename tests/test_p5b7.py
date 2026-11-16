import unittest
from src.application.p5b7_context_checks import signals,reply_review

class ContextRepair(unittest.TestCase):
    def test_store_aliases_are_scoped_and_unknown_not_inferred(self):
        from src.application.p5b7_research import canonical_store
        self.assertEqual(canonical_store('浦东店'),'Shanghai Pudong Store')
        self.assertEqual(canonical_store('Pudong store'),'Shanghai Pudong Store')
        self.assertEqual(canonical_store('unknown'),'unknown')
        self.assertEqual(canonical_store('某个浦东新店'),'某个浦东新店')
    def test_product_association_deduplicates_and_excludes_failed_raw(self):
        from src.application.p5b7_research import B7Insights
        c=B7Insights.__new__(B7Insights);c.sources={'b7-test':{'id':'b7-test'}}
        p=dict(sentiment='negative',is_complaint=True,store_location='unknown',product_category='unknown',complaint_reason='product quality',source_attribution='product issue',urgency='low')
        issue=dict(category='Electronics',object_type='product',sentiment='negative',issue_kind='complaint')
        r=dict(id='one',email=dict(email_id='one',subject='explicit fixture'),input_hash='1',output_hash='1',prediction=p,status='succeeded',created_at=None,issues=[issue,issue])
        failed=dict(r,id='two',email=dict(email_id='two',subject='failed fixture'),input_hash='2',prediction=None,status='failed')
        c.records={'b7-test':[r,failed]}
        x=c.snapshot('b7-test');g=x['groups']['product_negative_association'][0]
        self.assertEqual(g['negative']['numerator'],1);self.assertEqual(g['negative']['denominator'],1)
        self.assertEqual(g['negative']['member_ids'],['one']);self.assertEqual(x['metrics']['emails']['denominator'],2)
    def test_reported_unanswered_contacts_and_negation(self):
        self.assertTrue(signals('我发过两次邮件，都没有人回复')['repeated_failure'])
        self.assertTrue(signals('I called a couple times and kept getting passed around')['repeated_failure'])
        self.assertFalse(signals('我发过两次邮件，问题已解决')['repeated_failure'])
        self.assertFalse(signals('说明书例句：我发过两次邮件，都没有人回复')['repeated_failure'])
    def test_deadline_is_not_bare_weekend_mention(self):
        self.assertTrue(signals('是准备这周末参加婚礼穿的')['deadline'])
        self.assertFalse(signals('这周末我去过店里')['deadline'])
    def test_listing_report_does_not_waive_new_promise(self):
        source='下单时页面显示预计两天内送达'
        self.assertFalse(reply_review('您下单时页面显示预计两天内送达。',source)['findings'])
        self.assertTrue(reply_review('我们保证明天送达。',source)['findings'])
        self.assertTrue(reply_review('预计两天内送达。',source)['findings'])
    def test_customer_reporting_verb_and_nested_execution(self):
        self.assertFalse(reply_review('你已说明鞋子寄回、门店曾表示收到后处理退款。','鞋子寄回')['findings'])
        self.assertTrue(reply_review('你已说明我们已退款。','')['findings'])
        self.assertTrue(reply_review('我们已为您处理退款。','')['findings'])

if __name__=='__main__':unittest.main()
