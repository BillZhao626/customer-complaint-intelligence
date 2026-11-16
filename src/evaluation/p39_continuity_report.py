"""Deterministic failure-inclusive report; semantic judgments stay unsigned."""
from collections import Counter
from hashlib import sha256
from html import escape
import json
from pathlib import Path

from src.application.p39_continuity import diagnose,load_runs,VERSION
from src.domain.analysis_v31_context import stored_context_analysis
from src.domain.contracts import digest
from src.evaluation.e2e_v3 import SEVEN
from src.evaluation.p2_report import percentile
from src.evaluation.semantic_review_v2 import GUIDANCE
from src.application.reply_review import inspect_reply
from src.application.research_policy_v2 import language,requested_language


def review(run):
    value = stored_context_analysis(run).model_dump() if run.result else (run.attempts[-1].parsed_output if run.attempts else None)
    value = value if isinstance(value,dict) else {}
    reply = value.get('suggested_reply',''); summary = value.get('summary','')
    reply = reply if isinstance(reply,str) else ''
    summary = summary if isinstance(summary,str) else ''
    issues = value.get('issues',[])
    issues = issues if isinstance(issues,list) else []
    source_language = requested_language(run.email.body)
    reply_language = language(reply) if reply else 'unknown'
    gate = inspect_reply(reply)
    dimensions = {k:dict(verdict_candidate='UNVERIFIED',ai_opinion=text,
                          human_score=None,human_critical_error=None,
                          evidence_source='original email and raw output',evidence_quote=run.email.body,
                          applicability='accepted_output' if run.result else 'failed_raw_diagnostic_only') for k,text in GUIDANCE.items()}
    dimensions['summary_facts']['evidence_quote'] = summary
    for k in ('reply_language','reply_coverage','repeated_information','mechanical_disclaimer','invented_actions','material_promises','safety_privacy','multi_issue_reply'):
        dimensions[k]['evidence_quote'] = reply
    dimensions['evidence_support'].update(ai_opinion='原文跨度通过仅是工程证据；标签语义支持仍待人工。' if run.result else '失败raw仅作诊断，不能作为正式接受输出计分。',
        evidence_quote=json.dumps([i.get('evidence') for i in issues if isinstance(i,dict)],ensure_ascii=False))
    if reply:
        dimensions['reply_language'].update(verdict_candidate='PASS_VISIBLE_EVIDENCE' if source_language in (reply_language,'bilingual') else 'MAJOR_CANDIDATE',
            ai_opinion=f'词面语言：source={source_language}, reply={reply_language}；须人工核查自然性和客户明确要求。')
        for k in ('invented_actions','material_promises'):
            findings=[f for f in gate['findings'] if (f['kind'] in ('executed_action','approval_claim')) == (k=='invented_actions')]
            dimensions[k].update(verdict_candidate='MAJOR_CANDIDATE' if findings else 'UNVERIFIED',
                ai_opinion='词面门禁信号：'+json.dumps(findings,ensure_ascii=False) if findings else '词面门禁未发现已知信号；不证明没有虚构动作或承诺。')
        mechanical=any(x in reply.lower() for x in ('system prompt','cannot directly','unable to directly','无法在此','无权','系统提示'))
        dimensions['mechanical_disclaimer'].update(verdict_candidate='MINOR_CANDIDATE' if mechanical else 'UNVERIFIED',
            ai_opinion='发现能力/系统免责声明词面，需判断实用性。' if mechanical else '未见列举的免责声明词面，语义仍待审。')
    d=diagnose(run)
    if d['stage']=='semantic_validation':
        error=str(d['error']).lower()
        dimension=('customer_importance' if any(s in error for s in ('importance','equal','primary')) else
                   'reply_language' if 'language' in error else
                   'risk_urgency' if any(s in error for s in ('urgency','urgent','repeated failure','relaxed','risk','severe')) else None)
        if dimension:
            dimensions[dimension].update(verdict_candidate='REJECTION_REVIEW_REQUIRED',ai_opinion='最早原文校验拒绝：'+str(d['error'])+'；拒绝可能含模型错误或有界校验误拒，需因果审查。')
    if d['stage']=='safety_gate':
        dimensions['material_promises'].update(verdict_candidate='MAJOR_CANDIDATE',ai_opinion='正式回复门禁拒绝：'+str(d['error']))
    return dict(dimensions=dimensions,gate=gate,ai_opinions_only=True,
                method='assistant-authored rubric with deterministic visible-evidence candidates; not an independent LLM Judge',
                critical_errors_human=None,semantic_score=None,reply_status='unreviewed_unsent')


