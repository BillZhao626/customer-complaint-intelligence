"""One evidence-filled human review package; never signs or changes Gold."""
from pathlib import Path
import argparse
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b5 import read,write_new,hashfile

def build(results_path=None):
    doc=ROOT/'docs/p5b5r2'
    if results_path is None:
        results_path=next((doc/p for p in ('grader-v4/RESULTS.json','grader-v3/RESULTS.json','RESULTS.json') if (doc/p).is_file()))
    results_path=Path(results_path);report=read(results_path);judge=read(doc/'JUDGE_REAL.json')
    pairs={p['case_id']:p for p in report['pairs'] if p['turn']==1}
    items=[]
    for dispute in read(doc/'JUDGE_DISPUTES.json')['items']:
        p=pairs[dispute['case_id']];runs=p['runs'];latest=runs['R3']
        items.append(dict(id='REPLY-'+p['case_id'],category='Judge与回复争议',case_id=p['case_id'],source='合成DEV真实首次回复；已认可政策无需重签',
          approval_level='SUGGESTED_SPOT_CHECK',score_target='R3',input=p['input'],customer_history=p['gold']['input_messages'],gold=p['gold'],b2_reply=runs['B2']['reply'],candidate_reply=latest['reply'],
          historical_candidate_reply=runs['E4']['reply'],events=latest['runtime']['events'],automatic_scores=latest['judge_links'],
          disagreement=dispute['engineering_diagnosis'],diagnosis=dispute['recommended_decision'],
          recommendation='抽查新回复的完整性、自然度与动作边界；已有条件式提议和未决定偏好政策不重新批准。',decision=None,comment='',
          evidence=dict(historical=dispute,run=latest['run_ref'])))
        if p['case_id']=='CAL-05':
            items[-1]['disagreement']={'historical':dispute['engineering_diagnosis'],'current_judge_repetition':[
                row for row in judge.get('stability',[]) if 'CAL-05' in str(row.get('id',row))]}
            items[-1]['recommendation']='抽查具体B2/B3评分差异与B5适用性翻转，任选自然等价表达；无需重签条件式政策。'
        elif p['case_id']=='CAL-04':
            items[-1]['diagnosis']='新回复安全建议合理且原分析雨淋归因已修，但runtime.events=[]；没有创建后续核实任务，问题推进仍不足。'
    for case_id in ('CAL-11','CAL-12','CAL-15','CAL-16'):
        p=next(p for p in report['pairs'] if p['case_id']==case_id and p['turn']==(2 if case_id in ('CAL-15','CAL-16') else 1));latest=p['runs']['R3']
        items.append(dict(id='ACTION-'+case_id,category='业务推进与状态',case_id=case_id,source='LOCAL_ACTIONS_NOT_EXTERNAL_EXECUTION',approval_level='SUGGESTED_SPOT_CHECK',
          score_target='R3',input=p['input'],customer_history=p['gold']['input_messages'],gold=p['gold'],b2_reply=p['runs']['B2']['reply'],candidate_reply=latest['reply'],events=latest['runtime']['events'],
          automatic_scores=latest['judge_links'],disagreement='请抽查多Issue推进、人工等待状态或当前安装时限是否清楚；内部登记不是外部完成。',
          diagnosis='Issue关联、幂等和重启已工程验证；真人是否觉得有帮助仍需语义抽查。',recommendation='同意仅说明本地待核实进度，保留外部结果未知。',decision=None,comment=''))
        if case_id=='CAL-11':
            items[-1]['disagreement']='R3有“抽屉里的东西先取出”建议；自滑抽屉曾磕腿，可能诱导客户接近或操作危险家具。真实Judge未指出，不视为已获安全认证。'
            items[-1]['diagnosis']='发票/取件/售后/人工请求已分开创建，局部取物建议需安全措辞抽查；离线规则补充复核发现不改真实回复。'
            items[-1]['recommendation']='建议改为先避开并暂停使用受影响家具，不要求客户取物、拆装或重现；若认为有安全前提请说明。'
    for row in read(doc/'DATA_ACTIONS.json').get('unified_review_materials',[]):
        items.append(dict(id=row.get('item_id'),category='邮件自然度',case_id=row['case_id'],source=row['source'],approval_level='SUGGESTED_SPOT_CHECK',
          input=row.get('customer'),gold=None,b2_reply=None,candidate_reply=None,events=[],automatic_scores=row.get('automatic_evidence'),
          disagreement='自然表达及多轮延续未获独立真人数值评分。',diagnosis=row.get('engineering_diagnosis'),
          recommendation=row.get('recommended_decision'),proposed_revision=row.get('proposed_revision'),decision=None,comment=''))
        items[-1]['source_evidence']={k:row.get(k) for k in ('source_sha256','input_sha256','reference_status','required_points')}
    for p in report['pairs']:
        if 'FINAL' not in p['runs']:continue
        run=p['runs']['FINAL']
        if run['first_contract'] and not run['diagnostic']['hard_findings']:continue
        items.append(dict(id=f'SCENARIO-{p["case_id"]}-T{p["turn"]}',category='新场景边界',case_id=p['case_id'],source='未用于调优的新合成场景；不是独立真人Gold',approval_level='SUGGESTED_SPOT_CHECK',
          score_target='FINAL',input=p['input'],customer_history=p['synthetic_expectations']['input_messages'],gold=None,synthetic_expectations=p['synthetic_expectations'],b2_reply=p['runs']['B2-SCENARIO']['reply'],candidate_reply=run['reply'],events=run['runtime']['events'],
          automatic_scores=run['judge_links'],disagreement=run['error'] or run['diagnostic']['hard_findings'],diagnosis='严格门禁未接受的首次输出仍保留，未重试或在该场景上调优。',
          recommendation='保留该失败；可评价回复内容，但不能把内容合理等同于工程可发送。',decision=None,comment=''))
    items.append(dict(id='PROMOTION-R3',category='正式晋升主观评价',case_id='B2 vs R3',source='18 DEV配对 + 新合成场景，真人数值0',approval_level='MUST_HUMAN_APPROVE',
      input='全部客户原文、首次回复、工具回执和逐维Judge均在RESULTS.json / FIRST_REPLIES.json；本项不要求重签历史Gold。',gold=None,b2_reply=None,candidate_reply=None,events=[],
      automatic_scores=judge.get('comparisons'),disagreement='同Provider Judge偏差与评分饱和；没有独立真人Gold，正式认证仍不足。',
      diagnosis='工程18/18、动作改善支持继续评审；不能用Judge偏好或无硬规则flag自动晋升。',recommendation='保持B2；请对主观语义改善给集中意见。没有足够独立证据时即使偏好R3也不宣布总体泛化优越。',decision=None,comment=''))
    items.append(dict(id='VISUAL-FINAL',category='产品视觉与体验',case_id='客服工作台 / 质量控制台',source='本机真实浏览器；工程验收不代替主观审美',approval_level='MUST_HUMAN_APPROVE',
      input='原参考图/改造前/最终截图和视口、操作证据见UI_ACCEPTANCE.md，浏览器文件在docs/p5b5r2/browser。',gold=None,b2_reply=None,candidate_reply=None,events=[],automatic_scores=None,
      disagreement='商业产品信息密度、字号、阅读和持续编辑体验需要用户主观评价。',diagnosis='已有React产品继续精修，真实新邮件与续信、审核/本地模拟/重启均有实物证据。',
      recommendation='在本机入口试用并评价视觉和流程；不涉及真实外部联系或发布。',decision=None,comment=''))
    from src.app.p5b5r2_api import media_manifest
    media=media_manifest()
    items[-1]['media']=media
    return dict(version='p5b5r2-single-prefilled-human-review-3',human_signed=False,human_numeric_labels=0,prior_gold_needs_resigning=False,
      choices=['agree','modify','reject','unable'],items=items,media=media,judge_stability=judge.get('stability'),
      source_hashes={str(results_path.relative_to(ROOT)):hashfile(results_path),**{name:hashfile(doc/name) for name in ('JUDGE_REAL.json','DATA_ACTIONS.json')}},
      note='所有人工选择留空；工程已能确定的政策与状态错误不要求重新批准。此包是唯一人工审核包，UI导出把本机意见附在同一包中。')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results');p.add_argument('--out',default=str(ROOT/'docs/p5b5r2/HUMAN_REVIEW.json'));args=p.parse_args()
    value=build(Path(args.results).resolve() if args.results else None);write_new(args.out,value);print('Unified prefilled review items:',len(value['items']))
