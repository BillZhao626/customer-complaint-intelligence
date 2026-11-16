"""No live calls; fake orchestration and production factory integration."""
import json,tempfile,unittest
from pathlib import Path
from src.application.r6u0_workflow import generate,product_run
from src.domain.contracts import EmailInput
ROOT=Path(__file__).resolve().parents[1]

class WorkflowTest(unittest.TestCase):
 def test_delivery_goal_synonym_requires_own_scoped_task(self):
  from src.application.p5b8r4_evidence import claim,support
  event=dict(event_id='delivery-created',input_hash='h',kind='logistics_followup',status='created',payload=dict(action=dict(goal='核查包装破损的交付环节情况')))
  c=claim('已创建物流核查请求','INTERNAL_CREATED')
  self.assertTrue(support(c,dict(events=[event]),'h')['supported'])
  self.assertFalse(support(c,dict(events=[dict(event,kind='aftersales_request')]),'h')['supported'])

 def test_real_orchestrator_fake_provider_and_scoped_receipts(self):
  fixture=json.loads((ROOT/'tests/fixtures/service_response_r6_regressions.json').read_text('utf8'))['B7-036']
  calls=[]
  def invoke(suffix,msg,payload):
   calls.append((suffix,payload))
   raw=json.dumps(fixture['analysis']) if suffix=='ANALYSIS' else '{"actions":[]}' if suffix.endswith('PLAN') else '{"reply":"很抱歉商品受损。请先不要通电，提供已拍照片和订单凭证以便核查。"}'
   return dict(raw=raw,run_id=suffix,elapsed_ms=1,metadata=dict(dispatch_at='2026-11-05T00:00:00+00:00',finish_reason='tool_calls' if suffix.endswith('REPLY') else 'stop'))
  with tempfile.TemporaryDirectory() as t:
   r=generate(fixture['email'],invoke,t,semantic_planning=False)
   self.assertEqual(len(calls),4)
   self.assertTrue(r['GUIDED']['parse']['semantic_eligible'])
   self.assertTrue(r['GUIDED']['analysis_parse']['semantic_eligible'])
   a,b=[{e['event_id'] for e in r[x]['runtime']['events']} for x in ('DIRECT','GUIDED')]
   self.assertFalse(a&b)
   self.assertTrue(any(e['kind']=='logistics_followup' for e in r['GUIDED']['runtime']['events']))
   self.assertEqual(product_run(r['GUIDED']).metadata['analysis_run_id'],'ANALYSIS')
   from src.application.product_workflow import ProductStore
   store=ProductStore(Path(t)/'product.sqlite3',quality_inspector=lambda *a:dict(status='review_required',findings=[]))
   self.assertIsNotNone(store.create(product_run(r['GUIDED']),'fake controlled integration',origin='new_analysis'))
   self.assertTrue(all(not e['payload']['external_execution'] for arm in r.values() for e in arm['runtime']['events']))

 def test_compound_tasks_need_both_receipts_and_generic_team_not_named_store(self):
  from src.application.p5b8r4_evidence import claim,support
  c=claim('已经创建了售后核实请求和物流核查请求','INTERNAL_CREATED')
  e=lambda kind,goal:dict(event_id=kind,input_hash='h',kind=kind,status='created',payload=dict(action=dict(goal=goal)))
  a=e('aftersales_request','核实维修或退换适用条件');b=e('logistics_followup','外箱破损')
  self.assertTrue(support(c,dict(events=[a,b]),'h')['supported'])
  self.assertFalse(support(c,dict(events=[b]),'h')['supported'])
  self.assertIsNone(claim("I've created a request to pass your thanks to the store team",'INTERNAL_CREATED')['target'])
  self.assertEqual(claim('created a request to store B','INTERNAL_CREATED')['target'],'B')

 def test_unsafe_english_power_test_and_negation(self):
  from src.evaluation.p5b5r2_judge import diagnose
  ctx=[dict(role='customer',text='My coffee machine arrived damaged.')]
  self.assertTrue(any(f['code']=='H01' for f in diagnose('Switch on the damaged machine to check it.',customer_context=ctx)['hard_findings']))
  self.assertFalse(diagnose('Do not switch on the damaged machine.',customer_context=ctx)['hard_findings'])

 def test_product_recording_review_does_not_inherit_execution_block(self):
  from src.application.p5b8r1_guard import calibrate
  from src.application.p5b8r3_final_guard import assess
  reply='您的谢意我们已记录。'
  prior=dict(findings=[dict(code='executed_action',quote='我们已记录',severity='block')])
  audit=assess(reply,dict(events=[],facts={}), 'h')
  result=calibrate(prior,reply,{},'h',action_audit=audit)
  self.assertEqual(result['status'],'review_required')
  self.assertTrue(any(x['code']=='RECORD_REVIEW' for x in result['findings']))
  fake='我们已创建表扬转达请求。'
  bad=calibrate(dict(findings=[]),fake,{},'h',action_audit=assess(fake,dict(events=[],facts={}), 'h'))
  self.assertEqual(bad['status'],'blocked')

 def test_current_factory_live_injection_defaults_closed(self):
  from src.app.p5b8_api import create
  from fastapi.testclient import TestClient
  class Closed:
   def status_ui(self):return dict(enabled=False,remaining_requests=0,remaining_cny=0,halted='test_closed')
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)
   with TestClient(create(p/'db.sqlite3',p,live_driver=Closed())) as c:
    self.assertEqual(c.get('/api/p5b5r2/live/status').json()['halted'],'test_closed')
