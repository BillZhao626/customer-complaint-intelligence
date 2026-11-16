"""Free-only R1 freeze, historical audit and compact evidence export."""
import os,sys,json,csv,random,hashlib,shutil,sqlite3
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
from src.domain.contracts import EmailInput,digest
from src.application.p5b8_research import cases,read,readable_reply,comparison
from src.application.p5b8_product import make_run
from src.application.p5b8r1_guard import quality,assess,calibrate,VERSION as GUARD_VERSION
from src.application.p5b8r1_contracts import paired_messages,parse_outcome,analysis_system,REPLY_SYSTEM,VERSION as CONTRACT_VERSION
from src.application.p5b8r1_experiment import ARMS,MODEL,VERSION,pair_invariant
from src.evaluation.p5b8r1_judge import SYSTEM as JUDGE_SYSTEM,VERSION as JUDGE_VERSION
LOCAL=ROOT/'.local/p5b8r1';DOC=ROOT/'docs/p5b8r1';REF=LOCAL/'reference';OLD=ROOT/'.local/p5b8'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def frozen(path,value):
    if Path(path).exists():
        if digest(read(path))!=digest(value):raise ValueError('Frozen input changed; introduce a new explicit version: '+str(path))
    else:dump(path,value)
def csvout(path,rows,fields=None):
    rows=list(rows);fields=fields or list(dict.fromkeys(k for r in rows for k in r));path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})
def mdjson(v):return '\n```json\n'+json.dumps(v,ensure_ascii=False,indent=2)+'\n```\n'
def selection():
    with (REF/'消融候选24案_分层索引.csv').open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def prepare(rows):
    selected=selection();by={r['case_id']:r for r in rows};orders=[list(ARMS),list(reversed(ARMS))]*12;random.Random(20261031).shuffle(orders);manifest=[]
    for s,order in zip(selected,orders):
        r=by[s['case_id']];e=EmailInput.model_validate(r['email']);a=r['analysis']['data'];runtime=r['replies']['A_GUIDED']['runtime']
        if s['input_sha256']!=e.input_hash:raise ValueError('Attachment/source hash mismatch')
        if not a or r['analysis']['error']:raise ValueError('Frozen selected analysis invalid: no silent substitution')
        checked=parse_outcome(r['analysis']['call']['raw'],email=e,metadata=r['analysis']['call']['metadata'])
        if checked['status']!='accepted' or checked['value']!=a:raise ValueError('Analysis raw/parsed mismatch')
        msgs=paired_messages(e,a,runtime);proof=pair_invariant(msgs)
        spec=dict(version=VERSION,case_id=e.email_id,input_hash=e.input_hash,stratum=s['stratum'],language=r['language'],family=r['family'],dataset_role='DEV_DIAGNOSTIC_EXPOSED_B7',annotation_status='MODEL_PROVISIONAL_NO_HUMAN_GOLD',status='AUTHORIZATION_BLOCKED',order=order,model=MODEL,messages=msgs,invariant=proof,analysis_run_id=r['analysis']['call']['run_id'],analysis_sha256=sha(OLD/'analysis'/(e.email_id+'.json')),reference_file_sha256=sha(REF/'消融候选24案_分层索引.csv'),source_sha256=sha(ROOT/'.local/p5b7/dataset'/(e.email_id+'.json')),notes='No fresh analysis or tools. Both arms retain all non-emotion Issue fields; free-form uncertainty notes excluded from BOTH arms to prevent hidden sentiment explanations. Raw notes preserved in evidence. Praise/complaint intent and original mail remain visible in both arms; this measures explicit-field increment, not removing all inferable affect.')
        frozen(LOCAL/'prepared'/(e.email_id+'.json'),spec)
        manifest.append({k:spec[k] for k in ('case_id','input_hash','stratum','language','family','order','invariant','analysis_run_id','analysis_sha256','source_sha256')})
    protocol=dict(version=VERSION,status='AUTHORIZATION_BLOCKED',selected=24,ready_pairs=24,planned_reply_requests=48,actual_new_paid_requests=0,actual_new_cost_cny=0,budget_ledger=None,model=MODEL,system_prompt_hash=digest(REPLY_SYSTEM),analysis_prompt_hash=digest(analysis_system()),judge_prompt_hash=digest(JUDGE_SYSTEM),contract=CONTRACT_VERSION,guard=GUARD_VERSION,judge=JUDGE_VERSION,random_seed=20261031,order_counts=dict(Counter(x['order'][0] for x in manifest)),strata=dict(Counter(x['stratum'] for x in manifest)),languages=dict(Counter(x['language'] for x in manifest)),families=dict(Counter(x['family'] for x in manifest)),substitutions=[],primary_endpoint='Source-grounded emotion_fit 0/1/2 paired WITH minus NO; no-deterioration checks on B1 facts, B2 goals, B3 receipt/authority and severe errors. Report W/L/T/UNKNOWN over all 24 dispatched pairs; emotion delta only for both-parsed and judged pairs, with its own n. Never score parse failure as zero emotion.',engineering_endpoints='Provider transport / JSON / schema / safety / language / receipt consistency over all 48 planned first replies, unknowns retained. Reviewable is not human approved or problem solved.',emotion_rubric={'2':'Matches actual tone and all mixed aspects without forced apology; neutral fault is not automatically angry.','1':'Partly appropriate with minor excess/under-acknowledgment or one mixed aspect missed.','0':'Materially mismatched tone or no acknowledgment of salient expressed sentiment.','NA':'Structure failed, response missing, or no authorized assessment.'},evaluation_plan='Version blind X/Y; balanced AB/BA; R1 slot-bound Judge; key reversals and exact repeats only after separate authorization. Human scores blank; human agreement/Kappa null. Pair differences and uncertainty intervals only when observed n permits; no post-hoc sample replacement.',human_agreement=None,cohens_kappa=None,results=dict(with_sentiment=None,no_sentiment=None,improved=None,regressed=None,tied=None,unknown=24,p50_ms=None,p95_ms=None,tokens=None,emotion_delta=None),cases=manifest)
    # v1 preparation remains immutable. v2 freezes the corrected Guard; messages
    # and sample/order hashes remain identical. Neither preparation dispatched.
    frozen(LOCAL/'FROZEN_PROTOCOL_v2.json',protocol);dump(DOC/'ABLATION_READINESS.json',protocol);csvout(DOC/'FROZEN_24.csv',manifest)
    return protocol

