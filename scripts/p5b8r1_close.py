"""R1 delivery packaging; no API, source-data mutation or Gold signing."""
import sys,json,csv,shutil,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.p5b8r1 import read,dump,sha,DOC,LOCAL

def prepare():
    r=read(DOC/'RESULTS.json');metrics=read(DOC/'browser/layout-metrics.json')
    historical=ROOT/'docs/p5b8'
    for name in ['ANNOTATION_GUIDELINES.md','BASELINE.json','BASELINE80.csv','HISTORICAL_CLASSIFICATION.json','HISTORICAL18_FOLLOWUP.json','PROVIDER_CALLS.csv','RESULTS.json']:
        shutil.copyfile(historical/name,DOC/('HISTORICAL_'+name))
    for name in ['test-full.txt','test-r1-final.txt','test-b-family-final.txt','frontend-tests.txt','UI_WORKFLOW_EVIDENCE.json']:
        shutil.copyfile(LOCAL/name,DOC/name)
    table='\n'.join(f'| {x["page"]} | {x["width"]}×{x["height"]} | {x["panelWidth"]:g}px | {x["documentWidth"]}px | VERIFIED |' for x in metrics)
    ui=f'''# P5-B8-R1 React浏览器验收

状态：VERIFIED（以下本地工程范围）。浏览器：Codex内置IAB，Browser SDK；不是computer-use或headless截图。网址http://127.0.0.1:8774/，独立数据库.local/p4/p5b8r1-20261031，旧8773工作区保持。模型API与外部发送均关闭。

| 页面 | 真实CSS视口 | 主面板实际宽度 | document scrollWidth | 结果 |
|---|---|---|---|---|
{table}

四个质量视口均显示94个Case成员、旧90/27与新0/48身份；1440px主面板1382px、1280px1228px，没有360px窄列或竖排。分类矩阵1280视口实际宽1137px。390px降级主面板342px、无页面横向溢出。DOM尺寸与原始截图文件尺寸分别保存于layout-metrics与VERIFICATION，截图未使用clip裁切；验证后已reset视口覆盖。

## 真实交互

1. 点击“导入分析与回复”，从已有真实DeepSeek结果导入94案，未调用模型；重复导入未创建重复Case。
2. 查看质量实验与分类矩阵，准确显示B2历史90派发/72接受/18失败；校准分析旧94中91接受；旧A90对、27 Judge、63未评。明确24案新标签消融尚无首响应/分数，¥0不代表运行成本优势。
3. 点击业务洞察“产品负面体验37/87”，列表恰37个成员；实际打开B7-016及B7-036的原文、表达/体验/Issue、任务和完整A/B首次回复。统计全90、有效87、3失败，与B2旧72口径分开。
4. B7-036查看“不要通电”的正确安全否定；当前门禁不把它当危险指令，仍保留“我们会尽快回复”缺可执行安排的拦截，dialog宽980px。Gate v2细节可展开；未降低安全标准。
5. 工作台B7-002英文原文与完整英文草稿一致。动作面板最初只有knowledge_lookup executed/UNKNOWN，Copilot明确“尚无内部任务创建回执”。修复后的规划器保留表扬中的明确转达请求，实际点击创建store_service_request requested/created，责任方“门店运营”；再次点击仍只有一项业务待办（加一项查询卡，共2卡），幂等。
6. 在独立R1库进行操作审核与本地模拟，审核理由明确R1_UI_SMOKE_ONLY、不是语义Gold签署；真实产品状态simulated_sent，mode=simulation_only。本地回执及任务保存在UI_WORKFLOW_EVIDENCE与CASEBOOK B7-002。后续任务发生在旧首次回复之后，不追认旧承诺、不改变新24案任一组冻结事件。没有发信或外部联系。
7. 刷新后上述本地状态/任务仍在；旧原始回复、Judge和所有Gold不变。后续本地待办与原实验回执按阶段区别展示。

## 截图

![1440质量页](browser/quality-final-1440.jpg)

![1280分类页](browser/classification-final-1280.jpg)

![1280统计页](browser/insights-final-1280.jpg)

![工作台真实本地回执](browser/workspace-final-1440.jpg)

1920、390及案例详情原图同目录。初版连续改变viewport后，1920、390及分类1280截图出现陈旧/部分帧，实际DOM尺寸正确但图像像素不匹配；原图以stale-frame保留。改为分步设置、读取页面、再取得截图，最终每张源图均按实际像素尺寸断言匹配（含1920×1080与390×844），不凭裁切掩盖布局。初次页面数据异步载入，测试在数据实际出现后测量；一次等待90/27超时后重新读取DOM，数据已正常就绪，未以空白占位验收。favicon的404不属于业务请求失败。未进行付费模型生成或外部服务端到端验收；这些项目仍AUTHORIZATION_BLOCKED/NOT_RUN。
'''
    (DOC/'UI_ACCEPTANCE.md').write_text(ui,encoding='utf-8')
    tests='''# R1验证范围

- 全量离线702/702，411.588秒，网络socket阻断、冻结数据目录写保护；原始证据.local/p4/test-evidence/20261031T134818。该运行在最后v2记录/回访补充与表扬待办规划器之前启动，不能称最终所有源码已重跑702。
- 最终B系列170/170，包含R1最终23项，覆盖可选API注入、契约/回执、幂等与安全。此前独立R1最终Guard22/22记录也保留。
- 前端11/11（原7＋回执文案4），TypeScript noEmit通过，最终Vite构建通过。
- 首次npm test沙箱内spawn EPERM为子进程权限问题；授权的同一本地测试入口执行后11项通过，没有网络、安装或付费请求。
- 旧.local/p5b6/plot-deps没有可用Matplotlib，首次新图生成失败已保留工作记录；最终使用已有捆绑ReportLab标准柱状图及Sharp渲染，三组SVG/PNG均实际打开检查，无新增安装。
- 提取旧六例结构失败的raw再次严格拒绝；不把格式fixture通过当作新模型可靠率。R1 --live在Provider构造前拒绝，原398账本未恢复。
- 未做新的付费语义Judge、重复评分、新24案模型生成、人类Gold签署或独立泛化验收。
'''
    (DOC/'TESTS.md').write_text(tests,encoding='utf-8')
    handoff=f'''# HANDOFF — P5-B8-R1 质量收敛与显式情绪消融准备

2026-10-31 Asia/Shanghai。集中入口：[交付](docs/p5b8r1/DELIVERY.md)、[完整证据ZIP](docs/p5b8r1/P5-B8-R1_COMPLETE_REVIEW.zip)、[Judge校准](docs/p5b8r1/JUDGE_CALIBRATION.md)、[冻结24案](docs/p5b8r1/ABLATION_PROTOCOL.md)、[论文章节](docs/p5b8r1/thesis_full_draft_p5b8r1_v1.md)。本段之后原交接字节保留。

- 授权：P5-B8-R1无新增付费授权；新请求0、新费用¥0、未创建预算库。旧P5-B8仍398 completed、halted=P5B8_EXPERIMENT_COMPLETED、上界¥3.302730，不能用剩余2次恢复。CLI --live在Provider构造前拒绝。未来要明确新金额/请求上限、新独立账本及逐次预检，不自动重发UNKNOWN。
- 历史不变：B2 Champion、72/90首次契约接受、18失败；旧Gold/raw/首回复/SQLite/账本/Prompt/结论未覆盖。28555开工文件Hash核对；共享源码只改4处可选入口/呈现，其余为新增R1文件；本HANDOFF追加首段。没有Git提交/推送或外部业务操作。
- 修复：缺uncertainty仍严格拒绝，完整形状示例/清单独立版本；三非法回复为stop且缺末尾对象括号，不是长度截断。新回复严格单一非空字符串，先存raw再解析，结构失败不以空串打语义分。真实新模型复验ENGINEERING_FIXED_LIVE_RETEST_PENDING。
- Guard v2：四种动作状态、当前Hash/类型/状态绑定；输入归档仅支持记录，created仅支持本地待办；回访需可执行安排/owner/deadline/executor。保留独立安全/语言/附件/偏好/Issue门禁。旧94首响应原66可审/28阻断，新50可审/44阻断，是门禁变化而非模型质量改善。
- 新本地规划器不再把有明确转达请求的门店表扬随纯表扬一律跳过；旧默认规划器不变。R1工作台实际创建1项门店内部待办并验证幂等、simulation_only。记录标UI_SMOKE_ONLY，不是人类Gold，后续事件不追认旧首次回复，也未进入24案冻结回执。
- Judge：旧A90对/27评/63未知、2改善25持平原值保留；085是JSON空串混杂，010涉记录/未来转达边界。旧B11对/1退步10持平；009 B_GUIDED无created任务，Judge理由引用了B_DIRECT的store_service_request，证据错配已确定，数值未重写。反转6中4稳定，002/010增强B3 2→1并新增H04；新精确重复n=0。长度偏好、人类语义认证未解决。
- 消融：附件24案全部原文Hash匹配、原raw分析有效、无替补；4/4/4/6/6模型分层，混合6同一家族。两个输入除explicit_emotion外逐字同构，完整非情绪Issue/事实/政策/回执/模型/输出预算相同；自由文本uncertainty两组均去除防泄漏，原始记录保留。seed20261031，WITH先12/NO先12。FROZEN_PROTOCOL v1保留、v2仅更新最终Guard身份，24案输入和顺序不变。实际0/48，情绪差/时延/Token/费用差均null、AUTHORIZATION_BLOCKED，不能用旧A或旧8去情绪案例代替。
- 导出：主CASEBOOK94完整案＋原242案历史CASEBOOK逐字副本；索引和RAW覆盖242，Bad Case合并159（本轮94内79候选）。旧A24案全文版本盲评48份人工分数空白；未来新消融48空槽明确未运行；5个规则族HUMAN_PENDING，不重复签16旧Gold。新Accuracy/Kappa不可计算。
- 验证：全量702在最终补充前通过；最终B系列170/170含R1 23项、前端11/11、TSC/Vite通过。内置IAB实测1920/1440/1280/390，真实CSS面板1858/1382/1228/342px，无页面横向溢出；统计37案下钻、036安全否定及回访边界、英文草稿、导入、待办/审核/模拟/刷新均已操作。独立产品库.local/p4/p5b8r1-20261031，服务8774，模型/外部业务API关闭。
- 论文按章节替换设计、结果与总结，正式英文题目不变；新情绪独立贡献尚不可估计。学校Word/PDF、真实人类盲评和导师质量认证均未完成。

```powershell
.\\.venv\\Scripts\\python.exe -B scripts/p5b8r1.py
.\\.venv\\Scripts\\python.exe -B scripts/p5b8r1_finish.py
node scripts/p5b8r1_render_figures.cjs
.\\.venv\\Scripts\\python.exe -B tests/run_offline.py 'test_p5b*.py'
.\\.venv\\Scripts\\python.exe -B scripts/p5b8r1_verify.py
.\\.venv\\Scripts\\python.exe -B scripts/p5b8r1_serve.py
# 8774已运行时无需重复启动；不要运行旧live/init/judge命令。
```

剩余：新独立付费授权后接入既有受控预算驱动、执行48条新首回复及必要Judge/反转/重复；集中5语义规则/24案盲评由人类决定；保留所有失败、未知与旧分母。
'''
    (DOC/'HANDOFF.md').write_text(handoff,encoding='utf-8')
    root_handoff=ROOT/'HANDOFF.md';old=root_handoff.read_bytes()
    if not old.startswith(b'# HANDOFF '+bytes.fromhex('e28094')+b' P5-B8-R1'):
        root_handoff.write_bytes(handoff.encode('utf-8')+b'\n---\n\n'+old)
    previous=(LOCAL/'recovery/HANDOFF.md').read_bytes();assert root_handoff.read_bytes().endswith(previous)
    print('R1 UI/tests/historical references/HANDOFF prepared; original HANDOFF suffix preserved')

