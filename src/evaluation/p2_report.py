"""Deterministic pilot reporting from durable records; never calls models."""
import csv
import json
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from src.infrastructure.repository import Repository
from src.infrastructure.pilot_budget import PilotBudget

FIELDS=('sentiment','urgency','is_complaint','store_location','product_category','complaint_reason','source_attribution')

def percentile(values,p):
    if not values:return None
    values=sorted(values);position=(len(values)-1)*p
    low=int(position);high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(position-low)

def generate(root,space,fixture_path):
    cases=json.loads(Path(fixture_path).read_text(encoding='utf-8'))['cases']
    repo=Repository(space/'runs.sqlite3');budget=PilotBudget(space/'budget.sqlite3')
    runs=[r for r in repo.list_runs() if r.config.backend=='deepseek_live'];by_id={r.email.email_id:r for r in runs}
    from src.domain.contracts import EmailInput
    expected_hashes={c['email']['email_id']:EmailInput.model_validate(c['email']).input_hash for c in cases}
    if len(by_id)!=len(runs) or any(expected_hashes.get(r.email.email_id)!=r.input_hash for r in runs):
        raise ValueError('Pilot runs must uniquely match the frozen fixture IDs and hashes')
    attempted=[r for r in runs if any(a.metadata.get('dispatch') in ('started_or_unknown','response_received') for a in r.attempts)]
    attempts=[a for r in attempted for a in r.attempts if a.metadata.get('dispatch') in ('started_or_unknown','response_received')]
    accepted=[r for r in attempted if r.status=='succeeded']
    mismatch=[];scores={f:0 for f in FIELDS};rows=[];complete=0
    for case in cases:
        run=by_id.get(case['email']['email_id'])
        if run not in attempted:continue
        prediction=run.result.model_dump() if run.result else {}
        errors=[]
        for f in FIELDS:
            match=prediction.get(f)==case['expected'][f];scores[f]+=match
            if not match:
                errors.append(f);mismatch.append(dict(email_id=run.email.email_id,run_id=run.run_id,input_hash=run.input_hash,
                    field=f,expected=case['expected'][f],predicted=prediction.get(f),category=category(f)))
        complete+=not errors
        rows.append(dict(email_id=run.email.email_id,input_hash=run.input_hash,run_id=run.run_id,status=run.status,
            attempts=len(run.attempts),all_seven_match=not errors,elapsed_ms=run.metadata.get('elapsed_ms'),
            **{f:prediction.get(f) for f in FIELDS}))
    n=len(attempted);a=len(attempts)
    def rate(num,denom):return dict(numerator=num,denominator=denom,rate=num/denom if denom else None)
    timings=[t.elapsed_ms for t in attempts if t.elapsed_ms is not None]
    logical=[r.metadata['elapsed_ms'] for r in attempted if r.metadata.get('elapsed_ms') is not None]
    tokens={key:sum(t.metadata[key] for t in attempts if t.metadata.get(key) is not None) for key in ('input_tokens','output_tokens','total_tokens')}
    known_usage=sum(all(t.metadata.get(k) is not None for k in tokens) for t in attempts)
    known_cost=[t.metadata['cost_cny'] for t in attempts if t.metadata.get('cost_cny') is not None]
    errors=Counter(t.error.error_type for t in attempts if t.error)
    attempt_rows=[dict(email_id=r.email.email_id,run_id=r.run_id,attempt_no=t.attempt_no,
        started_at=t.started_at,finished_at=t.finished_at,elapsed_ms=t.elapsed_ms,stage=t.stage,
        parse_status=t.parse_status,contract_status=t.contract_status,normalization_status=t.normalization_status,
        business_status=t.business_status,error_type=t.error.error_type if t.error else None,
        **{key:t.metadata.get(key) for key in ('resolved_model','request_id','provider_response_id','finish_reason','input_tokens','output_tokens','total_tokens','cost_cny')})
        for r in attempted for t in r.attempts if t in attempts]
    result=dict(version='p2-pilot-report-v1',generated_at=datetime.now(timezone.utc).isoformat(),
        evaluation_type='developer-fixture preliminary evaluation; not independent blind human accuracy',
        planned_samples=len(cases),sent_samples=n,logical_runs=len(runs),attempt_records=a,budget=budget.summary(),
        requested_models=sorted({r.config.model_id for r in attempted}),resolved_models=sorted({t.metadata['resolved_model'] for t in attempts if t.metadata.get('resolved_model')}),
        model_snapshot='unavailable; returned model may be an alias, not fixed weights',
        first_attempt_success=sum(r.status=='succeeded' and len(r.attempts)==1 for r in attempted),
        success_after_retry=sum(r.status=='succeeded' and len(r.attempts)>1 for r in attempted),
        failures=sum(r.status=='failed' for r in attempted),uncertain=sum(r.status in ('running','interrupted_or_unknown') for r in attempted),errors=dict(errors),
        structure=dict(nonempty=rate(sum(bool(t.raw_output and t.raw_output.strip()) for t in attempts),a),
            json_parse=rate(sum(t.parse_status=='passed' for t in attempts),a),
            raw_schema=rate(sum(t.contract_status=='passed' for t in attempts),a),
            normalization=rate(sum(t.normalization_status=='identity' for t in attempts),a),
            semantic_warning=rate(sum(t.business_status=='warning' for t in attempts),a),accepted=rate(len(accepted),n),fallback=0),
        fields={f:rate(scores[f],n) for f in FIELDS},overall_fields=rate(sum(scores.values()),n*7),all_seven=rate(complete,n),
        mismatches=mismatch,per_email=rows,per_attempt=attempt_rows,
        latency_ms=dict(http=dict(n=len(timings),p50=percentile(timings,.5),p95=percentile(timings,.95)),
                        logical=dict(n=len(logical),p50=percentile(logical,.5),p95=percentile(logical,.95))),
        usage=dict(known_attempts=known_usage,total_attempts=a,known_token_subtotals=tokens,total_tokens=tokens['total_tokens'] if known_usage==a and a else None),
        cost=dict(known_attempts=len(known_cost),estimated_peak_upper_subtotal_cny=sum(known_cost) if known_cost else None,
            all_attempts_estimate_cny=sum(known_cost) if len(known_cost)==a and a else None,actual_billed_cny=None,
            source='https://api-docs.deepseek.com/zh-cn/quick_start/pricing/',input_peak_per_million=2,output_peak_per_million=8),
        limitations=['12 developer-designed synthetic examples, small sample; no production SLO or independent holdout claim.',
            'Logical elapsed measures orchestration after claim and before final transaction; UI submit-to-render timing is separately recorded in ui-evidence JSON.',
            'All failed sent samples stay in semantic denominators. Missing predictions are mismatches.',
            'Field comparison is exact, no post-hoc mapping or expected-label edits.',
            'HTTP count is durable dispatch reservation count; a crash can leave dispatch uncertain. SDK retries are zero.',
            'AppTest is not browser E2E. Draft reply factuality needs qualitative review.',
            'Confidence is uncalibrated; structure acceptance is not semantic correctness.'])
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    dest=root/'docs/p2/evidence'/('pilot-'+stamp);dest.mkdir(parents=True)
    (dest/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (dest/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['email_id']);writer.writeheader();writer.writerows(rows)
    with (dest/'mismatches.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['email_id','run_id','input_hash','field','expected','predicted','category']);writer.writeheader();writer.writerows(mismatch)
    with (dest/'attempts.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(attempt_rows[0]) if attempt_rows else ['run_id']);writer.writeheader();writer.writerows(attempt_rows)
    def display(r):return f"{r['numerator']}/{r['denominator']}"+(f" = {r['rate']:.2%}" if r['rate'] is not None else ' (unavailable)')
    text=['# P2 真实模型试点报告',f"生成时间：{result['generated_at']}。developer-fixture preliminary evaluation。",
        f"计划 {len(cases)} 封；实际发送 {n} 封；attempt {a}，预算账本预留 {budget.summary()['reserved_attempts']} 次。",
        f"首次成功 {result['first_attempt_success']}；重试后成功 {result['success_after_retry']}；失败 {result['failures']}；不确定 {result['uncertain']}。",
        f"模型请求：{result['requested_models']}；返回：{result['resolved_models']}；权重快照 unavailable。",
        '## 结构质量（响应指标分母为全部实际 attempt，accepted 分母为已发送邮件）',
        *[f"- {k}: {display(v)}" for k,v in result['structure'].items() if isinstance(v,dict)],'- fallback: 0',
        '## 七字段语义（分母包括发送失败的邮件；不包括未发送）',
        '| 字段 | 匹配 |','|---|---|',*[f'| {k} | {display(v)} |' for k,v in result['fields'].items()],
        f"整体字段：{display(result['overall_fields'])}；七字段全对邮件：{display(result['all_seven'])}。",
        '## 延迟、Token 与费用',f"毫秒，线性插值分位数：`{json.dumps(result['latency_ms'])}`。小样本，不可推广为生产 SLO。",
        f"Token：`{json.dumps(result['usage'])}`。",
        f"按官方高峰缓存未命中价格估算人民币：{result['cost']['all_attempts_estimate_cny']}；实际扣费 unknown。",
        f"持久预留费用上界：{budget.summary()['reserved_upper_cny']:.6f} 元（不退款释放预留，防止重试超额）。",
        '[官方计价来源](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)，核查日期2026-10-15。',
        '## Bad cases',*[f"- {m['email_id']} / {m['field']}: expected={m['expected']!r}, prediction={m['predicted']!r}; {m['category']}" for m in mismatch],
        '无七字段 mismatch。' if not mismatch else '原因假设及回复事实审阅见本目录上级的 LIVE_REVIEW.md；未修改 expected 或映射消除错误。',
        '## 证据与限制','原文、原始响应、解析、规范结果和每次 attempt 在本机 `.local/p2-pilot-v1/runs.sqlite3`；冻结 manifest/fixtures/prompt 和 run JSON 同目录。',
        *['- '+s for s in result['limitations']]]
    (dest/'REPORT.md').write_text('\n\n'.join(text).replace('|\n\n|','|\n|')+'\n',encoding='utf-8')
    return str(dest)

def category(field):
    return {'sentiment':'情绪理解','urgency':'紧急程度','product_category':'类别边界','source_attribution':'来源归因',
            'store_location':'不确定性或事实提取','complaint_reason':'主要问题分类','is_complaint':'投诉判断'}[field]
