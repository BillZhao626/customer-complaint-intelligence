"""Same frozen pipeline for offline fixtures and explicitly authorized live runs."""
import copy,json
from pathlib import Path
from src.domain.contracts import EmailInput,digest
from src.application import p5b8r3_reply as composer
from src.application.p5b8r1_experiment import write_first,pair_invariant
from src.application.p5b8r1_contracts import parse_outcome,analysis_system
from src.application.p5b8r1_actions import guided_actions
from src.application.p5b8_pipeline import execute,validate_plan,check_reply
from src.application.p5b8r3_guard import assess
from src.evaluation import p5b8r3_judge as judge
from src.infrastructure.p5b8r3_execution import read

def save(path,value):
    path=Path(path)
    if path.exists():
        if read(path)!=json.loads(json.dumps(value)):raise ValueError('Frozen artifact drift: '+str(path))
    else:write_first(path,value)
    return value

class Experiment:
    def __init__(self,root,dispatcher,prepared):
        self.root=Path(root);self.dispatcher=dispatcher;self.prepared=Path(prepared)
        self.plan=read(self.prepared/'PLAN.json')
    def reply(self,identity,email,messages,runtime,arm):
        path=self.root/'results'/(identity+'.json')
        call=self.dispatcher.call(identity,messages,dict(customer=email.model_dump(),runtime=runtime))
        parsed=parse_outcome(call['raw'],metadata=call['metadata'])
        reply=parsed['value']['reply'] if parsed['value'] else ''
        slot=dict(case_id=email.email_id,run_id=call['run_id'],arm=arm,input_hash=email.input_hash,parse_ok=parsed['semantic_eligible'],reply=reply,facts=runtime['facts'],attachment_manifest=[])
        slot['events']=judge.bind(runtime['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
        result=dict(identity=identity,customer=email.model_dump(),slot=slot,runtime=runtime,parse=parsed,call=call,
                    action_screen=assess(reply,runtime,email.input_hash),inherited_screen=check_reply(email,reply,runtime),quality_identity='OFFLINE_FIXTURE_NOT_QUALITY' if self.dispatcher.mode!='LIVE' else 'AUTOMATIC_PROVISIONAL')
        return save(path,result)
    def A(self):
        for spec in self.plan['A']:
            email=EmailInput.model_validate(spec['email']);runtime=spec['runtime']
            messages=spec['messages'];pair_invariant(messages)
            for arm in spec['order']:self.reply('A-'+email.email_id+'-'+arm,email,messages[arm],runtime,arm)
    def B(self):
        for index,spec in enumerate(self.plan['B']):
            email=EmailInput.model_validate(spec['email']);eid=email.email_id
            # Balanced first-arm order; both start in their own empty store.
            for arm in (('DIRECT','GUIDED') if index%2==0 else ('GUIDED','DIRECT')):
                pre='B-'+eid+'-'+arm
                system=composer.PLANNER_SYSTEM if arm=='DIRECT' else analysis_system()
                call=self.dispatcher.call(pre+'-PLAN',[('system',system),('human',json.dumps(email.model_dump(),ensure_ascii=False))],dict(customer=email.model_dump(),stage='PLAN',arm=arm))
                analysis=None;error=None
                try:
                    if arm=='DIRECT':actions=validate_plan(call['raw'],email)
                    else:
                        parsed=parse_outcome(call['raw'],email=email,metadata=call['metadata'])
                        if not parsed['semantic_eligible']:raise ValueError(parsed['error'])
                        analysis=parsed['value'];actions=guided_actions(analysis)
                except (ValueError,TypeError,KeyError,AssertionError) as exc:actions=[];error=str(exc)
                save(self.root/'plans'/(pre+'.json'),dict(actions=actions,analysis=analysis,error=error,call=call))
                runtime_path=self.root/'runtime'/(pre+'.json')
                runtime=read(runtime_path) if runtime_path.exists() else save(runtime_path,execute(email,actions,self.root/'state'/pre/'actions.sqlite3'))
                # A failed planner is preserved; reply has no invented analysis.
                self.reply(pre+'-REPLY',email,composer.chain_messages(email,runtime,analysis),runtime,arm)
    def evaluate(self,identity,email,slots,reverse=False):
        path=self.root/'judgments'/(identity+'.json')
        try:payload,key=judge.blind_pair(email,slots,reverse=reverse)
        except ValueError as exc:
            return save(path,dict(identity=identity,status='NOT_ASSESSABLE_STRUCTURE_OR_IDENTITY',error=str(exc),parsed=None))
        # Key is stored locally only, never included in provider payload.
        save(self.root/'judge-inputs'/(identity+'.json'),dict(payload=payload,key=key))
        call=self.dispatcher.call(identity,[('system',judge.SYSTEM),('human',json.dumps(payload,ensure_ascii=False))],dict(blind_payload=payload))
        try:parsed=judge.parse(call['raw'],payload);error=None
        except (ValueError,TypeError,KeyError,AttributeError) as exc:parsed=None;error=str(exc)
        return save(path,dict(identity=identity,status='PARSED' if parsed else 'JUDGE_STRUCTURE_FAILURE',parsed=parsed,error=error,call=call,key=key))
    def calibration(self):
        for item in self.plan['calibration']:
            email=EmailInput.model_validate(item['email'])
            for suffix in item.get('schedule',['AB','REPEAT','BA']):
                reverse=suffix=='BA'
                self.evaluate('CAL-'+item['id']+'-'+suffix,email,item['slots'],reverse)
        result=calibration_metrics(self.root,self.plan)
        save(self.root/'CALIBRATION_METRICS.json',result)
        return result
    def judgments(self):
        for group in ('A','B'):
            for index,spec in enumerate(self.plan[group]):
                email=EmailInput.model_validate(spec['email']);eid=email.email_id
                arms=spec['order'] if group=='A' else ['DIRECT','GUIDED']
                paths=[self.root/'results'/((group+'-'+eid+'-'+arm+('-REPLY' if group=='B' else ''))+'.json') for arm in arms]
                slots=[read(p)['slot'] for p in paths]
                identity='J-'+group+'-'+eid
                if identity not in self.plan['allowed_call_ids']:continue
                self.evaluate(identity,email,slots)
                if identity+'-BA' in self.plan['allowed_call_ids']:self.evaluate(identity+'-BA',email,slots,True)
                if identity+'-REPEAT' in self.plan['allowed_call_ids']:self.evaluate(identity+'-REPEAT',email,slots)
    def all(self):
        metrics=self.calibration()
        if self.dispatcher.mode=='LIVE' and not metrics['preflight_pass']:
            self.dispatcher.halt('CALIBRATION_FAILED_DEV_NOT_DISPATCHED');return
        self.A();self.B();self.judgments()
        self.dispatcher.halt('R3_DEV_COMPLETED_NO_REUSE')

def unblind(row):
    if not row.get('parsed'):return None
    key=row['key'];return {key[a['slot']]['arm']:a for a in row['parsed']['answers']}
def stability(first,second):
    a,b=unblind(first),unblind(second)
    if not a or not b:return dict(valid=False,numeric_equal=0,numeric_n=0,na_changes=None,hard_sets_equal=None,preference_equal=None)
    equal=n=na=0
    for arm in a:
        for d in judge.DIMENSIONS:
            x,y=a[arm]['scores'][d],b[arm]['scores'][d]
            if type(x)is int and type(y)is int:n+=1;equal+=x==y
            elif x!=y:na+=1
    def hard(z):return {arm:sorted((f['category'],f['quote']) for f in v['findings'] if f['category']=='HARD_ERROR') for arm,v in z.items()}
    def pref(row):return row['key'].get(row['parsed']['preference'],{}).get('arm',row['parsed']['preference'])
    return dict(valid=True,numeric_equal=equal,numeric_n=n,na_changes=na,hard_sets_equal=hard(a)==hard(b),preference_equal=pref(first)==pref(second))
def calibration_metrics(root,plan):
    root=Path(root);checks=[];repeats=[];swaps=[]
    for item in plan['calibration']:
        first=read(root/'judgments'/('CAL-'+item['id']+'-AB.json'))
        rows=[first]
        if 'REPEAT' in item.get('schedule',['AB','REPEAT','BA']):repeats.append(stability(first,read(root/'judgments'/('CAL-'+item['id']+'-REPEAT.json'))))
        if 'BA' in item.get('schedule',['AB','REPEAT','BA']):swaps.append(stability(first,read(root/'judgments'/('CAL-'+item['id']+'-BA.json'))))
        values=unblind(rows[0]);expect=item.get('expectation')
        if expect and values:
            detected=any(f['category']=='HARD_ERROR' and len(f['quote'])>=6 and (expect['quote'] in f['quote'] or f['quote'] in expect['quote']) for f in values['MUTATED']['findings'])
            checks.append(dict(id=item['id'],expected_hard=expect['hard'],detected_hard=detected,correct=detected==expect['hard']))
    def aggregate(rows):
        n=sum(r['numeric_n'] for r in rows);eq=sum(r['numeric_equal'] for r in rows)
        return dict(pairs=len(rows),valid_pairs=sum(r['valid'] for r in rows),numeric_equal=eq,numeric_n=n,ratio=eq/n if n else None,details=rows)
    repeat,swap=aggregate(repeats),aggregate(swaps)
    n_expected=sum(bool(c.get('expectation')) for c in plan['calibration'])
    passed=len(checks)==n_expected and all(c['correct'] for c in checks) and repeat['valid_pairs']==len(repeats) and swap['valid_pairs']==len(swaps) and (repeat['ratio'] or 0)>=.85 and (swap['ratio'] or 0)>=.85 and all(r['hard_sets_equal'] and r['preference_equal'] and r['na_changes']==0 for r in repeats+swaps)
    return dict(identity='DEVELOPMENT_POLICY_CALIBRATION_NOT_HUMAN_AGREEMENT',expected_policy_controls=n_expected,observed_policy_controls=len(checks),policy_correct=sum(c['correct'] for c in checks),policy_checks=checks,repeats=repeat,AB_BA=swap,preflight_pass=passed,human_numeric_n=0,human_agreement=None,kappa=None)

def mock_provider(messages,folder,payload):
    """Explicit fixture outputs, never interpreted as semantic observations."""
    from src.evaluation.p5b8r3_judge import DIMENSIONS
    data=json.loads(messages[1][1]);system=messages[0][1]
    if payload and 'blind_payload' in payload:
        value=dict(answers=[dict(slot=s['slot'],scores={d:2 for d in DIMENSIONS},reasons={d:'OFFLINE MOCK FIXTURE; no semantic evidence' for d in DIMENSIONS},findings=[],action_evidence=[]) for s in data['answers']],preference='TIE')
    elif payload and payload.get('stage')=='PLAN':
        if payload['arm']=='DIRECT':value=dict(actions=[])
        else:
            email=data;quote=email['body'][:12]
            value=dict(version='p5b8-calibration-1',uncertainty=['Explicit offline fixture'],expressed_sentiment='neutral',expressed_evidence=[],experience_polarity='unknown',complaint_intent='uncertain',complaint_evidence=[],urgency='unknown',urgency_evidence=[],mentioned_store=None,issues=[dict(issue_id='I1',object_type='unknown',object_name='fixture',category='unknown',sentiment='neutral',experience_polarity='unknown',issue_kind='inquiry',business_process='unclear',customer_requests=['fixture request'],evidence=[quote],risk='unknown',urgency='unknown',resolution='unknown')])
    else:value=dict(reply='OFFLINE MOCK FIXTURE - 已收到本次测试输入，可进一步核实。')
    raw=json.dumps(value,ensure_ascii=False)
    save(Path(folder)/'mock-provider-response.json',dict(identity='OFFLINE_MOCK_NOT_PROVIDER_HTTP',content=raw))
    return raw,dict(input_tokens=100,output_tokens=100,total_tokens=200,finish_reason='stop',resolved_model='OFFLINE_FIXTURE',provider_response_id='mock-'+digest(messages)[:16])
