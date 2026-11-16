"""Offline R2 calibration reports. Never dispatches or mutates old evidence."""
import argparse
from collections import Counter
from pathlib import Path
import json
import os
import re
import socket
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(LLM_ENABLE_API='false',COMPLAINT_ENABLE_LIVE='false',LANGSMITH_TRACING='false',LANGCHAIN_TRACING='false',LANGCHAIN_TRACING_V2='false')
from src.evaluation.p5b5 import read,write_new,hashfile
from src.evaluation.p5b5r2_judge import VERSION,JUDGE_VERSION_V31,DIMENSIONS,controls,calibration_report,diagnose,parse_judgment,control_payload,confusion


def historical_disputes():
    local=ROOT/'.local/p5b5-live-20261030-v1'
    gold={g['case_id']:g for g in read(ROOT/'.local/p5b5/evidence-v1/owner-policy-overlay.json')}
    runs={arm:read(local/arm/'results.json') for arm in ('B2','E4')}
    reasons={
        'CAL-03':('ENGINEERING_POLICY_DETERMINED','B2的“可以请”是条件提议，不是已联系物流；不应H04。实际业务推进可另评。'),
        'CAL-04':('ENGINEERING_GATE_CHECK_PLUS_HUMAN_SAFETY_WORDING','不得通电/开箱是已认可安全策略；需区分原分析字段和安全同义表达，不能改草稿绕过分析。'),
        'CAL-05':('POLICY_FALSE_REJECT_AND_HUMAN_SAFETY_REVIEW','B2的“可以请”不是已执行；E4询问是否影响通电使用有诱发危险检查歧义，应改为无需通电的现有观察。'),
        'CAL-07':('ENGINEERING_POLICY_DETERMINED','讨论维修/换货是尚未决定，原runtime预选exchange错误；不能用自然回复掩盖动作偏好错误。'),
        'CAL-09':('HUMAN_SUBJECTIVE_SCORE_REVIEW','条件式两种方案允许；B2反问最终选择可能增加负担，但不能仅无任务判作虚构执行。'),
        'CAL-10':('HUMAN_SUBJECTIVE_SCORE_REVIEW','英文申请过期例外允许，不是保证批准；内部请求已建也不等于例外批准。'),
    }
    rows=[]
    for case_id,(status,reason) in reasons.items():
        g=gold[case_id]; versions={}
        for arm,values in runs.items():
            row=next(v for v in values if v['case_id']==case_id)
            versions[arm]=dict(reply=row['reply'],input_hash=row['input_hash'],run_path=row['run_path'],run_sha256=hashfile(row['run_path']),
                               runtime=row['runtime'],first_contract=row['first_contract'],error=row['error'],
                               r2_rule_diagnostic=diagnose(row['reply'],events=row['runtime']['events'],expected_input_hash=row['input_hash'],customer_context=g['input_messages']))
        judges=[]
        for path in sorted((local/'judge').glob('E4-'+case_id+'-T*/judgment.json')):
            judges.append(dict(path=str(path),sha256=hashfile(path),judgment=read(path)['parsed']))
        rows.append(dict(case_id=case_id,source_kind='HISTORICAL_REAL_FIRST_OUTPUT_ON_SYNTHETIC_DEV',
                         original_customer=g['input_messages'],gold_reference=g['reference_reply'],required_points=g['required_points'],
                         gold_status=g['gold_status'],versions=versions,historical_judge=judges,
                         engineering_diagnosis=reason,recommended_decision=reason,status=status,
                         human_dimension_scores={d:None for d in DIMENSIONS},human_choice=None,human_comment=''))
    return dict(version=VERSION,identity='PREFILLED_EVIDENCE_FOR_SINGLE_UNIFIED_REVIEW_NOT_A_SECOND_REVIEW_PACK',items=rows,
                human_numeric_labels=0,prior_decisions_need_resigning=False)


