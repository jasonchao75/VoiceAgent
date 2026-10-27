# 主审独立返修复验 — 2026-10-26

限定结论 PASS：G2-02-OVERFLOW-HISTORY 确认修复，可关闭。本次为主审实际重新执行，不以研发自测报告代替。

- 修复源码及两份相关测试的 SHA256 与研发交付快照 3/3 一致。源码只扩展历史展示条件，允许实际编号/提醒/跟读事件保留轮次；未新增普通提交或伪造指标。
- 重新构建正式前端成功。全新本地数据目录 /tmp/voiceagent-gate2-history-recheck-20261026，原隔离夹具仅替换数据目录；端口18998，非回环连接被阻断。未调用外部服务。
- 原完整 gate2-number-playback.spec.js（断言未改）及 td-history-evidence.spec.js：10 passed /32.2s。满位14.0s、超位13.7s，均核对真实WS/AudioWorklet播放回执与刷新后的正式历史页面；其余8项为正式组件+固定API数据，覆盖未满位、超位、1440/390、中英切换、旧历史和普通多轮。
- 本目录 complete.json、overflow.json 和截图为主审新生成证据，不覆盖先前失败记录。
- 顺带继续G2-03本地逻辑检查：test_td_identifier_tools.py、test_td_identifier_pipeline.py、test_td_identifier_rules.py、test_td_tool_scope.py，31 passed /1.18s，3项依赖警告。覆盖严格混合输入分流、受控工具来源验证/幂等/清空/新代次隔离及真实SDK调度，但推理为替身，不证明真实LLM能识别更正意图，也不代替用户分项验收。
- 未发现新增缺陷。真实厂商全链、真实LLM选择、设备声学/手机弱网/听感维持原未验证范围。整体Checkpoint C及Gate2未签通过，用户验收未代填。
- 18998测试服务复验后停止，18997配置页保留。临时库/缓存/录音/密钥在上述/tmp目录，不提交；运行脚本/tmp/gate2-history-recheck-app.py，自动化临时报告test-results/playwright-report。只有本目录白名单JSON/截图留作证据。

复现：frontend目录，VOICE_AGENT_UI_URL=http://127.0.0.1:18998 VOICE_AGENT_TD_LOCAL_RUNTIME=1 VOICE_AGENT_GATE2_NUMBER_PLAYBACK=1 VOICE_AGENT_TD_UI_EVIDENCE指本目录，运行npx playwright test tests/ui/td-history-evidence.spec.js tests/ui/gate2-number-playback.spec.js --project=desktop-chromium --retries=0。
