"""One derived review package, preserving old items and approved policies."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.research_insights import file_hash


def main():
    p=argparse.ArgumentParser();p.add_argument('--research',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    oldpath=ROOT/'docs/p5b5r2/HUMAN_REVIEW.json';pack=json.loads(oldpath.read_text(encoding='utf-8'))
    rpath=Path(a.research)/'classification.json';report=json.loads(rpath.read_text(encoding='utf-8'))
    # Existing items remain byte-equivalent after JSON parsing; no decisions added.
    for e in report['reports'][0]['errors']:
        if not any(m['field']=='sentiment' for m in e['mismatches']):continue
        pack['items'].append(dict(id='B6-CLASS-'+e['email']['email_id'],case_id=e['email']['email_id'],category='分类边界与论文解释',
            source='HISTORICAL_REVIEWED_AI_ASSISTED_NOT_INDEPENDENT_GOLD',input=e['email']['body'],
            disagreement=e['mismatches'],diagnosis='售后流程未明的负面/中性边界；旧参考保持。词法but标签不能证明混合情绪。',
            recommendation='只评价新增研究解释及是否需要未来独立边界样本；不重复签署历史政策、不自动回写标签。',
            automatic_scores=None,decision=None,comment='',input_hash=e['input_hash']))
    for key,title,category,text in [
        ('B6-GOLD-SCOPE','最小独立分类/Issue复核范围','独立研究标签','建议先建立9场景×中英文的18个完整会话覆盖：表扬、普通投诉、咨询、否定、矛盾/讽刺、多Issue、多轮、缺门店、缺产品。模板族与整会话隔离、盲化预测，双人分歧仲裁；这只是最小覆盖，不足以认证总体准确率。24条已批准裁决无需重签。'),
        ('B6-NATURALNESS','新数据自然度审核与生成等待','生成与自然度','复用旧包已有自然度争议，先核对400模板的11场景族及未覆盖风险代表；新9场景样本在明确新金额/请求上限之后生成，逐条盲审自然度、连贯性和信息缺失合理性。生成标签不得当Gold；当前没有新真实样本可签。'),
        ('B6-THESIS','论文结论与来源确认','论文结论','确认正式课题题目不变；400来自55程序模板；97.5%仅80条辅助reviewed项目参考的情绪字段结果；44共享模板族阻止独立泛化声明；业务归因不表示因果责任；生成优越性、独立Gold、Issue准确率保持UNKNOWN。导师原邮件未找到。')]:
        pack['items'].append(dict(id=key,case_id=title,category=category,source='P5B6_RESEARCH_REVIEW_PENDING',input=text,
            disagreement=None,diagnosis=text,recommendation='由实际研究者填写意见；未自动批准或改动历史Gold。',automatic_scores=None,decision=None,comment=''))
    pack.update(version='p5b6-consolidated-human-review-v1',extends='docs/p5b5r2/HUMAN_REVIEW.json',prior_items_unchanged=True,
        prior_gold_needs_resigning=False,human_signed=False,new_item_count=5)
    pack['source_hashes']={'docs/p5b5r2/HUMAN_REVIEW.json':file_hash(oldpath),rpath.relative_to(ROOT).as_posix() if rpath.is_absolute() else rpath.as_posix():file_hash(rpath)}
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(pack,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(items=len(pack['items']),new_items=5,human_signed=False)))


if __name__=='__main__':main()