def audit_runtime(r,variant):
    reply=r['replies'][variant];rt=dict(reply['runtime'],audit_records=[],capabilities={},attachment_manifest=[]);p=OLD/'calls'/variant/r['case_id']/'frozen-input.json'
    if p.exists():
        f=read(p)
        try:e=EmailInput.model_validate(f['payload']['email'])
        except (ValueError,KeyError):return rt
        if e.input_hash==r['input_hash'] and f['run_id']==reply['call']['run_id']:rt['audit_records']=[dict(record_id=f['run_id']+':input',input_hash=e.input_hash,artifact_sha256=sha(p),phase='before_provider')]
    return rt

def judge_audit(rows):
    differences=[];mapped=[];cross=[];swaps=[]
    for r in rows:
        for j in r['judges']:
            for answer in (j['parsed'] or {}).get('answers',[]):
                variant=j['order'][['A','B'].index(answer['slot'])];reply=r['replies'][variant];runtime=audit_runtime(r,variant)
                prior=dict(findings=[dict(f,severity='block') for f in answer['hard_errors']]+[dict(f,severity='review') for f in answer.get('review_findings',[])])
                decision=calibrate(prior,reply['reply'] or '',runtime,r['input_hash']) if reply['reply'] else dict(status='NOT_ASSESSABLE_STRUCTURE',findings=[],exclusions=[],action_states=[])
                row=dict(case_id=r['case_id'],experiment=j['experiment'],swap=j['swap'],variant=variant,slot=answer['slot'],old_scores=answer['scores'],old_emotion_fit=answer.get('emotion_fit'),old_hard=answer['hard_errors'],old_reasons=answer['dimension_reasons'],r1_deterministic=decision,new_judge_scores=None,new_judge_status='AUTHORIZATION_BLOCKED',semantic_eligible=bool(reply['reply'] and not reply['error']),old_judge_run_id=j['call']['run_id'])
                mapped.append(row)
                if decision['exclusions'] or decision['findings']!=prior['findings'] or not row['semantic_eligible']:differences.append(row)
                own={e['kind'] for e in runtime['events'] if e['status'] in ('created','handoff_pending') and e['input_hash']==r['input_hash']}
                for f in answer['hard_errors']:
                    for kind in ('store_service_request','aftersales_request','logistics_followup','support_followup','billing_request'):
                        if kind in f['reason'] and kind not in own:
                            other=[v for v,q in r['replies'].items() if v in j['order'] and v!=variant and any(e['kind']==kind and e['status']=='created' for e in q['runtime']['events'])]
                            cross.append(dict(case_id=r['case_id'],variant=variant,claimed_receipt_kind=kind,actual_matching_receipts=sorted(own),other_slot_has_kind=other,quote=f['quote'],old_reason=f['reason'],status='DETERMINISTIC_EVIDENCE_MISMATCH_SEMANTIC_REVIEW_PENDING'))
        for j in [x for x in r['judges'] if x['swap'] and x['parsed']]:
            original=next((x for x in r['judges'] if not x['swap'] and x['experiment']==j['experiment']),None)
            if not original or not original['parsed']:continue
            def indexed(x):return {x['order'][['A','B'].index(a['slot'])]:a for a in x['parsed']['answers']}
            x,y=indexed(original),indexed(j);changes=[]
            for v in x:
                for d in ('B1','B2','B3','B4','B5'):
                    if x[v]['scores'][d]!=y[v]['scores'][d]:changes.append(dict(variant=v,dimension=d,before=x[v]['scores'][d],reversed=y[v]['scores'][d]))
                if x[v].get('emotion_fit')!=y[v].get('emotion_fit'):changes.append(dict(variant=v,dimension='emotion_fit',before=x[v].get('emotion_fit'),reversed=y[v].get('emotion_fit')))
                if x[v]['hard_errors']!=y[v]['hard_errors']:changes.append(dict(variant=v,dimension='hard_errors',before=x[v]['hard_errors'],reversed=y[v]['hard_errors']))
            swaps.append(dict(case_id=r['case_id'],experiment=j['experiment'],changes=changes,numeric_or_hard_stable=not changes,old_run_ids=[original['call']['run_id'],j['call']['run_id']]))
    c=comparison(rows,'A');b=comparison(rows,'B');result=dict(version=JUDGE_VERSION,status='IMPROVED_NOT_CERTIFIED',historical_A=c,historical_B=b,swaps=swaps,order_stable=sum(s['numeric_or_hard_stable'] for s in swaps),order_tested=len(swaps),exact_same_input_repeat_n=0,exact_repeat_agreement=None,new_paid_judgments=0,cross_slot_evidence_mismatches=cross,calibrations=differences,all_dimensions=mapped,human_agreement=None,cohens_kappa=None,limitations=['No numerical rescoring without new authorized Judge/human observations','Length bias not established or ruled out by the deterministic concise/long control','Same-provider Judge correlation and exposed DEV selection remain','B7-085 empty parsed reply is a structure confound, not evidence of emotional improvement'])
    dump(DOC/'JUDGE_CALIBRATION.json',result);csvout(DOC/'JUDGE_DIMENSIONS.csv',mapped);csvout(DOC/'JUDGE_ORDER_DIFFS.csv',[dict(case_id=s['case_id'],experiment=s['experiment'],stable=s['numeric_or_hard_stable'],changes=s['changes']) for s in swaps]);return result

