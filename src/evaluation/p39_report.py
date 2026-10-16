"""Offline paired reporting; signed semantic judgments remain absent."""
from collections import Counter
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from src.domain.contracts import digest
from src.domain.analysis_v31 import AnalysisV31,stored_analysis
from src.infrastructure.dashboard_sources import ReadOnlyRepository
from src.evaluation.semantic_review_v2 import GUIDANCE
from src.application.reply_review import inspect_reply
from src.application.research_policy_v2 import language,requested_language
from src.evaluation.e2e_v3 import SEVEN
from src.evaluation.p2_report import percentile


def candidate_review(run):
    actual=stored_analysis(run).model_dump() if run.result else None
    raw=run.attempts[-1].parsed_output if run.attempts else None
    value=actual or raw
    reply=value.get('suggested_reply','') if isinstance(value,dict) else ''
    source_lang=requested_language(run.email.body);reply_lang=language(reply) if reply else 'unknown'
    gate=inspect_reply(reply)
    dimensions={k:dict(verdict_candidate='UNVERIFIED',ai_opinion=v+' 本次输出需逐项审核。',human_score=None,
                      human_critical_error=None,evidence_source='original email + pre-gate output',evidence_quote=run.email.body)
                for k,v in GUIDANCE.items()}
    if not actual:
        for item in dimensions.values():item.update(accepted_output_applicability='NOT_APPLICABLE_NO_ACCEPTED_OUTPUT')
    if reply:
        d=dimensions['reply_language'];match=source_lang==reply_lang or source_lang=='bilingual'
        d.update(verdict_candidate='PASS_VISIBLE_EVIDENCE' if match else 'MAJOR',ai_opinion=f'词面语言候选：来信要求/主语言={source_lang}，回复={reply_lang}。语言词面检查不能代替上下文判断。',evidence_quote=reply,evidence_source='raw suggested_reply')
        for k in ('invented_actions','material_promises'):
            findings=[f for f in gate['findings'] if (f['kind'] in ('executed_action','approval_claim'))==(k=='invented_actions')]
            dimensions[k].update(verdict_candidate='MAJOR' if findings else 'UNVERIFIED',
                ai_opinion='词面门禁发现：'+json.dumps(findings,ensure_ascii=False) if findings else '词面门禁未见信号；虚构动作/承诺仍需逐句语义审核。',evidence_quote=reply,evidence_source='raw suggested_reply')
        mechanical=any(s in reply.lower() for s in ('system prompt','cannot directly','unable to directly','无法在此','无权','系统提示'))
        dimensions['mechanical_disclaimer'].update(verdict_candidate='MINOR' if mechanical else 'UNVERIFIED',
            ai_opinion='检测到能力/系统免责声明词面，请检查是否影响有用性。' if mechanical else '未见已列举免责声明词面；是否机械仍需内容判断。',evidence_quote=reply,evidence_source='raw suggested_reply')
    if actual:
        dimensions['evidence_support'].update(ai_opinion='原文跨度工程验证已通过；每个标签的语义支持仍待人工。',
            evidence_quote=json.dumps([i['evidence'] for i in actual['issues']],ensure_ascii=False),evidence_source='accepted issues.evidence')
    return dict(dimensions=dimensions,gate=gate,source_language_candidate=source_lang,reply_language_candidate=reply_lang,
                critical_errors_human=None,content_semantics_human=None,reply_status='unreviewed_unsent',ai_opinions_only=True)


