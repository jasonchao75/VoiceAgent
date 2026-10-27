# r44：历史回归与交付差异审计

上一轮已关闭D-061失败出口，本轮核查其历史渲染改动的影响：正式组件fixture旧会话与逐轮记录4 passed（2.6秒），覆盖1440/390px、中英、原文不翻译、未归属证据和浮层无横溢。人工查看history-turns双视口截图，未发现新增视觉缺陷。

发现并修复测试截图写旧证据目录的问题；只写本轮派生截图，不更新冻结baseline。没有新的生产行为改动、外部调用或付费测试。测试命令及完整结果见history-regression.txt；VOICE_AGENT_UI_URL=http://127.0.0.1:5177、VOICE_AGENT_TD_UI_EVIDENCE指本目录、playwright td-history-evidence.spec.js desktop-chromium（用例内设置1440和390）。

已将ui-checklist/task-evidence-matrix/vendor-integration-batches的当前状态与历史准备快照分开。未降低R1/R2/R3完成条件，未勾完整A/B或独立审核。等待r43新外部批次授权期间不调用厂商。
