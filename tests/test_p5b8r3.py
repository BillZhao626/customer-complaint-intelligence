"""Offline adversarial evidence/budget fixtures; no model quality assertions."""
import copy,json,tempfile,unittest,asyncio
from pathlib import Path
from unittest.mock import patch
from src.domain.contracts import EmailInput,digest
from src.evaluation import p5b8r3_judge as judge
from src.infrastructure.p5b8r3_execution import Dispatcher,read
from src.application.p5b8r3_guard import assess
from src.application.p5b8r3_reply import paired_messages,chain_messages
from src.application.p5b8r1_experiment import pair_invariant
from src.application.p5b8r3_experiment import Experiment,mock_provider,save,stability

def slot(email,arm='ONE'):
    s=dict(case_id=email.email_id,run_id='run-'+arm,arm=arm,input_hash=email.input_hash,parse_ok=True,reply='已创建内部转达请求。',events=[])
    e=dict(event_id='event-'+arm,conversation_id=email.email_id,input_hash=email.input_hash,kind='store_service_request',status='created',payload=dict(external_execution=False))
    s['events']=judge.bind([e],**{k:s[k] for k in ('case_id','run_id','arm','input_hash')});return s
def plan(ids):return dict(planned_requests=len(ids),allowed_call_ids=ids,proposed_cny_cap=20,pricing=dict(input_cny_per_million=2,output_cny_per_million=8))
MESSAGES=[('system','fixture'),('human','fixture')]
class Evidence(unittest.TestCase):
    def setUp(self):self.email=EmailInput(email_id='fixture',subject='thanks',body='请向门店转达谢意。')
    def test_empty_events_cannot_change_case_or_input_at_blinding(self):
        a,b=slot(self.email),slot(self.email,'TWO');a['events']=[]
        for field in ('case_id','input_hash'):
            bad=copy.deepcopy(a);bad[field]='other' if field=='case_id' else '0'*64
            with self.assertRaises(ValueError):judge.blind_pair(self.email,[bad,b])
    def test_raw_event_intrinsic_identity_cannot_be_rebound(self):
        a=slot(self.email);e={k:v for k,v in a['events'][0].items() if k!='_binding'}
        for k in ('case_id','conversation_id','run_id','arm','input_hash'):
            bad=copy.deepcopy(e);bad[k]='foreign'
            with self.assertRaises(ValueError):judge.bind([bad],**{k:a[k] for k in ('case_id','run_id','arm','input_hash')})
    def test_binding_payload_state_and_duplicate_ids_are_checked(self):
        a=slot(self.email)
        for key in ('case_id','run_id','arm','input_hash'):
            bad=copy.deepcopy(a);bad[key]='foreign'
            with self.assertRaises(ValueError):judge.validate_slot(bad,self.email)
        for key in ('status','kind','payload','event_id'):
            bad=copy.deepcopy(a);bad['events'][0][key]='changed'
            with self.assertRaises(ValueError):judge.validate_slot(bad)
        a['events']*=2
        with self.assertRaises(ValueError):judge.validate_slot(a)
    def test_blind_reversal_preserves_own_receipts_and_key(self):
        a,b=slot(self.email),slot(self.email,'TWO');b['events']=[]
        p,k=judge.blind_pair(self.email,[a,b]);q,j=judge.blind_pair(self.email,[a,b],reverse=True)
        self.assertEqual(k['X'],j['Y']);self.assertEqual(q['answers'][0]['events'],[])
        self.assertNotIn('ONE',json.dumps(p));self.assertNotIn('TWO',json.dumps(p))
    def test_parser_rejects_cross_slot_ids_and_query_pending(self):
        p,_=judge.blind_pair(self.email,[slot(self.email),slot(self.email,'TWO')])
        with tempfile.TemporaryDirectory() as directory:
            raw,_=mock_provider([('system',''),('human',json.dumps(p))],Path(directory),dict(blind_payload=p))
        out=json.loads(raw);out['answers'][0]['action_evidence']=[dict(quote='已创建内部转达请求',state='INTERNAL_CREATED',event_ids=[p['answers'][1]['events'][0]['event_id']],missing_evidence='')]
        with self.assertRaises(ValueError):judge.parse(out,p)
        out['answers'][0]['action_evidence'][0].update(event_ids=[p['answers'][0]['events'][0]['event_id']],state='EXTERNAL_COMPLETED')
        with self.assertRaises(ValueError):judge.parse(out,p)
    def test_separate_conjunction_cannot_hide_completion_behind_negation(self):
        a=slot(self.email);rt=dict(events=a['events'])
        self.assertFalse(assess('尚未转达谢意。',rt,self.email.input_hash)['findings'])
        self.assertFalse(assess('已创建内部转达请求。',rt,self.email.input_hash)['findings'])
        for text in ('尚未转达谢意，但已联系门店。','已创建内部转达请求，并已转达谢意。'):
            self.assertIn('H04',{f['code'] for f in assess(text,rt,self.email.input_hash)['findings']})
    def test_shared_policy_is_same_for_arms_and_not_case_id_specific(self):
        from tests.test_p5b8r1 import analysis
        rt=dict(events=[],facts=dict(status='UNKNOWN'));a=analysis()
        m=paired_messages(self.email,a,rt);self.assertTrue(pair_invariant(m)['equal_common'])
        self.assertEqual(chain_messages(self.email,rt)[0],chain_messages(self.email,rt,a)[0]);self.assertNotIn('B7-',m['ISSUES_NO_SENTIMENT'][0][1])
    def test_missing_evidence_context_is_retained_without_authorizing_action(self):
        a,b=slot(self.email),slot(self.email,'TWO')
        e=a['events'][0];e.pop('_binding');e.update(kind='knowledge_lookup',status='executed')
        a['events']=judge.bind([e],**{k:a[k] for k in ('case_id','run_id','arm','input_hash')})
        payload,_=judge.blind_pair(self.email,[a,b]);eid=payload['answers'][0]['events'][0]['event_id']
        answer=lambda label:dict(slot=label,scores={d:1 for d in judge.DIMENSIONS},reasons={d:'fixture' for d in judge.DIMENSIONS},findings=[],action_evidence=[])
        result=dict(answers=[answer('X'),answer('Y')],preference='TIE')
        result['answers'][0]['action_evidence']=[dict(quote='已创建内部转达请求',state='INTERNAL_CREATED',event_ids=[eid],missing_evidence='Only query exists; no created task')]
        parsed=judge.parse(result,payload);claim=parsed['answers'][0]['action_evidence'][0]
        self.assertEqual(claim['event_ids'],[]);self.assertEqual(claim['context_event_ids'],[eid]);self.assertEqual(claim['support_status'],'UNSUPPORTED_CONTEXT_ONLY')
        result['answers'][0]['action_evidence'][0]['event_ids']=['foreign']
        with self.assertRaises(ValueError):judge.parse(result,payload)

