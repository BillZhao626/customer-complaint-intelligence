"""Local, immutable historical replay harness; no provider import or dispatch path."""
from pathlib import Path
from datetime import datetime, timezone
from hashlib import sha256
import csv, json, os, platform, subprocess
from src.domain.contracts import EmailInput, digest
from src.domain.analysis_v32 import AnalysisV32, adapt, validate, wire_schema
from src.application.live_execution import strict_json
from src.application.p5b4_guard import inspect, lexical, receipts
from src.application.product_quality import inspect as old_product
from src.application.research_policy_v2 import requested_language, language

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'p5b4-replay-grader-1'
SOURCES = ['src/evaluation/p5b4.py','src/application/p5b4_guard.py','src/domain/analysis_v32.py','src/application/reply_review.py','src/application/product_quality.py','src/application/urgency_context_v2.py']

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def hashfile(p): return sha256(Path(p).read_bytes()).hexdigest()
def write(p, value):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf-8') as f:
        f.write(value if isinstance(value,str) else json.dumps(value, ensure_ascii=False, indent=2))
def now(): return datetime.now(timezone.utc).isoformat()

def source_pairs():
    """All sources already exposed; preserve first raw even when rejected."""
    manifest=read(ROOT/'docs/p5b_dev_pilot/pilot_manifest_16.json')
    pairs=[]
    for c in manifest['cases']:
        for n,t in enumerate(c['turns'],1):
            turn_id=next(s['turn_id'] for s in manifest['schedule'] if s['calibration_id']==c['calibration_id'] and s['turn']==n)
            pairs.append(dict(case_id=f'{c["calibration_id"]}-T{n}', family_id=c.get('source_id','legacy'), thread_id=c['calibration_id'], turn_index=n, current=t, b2_path=f'docs/p5b2/evidence/formal/{turn_id}/run.json', b3_stage='regression', fixture=[], source_manifest='docs/p5b_dev_pilot/pilot_manifest_16.json'))
    for c in read(ROOT/'docs/p5b3/dataset-manifest.json')['cases']:
        if c['split']!='test': continue
        for n,t in enumerate(c['turns'],1):
            pairs.append(dict(case_id=f'{c["case_id"]}-T{n}', family_id=c['family'], thread_id=c['case_id'], turn_index=n, current=t, b2_path=None, b3_stage='test', fixture=c['scoped_facts'], source_manifest='docs/p5b3/dataset-manifest.json'))
    for pair in pairs:
        for arm,stage in [('b2','paired-b2'),('b3',pair['b3_stage'])]:
            if pair.get(arm+'_path'): p=ROOT/pair[arm+'_path']
            else:
                found=[p for p in (ROOT/'.local/p5b3-20261029-v1'/stage).glob('*/run.json') if read(p)['email']['email_id']==pair['case_id']]
                if len(found)!=1: raise ValueError('Missing/duplicate history: '+pair['case_id']+'/'+arm)
                p=found[0]
            if not p.is_file(): raise ValueError('Missing source '+str(p))
            pair[arm+'_path']=p.relative_to(ROOT).as_posix()
            pair[arm+'_sha256']=hashfile(p)
            pair[arm+'_raw_sha256']=sha256(read(p)['attempts'][0]['raw_output'].encode()).hexdigest()
        pair['current_hash']=digest(pair['current'])
        pair['fixture_hash']=digest(pair['fixture'])
        pair['split']='DEV_EXPOSED_REPLAY'
        pair['reference_requirements']=['逐一回应当前客户要求；客户自述不升级为已核实事实','已有资料不重复索取；无执行凭据不声称完成','匹配当前来信语言；风险不降级；未知规格待核实']
        pair['reference_actions']='GOLD_CANDIDATE_PENDING_HUMAN'
    return pairs

def freeze_config():
    pairs=source_pairs()
    return dict(version='p5b4-config-v1', mode='historical_raw_replay', authorized_new_api_budget_rmb=0, max_provider_calls=0, max_iterations=8, stop_no_improvement=3, dataset_hash=digest(pairs), cases=pairs, source_hashes={p:hashfile(ROOT/p) for p in SOURCES}, schema_hash=digest(wire_schema()), grader_version=VERSION, model='historical deepseek-flash; weight snapshot unavailable', semantic_status='SEMANTIC_PROVISIONAL', holdout_status='NONE_ALL_EXPOSED', policies=[dict(id='H1',event_guard=True),dict(id='H2',event_guard=True,safety_synonyms=True),dict(id='H3',event_guard=True,safety_synonyms=True,attachment_guard=True)])