def evaluate(rt,runs,refs,budget_state):
    m=rt['candidate']; inputs={r['email']['email_id']:r for r in m['inputs']}
    if set(refs)!={k for k,v in inputs.items() if v['group']=='frozen24'}:
        raise ValueError('Frozen reference coverage drift')
    for key,ref in refs.items():
        if digest(ref)!=inputs[key]['source_hash'] or ref['email']!=inputs[key]['email']:
            raise ValueError('Reference identity drift')
    by={}
    for r in runs:
        key=(r.email.email_id,r.config.parameters['arm'])
        if key in by or r.email.model_dump()!=inputs[key[0]]['email'] or r.config.model_dump()!=m['configs'][key[1]]:
            raise ValueError('Duplicate or changed experimental identity')
        by[key]=r
    arms={};members=[];pairs=[]
    for arm in ('A','B'):
        chosen=[r for (sid,a),r in by.items() if a==arm]
        attempts=[a for r in chosen for a in r.attempts]
        submitted=[a for a in attempts if a.metadata.get('dispatch') in ('response_received','started_or_unknown')]
        fields={k:dict(agreement=0,denominator=24) for k in SEVEN}
        all7=0
        for sid,ref in refs.items():
            r=by.get((sid,arm));checks=[]
            for field in SEVEN:
                good=bool(r and r.result and getattr(r.result,field)==ref['expected'][field]);checks.append(good)
                fields[field]['agreement']+=int(good)
            all7+=int(all(checks))
        quality=[r for r in chosen if r.status=='failed' and r.attempts and r.attempts[-1].metadata.get('dispatch')=='response_received'
                 and r.attempts[-1].error and r.attempts[-1].error.error_type in ('invalid_json','empty_response','raw_schema_invalid')]
        accepted=sum(r.result is not None for r in chosen)
        costs=[a.metadata.get('cost_cny') for a in attempts]
        unknown=sum(a.metadata.get('dispatch')=='started_or_unknown' for a in attempts)
        arms[arm]=dict(planned=32,actual_requests=len(submitted),response_received=sum(a.metadata.get('dispatch')=='response_received' for a in attempts),
                       actual_sent_count_exact=None if unknown else len(submitted),dispatch_unknown=unknown,prepared_not_sent=len(attempts)-len(submitted),
                       accepted=accepted,failed_predictions=len(quality),model_quality_rejected=len(quality),
                       infrastructure_blocked=sum(r.result is None for r in chosen)-len(quality),unattempted=32-len(submitted),
                       contract_acceptance_numerator=accepted,contract_acceptance_denominator=32,attempted_denominator=len(submitted),
                       field_consistency=fields,seven_agreement=sum(v['agreement'] for v in fields.values()),seven_denominator=168,
                       all_seven_agreement=all7,email_denominator=24,reference_source='researcher-approved exposed development reference v1.1, never Human Gold',
                       field_policy_version='historical-v1.1-reference-vs-v3.1-safe-projection; raw consistency, no corrected reference',
                       provider_p50_ms=percentile([a.elapsed_ms for a in attempts if a.elapsed_ms is not None],.5),
                       provider_p95_ms=percentile([a.elapsed_ms for a in attempts if a.elapsed_ms is not None],.95),provider_n=len(attempts),
                       service_p50_ms=percentile([r.metadata['elapsed_ms'] for r in chosen if 'elapsed_ms' in r.metadata],.5),
                       service_p95_ms=percentile([r.metadata['elapsed_ms'] for r in chosen if 'elapsed_ms' in r.metadata],.95),
                       input_tokens=sum(a.metadata.get('input_tokens') or 0 for a in attempts),output_tokens=sum(a.metadata.get('output_tokens') or 0 for a in attempts),
                       total_tokens=sum(a.metadata.get('total_tokens') or 0 for a in attempts),
                       cache_hit_tokens=sum(a.metadata.get('cache_hit_tokens') or 0 for a in attempts),cache_miss_tokens=sum(a.metadata.get('cache_miss_tokens') or 0 for a in attempts),
                       peak_miss_cost_upper_estimate_cny=sum(c for c in costs if c is not None),cost_unknown=sum(c is None for c in costs),actual_invoice_cny=None,
                       issue_semantic_accuracy=None,evidence_semantic_accuracy=None,summary_reply_human_quality=None)
    for step in m['schedule']:
        row=m['inputs'][step['input_index']];sid=row['email']['email_id'];r=by.get((sid,step['arm']))
        if r:
            value=stored_context_analysis(r).model_dump() if r.result else None
            d=diagnose(r)
            members.append(dict(pair=step['pair'],sample_id=sid,arm=step['arm'],run_id=r.run_id,input_hash=r.input_hash,
                                config_hash=digest(r.config.model_dump()),run_hash=digest(r.model_dump()),state=r.status,
                                original_email=r.email.model_dump(),attempts=[a.model_dump() for a in r.attempts],accepted_output=value,
                                pre_gate_output=r.attempts[-1].parsed_output if r.attempts else None,diagnosis=d,review=review(r),
                                formal_issue_count=len(value['issues']) if value else None,
                                evidence_semantics='human-review-pending',reply_status='unreviewed_unsent',
                                historical_reference_comparison={k:dict(expected=refs[sid]['expected'][k],actual=getattr(r.result,k) if r.result else None,
                                                                      agreement=bool(r.result and getattr(r.result,k)==refs[sid]['expected'][k])) for k in SEVEN} if sid in refs else None))
    member_by={(r['sample_id'],r['arm']):r for r in members}
    for step in m['schedule'][::2]:
        sid=m['inputs'][step['input_index']]['email']['email_id'];pair=dict(pair=step['pair'],sample_id=sid)
        for arm in ('A','B'):
            r=member_by.get((sid,arm));pair[arm]=dict(state=r['state'] if r else 'not_attempted',run_id=r['run_id'] if r else None,
                                                   issue_count=r['formal_issue_count'] if r else None)
        pair['both_attempted']=all((sid,a) in by and any(t.metadata.get('dispatch') in ('response_received','started_or_unknown') for t in by[sid,a].attempts) for a in ('A','B'))
        pair['both_accepted']=all((sid,a) in by and by[sid,a].result is not None for a in ('A','B'))
        pair['seven_projection_differences']={k:dict(A=getattr(by[sid,'A'].result,k),B=getattr(by[sid,'B'].result,k)) for k in SEVEN
            if getattr(by[sid,'A'].result,k)!=getattr(by[sid,'B'].result,k)} if pair['both_accepted'] else None
        pair['semantic_winner']=None;pair['human_judgment']=None;pairs.append(pair)
    return dict(version='p39-r3-fixed-report-v1',execution_policy=VERSION,runtime_hash=rt['runtime_hash'],manifest_hash=m['manifest_hash'],
                planned=64,actual_requests=sum(a['actual_requests'] for a in arms.values()),model_quality_rejected=sum(a['model_quality_rejected'] for a in arms.values()),
                infrastructure_blocked=sum(a['infrastructure_blocked'] for a in arms.values()),unattempted=sum(a['unattempted'] for a in arms.values()),
                dispatch_unknown=sum(a['dispatch_unknown'] for a in arms.values()),prepared_not_sent=sum(a['prepared_not_sent'] for a in arms.values()),
                complete_attempted_pairs=sum(bool(p['both_attempted']) for p in pairs),both_accepted_pairs=sum(p['both_accepted'] for p in pairs),
                failed_predictions=sum(a['failed_predictions'] for a in arms.values()),formally_accepted_outputs=sum(a['accepted'] for a in arms.values()),
                failure_stages=dict(Counter(r['diagnosis']['stage'] for r in members if r['state']!='succeeded')),
                acceptance_pair_outcomes=dict(Counter(p['A']['state']+'/'+p['B']['state'] for p in pairs)),
                arms=arms,pairs=pairs,members=members,budget=budget_state,actual_invoice_cny=None,
                field_caveats=dict(urgency='policy v2 pure help is medium; original old-reference low retained',
                    sentiment='mixed projects unknown',store_location='safe uncertainty projection',product_category='customer-primary projection',
                    complaint_reason='billing/size lossy v2 other',source_attribution='safe process-source projection; not proved liability',
                    is_complaint='unknown projects false with diagnostics'),
                human_semantics='human-review-pending',independent_gold='pending',independent_holdout='pending',reply_status='unreviewed_unsent')