def package():
    verify=read(DOC/'VERIFICATION.json');assert verify['status']=='VERIFIED'
    # No data-producing code runs after the full historical protection check.
    prior=read(DOC/'PROTECTION_FINAL.json');old=(LOCAL/'recovery/HANDOFF.md').read_bytes();assert (ROOT/'HANDOFF.md').read_bytes().endswith(old)
    if 'HANDOFF.md' not in prior['changed']:prior['changed'].append('HANDOFF.md')
    prior['handoff_original_suffix_preserved']=True;dump(DOC/'PROTECTION_FINAL.json',prior)
    verify['historical_protection']=prior;dump(DOC/'VERIFICATION.json',verify)
    sources=[p for base in ('src','scripts','tests','web-client/src','web-client/tests','web-client/p5b8r1') for p in (ROOT/base).glob('*p5b8r1*') if p.is_file()]
    sources+=[ROOT/x for x in ['src/app/p5b8r1_api.py','src/application/p5b8r1_contracts.py','src/application/p5b8r1_guard.py','src/application/p5b8r1_experiment.py','src/application/p5b8r1_actions.py','src/evaluation/p5b8r1_judge.py','web-client/src/action-evidence.ts','web-client/tests/action-evidence.test.ts','web-client/p5b8r1/index.html','web-client/vite.p5b8r1.config.ts','src/app/p5b5r2_api.py','src/app/p5b8_api.py','web-client/src/p5b5.tsx','web-client/src/p5b8-entry.tsx']]
    sources=sorted(set(sources));dump(DOC/'SOURCE_IDENTITIES.json',{p.relative_to(ROOT).as_posix():sha(p) for p in sources})
    extra={p:'source/'+p.relative_to(ROOT).as_posix() for p in sources}
    extra.update({p:'prepared/'+p.name for p in (LOCAL/'prepared').glob('*.json')})
    extra.update({LOCAL/n:n for n in ['FROZEN_PROTOCOL.json','FROZEN_PROTOCOL_v2.json']})
    for folder in ['controls','plans']:
        extra.update({p:'historical-'+folder+'/'+p.name for p in (ROOT/'.local/p5b8'/folder).glob('*.json')})
    extra.update({p:'attachment-reference/'+p.name for p in (LOCAL/'reference').iterdir() if p.is_file()})
    files={p:p.relative_to(DOC).as_posix() for p in DOC.rglob('*') if p.is_file() and p.suffix!='.zip' and p.name not in ('PACKAGE_CHECK.json','PACKAGE_CONTENTS.json')}
    files.update(extra)
    # Check actual configured key values without logging them or copying .env.
    from dotenv import dotenv_values
    sensitive=[v.encode() for k,v in dotenv_values(ROOT/'.env').items() if v and ('KEY' in k or 'SECRET' in k or 'PASSWORD' in k) and len(v)>10]
    matches=[name for path,name in files.items() if any(secret in path.read_bytes() for secret in sensitive)]
    if matches:raise ValueError('Secret match in delivery artifacts; filenames only: '+repr(matches))
    manifest={name:sha(path) for path,name in files.items()};dump(DOC/'PACKAGE_CONTENTS.json',manifest);files[DOC/'PACKAGE_CONTENTS.json']='PACKAGE_CONTENTS.json'
    archive=DOC/'P5-B8-R1_COMPLETE_REVIEW.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for path,name in sorted(files.items(),key=lambda x:x[1]):z.write(path,name)
    with zipfile.ZipFile(archive) as z:
        assert not z.testzip();assert all(hashlib.sha256(z.read(name)).hexdigest()==h for name,h in manifest.items())
    result=dict(status='VERIFIED',archive=archive.name,bytes=archive.stat().st_size,sha256=sha(archive),files=len(files),secret_matches=0,complete_primary_cases=94,registry_cases=242,bad_cases=159,new_paid_requests=0,new_ablation='AUTHORIZATION_BLOCKED',contents_hashes_verified=True)
    dump(DOC/'PACKAGE_CHECK.json',result);print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':package() if '--package' in sys.argv else prepare()
