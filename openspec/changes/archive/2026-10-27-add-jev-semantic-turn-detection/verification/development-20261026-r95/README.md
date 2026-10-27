# r95 D084真实Flux取消与替换单例（2026-10-26）

**本批已执行成功，授权已消费不可重放。** 沿用已独立复审的r94取消边界修复/执行器，无源码变更、无新局部扩测。

D084用户明确授权：api.deepgram.com/v2/speak、flux-alexis-en、固定两条虚构英文196字符、24kHz单声道PCM16、1连接最多2Speak、总生命周期30秒/确认2秒、费用上限US$0.02；首异常停、无重试/重连/ASR/Jev/LLM。不发送客户数据或录音。

## 实际结果与可证明范围

- actual connections=1、Speak attempts=2，status=ok；未自动重连或追加请求。冻结plan hash/授权/独占claim相符，见../deepgram-tts-cancel-r94-plan.json、decision-log D084和delivery-status。
- 入站顺序：Connected、SpeechStarted、Flushed、**SpeechInterrupted**、新SpeechStarted、Flushed、SpeechMetadata。两个真实speech_id hash不同，取消回执匹配首speech身份；新Speak只在实际确认后发出。
- 取消发出至回执间实际仍收到**19200字节PCM16（9600样本，400ms生成音频）**；取消后的旧身份SDK输出样本为0。不是仅靠Mock残留或“没观察到”判通过。
- 替换回答实际SDK输出49920样本（24kHz下2.08秒），身份属于新response。它是**合成/SDK输出时长，不是用户听到时长**。
- billable_character_counts仅采集到新SpeechMetadata的白名单值；实际账户美元扣费未知。固定两文本按官方Flux US$0.045/千字符的整文本估算上界US$0.00882，不能用估算说已实扣，也不能把US$0.02预算当供应商账号硬封顶。

白名单原始结果deepgram-D084.jsonl，摘要result-summary.json。原日志scripts/vendor/deepgram/logs/deepgram-flux-cancel-replace-r94-v1-D-084.log已被忽略，保留不可重放claim；未保存响应headers、Key、任意供应商异常正文或新音频文件。

## 未验证与下一步

本次只证明这一voice/格式/固定输入下的真实TTS取消确认、在途音频隔离及新SDK身份。没有浏览器/AudioWorklet真实网络组合或扬声器物理停播、RTC、ASR/Jev/LLM实时整链、取消延迟分布/其他音色语言厂商证据，不将单例扩大为全部兼容。没有本次可用账单金额。完整C/Gate2仍未通过。

本批已由未参与实现的评审只读核对，见stage-review/evidence-review-r95.md，未发现新增确认缺陷；不重放已消费授权。下一步后续如做真实TTS＋正式浏览器组合，须先冻结新的数据/次数/费用/停止条件单独授权。LLM工具仍按用户“先做TTS取消”暂缓，缺模型和Key确认，不能自行调用。

执行环境使用/tmp/voiceagent-r91-py311（Python3.11.15），源码SHA沿用r94/source-sha.json；临时控制日志/tmp/voiceagent-r95-console.txt及门禁日志，未新建DB或客户录音。标准输出没有暴露密钥。原型SHA/RTP/默认RTC开关不变，无提交/推送/部署/归档。
