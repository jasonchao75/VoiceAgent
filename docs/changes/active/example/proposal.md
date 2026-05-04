# add-pipecat-minimal-pipeline

## Why(为什么要做)

当前项目已有 ASR 厂商调研和测试脚本，但还缺少一个可运行的最小实时语音 pipeline。
需要先验证 Pipecat 是否能承载 ASR → LLM → TTS 的基础流转。

## What(这次要做什么)

- 搭建最小 Pipecat pipeline
- 支持本地 wav 音频输入
- ASR 阶段先使用 mock 或已验证厂商
- LLM / TTS 允许先用 mock
- 输出 frame 流转日志和基础延迟信息

## Out of Scope（这次明确不做什么）

- 不接 FreeSWITCH
- 不做多会话
- 不做完整 barge-in
- 不接多个 ASR 厂商

## Relevant Skills（这次需要参考哪些 skill）

- `.opencode/skills/pipecat-integration/SKILL.md`
