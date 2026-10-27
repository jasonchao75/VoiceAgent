# G2-02-OVERFLOW-HISTORY 限定独立返修复审

2026-10-26；已加载canonical change-verifier，只读实现与证据，未参与返修、未启动浏览器/服务或调用厂商。

**限定结论：支持关闭 G2-02-OVERFLOW-HISTORY。** 未发现新增确认缺陷。不签完整Checkpoint C、全Change PASS或User Gate2；全产品未验证范围不因此关闭。

## 核查

1. `appendTDHistory`原回退条件仅接受conversation_utterance，确会丢掉尚无普通提交的编号轮次。当前hasTurnContent仅额外接受真实identifier_local_processed、identifier_reminder、identifier_echo_scheduled，未把任意candidate当新历史有效依据；旧call.turns回退和未归属session分组逻辑不变。没有添加提交、普通回答、LLM指标或播放事实。
2. 三项source-sha逐文件重算匹配当前源码/测试；原gate2-number-playback脚本hash也匹配。新四fixture案例在正式路由通过既有API适配进入相同历史DOM，涵盖未满位/超位×1440/390、刷新、字面值/中英切换、非committed状态及无LLM请求提示。保存红灯两项为1440下轮次缺失，修后8项4.9秒；旧历史两项及原正常多轮/未归属两项仍通过。溢出断言使用真实dialog scrollWidth/clientWidth，未更新原型或另建页面壳。
3. 独立核对本批runtime JSON：满位1次td_commit、2条conversation_utterance（用户/助手），超位0提交/0普通对话、1次identifier_reminder；各6条真实AudioWorklet回执均204。history保留编号/跟读/提醒事件，未把派发替代实际播放。原组合保存日志2项30.4秒通过；厂商/推理为替身，实际HTTP/WS/SQLite/浏览器播放器为本地真实路径，不能称真实厂商效果。
4. 本次独立执行Change门禁：0 errors / 39 warnings。未重跑已通过浏览器组合或全量；研发保存结果与当前hash一致，可作为本限定返修复核证据。

## 仍未验证

真实ASR/LLM工具选择、真实TTS听感、设备声学、手机/弱网及完整最终验收仍保留。新增fixture合并了三种identifier事件，事件分支单独覆盖主要依靠源码条件检查；这不构成当前缺陷。无需新产品决定；按原矩阵继续审核，不重复收费或旧服务实验。
