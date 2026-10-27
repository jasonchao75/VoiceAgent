# 阶段审核包 — add-jev-semantic-turn-detection

2026-10-23；**阶段提前审查材料已整理，完整实现/最终自测未完成。** 不请求独立PASS、Checkpoint C或User Gate 2；不把阶段审核代替最终验收。开发者没有填写independent-review.md。

只读输入副本`review-inputs.tar.gz`保留本次源码/依赖声明/精选证据，供后续工作继续时仍可审阅同一输入；SHA见snapshot.json。它不是Git提交、部署包或OpenSpec Change归档。不要覆盖现有工作区解包，使用新的临时目录。

## 评审先读

1. [阻塞收敛报告](blocker-report.md)：H1 RTC缺接与有限实验边界，最小候选A/B取舍、改动范围/风险/关闭条件。
2. [ASR/TTS逐批归因](vendor-analysis.md)：厂商回包、适配校验、SDK集成、探针缺口分开；确认/推断/未知分开。
3. [Spec→测试/结果矩阵](scenario-matrix.md)、[机器索引](scenario-matrix.json)：列出当前Delta全部Requirement/Scenario与代表用例；不是全项PASS声明。
4. [复现与运行边界](reproduction.md)、[版本/源码指纹](snapshot.json)、[证据索引](evidence-index.json)。

## 已实现与正式入口

| 能力 | 正式入口/实现链 | 已有证据与边界 |
|---|---|---|
| 四厂商六ASR配置/策略隔离 | Bot settings→ASR来源；Advanced→Turn Detection；ASRProviderRegistry→SourceOwnedASRMixin→ASRService | 本地Catalog/快照/归一化/单一提交；真实只有Flux英文一条范围成功，其余并未兼容通过 |
| 普通TD/Jev/等待/续说 | 正式Web call→POST /api/sessions→WS→CustomTDCoordinator→现有LLM流水线 | 本地SDK/WS及Jev两文本实测；Jev语言效果/P95/整链仍缺 |
| D-049 Final取消重答 | response_revision/response_scope→LLM/TTS来源隔离→WS任务播放器；原RTP队列取消 | 首有效同范围Final无含义比较、单用户提交、工具幂等；WS实际渲染证据，本地RTC仅旧答截短/新答接续 |
| 严格编号/受控工具 | identifier/rules/tools＋普通LLM受控schema；WS IdentifierOutput/SerialAudioOutput | 严格全输入/混合整句/共享状态/代次/提醒/清空有SDK/WS组合；RTC编号音频输出未接 |
| 永久缓存/发布/恢复 | Advanced→Priority rules；/api/bots/{id}/echo-audio、generate、/api/echo-assets/{version}、Publish | 本地API保存/试听/重启/版本与发布检查；WS草稿故障恢复有实际Worklet证据，公开发布RTC未闭环 |
| 历史与来源真实性 | Sessions列表/正式详情抽屉；/api/history；/api/sessions/{id}/playback-events | 原turn/response/任务关联、未归属原文、D-061失败、旧数值保留且标未验证；不能计算的播放指标保留null/原因 |
| D-061来源缺失失败 | CustomTDCoordinator→永久错误→API failed历史→正式客户端错误 | 截止前可证恢复、截止后结束/不提交工具；匿名/无接收上下文不猜当前连接；本地SDK及WS/API通过 |
| 冻结正式配置UI | 同一正式路由/组件，fixture/真实API适配 | r42六状态中英双视口、r40保存/缓存/重启等部分A/B；唯一批准差异D-056，整体A/B/C未签 |

## 未实现、失败、未验证分开

### 未实现或未接入（不能只称“缺测试”）

- RTC任务来源到实际客户端渲染的完整映射；正式RTC SerialAudioOutput/IdentifierOutput及编号串行/定向清空组合。
- D-062 digits端点精度不一致的修正算法；不是已经离线修好了等待测。
- 精确服务器/渲染跨钟关联和相应数值指标；目前缺值不是已实现的精确测量。
- 当前缺口的最终候选冻结、完整自测矩阵及最终独立审核流程。

### 已观察到的失败

- D-062 digits第7事件包含校验拒绝；同批另7例停止未执行。首continuation范围通过，不代表文字识别准确。
- D-058真实TTS超时；D-063真实首条无有效音频。SDK尾空格集成缺陷已离线修复，但真实修复后仍未成功验证。
- D-054/D-060前置映射关口未达到所要求证明，依约停止；不是技术不可行证明。后续浏览器/Final/编号组合NOT_RUN。
- 默认Python3.11全目录mypy受既有NumPy类型语法约束；实际Python3.13相关文件检查通过，二者不混报。

