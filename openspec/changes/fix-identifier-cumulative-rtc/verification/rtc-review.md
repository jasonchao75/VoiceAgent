# RTC 接线独立复核

- Date: 2026-10-27
- Reviewer: 独立子 Agent rtc_fix_review（未修改生产代码）
- Scope: `src/api.py` 正式自建 TD + 编号规则会话启用已有 RTP 任务播放；不评价累计转写实现。
- Result: PASS（限定本次 RTC 接线的本地离线/loopback 范围；不代表累计转写专项、真实厂商、手机或弱网验收）。

## 已确认

1. `_uses_task_playback(lease)` 在公开 session 返回、transport 安装、RTP 输入 source epoch、pipeline protocol 四处一致。默认开发开关关闭时，自建 TD 且编号规则 enabled 进入任务播放；厂商 TD 和未启用规则保持 native。显式开发开关继续支持原诊断路径。
2. 既有 pipeline 的 `webrtc_candidate` 路径实际建立 SerialAudioOutput / IdentifierOutput；相关 playback-clock、rtp-input、playback-events API 没有额外开发开关拦截。
3. 正式 `mobile-demo.js` 在连接前准备任务播放器，原生 audio 设置 muted，避免双播。控制数据承载任务身份，音频仍使用 RTP/Opus；没有新增数据通道 PCM。
4. 已按 change-verifier 阅读 Change 设计、Delta、决策和主 voice-pipeline 规格；未修改规格、原型或用户验收状态。

## 独立复跑证据（offline/mock/local-real，非 external-real）

- `.venv/bin/python -m pytest tests/test_td_rtp_input.py tests/test_td_rtp_writer.py tests/test_td_rtp_mapping.py tests/test_td_rtp_integration.py tests/test_td_webrtc_cancel.py tests/test_rtp_capture_clock.py tests/test_publication.py tests/test_webrtc.py -q`：42 passed，3.25s。两个现有依赖弃用 warning。
- `node --test frontend/tests/unit/td-rtc-entry.test.js frontend/tests/unit/td-rtp-decode-job.test.js`：7 passed，2.06s。覆盖 receiver 绑定顺序、输入观察能力失败不阻断输出、播放回执超时、解码范围归属。
- `python3 scripts/quality/verify_change.py fix-identifier-cumulative-rtc`：PASS，0 errors / 3 warnings；warnings 为累计修订缺陷待修、真实环境未验证、4项任务未勾选。门禁通过不等于产品验证通过。

## 收口要求与限制

- 已审阅父 Agent 在开发开关关闭条件下执行的正式 mobile-demo 浏览器证据：`/tmp/voiceagent-cumulative-rtc-evidence/` 三份 JSON。该浏览器运行由父 Agent执行（1 passed / 14.3s），本审核独立读取实际结果与测试断言，并未冒认独立复跑浏览器。历史状态 completed；echo 的 AudioWorklet 回执 task_started 后在 clear 工具成功时 task_stopped（实际渲染282824样本）；两段普通播放各完成5760样本且匹配 manifest，全部6个回执HTTP204，worker无candidate failure。测试包含 native audio muted 断言。它证明真实本地RTC/解码/播放器接线，ASR/LLM/TTS是离线替换。
- 已独立复跑 `tests/test_echo_api.py`：3 passed / 2.11s，其中新增测试通过默认create_app实际发布+创建会话验证全部三种选择：自建+enabled => rtp_candidate，自建+disabled / provider => native。
- 客户端要求 RTCRtpScriptTransform + AudioDecoder，不支持的浏览器会明确拒绝；不能据桌面 loopback 推断 iOS/Android 兼容。
- 现有候选 worker 对 RTP packet/mapping 1秒缺失或解码范围不连续执行失败处理。真实弱网和实际手机尚未验证，不能宣称具备与 native RTP 相同的丢包容错体验。
- 初始化清理缺口已修复并独立验证：try/catch关闭sourceUploader、已创建worker、player和AudioContext后重抛。重跑 `node --test frontend/tests/unit/td-rtc-entry.test.js frontend/tests/unit/td-rtp-decode-job.test.js`：10 passed / 2.05s，含addModule失败、第二个Worker创建失败、resume失败的三条资源释放回归。

未调用任何收费 API，未部署，未产生录音或测试数据库文件；pytest/node 常规缓存不作为提交证据。

## 最终门禁复核

再次运行verify_change：0 errors / 5 warnings。尚存累计来源缺陷和初始化清理的交付状态记录待主Agent更新；本报告仅确认RTC清理缺陷现已复验关闭，累计专项由对应独立审阅负责。正式手机/网络限制仍保留，不宣称外部验收通过。
