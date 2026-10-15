"""Prepare 24 exposed development cases for two REAL reviewers; never approve Gold."""
import argparse
import json
from pathlib import Path
import sys
from hashlib import sha256

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.evaluation.e2e_schema import validate_dataset, dataset_hash
from src.evaluation.gold import blank_queue
from src.domain.contracts import digest


def prepare(source,out):
    source=Path(source).resolve();out=Path(out).resolve()
    if any(out.is_relative_to(ROOT/p) for p in ('data','outputs','docs','.local/p25','.local/p2-pilot-v1')):
        raise ValueError('Protected destination')
    complex_cases=validate_dataset(json.loads((source/'complex-candidates.json').read_text(encoding='utf-8')))
    legacy=validate_dataset(json.loads((source/'legacy-candidates.json').read_text(encoding='utf-8')))
    selected=[];templates=set();scenarios=set()
    for sample in legacy:
        if sample.template_group in templates or tuple(sample.scenarios) in scenarios:continue
        selected.append(sample.model_copy(update={'split':'development'}))
        templates.add(sample.template_group);scenarios.add(tuple(sample.scenarios))
        if len(selected)==4:break
    if len(complex_cases)!=20 or len(selected)!=4:raise ValueError('Unexpected candidate pool; review selection')
    out.mkdir(parents=True,exist_ok=False)
    def write(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=dict(status='HUMAN_GOLD_PENDING',count=24,independent_holdout=False,
        selection='All 20 distinct complex scenarios + first representative of four distinct legacy scenario/template pairs; no repeated legacy template.',
        caveat='Development calibration exposed to agent and reviewers. No future holdout claim; exclude these template/semantic families from future holdout.',
        source_hashes={p.name:sha256(p.read_bytes()).hexdigest() for p in source.glob('*-candidates.json')},groups={})
    for name,samples in [('complex',complex_cases),('legacy',selected)]:
        samples=validate_dataset(samples)
        write(name+'-candidates.json',[s.model_dump() for s in samples])
        for slot in ('a','b'):write(name+'-reviewer-'+slot+'.json',blank_queue(samples,slot.upper()))
        write(name+'-adjudication.json',dict(status='pending',reviewer=None,human_declaration=False,dataset_hash=dataset_hash(samples),packet_hashes=[],decisions=[],final_packet=None))
        manifest['groups'][name]=dict(count=len(samples),dataset_hash=dataset_hash(samples),sample_ids=[s.sample_id for s in samples])
        lines=['# '+name+'：独立人工校准工作表','',
            'HUMAN_GOLD_PENDING。先独立填写自己的副本；不可看预测或另一位答案。所有字段、身份和声明都留空。',
            '把最终记录录入同名 reviewer-a/b.json，使用原P2.5 gold_workflow.py compare/freeze；有分歧由真人仲裁。',
            '每个类别须给原文连续片段、high/medium/low 确定度和理由。未知仍写 unknown；非投诉为 none，不能以 Service/Other 兜底。','']
        for sample in samples:
            lines += ['## '+sample.sample_id,'',f'Input hash: `{sample.input_hash}`','',sample.subject,'',sample.email_body,'',
                '|字段|人工值|逐字原文证据|确定度|理由|','|---|---|---|---|---|']
            lines += ['|'+field+'|待填写|待填写|待填写|待填写|' for field in type(sample.expected).model_fields]
            lines += ['', '|待审参考|事实 facts|禁止编造 forbidden|约束 constraints|可接受替代表达 alternatives|',
                '|---|---|---|---|---|','|summary_reference|待填写|待填写|待填写|待填写|',
                '|reply_reference|待填写|待填写|待填写|待填写|','|attribution_reference|待填写|待填写|待填写|待填写|',
                '', '摘要 rubric：关键事实、主要问题、无编造、实体/诉求。回复 rubric：忠实、覆盖、无擅自承诺、礼貌清晰、修改需求。',
                '逐项0/1/2须待绑定实际输出的人工评阅时填写；本表只准备参考。不得假设退款批准、金额、期限或已执行动作。','']
        for slot in ('a','b'):(out/(name+'-reviewer-'+slot+'.md')).write_text('\n'.join(lines),encoding='utf-8')
    write('manifest.json',manifest)
    (out/'START_HERE.md').write_text('# 24条真人校准包\n\n先各自阅读 complex/legacy-reviewer-a.md 或 b.md 原文工作表；答案不共享。填写对应 JSON 空白记录，真实 reviewer 身份及声明由本人完成。两份完成后按 docs/p25/ANNOTATION_GUIDE.md 和 scripts/gold_workflow.py 比较、仲裁、冻结。来源分开，不能混成同一数据集。\n\n20条复杂样本覆盖明确安全高紧急、混合情绪、服务、缺对象、归属不清、指令注入、承诺风险、中文等；4条历史模板代表只作校准。未来独立 holdout 必须隔离已暴露模板和语义族。当前 HUMAN_GOLD_PENDING。\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.source,args.out),ensure_ascii=False))
