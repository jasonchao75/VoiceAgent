# r94发送任务生命周期返修复核：当前结论（2026-10-26）

**原独立确认缺陷已修复，支持Resolved；本限定工程/待授权探针未发现剩余确认缺陷。整体全产品仍INSUFFICIENT EVIDENCE，非全Change PASS、完整C或User Gate2。** 下方首次BLOCKED原文保留历史，不能再当当前未修状态。

当前实现保留全部活跃senders集合，done callback释放；cleanup/disconnect取消并join集合全部任务（排除当前task），不再只依赖单一指针。每发送任务捕获自己的generation和原deadline，只有当前未确认、且没有既有错误的同代失败可以写_interrupt_error；已获ACK的旧代次/新代次不被迟到旧错误污染。没有延长2秒预算或阻塞本地Interruption传播。

评审用**原同一独立复现**确认：distinct_sender_tasks=true、first_survived_join=false、second_done=true（修前旧task仍存活）。另仅跑两个新增精确场景，**2 passed/8 deselected/1依赖警告/0.60s**：旧未drain任务清理、旧发送失败不污染新generation。证据r94-independent/interrupt-lifecycle-after.txt与lifecycle-two-tests.txt；未扩大矩阵、未代修实现或调用厂商。初次14项执行属于返修前版本，不与这次2项相加冒称一次当前全量。研发当前16相关定向绿及Ruff/mypy79源结果由其保存，最终核心全量因代码变化应以研发后续实测结果为准，不重复由本评审跑旧771。

当前有限结论不证明真实供应商回包/无活动warning或全部原生off模式兼容。196字符专属费用授权在本复审时仍待用户，无真实TTS执行，更无浏览器/扬声器实际停播证据。待授权probe精确预算/请求/身份范围结论保持；不得把优先做TTS取消的选择当费用许可。

---

# r94 Flux取消工程与待授权探针独立复审（2026-10-26）

**当前：BLOCKED（独立发现一个后台发送任务生命周期缺陷，待研发修复复核）。** 其余限定取消屏障与探针边界检查未发现确认问题。未签全Change PASS、完整C或User Gate2；真实TTS尚未执行，不能称外部取消兼容通过。

评审使用change-verifier，不代改实现/测试，不收费、不运行Docker/旧WS，不重复全量771。仅离线实际SDK/队列与内存socket测试和独立生命周期复现。

## 确认缺陷：发送ACK先于send完成时覆盖任务引用

位置：`src/tts/confirmed_flux.py`的on_audio_context_interrupted和_cancel_interrupt_sender。

触发：第一Interrupt发送协程还在await网络返回/回压时，接收协程已处理SpeechInterrupted，屏障重新开放；另一次本地取消创建第二发送任务并覆盖`_interrupt_sender`。当前清理仅cancel/join第二任务，第一任务仍存活。它随后失败还会写共享`_interrupt_error`。这不是无限无界任务，但违反“全部session-owned发送任务在disconnect/cleanup加入”的要求，存在旧任务在已清理/新边界后写状态的风险。

独立复现用实际factory/scoped服务，只替换wire sender，ACK在第一个发送await未返回时到达；随后第二取消、调用实际_cancel_interrupt_sender。结果：`distinct_sender_tasks:true, first_survived_join:true, second_done:true`。旧任务最后由复现脚本显式取消，不留后台任务。见`r94-independent/interrupt-lifecycle-repro.py`与before.txt。

此排序对WebSocket写出后仍等待drain的异步发送是可达的工程风险；本报告没有声称已在真实厂商上抓到它。最小关闭条件是所有未结束发送任务保留会话所有权，并确保新边界/teardown后旧任务不能残留或错误覆盖新状态；研发补对应定向红绿，评审复跑原复现。无需新产品决定或额外收费。

## 已检查且目前未发现确认问题的机制

- active transport取消时立即关闭PCM接收屏障；旧未带context的wire bytes与SpeechMetadata在ACK前丢弃，避免套新context/误关闭新队列。
- 下一Speak等待同一原取消时刻起算的2秒截止，不为新回答重启TD Tmax或Final计时；缺ACK、发送失败、断连时不发送新Speak，下一合成报永久错误，不猜成功。
- 网络Interrupt发送后台化使SDK hook及时返回，原本地InterruptionFrame传播不被网络回压挡住。当前剩余问题正是该后台化任务所有权未完整覆盖上述重叠窗口。
- NO_ACTIVE_SPEECH/NO_AUDIO_GENERATED作为无活动边界允许普通流程退出屏障；真实专项将它记未触发且不发第二付费文本，不重复求通过。
- 共享Flux适配器用于原生和自建路径，正常无取消时不加网络请求。但共享路径的真实原生/off兼容尚未实测，不能只凭Mock宣布全部供应商模式通过。

## 待授权探针

`probe_td_tts_cancel.py`冻结196字符/1连接/2Speak/30秒、flux-alexis-en、24kHz单声道PCM16、速度1/expressivity0。独立重算plan hash匹配：`3be31d39bd9b083a0d0c680d0226452e7557e87cc69d3137fc86ff61a5649432`。

main先校验精确grant再读取Key，独占claim/started_no_replay防误重放；实际Speak逐条比较全文及次序，连接守卫在真实SDK握手前计数、无自动重连；首错误/身份/格式/大小/无活动场景退出，不换语音/文本补测。新Speak需要对应旧speech_id的SpeechInterrupted确认，接受PCM必须携带当前response身份。原合成已结束则未触发，不再发送第二条。

执行器记录的是SDK实际PCM输出、控制与响应来源，**没有客户端/扬声器/RTC真实停播证据**。audio_played_ms不作为客户端事实。内存Socket只替换wire、保留锁定SDK解析/队列，不是external-real。

用户选择先做TTS取消不是费用授权。复审时专属196字符批次仍待回复，没有执行；无费用许可不运行--execute。US$0.00882是196字符按已记录费率的估算，US$0.02预算不是厂商账户硬扣费封顶。

## 独立执行与范围

`pytest tests/test_flux_interrupt_boundary.py tests/test_td_tts_cancel_probe.py tests/test_confirmed_flux.py -q`实际14 passed /2依赖/SDK弃用警告/1.26s（取消8+新探针3+Configure3），见affected-tests-first.txt。现有14项通过没有覆盖上面的sender重叠窗口，不能用它们消除独立复现。

旧PCM重贴新身份与新Speak提前的原始红灯，以及hook回压红灯由研发保留；最初配置voice/Sink StartFrame/Runner用法等是测试准备错误，不当作厂商错误或多轮收费证据。完整最终质量与包待研发收口，本报告不拿中间全量值或原r93镜像冒充含此新修复。
