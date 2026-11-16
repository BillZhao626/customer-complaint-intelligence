"""Targeted convergence and a one-shot frozen new-family synthetic test.

prepare is free. Live requires a NEW explicit authorization (old grants invalid).
Independent generation begins only after candidate/judge freeze; no test tuning.
"""
import argparse,json,sys,hashlib,copy,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.domain.contracts import EmailInput,digest
from src.infrastructure.p5b8r3_execution import Dispatcher,LangChainProvider,read
from src.application.p5b8r3_experiment import Experiment,save,mock_provider
from src.application.p5b8r3_final_reply import SYSTEM,identity
from src.application.p5b8r3_final_guard import assess
from src.application.p5b8r1_contracts import analysis_system,parse_outcome
from src.application.p5b8r1_actions import guided_actions
from src.application.p5b8_pipeline import validate_plan,execute
from src.application.p5b8r3_reply import PLANNER_SYSTEM,chain_messages,paired_messages
from src.application.p5b8r1_experiment import pair_invariant,MODEL
from src.evaluation import p5b8r3_judge as judge
DOC=ROOT/'docs/p5b8r3';PREP=DOC/'followup-prepared';RUN=ROOT/'.local/p5b8r3/quality-final-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def frozen_sources():
    paths=[Path(__file__)]+list((ROOT/'src').rglob('*.py'))
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths}
def prepared():
    # Each selected baseline is an actual R3 first response, not a best retry.
    cases=['B7-009','B7-036','B7-035','B7-084','B7-085','B7-065'];target=[]
    for eid in cases:
        base=ROOT/'.local/p5b8r3/live-v4/results'/('B-'+eid+'-GUIDED-REPLY.json')
        if not base.exists():base=ROOT/'.local/p5b8r3/live-v4/results'/('A-'+eid+'-ISSUES_WITH_SENTIMENT.json')
        row=read(base);call=ROOT/'.local/p5b8r3/live-v4/calls'/digest(row['identity'])/'frozen-input.json';frozen=read(call)
        messages=copy.deepcopy(frozen['messages']);messages[0]=['system',SYSTEM]
        target.append(dict(case_id=eid,baseline_path=base.relative_to(ROOT).as_posix(),baseline_sha256=sha(base),baseline=row,messages=messages,runtime=row['runtime']))
    ids=[prefix+'-'+s['case_id'] for s in target for prefix in ('T_REPLY','T_JUDGE')]
    for n in range(1,13):
        eid=f'R3N-{n:03}'
        for stage in ('GEN','DIRECT_PLAN','GUIDED_ANALYSIS','DIRECT_REPLY','GUIDED_REPLY','NO_EMOTION','WITH_EMOTION','JUDGE_CHAIN','JUDGE_EMOTION'):ids.append(stage+'-'+eid)
    assert len(ids)==120
    plan=dict(version='p5b8r3-targeted-plus-unseen-1',authorization_scope='P5-B8-R3-FINAL-QUALITY',planned_requests=120,allowed_call_ids=ids,proposed_cny_cap=15,pricing=read(DOC/'prepared-v4/PLAN.json')['pricing'],model=MODEL,target=target,candidate=identity(),judge=dict(version=judge.VERSION,hash=digest(judge.SYSTEM)),sources=frozen_sources(),
       breakdown=dict(targeted_reply=6,targeted_judge=6,independent_synthetic_generation=12,independent_chain_plan_analysis_reply=48,independent_emotion_replies=24,independent_judges=24),
       independent=dict(n=12,families=6,language='one zh and one en per family',identity='NEW_FAMILY_SYNTHETIC_HOLDOUT_NOT_HUMAN_GOLD',content_created=False,family_content_opened=False,generation_after_candidate_judge_freeze=True,source_note='Family names and all samples instantiated only after freeze. Generator intent is not Gold. Source is same Provider, independent of DEV outputs but not independent human evaluation.',tuning_allowed=False,post_test_rule='Any later tuning with these samples requires an explicit DEV exposure overlay and a new independent set.'),
       hypothesis='Misreading normative task requests as execution permission and unsupported callback promises. Same frozen facts/receipts/model/human payload; change shared composer only. General task-noun scoping remains evidence checked.',selection='Final candidate predeclared version2; no best-of retries, no automatic production promotion; weaknesses are reported even if it loses.',human_numeric_n=0)
    PREP.mkdir(parents=True,exist_ok=True);save(PREP/'PLAN.json',plan)
    save(PREP/'CONFIG.json',dict(reply_system=SYSTEM,judge_system=judge.SYSTEM))
    print(json.dumps(dict(plan_hash=digest(plan),requests=120,cny_cap_proposed=15,authorized=False,target_cases=cases,independent=plan['independent'])))
