"""Offline P5-A authored content report. New output directory only, no provider.

This reports schema/evidence/guard engineering checks. Human naturalness and
usefulness are deliberately blank; no model-quality improvement is measured.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false', LANGCHAIN_TRACING_V2='false',
                  LANGSMITH_TRACING='false', LANGCHAIN_TRACING='false')

from src.application import p5_quality as p5
from src.application.analysis_service import AnalysisService
from src.application.product_analysis import ProductAnalysis
from src.application.product_workflow import ProductStore
from src.infrastructure.repository import Repository


def report():
    checks = []
    with tempfile.TemporaryDirectory(prefix='p5a_quality_') as tmp:
        store = ProductStore(Path(tmp) / 'product.sqlite3')
        repo = Repository(Path(tmp) / 'analysis.sqlite3')
        for item in p5.list_cases():
            email, data = p5.example(item['case_id'])
            case = ProductAnalysis(AnalysisService(repo, p5.P5CandidateAnalyzer(email, item['case_id'])), store).submit(email)
            restored = ProductStore(store.path).get(case['case_id'])
            checks.append(dict(candidate_id=item['case_id'], input_hash=email.input_hash,
                candidate_hash=case['run'].config.parameters['p5_candidate_hash'],
                schema_accepted=bool(case['accepted']), storage_restored=restored['analysis'] == data,
                source_strategy_bound=p5.p5_strategy(restored) is not None,
                blocked=any(f['severity'] == 'block' for f in case['quality']['findings']),
                finding_codes=[f['code'] for f in case['quality']['findings']],
                action=item['policy_decision']['action'], human_naturalness=None, human_usefulness=None,
                semantic_correctness='NOT_CERTIFIED', model_calls=0))
    return dict(version='p5a-development-engineering-checks-v1',
                identity='developer_authored_synthetic_not_real_model_evaluation_not_human_gold',
                unit='48 whitelisted authored single-email candidates', denominator=len(checks),
                schema_accepted=sum(c['schema_accepted'] for c in checks),
                storage_restored=sum(c['storage_restored'] for c in checks),
                source_strategy_bound=sum(c['source_strategy_bound'] for c in checks),
                blocked=sum(c['blocked'] for c in checks), model_calls=0,
                human_naturalness=None, human_usefulness=None, quality_improvement_claim=False,
                assets={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(p5.ROOT.iterdir()) if p.is_file()},
                candidates=checks)


def review_html():
    payload = dict(cases=p5.list_cases(), knowledge=p5.knowledge_drafts(),
                   bad=json.loads((p5.ROOT / 'bad_cases.json').read_text(encoding='utf-8')),
                   conversations=json.loads((p5.ROOT / 'conversations_dev.json').read_text(encoding='utf-8')))
    embedded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P5-A 内容候选审阅</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#172334;font:15px/1.7 system-ui,"Microsoft Yahei",sans-serif}
header{padding:24px 32px;background:white;border-bottom:1px solid #dce2ea}h1{font-size:24px;margin:0}h2{font-size:19px}h3{font-size:16px}
small,.muted{color:#56677b}nav{display:flex;gap:8px;padding:12px 32px;position:sticky;top:0;background:#f5f6f8;flex-wrap:wrap}
button,select,input{font:inherit;border:1px solid #bac6d5;border-radius:6px;padding:7px 12px;background:white;color:#172334}button{cursor:pointer}button[aria-pressed=true]{background:#194d70;color:white}
button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #e49c17;outline-offset:2px}.toolbar{padding:8px 32px;display:flex;gap:12px;flex-wrap:wrap}
main{max-width:1280px;margin:auto;padding:8px 24px 40px}article{border:1px solid #d4dde8;border-radius:8px;background:white;margin:16px 0;padding:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.pane{white-space:pre-wrap;background:#f6f8fb;padding:16px;border-radius:6px;overflow-wrap:anywhere}.reply{background:#eef6f5}
.badge{display:inline-block;padding:2px 9px;background:#e8eef5;border-radius:4px;margin-right:6px;font-size:13px}.warning{background:#fff2cd;color:#5b4200;padding:10px 16px;border-left:3px solid #ad7a08}
details{margin-top:16px}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.signature{border-top:1px dashed #aab8c9;padding-top:12px;color:#56677b}
@media(max-width:800px){.grid{grid-template-columns:1fr}header,nav,.toolbar{padding-left:16px;padding-right:16px}main{padding:8px 12px}}
</style><header><h1>P5-A 邮件、回复与知识候选审阅</h1>
<p>16 个 DEV 细分族 · 48 封单轮（中文 36 / 英文 12）· 6 组递进会话 · 4 条待批准虚构知识 · 3 个完整 Bad Case</p>
<div class="warning">全部由开发代理原创编写，离线回放；未调用真实模型。知识草案未获批准、不可注入模型。自然度、有用性和研究者接受决定均待真人填写。</div></header>
<nav id="nav"></nav><div class="toolbar" id="filters"><label>细分族 <select id="family"><option value="">全部 16 族</option></select></label><label>语言 <select id="lang"><option value="">全部</option><option value="zh">中文</option><option value="en">英文</option></select></label><label>搜索 <input id="search" placeholder="邮件 / 回复 / 动作" /></label><span id="count" aria-live="polite"></span></div><main id="main"></main>
<script id="data" type="application/json">''' + embedded + '''</script><script>
const d=JSON.parse(document.getElementById('data').textContent);let mode='cases';
const main=document.getElementById('main'),family=document.getElementById('family'),lang=document.getElementById('lang'),search=document.getElementById('search');
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function pane(title,text,cls){const box=el('section');box.append(el('h3',title),el('div',text,'pane '+(cls||'')));return box}
function detail(title,value){const e=el('details');e.append(el('summary',title),el('pre',JSON.stringify(value,null,2)));return e}
function sign(){return el('p','研究者：________________  日期：____________  决定 / 修改意见：________________________________','signature')}
for(const id of [...new Set(d.cases.map(c=>c.scenario_family))].sort()){const o=el('option',id);o.value=id;family.append(o)}
const titles={cases:'邮件与回复',bad:'完整 Bad Case',knowledge:'知识与政策草案',conversations:'递进会话'};
for(const [key,title] of Object.entries(titles)){const b=el('button',title);b.dataset.mode=key;b.onclick=()=>{mode=key;render()};document.getElementById('nav').append(b)}
function render(){main.replaceChildren();document.getElementById('filters').hidden=mode!=='cases';document.querySelectorAll('nav button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mode===mode)));
if(mode==='cases'){const items=d.cases.filter(c=>(!family.value||c.scenario_family===family.value)&&(!lang.value||c.language===lang.value)&&(!search.value||JSON.stringify(c).toLowerCase().includes(search.value.toLowerCase())));document.getElementById('count').textContent=items.length+' 封';for(const c of items){const a=el('article');a.append(el('h2',c.case_id+' · '+c.subject),el('span',c.language==='zh'?'中文':'English','badge'),el('span',c.policy_decision.action,'badge'),el('p',c.understanding.customer_goal,'muted'));const g=el('div',undefined,'grid');g.append(pane('客户原邮件',c.body),pane('客户回复候选 · 未发送',c.customer_reply,'reply'));a.append(g,detail('理解、事实与情绪（开发候选）',c.understanding),detail('内部待核实 / 客户最少待补 / 权限',c.policy_decision),detail('语气与回复规划',c.reply_plan),detail('身份与评价空白',c.evaluation),sign());main.append(a)}}
if(mode==='bad')for(const c of d.bad){const a=el('article');a.append(el('h2',c.bad_case_id+' · '+c.scenario),el('p','最早失效层：'+c.root_cause_layer+'；'+c.root_cause),pane('同一封历史开发邮件',c.email.body));const g=el('div',undefined,'grid');g.append(pane('修改前 · 原内容完整保留',c.before_reply),pane('修改后 · 新候选',c.after_reply_candidate,'reply'));a.append(g,el('p','修改依据：'+c.change),detail('来源、hash与开发诊断',c),sign());main.append(a)}
if(mode==='knowledge')for(const c of d.knowledge){const a=el('article');a.append(el('h2',c.knowledge_id+' · '+c.subject),el('div','OWNER_PENDING · use_in_model=NO · '+c.version,'warning'),pane('虚构知识 / 政策正文草案',JSON.stringify(c.claims,null,2)),detail('未知、限制与审批项',c),sign());main.append(a)}
if(mode==='conversations')for(const c of d.conversations){const a=el('article');a.append(el('h2',c.conversation_id+' · '+c.scenario_family));for(const t of c.turns)a.append(pane(t.role==='customer'?'客户来信':'前轮回复候选 · 未发送',t.body));a.append(pane('本轮回复候选 · 未发送',c.turn2_customer_reply,'reply'),el('p','事实递进与下一步：'+c.turn2_plan),detail('身份与不变量',c),sign());main.append(a)}}
for(const e of [family,lang,search])e.addEventListener('input',render);render();
</script></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, help='new exclusive output directory')
    args = parser.parse_args(); out = Path(args.out).resolve()
    for protected in ('data', 'outputs'):
        if out.is_relative_to(ROOT / protected):
            raise ValueError('Research asset paths are not report destinations')
    out.mkdir(parents=True, exist_ok=False)
    result = report()
    (out / 'engineering-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'CONTENT_REVIEW.html').write_text(review_html(), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in ('assets', 'candidates')}, ensure_ascii=False))
    if not (result['schema_accepted'] == result['storage_restored'] == result['source_strategy_bound'] == result['denominator'] and result['blocked'] == 0):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
