# P3.6 复验与待审入口

默认离线，禁止把历史API脚本当测试。现有真实试点预算40次已耗尽，不能重置或借用其他轮次额度。

```powershell
python -B tests/run_offline.py
python -B scripts/run_portable.py
python -B scripts/p36.py report --experiment draft-v3
```

report只读现有SQLite，并追加新版本报告/审核空白包；诊断gate哈希在新报告中标注，原attempt通过/失败始终保留，不因当前门禁变化回写。新审核写新文件，不覆盖原始预测。研究者可以填写本机`AI_SEMANTIC_REVIEW-v1.json`副本及中文表，保留真实reviewer、输出hash和证据；AI候选意见不是签署。

UI读取真实结果：设置`COMPLAINT_P36_EXPERIMENT=draft-v3`，运行原Streamlit app → Single Analysis → P3.6 real Analysis-v3，输入已存run_id。无需启用API。回复均未审核、未发送，七字段参考是开发裁决，问题级和内容参考仍待审。

有新独立授权时才可在新目录建立预算与实验。`scripts/p36.py audit/prepare`排他创建文件，不能覆盖本轮目录；`smoke/remaining`额外要求COMPLAINT_ENABLE_LIVE=true，经过正式service，不使用fake。当前目录的调用已被账本halted锁止。新的输入需要先核验虚构来源和可外发范围，再冻结输入hash；不把任意编辑的真实客户邮件加入本轮白名单。

v3-2/v3-3目录由原文标点切分，逐字位置不改原文；其角色是帮助复制合法跨度，语义支持仍需人判断。三个版本不可混算七字段或问题级质量；F176只按原冻结标记从23题干净子集排除。
