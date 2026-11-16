"""Deterministic reporting of saved real outputs plus explicit Codex DEV reviews.

No provider, data editing, threshold fitting, or Human/Gold certification.
"""
import csv
import json
from pathlib import Path
from hashlib import sha256
from collections import Counter
from src.evaluation.p5b2 import ROOT,LOCAL,DOC,BASE,read,write_new,validate,strict_json
from src.domain.contracts import EmailInput,digest
from src.application.research_policy_v2 import requested_language,language

# One review per scheduled turn, in the inherited frozen order. RAW TEXT diagnosis only.
# score, paired explanation, exact reply quote, findings, hard-error overrides
REVIEWS=[
([2,2,2,1,2],'从让客户查页面改为产品支持核实；电脑系统是新增的合理兼容性信息，仍有问候和复述。','建议由产品支持同事核对',[],{}),
([0,2,1,1,1],'退步：无已批准规格，仍断言两接口用途不同，并给USB/网口用途；后面的待核实不能撤销前面的确定陈述。','两者用途不同',['UNSUPPORTED_INTERFACE_SPEC'],{'H02':'PRESENT'}),
([2,2,2,1,2],'正文提出物流同事向承运商核实实际交接，B3改善；但结构状态矛盾、explicit_relaxed无据，正式结果仍失败。','可以请物流同事向承运商核实',[],{}),
([1,1,0,1,1],'退步：已有DEMO编号与照片仍索订单并要求新照片，可能诱导取出未检查灯具；未充分尊重少填资料偏好。','请提供订单号或购买凭证',['REPEATED_INFO','UNNECESSARY_EVIDENCE_COLLECTION'],{'H01':'UNKNOWN'}),
([2,2,2,1,2],'改善：识别明天送礼，售后核实换货/补发、物流核实加急；未保证结果，免重复索资；仍有免责收尾和额外碎片操作建议。','同时由物流团队核查运输破损情况以及加急处理的可行性',[],{}),
([1,2,1,1,1],'正文稍有情境回应但仍以客户自行检查和资料清单为主；“又不亮”对repeated_failure的边界仍过窄而被拒，不能补造多次工单。','可以先确认灯泡或光源是否可更换',['CUSTOMER_TROUBLESHOOTING'],{}),
([1,2,1,1,2],'明确售后核实邮费，协作方向改善；“不会让你…被动承担费用”可能被理解为费用保障，需人审；business_process混用reason枚举被拒。','不会让你在寄出后才被动承担费用',['AMBIGUOUS_FEE_ASSURANCE'],{'H03':'UNKNOWN'}),
([2,2,2,1,2],'改善：severe/high、停骑禁再试、优先安全售后，照片视频限定已拍摄；情绪承接仍偏冷，不以无道歉本身判硬错。','不要再次上路测试锁扣',[],{}),
([1,2,2,2,2],'改善：明确售后核实是否可同一处理中选择、只问未知具体问题；“不必同时提交”仍是K0下流程建议，需限定。','在您确定退或换之前，不必两边同时提交',[],{}),
([2,2,2,1,2],'改善：英文回复、退款权限团队核实例外，无批准或送达承诺；仍有固定感谢及较长复述。','the refunds team to check',[],{}),
([2,2,1,1,1],'正文减少重复订单索取并保持三事项；仍把旧床取件统称物流、让客户避免在抽屉附近走动；第三Issue漏urgency，未达成功。','请先避免在抽屉附近走动',['INAPPROPRIATE_CUSTOMER_INSTRUCTION','COLLECTION_OWNER_VAGUE'],{}),
([2,0,0,1,0],'退步：明确人工请求仍被重新叙述和联系资料作为前置；程序按客户原文记录请求不算模型会转交。','你之前反映的具体问题是什么',['REPEAT_STORY','HUMAN_REQUEST_CONDITIONAL'],{'H06':'PRESENT'}),
([2,1,0,1,2],'退步：保留拒绝转人工，但再次索取已有C200型号，未提出商品资料人员后台核实；仍许诺后续说明而无跟进任务。','请补充 C200 的完整型号',['REPEATED_INFO','MERCHANT_LOOKUP_SHIFTED_TO_CUSTOMER'],{}),
([2,2,1,1,1],'基本持平：未安排维修，询问未知金额合理；仍无内部收费核实责任方，分析把拒绝维修另拆为投诉，单列分析缺陷。','以便核对收费明细',['PASSIVE_LOOKUP','ANALYSIS_OVER_SPLIT'],{}),
([2,2,2,1,2],'改善：停骑禁上路/开合锁扣、优先安全团队，仅索未知订单车型；未要求新视频，保留严重风险门禁。','不要再次上路测试或反复开合锁扣',[],{}),
([2,2,2,1,2],'改善：使用本组真实首回复；更新DEMO-D505/F20、退不修、停用禁测试和人工资格核实，无擅批退货；购买渠道重复首轮提问但客户尚未答，不属重复已给信息。','您希望退货而不是维修',[],{}),
([2,2,2,2,2],'改善：安装服务方先核实可履行时段再向客户确认，负担和情绪承接自然；只索未知编号和可用时段，未声称已预约。','可以请安装服务方先核实可执行的安装时段',[],{}),
([2,2,2,1,2],'改善：保留DEMO-S5096/仅周三下午/其他时间不直接约，不把可用时段当预约；仍机械复述限制并追加区域问题。','再与您确认，而不是直接下预约',[],{})]

