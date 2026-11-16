"""Finalize P5-B2 receipts and preserve every prior file; no paid work."""
from pathlib import Path
import sys,json,csv,hashlib,sqlite3,subprocess,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from src.evaluation.p5b2 import LOCAL,DOC,BASE,read,write_new,now
from src.evaluation.p5b2_report import csv_new
from src.application.product_workflow import ProductStore

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    store=ProductStore(ROOT/'.local/p4/p5-b2-20261029-v1/product.sqlite3')
    cases={r['run'].run_id:r for r in store.list_cases()}
    olddiag={r['turn_id']:r for r in csv.DictReader((BASE/'DEV_DIAGNOSTICS.csv').open(encoding='utf-8-sig'))}
    proposed=['ASK_HUMAN_INPUT','ASK_HUMAN_INPUT','ASK_CLARIFICATION+ASK_HUMAN_INPUT','ASK_HUMAN_INPUT',
        'ASK_HUMAN_INPUT','ASK_CLARIFICATION+ASK_HUMAN_INPUT','ASK_HUMAN_INPUT','HARD_BLOCK+ASK_HUMAN_INPUT',
        'ASK_CLARIFICATION+ASK_HUMAN_INPUT','ASK_CLARIFICATION+ASK_HUMAN_INPUT','ASK_HUMAN_INPUT',
        'ASK_CLARIFICATION+FULL_HANDOFF_REQUEST','ASK_CLARIFICATION','ASK_CLARIFICATION+ASK_HUMAN_INPUT',
        'HARD_BLOCK+ASK_HUMAN_INPUT','HARD_BLOCK+ASK_HUMAN_INPUT','ASK_CLARIFICATION+ASK_HUMAN_INPUT','ASK_CLARIFICATION+ASK_HUMAN_INPUT']
    actions=[]
    for n,r in enumerate(read(LOCAL/'formal/results.json')):
        c=cases[r['run_id']];tid=r['turn_id'];events=c['events']
        actions.append(dict(turn_id=tid,calibration_id=r['calibration_id'],identity='DEV_DIAGNOSTIC',
            A_proposed_action=olddiag[tid]['proposed_action'],B_text_proposed_action=proposed[n],
            decision_diagnostic='INAPPROPRIATE' if r['calibration_id'] in ('CAL-02','CAL-04','CAL-12','CAL-13') else 'REQUIRES_EDIT_OR_VALIDATION' if r['status']!='succeeded' else 'PLAUSIBLE_NOT_HUMAN_CERTIFIED',
            gate_state=c['quality']['status'],case_state=c['state'],verified_event_actions=';'.join(e['action'] for e in events),
            local_handoff_request=any(e['action']=='request_handoff' for e in events),demo_takeover=any(e['action']=='take_over' for e in events),
            actual_human_takeover=0,actual_external_action='NONE_VERIFIED',local_simulation=bool(c['receipt']),
            task_progress='UNKNOWN',task_completion='UNKNOWN',event_refs=';'.join(e['event_id'] for e in events),
            source_run_id=r['run_id'],human_action_set='',human_required_handoff='',human_reviewer=''))
    csv_new(DOC/'ACTION_RESULTS.csv',actions)
    with sqlite3.connect('file:'+str(LOCAL/'budget.sqlite3').replace('\\','/')+'?mode=ro',uri=True) as c:
        n,cost=c.execute('SELECT COUNT(*),SUM(reserved_cny) FROM reservations').fetchone()
        summary=dict(calls=n,reserved_upper_cny=cost,halted=c.execute('SELECT halted FROM policy').fetchone()[0],
            pending=c.execute('SELECT COUNT(*) FROM reservations WHERE completed=0').fetchone()[0],leases=c.execute('SELECT COUNT(*) FROM lease').fetchone()[0])
    assert summary['calls']==24 and summary['pending']==summary['leases']==0 and summary['halted']=='planned_generation_complete'
    write_new(DOC/'BUDGET_FINAL.json',summary)
    productpaths=['src/application/product_quality.py','src/application/service_triage.py','src/app/p5_api.py',
        'web-client/src/main.tsx','web-client/src/api.ts','scripts/p5b2_product.py','scripts/p5b2_e2e.py']
    write_new(DOC/'PRODUCT_SOURCE_HASHES.json',{p:sha(ROOT/p) for p in productpaths})
    write_new(DOC/'HANDOFF.md','''# P5-B2 交付与交接

2026-10-29 Asia/Shanghai。REAL_MODEL_AB_COMPLETED / ENGINEERING_VERIFIED / MIXED_QUALITY_RESULT / HUMAN_REVIEW_PENDING。

- 原P5-B1旧契约5/18保持；原raw候选契约离线11/18；冻结B-2真实18响应、14/18契约接受，未达15目标。工程/文本改善及退步分别报告，不晋升为独立质量认证。
- 新analysis-v3.2、缺门店null及显式旧哨兵兼容、运行时policy/language观察、版本化证据规则；旧Schema、Gold、数据、Prompt、账本及数据库保留。
- 一轮6案探索4接受，集中修正一次，冻结后18次首次生成；24总付费调用，0重试/纠错/fallback/UNKNOWN。账本独立且halted，不复用旧预算或剩余额度。
- 全24次129801输入+15872输出=145673 tokens。高峰按usage缓存明细估算¥0.16028424；全未命中费用上界¥0.386578；累计预留上界¥2.045082。余额11.00→10.92，账号观察扣减¥0.08，非实验独占账单；实际实验账单null。
- 配对18轮RAW_TEXT_ONLY开发诊断B3 0.889→1.389、B4 0.944→1.111；B1退步，出现接口规格无据断言、人工请求继续重述、重复C200型号和新取证负担。语言17→18/18；重复索取5→3/18。未改阈值；失败保留分母；全部合成DEV，不是独立Holdout。
- React真实普通咨询与英文接管案例经原审核完成2次本地模拟；风险接管门禁及失败不可编辑解锁均浏览器/HTTP验证，重启恢复通过。demo_test接管2（含失败负例）；真实人类接管/外部邮件/物流/售后/退款/预约均0。任务最终结果UNKNOWN。
- 人工Gold、正式RQPR/AAR、独立盲评及质量晋升仍待研究者。重点复核CAL-02/04/07/11/12/13与安全语境。直接交付，不自动启动P5-C、RAG、继续调参或UI美化。

入口：DELIVERY.md、AB_COMPARISON.md全18原文、AB_RESULTS.csv、BASELINE_AND_ROOT_CAUSE.md、BAD_CASE_ANALYSIS.md、HUMAN_REVIEW.md、PRODUCT_E2E_VERIFICATION.md。恢复工作库.local/p4/p5-b2-20261029-v1；应用127.0.0.1:8766，启动见REPRODUCE.md。
''')
    write_new(DOC/'DELIVERY.md','''# P5-B2 交付

已按授权完成契约修复、6案探索、冻结18轮真实B生成、A/B诊断和React本地模拟闭环。结果有改善也有退步，尚未达到全部目标。

|项目|A历史基线|A同新契约离线|B正式真实|
|---|---|---|---|
|Provider响应 / JSON|18/18 / 18/18|不是新调用|18/18 / 18/18|
|契约接受|5/18|11/18|14/18（目标15未达）|
|语言匹配|17/18|原正文不改|18/18|

全文与逐案证据：[AB_COMPARISON](AB_COMPARISON.md)、[AB_RESULTS.csv](AB_RESULTS.csv)、[METRICS](METRICS.json)。RAW_TEXT_ONLY的Codex诊断B3均值0.889→1.389，B4为0.944→1.111；事实维度退步，不能宣称整体质量已认证。正式人类评分/Gold/RQPR/AAR仍PENDING/UNKNOWN。

24次底层付费调用（6探索+18正式），0重试；累计预留¥2.045082，按高峰usage明细估算¥0.16028424，全未命中上界¥0.386578；余额账号观察减少¥0.08，实际实验账单未知。官方价格来源与授权预检在PRECALL_PRICE_AND_AUTH.json，逐条PROVIDER_LEDGER.csv及原始响应在evidence/。

已完成2次浏览器审核后的本地模拟发送、严重风险/拒绝门禁及重启恢复；自动demo_test不冒充真人。真实外部发送、退款、物流/售后执行及真正人类接管均0。证据见PRODUCT_E2E_VERIFICATION.md。

主要材料：

1. BASELINE_AND_ROOT_CAUSE.md / OFFLINE_REPLAY.json
2. CONTRACT_CHANGELOG.md / formal-wire-schema.json
3. PROMPT_CHANGELOG.md / explore与formal冻结Prompt
4. AB_COMPARISON.md / AB_RESULTS.csv / DEV_REVIEW.json
5. PROVIDER_LEDGER.csv / BUDGET_FINAL.json / BALANCE_OBSERVATION.json
6. BAD_CASE_ANALYSIS.md / CUSTOMER_EXPERIENCE_DIAGNOSTICS.csv
7. ACTION_RESULTS.csv / PRODUCT_E2E_RECEIPT.json / browser/
8. HUMAN_REVIEW.md / HANDOFF.md / REPRODUCE.md
9. VERIFICATION.md / PROTECTION_FINAL.json / CHANGE_LEDGER.json

历史资产与旧未提交成果保留，源码为渐进修改；未commit/push/tag/release。调用时代码和产品最终代码分开指纹。只读复验：`.\\.venv\\Scripts\\python.exe -B docs/p5b2/verify_delivery.py`。
''')
    original=(LOCAL/'HANDOFF-before.bin').read_bytes()
    if (ROOT/'HANDOFF.md').read_bytes()!=original:raise ValueError('Root HANDOFF changed unexpectedly')
    prefix=('''# HANDOFF — P5-B2 契约恢复与真实A/B完成

2026-10-29（Asia/Shanghai）。**REAL_MODEL_AB_COMPLETED / ENGINEERING_VERIFIED / MIXED_QUALITY_RESULT / HUMAN_REVIEW_PENDING**。

- [完整交付](docs/p5b2/DELIVERY.md)；[18回合完整对照](docs/p5b2/AB_COMPARISON.md)；[本轮交接](docs/p5b2/HANDOFF.md)；[验证](docs/p5b2/VERIFICATION.md)。下方原HANDOFF完整字节保留。
- A旧契约5/18；A旧raw新契约离线11/18；B真实14/18，目标15未达。6案探索后仅一次集中修正并冻结；正式18均首次，无挑选/替换。
- 24付费调用，0重试/fallback/UNKNOWN；高峰usage估算¥0.16028424，全未命中上界¥0.386578，预留¥2.045082；余额账号观察减少¥0.08，独占实验账单未知。新账本.local/p5b2-20261029-v1/budget.sqlite3已halted。
- B3/B4开发文本诊断改善，B1出现退步；CAL-02规格无据、CAL-12重述、CAL-13重索型号、CAL-11漏字段均保留。English18/18；独立Gold/正式RQPR与AAR未知，不宣称总体通过。
- 独立React工作库.local/p4/p5-b2-20261029-v1，127.0.0.1:8766；真实B草稿普通/英文接管2次本地模拟，风险/拒绝门禁与重启恢复已验。demo_test接管2不等于真人；真实外部操作0。
- 原资产/Gold/旧库/预算/.env不改，旧v3/v3.1兼容；不commit/push。直接交付，不自动启动P5-C/RAG/额外生成。

---

''').encode('utf8')
    (ROOT/'HANDOFF.md').write_bytes(prefix+original)
    old=read(LOCAL/'protection-start.json');changed=[];missing=[]
    for p,h in old.items():
        path=ROOT/p
        if not path.exists():missing.append(p)
        elif sha(path)!=h:changed.append(dict(path=p,before=h,after=sha(path)))
    allowed={'HANDOFF.md','src/domain/contracts.py','src/domain/versioned_analysis.py','src/application/analysis_service.py',
        'src/application/product_workflow.py','src/infrastructure/repository.py','src/application/product_quality.py',
        'src/application/service_triage.py','src/app/p5_api.py','web-client/src/main.tsx','web-client/src/api.ts'}
    unexpected=[r['path'] for r in changed if r['path'] not in allowed]
    report=dict(checked_at=now(),start_files=len(old),unchanged=len(old)-len(changed)-len(missing),changed=len(changed),missing=missing,
        unexpected=unexpected,authorized_changes=changed,handoff_original_suffix=(ROOT/'HANDOFF.md').read_bytes().endswith(original),
        old_assets_preserved=not missing and not unexpected,git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    write_new(DOC/'PROTECTION_FINAL.json',report)
    currentstatus=subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT)
    (DOC/'GIT_STATUS.txt').write_bytes(currentstatus)
    newfiles=[]
    for folder in ('src','scripts','tests','docs/p5b2'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.relative_to(ROOT).as_posix() not in old:
                newfiles.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)))
    write_new(DOC/'CHANGE_LEDGER.json',dict(modified=changed,new=newfiles,deleted=missing,unexpected=unexpected))
    # Credential values are never printed. Check exact real API key in all new delivery files.
    key=os.getenv('LLM_API_KEY')
    from src.config.llm_config import _load_dotenv_if_present
    _load_dotenv_if_present();key=os.getenv('LLM_API_KEY')
    leaks=[str(p.relative_to(DOC)) for p in DOC.rglob('*') if p.is_file() and key and key.encode() in p.read_bytes()]
    if missing or unexpected or leaks:raise ValueError('Final protection or credential check failed')
    print(json.dumps(dict(protection=report,credential_scan='PASS',new_files=len(newfiles)),ensure_ascii=False))

if __name__=='__main__':main()
