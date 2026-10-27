# r96 正式浏览器 TTS 组合准备

日期：2026-10-26。限定证据，不是全产品验收。正式生产源未改，RTC默认关闭，未调用外部厂商，未读取真实Key。

## 关闭的缺口

在正式 `/` 页面、原组件、真实API/认证/SQLite、实际Flux SDK与AudioWorklet之间，新增单条端到端夹具。只有旧任务真实开播回执获认证接受后，才由替身ASR发送固定Final。ASR/VAD/Jev/LLM与厂商网络分别为替身；不称真实全链。

离线浏览器1条通过（5.8秒）：1连接、2Speak、1会话、1提交/1重答。旧任务开播128样本、停止12032样本，停止frame91520；新任务开播frame91776、最终结束12480样本。同一24kHz渲染时钟，停止后256样本（10.67ms）新开播；这是本次离线调度间隔，不是新增链路延迟或厂商延迟。证据见 `wire-first/history.json`、`receipts.json`、`probe-state.json`、`formal-page.png`。不能证明扬声器实际声学停播。

新夹具UDP连接能力漏洞先红后绿，已收紧TCP限定；3项定向单测通过，Ruff通过。测试遥测路由曾被SPA兜底遮蔽，已前置；首轮浏览器启动及本地端口被权限拒绝，放行后通过。无厂商请求。

## 复现

使用 `/tmp/voiceagent-r91-py311/bin/python -m tests.ui.td_tts_browser_app --wire-fixture --data-dir /tmp/<全新空目录>`，监听127.0.0.1:18996。然后在frontend执行 `VOICE_AGENT_UI_URL=http://127.0.0.1:18996 VOICE_AGENT_TD_TTS_BROWSER=1 npx playwright test tests/ui/td-tts-browser.spec.js --project=desktop-chromium --retries=0`。本机需允许启动浏览器及监听端口。测试进程退出；本轮临时库为 `/tmp/td-r96-wire-first`（启动失败）、`/tmp/td-r96-wire-second`（路由定位）、`/tmp/td-r96-wire-third`（成功），不提交。Playwright临时trace在test-results/playwright，不作为新产品通过。

版本：Python3.11.15、Chromium153、当前未提交源hash见source-sha.json。新增显式来源/非空时钟断言后未重跑同类组合，已保存证据满足该断言。

## 下一步与停止条件

独立预检之后，精确新计划 `../deepgram-tts-formal-browser-r96-plan.json` 另行申请授权。沿用196字符虚构文本，但新目的为浏览器真实停止/新开播：最多1连接2Speak、30秒、预算US$0.02，无重试/重连。允许服务端旧合成已完成，但客户端必须仍在播放并实际停止；这不是重跑D084在途SDK取消。首次错误或无法证明即停，不扩大数据。当前未授权，不能执行。

真实手机/Safari、弱网、AEC、真实LLM工具、其他厂商/语种与默认RTC采用仍未验证/待决定；完整C、独立PASS与Gate2不变。

## 独立预检返修（当前）

两项预检问题已最小修复，待独立关闭：SpeechMetadata必须匹配首个SpeechStarted身份，缺失/错误失败即停；浏览器try/finally使用仅本地夹具的停止端点直接abort本批连接并关页面。出站/Session/Speak预算保持，停止后禁止新建/新Speak。未改生产源。

7项定向单测通过（4项新负例先红后绿）；Ruff/node语法通过。`wire-repaired`正常组合5.7秒通过（包括新增来源/非空clock断言）；`wire-failure/failure-teardown.json`故意失败清理4.5秒通过，保留原intentional-local-failure，只有1Speak并stopped=true。没有付费调用。新增临时目录/tmp/td-r96-wire-repaired、/tmp/td-r96-wire-failure，服务均退出。源hash已更新，正常路径最后只补停止后不能重开守卫；该守卫随失败清理场景运行，正常成功路径未再重复。

独立复审已确认上述两项关闭、无新增确认阻塞，见../stage-review/preflight-review-r96.md。真实新批授权已请求、尚未确认；不得执行。既有BLOCKED原文仅历史，不代表返修仍未完成。