def attach_semantic_reviews(report,packet):
    """Attach unsigned assistant observations by exact raw identity, never backfill runs."""
    rows=packet['records'];by={r['run_id']:r for r in rows}
    if len(by)!=len(rows) or set(by)!={r['run_id'] for r in report['members']}:
        raise ValueError('Assistant review coverage/duplicate mismatch')
    counts={a:{s:Counter() for s in ('accepted_output','failed_raw_diagnostic_only')} for a in ('A','B')}
    critical=[]
    for member in report['members']:
        row=by[member['run_id']];raw=member['attempts'][-1]['raw_output']
        if (row['input_hash']!=member['input_hash'] or row['raw_sha256']!=sha256(raw.encode()).hexdigest()
            or row['status']!=member['state'] or set(row['dimensions'])!=set(GUIDANCE)
            or any(d.get('human_score') is not None or not isinstance(d.get('ai_opinion'),str)
                   or not isinstance(d.get('evidence_quote'),str) or not isinstance(d.get('verdict_candidate'),str)
                   for d in row['dimensions'].values())):
            raise ValueError('Assistant review provenance/type/human-score mismatch')
        scope='accepted_output' if member['state']=='succeeded' else 'failed_raw_diagnostic_only'
        if row['review_scope']!=scope:
            raise ValueError('Failed raw review cannot become accepted semantic output')
        member['assistant_semantic_review']=row
        for dimension,item in row['dimensions'].items():
            counts[member['arm']][scope][item['verdict_candidate']]+=1
            label=item['verdict_candidate'].upper()
            if dimension in ('invented_actions','material_promises','safety_privacy') and any(s in label for s in ('MAJOR','CRITICAL','DEFECT')):
                critical.append(dict(run_id=member['run_id'],sample_id=member['sample_id'],arm=member['arm'],scope=scope,dimension=dimension,
                                     ai_opinion=item['ai_opinion'],human_confirmed=None))
    report['assistant_review_summary']=dict(reviewed_runs=len(rows),dimensions_per_run=18,total_dimension_candidates=len(rows)*18,
        candidate_verdict_counts=counts,critical_safety_promise_candidates=critical,semantic_accuracy=None,
        verdict_caveat='Partitions preserve their original candidate vocabulary; counts are descriptive, not calibrated severity scores, inter-rater agreement or confirmed critical-error rates.',
        reviewer_kind='Codex assistant candidate review in three parallel partitions, not independent human raters or an extra DeepSeek Judge',
        packet_hash=digest(packet),human_review='pending')
    report['quality_rejection_caveat']='Validation rejection is an observed acceptance outcome; root cause may be model defect, expected strict rejection or validator false rejection. Counts are not proven semantic-model error rates.'
    return report


