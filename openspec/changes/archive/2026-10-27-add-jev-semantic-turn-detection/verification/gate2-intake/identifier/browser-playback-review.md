# 满位与超位浏览器播放补验 — 2026-10-26

结果：BLOCKED（超位历史展示缺陷）；实际播放通过，未修改生产实现，无外部调用。

## 场景和证据
- 同一正式根路由、生产流水线、真实本地HTTP/WS/SQLite/AudioWorklet。仅ASR/VAD/Jev/LLM/TTS为隔离替身，外网连接被阻断。
- 固定输入one→two three（1→123）。满位目标3、超位目标2；首段跟读故意持续10秒，使末段等待播放，同时正常回答或超位提醒就绪。
- 满位：唯一普通提交、唯一正常回答任务实际started/finished，未出现提醒。首段跟读播完；排队末段不播，正常回答接着播；同一渲染时钟确认无重叠。刷新历史能看到回答。
- 超位：保留123，普通提交0次，提醒事件及播放各一次；已播首段完成，末段未开播；提醒随后实际started/finished，回执204，历史API有完整记录。通话持续超过编号保护8秒以检查静音不重复。
- complete.json、overflow.json保存原始历史与回执。complete-history.png保留正常历史截图。

## P2：G2-02-OVERFLOW-HISTORY
复现：开启编号收集，输入超过目标位数，等提醒实际播放完成，结束通话，刷新Sessions打开本次详情。
预期：显示已收集编号、超位提醒及其播放证据，即便尚未提交普通对话。
实际：API td_events存在turn_id=1的编号、提醒和播放记录，但详情仅显示开场白和无归属会话证据，看不到该编号轮次。
原因：frontend/src/td-history.js:125-128在没有conversation_utterance时执行model.turns=[]，误丢弃已有编号和提醒的轮次。
研发修复：保留有真实编号/提醒事件的轮次，并覆盖未满位提醒、超位提醒及旧历史兼容。不得为了显示历史伪造普通用户提交。失败断言保留在frontend/tests/ui/gate2-number-playback.spec.js。

## 执行记录
初版探针将normal误写ordinary，已修正且保留complete-initial-probe.json；不是产品失败。新增历史断言最初只查普通turns，后改为实际提醒事件及正式UI验证，发现上述真实展示缺陷。最终两场景组合为1通过、1失败（33.5秒），失败点为超位历史UI文本缺失。

启动：从仓库根目录，NLTK_DATA指向已有.venv/nltk_data，PYTHONPATH=.，用Python3.11运行同目录browser_number_app.py。隔离数据在/tmp/voiceagent-gate2-number-playback-20261026，端口18998。
浏览器：在frontend目录设置VOICE_AGENT_UI_URL=http://127.0.0.1:18998、VOICE_AGENT_TD_LOCAL_RUNTIME=1、VOICE_AGENT_GATE2_NUMBER_PLAYBACK=1、VOICE_AGENT_TD_UI_EVIDENCE指本证据目录，运行npx playwright test tests/ui/gate2-number-playback.spec.js --project=desktop-chromium --retries=0。

真实语音质量、真实识别/LLM、硬件、手机弱网不在本轮证据内。测试音频为合成固定PCM；不是听感验收。测试库/缓存/临时密钥留在上述/tmp路径不提交；临时报告在test-results/playwright-report。18998服务验证后停止，18997配置页不受影响。

独立重复超位复验：19.1秒，播放断言全部先通过，随后同一历史UI断言再次失败。截图overflow-history-failure.png。证据复制曾因路径匹配失败，已按实际生成路径恢复，无证据丢失。
