# Docker归因纠正：r93原生反证已推翻r92旧静态结论（2026-10-26）

**撤回下文“原四个Docker输入缺失、增加四个!即可修复真实缺项”的归因。** 旧复审使用Git wildmatch检查，只证明Git语义下的结果，不能作为Docker父目录否定规则的实际排除证据。此前虽注明不是完整Docker匹配器，仍据它支持了错误缺项归因，这是本次独立审查的判断错误；旧原文保留用于追溯，不再作为当前有效结论。

R93原生scratch微型context只用哨兵、不含真实.env：原规则与加四条!规则都包含全部四个输入，也包含frontend/.env及node_modules哨兵，根.env被排除。当前反证支持的真实缺陷是**父目录例外过宽**，不是原四输入缺失。不能把哨兵进入上下文说成实际Key泄漏；现有记录未发现真实frontend/.env、未发现实际密钥外泄，也未推送镜像。R93-DOCKERIGNORE-SEMANTICS登记并披露，后续以Docker原生回归和严格新artifact证据核查，不沿用r92四项Git测试关闭真实隔离风险。

D-083已明确允许启动本机Docker Desktop及另建隔离1核1GB测试，不含停改旧容器/真实数据/付费API/部署/RTC默认采用/C/Gate2。研发已报告旧镜像Linux资源限定结果，严格新镜像原生回归/复验尚在收集；本补记只纠正旧归因，不提前独立签新镜像或全性能/RTC通过。

Jev D-082限定证据结论不受此Docker反证影响。下方全部旧Docker静态段落为历史错判，后续r93独立报告优先；本次不修改实现、运行Docker或重跑测试。

---

# r92 真实Jev＋留存ASR回放独立核查（2026-10-26）

**限定结论：新增工具及本批证据未发现确认缺陷；全产品仍INSUFFICIENT EVIDENCE，不签完整C、全Change PASS或User Gate2。**

评审按change-verifier检查新增probe、4个离线测试、授权/请求/来源hash及实际安全结果，不修改实现/测试/基线，不调用厂商/ASR/RTC，不重跑既有756/25矩阵。

## 授权封闭与工具

- D-082保留用户`call_f115da4a2e6745e5934ab4157210d66c`及原话“授权本批（上限US$0.01）”。接收方固定api.typesafe.ai/v1/systemone、jev-1.14.0，两条r91留存虚构文本+固定助手/问题，最多2次各3秒；无音频、客户数据或ASR/LLM/TTS。
- 独立重算请求SHA-256 `37366f09654e4f3f93565137e61bcf473180da107fe958fd0a34427270db7a1d`，与plan、grant及实际claim一致；来源jsonl hash与冻结来源相同，所取第5/15帧文本与请求完全匹配。当前grant=completed，授权已消费不可重放。
- main在读Key前核对准确授权，独占结果文件及started_no_replay阻止误重跑；每次实际发送前逐项比较model/state/questions与冻结序列，max_calls双层限制2，不跟随重定向。非ok/真实model或usage缺失后不继续第二次。这里只审核本批封闭边界，不授权任何新批次。
- 生产CustomTDCoordinator/SourceNormalizer/JevClient与融合/TurnClock被复用；push出口只记录提交，不接LLM、工具、TTS或播放器。无src/frontend生产改动。

## 实际结果与旧计时点事实

jsonl原记录两次status=ok，实际model=jev-1.14.0，概率/目标与summary一致：

| 请求 | noul / choice | 融合target |
|---|---|---:|
| 完整句Partial |0.7；complete0.93/incomplete0.07|963ms|
| 加“I would like to”的新Partial |0.05；complete0/incomplete1|1952.5ms|

受控静音起点6000ms。第一次主动advance到6963ms，开启原Final窗口至7163ms；新文本/真实Jev目标进入同一候选后，主动检查旧7163点，累计提交数0。再主动advance到原Tmax8500ms，提交数1，原事件reason=maximum_silence，文本是新Partial。

因此本批确实证明**真实Jev新目标进入生产状态机后，旧Final窗口不能抢交；原Tmax仍可有界提交**。未采样6000+1952.5=7952.5ms目标点，不能据本批声称恰在新目标点提交。两个Jev网络请求的真实耗时没有推进受控音频时钟，不能证明实时ASR到达竞争、实际网络耗时计算一次的整链效果或媒体性能。

input_tokens=380+384=764，按记录价US$0.042/Mtok重算估算US$0.000032088一致；实扣账单未知。两次默认64k上下文的保守估价US$0.005376低于授权预算，但不是厂商账号硬封顶。

## 离线复核与准备错误

独立执行仅新增测试：

```sh
/tmp/voiceagent-r91-py311/bin/python -m pytest -q tests/test_td_jev_replay_probe.py
```

**4 passed /3依赖警告/0.97s**，见`stage-review/r92-independent/new-offline-tests.txt`。包括dry无凭证、生产coordinator旧窗口不得抢交、首429立即停止及首目标已Tmax时明确未触发、不再付费调用第二次。

最初模块缺失红灯是工具尚未实现；后续Tmax场景红灯是准备阶段新工具处理缺口，已按明确“没有旧Final窗口则不得声称D080触发”修正。保留red/maximum-red/green及Ruff准备失败，没有将它们说成真实Jev生产规则失败或反复收费重跑。当前产品D-080规则未改动。

本次结构门禁结果见`r92-independent/change-gate.txt`，仅结构结果，不改变限定证据层级。

## 结论边界

证据级别为**external-real Jev + recorded ASR fixture + controlled clock**，不是实时ASR+Jev，也不是LLM工具/TTS取消、WPM/多语/重连/硬件/弱网/新增延迟。现有4离线测试与真实两次结果足以支持本批限定结论，未发现需要新增产品决定或扩展同类测试的确认问题。

可作为专项证据增量交后续完整独立审核；设备/资源/完整真实效果及默认RTC采用仍按既有计划未验证或待决定，不从本批提升到C/PASS/Gate2。没有新的费用授权。

## 门禁时点补记

本次读取门禁实际返回1 error/36 warnings：并行开发新登记R92-DOCKER-CONTEXT-INPUTS为Open且当时未标披露。该项涉及Docker构建上下文输入，不是本probe测试失败；评审已通知研发并在用户可见更新中披露，不并发修改status或配置。日志保留，最终状态以研发随后处理和新门禁为准，不把本时点记成PASS。

## Docker输入修复限定静态复核（后续收口）

已只读核对`.dockerignore`实际diff，仅新增四个精确放行项：frontend/demo.html、frontend/evaluation.html、frontend/login.html和scripts/deploy/verify_webrtc_production.py。它们分别为Vite声明入口和Dockerfile直接COPY输入；父目录已在原allowlist放行，不新增整个frontend或scripts的宽泛例外。

新tests/test_docker_context.py对四个目标用当前锚定allowlist做Git wildmatch审计；研发voiceagent-r92-context-red.txt为4失败、green.txt为4通过，实际文件/规则对应，评审没有重跑测试。该方法只证当前精确规则不排除必要输入，不是完整Docker pattern实现，也不是镜像构建、运行时或资源性能证明。

R92-DOCKER-CONTEXT-INPUTS现已Resolved且disclosed_to_user=true，研发最终gate.txt为0 errors/36 warnings。此前独立门禁因过渡未披露状态阻塞的记录保留，**不再是当前未处理阻塞**。本次没有启动daemon、构建镜像/容器，Linux1核1GB仍未测；Docker启动授权等待用户答复，不由静态修复代批。原Jev限定结论不变，整体仍INSUFFICIENT EVIDENCE，未签全Change PASS/C/Gate2。