def export(rt,budget,out,refs,assistant_review=None):
    from src.application.p39_context_live import write_new
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    report=evaluate(rt,load_runs(rt),refs,budget.summary())
    if assistant_review is not None:
        packet=json.loads(Path(assistant_review).read_text(encoding='utf8'))
        attach_semantic_reviews(report,packet)
    report['report_source_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
    write_new(out/'paired-evaluation.json',report)
    summary={k:v for k,v in report.items() if k not in ('members','pairs')}
    text=['# P3.9-R3 固定 A/B 真实实验','',
          '32封全部为已暴露虚构开发数据。失败保留分母；工程接受不代表语义正确。所有回复未审核、未发送。',
          '','```json',json.dumps(summary,ensure_ascii=False,indent=2),'```','',
          '七字段只与原24题研究者批准开发参考v1.1比较，各臂168字段/24邮件固定分母；策略/投影变化逐项提示，不把它称为独立准确率。',
          'Issue、证据语义、摘要回复18维为未签名候选；没有人类分数和独立AI Judge调用。实际账单未知，费用是收到用量按高峰未命中价格计算的保守估算。','']
    rows={(r['sample_id'],r['arm']):r for r in report['members']}
    html=['<!doctype html><html lang="zh"><meta charset="utf-8"><title>P3.9-R3 paired evaluation</title>',
          '<style>body{max-width:1300px;margin:30px auto;padding:20px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6fa;padding:15px}section{border-top:2px solid #bcd}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{min-width:0}table{border-collapse:collapse}td,th{border:1px solid #bcd;padding:8px}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>',
          '<h1>P3.9-R3 固定 A/B 真实实验</h1><p>虚构开发数据；失败保留分母；未审核、未发送；候选意见不是Human Gold。</p>',
          '<pre>'+escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>']
    for p in report['pairs']:
        member=rows.get((p['sample_id'],'A')) or rows.get((p['sample_id'],'B'))
        text += [f"## 第{p['pair']}对：{p['sample_id']}",'','```json',json.dumps(p,ensure_ascii=False,indent=2),'```','']
        html += [f"<section><h2>第{p['pair']}对：{escape(p['sample_id'])}</h2>"]
        if member:
            e=member['original_email'];text += ['### 原邮件','',e['subject'],'',e['body'],'']
            html += ['<h3>'+escape(e['subject'])+'</h3><pre>'+escape(e['body'])+'</pre>']
        html += ['<div class="pair">']
        for arm in ('A','B'):
            r=rows.get((p['sample_id'],arm))
            if not r:
                text += [f'### {arm} 未尝试',''];html += ['<div class="card"><h3>'+arm+' 未尝试</h3></div>'];continue
            text += [f"### {arm} {r['state']}",'','```json',json.dumps(r,ensure_ascii=False,indent=2),'```','']
            v=r['accepted_output'] or r['pre_gate_output'] or {}
            v=v if isinstance(v,dict) else {}
            summary_text=v.get('summary','无');reply=v.get('suggested_reply','无')
            summary_text=summary_text if isinstance(summary_text,str) else '非字符串摘要，见完整raw诊断'
            reply=reply if isinstance(reply,str) else '非字符串回复，见完整raw诊断'
            html += ['<div class="card"><h3>'+arm+' '+r['state']+'</h3><h4>摘要</h4><pre>'+escape(summary_text)+'</pre>',
                     '<h4>未审核回复草稿</h4><pre>'+escape(reply)+'</pre>',
                     '<h4>完整分析</h4><pre>'+escape(json.dumps(v,ensure_ascii=False,indent=2))+'</pre>',
                     '<h4>最早拒绝阶段</h4><pre>'+escape(json.dumps(r['diagnosis'],ensure_ascii=False,indent=2))+'</pre>']
            if 'assistant_semantic_review' in r:
                html+=['<h4>18维助手候选审核（非Human Gold）</h4><table><tr><th>维度</th><th>候选</th><th>具体意见</th></tr>']
                for key,item in r['assistant_semantic_review']['dimensions'].items():
                    html+=['<tr><td>'+escape(key)+'</td><td>'+escape(item['verdict_candidate'])+'</td><td>'+escape(item['ai_opinion'])+'</td></tr>']
                html+=['</table>']
            html+=['<details><summary>raw、候选证据、版本、用量和追溯</summary><pre>'+escape(json.dumps(r,ensure_ascii=False,indent=2))+'</pre></details></div>']
        html += ['</div></section>']
    html += ['</html>']
    with (out/'REPORT.md').open('x',encoding='utf8') as f:f.write('\n'.join(text))
    with (out/'REVIEW.html').open('x',encoding='utf8') as f:f.write('\n'.join(html))
    return summary
