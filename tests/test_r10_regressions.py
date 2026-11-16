"""R10 scope regressions exercised with explicit offline inputs."""
import unittest

from src.application import service_response
from src.application.p5b8r3_final_guard import assess
from src.application.source_facts import attachment_claim_audit
from src.domain.contracts import EmailInput


class R10Regression(unittest.TestCase):
    def test_report_no_photo_taken_does_not_assert_photo(self):
        mail=EmailInput(email_id='fixture',subject='Missing screws',body='我还没拍照片。请问怎么补件？')
        self.assertFalse(attachment_claim_audit('您提到还没拍照片。',mail)['findings'])
        self.assertTrue(attachment_claim_audit('我已经查看了您的照片。',mail)['findings'])

    def test_open_dispatch_question_keeps_independent_assertion(self):
        self.assertFalse(assess('That helps verify what was dispatched.',dict(events=[]),'h')['findings'])
        self.assertTrue(assess('That helps verify what was dispatched. The lamp was dispatched.',dict(events=[]),'h')['findings'])

    def test_product_inquiry_requires_its_own_created_receipt(self):
        receipt=dict(event_id='e',input_hash='h',kind='human_input_request',status='created',
                     payload=dict(action=dict(goal='verify care for wood')))
        reply="I've created an internal product inquiry to verify care for wood."
        self.assertFalse(assess(reply,dict(events=[receipt]),'h')['findings'])
        self.assertTrue(assess(reply,dict(events=[]),'h')['findings'])
        self.assertTrue(assess(reply+" We contacted the store.",dict(events=[receipt]),'h')['findings'])

    def test_visit_constraint_does_not_become_its_own_work(self):
        body='Can you check whether the Tuesday appointment slot can be moved? Please ask before giving anyone a key code.'
        mail=EmailInput(email_id='fixture',subject='Visit',body=body)
        constraint=dict(kind='store_service_request',goal='ask before giving anyone a key code',issue_ids=['I1'],
                        evidence=['Please ask before giving anyone a key code.'],priority='normal')
        plan=service_response.reconcile_plan(mail,[constraint])
        self.assertEqual(len(plan),1)
        self.assertIn('rescheduling',plan[0]['goal'])

    def test_composed_brief_prioritizes_service_over_incidental_praise(self):
        mail=EmailInput(email_id='fixture',subject='Chair',body='Your shop assistant was lovely. The chair wobbles. Can you help?')
        messages=service_response.chain_messages(mail,dict(events=[]))
        self.assertNotIn('feedback_relay',messages[-1][1])
        self.assertIn('chair wobbles',messages[-1][1])