class Execution(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def dispatcher(self,ids=('one','two'),provider=mock_provider,**kwargs):return Dispatcher(self.root,plan(list(ids)),provider=provider,**kwargs)
    def test_live_denial_creates_neither_ledger_nor_provider(self):
        with self.assertRaises(PermissionError):self.dispatcher(mode='LIVE')
        self.assertFalse((self.root/'budget.sqlite3').exists())
    def test_raw_survives_bad_usage_before_billing_validation(self):
        n=[]
        def provider(*args):n.append(1);return 'broken-json',dict(input_tokens=None,output_tokens=None,total_tokens=None)
        d=self.dispatcher(provider=provider)
        with self.assertRaisesRegex(RuntimeError,'UNKNOWN'):d.call('one',MESSAGES)
        self.assertEqual(read(self.root/'calls'/digest('one')/'response.json')['raw'],'broken-json')
        with self.assertRaisesRegex(RuntimeError,'UNKNOWN'):d.call('one',MESSAGES)
        with self.assertRaises(RuntimeError):d.call('two',MESSAGES)
        self.assertEqual(len(n),1);self.assertEqual(d.summary()['states'],{'UNKNOWN':1})
    def test_transport_unknown_restart_and_pre_dispatch_reservation_never_retry(self):
        def fail(*args):raise TimeoutError('fixture')
        d=self.dispatcher(provider=fail)
        with self.assertRaises(TimeoutError):d.call('one',MESSAGES)
        restored=self.dispatcher()
        with self.assertRaises(RuntimeError):restored.call('one',MESSAGES)
        with self.assertRaises(RuntimeError):restored.call('two',MESSAGES)
    def test_resume_completed_is_no_new_request_and_detects_drift(self):
        count=[]
        def provider(*args):count.append(1);return 'invalid-json',dict(input_tokens=1,output_tokens=1,total_tokens=2)
        d=self.dispatcher(provider=provider);r=d.call('one',MESSAGES);self.assertEqual(d.call('one',MESSAGES),r);self.assertEqual(count,[1])
        with self.assertRaises(ValueError):d.call('one',MESSAGES+[('human','changed')])
        p=self.root/'calls'/digest('one')/'response.json';raw=read(p);raw['raw']='tampered';p.write_text(json.dumps(raw),'utf-8')
        with self.assertRaises(ValueError):d.call('one',MESSAGES)
    def test_budget_rejects_before_invoking_provider(self):
        p=plan(['one']);p['proposed_cny_cap']=.000001;count=[]
        d=Dispatcher(self.root,p,provider=lambda *args:count.append(1))
        with self.assertRaisesRegex(RuntimeError,'Budget'):d.call('one',MESSAGES)
        self.assertEqual(count,[]);self.assertEqual(d.summary()['states'],{})
    def test_unplanned_request_and_authorization_drift_rejected(self):
        d=self.dispatcher()
        with self.assertRaises(ValueError):d.call('foreign',MESSAGES)
        with self.assertRaises(ValueError):Dispatcher(self.root,plan(['different']),provider=mock_provider)
    def test_concurrent_dispatch_observes_inflight_reservation(self):
        d=self.dispatcher()
        def provider(*args):
            other=self.dispatcher()
            with self.assertRaises(RuntimeError):other.call('two',MESSAGES)
            return '{}',dict(input_tokens=1,output_tokens=1,total_tokens=2)
        d.provider=provider;d.call('one',MESSAGES)
    def test_storage_failure_after_provider_response_stops_dispatch(self):
        d=self.dispatcher(provider=lambda *args:('{}',dict(input_tokens=1,output_tokens=1,total_tokens=2)))
        from src.infrastructure import p5b8r3_execution as execution
        original=execution.write_first
        def write(p,v):
            if Path(p).name=='response.json':raise OSError('fixture disk error')
            return original(p,v)
        with patch.object(execution,'write_first',write):
            with self.assertRaises(OSError):d.call('one',MESSAGES)
        self.assertEqual(d.summary()['states'],{'UNKNOWN':1})
    def test_actual_existing_sdk_mocktransport_retains_http_response(self):
        import httpx
        from src.application.p5b3_runtime import Analyzer
        from src.infrastructure.v3_live_settings import V3PilotSettings
        def respond(request):
            return httpx.Response(200,json=dict(id='fixture-sdk',object='chat.completion',created=1,model='deepseek-flash',choices=[dict(index=0,message=dict(role='assistant',content='{"reply":"fixture"}'),finish_reason='stop')],usage=dict(prompt_tokens=5,completion_tokens=5,total_tokens=10)))
        settings=V3PilotSettings(api_key='offline-fixture-only',enabled=True,max_tokens=4000,max_attempts=1)
        a=Analyzer(settings,self.root,candidate=False,mock_http_transport=httpx.MockTransport(respond));a.messages=lambda e:MESSAGES
        raw,meta=asyncio.run(a.request(EmailInput(email_id='sdk',subject='',body='fixture'),False,90))
        self.assertEqual(raw,'{"reply":"fixture"}');self.assertTrue((self.root/'provider-response.txt').exists());self.assertEqual(meta['total_tokens'],10)
if __name__=='__main__':unittest.main()