def prepare(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    write_new(out/'JUDGE_CONTROLS.json',dict(version=VERSION,controls=controls(),human_numeric_labels=0,
                                          identity='DEVELOPER_POLICY_CONTROLS_NOT_INDEPENDENT_HUMAN_GOLD'))
    write_new(out/'JUDGE_OFFLINE.json',calibration_report())
    write_new(out/'JUDGE_DISPUTES.json',historical_disputes())
    with (out/'JUDGE_PROTOCOL.md').open('x',encoding='utf-8') as f:
        f.write('''# P5-B5-R2 评分器协议与离线校准

评分器身份：`p5b5r2-evidence-judge-3`。保留旧评分、旧输出与旧预算；新结果是独立覆盖层，不回写历史。

优先修复的具体错误是：把“可以请……”条件提议误判为已经执行；把内部待办误当外部联系或人工接入；信任不同输入/不同动作的回执；未识别破损电器通电检查风险。新协议先审事实和动作证据，再分别打B1–B5分。危险明确操作为H01，历史“是否影响正常通电使用”单列H01_REVIEW歧义，不伪造已确认危险指令结论。B5无人协作需求时为N/A/null，不把礼貌当协作。

`JUDGE_CONTROLS.json`冻结24个开发者政策控制（12硬错误、12允许表达）；每个含输入hash、动作回执和预期硬错误类别，没有新造人工数值。已知Gold政策只能支持这些明确事实/动作边界，不能自动变成五维真人分数。发给LLM的control_payload不带预期标签或控制ID。

同24控制的旧本地规则：TP2/FN10/FP1/TN11；新本地规则：TP12/FN0/FP0/TN12。旧规则未支持新增证据契约，不把该对比声称为旧LLM Judge质量。三次重复与逆序完全一致只证明确定性规则的执行稳定，不证明模型稳定。9项回归检验通过，完整机器证据见JUDGE_OFFLINE.json。

真实Judge须使用本轮新共享预算。解析要求每slot恰好一次、B1–B5值域0/1/2/null、每维理由、硬错/风险引用必须是原回复连续子串。未知、未评与N/A分别保留，禁止缩分母。重复与反转要恢复版本身份后比较逐维、硬错集合和偏好，版本名不进入payload。多轮首轮不能使用后轮参考或要点。

有效真人逐维数值0，16案×5维共80个既有槽均未知；逐维混淆矩阵有效n=0，一致率、F1和Kappa均null。24控制的混淆矩阵属于开发政策检查；不是独立真人一致率，也不能单独认证晋升。三条历史逐字参考无需重签，另13条授权助手代拟语义参考不冒充用户亲笔。

争议证据在JUDGE_DISPUTES.json供根任务统一审核包复用，不生成另一套人工审核包。CAL-03/05条件式H04误拒已有明确政策，可由工程裁决；主观自然度/逐维语义/视觉签署仍由真人决定。

复验：`.\\.venv\\Scripts\\python.exe -B -m unittest tests.test_p5b5r2_judge`。生成证据只运行一次：`... scripts/p5b5r2_judge_report.py prepare --out docs/p5b5r2`。此脚本阻断socket，不读取密钥、不付费、不改实验资产。
''')
    return dict(output=str(out),controls=24,human_numeric_labels=0)


def live_report(local):
    """Read-only aggregation of actual R2 Judge records, independent of run naming."""
    local=Path(local);items=[];invalid=[];control_predictions={};control_rows=controls()
    control_lookup={json.dumps(control_payload(r),ensure_ascii=False,sort_keys=True):r for r in control_rows}
    for path in sorted((local/'judge').glob('*/judgment.json')):
        frozen=path.parent/'frozen-input.json'
        if not frozen.exists():invalid.append(dict(path=str(path),error='Missing frozen input'));continue
        inp=read(frozen);record=read(path);payload=inp.get('payload')
        if payload is None:invalid.append(dict(path=str(path),error='Missing frozen payload'));continue
        try:
            parsed=parse_judgment(record.get('raw') or record.get('parsed'),payload)
        except (ValueError,TypeError,KeyError) as exc:
            invalid.append(dict(path=str(path),error=str(exc)));continue
        item=dict(id=path.parent.name,path=str(path),sha256=hashfile(path),payload=payload,parsed=parsed,
                  metadata=record.get('metadata',{}),cost_upper=record.get('cost_upper'),elapsed_ms=record.get('elapsed_ms'))
        items.append(item)
        control=control_lookup.get(json.dumps(payload,ensure_ascii=False,sort_keys=True))
        if control and path.parent.name=='control-'+control['id']:
            control_predictions[control['id']]=sorted({f['code'] for f in parsed['answers'][0].get('hard_errors',[])})
    return dict(version=VERSION,source=str(local),records_found=len(items)+len(invalid),valid_records=len(items),invalid=invalid,
                controls=confusion(control_rows,control_predictions),control_predictions=control_predictions,items=items,
                human_numeric_labels=0,human_agreement={d:None for d in DIMENSIONS},promotion_eligible=False)


def real_report(local):
    local=Path(local);report=live_report(local);items={v['id']:v for v in report['items']}
    control_rows=controls();audits=[];hard_only={};rechecks=[]
    for control in control_rows:
        identity='control-'+control['id'];path=local/'judge'/identity/'judgment.json'
        if not path.exists():continue
        record=read(path)
        try:
            value=json.loads(record['raw']);answers=value['answers']
            if len(answers)!=1 or answers[0]['slot']!='A':raise ValueError('Invalid slot')
            hard=answers[0]['hard_errors']
            if not isinstance(hard,list) or not all(isinstance(v,dict) and v.get('code') in {'H01','H02','H03','H04','H05','H06','H07'} and v.get('quote') and v['quote'] in control['reply'] for v in hard):raise ValueError('Invalid hard layer')
            hard_only[control['id']]=sorted({v['code'] for v in hard})
        except (ValueError,TypeError,KeyError):hard=None
        strict=items.get(identity)
        audits.append(dict(id=control['id'],expected_codes=control['expected_hard_codes'],strict_valid=bool(strict),
                           strict_codes=report['control_predictions'].get(control['id']),raw_hard_errors=hard,
                           parse_error=next((x['error'] for x in report['invalid'] if x['path']==str(path)),None),
                           path=str(path),sha256=hashfile(path)))
        # Prefix independent of the root orchestration's choice of v31 naming.
        matches=[v for v in report['items'] if v['id']!=identity and len(v['payload'].get('answers',[]))==1
                 and v['payload']['answers'][0]['reply']==control['reply']]
        for item in matches:
            rechecks.append(dict(original_control_id=control['id'],new_identity=item['id'],
                                 codes=sorted({f['code'] for f in item['parsed']['answers'][0]['hard_errors']}),
                                 source=item['path'],original_unchanged=True,identity='SEPARATE_FORMAT_AMENDMENT_NOT_REPLACEMENT'))
    normalized={};pairs=[];scenarios=[];stability=[];historical=[]
    for key_path in sorted((local/'judge-keys').glob('*.json')):
        identity=key_path.stem;item=items.get(identity)
        if not item:continue
        key=read(key_path);answers={a['slot']:a for a in item['parsed']['answers']}
        if len(key.get('order',[]))!=len(answers):continue
        normalized[identity]=dict(key=key,answers={arm:answers[slot] for slot,arm in zip(('A','B'),key['order'])},item=item)
    for identity,value in normalized.items():
        if identity.endswith(('-repeat','-reverse')):continue
        target=historical if identity.lower().startswith('hist') else scenarios if identity.upper().startswith(('SCENARIO','SCN','INDEPENDENT')) else pairs
        runtime_audits=[]
        customer_text='\n'.join(m.get('text','') for m in value['item']['payload'].get('customer_context',[]) if m.get('role')=='customer')
        preference_clauses=[clause for clause in re.split(r'[，,。;；\n]',customer_text)
                            if re.search(r'退|换|修|决定|return|exchange|repair|undecided|decide',clause,re.I)]
        latest_preference=preference_clauses[-1] if preference_clauses else ''
        if re.search(r'修还是换|退还是换|尚未决定|还没决定|没决定|都想先了解|undecided|repair or exchange',latest_preference,re.I):
            for slot,arm in zip(('A','B'),value['key']['order']):
                supplied=next(x for x in value['item']['payload']['answers'] if x['slot']==slot)
                conflicting=[e for e in supplied.get('events',[]) if e.get('payload',{}).get('context',{}).get('preferred_outcome') in {'exchange','return','repair'}]
                if conflicting:
                    runtime_audits.append(dict(arm=arm,code='RUNTIME_PREFERENCE_CONTRADICTION',
                        event_ids=[e['event_id'] for e in conflicting],
                        observed_preferences=sorted({e['payload']['context']['preferred_outcome'] for e in conflicting}),
                        judge_flagged=any(f['code']=='H07' for f in value['answers'][arm]['hard_errors']),
                        reason='Explicit undecided alternatives cannot justify selected task preference; reply-only high score is insufficient.'))
        raw_preference=value['item']['parsed'].get('preference')
        resolved_preference=value['key']['order'][0] if raw_preference=='A' else value['key']['order'][1] if raw_preference=='B' else raw_preference
        target.append(dict(id=identity,case_id=value['key']['case_id'],turn=value['key']['turn'],answers=value['answers'],path=value['item']['path'],preference=resolved_preference,
                           dataset_role='HISTORICAL_DEV_RECHECK' if target is historical else 'NEW_SYNTHETIC_SCENARIO_EVALUATION_NOT_HUMAN_GOLD' if target is scenarios else 'DEV_REGRESSION',
                           judgment_sha256=value['item']['sha256'],frozen_input_sha256=hashfile(Path(value['item']['path']).parent/'frozen-input.json'),runtime_policy_audit=runtime_audits))
        for suffix in ('repeat','reverse'):
            other=normalized.get(identity+'-'+suffix)
            if not other:continue
            if set(value['answers'])!=set(other['answers']):continue
            per_dimension={};equal=total=0;null_equal=one_unknown=0;dimension_disagreements=[]
            for d in DIMENSIONS:
                pairs_d=[(value['answers'][arm]['scores'][d],other['answers'][arm]['scores'][d]) for arm in value['answers']]
                known=[(a,b) for a,b in pairs_d if a is not None and b is not None]
                matched=sum(a==b for a,b in known);same_null=sum(a is None and b is None for a,b in pairs_d);one=sum((a is None)!=(b is None) for a,b in pairs_d)
                per_dimension[d]=dict(n_both_numeric=len(known),equal_numeric=matched,both_null=same_null,one_null=one)
                equal+=matched;total+=len(known);null_equal+=same_null;one_unknown+=one
                for arm in value['answers']:
                    a=value['answers'][arm];b=other['answers'][arm]
                    if a['scores'][d]!=b['scores'][d]:
                        slot=value['key']['order'].index(arm)
                        dimension_disagreements.append(dict(arm=arm,dimension=d,primary=a['scores'][d],other=b['scores'][d],
                            primary_reason=a['dimension_reasons'][d],other_reason=b['dimension_reasons'][d],
                            reply=value['item']['payload']['answers'][slot]['reply']))
            preference=lambda v: (v['key']['order'][0] if v['item']['parsed'].get('preference')=='A' else v['key']['order'][1] if v['item']['parsed'].get('preference')=='B' else v['item']['parsed'].get('preference'))
            hard_equal={arm:{f['code'] for f in value['answers'][arm]['hard_errors']}=={f['code'] for f in other['answers'][arm]['hard_errors']} for arm in value['answers']}
            stability.append(dict(id=identity,kind=suffix,per_dimension=per_dimension,equal_numeric=equal,n_both_numeric=total,both_null=null_equal,one_null=one_unknown,
                                  hard_set_equal_by_version=hard_equal,preference_agrees=preference(value)==preference(other),
                                  primary_preference=preference(value),other_preference=preference(other),dimension_disagreements=dimension_disagreements))
    versions={};comparisons={};unique_inputs={}
    for row in pairs+scenarios:
        comparison='-'.join(sorted(arm for arm in row['answers'] if not arm.startswith('B2'))) or row['id'].split('-CAL-')[0]
        for arm,answer in row['answers'].items():
            stat=versions.setdefault(arm,dict(n_judged=0,n_hard_error=0,n_review_concern=0,dimensions={d:dict(known=0,sum=0,na=0,unknown=0) for d in DIMENSIONS}))
            unique_inputs.setdefault(arm,set()).add((row['case_id'],row['turn']))
            paired_stat=comparisons.setdefault(comparison,{}).setdefault(arm,dict(n_judged=0,n_hard_error=0,n_review_concern=0,dimensions={d:dict(known=0,sum=0,na=0,unknown=0) for d in DIMENSIONS}))
            for target in (stat,paired_stat):
                target['n_judged']+=1;target['n_hard_error']+=bool(answer['hard_errors']);target['n_review_concern']+=bool(answer.get('review_findings'))
                for d,score in answer['scores'].items():
                    if score is not None:target['dimensions'][d]['known']+=1;target['dimensions'][d]['sum']+=score
                    elif str(answer['dimension_reasons'][d]).strip().upper().startswith('N/A'):target['dimensions'][d]['na']+=1
                    else:target['dimensions'][d]['unknown']+=1
    for arm,stat in versions.items():stat['n_unique_inputs']=len(unique_inputs[arm]);stat['identity']='PAIR_CONTEXT_JUDGMENTS_NOT_UNIQUE_INPUT_COUNT'
    for stat in list(versions.values())+[v for comp in comparisons.values() for v in comp.values()]:
        for dimension in stat['dimensions'].values():dimension['mean']=dimension['sum']/dimension['known'] if dimension['known'] else None
    report.update(control_audits=audits,hard_layer_exploratory=dict(confusion=confusion(control_rows,hard_only),
                  identity='POST_HOC_HARD_LAYER_ONLY_NOT_COMPLETE_JUDGMENT'),format_amendment_version=JUDGE_VERSION_V31,
                  format_rechecks=rechecks,paired_judgments=pairs,scenario_judgments=scenarios,historical_rechecks=historical,stability=stability,versions=versions,comparisons=comparisons,
                  evaluation_source_sha256=hashfile(ROOT/'src/evaluation/p5b5r2_judge.py'),report_source_sha256=hashfile(Path(__file__)),
                  control_freeze_sha256=hashfile(local/'judge-controls-freeze.json') if (local/'judge-controls-freeze.json').exists() else None)
    report['human_dimension_confusion']={d:dict(n_owner_gold_cases=16,n_valid_numeric_human_labels=0,n_unknown=16,
        confusion=[[0,0,0],[0,0,0],[0,0,0]],agreement=None,f1=None,kappa=None) for d in DIMENSIONS}
    report['error_family_label_policy']='Minimum probed codes, not exhaustive multi-label truth; extra overlapping codes are disagreements, not adjudicated semantic false positives.'
    provider_records=[read(path) for path in sorted((local/'judge').glob('*/judgment.json'))]
    durations=[x['elapsed_ms'] for x in provider_records if isinstance(x.get('elapsed_ms'),(int,float))]
    report['judge_provider_metrics']=dict(n_response_records=len(provider_records),
        n_usage_records=sum(isinstance(x.get('metadata',{}).get('total_tokens'),int) for x in provider_records),
        input_tokens=sum(x.get('metadata',{}).get('input_tokens') or 0 for x in provider_records),
        output_tokens=sum(x.get('metadata',{}).get('output_tokens') or 0 for x in provider_records),
        total_tokens=sum(x.get('metadata',{}).get('total_tokens') or 0 for x in provider_records),
        n_cost_known=sum(isinstance(x.get('cost_upper'),(int,float)) for x in provider_records),
        cost_upper_cny=sum(x.get('cost_upper') or 0 for x in provider_records),actual_bill_cny=None,
        latency_n=len(durations),p50_ms=statistics.median(durations) if durations else None,
        p95_ms=statistics.quantiles(durations,n=100,method='inclusive')[94] if len(durations)>1 else durations[0] if durations else None,
        includes_invalid_judgments=True,source='Actual Judge response metadata, not full experiment generation ledger')
    report.pop('items')
    return report


def write_real(local,out):
    report=real_report(local);out=Path(out)
    write_new(out/'JUDGE_REAL.json',report)
    control=report['controls'];matrix=control['confusion']
    repeat=[x for x in report['stability'] if x['kind']=='repeat'];reverse=[x for x in report['stability'] if x['kind']=='reverse']
    def ratio(values):return f"{sum(x['equal_numeric'] for x in values)}/{sum(x['n_both_numeric'] for x in values)}"
    sections=[]
    for label,key in (('18回合开发配对','paired_judgments'),('新合成场景配对','scenario_judgments')):
        rows=report[key];preferences=dict(Counter(r['preference'] for r in rows))
        parts=[f'## {label}',f'已评{len(rows)}对；版本恢复后的偏好计数：`{json.dumps(preferences,ensure_ascii=False)}`。']
        arms=sorted({a for r in rows for a in r['answers']})
        parts.append('|版本|硬错回合|风险复核回合|B1均分(n)|B2均分(n)|B3均分(n)|B4均分(n)|B5均分(n；N/A)|')
        parts.append('|---|---|---|---|---|---|---|---|')
        for arm in arms:
            answers=[r['answers'][arm] for r in rows if arm in r['answers']]
            cells=[]
            for d in DIMENSIONS:
                values=[a['scores'][d] for a in answers if a['scores'][d] is not None]
                na=sum(a['scores'][d] is None and str(a['dimension_reasons'][d]).strip().upper().startswith('N/A') for a in answers)
                cells.append((f'{sum(values)/len(values):.3f}({len(values)}' if values else 'UNKNOWN(0')+(f'；{na})' if d=='B5' else ')'))
            parts.append('|'+ '|'.join([arm,f"{sum(bool(a['hard_errors']) for a in answers)}/{len(answers)}",f"{sum(bool(a.get('review_findings')) for a in answers)}/{len(answers)}",*cells])+'|')
        sections.append('\n\n'.join(parts[:2])+'\n\n'+'\n'.join(parts[2:]))
    comparison_md='\n\n'.join(sections)
    with (out/'JUDGE_REAL.md').open('x',encoding='utf-8') as f:
        f.write(f'''# P5-B5-R2 真实 Judge 校准

本轮DeepSeek真实Judge原始响应和输入在 `.local/p5b5r2/judge/`；不改写P5-B5历史分数。有效真人逐维标签仍0，不能计算真人一致率、F1或Kappa，不能靠此完成晋升认证。

v3首轮24开发政策控制，严格完整结构有效{control['n_scored']}/24，未知{control['unknown']}/24。有效判断混淆矩阵：TP={matrix['TP']}，FN={matrix['FN']}，FP={matrix['FP']}，TN={matrix['TN']}。分母始终24，不把两条未知当正确或失败。条件式物流/售后核实均未误判已执行；回执错输入/动作、虚构附件、通电检查、接入、退款等分别核对。

两条首轮结构错误（danger_ride_en、wrong_action_receipt）输出字符串review_findings，原响应、HTTP200、usage和费用已知；不是未知派发，也未重发原调用。两条hard_errors本身引用和代码可解析，事后只看硬错层为24/24二元命中，但这不是完整评分通过率。正式完整首轮覆盖仍22/24。

错误家族存在分歧：unknown_confirmed预期H02，被Judge标H04（均认为UNKNOWN不能确认发货）；refund_promise同时标H02/H03/H04，而控制最低要求H03。二元硬错识别正确不代表逐家族完全一致，也不自动成为严重错误漏判零的总体结论。

格式v3.1仅要求review_findings对象必须包含code/原文quote/reason，不改语义规则。复评{len(report['format_rechecks'])}条是独立新版本调用，保留首轮结构未知，不挑选最佳重试替换结果。

{comparison_md}

以上为同模型LLM评分点数，不是通过率、字段准确率或人类满意度。B5的版本间适用数量不同，均值不可直接作为同分母改善。R3开发主评B1–B4均顶分，存在评分饱和与偏乐观风险；独立真人评分仍缺失。

当前{len(report['paired_judgments'])}个DEV主配对、{len(report['scenario_judgments'])}个新合成场景配对，{len(report['historical_rechecks'])}个历史争议复评。DEV与新场景分开，合成冻结场景不是独立真人Gold。重复逐维数值相等{ratio(repeat)}，反转逐维数值相等{ratio(reverse)}；null双方相等与单方null单独记录，不计入数值一致分母。逐例硬错集合、偏好及N/A差异见JUDGE_REAL.json。此为同一DeepSeek模型评分，不是独立Judge或真人盲评。

历史原文复评中，CAL-03/05 B2的条件式核实不再误判H04；E4 CAL-05“是否影响正常通电使用”单列H01_REVIEW。CAL-07仍暴露残余盲区：回复承认尚未决定，但历史任务context却预选exchange，Judge未指出该动作状态矛盾。JUDGE_REAL.json的runtime_policy_audit以事件ID列出确定性政策审计，不把高回复分当动作正确。因此本评分器不能独立认证全链业务质量。

旧本地规则在同24开发控制TP2/FN10/FP1/TN11，新本地规则TP12/FN0/FP0/TN12；确定性三次与逆序一致。它与真实LLM Judge是不同层，不混算。所有控制属于开发者按已认可政策构造的正反例，没有独立真人数值真值；同语义族复用与模型偏差仍限制外推。

真实R1又发现两例本地规则误拒：安装收费的账单请求被整句“安装”误算成安装任务；发票请求的账单协作被误要求另建账单任务。通用修复改为按已声明任务名绑定scope，而不是按句子出现的全部部门；无回执/错输入/错动作仍拦截。新规则身份p5b5r2-task-noun-diagnostic-2，10项专项离线回归通过，统一重算覆盖层保留原预测与旧分。
''')
    return dict(output=str(out/'JUDGE_REAL.json'),strict_control_coverage=control['n_scored'],unknown=control['unknown'],paired=len(report['paired_judgments']),scenarios=len(report['scenario_judgments']),historical=len(report['historical_rechecks']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','live','real']);parser.add_argument('--out',default=str(ROOT/'docs/p5b5r2'));parser.add_argument('--local');args=parser.parse_args()
    def blocked(*a,**k):raise RuntimeError('Offline report forbids network')
    socket.socket.connect=blocked;socket.create_connection=blocked
    result=prepare(args.out) if args.action=='prepare' else write_real(args.local,args.out) if args.action=='real' else live_report(args.local)
    if args.action=='live':write_new(Path(args.out)/'JUDGE_LIVE.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'items','control_predictions'}},ensure_ascii=False))