def verify(plan):
    if any(sha(ROOT/p)!=h for p,h in plan['sources'].items()):raise ValueError('Frozen source drift')
    for s in plan['target']:
        if sha(ROOT/s['baseline_path'])!=s['baseline_sha256']:raise ValueError('Baseline first response drift')
def set_system(messages):return [('system',SYSTEM),messages[1]]
def corpus_grams(text):
    text=re.sub(r'\s+',' ',text.lower());return {text[i:i+4] for i in range(max(0,len(text)-3))}
def novelty(email):
    grams=corpus_grams(email.body);matches=[]
    for directory in (ROOT/'.local/p5b7/dataset',ROOT/'.local/p5b8/new-dataset'):
        for path in directory.glob('*.json'):
            d=read(path);other=corpus_grams(d.get('body',''));similar=len(grams&other)/max(1,len(grams|other))
            if similar>=.8:matches.append(dict(path=path.relative_to(ROOT).as_posix(),jaccard=similar))
    return dict(threshold=.8,near_duplicates=matches,identity='LEXICAL_SCREEN_NOT_PROOF_OF_SEMANTIC_INDEPENDENCE')
def run(dispatcher,plan):
    exp=Experiment(RUN,dispatcher,PREP)
    for s in plan['target']:
        email=EmailInput.model_validate(s['baseline']['customer'])
        new=exp.reply('T_REPLY-'+s['case_id'],email,s['messages'],s['runtime'],'CANDIDATE_V2')
        exp.evaluate('T_JUDGE-'+s['case_id'],email,[s['baseline']['slot'],new['slot']])
    # A loss does not change the predeclared candidate or remove its bad cases.
    freeze=dict(candidate=identity(),judge=plan['judge'],model=MODEL,sources=plan['sources'],plan_hash=digest(plan),selection='PREDECLARED_EXPERIMENTAL_CANDIDATE_NOT_CHAMPION_PROMOTION',test_samples_opened=0,tuning_after_test=False)
    save(RUN/'FINAL_CANDIDATE_AND_JUDGE_FREEZE.json',freeze)
    # Instantiate wholly new family content after the above freeze, not before.
    families=[('marketing-consent-removal','A request to stop optional marketing while keeping necessary order notices; no claim about a law or deadline.'),
      ('account-data-export-scope','A request for a copy of the customer account history with a question about which fields are included; no actual personal information.'),
      ('device-recycling-data-erasure','A question about data-erasure verification before recycling an old device; no physical fault, refund or delivery issue.'),
      ('accessible-digital-instructions','A request for a screen-reader-friendly digital manual and a question about format availability; no physical store access issue.'),
      ('gift-recipient-information-privacy','A request to avoid disclosing a gift purchase price to its recipient while retaining the purchaser receipt; no delivery-delay or refund issue.'),
      ('software-license-seat-transfer','A question about moving a purchased software license from an old device to a new one without assuming transfer terms or claiming a billing error.')]
    specifications=[dict(case_id=f'R3N-{i*2+j+1:03}',family=fam,language=lang,situation=situation) for i,(fam,situation) in enumerate(families) for j,lang in enumerate(('zh','en'))]
    save(RUN/'INDEPENDENT_PROTOCOL_AFTER_FREEZE.json',dict(freeze_hash=digest(freeze),specifications=specifications,identity=plan['independent'],candidate_frozen_before_generation=True))
    for spec in specifications:
        eid=spec['case_id'];messages=[('system','Generate one natural fictional customer-service email in the requested language. JSON only {"subject":"...","body":"..."}. No analysis labels, case IDs, real personal information or unsupported merchant promises. Stay in the specified new semantic family, not product faults, delivery delays, refunds, store praise or invoice disputes. Include a concrete request and plausible context. This is not a reference answer or Gold.'),('human',json.dumps(dict(language=spec['language'],situation=spec['situation']),ensure_ascii=False))]
        call=dispatcher.call('GEN-'+eid,messages,dict(role='INDEPENDENT_GENERATION_AFTER_FREEZE'))
        try:
            d=json.loads(call['raw'])
            if set(d)!={'subject','body'} or not all(isinstance(v,str) and v.strip() for v in d.values()):raise ValueError('Invalid generated mail')
            email=EmailInput(email_id=eid,**d);screen=novelty(email)
            for previous in (RUN/'dataset').glob('*.json'):
                old=read(previous)
                if old.get('email') and old['email']['body']==email.body:screen['near_duplicates'].append(dict(path=str(previous),exact=True))
            record=dict(spec=spec,email=email.model_dump(),input_hash=email.input_hash,source='LLM_SYNTHETIC',role='INDEPENDENT_TEST_UNSEEN_AT_FREEZE',used_for_tuning=False,first_call=call,novelty_screen=screen,status='EXCLUDED_NEAR_DUPLICATE_NO_REPLACEMENT' if screen['near_duplicates'] else 'FROZEN_TEST_SAMPLE')
        except (ValueError,TypeError,KeyError) as exc:record=dict(spec=spec,email=None,source='LLM_SYNTHETIC',role='INDEPENDENT_GENERATION_FAILURE_NO_REPLACEMENT',first_call=call,error=str(exc))
        save(RUN/'dataset'/(eid+'.json'),record)
    for spec in specifications:
        verify(plan);record=read(RUN/'dataset'/(spec['case_id']+'.json'));eid=spec['case_id']
        if record.get('status')!='FROZEN_TEST_SAMPLE':continue
        email=EmailInput.model_validate(record['email']);answers={};analysis=None;guided_runtime=None
        for arm in ('DIRECT','GUIDED'):
            stage='DIRECT_PLAN' if arm=='DIRECT' else 'GUIDED_ANALYSIS';system=PLANNER_SYSTEM if arm=='DIRECT' else analysis_system()
            call=dispatcher.call(stage+'-'+eid,[('system',system),('human',json.dumps(email.model_dump(),ensure_ascii=False))],dict(customer=email.model_dump(),stage='PLAN',arm=arm))
            error=None
            try:
                if arm=='DIRECT':actions=validate_plan(call['raw'],email)
                else:
                    outcome=parse_outcome(call['raw'],email=email,metadata=call['metadata'])
                    if not outcome['semantic_eligible']:raise ValueError(outcome['error'])
                    analysis=outcome['value'];actions=guided_actions(analysis)
            except (ValueError,TypeError,KeyError,AssertionError) as exc:actions=[];error=str(exc)
            save(RUN/'plans'/(eid+'-'+arm+'.json'),dict(call=call,analysis=analysis if arm=='GUIDED' else None,actions=actions,error=error))
            rt_path=RUN/'runtime'/(eid+'-'+arm+'.json');runtime=read(rt_path) if rt_path.exists() else save(rt_path,execute(email,actions,RUN/'state'/eid/arm/'actions.sqlite3'))
            answers[arm]=exp.reply(arm+'_REPLY-'+eid,email,set_system(chain_messages(email,runtime,analysis if arm=='GUIDED' else None)),runtime,arm)
            if arm=='GUIDED':guided_runtime=runtime
        exp.evaluate('JUDGE_CHAIN-'+eid,email,[answers[a]['slot'] for a in ('DIRECT','GUIDED')])
        if analysis:
            m={k:set_system(v) for k,v in paired_messages(email,analysis,guided_runtime).items()};pair_invariant(m);emo=[]
            for arm,stage in (('ISSUES_NO_SENTIMENT','NO_EMOTION'),('ISSUES_WITH_SENTIMENT','WITH_EMOTION')):emo.append(exp.reply(stage+'-'+eid,email,m[arm],guided_runtime,arm))
            exp.evaluate('JUDGE_EMOTION-'+eid,email,[r['slot'] for r in emo])
        else:save(RUN/'emotion-skipped'/(eid+'.json'),dict(status='ANALYSIS_FAILURE_NO_FAKE_EMOTION',role='INDEPENDENT_TEST_UNKNOWN',input_hash=email.input_hash))
    save(RUN/'DATA_IDENTITY.json',dict(role='INDEPENDENT_NEW_SEMANTIC_FAMILY_SYNTHETIC_TEST',candidate_frozen_before_generation=True,used_for_tuning=False,n_planned=12,n_generated=sum(read(p).get('email') is not None for p in (RUN/'dataset').glob('*.json')),not_human_gold=True,semantic_family_novelty='Intended new six families plus lexical screen; requires manual semantic audit, not proven by renaming. No post-test candidate tuning.'))
    dispatcher.halt('FINAL_QUALITY_SCOPE_COMPLETED_NO_REUSE')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','live']);parser.add_argument('--authorization',type=Path);args=parser.parse_args()
    if args.action=='prepare':prepared();return
    plan=read(PREP/'PLAN.json');verify(plan)
    if not args.authorization:raise PermissionError('NEW_AUTHORIZATION_REQUIRED: CNY15 / up to120 Provider requests, no use of prior grant')
    d=Dispatcher(RUN,plan,authorization=read(args.authorization),mode='LIVE');d.provider=LangChainProvider();run(d,plan);print(json.dumps(d.summary()))
if __name__=='__main__':main()