def evaluate(m,runs,refs):
    by={};inputs={x['email']['email_id']:x for x in m['inputs']};members=[]
    if set(refs)!={k for k,v in inputs.items() if v['group']=='frozen24'}:raise ValueError('Frozen reference coverage mismatch')
    for id,ref in refs.items():
        if digest(ref)!=inputs[id]['source_hash'] or ref['email']!=inputs[id]['email']:raise ValueError('Frozen reference identity drift')
    for r in runs:
        arm=r.config.parameters['arm'];key=(r.email.email_id,arm)
        if key in by or r.email.model_dump()!=inputs[r.email.email_id]['email'] or r.config.model_dump()!=m['configs'][arm]:raise ValueError('Run/cohort identity mismatch')
        if r.result:stored_analysis(r)
        by[key]=r
    arms={}
    for arm in ('A','B'):
        selected=[r for r in runs if r.config.parameters['arm']==arm];attempts=[a for r in selected for a in r.attempts]
        lat=[a.elapsed_ms for a in attempts if a.elapsed_ms is not None]
        logic_lat=[r.metadata['elapsed_ms'] for r in selected if r.metadata.get('elapsed_ms') is not None]
        field={k:dict(agreement=0,observed_reference_fields=0,planned_reference_fields=24,policy_conflicts=[]) for k in SEVEN}
        all7=0;reference_observed=0
        for r in selected:
            if r.email.email_id not in refs:continue
            reference_observed+=1;expected=refs[r.email.email_id]['expected'];checks=[]
            for k in SEVEN:
                agree=bool(r.result and getattr(r.result,k)==expected[k]);checks.append(agree)
                field[k]['agreement']+=agree;field[k]['observed_reference_fields']+=1
                if k=='urgency' and r.email.email_id=='p25-no_object':
                    field[k]['policy_conflicts'].append(dict(sample_id=r.email.email_id,old_expected=expected[k],new_policy='medium',count_as_new_policy_error=False))
            all7+=all(checks)
        costs=[a.metadata.get('cost_cny') for a in attempts];known=sum(c for c in costs if c is not None)
        arms[arm]=dict(planned_requests=32,attempted=len(attempts),accepted=sum(r.status=='succeeded' for r in selected),
            failed=sum(r.status=='failed' for r in selected),interrupted_or_unknown=sum(r.status=='interrupted_or_unknown' for r in selected),
            not_attempted=32-len(selected),response_received=sum(a.raw_output is not None for a in attempts),fallback=0,
            field_consistency=field,old_seven_consistency=dict(agreement=sum(d['agreement'] for d in field.values()),fixed_denominator=168,
                observed_reference_fields=reference_observed*7,unattempted_reference_fields=(24-reference_observed)*7,
                failed_reference_fields=sum(7 for r in selected if r.email.email_id in refs and not r.result),
                all_seven_agreement=all7,fixed_email_denominator=24,observed_reference_emails=reference_observed,
                semantic_accuracy=None,caveat='Historical development consistency only; all changed policy/projection fields separately qualified'),
            provider_p50_ms=percentile(lat,.5),provider_p95_ms=percentile(lat,.95),provider_n=len(lat),
            service_p50_ms=percentile(logic_lat,.5),service_p95_ms=percentile(logic_lat,.95),service_n=len(logic_lat),
            observed_input_tokens=sum(a.metadata.get('input_tokens') or 0 for a in attempts),
            observed_output_tokens=sum(a.metadata.get('output_tokens') or 0 for a in attempts),
            observed_total_tokens=sum(a.metadata.get('total_tokens') or 0 for a in attempts),
            cache_hit_tokens_known=sum(a.metadata.get('cache_hit_tokens') or 0 for a in attempts),
            cache_hit_unknown_attempts=sum(a.metadata.get('cache_hit_tokens') is None for a in attempts),
            cache_miss_tokens_known=sum(a.metadata.get('cache_miss_tokens') or 0 for a in attempts),
            cache_miss_unknown_attempts=sum(a.metadata.get('cache_miss_tokens') is None for a in attempts),
            known_peak_miss_cost_subtotal_cny=known,estimated_cost_cny=None if any(c is None for c in costs) else known,
            cost_unknown_attempts=sum(c is None for c in costs),actual_invoice_cost_cny=None,
            resolved_models=dict(Counter(a.metadata.get('resolved_model') for a in attempts)),
            issue_semantic_accuracy=None,evidence_semantic_accuracy=None,summary_reply_quality_human=None)
    for row in m['inputs']:
        for arm in ('A','B'):
            run=by.get((row['email']['email_id'],arm))
            if not run:continue
            actual=stored_analysis(run).model_dump() if run.result else None
            raw=run.attempts[-1].parsed_output if run.attempts else None
            try:
                AnalysisV31.model_validate(raw);pre_gate_schema='passed'
            except (ValueError,TypeError):pre_gate_schema='failed'
            members.append(dict(sample_id=run.email.email_id,arm=arm,run_id=run.run_id,input_hash=run.input_hash,
                config_hash=digest(run.config.model_dump()),output_hash=run.metadata.get('analysis_v31_hash'),
                raw_hashes=[digest(a.raw_output) for a in run.attempts],state=run.status,original_email=run.email.model_dump(),
                pre_gate_schema=pre_gate_schema,pre_gate_output=raw,accepted_output=actual,
                attempts=[a.model_dump() for a in run.attempts],review=candidate_review(run)))
    pairs=[]
    for step in m['schedule'][::2]:
        id=m['inputs'][step['input_index']]['email']['email_id'];values={}
        for arm in ('A','B'):
            r=by.get((id,arm));v=stored_analysis(r) if r and r.result else None
            values[arm]=dict(state=r.status if r else 'not_attempted',run_id=r.run_id if r else None,
                            issue_count=len(v.issues) if v else None,urgency=v.urgency if v else None,
                            summary=v.summary if v else None,reply=v.suggested_reply if v else None)
        pairs.append(dict(pair=step['pair'],sample_id=id,phase=step['phase'],**values,
            issue_count_difference=(values['B']['issue_count']-values['A']['issue_count']) if all(values[a]['issue_count'] is not None for a in ('A','B')) else None,
            semantic_winner=None,human_judgment=None))
    return dict(version='p39-paired-report-v1',manifest_hash=m['manifest_hash'],arms=arms,members=members,pairs=pairs,
        planned_requests=64,actual_attempts=sum(a['attempted'] for a in arms.values()),
        not_attempted=sum(a['not_attempted'] for a in arms.values()),human_semantic_judgment='PENDING',independent_holdout='PENDING',
        field_applicability=dict(sentiment='old development consistency; mixed→unknown projection loss',
            urgency='policy v2 changed; pure help old low/new medium is explicit conflict',is_complaint='unknown projects false with diagnostics',
            store_location='new safe uncertainty projection differs',product_category='customer-primary projection differs',
            complaint_reason='billing/size have lossy v2 other projection',source_attribution='new safe projection; not verified liability'),
        historical_p36='143/168;17/24;29/32 frozen, different schema, not a direct improvement comparison')


