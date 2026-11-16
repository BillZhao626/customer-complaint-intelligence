"""Local playback of archived synthetic cases through the real inbox and review routes."""
import argparse
from html import escape
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'examples/replay'
OFFLINE = dict(LLM_ENABLE_API='false', COMPLAINT_ENABLE_LIVE='false',
               LANGSMITH_TRACING='false', LANGCHAIN_TRACING='false',
               LANGCHAIN_TRACING_V2='false')
def read(path):
    return json.loads(path.read_text(encoding='utf-8'))
def create_review(database, port=8790):
    os.environ.update(OFFLINE)
    from fastapi.responses import HTMLResponse
    from src.app.p5b8r5_api import create
    from src.application.r6u0_workflow import product_run
    web = ROOT / 'web-client/dist'
    if not (web / 'index.html').exists():
        raise FileNotFoundError('Build the React review client with npm.cmd run build first.')
    app = create(database, web, port=port, policy_overlays=read(EVIDENCE / 'store-review-policy.json'))
    archive = read(EVIDENCE / 'cohort-results.json')
    rows = []
    for path in sorted((EVIDENCE / 'replays').glob('*.json')):
        record = read(path)
        slot = record['slot']
        run = product_run(record)
        stored = app.state.store.create(run, 'Saved synthetic research draft', origin='new_analysis')
        is_transfer = slot['case_id'].startswith('R11OG')
        current = app.state.store.get(stored['case_id'])
        rows.append(dict(case_id=slot['case_id'], cohort='HOLDOUT' if is_transfer else 'DEV',
                         source_revision='holdout-final' if is_transfer else None, email=record['email'],
                         new_reply=slot['reply'], new_verdict=record['historical_grade'],
                         events=slot['events'], analysis=record['analysis'],
                         guard=app.state.store.quality_inspector(
                             run, current.get('analysis'), slot['reply'], True),
                         input_hash=slot['input_hash'], run_id=slot['run_id'], product_case_id=stored['case_id']))
    public = read(EVIDENCE / 'portfolio-case-metrics.json')
    samples = {}
    for path in sorted((EVIDENCE / 'portfolio').glob('*.json')):
        record = read(path)
        run = product_run(record)
        stored = app.state.store.create(run, 'Saved synthetic research draft', origin='new_analysis')
        samples[path.stem] = stored['case_id']
        if path.stem.startswith('yoga-'):
            text = next(r['reply'] for r in public['case']['replies'] if path.stem == 'yoga-' + r['key'])
            assert text == record['slot']['reply'] == run.result.suggested_reply
    app.state.portfolio_cases = samples
    static = app.router.routes.pop()
    @app.get('/api/review/health')
    def health():
        return dict(replays=len(rows) + len(samples), mode='saved_synthetic_replay', paid_enabled=False)
    @app.get('/api/r8/quality')
    def quality():
        states = ('PASS','PARTIAL','FAIL','UNKNOWN')
        def summary(n, outcomes):
            return dict(N=n, **{s:outcomes.get(s,0) for s in states})
        return dict(release='v25b', prior_release='v14', current_cohort=True, cases=rows,
                    summary={'DEV':summary(archive['fixed']['DEV']['n'], archive['fixed']['DEV']['new']),
                             'holdout-final':summary(archive['transfer']['n'], archive['transfer']['counts'])},
                    judge_summary='下表展示选定的保存案例。上方分母是历史全组；当前审核使用 v27 离线规则。',
                    human_review_label='瑜伽垫回复对照 ↗')
    @app.get('/portfolio/cases/{key}', include_in_schema=False)
    def sample(key: str):
        from fastapi import HTTPException
        from fastapi.responses import RedirectResponse
        if key not in samples:
            raise HTTPException(404, 'Case unavailable')
        return RedirectResponse('/?case=' + samples[key])
    @app.get('/portfolio/yoga', response_class=HTMLResponse, include_in_schema=False)
    @app.get('/api/r8/human', response_class=HTMLResponse, include_in_schema=False)
    def comparison():
        case = public['case']
        cards = []
        for reply in case['replies']:
            key = 'yoga-' + reply['key']
            record = app.state.store.get(samples[key])
            cards.append(
                f'<article data-reply="{reply["key"]}"><header><h2>{escape(reply["title"])}</h2>'
                f'<p>人工复核 · {escape(reply["review"])}</p></header>'
                f'<a href="/portfolio/cases/{key}">在工作台打开原保存草稿 ↗</a>'
                f'<p class="reply">{escape(record["run"].result.suggested_reply)}</p>'
                f'<footer>原始草稿 · 待审核 · 售后核查待处理</footer></article>'
            )
        return f'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>瑜伽垫异味 · 保存回复对照</title>
<style>
* {{ box-sizing: border-box }}
body {{ margin:0; background:#faf9f6; color:#262831; font:16px/1.45 "Microsoft YaHei",system-ui,sans-serif }}
main {{ max-width:1700px; margin:auto; padding:12px 18px }}
nav {{ display:flex; justify-content:space-between; color:#54466e }}
a {{ color:#594676 }}
h1 {{ font-size:25px; margin:8px 0 4px }}
.original {{ margin:0 0 10px; padding:8px 13px; border:1px solid #e5e1da; background:#fff }}
.versions {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px }}
article {{ background:#fff; padding:9px 14px; border:1px solid #e5e1da; border-radius:5px;
           display:flex; flex-direction:column; align-items:flex-start }}
article header {{ display:flex; align-items:center; justify-content:space-between; width:100%; gap:6px }}
article h2 {{ margin:0; font-size:21px }}
article header p {{ margin:0; color:#594676; font-size:14px; text-align:right }}
article a {{ font-size:13px; margin:4px 0 0 }}
.reply {{ white-space:pre-wrap; font:16px/1.24 "Segoe UI",sans-serif; margin:8px 0; flex:1 }}
footer {{ border-top:1px solid #e5e1da; padding-top:8px; width:100%; color:#62606c; font-size:13px }}
@media(max-width:750px) {{ .versions {{ grid-template-columns:1fr }} }}
</style>
<main>
<nav><a href="/">← 客服工作台</a><span>演示环境，不发送真实邮件</span></nav>
<h1>瑜伽垫异味 · 保存回复对照</h1>
<p class="original"><b>合成研究邮件</b><br>{escape(case["email"])}</p>
<div class="versions">{"".join(cards)}</div>
</main></html>'''
    app.router.routes.append(static)
    return app
if __name__ == '__main__':
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    with TemporaryDirectory(prefix='complaint-supervisor-') as directory:
        uvicorn.run(create_review(Path(directory) / 'review.sqlite3', args.port),
                    host='127.0.0.1', port=args.port)