### 尚未验证（不能写成厂商已失败）

- 其他五个ASR目标、真实重连/跨连接绝对时钟、语言/真人/噪声和WPM实际覆盖。
- 真实LLM/TTS取消残留、TTS音质/采样覆盖与公开发布入口恢复；草稿Web测试不能代替发布RTC。
- 实机手机/Safari、弱网/丢包、物理AEC与双讲、目标1核1GB容量/调度、可靠P50/P95。
- 整体正式UI A/B状态/视觉矩阵及独立可访问性/Checkpoint C；已有配置和历史子集不扩大为全项通过。

## 评审本阶段应输出什么

请审查缺接位置、归因是否由证据支持、A候选是否有明确可实施接口、ASR边界候选应如何证明、测试/业务失败是否混淆、是否有合同或证据门槛被自行加严/放宽。可给出发现与建议，**不需要也不应给最终验收PASS**。建议反馈文件`stage-review/reviewer-findings.md`，由评审Codex自行创建；当前没有伪造该文件。正式独立流程仍在handoff.md，不因阶段包就绪被跳过。

## 当前待用户决定

Q-046：在阶段评审确认技术分解可落地后，是否允许报告A的保留RTP有限纵向工程候选，还是选择B暂保留该阻塞。没有批准正式替换，没有数据通道音频，没有新的费用请求。阶段包提交后继续不依赖该决定的必要离线工程；不扩展已通过同类测试、不提前重跑完整回归。

## 后续开发增量（不改本包原输入）

阶段提交后继续W2必要修复，见[r49说明](../development-20261023-r49/README.md)与相对封存源码的独立patch。原review-inputs.tar.gz/snapshot.json不更新；其结果仍对应阶段提交时输入，当前工作树已不同。请按封存副本审查原包、按增量审查新修复，不能把原683项结论当作修复后的最终全量。

复验准备与授权保护增量见[r50](../development-20261023-r50/README.md)：封存副本中的旧探针尚不检查已消费执行状态，**仅供审代码，不能运行任何旧收费命令**；当前实现补齐该拒绝，仍不构成新费用授权。

后续W3增量：[r51正式Sessions失败恢复](../development-20261023-r51/README.md)。原阶段输入副本不改；本轮未关闭RTC/真实厂商硬阻塞，不签整体A/B。

## 当前修复的可重建审核入口

已在隔离临时目录依次应用r49→r50→r51补丁，11个改动文件与当前工作区hash一致；具体完整比较及临时路径见[r52核验](../development-20261023-r52/README.md)。这只证明审核输入可复现，不是新增业务回归或最终验收。原包中“digits算法未实现”是r48历史状态，当前已按r49离线修复，真实确认仍未完成。

D-064用户已选择A，见[r53隔离RTP候选](../development-20261024-r53/README.md)：前置映射正常/篡改拒绝实际通过，Final/编号及正式采用尚未完成；原阶段包不重写。

重要后续：[r54候选组合失败与停止点](../development-20261024-r54/README.md)。r53短流映射通过不能扩为稳定流/Final/编号通过；本次解码坐标不匹配未唯一归因，候选停止。

[r57固定TTS one单例](../development-20261024-r57/README.md)已按D-065新授权实际成功，仅此范围；执行前门禁编排偏差亦保留。不改变RTC停止/ASR数据缺失和整体未完成状态。

[r58单次诊断与离线修复](../development-20261024-r58/README.md)：1us微秒键误拒已由真实字段定位；单包解码完成屏障离线重放通过，原生修复/Final/编号仍未验证。当前候选源码只读副本单列，不覆盖原阶段tar。

[r59 D-067隔离RTC修复确认](../development-20261024-r59/README.md)三个关口实际通过；原r54失败保留，本次不替代正式入口/E2E对照/手机兼容及采用决定。

### r60—r63正式入口增量

D-068受控接入已授权，默认旧链保留。入口接线和回执schema修复见[r61](../development-20261024-r61/README.md)；空track发送器缺陷修复及正式复测失败见[r62](../development-20261024-r62/README.md)；构建/既有兼容检查见[r63](../development-20261024-r63/README.md)。正式RTC开播仍未证明，不能将隔离通过当正式闭环，有限诊断请求待回复。原阶段源码快照不覆盖本增量，以各轮源码/记录为准，不覆盖原归档。

### r67—r69核心正式RTC组合

安装顺序与测试观测修复后，短开场原断言失败但manifest审计精确匹配；[正式Final](../development-20261025-r68/README.md)及[正式编号](../development-20261025-r69/README.md)组合本地通过，含鉴权回执/持久历史。仍缺对照延迟/平台兼容与最终完整回归，不视为最终独立验收。
