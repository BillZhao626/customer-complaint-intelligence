import json, unittest
from src.domain.contracts import EmailInput
from src.application.source_facts import attachment_facts, attachment_claim_audit
from src.application.service_response import chain_messages

class SourceFactsTest(unittest.TestCase):
 def email(self,body):return EmailInput(email_id='fixture',subject='Feedback',body=body)
 def test_source_levels_and_offsets(self):
  fixtures=[('我可以提供照片','OFFER_TO_PROVIDE'),('我已经拍了照片','CUSTOMER_REPORT_TAKEN'),('照片已发送给你','CUSTOMER_REPORT_SENT'),('我没有发送照片','DENIED_OR_NOT_SENT'),('上次发送了照片','HISTORICAL_UNVERIFIED'),('I took photos.','CUSTOMER_REPORT_TAKEN'),('I have sent the photos.','CUSTOMER_REPORT_SENT'),("I haven't sent the photos.",'DENIED_OR_NOT_SENT'),('The screenshot is inaccessible.','MENTION_UNCLEAR')]
  for text,expected in fixtures:
   with self.subTest(text=text):
    e=self.email(text);f=attachment_facts(e);s=f['source_mentions'][0]
    self.assertEqual(s['state'],expected)
    self.assertEqual((e.subject+'\n'+e.body)[s['start']:s['end']],s['quote'])
    self.assertFalse(f['received_files']);self.assertFalse(f['viewed_files'])
 def test_absent_source_never_gets_sending_prompt(self):
  payload=json.loads(chain_messages(self.email('电池鼓包，请帮忙处理。'),{'facts':{},'events':[]})[1][1])
  self.assertTrue(payload['attachment_evidence']['absent'])
  self.assertNotIn('allowed_statement',payload['attachment_evidence'])
 def test_fact_claims_and_conditional_advice(self):
  e=self.email('电池鼓包。')
  for bad in ['您提到已拍摄照片，如尚未发送，也可一并附上。','您提到已发送照片','您提到已拍摄照片','You mentioned sending photos.','I have reviewed your attached photos.']:
   self.assertTrue(attachment_claim_audit(bad,e)['findings'],bad)
  for good in ['如果您有照片，可以提供。','请提供照片。','Please share photos if safe to do so.','I cannot confirm receipt of photos.']:
   self.assertFalse(attachment_claim_audit(good,e)['findings'],good)
  self.assertFalse(attachment_claim_audit('You have sent photos.',self.email('I have sent photos.'))['findings'])
  self.assertTrue(attachment_claim_audit('We have received photos.',self.email('I have sent photos.'))['findings'])
 def test_unicode_quotes_remain_exact(self):
  e=self.email('我想问ＡＢＣ："Photo"\n這是另一段。')
  source=e.subject+'\n'+e.body
  self.assertNotIn('問',source);self.assertIn('问ＡＢＣ',source)
  from src.application.p5b8r1_contracts import parse_outcome
  from pathlib import Path
  fixture=json.loads((Path(__file__).parent/'fixtures/service_response_r6_regressions.json').read_text('utf8'))['B7-036']
  a=fixture['analysis'];a['issues'][0]['evidence']=['我想問ABC']
  self.assertFalse(parse_outcome(json.dumps(a),email=e)['semantic_eligible'])

 def test_judge_hard_error_reliability_cannot_be_averaged(self):
  from src.evaluation.p5b8r4_judge import validate_judgment
  e=self.email('No photos mentioned; a book is missing a page.')
  slot=dict(slot='X',case_id=e.email_id,run_id='r',arm='A',input_hash=e.input_hash,events=[],reply='I have reviewed your photos.',parse_ok=True)
  answer=dict(slot='X',scores=dict(action_accuracy=2,reliability=1),action_evidence=[],findings=[dict(category='HARD_ERROR',quote=slot['reply'],reason='no receipt')])
  data=dict(answers=[answer],preference='X')
  r=validate_judgment(data,dict(customer=e.model_dump(),answers=[slot]))
  self.assertEqual(r['validation']['validated_preference'],'UNKNOWN')
  self.assertTrue(any(x['code']=='HARD_ERROR_RELIABILITY_MUST_BE_ZERO' for x in r['validation']['errors']))