def repairs(rows):
    by={r['case_id']:r for r in rows};out=[]
    for eid in ('B7-034','B7-056','B7-067'):
        r=by[eid];a=r['analysis'];outcome=parse_outcome(a['call']['raw'],email=EmailInput.model_validate(r['email']),metadata=a['call']['metadata'])
        out.append(dict(case_id=eid,family='ANALYSIS_REQUIRED_UNCERTAINTY',original_raw=a['call']['raw'],original_run_id=a['call']['run_id'],original_error=a['error'],r1_replay=outcome,change='Versioned full-shape example, required-key checklist, uncertainty near start; strict parser rejects missing field without defaults',new_live_result=None,status='ENGINEERING_FIXED_LIVE_RETEST_PENDING'))
    for eid,v in [('B7-049','A_DIRECT'),('B7-072','A_GUIDED'),('B7-085','A_DIRECT')]:
        r=by[eid];q=r['replies'][v];out.append(dict(case_id=eid,variant=v,family='REPLY_JSON_MISSING_OBJECT_DELIMITER',original_raw=q['call']['raw'],readable_audit_only=readable_reply(q),original_error=q['error'],original_run_id=q['call']['run_id'],finish_reason=q['call']['metadata'].get('finish_reason'),output_tokens=q['call']['metadata'].get('output_tokens'),r1_replay=parse_outcome(q['call']['raw'],metadata=q['call']['metadata']),change='JSON mode retained, explicit complete-object/escaping example, strict nonblank one-key contract, length finish rejected, failed structure excluded from semantic Judge',new_live_result=None,status='ENGINEERING_FIXED_LIVE_RETEST_PENDING'))
    dump(DOC/'REPAIR_RESULTS.json',out);return out

