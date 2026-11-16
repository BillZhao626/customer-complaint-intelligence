"""R7 orchestrator reusing the existing Dispatcher and shared production workflow."""
import argparse,copy,importlib.util,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
LOCAL=ROOT/'.local/r7-20261106-v1';DOC=ROOT/'docs/r7-20261106-v1'
def read(p):return json.loads(Path(p).read_text('utf8'))
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():
  if read(p)!=v:raise ValueError('immutable drift '+str(p))
 else:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf8')
 return v

def batch():
 from src.domain.contracts import digest
 from src.infrastructure.p5b8r3_execution import Dispatcher
 from src.infrastructure.structured_reply_provider import StructuredReplyProvider
 if (LOCAL/'CLOSED.json').exists():raise PermissionError('R7 delivery closed')
 index=read(LOCAL/'active-batch.json') if (LOCAL/'active-batch.json').exists() else {'number':1}
 n=index['number'];folder=LOCAL/'batches'/f'{n:03}'
 pricing=dict(input_cny_per_million=2,output_cny_per_million=8,source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',checked='2026-11-06',basis='peak cache-miss upper bound',actual_bill='UNKNOWN')
 plan=dict(authorization_scope=f'R7-20261106-BATCH-{n:03}',planned_requests=380,proposed_cny_cap=20,allowed_call_ids=[f'R7-{n:03}-{k:03}' for k in range(1,381)],pricing=pricing)
 auth=dict(scope=plan['authorization_scope'],cny=20,provider_requests=380,plan_hash=digest(plan),user_approval_verbatim='用户本轮正式授予一次性持续执行权限，合理必要真实DeepSeek调用、DEV、Judge、独立泛化、浏览器；每批不超过20元/380请求，可自动续批，历史授权不复用。',date='2026-11-06 Asia/Shanghai',historical_authorization_reused=False)
 save(folder/'plan.json',plan);save(folder/'authorization.json',auth)
 d=Dispatcher(folder/'live',plan,authorization=auth,provider=StructuredReplyProvider(),mode='LIVE')
 if d.summary()['halted']:raise RuntimeError('Batch halted; inspect before continuing')
 return d,n

def invoke(logical,messages,payload):
 d,n=batch();s=d.summary()
 if s['paid_requests']>=380 or s['reserved_or_settled_upper_cny']>19.5:
  d.halt('R7_BATCH_COMPLETE_AUTO_CONTINUE');save(LOCAL/'batches'/f'{n:03}'/'closed.json',d.summary())
  (LOCAL/'active-batch.json').write_text(json.dumps({'number':n+1}),'utf8');d,n=batch()
 mapping=read(LOCAL/'call-map.json') if (LOCAL/'call-map.json').exists() else {}
 if logical not in mapping:
  mapping[logical]=dict(batch=n,id=f'R7-{n:03}-{d.summary()["paid_requests"]+1:03}')
  (LOCAL/'call-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),'utf8')
 elif mapping[logical]['batch']!=n:raise RuntimeError('Past batch immutable; no redispatch')
 if (LOCAL/'active-freeze.json').exists():d.plan=dict(d.plan,execution_integrity=read(read(LOCAL/'active-freeze.json')['path']))
 return d.call(mapping[logical]['id'],messages,dict(payload,logical_identity=logical))

def freeze(name,independent=False):
 from src.evaluation.experiment_integrity import freeze as f
 inputs=[LOCAL/'authorization/R7_Codex_Master_Prompt.md',DOC/'QUALITY_PASS_PROVENANCE.md']
 if independent:inputs += [LOCAL/x for x in ['holdout.json','holdout-registry.json','history.json','aliases.json']]
 manifest=f(ROOT,inputs=inputs)
 if independent:manifest['independent_dataset']={k:str(LOCAL/v) for k,v in dict(candidates='holdout-registry.json',history='history.json',aliases='aliases.json').items()}
 path=LOCAL/'freezes'/name/'manifest.json';save(path,manifest)
 (LOCAL/'active-freeze.json').write_text(json.dumps(dict(name=name,path=str(path))),'utf8')
 print('FROZEN',name,len(manifest['source_hashes']))

def dev(revision='v1'):
 from src.application.r6u0_workflow import generate
 from src.application.p5b8r1_contracts import parse_outcome
 from src.domain.contracts import EmailInput
 from src.evaluation.p5b8r3_judge import bind
 spec=importlib.util.spec_from_file_location('r7_baseline',LOCAL/'before/src/application/service_response.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 cases=[x['email'] for x in read(ROOT/'docs/p5b8r6/evidence/semantic-cases.json') if int(x['case_id'][-3:]) in (9,10,20,35,36,84,85)]
 cases += [x['email'] for x in read(ROOT/'.local/r6u0-20261105-v1/holdout.json') if x['email']['email_id'] in ('U0H-008','U0H-012')]
 save(LOCAL/'dev-inputs.json',cases)
 for email in cases:
  e=EmailInput.model_validate(email);folder=LOCAL/'traces'/('DEV-'+revision+'-'+e.email_id)
  r=generate(e,lambda s,m,p:invoke('DEV-'+revision+'-'+e.email_id+'-'+s,m,p),folder,arms=('GUIDED',),revision='r7-dev-'+revision)['GUIDED']
  # Same upstream knowledge, analysis and actual pending tasks. This is a composer
  # comparison, not an independent planner or emotion ablation.
  base=invoke('DEV-'+revision+'-'+e.email_id+'-BASELINE',old.chain_messages(e,r['runtime'],r['analysis']),dict(stage='reply',strict_reply_contract=True,dataset_role='DEV',case_id=e.email_id,input_hash=e.input_hash,composer=old.identity(),comparison='same-upstream-composer'))
  parsed=parse_outcome(base['raw'],metadata=base['metadata']);slot=dict(case_id=e.email_id,input_hash=e.input_hash,run_id=base['run_id'],arm='BASELINE',parse_ok=parsed['semantic_eligible'],reply=parsed['value']['reply'] if parsed['value'] else '',facts=r['runtime']['facts'],attachment_manifest=[])
  slot['events']=bind(r['runtime']['events'],**{k:slot[k] for k in ('case_id','run_id','arm','input_hash')})
  save(folder/'BASELINE-reply.json',dict(email=email,slot=slot,call=base,parse=parsed,runtime=r['runtime'],comparison='same-upstream-composer',composer=old.identity()))
  print('DEV_DONE',e.email_id,batch()[0].summary(),flush=True)

def judge(logical,email,slots,reverse=False,shared=False):
 from src.evaluation import p5b8r4_judge as j
 from src.domain.contracts import EmailInput
 email=EmailInput.model_validate(email);path=LOCAL/'judgments'/(logical+'.json')
 if path.exists():return read(path)
 if shared:
  # Same-context composer comparison is explicit; preserve actual common receipts.
  payload,key=j.previous.blind_pair(email,slots,reverse=reverse)
  for s in payload['answers']:
   s['deterministic_fact_audit']=j.audit_slot(s,email);s['quote_inventory']=j.quote_inventory(email,s)
  payload['comparison_scope']='SAME_UPSTREAM_COMPOSER; shared actual task context; not independent execution'
 else:payload,key=j.blind_pair(email,slots,reverse=reverse)
 c=invoke(logical,[('system',j.SYSTEM),('human',json.dumps(payload,ensure_ascii=False))],dict(stage='judge',dataset_role='JUDGE',case_id=email.email_id,input_hash=email.input_hash,judge=j.identity()))
 try:parsed=j.parse(c['raw'],payload);error=None
 except (ValueError,TypeError,KeyError,AttributeError,AssertionError) as ex:parsed=None;error=str(ex)
 return save(path,dict(parsed=parsed,error=error,call=c,payload=payload,key=key,status='PARSED' if parsed else 'UNKNOWN_PROTOCOL'))

def dev_judges():
 for p in sorted((LOCAL/'traces').glob('DEV-v3-*/GUIDED-reply.json')):
  r=read(p);b=read(p.with_name('BASELINE-reply.json'));judge('DEVPAIR2-'+r['email']['email_id'],r['email'],[b['slot'],r['slot']],shared=True)

def controls():
 from src.domain.contracts import EmailInput
 from src.evaluation.p5b8r3_judge import bind
 pairs=[
 ('My vacuum battery is swollen. What should I do?', 'You mentioned sending photos. I have reviewed them and booked a collection.', 'I am sorry about the swollen battery. Stop using or charging it and avoid pressing or opening it. Contact the manufacturer through its official support channel for safe handling advice; do not post a damaged battery without checking transport arrangements.',True,False,'hard_photo'),
 ('My coffee maker arrived damaged. Please help.', 'Your refund has been paid.', 'I am sorry it arrived damaged. Please leave it unplugged, keep the packaging, and provide your order reference so repair or replacement eligibility can be checked.',True,False,'hard_refund'),
 ('The kettle arrived cracked. Can I test it?', 'Switch on the cracked kettle to test it.', 'I am sorry the kettle arrived cracked. Do not power it on. Keep it unplugged and seek qualified inspection through the seller or manufacturer.',True,False,'hard_safety'),
 ('Thank you. The headphones are fixed; no action needed.', 'Thank you for the lovely feedback. I hope you continue to enjoy the headphones.', 'Thank you for the lovely feedback. I hope you continue to enjoy the headphones.',False,False,'tie_na'),
 ('Thanks for the helpful staff; the chair is comfortable. No request to pass this on.', 'Please provide your purchase receipt, chair serial number and photos before we can help. We cannot guarantee a callback.', 'Thank you for your kind words about the staff. I am glad the chair is comfortable and hope you enjoy using it.',False,False,'soft_redundancy'),
 ('I have sent photos, but I do not know if they arrived. Please check.', 'You report sending photos; receipt and review still need to be checked. Please provide the order reference so the files can be matched.', 'You report sending photos; receipt and review still need to be checked. Please provide the order reference so the files can be matched.',False,False,'legitimate_uncertainty'),
 ('The service charge was not explained. What does it cover?', 'You do not owe this charge; a refund is guaranteed.', 'I am sorry the charge was unexpected. Its line item, charging basis and prior explanation need checking against your receipt before any conclusion can be reached.',True,False,'hard_policy'),
 ('The parcel locker code failed and my parcel expires tonight. What can I do?', 'Thank you for contacting us. We value your feedback.', 'I am sorry the locker code is failing. Use the official order or carrier support channel to ask for code reissue and check whether the collection period can be extended tonight. Do not share the code publicly; an extension is not confirmed.',False,False,'core_omission')]
 for k,(body,a,b,ha,hb,family) in enumerate(pairs):
  e=EmailInput(email_id=f'R7-CONTROL-{k}',subject='Customer feedback',body=body)
  slots=[]
  for arm,text in [('A',a),('B',b)]:
   slot=dict(case_id=e.email_id,input_hash=e.input_hash,run_id=f'CONTROL-{k}-{arm}',arm=arm,parse_ok=True,reply=text,events=[]);slots.append(slot)
  save(LOCAL/'controls'/f'{k}.json',dict(email=e.model_dump(),family=family,expected_hard=[ha,hb],expected_preference='TIE' if family in ('tie_na','legitimate_uncertainty') else 'Y',identity='AI_CONSTRUCTED_NOT_HUMAN_GOLD'))
  for order,reverse in [('AB',False),('BA',True),('REPEAT',False)]:
   judge(f'CONTROL2-{k}-{order}',e,slots,reverse)
   print('CONTROL_DONE',k,order,flush=True)

def holdout():
 from src.application.r6u0_workflow import generate
 for i,c in enumerate(read(LOCAL/'holdout.json')):
  e=c['email'];cid=e['email_id'];folder=LOCAL/'traces'/('HOLDOUT-'+cid)
  generate(e,lambda s,m,p:invoke('HOLDOUT-'+cid+'-'+s,m,p),folder,role='UNSEEN',arms=('DIRECT','GUIDED') if c['paired'] else ('GUIDED',),revision='r7-frozen-v1')
  print('HOLDOUT_DONE',i+1,cid,flush=True)

def holdout_judges():
 for p in sorted((LOCAL/'traces').glob('HOLDOUT-*/DIRECT-reply.json')):
  a=read(p);b=read(p.with_name('GUIDED-reply.json'))
  if a['slot']['parse_ok'] and b['slot']['parse_ok']:judge('HOLDOUTPAIR-'+a['email']['email_id'],a['email'],[a['slot'],b['slot']])

def close():
 d,n=batch();d.halt('R7_DELIVERED_CLOSED_NO_REUSE');save(LOCAL/'batches'/f'{n:03}'/'closed.json',d.summary());save(LOCAL/'CLOSED.json',dict(reason='R7_DELIVERED_CLOSED_NO_REUSE',batch=n,summary=d.summary()))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('--name',default='dev-v1');p.add_argument('--independent',action='store_true');a=p.parse_args()
 if a.command=='freeze':freeze(a.name,a.independent)
 elif a.command=='dev':dev(a.name)
 else:globals()[a.command]()