def export_report(m,runtime,archive_path):
    runtime=Path(runtime);version=1
    while (runtime/f'review-v{version}').exists():version+=1
    report_dir=runtime/f'review-v{version}';report_dir.mkdir(exist_ok=False)
    runs=ReadOnlyRepository(runtime/'runs.sqlite3').list_runs()
    root=Path(__file__).resolve().parents[2]
    refs=json.loads((root/'.local/p38/prepared-final-v4/old-reference-v1.1.json').read_text(encoding='utf8'))
    report=evaluate(m,runs,refs)
    receipt_path=runtime/'smoke-receipt.json'
    receipt=json.loads(receipt_path.read_text(encoding='utf8')) if receipt_path.exists() else None
    report.update(smoke_receipt_hash=digest(receipt) if receipt else None,
                  content_archive_hash=json.loads(Path(archive_path).read_text(encoding='utf8'))['archive_hash'],
                  report_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                  smoke_status='AB_SMOKE_REAL_VERIFIED' if receipt else 'AB_SMOKE_STOPPED_BEFORE_GATE')
    with (report_dir/'paired-evaluation.json').open('x',encoding='utf8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    gate_message=('剩余28对尚未执行，等待研究者批准内容安全。请选择“批准继续”或“拒绝/要求修复”，并绑定上述完整hash。'
                  if receipt else '冒烟尚未完成，因失败即停条件锁止。没有冒烟通过收据，不能批准remaining。本包仅供失败审阅；继续需研究者明确决定新版本或有记录复验的范围，不能代替4对内容安全批准。')
    text=['# P3.9 真实冒烟内容与安全审核包','',
          '全部为开发暴露虚构邮件；以下18维是AI候选意见。工程接受、内容可采纳和真实发送许可分别判断；所有草稿未审核、未发送。',
          '','冒烟收据 hash：`'+str(report['smoke_receipt_hash'])+'`','',
          gate_message,'',
          '人工评分、Issue Gold、证据语义、摘要回复质量及A/B语义胜负均pending。','']
    summary=[]
    for arm,s in report['arms'].items():
        summary.append(f"{arm}：计划32，尝试{s['attempted']}，接受{s['accepted']}，失败{s['failed']}，未知发送{s['interrupted_or_unknown']}，未尝试{s['not_attempted']}；tokens={s['observed_total_tokens']}；高峰未命中估算¥{s['known_peak_miss_cost_subtotal_cny']:.6f}；实际账单未知。")
    text+=summary+['','## 性能与字段一致性','',json.dumps(report['arms'],ensure_ascii=False,indent=2),'']
    by={(r['sample_id'],r['arm']):r for r in report['members']}
    for pair in report['pairs']:
        if not any((pair['sample_id'],a) in by for a in ('A','B')):continue
        member=by.get((pair['sample_id'],'A')) or by[pair['sample_id'],'B'];e=member['original_email']
        text += [f"## 第{pair['pair']}对：{pair['sample_id']}",'',f"主题：{e['subject']}",'','### 原邮件','',e['body'],'']
        for arm in ('A','B'):
            r=by.get((pair['sample_id'],arm))
            if not r:text += [f'### {arm} 尚未尝试',''];continue
            v=r['accepted_output'] or r['pre_gate_output'] or {}
            text += [f"### {arm}：{r['state']}",'',f"run_id：`{r['run_id']}`；input：`{r['input_hash']}`；output：`{r['output_hash']}`",'',
                     '**摘要**','',v.get('summary','无可读摘要'),'', '**回复草稿**','',v.get('suggested_reply','无可读回复'),'',
                     '**完整分析（含Issue字段、证据跨度、风险、客户重要性、业务顺序、关系）**','',
                     '```json',json.dumps(v,ensure_ascii=False,indent=2),'```','',
                     '**18维自动候选与关键错误**','', '|维度|候选等级|可核查意见|','|---|---|---|']
            for key,item in r['review']['dimensions'].items():text.append('|'+key+'|'+item['verdict_candidate']+'|'+item['ai_opinion'].replace('|','/').replace('\n',' ')+'|')
            text += ['','原始attempt（gate前、错误、用量、实际模型、预留与payload hash）：','', '```json',json.dumps(r['attempts'],ensure_ascii=False,indent=2),'```','']
    with (report_dir/'SMOKE_REVIEW.md').open('x',encoding='utf8') as f:f.write('\n'.join(text))
    # Standalone readable HTML keeps complete pre/post-gate evidence locally.
    blocks=['<!doctype html><html lang="zh"><meta charset="utf-8"><title>P3.9冒烟内容审核</title><style>body{max-width:1280px;margin:32px auto;padding:0 24px;font:16px/1.6 system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6fa;padding:16px}section{border-top:2px solid #ccd;padding:24px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}.card{min-width:0;background:#fafbfc;padding:18px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:8px}code{overflow-wrap:anywhere}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>',
            '<h1>P3.9 真实冒烟审核包</h1><p>工程结果与内容质量分别审核；全部未审核、未发送。18维为AI候选，不能代签人类批准。</p>',
            '<p>冒烟收据 hash：<code>'+escape(str(report['smoke_receipt_hash']))+'</code></p>',
            '<p>'+escape(gate_message)+'</p>',
            '<pre>'+escape('\n'.join(summary))+'</pre>']
    for pair in report['pairs']:
        if not any((pair['sample_id'],a) in by for a in ('A','B')):continue
        r=by.get((pair['sample_id'],'A')) or by[pair['sample_id'],'B'];e=r['original_email']
        blocks+=['<section><h2>第'+str(pair['pair'])+'对：'+escape(pair['sample_id'])+'</h2><h3>'+escape(e['subject'])+'</h3><pre>'+escape(e['body'])+'</pre><div class="pair">']
        for arm in ('A','B'):
            r=by.get((pair['sample_id'],arm))
            if not r:blocks+=['<div class="card"><h3>'+arm+' 尚未尝试</h3></div>'];continue
            v=r['accepted_output'] or r['pre_gate_output'] or {}
            blocks+=['<div class="card"><h3>'+arm+' · '+escape(r['state'])+'</h3><p>run_id：'+r['run_id']+'</p><h4>摘要</h4><pre>'+escape(v.get('summary','无'))+'</pre><h4>回复草稿</h4><pre>'+escape(v.get('suggested_reply','无'))+'</pre><h4>问题、原文证据及完整分析</h4><pre>'+escape(json.dumps(v,ensure_ascii=False,indent=2))+'</pre><h4>18维候选审核</h4><table><tr><th>维度</th><th>候选</th><th>意见</th></tr>']
            for key,item in r['review']['dimensions'].items():blocks+=['<tr><td>'+escape(key)+'</td><td>'+item['verdict_candidate']+'</td><td>'+escape(item['ai_opinion'])+'</td></tr>']
            blocks+=['</table><details><summary>raw、用量与来源hash</summary><pre>'+escape(json.dumps(r['attempts'],ensure_ascii=False,indent=2))+'</pre></details></div>']
        blocks+=['</div></section>']
    blocks+=['<h2>32对完整状态、分母、性能与成本</h2><pre>'+escape(json.dumps({k:v for k,v in report.items() if k!='members'},ensure_ascii=False,indent=2))+'</pre></html>']
    with (report_dir/'SMOKE_REVIEW.html').open('x',encoding='utf8') as f:f.write('\n'.join(blocks))
    return dict(actual_attempts=report['actual_attempts'],not_attempted=report['not_attempted'],
                smoke_receipt_hash=report['smoke_receipt_hash'],review_path=str(report_dir/'SMOKE_REVIEW.html'),human_approved=False)