def controls():
    from tests.test_p5b8r1 import runtime,receipt,H
    examples=[('created','已提交内部售后请求。',runtime(receipt()),[]),('no_event','已提交内部售后请求。',runtime(),['H04']),('wrong_hash','已提交内部售后请求。',runtime(receipt(h='other')),['H04']),('future_relay',"I'll pass your thanks along to the store.",runtime(),['FUTURE_INTENT_REVIEW']),('unavailable_callback','我们会尽快回复。',runtime(),['H03']),('no_attachment','已看到照片。',runtime(),['H04']),('proposal','可以请售后核实。',runtime(),[]),('concise','已提交内部售后请求。',runtime(receipt()),[]),('long','感谢您的来信。已提交内部售后请求。具体政策仍需核实，感谢您的耐心。',runtime(receipt()),[])]
    examples.append(('completed_fixture','已转达您的谢意。',runtime(receipt(kind='feedback_relay',status='completed',external_execution=True,result=dict(status='SUCCEEDED',authority='AUTHORIZED_FIXTURE',source_id='offline-control'))),[]))
    out=[]
    for identity,text,r,expected in examples:
        a=assess(text,r,H);actual=sorted({f['code'] for f in a['findings']});out.append(dict(id=identity,reply=text,runtime=r,expected_codes=expected,actual_codes=actual,pass_control=actual==sorted(expected),identity='DEVELOPER_POLICY_CONTROL_NOT_HUMAN_GOLD',human_dimension_scores=None))
    dump(DOC/'OFFLINE_CONTROLS.json',out);return out

