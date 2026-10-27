# r47：D-062／D-063实际批次与离线修复

## 真实授权/执行

两项均来自request_user_input_async call_0cc945e8a4a54365aa11631d7c034e31的明确授权；各≤US$0.10，固定数据/hash和停止条件已记录决策与manifest，脚本独占claim禁止重放。

- D-062：probe_td_compatibility.py --execute --authorization-decision D-062，实际2连接，各1次无重连。continuation 29个有效来源事件含Final，12.106秒；digits第7事件（window_end 2.6399999 vs最后word.end 2.64）相差0.1微秒，严格范围校验失败后4.403秒结束。其余7连接未运行，整批失败。首条识别文字明显偏离Albert合成原文；范围兼容通过不代表识别/语义效果。
- D-063：probe_td_tts.py --execute --authorization-decision D-063，one首连接2.149秒合成/格式失败即停，余2条未执行。Connected/Flush、0音频字节，未成功发送Speak。没有真实音频输出；不据此保证无连接计费，不报告确定扣费。

对应完整安全结果为同名jsonl；原始安全日志保留scripts/vendor/deepgram/logs/（忽略），未保存凭证/headers/任意异常原文。没有Jev/LLM或其他厂商调用。执行命令退出1是按首失败停，不是进程仍运行；不得重新调用这些decision。

## TTS离线工程闭环

实际SDK的sentence模式会把one变为one加尾空格，精确Speak守卫正确阻止。tts-exact-text-red.txt复现SDK自动尾空格及scope mismatch。独立单元没有连续句子分隔需要，unit_synthesis仅对其新处理器关闭_append_trailing_space，普通回复不变；没有放宽授权文本守卫。

tts-exact-text-final.txt：20 passed、1警告、1.38秒，包含真实SDK→单元renderer→精确Speak guard→假socket→PCM/SpeechMetadata全路径，实际发送one、3计费字符、480样本。tts-exact-text-green.txt仍失败是输出目录在pytest临时根下、relative_to仓库根不成立；测试将probe.ROOT限定该临时根后通过，不修改生产路径规则、不把fixture错误当需求红灯。真实D-063只留白名单阶段，不能仅据同SDK离线复现排除真实失败的其他原因；修复后未再调用。

ASR后续需以真实采样范围证明边界比较，不能随意改毫秒容差、夹断原始时间或猜来源。当前Open。所有已停授权不重放；新调用先另批明确授权。

## 检查命令

.venv/bin/pytest tests/test_td_tts_vendor_probe.py tests/test_echo_synthesis.py tests/test_echo_cache.py tests/test_echo_runtime.py -q；相关ruff；实际Python3.13 mypy src/tts/unit_synthesis.py。最后完整后端683为r46快照，早于此TTS修复，不当作修复后完整全量。
