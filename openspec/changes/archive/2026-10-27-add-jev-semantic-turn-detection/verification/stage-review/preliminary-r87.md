# r87 研发候选独立交接核查（2026-10-26）

**整体最终验收：INSUFFICIENT EVIDENCE；本次新增核心实现未发现确认缺陷。** 当前受控开发候选可以连同准确自测包交完整独立审核；不能因为“最终独立PASS尚未有”而要求研发先得到PASS再交包。本次不是完整Checkpoint C，也不设置User Gate 2。默认RTC正式采用与全范围产品验收仍未通过。

独立评审使用change-verifier，未参与实现、未代修代码、未收费调用/部署/提交/推送。检查当前r87来源关联/时钟/边界与正式已有证据，复跑必要小范围测试，没有重跑浏览器或旧有限实验。

## 1. 新来源与时钟真实性

- server创建连接epoch；认证`/rtp-input`只上传固定SSRC/RTP timestamp/payload hash/captureTime记录，客户端不能提交自己的processed PCM范围。匹配依赖server实际decoder/resampler旁路证据与相同payload hash；外来epoch、时钟切换、冲突、缺包、过期不能借新数据补旧段。
- 浏览器原生captureTime与挑战采样均在**同sender worker**。worker挑战返回performance.now的16k ticks；API认证的nonce挑战/ack建立服务器因果前后界。未使用window当前时间、RTT/2或收件时刻冒充播放时刻。
- 原生captureTime相对Performance.timeOrigin、RTP timestamp标识包首采样时点有[W3C当前草案定义](https://www.w3.org/TR/webrtc-encoded-transform/#rtcencodedframemetadata)支持；此处证明的是**浏览器报告坐标**，不是物理ADC校准。server将相同媒体包内的采样偏移加到报告captureTime，只接受原始processed/decoded范围连续的证据；相邻边界不同映射不一致时返回缺失。
- VAD候选停声源位置按实际16k输入offset定位，允许迟到metadata/anchor在2秒有效期内加入；提交前冻结的来源界/证据能跨最长等待保留，续说撤销未提交候选。没有来源界时E2E仍明确缺失。
- 实际播放任务、response版本与原turn身份保留；两个Final响应关联同一原turn的源端证据。E2E区间按`[max(0,renderLower-sourceUpper), renderUpper-sourceLower]`计算，不以窗口中点伪装精确值。

评审只读重算`formal-final-history.json`两个响应：1:1约598–1335ms、1:2约815–1841ms，双端锚/源frame包络/媒体坐标匹配，原turn均1。区间很宽，只证明因果范围，**不证明精确低延迟、P95或候选性能达标**；该限制已登记R87-RTC-TIMING-PRECISION。

实际RTC/认证HTTP/Worklet与SQLite重启记录属于local-real，ASR/LLM/TTS/Jev为本机替身，不冒充external-real。`restart-history-check.json`保存原API历史完全相等。评审未独立重跑浏览器/进程重启；核查已有回执、原history与测试断言，未把两个测试准备失败当生产缺陷或通过。

## 2. 独立验证

| 范围 | 结果 |
|---|---|
| 来源ledger、CallCapture冻结、nonce时钟、认证API及原生RTP输入 | 25 passed /2依赖警告/2.22s；source-timing-tests.txt |
| uploader、sender原样旁路、optional RTC能力 | 8 passed /0 failed；capture-uploader-tests.txt |
| Change结构门禁 | 0 errors/43 warnings、51任务未勾；日志是检查时点，不等同51项实现缺失 |

日志在`stage-review/r87-independent/`。完整739后端、20客户端、Ruff、构建、实际Python3.13类型79源由研发本轮完整结果证明，评审未重复全量。默认3.11类型检查在当前NumPy存根解析失败保留，不能说3.11通过；它当前是环境/目标兼容未验证，未据此确认生产功能缺陷。

## 3. 研发交包还需什么

本次未发现需要继续编写核心生产代码才能交审的**确认缺陷**。当前最明确的交接项是准确记录，而非继续堆同类测试：

- R87-INDEPENDENT-HANDOFF-TRACEABILITY：机器状态仍有旧Open句称RTC只接WS/实际停止未证、六模型未接或B未完成，已被后续证据部分或全部覆盖。需逐项Resolved或改为准确剩余范围，保留历史失败。
- 当前22个自测ID/Delta Scenario→具体测试及实际结果/证据/限制矩阵；把r87源码、当前完整回归、旧不变实现的可复用证据与新增来源证据清楚关联。已有历史映射不能全部当当前版本。
- 未勾任务按下表分类；不凭总数认定未实现，不由研发代填独立验收。包hash冻结后再核对源与证据，不能把旧包当新源。

| 未勾类目 | 当前判断与职责 |
|---|---|
| M1-3来源/代次/范围、M2-4 Final取消/重答、M3-5串行/实播、M4-4来源与逐响应指标 | 已有本地SDK及受控正式WS/RTC实现证据；应以具体契约审计勾选或明确剩余测试，不因“完整真实重连未测/默认采用未批”一概写成未实现。审查中未找到需新增代码的确认缺陷。 |
| M4-3统一格式/间隔与AEC | 软件格式/间隔已有实现；物理外放/双讲部分按D-045明确允许当前缺设备时待测。不是新增服务端AEC的理由，也不是研发交包前必须取得设备。 |
| M5-1/4/5自测报告/原生off回归/状态与门禁 | 研发负责当前结果/失败/范围映射和可复现包。739等实际结果不能替代Scenario映射，但不要求无变化再跑全量。 |
| M5-2真实厂商 | 六模型基本单例、Jev两文本及TTS one有真实证据；完整多语种/续说/修订/真实重连、工具/取消/效果仍未验证。研发应列准确范围与最小授权计划，不自行收费、也不把未获新授权当无限延迟交包理由。 |
| M5-3设备/目标资源/参数 | 当前Mac无麦克风，D-045准许软件阶段明确待验证；手机/Safari/弱网/目标1核1GB、Python3.11及新增延迟未验证，交审核列风险/条件，不伪造通过。 |
| M6/独立C/Gate2/主规格归档 | 独立评审和用户职责，不能作为“研发先得到最终PASS才可交审核”的前置。用户验收前不合主规格/归档/提交/部署。 |
| 早期历史诊断未勾条目 | 已停止/已消费实验保留原结果；以后续授权成功证据链接说明，不能重启旧实验，也不重复计入当前待开发工作。 |

## 4. 可交接与最终接受严格区分

研发完成上述记录收口后，应直接交付**受控开发候选的实现与自测包**给完整独立审查，明确默认RTC未替换、真实效果/设备范围未验证。没有发现的新代码缺陷不应被假设出来拖延交包。

最终独立PASS仍须完整Spec/功能/可访问性/视觉检查与确认剩余范围，未验证项不得自动变PASS；D-045仅允许缺设备时明确标未验证，不等于放弃Gate2实机证据。受控RTC正式采用仍需用户基于新增延迟/设备风险决定，不由本报告默认批准。现有授权全部消费，本报告不授权新调用。

## 5. 输入包

r87源码包正在按最终记录重封，评审将以最终package-check.json核对。不使用r85/r86 hash代表r87；本报告只写评审实际执行结果，不代开发修改源或测试。

## 记录收口复核（2026-10-26）

研发新增current-scenario-matrix-r87.md，评审只读确认22个唯一ID、对应测试文件与证据入口存在，按SDK/fixture、local-real、external-real及剩余范围分开。tasks首区已把核心实现、本地验证、设备/厂商未测与独立职责分类；task-evidence标r87唯一当前入口，旧轮次为历史。status原已被后续证据关闭的6项故障已Resolved，其余Open已改为当前真正剩余边界，不再把RTC仅接WS/六模型未接/B未完成当当前事实。R87-INDEPENDENT-HANDOFF-TRACEABILITY的交接收口条件已满足，可由研发记Resolved。

**研发实现与自测包可以提交完整独立审查。** 不需要继续无变化的局部测试或等待最终独立PASS才交包。最终独立验收仍INSUFFICIENT EVIDENCE，未验证设备/真实效果/默认采用等边界如上；没有把这些事项伪装为研发已测通过。

## 最终冻结包只读核验（2026-10-26）

研发已冻结r87包1049文件，评审独立逐文件hash与9项关键当前源码核对一致。archive SHA-256：`99db07ce117e9b73f2c37056830a305216a16acfd74b8dd6fbc0ac42f8cb9826`。包含22ID当前矩阵与任务/状态收口，R87-INDEPENDENT-HANDOFF-TRACEABILITY已Resolved。包不再重打；本冻结核验补记仅在外层报告，不声称已在包内。研发phase=ready_for_independent_review表示可以交完整审核，非产品接受。
