# ASR范围回归的模型ID更正（r33）

r27～r32新增范围恢复用例中的Soniox/AssemblyAI参数，曾标为stt-rt-v4和universal-streaming-english；本Change目标实际为stt-rt-v5和universal-3-5-pro。这些日志只能证明对应provider归一化分支的fixture行为，不能当作目标型号Catalog/会话配置覆盖；不改写历史日志或凭空声称真实兼容。

r33在范围恢复测试入口调用正式validate_asr_options，旧ID的4项场景失败并留证；更正为正式Catalog实际ID后，目标六模型范围场景及相关配置/运行时共89项通过。六模型同时覆盖SessionConfig的深复制/冻结与凭证不入配置快照。完整结果见development-20261022-r33/model-matrix-green.txt。

目标六模型为Deepgram flux-general-en、flux-general-multi、nova-3；Speechmatics enhanced；Soniox stt-rt-v5；AssemblyAI universal-3-5-pro。真实厂商回包、语言/时间覆盖及兼容始终未验证，ID更正及fixture通过不提高证据等级。
