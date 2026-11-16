"""Recover all historical rows and diagnose taxonomy without mutating Gold/raw."""
import csv
import json
from collections import Counter
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.application.research_insights import read_csv,FIELDS,file_hash
from src.domain.contracts import EmailInput
from src.dataset.build_i5c_deepseek_prediction_dashboard_stats_v1 import product_ranking,store_ranking

OUT=ROOT/'docs/p5b7/forensics'
def write(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
def csvwrite(name,rows):
    with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    paths=['data/golden/golden_labels_review_sample_v1_reviewed.csv','outputs/i4e2_reviewed_80_raw_predictions_v1.csv','data/synthetic/customer_emails_full_v1.csv','src/chains/langchain_complaint_chain.py','configs/dataset/synthetic_dataset_profile_v1.json']
    gold=read_csv(ROOT/paths[0]);pred={r['email_id']:r for r in read_csv(ROOT/paths[1])};emails={r['email_id']:r for r in read_csv(ROOT/paths[2])}
    rows=[];product=[];long=[];aliases={'Beauty Products':'Beauty/Personal Care','Service':'Service/Other','Sportswear':'Sports/Outdoor'}
    mapped=[];assisted=[]
    for g in gold:
        eid=g['email_id'];p=pred[eid];e=emails[eid];email=EmailInput(email_id=eid,subject=e['subject'],body=e['email_body'])
        mismatches=[f for f in FIELDS if str(g[f]).lower()!=str(p[f]).lower()]
        rows.append(dict(email_id=eid,input_hash=email.input_hash,subject=email.subject,email_body=email.body,reference_source=g.get('review_source'),reference_status=g.get('review_status'),mismatches='|'.join(mismatches),**{f+'_reference':g[f] for f in FIELDS},**{f+'_raw':p[f] for f in FIELDS}))
        for f in FIELDS:long.append(dict(email_id=eid,input_hash=email.input_hash,field=f,reference=g[f],raw=p[f],match=str(g[f]).lower()==str(p[f]).lower(),reference_source=g.get('review_source'),reference_status=g.get('review_status')))
        pg=p['product_category'];gg=g['product_category'];mp=pg;sp=pg
        if pg!=gg:
            if pg in ('Beauty Products','Service') or (pg=='Sportswear' and 'running shoes' in email.body):
                cause='TAXONOMY_LABEL_OR_SCOPE_MISMATCH';reason='旧Schema限定 '+pg+'；新参考使用 '+gg+'。已知商品对应同一业务范围；仅派生映射，不改变模型输出。';mp=aliases[pg];sp=mp;decision='NO_NEW_OWNER_DECISION'
            elif gg=='Food/Beverage' and pg=='Other':
                cause='TAXONOMY_UNREPRESENTABLE';reason='旧8类没有Food/Beverage。原文明确食品/饮料，旧Other是可表达的剩余类；仅依赖原文可恢复，禁止把所有Other批量改食品。';sp=gg;decision='NO_NEW_OWNER_DECISION'
            elif eid=='F376':
                cause='PRODUCT_UNDERSTANDING_ERROR_PROVISIONAL';reason='原文明确membership plan；旧Schema有Service，预测Other，亦与同类F336不一致。可证明分类不一致，保留人工语义认证边界。';decision='REVIEW_IF_DISAGREE'
            else:
                cause='AMBIGUOUS_PRODUCT_AXIS_OR_REFERENCE';reason='电器/电子属性与个护/运动使用场景重叠，或gift card/露营灯超出旧窄类；不能只凭生成元数据判为理解错误。需统一分类轴后人工裁决。';decision='GROUPED_OWNER_TAXONOMY_REVIEW'
            product.append(dict(email_id=eid,input_hash=email.input_hash,subject=email.subject,email_body=email.body,reference=gg,raw=pg,reference_source=g.get('review_source'),reference_status=g.get('review_status'),cause=cause,reason=reason,label_mapping=mp,source_assisted_diagnostic=sp,owner_need=decision))
        mapped.append(dict(p,product_category=mp));assisted.append(dict(p,product_category=sp))
    assert len(product)==40 and sum(bool(r['mismatches']) for r in rows)==48
    assert sum(not r['match'] for r in long)==66
    def ranking(rs):return dict(products=product_ranking(rs),stores=store_ranking(rs))
    # Isolate each of the two sentiment cases; never overwrite saved predictions.
    counterfactual={}
    for eid in ('F201','F260'):
        g=next(x for x in gold if x['email_id']==eid)
        rs=[dict(p,**{f:g[f] for f in ('sentiment','is_complaint')}) if k==eid else p for k,p in pred.items()]
        counterfactual[eid]=dict(email=emails[eid],reference=g,raw=pred[eid],derived_only=ranking(rs),corrected_fields=['sentiment','is_complaint'],note='单变量诊断按参考更正这封两字段，其余79预测保留；不是新推理。')
    result=dict(n=80,fields=560,correct=494,mismatches=66,emails_with_mismatch=48,whole_correct=32,
        product_raw=dict(correct=40,n=80),label_mapping_diagnostic=dict(correct=sum(r['product_category']==g['product_category'] for r,g in zip(mapped,gold,strict=True)),n=80,rules=aliases,restriction='Sportswear仅在running shoes原文上使用；fitness band不自动映射'),
        source_assisted_diagnostic=dict(correct=sum(r['product_category']==g['product_category'] for r,g in zip(assisted,gold,strict=True)),n=80,note='额外10食品原文诊断，使用输入实体而非仅预测标签；不是模型准确率提高'),
        causes=Counter(r['cause'] for r in product),unresolved_ids=[r['email_id'] for r in product if r['cause'].startswith('AMBIGUOUS')],
        source_hashes={p:file_hash(ROOT/p) for p in paths},rankings=dict(reference=ranking(gold),raw=ranking(list(pred.values())),label_mapping=ranking(mapped),source_assisted=ranking(assisted)),counterfactual=counterfactual,
        limitations='全部是历史合成开发参考；28个明确口径/覆盖不一致，11个分类轴歧义，1个明确不一致候选。没有改Gold、raw或历史成绩。')
    write('RESULTS.json',result);csvwrite('HISTORICAL80_ALL.csv',rows);csvwrite('HISTORICAL80_ALL_FIELDS.csv',long);csvwrite('PRODUCT40.csv',product)
    with (OUT/'PRODUCT40.md').open('x',encoding='utf-8') as f:
        f.write('# 产品类别50%的逐案根因\n\n原始40/80=50%保持。明确标签/范围映射58/80=72.5%；加入食品原文诊断68/80=85%。二者均是同批raw的诊断，不是新模型改进。\n\n28/40明确体系差异，11/40需分类轴裁决，1/40 membership plan→Other为理解错误候选。\n\n')
        for r in product:f.write('## '+r['email_id']+'\n\n'+r['email_body']+'\n\n参考：'+r['reference']+'；原预测：'+r['raw']+'。\n\n'+r['cause']+'：'+r['reason']+'\n\n')
    print(json.dumps({k:result[k] for k in ('n','mismatches','causes','label_mapping_diagnostic','source_assisted_diagnostic')},ensure_ascii=False))

if __name__=='__main__':main()
