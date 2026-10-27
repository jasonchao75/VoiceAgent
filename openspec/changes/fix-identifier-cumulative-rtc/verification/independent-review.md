# 独立审核结论

- 日期：2026-10-27
- 结论：**PASS（限定本次两个缺陷的本地工程修复范围）**。
- 审核者：`cumulative_review`，结合另一独立审核者 `rtc_fix_review` 的 RTC 专项结果。审核者未实现修复、未修改需求、未代替用户验收。
- 本轮已具备进入用户授权部署的工程条件；部署成功、真实手机/厂商体验仍需单独验证，不能由本结论推定。

## 对照需求与流程

1. 未提交 LLM 的完整编号来源由本地持有，同来源累计 `12 → 123` 即使合并为单个词，也以最新贡献替换而非追加 `12123`；不再以本地跟读边界切词并终止通话。
2. Partial `12` 在关键词、完整格式、WPM、停顿均满足时已派发跟读，**不等待 Final、不调用 LLM**。累计扩展在续说中只更新/撤销旧待播状态，满足新停顿才派发；未满位超时仍有效。
3. 同范围修订可补读；重复 Final 由原输出去重；已独立处理的纯修订不会混入下一次普通问句。清空代次禁止旧来源回灌。真正提交 LLM 后恢复严格音频边界，不允许整体扩展旧普通回复。
4. 正式默认 `create_app()` 的自建 TD + enabled 编号规则，在 session 返回、transport、输入时钟、pipeline 协议四处使用一致选择，接通既有 IdentifierOutput/RTP 任务播放器。其他模式保留 native；未新增数据通道音频。
5. 初始化失败的播放器资源清理已修复，失败不伪报实际播放。详见 `rtc-review.md`。

## 独立复验

- 本审核者直接运行 `/tmp/voiceagent-r91-py311/bin/python -m pytest -q`：**791 passed、9 skipped**，38.30s。随后复跑最终新增 clear/fence 回归所在两文件：**62 passed**。
- 本审核者直接执行 5 个临时离线 probe：续说不抢跑与提醒、同范围补读、下一问无旧编号污染、LLM 提交后边界保护、清空后旧来源隔离，均通过。详见 `backend-review.md`。
- RTC 独立审核者复跑 42 项 RTC/发布后端测试、3 项 echo API 测试、10 项节点/资源释放测试并给出 PASS，详见 `rtc-review.md`。
- 正式浏览器测试由开发者运行、RTC 独立审核者读取证据复核（不冒认本审核者独立复跑）：开发开关关闭，正式 mobile-demo 路由，**1 passed**；真实本机 RTP/Opus 解码、AudioWorklet 播放回执和 clear 停止，native audio muted。ASR/LLM/TTS 是离线替身。
- 最终 `python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc`：**PASS，0 errors / 2 warnings**。剩余警告为部署/真实环境未验证及收尾任务未勾选。

## 发现的问题与闭环

审核先后阻止并复验修复：累计扩展在续说时抢跑、续说后未满位提醒丢失、无候选同范围修订漏补读、旧纯修订混入下一问、RTC 初始化异常资源泄漏。当前复验未发现仍阻塞本次本地修复交付的问题。

## 未验证与证据边界

真实手机、扬声器/AEC、弱网、真实 ASR/Jev/LLM/TTS 端到端未测；客户端仍要求 RTCRtpScriptTransform 与 AudioDecoder，不能承诺所有 iOS/Android 浏览器兼容。没有进行收费 API 调用或发送真实客户音频。全量测试的 9 个 skip 不计为通过。部署、CI/CD 和线上健康状态由后续交付记录负责。

本报告不修改 `product_acceptance`，也不宣称 Gate2 的真实体验已重新验收。临时证据位于 `/tmp/voiceagent-cumulative-rtc-evidence/`、`/tmp/identifier_review_*.py`，不提交数据库、录音、凭证或缓存。

## 后续匹配计时专项审核

2026-10-27 `matched_packet_review` 对已匹配包误报缺映射的修复给出限定范围PASS，详见 [matched-packet-review.md](matched-packet-review.md)。不将此专项PASS扩展为生产手机故障唯一归因或用户最终验收。

## 后续静音缺包与关闭清理专项审核

2026-10-27 `matched_packet_review` 对静音范围有序退休、关闭后不重启采样及有界鉴权诊断给出限定范围PASS，见 [packet-silence-review.md](packet-silence-review.md)。不推定生产手机首因已唯一确定或用户验收通过。
