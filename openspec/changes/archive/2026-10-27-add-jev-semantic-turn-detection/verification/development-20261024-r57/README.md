# r57：D-065 TTS one新单例真实成功

2026-10-24用户request_user_input_async call_9b2d2cd5108c4172b0576a5e419cfe17第0项明确“授权此 TTS 单例（上限 US$0.02）”，决策D-065及执行账本先登记。唯一实际命令为.venv/bin/python scripts/evaluation/probe_td_tts.py --single-unit-confirmation --execute --authorization-decision D-065。无重试、换voice、额外文本或其他服务，无客户数据。RTC未运行，单次诊断仍未授权。

## 实际结果与关闭范围

唯一连接3.155秒完成，精确Speak one与Flush各一次成功，收到Connected/SpeechStarted/Flushed/SpeechMetadata。3计费字符，34560音频字节，24k单声道PCM16、17280样本/0.72秒，WAV SHA62e05cc6b82e8a80b23b57a0bf271b176e7e1b717f2cd4e1aabe1fdc3d1a2bcc。audio-check.json校验非零样本、峰值/RMS/格式；音频未试听、未客户端实际播放。原音频及完整安全日志在git忽略的scripts/vendor/deepgram/logs/deepgram-td-tts-one-confirmation-v1-D-065/和同名.log保留；本目录只复制白名单JSONL与检查结果，不提交音频或Key。

本例证明r47精确单元修复后的固定voice/format/one真实SDK单元路径可用，关闭R47-D-063-REAL-FAILURE对应当前单元缺口。不能反推旧D-063无音频只有尾空格一种根因，不把新成功覆盖旧失败，也不把one推广为three-text全批、其他音色/采样、取消/缓存或RTC端到端完成。

费用按2026-10-24官方公开0.045美元/千字符及厂商3字符报告估算0.000135美元，上限0.02；实际账户扣费/最低计费/发票未查，不能叫实际美元支出。执行状态已completed，旧授权和本批余量不得重放。

## 执行前门禁偏差

gate-before.txt为非零：external_calls[8] missing provider。授权记录含精确recipient/hash/次数/金额/确认来源但漏门禁必需provider字段。同一工具编排在前一步非零后仍启动调用，这是研发执行编排错误；已主动披露，不伪称执行前门禁通过。补provider=Deepgram TTS，不改变授权范围；后续门禁另存gate-final.txt。禁止重跑本批来弥补门禁。之后门禁与外部调用必须分开读取退出码再运行，保留原非零证据。单例实际未超范围/次数/费用请求，也无密钥输出。

## 后续边界

H2整体仍Open：原ASR固定WAV缺失，新生成文件hash不符且未授权发送；其余ASR目标/重连、真实TTS取消/听感/全链仍缺。RTC r54组合失败后保持停止。没有跑完整回归、未更新冻结原型/原阶段tar、未标独立PASS/Checkpoint C/User Gate2。当前目标继续保留，等待独立RTC诊断答复，其他后续调用仍逐批授权。
