"""Scoped R9 regressions, using temporary receipts and a no-network provider."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from src.application import service_response as service
from src.domain.contracts import EmailInput
from src.infrastructure.p5b8r3_execution import Dispatcher


class R9Regressions(unittest.TestCase):
    def test_secret_warning_has_own_scope(self):
        mail = EmailInput(email_id='control',subject='柜机',body='我的包裹仍在柜里，柜机屏幕黑了。')
        safe = (
            '请回复订单号或运单号及柜机所在位置（无需提供取件码）。',
            'Please have the tracking reference ready — but do not share your pickup code by email.',
            'Reply with the tracking number without including your pickup code.',
        )
        for reply in safe:
            with self.subTest(reply=reply):
                self.assertFalse(any(f['code']=='SENSITIVE_EMAIL_INTAKE' for f in service.audit_reply(mail,reply,{})['findings']))
        unsafe = ('Please email the pickup code.', '请提供完整身份证。', 'Do not share your password. Reply with your pickup code.')
        for reply in unsafe:
            with self.subTest(reply=reply):
                self.assertTrue(any(f['code']=='SENSITIVE_EMAIL_INTAKE' for f in service.audit_reply(mail,reply,{})['findings']))

    def test_passive_creation_still_requires_receipt(self):
        from src.application.p5b8r3_final_guard import assess
        reply='A logistics verification request has been created.'
        self.assertTrue(any(f['severity']=='block' for f in assess(reply,dict(events=[]),'h')['findings']))
        event=dict(event_id='local',input_hash='h',kind='logistics_followup',status='created',
                   payload=dict(action=dict(goal='Trace the missing parcel with logistics')))
        self.assertFalse(any(f['severity']=='block' for f in assess(reply,dict(events=[event]),'h')['findings']))

    def test_collection_verification_uses_store_receipt_not_delivery(self):
        from src.application.p5b8r3_final_guard import assess
        event=dict(event_id='store',input_hash='h',kind='store_service_request',status='created',
                   payload=dict(action=dict(goal='check delegate collection and hold period')))
        reply='A store service request covering delegate collection has been created.'
        self.assertFalse(any(f['severity']=='block' for f in assess(reply,dict(events=[event]),'h')['findings']))
        both='A store service and logistics verification request covering delegate collection and parcel delivery has been created.'
        self.assertTrue(any(f['severity']=='block' for f in assess(both,dict(events=[event]),'h')['findings']))

    def test_declined_clock_is_not_payment_recommendation(self):
        mail=EmailInput(email_id='control',subject='Voucher',body='The voucher expires on Sunday. Which time zone applies?')
        reply='The payment timestamp depends on this merchant’s terms, so I won’t suggest a “safe” local time.'
        self.assertFalse(service.audit_reply(mail,reply,{})['findings'])
        self.assertTrue(service.audit_reply(mail,reply+' Please pay on Sunday in your local time.',{})['findings'])

    def test_scoped_denial_and_quotation_leave_later_claim(self):
        from src.application.source_facts import mask_nonasserted
        denial='请暂不要视为已完成代取授权。'
        quoted='核实“已联系门店”是否属于实际执行记录。'
        self.assertNotIn('已完成代取授权',mask_nonasserted(denial))
        self.assertNotIn('已联系门店',mask_nonasserted(quoted))
        self.assertIn('已联系门店',mask_nonasserted(quoted+'我们已联系门店。'))

    def test_subscription_and_billing_date_share_one_action(self):
        mail=EmailInput(email_id='control',subject='Next refill',
                        body='Can I skip one subscription refill? What is the next billing date?')
        a=dict(kind='clarification_request',issue_ids=['I1'],goal='check subscription skip',
               evidence=['Can I skip one subscription refill'],priority='normal')
        b=dict(kind='billing_request',issue_ids=['I2'],goal='check next billing date',
               evidence=['What is the next billing date'],priority='normal')
        plan=service.reconcile_plan(mail,[a,b])
        self.assertEqual([(item['kind'],item['issue_ids']) for item in plan],[('billing_request',['I1','I2'])])
        self.assertEqual(service.reconcile_plan(mail,plan),plan)

    def test_single_speaker_relay_intent_remains_review(self):
        mail=EmailInput(email_id='control',subject='凳子',body='店员态度好，买回的凳子却不平。')
        result=service.audit_reply(mail,'我会把这份好评转达。请回复订单号。',{})
        self.assertEqual([(f['code'],f['severity']) for f in result['findings']],
                         [('UNGROUNDED_RELAY_INTENT','review')])

    def test_one_process_can_share_reserved_budget_without_cross_process_lease(self):
        barrier=Barrier(2,timeout=10)
        plan=dict(allowed_call_ids=['A','B','C'],planned_requests=2,proposed_cny_cap=1,
                  pricing=dict(input_cny_per_million=2,output_cny_per_million=8))
        msg=[('human','fixture')]
        with TemporaryDirectory() as folder:
            other=Dispatcher(Path(folder),plan,provider=lambda *a:self.fail('Foreign process dispatched'))

            def provider(*args):
                barrier.wait()
                with self.assertRaisesRegex(RuntimeError,'unresolved'):
                    other.call('C',msg)
                barrier.wait()
                return '{}',dict(input_tokens=1,output_tokens=1,total_tokens=2)

            d=Dispatcher(Path(folder),plan,provider=provider,max_inflight=2)
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(len(list(pool.map(lambda k:d.call(k,msg),['A','B']))),2)
            self.assertEqual(d.summary()['states'],dict(COMPLETED=2))
            with self.assertRaisesRegex(RuntimeError,'cap exceeded'):
                d.call('C',msg)
