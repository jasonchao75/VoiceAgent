# 正式RTC Final组合：本地通过

D-068受控正式public demo入口，真实RTP/Worklet/鉴权回执/SQLite历史，ASR/LLM/TTS离线替身、合成音及假麦克风。首次测试错误地用toBeVisible判断aria-hidden/inert错误页而失败，保留first-browser-ui-assertion-failed.txt；修正为正式aria-hidden/active状态后1passed/7.2s。

真实开播任务至少3（开场、Partial、Final），Partial实际播放后停播，Final的实际开播位于同一渲染时钟停止之后；正常结束任务的渲染样本严格等于实际下发manifest；所有API回执有效。调用正式结束后重读持久历史，response_restart恰好1。证据formal-authenticated-receipts.json、formal-final-history.json。

额外工程缺陷：隔离账本累积10000来源帧会失败；已将来源按成功绑定packet end释放，独立_source_end仍校验连续性。ledger-red.txt与8项定向回归证明，不冒充100秒真实通话或弱网通过。

剩余同输入延迟对照、长期/重连/移动兼容、完整回归，默认旧链不变。不自签独立PASS/C/Gate2。临时DB/主密钥/录音/tmp/voiceagent-d068-final和原始/tmp/voiceagent-r68*-server.log忽略、不提交。
