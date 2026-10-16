# P3.9 只读复查与后续边界

默认复验离线，无付费调用。原输入、授权、内账和裁决均仅本机。

```powershell
.\.venv\Scripts\python.exe -B tests/run_offline.py
.\.venv\Scripts\python.exe -B scripts/run_portable.py
# 仅核验身份与24小时内价格收据；超时会拒绝，不能篡改旧收据时间
.\.venv\Scripts\python.exe -B scripts/p39.py preflight
# 新建下一个review版本，不覆盖已存报告
.\.venv\Scripts\python.exe -B scripts/p39.py evaluate --out .local/p39/runtime-v1
```

当前真实预算`halted=failure_requires_review`。不要再运行live、删除账本、重建运行目录绕过停止条件，或自行生成研究者批准。真实smoke-receipt不存在；stop-receipt是失败停止证据，没有解锁remaining的效力。

旧P3.8 prepare与零授权manifest仍原样保留；P3.9 prepare必须新目录并重读现有最终P3.8源身份、内容归档、官方价格/tokenizer收据和真实用户请求。不能重新prepare后当作新的72/10授权。正式运行源码hash已经冻结，本阶段工程变动仅报告/测试/交接，不修改实验处理链。

新模型调用需要遵守原授权累计计数与显式复验范围。4对成功后仍需研究者对绑定8输出receipt hash的内容安全批准；任何工程测试或AI意见均不能替代该批准。
