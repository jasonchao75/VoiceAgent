# 线上会话断连定位

会话816d7955-58ab-433d-82bc-a0087625fd70，只读排查，无重新调用厂商。

- Jev status=ok，173.56ms；Noul=0.5，目标静音1430ms，随后semantic_final提交。
- 2026-10-27T09:19:20Z，POST https://dashscope.aliyuncs.com/api/v1/chat/completions 返回404。
- ScopedOpenAILLMService被标记不可用，pipeline取消，ASR/TTS随之关闭。
- 历史误记completed，无error_category/diagnostic_id。
- 尚未修改线上配置或验证兼容地址后的实际通话；保留独立问题跟进。
