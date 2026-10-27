# r91 目标解释器与最小厂商专项准备（2026-10-26）

本轮不修改生产代码、冻结原型或默认RTC链路。r90已修表头/焦点并完成限定独立复审，原六项保持关闭。

## Python3.11

隔离环境`/tmp/voiceagent-r91-py311`使用实际Python3.11.15，在现有requirements.lock上安装pytest/pytest-asyncio开发依赖；现有.venv3.13未改。`pip check`通过，实际后端756 passed、9项依赖弃用警告、67.20秒（首轮新环境）；见voiceagent-r91-py311-tests.txt和JUnit XML。实际Python3.11下mypy目标3.11检查79源通过，关闭旧R12/R79/R87类型环境问题；见voiceagent-r91-py311-mypy.txt。

这是目标解释器兼容检查，不代表Linux1核1GB容量或手机媒体实测。

复现：`python3.11 -m venv /tmp/voiceagent-r91-py311`，使用其Python安装`-r requirements.lock 'pytest>=8.4,<9' 'pytest-asyncio>=1.1,<2'`，再运行`python -m pytest -q`。精确已安装版本以py311-freeze.txt为准。安装依赖是公开软件包下载，不调用收费模型、客户数据或生产服务。

## 新厂商批次（D081已执行并消费，无重放）

计划：[deepgram-negation-continuation-r91-plan.json](../deepgram-negation-continuation-r91-plan.json)。虚构文本“Please do not cancel my booking.”及“I would like to change the time.”，本机Albert离线合成、150词/分生成参数，中间插入0.8秒静音。生成参数不是测得WPM；段落样本边界不是人工词边界真值。

有效PCM16单声道16kHz时长5.8576875秒；格式、样本数、非空、峰值17446和SHA已校验。仅向Deepgram Flux英文发送一次，加3秒静音，连接≤30秒、预算US$0.02；不重试、首错/范围缺口即停，不调用其他服务。按[官方价格页](https://deepgram.com/pricing)2026-10-26查询的常规Flux英文US$0.0077/分钟保守估算30秒US$0.00385；预算并非已验证账号硬扣费封顶。

实际1连接、11737.98毫秒，26条有来源范围事件（25 Partial、1 Final），没有缺范围。第2→3条Partial出现“please do not test”→“please do not cancel my”的真实词汇修订，后续追加改时间续说，最终为“please do not cancel my booking. I would like to change the time.”；not保留。另两次标点修订独立列在vendor-result-summary.json，不混为实质语义变化计数。实际账单未获供应商记录，未知，不拿估算当实扣。证据deepgram-D081.jsonl。

本批仅观察真实ASR事件的否定、续说与出现的修订/范围；若厂商未改写就记该场景未触发，不重跑求通过。不宣称TD+Jev整链、WPM/多语/真实重连/人工识别效果通过。D081用户于本轮明确授权后执行，当前授权已消费，不允许重放。冻结请求JSON内not_authorized是申请时快照，当前授权与实际执行状态以delivery-status.external_calls/decision-log D081为准；未更改请求hash。

素材在忽略目录`test-results/td-vendor-inputs/20261026-r91/negation-continuation.wav`，不提交录音；生成的输入为本地合成音，需保留用于后续授权hash核对。input-check.json保存白名单样本证据。最初受限say退出0但输出零样本，已在冻结前拦截并登记；获得本机语音服务权限重新生成后才冻结有效数据，空数据未外发。

## 仍未验证

本机Docker context desktop-linux实际无法连接本地daemon（只读检查，未启动容器），Linux1核1GB仍缺可运行环境。

手机/Safari/VoiceOver、真实弱网/跨连接时钟/耳机外放双讲AEC、目标Linux1核1GB与成对新增链路延迟、完整厂商多语/修订/WPM/LLM工具/TTS取消。按两份专项计划继续；不把本环境回归或新ASR单例当全部验收。无部署、默认RTC采用、独立完整C或Gate2签署。

授权记录预门禁首次发现缺少展示cost_ceiling字段，在任何连接前阻止执行，补齐后门禁通过；未改变用户确认的数据/费用范围。临时执行器仅把冻结计划传给现有probe，并在鉴权核对后标记started_no_replay，无新生产逻辑，保存在本轮authorized-probe.py用于审计，不能当通用重放授权。

保留的本轮临时产物：`/tmp/voiceagent-r91-py311`（供后续同目标验证）、`/tmp/voiceagent-r91-pip-cache`（独立下载缓存）、`/tmp/voiceagent-r91-mypy-cache`、`/tmp/voiceagent-r91-*`日志/执行器/两段原合成WAV，以及仓库忽略目录内冻结合成输入和vendor原始白名单日志。不提交这些环境/缓存/音频；选定结果副本在本证据目录。它们不是生产数据或客户录音，无新数据库。

本轮证据已由未参与实现的评审只读复核：stage-review/evidence-review-r91.md。核对真实3.11环境/JUnit/类型、D081授权与素材hash、26来源范围及生产105文件未变。未发现新增确认缺陷；全Change仍INSUFFICIENT EVIDENCE，不签完整C/Gate2。
