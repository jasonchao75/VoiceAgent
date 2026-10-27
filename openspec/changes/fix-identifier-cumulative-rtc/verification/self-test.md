# 修复自测（2026-10-27）

## 结论与范围
本次只修累计转写本地归属与正式RTC编号接线。纯编号Partial满足原关键词、词表、WPM及pause配置即本地跟读，不等待Final，不调用LLM。满位/混合对话沿用原LLM路径。

## 证据
- mock/local-real：全量Python 789 passed、9 skipped，日志 `/tmp/voiceagent-cumulative-full-pytest.txt`；之后新增严格提交边界及clear回归单独62项通过；独立全量791 passed、9 skipped，详见独立报告。
- fixture：新增Nova累计12→123合并单词，续说/未续说、未满位/满位、Partial即派发、续说中不抢跑、未满位提醒；同范围修订补读不污染下一问；清空后旧来源不回灌；真正LLM提交后仍严格拦截跨边界。
- mock：默认create_app三组模式选择（custom+rule=RTP，custom rule关/native=原音轨）通过；初始化module/worker/resume三处失败均释放资源。
- node全部28项通过；frontend build通过；mypy src 79文件通过。
- local-real：关闭开发开关启动tests.ui.td_local_app identifier，18871后端/18872 Vite；正式td-rtc-identifier-entry Playwright 1 passed。真实本机WebRTC/Opus、AudioWorklet与播放回执，ASR/LLM/TTS为离线替身。证据 `/tmp/voiceagent-cumulative-rtc-evidence`。并非真实厂商或手机体验。

## 复现
Python：`/tmp/voiceagent-r91-py311/bin/python -m pytest -q`。
浏览器：以`VOICE_AGENT_TD_LOCAL_RTP_CANDIDATE=0`启动`python -m tests.ui.td_local_app --data-dir /tmp/voiceagent-cumulative-rtc-20261027 --port 18871 --ui-origin http://127.0.0.1:18872 --scenario identifier`；Vite代理18871。frontend执行`VOICE_AGENT_UI_URL=http://127.0.0.1:18872 VOICE_AGENT_TD_LOCAL_RUNTIME=1 npx playwright test tests/ui/td-rtc-identifier-entry.spec.js --project=desktop-chromium --retries=0`。

## 风险与回退
不涉及数据库迁移；回退本次代码提交即可回到此前版本。真实手机能力、弱网、物理AEC及真实服务效果尚未验证。未调用收费API、未修改生产机器人配置。临时库、录音和日志均在/tmp隔离目录或忽略的test-results，不提交。