def csv_new(path,rows):
    with Path(path).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    schedule=read(BASE/'pilot_manifest_16.json')['schedule']
    old_diag={r['turn_id']:r for r in csv.DictReader((BASE/'DEV_DIAGNOSTICS.csv').open(encoding='utf-8-sig'))}
    replay={r['turn_id']:r for r in read(DOC/'OFFLINE_REPLAY.json')['rows']}
    formal=read(LOCAL/'formal/results.json');byid={r['turn_id']:r for r in formal}
    if len(formal)!=18 or len(REVIEWS)!=18:raise ValueError('Fixed coverage required')
    ab=[];reviews=[];texts=[];ledgers=[];allhash={}; sums={'A':[0]*5,'B':[0]*5};failure=Counter();languages=Counter()
    b3delta=[];b4delta=[];change=Counter()
    for index,(s,review) in enumerate(zip(schedule,REVIEWS)):
        tid=s['turn_id']; score,reason,quote,findings,overrides=review
        a=read(BASE/'evidence/turns'/tid/'run.json');b=read(LOCAL/'formal/turns'/tid/'run.json')
        ad=strict_json(a['attempts'][0]['raw_output']);bd=strict_json(b['attempts'][0]['raw_output'])
        if quote not in bd['suggested_reply']:raise ValueError('Review quote mismatch '+tid)
        hard={f'H{i:02}':'ABSENT' for i in range(1,8)};hard.update(overrides)
        ascore=[int(old_diag[tid][f'B{n}']) for n in range(1,6)]
        direction='改善' if sum(score)>sum(ascore) else '退步' if sum(score)<sum(ascore) else '持平'
        if 'H02' in overrides:direction='退步'
        change[direction]+=1;b3delta.append(score[2]-ascore[2]);b4delta.append(score[3]-ascore[3])
        pair=[]
        for arm,r,data,sc in [('A',a,ad,ascore),('B',b,bd,score)]:
            for n,v in enumerate(sc):sums[arm][n]+=v
            current=read(BASE/'pilot_manifest_16.json')['cases'][next(i for i,c in enumerate(read(BASE/'pilot_manifest_16.json')['cases']) if c['calibration_id']==s['calibration_id'])]['turns'][s['turn']-1]
            correct=language(data['suggested_reply'])==requested_language(current['body']);languages[arm]+=correct
            att=r['attempts'][0]
            error=None
            if arm=='B' and r['status']!='succeeded':
                try:validate(data,EmailInput.model_validate(r['email']))
                except ValueError as exc:
                    error=str(exc).split('[type=')[0].strip();failure[error.split('\n')[0]+' / '+error.split('\n')[-1]]+=1
            hashes=dict(input_hash=r['input_hash'],raw_output_sha256=sha256(att['raw_output'].encode()).hexdigest(),reply_sha256=sha256(data['suggested_reply'].encode()).hexdigest(),prompt_sha256=r['config']['prompt_hash'])
            allhash[arm+'/'+tid]=hashes
            row=dict(arm=arm,**s,identity='DEV_DIAGNOSTIC',scope='RAW_TEXT_ONLY_NOT_E2E_PASS',source='CODEX_ORIGINAL_SYNTHETIC_DEV',knowledge='K0',
                provider_success=att['metadata'].get('dispatch')=='response_received',json_parse=att['parse_status'],contract_accept=att['contract_status'],
                harmonized_contract_accept=replay[tid]['candidate_accepted'] if arm=='A' else r['status']=='succeeded',language_correct=correct,
                **{f'B{i+1}_text_diagnostic':v for i,v in enumerate(sc)},total_text_diagnostic=sum(sc),
                **{f'B{i+1}_e2e_diagnostic':v if r['status']=='succeeded' else 'UNKNOWN_FAILED' for i,v in enumerate(sc)},
                hard_errors=json.dumps(hard if arm=='B' else json.loads(old_diag[tid]['hard_error_checks']),ensure_ascii=False),
                findings=';'.join(findings) if arm=='B' else old_diag[tid]['findings'],
                explanation=reason if arm=='B' else old_diag[tid]['dimension_reasons'],contract_failure=error or '',
                human_B1='',human_B2='',human_B3='',human_B4='',human_B5='',human_hard_errors='',reviewer='',signature='',**hashes)
            ab.append(row);pair.append(row)
        reviews.append(dict(**s,identity='DEV_DIAGNOSTIC',B_scores=score,reason=reason,reply_quote=quote,hard_errors=hard,findings=findings,direction=direction,human_scores=None))
        texts.append(f"## {tid}｜{s['calibration_id']}｜第{s['turn']}轮\n\n客户主题：{current['subject']}\n\n客户原文：\n\n{current['body']}\n\n### A 完整原文\n\n{ad['suggested_reply']}\n\n### B 完整原文\n\n{bd['suggested_reply']}\n\n工程：A原契约={a['status']}；A同新契约离线={replay[tid]['candidate_accepted']}；B真实={b['status']}。\n\nRAW_TEXT开发诊断：A={ascore}，B={score}；{direction}。{reason}\n\n逐字证据：“{quote}”。硬错：`{json.dumps(hard,ensure_ascii=False)}`。B拒绝原因：{pair[1]['contract_failure'] or '无'}。\n\n追溯：A raw SHA `{pair[0]['raw_output_sha256']}`；B raw SHA `{pair[1]['raw_output_sha256']}`。完整raw见 evidence/formal/{tid}/provider-response.txt。真人评分留空。\n")
    for stage in ('explore','formal'):
        for row in read(LOCAL/stage/'results.json'):
            tid=row['turn_id'];p=LOCAL/stage/'turns'/tid
            provider=read(p/'provider-response.txt');r=read(p/'run.json');att=r['attempts'][0];u=provider['usage'];meta=att['metadata']
            if provider['choices'][0]['message']['content']!=att['raw_output']:raise ValueError('Provider/raw mismatch')
            request=read(p/'wire-request.json')
            frozen=read(DOC/(stage+'-freeze.json'))
            if sha256(request['messages'][0]['content'].encode()).hexdigest()!=frozen['prompt_sha256']:raise ValueError('Wire prompt drift')
            hit=u.get('prompt_cache_hit_tokens',0);miss=u.get('prompt_cache_miss_tokens',u['prompt_tokens']-hit)
            ledgers.append(dict(stage=stage,turn_id=tid,calibration_id=row['calibration_id'],run_id=r['run_id'],requested_at=meta['dispatch_at'],
                received_at=read(p/'provider-http.json')['received_at'],http_status=read(p/'provider-http.json')['status'],
                requested_model='deepseek-flash',resolved_model=provider['model'],documented_provider_version='DeepSeek-V4.1-Flash-1017',weight_snapshot='UNAVAILABLE',
                input_hash=r['input_hash'],prompt_sha256=r['config']['prompt_hash'],payload_sha256=meta['payload_sha256'],
                raw_provider_sha256=sha256((p/'provider-response.txt').read_bytes()).hexdigest(),input_tokens=u['prompt_tokens'],output_tokens=u['completion_tokens'],total_tokens=u['total_tokens'],
                cache_hit_tokens=hit,cache_miss_tokens=miss,calculated_peak_tariff_cny=(hit*.04+miss*2+u['completion_tokens']*8)/1e6,
                peak_miss_upper_cny=meta['cost_cny'],reserved_upper_cny=meta['reserved_upper_cny'],actual_invoice_cny='UNKNOWN',
                sdk_retries=0,app_retries=0,fallback=False,parse_status=att['parse_status'],contract_status=att['contract_status'],
                raw_ref=f'evidence/{stage}/{tid}/provider-response.txt'))
    metrics=dict(identity='ENGINEERING_AND_CODEX_DEV_DIAGNOSTIC_NOT_HUMAN_GOLD',n_cases=16,n_turns=18,
        baseline_contract=5,baseline_candidate_replay=sum(r['candidate_accepted'] for r in replay.values()),
        B_contract=sum(r['status']=='succeeded' for r in formal),provider_success=dict(A=18,B=18),json_parse=dict(A=18,B=18),
        language_correct=dict(languages),failures=dict(failure),raw_text_dimension_means={k:[v/18 for v in vs] for k,vs in sums.items()},
        paired_B3_delta=sum(b3delta)/18,paired_B4_delta=sum(b4delta)/18,paired_directions=dict(change),
        provider_calls=len(ledgers),input_tokens=sum(r['input_tokens'] for r in ledgers),output_tokens=sum(r['output_tokens'] for r in ledgers),
        calculated_peak_with_usage_cny=sum(r['calculated_peak_tariff_cny'] for r in ledgers),peak_miss_upper_cny=sum(r['peak_miss_upper_cny'] for r in ledgers),
        reserved_upper_cny=sum(r['reserved_upper_cny'] for r in ledgers),actual_invoice_cny=None,human_gold='PENDING',RQPR='UNKNOWN',AAR='UNKNOWN')
    csv_new(DOC/'AB_RESULTS.csv',ab);csv_new(DOC/'PROVIDER_LEDGER.csv',ledgers)
    write_new(DOC/'DEV_REVIEW.json',reviews);write_new(DOC/'METRICS.json',metrics);write_new(DOC/'INPUT_OUTPUT_HASHES.json',allhash)
    intro='# P5-B2 全18回合A/B对照\n\nA为P5-B1首次raw，B为冻结B-2首次真实生成；探索结果不混入。全部为已暴露合成DEV，不是Holdout。B两个续轮只含B真实首回复；客户输入和K0相同，assistant历史按组不同。\n\n旧契约5/18；旧raw同新契约离线11/18；B真实14/18。跨Schema原始接受率不能单独证明生成改善。同一候选契约下11→14仍只是开发样本观察。\n\n以下五维均是RAW_TEXT_ONLY的Codex开发诊断，失败回复正文可读但不算端到端成功，CSV失败维度另列UNKNOWN_FAILED。人类RQPR、AAR及Gold均PENDING，未更改阈值。\n\n'
    write_new(DOC/'AB_COMPARISON.md',intro+'\n'.join(texts))
    # Copy original evidence bytes to a new destination; never mutate the source.
    for stage in ('explore','formal'):
        for p in (LOCAL/stage/'turns').rglob('*'):
            if p.is_file():
                dst=DOC/'evidence'/stage/p.relative_to(LOCAL/stage/'turns');dst.parent.mkdir(parents=True,exist_ok=True)
                with dst.open('xb') as f:f.write(p.read_bytes())
    print(json.dumps(metrics,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
