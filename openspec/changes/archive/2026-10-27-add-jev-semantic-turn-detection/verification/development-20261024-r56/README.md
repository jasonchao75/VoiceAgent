# r56：ASR冻结数据的有限离线恢复核验

目的仅尝试关闭R55数据缺失；没有RTC候选或外部厂商调用，无Key读取。已安装Albert本地语音，say -v Albert -r 135合成固定虚构原文“One two three. Four five six. Seven eight nine.”到新临时目录，再用已有ffmpeg转换16k单声道PCM16。实际82680样本/5.1675秒与原记录相同，但全文件hash a93499196b16dd1e9307ba97bedd24d246dedf995755e05bc9f20e382139966e与冻结f43daeb5ba88c445000499c4c7fed38e1ab73dc60aac834e9f7a13cfd99af2a0不同。只把同PCM用stdlib wave标准RIFF重封装的一份bb6545…也不匹配，未再尝试其他变体，未覆盖原计划/旧路径。无旧PCM hash，不能说只是元数据变化，也不能把相同时长叫同一音频。

recovery-check.json记录新目录、两个格式hash与新未批准数据路径。为避免再次只依赖临时路径，原ffmpeg版本拷贝到项目git忽略的test-results/td-vendor-inputs/20261024/digits-ready.wav；独占创建，不覆盖其他文件。未提交音频。新文件只用于准备，未被授权发送；原ASR计划和脚本仍指冻结旧数据，继续在读Key前因文件缺失拒绝。若后续决定采用新文件，需新的确切manifest/hash/执行范围及授权，不能借旧批次或TTS/RTC授权。

有限本地生成不是新增业务回归，也不证明厂商ASR质量/边界修复。现有r49离线算法证据不变。RTC最小诊断和TTS单例两个问题仍待用户回答，未重发或推定批准。保留AIFF/WAV临时目录及忽略的固定新数据，路径见JSON；不删除客户文件，不执行付费调用。最终独立PASS/C/Gate2均未开始。