def preflight(config):
    if config['mode']!='historical_raw_replay' or config['authorized_new_api_budget_rmb']!=0 or config['max_provider_calls']!=0: raise ValueError('Only zero-budget replay is implemented')
    if not 1<=config['max_iterations']<=8 or config['stop_no_improvement']!=3: raise ValueError('Invalid iteration cap')
    if len(config['policies'])>config['max_iterations']: raise ValueError('Too many hypotheses')
    if digest(config['cases'])!=config['dataset_hash'] or digest(wire_schema())!=config['schema_hash']: raise ValueError('Dataset/schema drift')
    for p,h in config['source_hashes'].items():
        if hashfile(ROOT/p)!=h: raise ValueError('Grader/source drift: '+p)
    seen=set(); checks=[]
    for case in config['cases']:
        if case['case_id'] in seen: raise ValueError('Duplicate case')
        seen.add(case['case_id'])
        if case['split']!='DEV_EXPOSED_REPLAY' or digest(case['current'])!=case['current_hash'] or digest(case['fixture'])!=case['fixture_hash']: raise ValueError('Case binding drift')
        ids=[]
        for arm in ('b2','b3'):
            p=ROOT/case[arm+'_path']
            if hashfile(p)!=case[arm+'_sha256']: raise ValueError('Historical run drift')
            r=read(p); email=EmailInput.model_validate(r['email']); a=r['attempts'][0]
            if email.input_hash!=r['input_hash'] or sha256(a['raw_output'].encode()).hexdigest()!=case[arm+'_raw_sha256']: raise ValueError('Input/raw drift')
            if not r['created_at'] or not r['config'].get('prompt_hash') or not r['run_id']: raise ValueError('Missing provenance')
            # Continuations have arm-specific assistant history; current facts must match exactly.
            current=email.body.rsplit('[customer · current message]\n',1)[-1]
            if '[customer · current message]\n' in email.body:
                current=current.removeprefix(case['current']['subject']+'\n')
            if current!=case['current']['body']: raise ValueError('Current input mismatch: '+case['case_id']+'/'+arm)
            provider=read(p.parent/'provider-response.txt')
            if provider['choices'][0]['message']['content']!=a['raw_output']: raise ValueError('Provider first raw mismatch')
            frozen=p.parent/'frozen-input.json'
            if frozen.exists():
                f=read(frozen)
                if digest(f['email'])!=digest(r['email']): raise ValueError('Frozen input mismatch')
                runtime=f.get('trusted_runtime',{})
                if runtime and digest(runtime)!=r['config']['parameters'].get('runtime_context_hash'): raise ValueError('Runtime fixture mismatch')
                journal=ROOT/'.local/p4/p5b3-20261029-v1/experiment-product-actions.sqlite3'
                valid={x['task_id']:x for x in receipts(journal,email.input_hash)}
                for task in runtime.get('action_results',[]):
                    if task['task_id'] not in valid or valid[task['task_id']]['event_id']!=task['event_id'] or valid[task['task_id']]['decision']!=task['decision']: raise ValueError('Unverified task receipt')
            elif arm=='b3': raise ValueError('Missing frozen B3 fixture')
            ids.append(dict(arm=arm,run_id=r['run_id'],generated_at=r['created_at'],model=r['config']['model_id'],prompt_hash=r['config']['prompt_hash'],input_hash=email.input_hash,source_path=case[arm+'_path'],run_hash=case[arm+'_sha256'],provider_hash=hashfile(p.parent/'provider-response.txt'),fixture_hash=case['fixture_hash']))
        checks.append(dict(case_id=case['case_id'],checks='PASS',reference_state='GOLD_CANDIDATE',runs=ids))
    return dict(status='ENGINEERING_PREFLIGHT_PASS',n=len(checks),cases=checks,grader_version=VERSION,grader_hash=digest(config['source_hashes']))

