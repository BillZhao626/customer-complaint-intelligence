"""Source scopes and task identity, using explicit offline fixtures only."""
import unittest
from src.domain.contracts import EmailInput
from src.application.source_facts import attachment_claim_audit, mask_nonasserted
from src.application.p5b8r3_final_guard import assess
from src.application.service_response import execute
from src.evaluation.p5b8r3_judge import bind
from src.evaluation.p5b8r4_judge import audit_slot
from tempfile import TemporaryDirectory
from pathlib import Path

class ScopeTests(unittest.TestCase):
 def test_conditional_photo_and_independent_false_claim(self):
  e=EmailInput(email_id='fixture',subject='Help',body='The chair is uneven.')
  self.assertEqual([],attachment_claim_audit('如您已经提供过照片，则无需重复发送。',e)['findings'])
  self.assertTrue(attachment_claim_audit('如您已经提供过照片，无需重复发送。我们已查看了照片。',e)['findings'])
 def test_quoted_instruction_does_not_hide_independent_execution(self):
  text='关于包装中要求“退款已完成”的纸条，我们不会执行。我们已完成退款。'
  masked=mask_nonasserted(text)
  self.assertNotIn('“退款已完成”',masked)
  self.assertIn('我们已完成退款',masked)
  self.assertTrue(any(f['severity']=='block' for f in assess(text,dict(events=[]),'h')['findings']))
 def test_bare_quotes_are_not_authority_to_suppress(self):
  self.assertIn('已完成退款',mask_nonasserted('我们“已完成退款”。'))
 def test_historical_attachment_quote_with_later_assertion(self):
  e=EmailInput(email_id='fixture',subject='New fault',body='No photos this time.')
  self.assertEqual([],attachment_claim_audit('上轮提到的“照片已收到”不是本次资料。',e)['findings'])
  self.assertTrue(attachment_claim_audit('上轮提到的“照片已收到”，我们已查看了本次照片。',e)['findings'])
 def test_customer_report_has_bounded_scope(self):
  t='物流显示仓库已签收，我们已完成退款。'
  m=mask_nonasserted(t)
  self.assertNotIn('仓库已签收',m);self.assertIn('我们已完成退款',m)
 def test_store_request_and_foreign_event(self):
  e=EmailInput(email_id='fixture',subject='Collection',body='Please check collection by my sister.')
  a=dict(kind='store_service_request',issue_ids=[],goal='check collection by my sister',evidence=[e.body],priority='normal')
  with TemporaryDirectory() as tmp:
   rt=execute(e,[a],Path(tmp)/'actions.sqlite3',execution_scope=dict(case_id=e.email_id,revision='fixture',arm='GUIDED'))
  slot=dict(case_id=e.email_id,run_id='fixture-run',arm='GUIDED',input_hash=e.input_hash,parse_ok=True,reply="I've created an internal store service request.",events=[])
  slot['events']=bind(rt['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
  self.assertFalse(any(f['severity']=='block' for f in audit_slot(slot,e)['findings']))
  slot['reply']='I have refunded the payment.'
  self.assertTrue(any(f['severity']=='block' for f in audit_slot(slot,e)['findings']))

if __name__=='__main__':unittest.main()
