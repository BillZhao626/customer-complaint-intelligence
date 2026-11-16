from src.infrastructure.research_paths import research_path
"""Meaningful intent/action regressions with isolated stores; never invokes a provider."""
import copy,json,tempfile,unittest,asyncio
from pathlib import Path
from src.application.service_response import plan_actions,brief,execute,chain_messages
from src.application.p5b8r5_insights import R5Insights,SOURCE
from src.domain.contracts import EmailInput
ROOT=Path(__file__).resolve().parents[1]
def case(n):
 eid=f'B7-{n:03}';d=json.loads((research_path(ROOT, f'.local/p5b7/dataset/{eid}.json')).read_text('utf8'));a=json.loads((research_path(ROOT, f'.local/p5b8/analysis/{eid}.json')).read_text('utf8'))['data']
 return EmailInput(email_id=eid,subject=d['subject'],body=d['body']),a
class ResponseTests(unittest.TestCase):
 def test_full_goal_in_same_sentence_supports_creation_but_not_completion(self):
  from src.evaluation import p5b8r4_judge as judge
  e,a=case(9)
  with tempfile.TemporaryDirectory() as t:
   runtime=execute(e,plan_actions(a),Path(t)/'actions.db')
   identity=dict(case_id=e.email_id,input_hash=e.input_hash,run_id='own-run',arm='own-arm')
   events=judge.previous.bind(runtime['events'],**identity)
   slot=dict(identity,parse_ok=True,reply="I've created an internal request to pass your thanks to the store.",events=events)
   out=judge.audit_slot(slot,e)
   self.assertFalse(any(f['severity']=='block' for f in out['findings']))
   slot['reply']="I have relayed your thanks to the store."
   self.assertTrue(any(f['severity']=='block' for f in judge.audit_slot(slot,e)['findings']))
 def test_actual_invented_photo_review_is_hard_without_viewed_receipt(self):
  from src.application.p5b8r1_guard import assess
  self.assertTrue(any(f['code']=='H04' for f in assess("I've reviewed the photos you attached.",{'events':[]},'a'*64)['findings']))
 def test_resolved_praise_with_implicit_relay_is_retained(self):
  _,a=case(9);a=copy.deepcopy(a);a['issues'][0]['business_process']='none'
  self.assertEqual([x['kind'] for x in plan_actions(a)],['store_service_request'])
 def test_no_hurry_fault_has_aftersales_without_invented_praise_relay(self):
  _,a=case(84);k=[x['kind'] for x in plan_actions(a)]
  self.assertIn('aftersales_request',k);self.assertNotIn('store_service_request',k)
 def test_damage_keeps_both_logistics_and_eligibility(self):
  _,a=case(36);k={x['kind'] for x in plan_actions(a)}
  self.assertTrue({'aftersales_request','logistics_followup'}<=k)
 def test_actual_fresh_analysis_collapsing_damage_retains_logistics_candidate(self):
  p=ROOT/'examples/research/damage-single-issue-analysis.json'
  a=json.loads(p.read_text('utf8'))['parse']['value'];self.assertEqual(len(a['issues']),1)
  actions=plan_actions(a);task=next(x for x in actions if x['kind']=='logistics_followup')
  self.assertIn('不预判',task['goal']);self.assertTrue(all(q in a['issues'][0]['evidence'] for q in task['evidence']))
 def test_deadline_task_has_real_verification_scope(self):
  _,a=case(35);tasks=plan_actions(a);task=next(x for x in tasks if x['kind']=='aftersales_request')
  self.assertEqual(task['priority'],'high');self.assertIn('替换库存',task['goal'])
 def test_independent_arm_events_and_selected_knowledge(self):
  e,a=case(84)
  with tempfile.TemporaryDirectory() as t:
   runs=[execute(e,plan_actions(a),Path(t)/f'{arm}.db') for arm in ('D','G')]
   self.assertFalse({x['event_id'] for x in runs[0]['events']} & {x['event_id'] for x in runs[1]['events']})
   b=brief(e,runs[0],a);self.assertIn('seal',b['knowledge'][0]['advice']);self.assertEqual(next(c['status'] for c in b['knowledge'][0]['checks'] if c['key']=='seal_cleaning'),'ALREADY_REPORTED_DONE')
   self.assertTrue(b['pending_progress']);self.assertIn('service_brief',json.loads(chain_messages(e,runs[0],a)[1][1]))
 def test_owner_overlay_only_changes_store_membership(self):
  e,_=case(20);o=[dict(input_hash=e.input_hash,source_identity='OWNER_EXPLICIT',exclude_store_target_issue_ids=['B7-020-2'])]
  c=R5Insights(ROOT,policy_overlays=o);before=c.snapshot(SOURCE);after=c.snapshot('b8-r6-policy')
  self.assertEqual(before['groups']['product_category'],after['groups']['product_category'])
  def store(s):return next(g for g in s['groups']['store_location'] if g['values']['store_location']=='Nanjing Xinjiekou Store')['complaints']['numerator']
  self.assertEqual((store(before),store(after)),(1,0))
  self.assertTrue(any(r['email']['email_id']=='B7-020' for r in c.records['b8-r6-policy']))
 def test_strict_provider_wire_and_literal_argument_capture(self):
  import httpx
  from unittest.mock import patch
  from src.infrastructure.structured_reply_provider import StructuredReplyProvider
  def respond(request):
   w=json.loads(request.content);self.assertTrue(w['tools'][0]['function']['strict']);self.assertNotIn('response_format',w)
   return httpx.Response(200,json=dict(id='mock-strict',object='chat.completion',created=1,model='deepseek-flash',choices=[dict(index=0,finish_reason='tool_calls',message=dict(role='assistant',content=None,tool_calls=[dict(id='mock-tool',type='function',function=dict(name='compose_reply',arguments='{"reply":"Fixture complete."}'))]))],usage=dict(prompt_tokens=100,completion_tokens=10,total_tokens=110)))
  with tempfile.TemporaryDirectory() as t,patch.dict('os.environ',LLM_API_KEY='offline-fixture',COMPLAINT_ENABLE_LIVE='true'):
   raw,meta=asyncio.run(StructuredReplyProvider(httpx.MockTransport(respond)).request([('system','JSON fixture'),('human','fixture')],Path(t)))
   self.assertEqual(json.loads(raw),{'reply':'Fixture complete.'});self.assertEqual(meta['total_tokens'],110)