def grade(case, arm, policy, journal_path=None):
    r=read(ROOT/case[arm+'_path']); email=EmailInput.model_validate(r['email']); a=r['attempts'][0]
    data=strict_json(a['raw_output']); structured=True; errors=[]
    inspected_data=data
    try: inspected_data=AnalysisV32.model_validate(adapt(data)[0]).validate_input(email).model_dump()
    except ValueError as exc: structured=False; errors.append(str(exc))
    legacy=True
    try: validate(data,email)
    except ValueError: legacy=False
    if legacy != (r['status']=='succeeded'): raise ValueError('Historical contract replay drift')
    old=old_product(email,inspected_data if legacy else data,accepted=legacy)
    guard=inspect(email,inspected_data,structured_ok=structured,journal_path=journal_path,**policy)
    actual_fixture_hash=digest(dict(knowledge=case['fixture'] if arm=='b3' else [],actions=sorted([t['decision'] for t in guard['receipts']],key=digest)))
    reply=data.get('suggested_reply',''); current=case['current']['body']; want=requested_language(current)
    lex=lexical(reply,guard['receipts'],event_guard=policy.get('event_guard',False))
    return dict(case_id=case['case_id'],arm=arm,run_id=r['run_id'],source_path=case[arm+'_path'],input_hash=email.input_hash,raw_hash=case[arm+'_raw_sha256'],actual_fixture_hash=actual_fixture_hash,provider_first=a.get('metadata',{}).get('dispatch')=='response_received',json_first=True,structure_input_pass=structured,legacy_contract_first=legacy,revised_contract_gate=structured and not lex, revised_contract_review=structured and not any(f['severity']=='block' for f in lex),product_gate_pass=guard['status']!='blocked',legacy_product_gate_pass=old['status']!='blocked',expected_language=want,language_match=language(reply)==want if want in ('zh','en') else None,english=want=='en',errors=errors,findings=guard['findings'],receipts=guard['receipts'],semantic_status='SEMANTIC_PROVISIONAL',semantic_gold_pass=None,reply_grounding=None,action_correctness=None,high_severity_errors=None,live_e2e_ready=None,elapsed_ms=a.get('elapsed_ms'),tokens=a.get('metadata',{}).get('total_tokens'),human_approved=False)

def summary(rows, *, legacy=False):
    n=len(rows); en=[r for r in rows if r['english']]
    return dict(n=n,provider_first=sum(r['provider_first'] for r in rows),json_first=sum(r['json_first'] for r in rows),structure_input_pass=sum(r['structure_input_pass'] for r in rows),contract_first_pass=sum(r['legacy_contract_first'] if legacy else r['revised_contract_review'] for r in rows),legacy_contract_first=sum(r['legacy_contract_first'] for r in rows),product_gate_pass=sum(r['legacy_product_gate_pass'] if legacy else r['product_gate_pass'] for r in rows),english_correct=sum(r['language_match'] is True for r in en),english_n=len(en),semantic_gold_pass=None,reply_grounding=None,action_correctness=None,high_severity_errors=None,human_status='SEMANTIC_PROVISIONAL',new_provider_calls=0,new_cost_rmb=0,promoted=False)

def paired(left,right, *, legacy_left=False):
    result=[]
    for a,b in zip(left,right,strict=True):
        if a['case_id']!=b['case_id']: raise ValueError('Unpaired IDs')
        av=a['legacy_product_gate_pass'] if legacy_left else a['product_gate_pass']; bv=b['product_gate_pass']
        result.append(dict(case_id=a['case_id'],outcome='tie' if av==bv else 'win' if bv else 'loss',baseline_ready=av,candidate_ready=bv,baseline_run_id=a['run_id'],candidate_run_id=b['run_id'],baseline_findings=a['findings'],candidate_findings=b['findings']))
    return result

def calibration(human, judge):
    """No human labels => unavailable. Disputes/abstentions never become fail."""
    counts=dict(total=len(human),matched=0,false_positive=0,false_negative=0,judge_abstained=0,needs_human_review=0,eligible=0)
    for key, val in human.items():
        pred=judge.get(key)
        if val not in ('PASS','FAIL'): counts['needs_human_review']+=1; continue
        if pred not in ('PASS','FAIL'): counts['judge_abstained']+=1; continue
        counts['eligible']+=1
        if val==pred: counts['matched']+=1
        elif pred=='FAIL': counts['false_positive']+=1
        else: counts['false_negative']+=1
    counts['agreement']=counts['matched']/counts['eligible'] if counts['eligible'] else None
    return counts

