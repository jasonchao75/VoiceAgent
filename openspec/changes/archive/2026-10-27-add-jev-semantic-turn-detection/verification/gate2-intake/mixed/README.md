# G2-03 混合输入与主动更正独立验证 — 2026-10-26

限定结论：本地控制流程 PASS，未发现新增问题；用户分项验收待定，真实LLM选择工具仍未验证。未修改生产实现。

## 正式浏览器组合
1. 固定转写“我的号码是123”：走普通TD；预设LLM调用submit_identifier后返回submitted/value=123/count=3/generation=0。未进入本地数字提取或跟读。
2. 输入纯编号“4”：本地累计1234并开始长跟读。
3. 固定转写“不是123，是124”：走普通TD；预设clear_identifier返回cleared/value为空/count=0/generation=1，未拼接123124或改成124。旧跟读实际渲染61312样本后收到task_stopped，工具成功后固定回答“编号已清空，请完整重念。”。
4. 输入89：本地只收集89，新代次跟读实际开播；结束测试时的新音频停止不与更正造成的旧音频停止混淆。
5. 同一通话仅两次普通提交，实际工具状态变化为提交一次、清空一次；全部播放回执204；刷新正式Sessions详情仍显示更正回答。

正式根路由/真实HTTP、WS、SQLite、SDK工具调度、AudioWorklet；ASR/VAD/Jev/LLM/TTS为本地替身，外部连接被阻断。结果1 passed /13.7s（用例13.2s）。原始事件、历史与回执mixed.json，刷新截图mixed-history.png。

## 重复、迟到和隔离
实际Python3.11运行test_td_identifier_tools、test_td_identifier_pipeline、test_td_identifier_rules、test_td_tool_scope，共31 passed /1.10s，3项依赖警告。覆盖无来源数字拒绝、清空后旧代次提交拒绝、重答不重放成功工具、迟到清空不影响新代次、并发提交/清空返回真实状态、混合输入不本地提取及SDK工具后续回复。

## 边界
测试预设了何时调用提交/清空；它证明控制流程正确，不证明真实模型能理解中文更正。要求用户完整重念的回答也是预设推理结果。真实LLM工具评测仍遵循D086暂缓，未调用付费API，也未接受或排除其剩余风险。未验证真实识别、音质、手机弱网或声学AEC；整体Gate2仍未通过。

## 复现与产物
仓库根目录，以NLTK_DATA指向已有.venv/nltk_data、PYTHONPATH=.、Python3.11运行browser_mixed_app.py。临时数据/tmp/voiceagent-gate2-mixed-20261026，端口18998，完成后停止。测试库/密钥/音频缓存不提交，自动化报告在test-results/playwright-report；18997配置页保持。
frontend目录设置VOICE_AGENT_UI_URL=http://127.0.0.1:18998、VOICE_AGENT_TD_LOCAL_RUNTIME=1、VOICE_AGENT_GATE2_MIXED=1及VOICE_AGENT_TD_UI_EVIDENCE指本目录，运行npx playwright test tests/ui/gate2-mixed.spec.js --project=desktop-chromium --retries=0。
