# Hello诊断补丁

范围：D-090，修复诊断证据缺口，不改变ASR/VAD/话轮/打断策略。

## 事件
- asr_audio_ingress：累计进入Nova SDK run_stt的bytes、调用前后连接存在状态。每32000bytes采样；不保证远端收件。
- asr_native_result：在SDK文本过滤之前记录Results开始/时长、Final、speech_final、字符数、词数、confidence。包括空结果；不另存转写全文、密钥或音频。
- asr_text_frame：SDK发出的转写帧长度和Final，用于对照native_result与已有source_transcript。
- vad_state_changed：原状态、新状态、实际输入音频位置；不二次运行模型，不推测噪声/回声身份。
- interruption_proposed：本地VAD确认开口导致的提议，不能冒充客户端实际停播。

记录沿用会话历史。ASR额外诊断600条上限，全部新增诊断2400条上限；到顶明确记录limit事件。诊断sink异常隔离，不新增通话失败路径。

## 本地验证
127项定向测试通过（runtime/source_frames/asr_factory/review_regressions/asr_events）；Ruff格式与检查通过，mypy3源通过。真实本地Silero静音装配、空ASR消息、非空元数据不泄漏文本、连接入口、诊断限额和异常sink转发均覆盖。测试日志：/tmp/voiceagent-hello-review-20261027/diagnostic-tests.txt。

## 边界
尚未部署，不代表已采集新线上证据。旧通话缺失的原始返回无法补回。不能仅由本补丁判断声音是用户/回声/噪声；客户端实际播放仍需已有回执。没有外部付费调用。
