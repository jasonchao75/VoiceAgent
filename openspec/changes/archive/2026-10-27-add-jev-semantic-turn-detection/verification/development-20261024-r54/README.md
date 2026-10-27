# r54：D-064候选组合失败与停止报告

结论：候选未达到采用条件，已停止，无正式默认播放器替换、无外部调用。r53短流映射通过仍有效，但不足以证明较长流/取消/编号组合。

## 实际实现与结果

新增RTPCandidateWriter将TaskAudioFrame身份接原生RTP队列；发送EOS只声明预期48k渲染样本总数，接收桥等实际解码样本覆盖才发Worklet task_end，槽仍由真实终态释放。静态/单元检查有限，不能因这个设计写EOS端到端通过。SerialRTCFixture复用现有SerialAudioOutput、ResponseRevisions、IdentifierOutput、EchoAudio永久缓存和CallCapture实际渲染回执校验。音源为本地合成资源，无厂商或客户音频。

Final实际：旧答start128样本、stop256样本（Worklet frame16384），新答start frame18176，用户提交仅1次，重复Final不重启/成功工具不重放。随后新答仅渲染1416样本因decode_coordinate_unproven停止，非14880预期完成，故整个组合FAILED。stop到新start的同渲染时钟间隔37.33ms只是本次局部衔接，不是新增E2E延迟对比或合格指标。

编号实际：跟读start128、清空后stop256，generation到1。question显示cancelled_unplayed；静态确认fixture仅将续说InterruptionFrame入队，未等其处理便直接准备question，因此续说处理把后来准备的普通答也取消，事件顺序不符合预定场景。该脚本错误不能当产品仲裁失败/成功证据。

两个场景均最后成功解码source_start11208，接着source_start12168映射hash已对应，预期chunk timestamp1253500us、960samples/48k。失败条件把“输出timestamp不在pending / rate不符 / frame长度不符”合成一个reason，未保存observed值，所以不能唯一归因，也不能猜成浏览器浮点误差后放宽容差。没有decoder_error、payload mismatch或sequence gap证据；只证明此关口失败，不能证明保留RTP技术不可行。

## 执行偏差与停机

serial-attempt.txt原命令预排两例且没有首失败停批，所以Final失败后编号仍自动执行；这是本次停止边界的脚本偏差，明确披露，不能说当时已正确fail-fast。现已停止自有8791服务（原会话56314，Ctrl-C返回终止），不重跑。测试文件改serial，后续命令必须--max-failures=1；仅静态修复，不倒改旧结果。Vite5177为本轮此前自有前端，保留供审阅，无候选服务继续发送音频。

停机后的离线修正：fixture先等待SDK marker再准备question；worker/bridge在相同失败点保留白名单observed timestamp/rate/frame数及pending keys。原JSON不补造这些字段；当前源码指纹晚于失败证据，不能把修正后代码标作实测。没有重新运行浏览器。

## 已执行检查

writer-red.txt为缺模块collection error；writer-green.txt一项通过，限源总数/EOS控制/清待发/迟到拒绝，不是实际client stop证明。serial-attempt.txt两失败，serial-final/identifier.json与combination-summary.json保存原事实。ruff/types最初失败已修，ruff-final/types-final通过，JS node语法通过；没有完整回归。

原组合复现需要进一步明确授权，当前不得执行：本地uvicorn td_rtp_candidate_app:app、前端5177、td-rtp-serial.spec.js且--max-failures=1。音频全部RTP，datachannel只有mapping/control/真实回执。测试缓存临时td-rtp-cache-*路径由系统临时目录生成保留，本轮日志不含精确路径；不声称已清理，后续仅按本fixture前缀定位，不动其他缓存。被忽略test-results保留失败trace。

## 最小下一步（未授权、未执行）

local-diagnostic-proposal.json仅建议一次固定本地连接，仍r53两个30ms合成音及最多1秒原生静音，保留现有RTP/解码设置，第一次不匹配记录白名单expected/observed便停止，不跑Final/编号、不猜容差、不换架构。费用0，未发客户数据/不调用厂商。需用户明确允许这一次诊断后才运行；或先交阶段技术审核。正式采用仍未授权，完整RTC/自测包/独立PASS/C/Gate2均未完成。
