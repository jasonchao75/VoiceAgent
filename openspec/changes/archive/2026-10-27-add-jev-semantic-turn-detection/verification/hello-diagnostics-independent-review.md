# Hello 诊断补丁专项独立复核

- 日期：2026-10-27（America/Los_Angeles）
- Reviewer：独立子 Agent `/root/diagnostic_review`
- 结论：**PASS（仅限本地诊断补丁）**。
- 本结论不替代原 Change 的独立验收，不证明线上问题已修复、旧会话证据已补回或新版本已部署。

## 范围与依据

按 `.codex/skills/change-verifier/SKILL.md` 及 canonical workflow，对本轮未提交的 `src/asr/source_frames.py`、`src/asr/factory.py`、`src/pipeline/custom_td.py` 和三个相应测试文件进行专项复核。用户授权为补齐 Hello 识别及打断证据；没有 UI 改动，未更新原型或基线。核对主规格关于诊断不泄漏凭证/完整厂商 payload、ASR 来源证据保留的要求。

## 验证

- `static`：Nova 原始 Results 回调在适配前记录空/非空文本长度、词数、时间范围、Final 和置信度；不存原始文字、完整响应、密钥或音频。适配后记录文本帧长度，供比对回调是否产生对应帧。
- `static`：音频入口只增加累计字节数及连接存在状态，不替换 SDK 发送实现；`remote_receipt_verified=false` 明确不把 socket 存在冒充厂商收到音频。未改变路由、识别阈值、提交规则或打断行为。
- `static`：仅自建 TD 绑定诊断 sink；ASR 600 条与总新增诊断 2400 条上限均保留截断标记。VAD 状态与打断提议明确标记 `local_vad`，不能据此判断是用户、回声或噪声。
- `mock/local-real`：独立运行 `/tmp/voiceagent-r91-py311/bin/python -m pytest tests/test_td_source_frames.py tests/test_asr_factory.py tests/test_td_runtime.py -q`，**74 passed**。包含真实本地 Silero 静音、正式 prepare 函数绑定、空 ASR 返回、禁止原文泄露、上限、诊断 sink 故障不阻断音频等验证。
- 自动门禁：`python3 scripts/quality/verify_change.py archive/2026-10-27-add-jev-semantic-turn-detection` → **0 errors，11 warnings**。警告为已有公开问题/未验证项及一项尚未勾选任务，不能据此宣称整个 Change 再次完全验收。

## 审查发现及修复复核

初版新增 `vad_state_changed` 直接使用可能抛异常的 sink。独立重现仅该诊断失败即可导致 `InputAudioRawFrame` 未继续转发（forwarded=0）。开发方已改用隔离异常的 `record_diagnostic`，新增故障 sink 回归通过。假 VAD 测试遗漏 cleanup 导致一次测试失败，也已补齐并重跑通过。

## 边界

没有真实厂商请求、生产部署或用户录音重识别。本次验证能证明新增证据采集路径及失败隔离，不能证明原始 Hello 漏识别的根因。厂商原始事件、客户端实际开播/停止、回声或真实开口归因仍需后续会话证据；录音人工听辨未在本审查执行。日志保存于 `/tmp/hello-diagnostics-independent-pytest.txt` 和 `/tmp/hello-diagnostics-independent-gate.txt`，未提交。