def loop(config, out):
    pf=preflight(config);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    write(out/'preflight.json',pf)
    manifest=dict(run_id=out.name,created_at=now(),config_hash=digest(config),dataset_hash=config['dataset_hash'],grader_hash=pf['grader_hash'],schema_hash=config['schema_hash'],commit_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),source_hashes=config['source_hashes'],environment=dict(python=platform.python_version(),platform=platform.platform()),mode='HISTORICAL_RAW_REPLAY_NO_GENERATION',budget=dict(authorized_rmb=0,calls=0,spent_rmb=0),comparison='SYSTEM_PAIRED_REPLAY; each arm retains its own assistant history and fixtures')
    write(out/'run_manifest.json',manifest)
    empty={}; journal=ROOT/'.local/p4/p5b3-20261029-v1/experiment-product-actions.sqlite3'
    b2=[grade(c,'b2',empty) for c in config['cases']]
    b3=[grade(c,'b3',empty,journal) for c in config['cases']]
    write(out/'b2.json',b2);write(out/'b3-legacy.json',b3)
    # Controlled actions ablation: genuinely create in a new local journal, never old DB.
    from src.application.p5b3_actions import TaskJournal
    action_db=TaskJournal(out/'b2-local-actions.sqlite3')
    for c in config['cases']: action_db.prepare(EmailInput.model_validate(read(ROOT/c['b2_path'])['email']))
    actions=[grade(c,'b2',empty,action_db.path) for c in config['cases']]
    write(out/'b2-actions.json',actions)
    best=b3; best_policy={}; history=[]; stagnant=0
    for index,p in enumerate(config['policies'][:config['max_iterations']],1):
        policy={k:v for k,v in p.items() if k!='id'}
        candidate=[grade(c,'b3',policy,journal) for c in config['cases']]
        diff=paired(best,candidate)
        wins=sum(r['outcome']=='win' for r in diff);losses=sum(r['outcome']=='loss' for r in diff)
        # Safety hardening is useful even if fewer drafts are eligible. Never optimize approval count alone.
        new_attachment=sum(any(f['code']=='attachment_receipt_without_manifest' for f in r['findings']) for r in candidate)
        safe_gain=new_attachment>sum(any(f['code']=='attachment_receipt_without_manifest' for f in r['findings']) for r in best)
        accepted=(wins>losses and losses==0) or safe_gain
        stagnant=0 if accepted else stagnant+1
        record=dict(iteration=index,hypothesis=p['id'],policy=policy,summary=summary(candidate),wins=wins,losses=losses,ties=len(diff)-wins-losses,selected_for_dev=accepted,selection_reason='new receipt/stop-use evidence or attachment hardening; not semantic promotion',code_change='immutable feature policy; rejected policy retained, original files never reset',new_attachment_blocks=new_attachment)
        history.append(record);write(out/f'iteration-{index}.json',dict(record=record,traces=candidate,paired_diff=diff))
        if accepted: best=candidate; best_policy=policy
        if stagnant>=config['stop_no_improvement']: break
    b2_revised=[grade(c,'b2',best_policy,action_db.path) for c in config['cases']]
    write(out/'b2-revised.json',b2_revised);write(out/'best.json',best)
    diff=paired(b2_revised,best);write(out/'paired-diff.json',diff)
    taxonomy={}
    for row in best:
        for reason in row['errors']:taxonomy['structure_input_rejection']=taxonomy.get('structure_input_rejection',0)+1
        for f in row['findings']:taxonomy[f['code']]=taxonomy.get(f['code'],0)+1
    result=dict(manifest=manifest,b2_legacy=summary(b2,legacy=True),b2_actions=summary(actions,legacy=True),b2_revised=summary(b2_revised),candidate_full=summary(best),b3_legacy=summary(b3,legacy=True),best_policy=best_policy,iterations=history,paired=dict(win=sum(d['outcome']=='win' for d in diff),loss=sum(d['outcome']=='loss' for d in diff),tie=sum(d['outcome']=='tie' for d in diff)),failure_taxonomy=taxonomy,promotion='NOT_PROMOTED',human_gold='PENDING',independent_holdout='NOT_RUN',calibration=calibration({},{}))
    write(out/'summary.json',result);write(out/'failure-taxonomy.json',taxonomy)
    write(out/'cost-ledger.json',dict(mode='REPLAY',new_provider_calls=0,new_tokens=0,estimated_cost_rmb=0,upper_bound_rmb=0,historical_costs_not_charged_again=True,unknown_execution=False))
    # Registry append only, unique experiment IDs; caller must choose a new run directory.
    registry=out.parent/'experiment_registry.jsonl'
    with registry.open('a',encoding='utf-8') as f:
        arm_traces={'B2 incumbent':b2,'B2 + B3 actions':actions,'B2 + revised guard':b2_revised,'candidate full replay':best}
        for arm,stats in [('B2 incumbent',result['b2_legacy']),('B2 + B3 actions',result['b2_actions']),('B2 + revised guard',result['b2_revised']),('candidate full replay',result['candidate_full'])]:
            row=dict(experiment_id=out.name+'/'+arm,date=manifest['created_at'],commit_sha=manifest['commit_sha'],baseline_sha=manifest['commit_sha'],change_class='REPLAY_ABLATION',change_summary=arm,prompt_hash=sorted({read(ROOT/c['b2_path' if arm.startswith('B2') else 'b3_path'])['config']['prompt_hash'] for c in config['cases']}),schema_hash=config['schema_hash'],grader_hash=pf['grader_hash'],dataset_hash=config['dataset_hash'],model=config['model'],fixture_hash=digest([r['actual_fixture_hash'] for r in arm_traces[arm]]),**stats,p50_ms=None,p95_ms=None,cost_estimated=0,ci_lower=None,ci_upper=None,live_e2e_ready=None,language_accuracy=stats['english_correct']/stats['english_n'] if stats['english_n'] else None)
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
    return result