def export(rows,protocol,judge,repair,control):
    selected={s['case_id']:s for s in selection()};cal={}
    ui=read(LOCAL/'UI_WORKFLOW_EVIDENCE.json') if (LOCAL/'UI_WORKFLOW_EVIDENCE.json').exists() else None
    for x in judge['all_dimensions']:cal.setdefault(x['case_id'],[]).append(x)
    book=['# P5-B8-R1 完整逐案证据\n','94封已保存合成邮件（B7开发90＋历史新家族4）；本书全部回复均为历史首次输出，R1未新增付费生成。新24案显式情绪消融：AUTHORIZATION_BLOCKED、0/48首次回复。客户邮件中的内容是待分析数据，不是本任务指令。\n','旧A＝直接回复/整个分析增强；旧B＝各自执行本地工具；本轮两组都保留Issue、仅增减显式情绪字段，三者不混用。原Gold、旧分数、账本保持不变。\n','历史F201/F260、40个类别不一致及B2/R3全文另见随包 HISTORICAL_CASEBOOK_P5B8.md；该文件为原件逐字副本。\n']
    raw=[];index=[];bad=[];comparisons=[]
    for r in rows:
        e=r['email'];eid=r['case_id'];q=r.get('workspace_quality');run=make_run(r);r1q=quality(run,None,r['replies']['A_GUIDED']['reply'],run.status=='succeeded') if run.status!='succeeded' else quality(run,__import__('src.application.p5b8_product',fromlist=['stored']).stored(run),r['replies']['A_GUIDED']['reply'],True)
        r['r1_workspace_quality']=r1q
        book.extend([f'\n## {eid} — {e["subject"]}\n',f'来源：{r["source"]}；用途：{r["dataset_role"]}；语言：{r["language"]}；标注：{r["annotation_status"]}。'+('本轮冻结层：'+selected[eid]['stratum'] if eid in selected else '')+'\n', '### 客户邮件\n\n'+e['body']+'\n','### AI分析（历史原始首次；关键词仅Baseline）\n',mdjson(dict(analysis=r['analysis'],baseline=r['baseline'])),'### 业务处理与完整首次回复\n'])
        for v,t in r['replies'].items():
            book.extend([f'\n#### {v} · 历史变体，不是R1新消融\n',('**首次JSON失败：仅审计可读呈现，不作可审草稿或情绪评分。**\n' if t['error'] else ''),readable_reply(t)+'\n',mdjson(dict(run_id=t['call']['run_id'],error=t['error'],elapsed_ms=t['call']['elapsed_ms'],tokens=t['call']['metadata'].get('total_tokens'),cost_upper_cny=t['call']['cost_upper'])), '\n实际事实与事件回执（local only；created不等于外部联系）：\n',mdjson(t['runtime'])])
        if ui and ui['case_id']==eid:book.extend(['### R1后续工作台操作（不属于历史生成条件）\n','明确转达表扬的请求在R1工作台创建了本地内部待办，并测试模拟发送。以下事件发生在历史首次回复之后，不能追认历史承诺，也不加入新24案任一组的冻结回执。UI_SMOKE_ONLY不是人类Gold或质量评分。\n',mdjson(ui)])
        if eid in selected:book.extend(['### 本轮显式情绪消融\n','ISSUES_NO_SENTIMENT：AUTHORIZATION_BLOCKED，尚无首次回复。\n\nISSUES_WITH_SENTIMENT：AUTHORIZATION_BLOCKED，尚无首次回复。\n\n两组输入已冻结，事实、Issue、回执及模型相同，仅explicit_emotion不同。人类评分留空。\n'])
        book.extend(['### 评价、争议与建议\n',mdjson(dict(original_judges=r['judges'],r1_judge_intake_and_deterministic_calibration=cal.get(eid,[]),historical_workspace=q,r1_workspace=r1q,findings=r['findings'],human_scores=None)), '建议：先核对原文证据与当前事件，开放语义按 OWNER_DECISIONS 的规则集中裁决；保留旧数值，未产生新的模型质量评分。\n'])
        raw.append(dict(case_id=eid,source=r,provenance='READ_ONLY_HISTORICAL_PLUS_VERSIONED_R1_DERIVATION',r1_post_experiment_ui=ui if ui and ui['case_id']==eid else None,r1_new_paid_output=None))
        index.append(dict(case_id=eid,source=r['source'],language=r['language'],family=r['family'],dataset_role=r['dataset_role'],annotation_status=r['annotation_status'],input_hash=r['input_hash'],stratum=selected.get(eid,{}).get('stratum'),expressed_sentiment=(r['analysis']['data'] or {}).get('expressed_sentiment'),experience=(r['analysis']['data'] or {}).get('experience_polarity'),complaint_intent=(r['analysis']['data'] or {}).get('complaint_intent'),old_workspace_status=q['status'],r1_workspace_status=r1q['status'],new_ablation_status='AUTHORIZATION_BLOCKED' if eid in selected else 'NOT_SELECTED'))
        families=sorted({f['family'] for f in r['findings']}|{f['code'] for f in r1q['findings']}|({'R1_JUDGE_CALIBRATION_DIFFERENCE'} if any(x['case_id']==eid for x in judge['calibrations']) else set()))
        if families:bad.append(dict(case_id=eid,error_families=families,original_findings=r['findings'],r1_findings=r1q['findings'],human_decision='',status='IMPROVED_NOT_CERTIFIED' if r1q!=q else 'HUMAN_PENDING'))
    # Reuse the existing Registry identities, keeping old case evidence rather
    # than starting a parallel registry or silently narrowing "ALL" to 94.
    original_bundle=ROOT/'docs/p5b8/review_bundle'
    def readcsv(name):
        with (original_bundle/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    r1_bad_count=len(bad);idx={x['case_id']:x for x in index};badidx={x['case_id']:x for x in bad};rawidx={x['case_id']:x for x in raw}
    for h in readcsv('ALL_CASES.csv'):
        if h['case_id'] not in idx:idx[h['case_id']]=dict(case_id=h['case_id'],subject=h['subject'],source=h['source'],dataset_role=h['dataset_role'],annotation_status=h['annotation_status'],input_hash=h['input_hash'],r1_workspace_status='NOT_EVALUATED_R1',new_ablation_status='NOT_SELECTED')
        idx[h['case_id']]['inherited_registry_row']=h
        idx[h['case_id']]['casebook']='CASEBOOK.md' if h['case_id'] in {x['case_id'] for x in rows} else 'HISTORICAL_CASEBOOK_P5B8.md'
    for h in readcsv('ALL_BAD_CASES.csv'):
        if h['case_id'] not in badidx:badidx[h['case_id']]=dict(case_id=h['case_id'],error_families=json.loads(h['error_families']),r1_findings=None,status='INHERITED_DIAGNOSTIC_NOT_REOPENED',human_decision='')
        badidx[h['case_id']]['inherited_bad_record']=h
    with (original_bundle/'RAW_EVIDENCE.jsonl').open(encoding='utf-8') as f:
        for line in f:
            h=json.loads(line)
            if h['case_id'] not in rawidx:rawidx[h['case_id']]=dict(case_id=h['case_id'],provenance='UNCHANGED_INHERITED_EVIDENCE_NOT_NEW_R1',r1_new_paid_output=None)
            rawidx[h['case_id']]['inherited_p5b8_evidence']=h
    index=list(idx.values());bad=list(badidx.values());raw=list(rawidx.values())
    (DOC/'CASEBOOK.md').write_text('\n'.join(book),encoding='utf-8')
    with (DOC/'RAW_EVIDENCE.jsonl').open('w',encoding='utf-8') as f:
        for r in raw:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    csvout(DOC/'ALL_CASES.csv',index);csvout(DOC/'ALL_BAD_CASES.csv',bad)
    by={x['case_id']:x for x in rows}
    for exp,comp in [('A',judge['historical_A']),('B',judge['historical_B']),('A_TRANSFER',comparison(rows,'A',independent=True))]:
        for x in comp['rows']:
            row=by[x['case_id']];prefix='B' if exp=='B' else 'A';d,g=(row['replies'][prefix+'_'+v] for v in ('DIRECT','GUIDED'))
            comparisons.append(dict(experiment='HISTORICAL_'+exp,**x,direct_full_first=readable_reply(d),guided_full_first=readable_reply(g),direct_parse_error=d['error'],guided_parse_error=g['error'],direct_run=d['call']['run_id'],guided_run=g['call']['run_id'],same_receipts=digest(d['runtime']['events'])==digest(g['runtime']['events'])))
    comparisons.extend(dict(experiment=VERSION,case_id=s['case_id'],delta='UNKNOWN',status='AUTHORIZATION_BLOCKED',with_reply=None,no_reply=None,new_paid_requests=0) for s in selection());csvout(DOC/'AB_COMPARISON.csv',comparisons)
    blind=['# 24案版本盲评 · 历史完整首响应\n','这不是R1新情绪消融。X/Y隐藏旧A变体身份；请先独立评分，再打开解盲映射。参考标签、Judge分数均不展示。原JSON失败只保留审计文本，结构不合格处语义分数为N/A，不填0。\n']
    mapping=[];scores=[];rng=random.Random(20261101)
    by={r['case_id']:r for r in rows}
    for s in selection():
        r=by[s['case_id']];order=['A_DIRECT','A_GUIDED'];rng.shuffle(order);mapping.append(dict(case_id=r['case_id'],X=order[0],Y=order[1],experiment='HISTORICAL_A_NOT_R1_ABLATION'))
        blind.extend([f'\n## {r["case_id"]} — {r["email"]["subject"]}\n',r['email']['body'], '\n共同已核实事实/同一组动作回执：\n',mdjson(r['replies']['A_GUIDED']['runtime'])])
        for slot,v in zip(['X','Y'],order):
            t=r['replies'][v];blind.extend([f'\n### 回复{slot}\n',('结构失败；以下仅审计可读正文，语义评分N/A。\n' if t['error'] else ''),readable_reply(t)+'\n']);scores.append(dict(case_id=r['case_id'],slot=slot,experiment='HISTORICAL_A_NOT_R1_ABLATION',reviewer='',accuracy_evidence='',all_goals='',actions_authority='',emotion_fit='',natural_concise='',severe_errors='',comments=''))
    (DOC/'BLIND_24_HISTORICAL.md').write_text('\n'.join(blind),encoding='utf-8');dump(DOC/'UNBLIND_AFTER_SCORING.json',mapping);csvout(DOC/'HUMAN_SCORES.csv',scores)
    csvout(DOC/'NEW_ABLATION_BLIND_INTAKE.csv',[dict(case_id=s['case_id'],slot=slot,response_status='AUTHORIZATION_BLOCKED',reply='',reviewer='',emotion_fit='',B1='',B2='',B3='',B4='',B5='',severe_error='') for s in selection() for slot in ('X','Y')])
    decisions=[('D1','礼貌客观故障是否中性表达、负面体验；历史F201/F260保留旧Gold，R1不覆盖','优先按表达证据分轴；仅新annotation overlay，历史分数不重算','F201;F260;B7-016;B7-036'),('D2','已归档来信能否支持“已记录表扬”，以及未来“将转达”应为review还是实质承诺','仅支持记录，不支持创建任务、送达；未来意图不判完成H04，承诺可单列H03/Review','B7-002;B7-010;B7-009'),('D3','混合情绪邮件应同时如何回应赞美与不满','依据实际表达逐Issue回应，不能仅看全局负面或机械道歉','B7-084;B7-085;B7-087;B7-088;B7-089;B7-090'),('D4','旧Judge B7-009引用另一组的门店任务，并将将来时判H04；B1/B3应如何重新评分','回执错配已确定；数值尚无新Judge或人类证据，不自动更改','B7-009'),('D5','英文语气、简洁性、表扬转达的自然程度及附件来信自然度','版本盲化全文评分；少量高价值规则决议，无需重签16旧Gold','24 frozen DEV cases')]
    csvout(DOC/'OWNER_DECISIONS.csv',[dict(id=i,question=q,agent_recommendation=a,cases=c,status='HUMAN_PENDING',human_decision='',reviewer='',annotation_version='') for i,q,a,c in decisions])
    shutil.copyfile(ROOT/'docs/p5b8/review_bundle/CASEBOOK.md',DOC/'HISTORICAL_CASEBOOK_P5B8.md')
    hist=[r for r in rows if r['case_id'].startswith('B7-')]
    result=dict(version=VERSION,status='IMPROVED_NOT_CERTIFIED',protected_files=len(read(LOCAL/'initial.json')['files']),historical_ledger=read(ROOT/'docs/p5b8/RESULTS.json')['budget'],actual_new_paid_requests=0,actual_new_cost_cny=0,new_ledger_created=False,new_ablation=protocol,original_analysis_accepted_90=sum(bool(r['analysis']['data']) for r in hist),original_analysis_n_90=len(hist),original_analysis_accepted_94=sum(bool(r['analysis']['data']) for r in rows),original_reply_parse_90={v:sum(bool(r['replies'][v]['reply']) and not r['replies'][v]['error'] for r in hist) for v in ('A_DIRECT','A_GUIDED')},original_reply_parse_94={v:sum(bool(r['replies'][v]['reply']) and not r['replies'][v]['error'] for r in rows) for v in ('A_DIRECT','A_GUIDED')},original_product_gates_94=dict(Counter(r['workspace_quality']['status'] for r in rows)),r1_product_gates_94=dict(Counter(r['r1_workspace_quality']['status'] for r in rows)),historical_judge_A=judge['historical_A'],historical_judge_B=judge['historical_B'],order_stability=dict(stable=judge['order_stable'],tested=judge['order_tested'],exact_repeat_n=0),cross_slot_mismatches=judge['cross_slot_evidence_mismatches'],controls=dict(n=len(control),passed=sum(x['pass_control'] for x in control)),repair_families=repair,bad_case_count=len(bad),r1_bad_case_count=r1_bad_count,registry_index_cases=len(index),raw_evidence_cases=len(raw),exported_cases=len(rows),human_agreement=None,cohens_kappa=None)
    dump(DOC/'RESULTS.json',result);return result

def main():
    if '--live' in sys.argv:raise SystemExit('AUTHORIZATION_BLOCKED: no P5-B8-R1 paid authorization. Old budget is closed. No provider constructed.')
    DOC.mkdir(parents=True,exist_ok=True);rows=cases();protocol=prepare(rows);j=judge_audit(rows);rep=repairs(rows);con=controls();r=export(rows,protocol,j,rep,con)
    print(json.dumps(dict(exported_cases=r['exported_cases'],frozen=protocol['selected'],strata=protocol['strata'],orders=protocol['order_counts'],A_judged=j['historical_A']['n_judged'],A_unknown=j['historical_A']['changes']['UNKNOWN'],swaps_stable=j['order_stable'],swaps_n=j['order_tested'],cross_slot=len(j['cross_slot_evidence_mismatches']),old_gates=r['original_product_gates_94'],r1_gates=r['r1_product_gates_94'],bad_cases=r['bad_case_count'],paid_requests=0),ensure_ascii=False))
if __name__=='__main__':main()
