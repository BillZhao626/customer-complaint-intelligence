"""Complete offline evidence book; labels, predictions and open opinions separated."""
import csv
import json
from collections import Counter
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.research_insights import read_csv,FIELDS
from src.application.p5b7_research import B7Insights
from scripts.p5b7_report import read,write

DOC=ROOT/'docs/p5b7';OUT=DOC/'review_bundle'
def main():
    OUT.mkdir(parents=True,exist_ok=True);cases=[]
    def add(key,identity,email,reference,predictions,findings,*,family,owner_question='',status='PROVISIONAL_REVIEW'):
        if not isinstance(email,dict):email=dict(body=email if isinstance(email,str) else json.dumps(email,ensure_ascii=False))
        cases.append(dict(case_key=key,identity=identity,email=email,reference=reference,predictions=predictions,findings=findings,family=family,owner_question=owner_question,status=status))
    hist=read_csv(DOC/'forensics/HISTORICAL80_ALL.csv');original={r['email_id']:r for r in read_csv(ROOT/'outputs/i4e2_reviewed_80_raw_predictions_v1.csv')};product={r['email_id']:r for r in read_csv(DOC/'forensics/PRODUCT40.csv')}
    for r in hist:
        eid=r['email_id'];fields=r['mismatches'].split('|') if r['mismatches'] else []
        add('H80/'+eid,'HISTORICAL_SYNTHETIC_ASSISTED_PROJECT_REFERENCE_NOT_INDEPENDENT_GOLD',dict(email_id=eid,subject=r['subject'],body=r['email_body'],input_hash=r['input_hash']),
            dict(labels={f:r[f+'_reference'] for f in FIELDS},source=r['reference_source'],status=r['reference_status']),
            dict(raw=original[eid]),dict(mismatched_fields=fields,product_diagnosis=product.get(eid)),family='historical-product-taxonomy' if eid in product else 'historical-other-fields',
            status='REFERENCE_MISMATCH' if fields else 'CONTEXT_NO_FIELD_MISMATCH',owner_question='按组D01裁决分类轴；原参考和raw不得回写。' if product.get(eid,{}).get('owner_need')=='GROUPED_OWNER_TAXONOMY_REVIEW' else '')
    catalog=B7Insights(ROOT);snapshot=read(ROOT/'.local/p35/calibration-decision-v1.1/snapshot.json')
    for r in snapshot['records']:
        o=r['original'];predictions=[]
        for source in catalog.sources:
            if source.startswith('p36-'):
                predictions.extend(dict(source=source,run=p['raw']) for p in catalog.records[source] if p['input_hash']==r['input_hash'])
        add('DEV24/'+r['sample_id'],'OWNER_REVIEWED_AI_ASSISTED_DEV_ADJUDICATION_ALREADY_APPROVED',dict(email_id=r['sample_id'],subject=o['subject'],body=o['email_body'],input_hash=r['input_hash']),
            r['decision'],predictions,dict(original_reference=o,history_preserved=True),family='historical-24-adjudications',status='APPROVED_REFERENCE_NO_RESIGN',owner_question='历史裁决已批准；仅保留争议背景，不重复签署。')
    r2=read(ROOT/'docs/p5b5r2/grader-v4/RESULTS.json')
    for p in r2['pairs']:
        found=[]
        for arm,r in p['runs'].items():
            if r.get('first_contract') is False:found.append(dict(arm=arm,kind='contract_failure'))
            d=r.get('diagnostic') or {}
            found.extend(dict(arm=arm,kind='rule_diagnostic',finding=f) for f in d.get('hard_findings',[]))
        add('REPLY/'+p['case_id']+'/T'+str(p.get('turn',1)),p['reference_status'],p['input'],p.get('gold') or p.get('synthetic_expectations'),p['runs'],dict(rule_findings=found,judge=p.get('judge'),rubric_identity='DEVELOPMENT_RULE_AND_LLM_JUDGE_NOT_HUMAN'),family='historical-B2-R3-reply',status='HISTORICAL_DIAGNOSTIC',owner_question='D04仅复核仍有分歧的回复，16条开发Gold不重签。')
    pending=read(ROOT/'docs/p5b6/HUMAN_REVIEW_FINAL.json')
    for p in pending['items']:
        add('OPEN/'+p['id'],'INHERITED_OPEN_REVIEW_NOT_NEW_GOLD',p.get('input',{}),p.get('gold'),p,dict(inherited_item=p),family='inherited-open-review',status='OPEN',owner_question=p.get('question') or p.get('decision_question') or '见原开放事项及预填建议；不代签。')
    summary=read(DOC/'RESULTS.json');intent={r['email_id']:r for r in summary['intent_consistency']['rows']}
    for path in sorted((ROOT/'.local/p5b7/dataset').glob('*.json')):
        d=read(path);predictions={};findings=[]
        for arm in ('B2','R3','C1'):
            p=ROOT/'.local/p5b7'/arm/d['email_id']/'run.json'
            if not p.exists():continue
            r=read(p);ev=read(p.with_name('evaluation.json'));predictions[arm]=dict(run=r,evaluation=ev)
            if r['status']!='succeeded':findings.append(dict(arm=arm,type='FIRST_CONTRACT_FAILURE',error=r['attempts'][0].get('error')))
            for f in ev.get('diagnostic',{}).get('hard_findings',[]):findings.append(dict(arm=arm,type='RULE_REVIEW_NOT_HUMAN',finding=f))
        if intent.get(d['email_id'],{}).get('matches') is False:findings.append(dict(type='GENERATOR_INTENT_DISAGREEMENT_NOT_MODEL_ERROR',diagnostic=intent[d['email_id']]))
        pair_judgments=[x for x in summary['judge']['rows'] if x['id']=='pair-'+d['email_id']]
        add('B7/'+d['email_id'],'LLM_SYNTHETIC_REAL_LANGCHAIN_FIRST_OUTPUT_NO_HUMAN_GOLD',dict(email_id=d['email_id'],subject=d['subject'],body=d['body'],input_hash=d['input_hash']),
            dict(independent_labels=None,generator_intent=d['scenario_intent'],intent_is_not_gold=True),predictions,dict(findings=findings,generation=d,real_paired_judge=pair_judgments),family='new-'+d['family'],
            status='FAILURE_OR_DISAGREEMENT' if findings else 'PENDING_SEMANTIC_REVIEW',owner_question='D02自然度与D03新样本语义复核。无正式人工标签。')
    for r in summary['judge']['rows']:
        bad=r['parse_error'] is not None or (r['id'].startswith('control-') and set(r.get('expected_codes',[]))!=set(r.get('predicted_codes',[])))
        if bad:
            add('JUDGE/'+r['id'],'DEVELOPER_CONTROL_OR_PAIRED_LLM_DIAGNOSTIC',r['payload'],dict(expected_codes=r.get('expected_codes')),r,dict(parse_error=r['parse_error'],predicted_codes=r.get('predicted_codes')),family='judge-parse-or-policy-disagreement',status='JUDGE_DIAGNOSTIC_FAILURE',owner_question='D04核对评分器漏判/误拒；不以Judge自己证明正确。')
    with (OUT/'RAW_EVIDENCE.jsonl').open('w',encoding='utf-8') as f:
        for c in cases:f.write(json.dumps(c,ensure_ascii=False)+'\n')
    with (OUT/'ALL_BAD_CASES.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['case_key','family','identity','status','subject','findings','owner_question'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for c in cases:w.writerow({k:(c['email'].get('subject','') if k=='subject' else json.dumps(c[k],ensure_ascii=False) if k=='findings' else c[k]) for k in fields})
    with (OUT/'CASEBOOK.md').open('w',encoding='utf-8') as f:
        f.write('# 完整案例书\n\n本书含全部80条历史参考、24条已批准开发裁决、B2/R3完整逐轮回复、23条继承开放事项、新90封及所有新增失败。状态区分错误、分歧、待审与无差异上下文；不把待审都算Bad Case。\n\n')
        for family in sorted({c['family'] for c in cases}):
            f.write('# '+family+'\n\n')
            for c in [r for r in cases if r['family']==family]:
                f.write('## '+c['case_key']+'\n\n身份：'+c['identity']+'；状态：'+c['status']+'\n\n### 原始邮件 / 上下文\n\n'+c['email'].get('subject','')+'\n\n'+c['email'].get('body',json.dumps(c['email'],ensure_ascii=False))+'\n\n')
                for title,key in [('参考及审核身份','reference'),('真实预测、完整回复、工具回执与版本','predictions'),('差异、根因与代理建议','findings')]:f.write('### '+title+'\n\n```json\n'+json.dumps(c[key],ensure_ascii=False,indent=2)+'\n```\n\n')
                if c['owner_question']:f.write('待决定：'+c['owner_question']+'\n\n')
    decisions=[
        dict(id='D01',scope='历史40产品差异中11个分类轴歧义',question='未来电子个护/运动电子/露营灯/礼品卡按功能还是用途归类？',suggestion='保留历史raw；按research-products-v2用途口径继续新研究，旧8类仅做明确crosswalk；11条不强判旧模型理解错误。',decision='',reviewer='',case_keys='|'.join('H80/'+x for x in read(DOC/'forensics/RESULTS.json')['unresolved_ids'])),
        dict(id='D02',scope='新90封与历史55模板族自然度',question='新邮件的自然度、代表性和缺失信息是否可接受？',suggestion='按语言/场景盲审；B7-066咨询场景出现皮肤反应、B7-074缺商品场景出现餐桌椅需特别标记。描述性多样性不能替代人工自然度评分。',decision='',reviewer='',case_keys='B7/*'),
        dict(id='D03',scope='新90封情绪/来源及排名敏感性',question='对隐含不满和流程不清案例给出独立语义标签；哪些是中性咨询？',suggestion='优先审查意图分歧14条、失败18条及来源边界；生成意图不作为答案。F201/F260历史结论保留，不重签24裁决。',decision='',reviewer='',case_keys='B7/*|H80/F201|H80/F260'),
        dict(id='D04',scope='新18配对回复、评分器分歧与继承开放项',question='自然、有帮助、事实/动作一致的回复是否达标？哪些Judge或规则判断需纠正？',suggestion='保留B2；R3暂不晋升。仅核对新输出和旧CAL04/07/11/16、HO07仍开放问题；16条已认可开发Gold不重复签署。',decision='',reviewer='',case_keys='REPLY/*|OPEN/*|JUDGE/*'),
        dict(id='D05',scope='最终真实产品截图',question='三项导航、业务洞察层次和草稿审核的主观体验是否可接受？',suggestion='接受本轮最小收敛；数据与版本明细可展开；网页导入真实已存结果，实时派发在受控CLI，模拟发送明确本地。',decision='',reviewer='',case_keys='UI_AUDIT.md')]
    with (OUT/'OWNER_DECISIONS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(decisions[0]));w.writeheader();w.writerows(decisions)
    for name in ('HISTORICAL80_ALL.csv','HISTORICAL80_ALL_FIELDS.csv','PRODUCT40.csv','PRODUCT40.md','RESULTS.json'):
        target=OUT/'historical-forensics'/name;target.parent.mkdir(exist_ok=True);shutil.copy2(DOC/'forensics'/name,target)
    write(OUT/'INHERITED_OPEN_REVIEW.json',pending)
    write(OUT/'COUNTS.json',dict(records=len(cases),unique_case_keys=len({c['case_key'] for c in cases}),by_status=Counter(c['status'] for c in cases),by_family=Counter(c['family'] for c in cases),pending_items=len(pending['items']),owner_decisions=len(decisions),historical_field_mismatches=66))
    (OUT/'INDEX.md').write_text('# P5-B7 完整本地研究证据包\n\n先读RESEARCH_RESULTS.md，再按ALL_BAD_CASES.csv索引阅读CASEBOOK.md；原始身份与完整输出见RAW_EVIDENCE.jsonl。OWNER_DECISIONS.csv仅5个集中问题，decision/reviewer留空；不重签16 Gold与24裁决。\n\n优先级：P1首次契约/语言/状态/安全；P2隐含不满、来源与分类轴；P3自然度和UI。历史80完整560字段保留，66字段差异/48封，40产品差异单列。\n\n计数见COUNTS.json；逐来源记录可指向同一语义族，不能相加称独立样本。无差异上下文和待审不等于错误。原始API密钥、.env、HTTP认证头及受限客户数据均不纳入。邮件为明确授权本地合成研究资料。\n',encoding='utf-8')
    print(json.dumps(dict(records=len(cases),by_status=Counter(c['status'] for c in cases)),ensure_ascii=False))

if __name__=='__main__':main()
