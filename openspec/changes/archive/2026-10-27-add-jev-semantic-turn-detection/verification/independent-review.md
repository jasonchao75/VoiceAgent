## 2026-10-27 用户最终决策 D-088

用户明确通过Gate2并接受剩余未验证范围转线上，授权发布。技术全范围结论仍为INSUFFICIENT EVIDENCE，未改成虚假PASS；用户风险接受优先于默认门禁要求。仅将剩余事项从本次上线前阻塞范围移出，保留未测事实与线上后续。部署需CI及健康检查，不改变RTC默认、不运行新的付费测试。

## 2026-10-27 本地专项收尾结论

**INSUFFICIENT EVIDENCE（完整Change）**；约定本地专项复验已收尾，未发现新增产品缺陷，已发现的超位历史缺陷已修复复验。新增87项规则/历史测试＋1项正式浏览器失败路径通过。配置页用户确认D087保留，其他产品确认未代填。真实模型组合、设备声学/手机弱网、RTC性能采用及完整独立C范围仍缺证据。结论及合并剩余清单见[收尾报告](gate2-intake/closeout/README.md)，各Open项见同目录remaining-items.json。旧BLOCKED为已关闭缺陷的历史记录，不是当前修复状态。

## 2026-10-26 G2-03 主动更正本地复验

正式浏览器中文混合编号提交→纯编号跟读→“不是123，是124”清空停播→89新代次流程通过（1项/13.7s），31项重复/迟到/工具隔离等回归通过。未发现新增缺陷，证据[混合输入复验](gate2-intake/mixed/README.md)。仅固定推理的本地控制流程PASS；真实LLM意图选择按D086未验证，整体仍INSUFFICIENT EVIDENCE，不代签用户Gate2。

## 2026-10-26 主审返修复验：G2-02-OVERFLOW-HISTORY 已关闭

主审重新构建并使用新隔离数据运行10项浏览器测试全部通过（32.2s），确认原超位历史缺陷已修复，未发现新增缺陷。G2-03受控工具/分流/SDK本地31项通过；真实LLM意图选择仍未验证。限定修复 PASS，整体仍 **INSUFFICIENT EVIDENCE**，不得代签User Gate2。详见[本轮独立证据](gate2-intake/identifier/reviewer-recheck/README.md)。下方旧BLOCKED为修复前历史记录。

## 2026-10-26 G2-02 浏览器播放补验 — BLOCKED

满位正式浏览器播放及历史展示通过；超位实际提醒播放通过，但刷新历史不显示只有编号/提醒、没有普通对话提交的轮次。P2 G2-02-OVERFLOW-HISTORY，定位frontend/src/td-history.js:125-128。未改生产实现，交研发修复。整体不能提交Gate2最终接受。见[复现与证据](gate2-intake/identifier/browser-playback-review.md)。

## 2026-10-26 G2-02 编号流程增量复验

限定本地检查通过：117项回归、独立6位规则样例及1项正式WS累计/清空播放组合。未发现新增确认缺陷。满位/超位提醒浏览器组合与真实TTS听感仍未验证（G2-02-REAL-REMINDER-PLAYBACK）。用户分项确认待定，整体仍 **INSUFFICIENT EVIDENCE**。见[编号复验记录](gate2-intake/identifier/README.md)。

## 2026-10-26 G2-01 配置页增量复验

六项本地正式页面/真实 API 配置测试通过；人工复核收集开关、参数保存与实际服务重启后保留通过。未发现新增确认缺陷。用户尚未验收，整体结论仍为 **INSUFFICIENT EVIDENCE**。详情见 [配置复验记录](gate2-intake/configuration/README.md)。

# Gate2接手审核（2026-10-26，r97交付增量）

**Result: INSUFFICIENT EVIDENCE（完整最终验收）；本轮交付核验和TTS限定复验未发现新增确认缺陷，可以继续分项产品验收准备。未签全Change PASS、完整C或User Gate2。**

最新接手记录及共同验收顺序：[gate2-intake/README.md](gate2-intake/README.md)。当前源输入185项hash已固定；r97关键8项生产hash匹配。主审27项定向通过；独立TTS子审35项通过（覆盖有重合，不累加冒充场景数）。主审额外启动全新离线正式WS环境，浏览器取消旧答/新答接续1 passed/6.2秒，实际渲染回执和历史证据在gate2-intake/offline-browser；无真实厂商调用。首次本机浏览器/监听权限失败已定位解决，不算产品bug。子审结论见stage-review/gate2-intake-tts.md。

无麦克风测试目前为固定转写和模拟媒体，不是任意录音真实整链；真实LLM按D086保留未验证。设备/弱网/声学AEC/完整厂商效果/精确新增性能及默认RTC采用保持原边界。用户尚未执行G2-01至G2-05共同验收，不代填接受。

本轮未修改生产代码或冻结原型，没有部署/费用。无需新增产品决定，下一步先开展正式配置页面的分项验收。下方旧BLOCKED/INSUFFICIENT EVIDENCE均保留历史时点，不据旧报告重开已修缺陷。

---

# 当前限定外部＋浏览器证据核查：r97（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（全产品最终验收）。** D085精确授权、消费记录、输入hash及真实TTS/正式WS浏览器Worklet证据核对相符，未发现新增确认阻塞。详见[evidence-review-r97.md](stage-review/evidence-review-r97.md)。本批1连接2Speak，旧答实际stopped2624样本、新答finished51840样本，不能据此宣称真实ASR/Jev/LLM整链、RTC或声学通过。

709.33ms仅一次停旧到新开播间隔；不是新增延迟或P95。预算USD0.02、实账未知；D085已消费，不重放。D086真实LLM工具暂保留未验证，非范围排除。本次仅只读，没有任何API/行为测试重跑；不签全Change PASS、Checkpoint C或User Gate2。下方旧SDK-only结论及待授权文字保留为历史时点。

---

# 当前限定外部证据核查：r95（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（全产品最终验收）。** D-084真实Flux TTS取消/替换单例的授权、hash、控制与SDK PCM来源证据已只读核对相符，未发现新增确认缺陷；详见[evidence-review-r95.md](stage-review/evidence-review-r95.md)。不签全Change PASS、完整C或User Gate2。

精确196字符/1连接2Speak批次已获D-084授权并消费；匹配旧speech身份的SpeechInterrupted后才允许新Speak，在途19200字节被屏障隔离，旧身份接受输出0，新身份49920样本。均为真实TTS控制/SDK来源证据，不等于客户端/扬声器实际停播或2080ms已听到。实账未知，预算及整文本估算不当硬封顶；不重放授权。

五项r94执行输入hash一致，无源码变化；本评审未调用任何API/测试/浏览器/Docker，未重复全量。其他voice/实时整链/设备/取消分布与默认采用仍未验证或待决定；下方“真实TTS本批待授权/未执行”属于历史时点，不再表示D-084当前状态。

---

# r94生命周期返修后的当前限定结论（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（全产品最终验收）；原r94后台任务缺陷支持关闭。** 新活跃senders集合与代次/确认状态隔离经只读源码及原独立复现确认，旧未drain任务现被join；新增两精确离线用例通过。详见[repair-review-r94.md](stage-review/repair-review-r94.md)。

旧BLOCKED原文保留，仅历史时点；当前未发现剩余确认工程/待授权探针缺陷。真实196字符TTS批次在复审时未授权未执行，不能称外部取消兼容或客户端实际停播通过；不签全Change PASS、完整C/Gate2，不调用厂商/Docker/旧WS或重复全矩阵。

---

# 当前限定工程复审：r94（2026-10-26）

**Result: BLOCKED（新增后台Interrupt任务生命周期缺陷待修）。** 发送仍await时ACK先到达，下一取消覆盖单一任务引用，cleanup只join新任务，旧任务仍存活；独立wire替身复现确认。详见[repair-review-r94.md](stage-review/repair-review-r94.md)。未代修代码，不签全Change PASS/完整C/Gate2。

其余取消屏障/原截止/旧PCM和Metadata隔离、待授权精确探针检查未发现确认问题；独立14项相关离线通过不覆盖该新窗口。196字符TTS专属费用授权仍待用户，未执行真实TTS、Docker或旧WS，不能称外部取消兼容或客户端真实停播通过。

---

# 当前限定证据复核：r93（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（全产品最终验收）。** Docker原生规则修复及严格新镜像的Linux arm64/1CPU/1GiB限定资源场景已独立核对，未发现新增确认缺陷；详见[evidence-review-r93.md](stage-review/evidence-review-r93.md)。不签完整C、全Change PASS或User Gate2。

独立真实scratch哨兵9项通过；只读inspect两本轮已停容器，实际strict镜像sha92223298…、1CPU/1GiB/无swap余量一致。冷暖正式WS各一次、Final实停/新答/来源历史，cgroup峰值187940864字节且无OOM，100ms样本统计相符。WS使用推理/VAD替身，真实无网Silero静音任务分开，不冒充完整真实链或全部容量性能。

r92 Gitwildmatch归因错误仍撤回并保留原文，当前以Docker原生语义为准，父目录例外过宽已收紧；哨兵包含不是实际Key泄漏证据。没有改停旧用户容器、付费调用、部署/推送/默认RTC采用。设备/真实负载/完整性能与其他平台范围继续未验证，不由此升级为产品通过。

---

# 当前Docker归因纠正通知：r93（2026-10-26）

**全产品仍INSUFFICIENT EVIDENCE，非完整C/PASS/Gate2。** 撤回r92基于Git wildmatch的“Docker缺四输入”归因：Docker原生微型哨兵context表明原规则和加四!行规则均包含四输入；真正暴露的是父目录例外过宽，连frontend/.env/node_modules哨兵也进入上下文。不是已经确认的实际Key泄漏，未推送镜像。详见[evidence-review-r92.md开头纠正](stage-review/evidence-review-r92.md)。

旧Git4红→4绿与r92静态复审全文保留，但不再作为Docker实际排除/修复证明。R93-DOCKERIGNORE-SEMANTICS后续以原生测试及严格新artifact复验为准；本次仅纠正文档，不改代码、不运行Docker或测试，不提前宣布新镜像/全性能/RTC通过。D-083现已批准限定启动与隔离准备，“Docker启动尚待批准”仅属旧时点历史。Jev D-082已消费批次及其他限定结论不变。

---

# r92静态构建输入收口补充（2026-10-26）

**全产品仍INSUFFICIENT EVIDENCE，非完整C/PASS/Gate2。** `.dockerignore`仅增加三个Vite HTML入口及一个Dockerfile直接COPY脚本的精确放行项，静态4红→4绿证据已只读核对；不是Docker完整匹配或镜像构建证明。R92-DOCKER-CONTEXT-INPUTS已Resolved并披露，最终门禁0 errors/36 warnings，之前过渡阻塞已处理，见[evidence-review-r92.md](stage-review/evidence-review-r92.md)。

评审未启动daemon、构建镜像或重跑测试；Docker启动授权尚待用户，1核1GB未实测。新真实Jev＋受控回放的限定结论与所有设备/完整实时效果边界保持，不扩展费用/部署/默认采用许可。

---

# 当前限定证据复核：r92（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（全产品最终验收）。** 新真实Jev＋留存ASR回放工具和本批证据未发现确认缺陷；详见[evidence-review-r92.md](stage-review/evidence-review-r92.md)。不签完整C、全Change PASS或User Gate2。

D-082准确两文本/固定提示及request/source/grant hash相符，授权已消费；两次真实Jev目标963→1952.5ms进入生产状态机，受控旧Final7163ms点0提交、原Tmax8500ms点1提交。新目标点未采样，音频时钟由执行器推进，不当作实时ASR/Jev或性能证明。独立仅4项新离线测试通过，不重跑无变化756/25或调用厂商。实账未知，估算不当硬封顶。

本限定证据与r91真实Python3.11/ASR、r90界面、原修复结论分别保留；完整实时链路、设备/资源/性能/默认采用边界仍未验证或待决定，不因本批变为产品通过。

---

# 当前限定证据复核：r91（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（全产品最终验收）。** 仅只读核对新Python3.11.15软件兼容与D-081 Flux英文否定续说单批证据，未发现新增确认缺陷；详见[evidence-review-r91.md](stage-review/evidence-review-r91.md)。不签完整C、全Change PASS或User Gate2。

实际3.11隔离环境756 JUnit成功用例、pip check及mypy79源记录相符，支持关闭旧目标环境证据限制；不证明Linux1核1GB或设备性能。D-081请求/输入hash和用户授权相符，实际1连接26完整范围帧、词汇修订和Final not保留；仅ASR/SDK/归一化，不等于TD/Jev/工具/TTS整链。预算非实扣，授权已消费不可重放。

本次无生产代码变化、无API/测试重跑，原空PCM及授权记录预门禁拦截留痕；设备/完整真实效果/性能和默认采用仍未验证或待决定。下方r90限定UI与先前修复结论保留，不因这份新证据升级为产品通过。

---

# 当前限定独立复审：r90（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（全Change最终验收）。** 本轮仅核冻结词表表头、键盘/焦点与专项计划，当前限定增量未发现剩余确认缺陷；详见[repair-review-r90.md](stage-review/repair-review-r90.md)。不签完整Checkpoint C、全Change PASS或User Gate 2。

独立发现Sessions列表晚刷新替换触发行后Escape仍聚焦隐藏close，研发已按callId最小修复；原独立复现修后返回可见按钮，双视口稳定ID回归通过，支持关闭R90-SESSIONS-REFRESH-FOCUS。表头按v0.14样式/700px断点恢复；701px oracle、Delete selector、多行定位错误与真正焦点竞态明确分流。

Chromium表头6及最终键盘10、Google Chrome原14和受影响Sessions4项、构建为本地fixture证据；不是Safari/手机/VoiceOver/硬件/真实厂商证明。专项计划尚缺冻结数据/费用/环境，未执行、未授权，不复用旧预算。不重跑未变756/25后端客户端，不启动RTC或调用厂商。下方r89来源修复与原六项结论保留，完整产品未验证范围不因本限定复审变为通过。

---

# 用户指定r89复审结论（2026-10-26）

**Result: BLOCKED。原六项返修通过；新发现一处P2页面样式偏差。核心实现方向可继续，不需要据本轮再做架构调整；尚不能签全Change独立PASS、完整Checkpoint C或User Gate2。**

本次由主审与三个未参与实现的独立分项评审执行change-verifier。未修改生产代码、既有测试或冻结基线，没有调用厂商/客户数据、没有推送部署。当前235个src/frontend/tests文件hash与r89交付快照逐项一致。

## 原问题复审

英文来源拼接、跨范围Final完整词覆盖、D080新Jev等待目标、RTC回执悬挂、完整性字段禁用及当前README入口均支持关闭。RTC晚赋/替换track通过实际重采样入口覆盖，保持PCM和严格来源判断；没有用放宽范围校验换通过。当前源码及原复现/新增正式回归均独立检查，不仅引用研发总结。

## 唯一新增确认缺陷：P2 词表表头未按冻结基线分列

`frontend/src/td-settings.css:43`仅设置列模板/gap，未设置display:grid、字号、颜色及间距。实际三标题挤在一起，计算样式display:block/16px；冻结原型为grid/10px及14px上间距。正式1440中文页面人工截图和计算样式均确认；这不是需要产品重新选择的偏离。

修复验收：恢复基线表头分列和视觉，覆盖1440/390、中英、表头与各输入/试听列对应。现有视觉测试只比较部分控件，不能证明全区域一致；将表头断言加入正式页面回归。详见[UI复审与截图](stage-review/recheck-r89-ui.md)，[样式证据](stage-review/recheck-r89-ui-evidence/vocab-header-style.json)。已登记delivery-status/tasks。

## 本次实际复跑

| 项目 | 结果 |
|---|---|
| 完整后端 | 756 passed，5条依赖弃用警告，39.02秒 |
| 全客户端单元 | 25 passed |
| 正式页面fixture独立测试 | 19 passed；包括设置、禁用、错误态、中英/桌面窄屏与部分基线，人工比较发现上述额外偏差 |
| Ruff / mypy / build | 通过；mypy为实际Python3.13、79源文件，不代表3.11 |
| 原审查复现与相关SDK路径 | 后端分项77＋107通过（有行为重合，不累加当独立覆盖）；RTC30后端＋9客户端通过 |
| 初始结构门禁 | 0 errors /39 warnings；不替代行为和产品验收 |

[后端复核](stage-review/recheck-r89-backend.md) · [RTC复核](stage-review/recheck-r89-rtc.md) · [UI复核](stage-review/recheck-r89-ui.md)。

此次未重跑全部真实API/重启或冷暖RTC组合；已核查研发r89冷暖、双响应源/渲染范围及重启原样证据，明确其为local-real媒体/存储＋推理替身，不冒充真实厂商整链或物理出声。

## Gate2剩余事项与执行建议

1. 研发修上述小样式偏差，并按受影响范围补验证；不用重复重做已经证明的架构与原六项修复。
2. 按已确认self-test-scope补真实厂商修订/续说/重连、多语/WPM及完整LLM工具/TTS取消；已有六模型英文数字基本单例不足以代替。新批次费用须单独列数据/次数/预算/停止条件授权。
3. 设备/弱网/手机Safari、耳机外放双讲/AEC、Python3.11/1核1GB目标环境及新增链路延迟仍未验证。D045允许无麦克风时交软件审核，不等于这些效果已验收。现有E2E宽区间仅证明有界证据。
4. 受控RTC仍是开发候选，默认采用未获批准。完成相应验证后明确采用范围，独立完整C通过，再由用户进行Gate2；若用户要缩小最终验收范围，须明确记录，不能由评审自行排除。

目前不需要为代码修复新增产品决定；费用/设备实测与后续RTC默认采用需在实际执行前明确。无需因最终Gate2尚未通过反复要求研发再造交包材料。既有Open未验证项继续保留披露，未因测试数量改为通过。

本轮新增材料仅分项审查文档、截图/计算样式证据及评审状态/tasks。frontend/dist为既有忽略构建产物；UI临时服务由子审停止，临时材料路径见其报告。生产代码未修改。

---

# 当前独立复审结论：r89（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（整体最终验收）；研发实现与自测包可交完整独立审查。** 原六项评审返修已Resolved，当前RTC来源缺口及SDK晚赋/替换track覆盖缺陷经独立复核支持关闭；详见[repair-review-r89.md](stage-review/repair-review-r89.md)。

独立21项相关后端通过，严格冷/暖两通各两个响应的源/渲染/同包证据重算相符。原r88失败当时缺native快照不能唯一历史归因；无效slots诊断计数0不是生产事实。保守E2E区间仍较宽，不证明精确性能、硬件声学或全部弱网/重连。

研发当前756后端/25客户端及Ruff、实际Python3.13类型79源、构建通过；原风格门禁项已修正披露，最终门禁0errors39warnings。当前68场景身份/执行选择器与22ID矩阵已核对，未将文件存在或一次单例当整个产品验收。旧任务原文完整保留，当前剩余7项明确为设备/真实完整效果/审核与用户职责，不凭数量延迟研发交包。

不设置全Change PASS、Checkpoint C或User Gate2；设备、目标环境、多语真实场景/完整取消/增量延迟和默认RTC采用仍按明确边界待验证/决定。下方r88 BLOCKED为历史时点结论，不再表示当前来源缺口仍未修；最终r89包待冻结后只补外层hash核验。

---

# 当前独立复审结论：r88（2026-10-26）

**Result: BLOCKED。** 原六项评审问题已独立复审为Resolved；正常RTC严格E2E来源区间仍为0，R88-NORMAL-RTC-SOURCE-BOUNDS继续Open，不能用播放/Final限域通过代替指标闭环。详见[repair-review-r88.md](stage-review/repair-review-r88.md)。

独立原3条复现、39项相关后端、9项回执/RTC客户端检查通过；正式RTC响应丢失故障及配置双视口证据已只读核查。故障中UI明确错误结束，历史保留started/ended_started及无停止确认事实；遥测被阻断时不声称服务器已记录确定客户端失败原因。未签完整Checkpoint C或User Gate2。

冻结返修包1104文件及15项关键当前源码hash已独立核验；archive SHA-256为`89e2c02589258d9bccecef86684ec304f63515a9fe9dca131aeee1bb899dafad`。本总入口/最终hash补记位于包外，不修改或重打冻结输入。下方全部旧审查保留历史，不代表当前六项尚未修复或新E2E红灯已关闭。

---

# 独立实现评审结论：BLOCKED（2026-10-26，r87候选）

方向可继续，但当前实现不能通过独立验收或交User Gate2。发现5项实现问题及1项交接文档问题，均已登记delivery-status与tasks。此次只改评审/决策/规格文档并保留复现脚本，没有修复生产代码、改冻结原型、调用外部厂商或推送部署。下方旧阶段评审仅历史，不能覆盖本结论。

## 需研发修复

| 优先级 | 问题与用户影响 | 定位 | 关闭条件 |
|---|---|---|---|
| P1 | B1 多段英文直接拼接，one＋two成onetwo，纯编号错走LLM；普通英文也受影响 | src/asr/transcript.py:217、227、272、283；custom_td.py:325 | 按语言/token来源保留真实边界；分段英文、跨提交切片、CJK、数字和自带空格回归 |
| P1 | B2 跨范围Final以不完整词时间切片，I do not agree可变Iagree并重答 | src/asr/transcript.py:256–272 | 切片前证明全文词覆盖；缺词时间保持未知，完整Final正常处理 |
| P1 | B3 新Jev要求等到2000ms，旧Final窗口仍在800ms提交 | src/pipeline/turn_detection.py:163–166、203–211 | 按本轮用户确认D-080遵守新目标且原最长截止不变；修正旧测试 |
| P1 | RTC回执HTTP挂起阻塞所有后续停止回执，旧任务长期占槽，新答无法播放 | frontend/src/td-rtc-entry.js:49–57；src/pipeline/serial_output.py:351–380 | 有界回执故障与关闭取消；确认不了则明确失败，不能猜停止或让新旧叠播 |
| P2 | 完整性收集关闭后四字段仍可编辑，保存忽略其值 | frontend/src/td-settings.js:91–94 | 加载和切换时正确禁用/启用；正常保存collection=null |
| P2 | README仍指r86为当前包，并称r87已完成源端链路未实现 | README.md:3–7 | 同步当前交接入口，保留旧历史但不混成当前状态 |

B2为通过真实生产适配器入口进行的本地缺字段故障注入，未声称真实厂商已出现过。B3原规格“修订不能沿用旧判断”与“Final窗口到期交最新Partial”存在口径冲突；用户本轮已选新Jev目标优先，D-080及Delta已同步，不需重复确认。其他项按既有规格修复。

## 独立复核与证据

- 本次完整后端：739 passed，5条依赖弃用警告，38.85秒；客户端单元20 passed。Ruff通过，Python3.13 mypy79文件通过，Vite build通过。不等于Python3.11验证通过。
- 审查新增行为复现：backend_repros_20261026.py为3 failed（有意按应有行为断言，B3现已有D-080确认）；RTC脚本输出requestsStarted=1、failureCallbacks=0、stopReceiptBlocked=true。主审再次复跑确认。
- UI：独立子审在正式根路由、实际生产组件、拦截API的Chromium中确认四字段disabled=false；保存实际成功但collection=null。不是另造静态壳，也不是“无法保存”的错误诊断。
- 冻结原型SHA核对匹配；既有A/B和r87实际RTC/历史证据已阅读。未重跑整个视觉/可访问性矩阵及全部RTC组合，发现阻塞后不冒签Checkpoint C。
- 初始结构门禁0errors/37warnings。最终结构门禁0 errors /43 warnings（含本次已披露问题和58项未勾任务）；结构通过不能消除行为红灯。

分项报告：[后端](stage-review/backend-review-20261026.md)、[RTC](stage-review/rtc-review-20261026.md)、[UI/API](stage-review/ui-review-20261026.md)。

复跑（仓库根目录，无真实Key或费用）：

```sh
.venv/bin/python -m pytest -q openspec/changes/add-jev-semantic-turn-detection/verification/stage-review/backend_repros_20261026.py
node openspec/changes/add-jev-semantic-turn-detection/verification/stage-review/rtc-review-receipt-hang.mjs
.venv/bin/python -m pytest -q
node --test frontend/tests/unit/*.test.js
```

## 仍未验证与后续

手机/Safari、弱网、物理AEC/耳机外放双讲、1核1GB/Python3.11目标、真实厂商多场景修订重连/完整取消/多语言效果、候选新增延迟仍未验证。六模型基本单例和本地替身不能代表这些项目。RTC仍为开发候选，默认采用没有获批；本轮不新增外部费用授权。delivery-status既有Open未验证项继续保留。

研发先修上述5项并同步文档，加入生产回归；按受影响路径重跑正式入口、全量离线和证据持久化，再交独立复审。用户已经作出D-080选择，本轮无需其他产品决定。

构建生成frontend/dist（既有忽略产物），复现证据保存在stage-review。UI初始复现脚本/tmp/td-ui-review.cjs及RTC初始/tmp/rtc-review-receipt-hang.mjs为非提交临时证据；RTC可复跑版已保存在stage-review。未生成真实录音/客户数据。

---

# 当前独立结论：r87（2026-10-26）

**Result: INSUFFICIENT EVIDENCE（整体最终验收）；研发实现与自测包可交完整独立审查。** 本次仅核查r87增量与交接准备，未完成整个Checkpoint C，不设置User Gate 2。详见[preliminary-r87.md](stage-review/preliminary-r87.md)。

新增认证RTC原生captureTime→同包hash→processed PCM→VAD候选源端→实际渲染范围未发现确认实现缺陷。独立25项后端/8项客户端通过；两个响应区间按实际双端锚重算一致，但误差宽，不能称精确低延迟或硬件声学测量。研发739后端/20客户端及当前静态检查证据不在本次重复全量。

22ID场景矩阵、当前未勾任务分类及status旧描述已收口。设备/真实多场景效果、Python3.11目标与1核1GB、手机弱网/新增延迟及受控RTC正式采用仍明确未验证或待决定；D-045允许缺设备软件阶段披露，不表示放弃最终验收证据。无新增费用授权。

没有发现的新代码缺陷不得假设出来阻止研发交包；最终独立PASS本来就应在交包后完整审查得出，不作为交包前置。下文r83 BLOCKED为历史阶段结论，不能据此继续声称r87 RTC源端尚未实现。

---

# 独立阶段审查：r83（2026-10-25）

**Result: BLOCKED — 全Change最终验收仍阻塞；本次为提前阶段审查，非Checkpoint C或User Gate 2。**

评审由未参与本次实现的独立Codex执行。使用项目change-verifier；未修改实现、未调用厂商、未重跑旧有限RTC诊断，未降低契约。

## 本次可确认的结果

- D-074确认日期/消息来源/用户原话齐全，bot-config Delta已同步“补合成失败跳过本次跟读、保留编号继续、留失败事实”；不存在新的费用授权。
- 源码路径`EchoAudio→SerialAudioOutput.stream_audio→IdentifierOutput.settled→CallCapture历史`：补合成源异常独立记录；已发送PCM申请stop并等待客户端证据，不发送正常task_end；失败来源的同文Final不重试。已播事实不被抹去。
- 独立执行`tests/test_td_serial_output.py tests/test_td_identifier_output.py tests/test_td_local_fixture_safety.py`：工作区 **9 passed /1依赖警告/1.03s**；在审核包解包目录独立cwd执行同组 **9 passed /1警告/0.72s**。使用现有Python3.13虚拟环境，未证明裸机安装或Python3.11。
- 正式公开RTC正负组合的测试源码断言与实际白名单证据相符：固定发布指纹/版本不被草稿速度污染；失败任务无回执/ready，只有一次补合成，编号从1继续12，后续clear成功。该组合使用本地推理替身，实际RTC/Worklet/HTTP/SQLite；**不是external-real，且负例失败前零PCM**。部分PCM异常停止仅本次SDK用例独立复核，未据此扩称实际RTC故障组合。
- 页面检查复用`frontend/src/main.js`根路由、Advanced/ASR/Sessions/Share正式组件及DOM；运行时API原入口。未发现另造验收壳的证据。开发RTC候选由`create_app(development_rtp_candidate=False)`默认关闭，不是正式替换。
- 冻结原型独立SHA-256匹配`657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4`。允许差异以D-056/072/073为准。本次未独立重做全视觉/可访问性检查。
- 独立Change门禁：0 errors /45 warnings /62未勾任务（审查时点）；仅结构门禁PASS，不能作为行为验收PASS。日志见`stage-review/r83-independent/`。

当前完整后端715通过由研发日志/JUnit证明；评审未重复全量，且报告已明确后续ASR Escape-only JS增量另由当前15静态/25浏览器及构建覆盖。没有把旧全量当最新原子快照。原有真实API/历史HTTP503恢复证据仅为有界中间件故障，不证明物理数据库损坏恢复。

## 两个硬阻塞与关闭条件

| 阻塞 | 当前原因 | 最小关闭步骤与验收条件 |
|---|---|---|
| H1 RTC全范围 | 受控正式入口已证明任务身份/实播/停止/Final/编号；RTC上行采集源时钟与跨连接绝对来源尚未完整闭环，手机/弱网/默认采用亦缺。是“当前范围未实现或未验证”，**不是RTP技术不可行**。 | 保留RTP与默认开关；先明确并实现可证明的上行样本→连接代次→配置VAD停声边界，再在同一正式入口保存认证源/渲染锚与保守E2E区间。断连/缺锚维持缺失，不能猜值。工程闭环后给新增延迟/设备风险结果，再请求正式采用决定。不得自行换架构。 |
| H2外部兼容 | D-062真实ASR第2连接范围失败；采样边界离线修复尚无修复后实际回包。其余六模型/修订/重连未完整实测。D-065 TTS one成功仅单例，Jev2条成功不证明语言质量/整链取消。 | 先针对保存失败事件和适配器根因完成离线检查；新素材精确hash、单模型最小请求/格式/费用/停止清单另行授权，只定位尚缺事实；不得重用旧额度或先重跑整批。之后按模型补兼容矩阵，失败即时停并保留实际证据。 |

另有完整B矩阵/目标运行环境/设备与性能的剩余项；封包后外层文档已补配置八路径：七项通过；音频试听在identifier场景素材10秒与ordinary预期0.1秒不符，切回ordinary待服务ready后单例通过2.2秒。评审只读核对最终日志与失败历史进程重启exact证据，未重复浏览器。该增量关闭r40同用例旧失败，不等于完整B统一审计或Checkpoint C。最终自测必须将每项Delta映射到具体结论，未实现、已失败、未验证分开。最终候选收敛后再进行完整独立功能/可访问性/视觉验收。

## 新缺陷与审核包

本次有限只读核查**未发现新增实现缺陷**；这不证明所有场景无缺陷。未新增产品问题，不要求重复决定D-074。

核查包：`development-20261025-r83/review-package/review-inputs.tar.gz`。审查时快照692文件，archive SHA-256 `0891015ea15a2c9ee5465562f7ee081e760ecf847f77adfcb049b177f7c0c25f`；独立逐文件哈希一致，关键两模块与对应测试同当前工作区一致。文件清单无.env/DB/音频/原始能力URL日志；包内源包含共享工作区运行上下文，不代表全由本Change修改。后续重封装必须以新package-check.json为准，不沿用该包hash。包复现依赖既有锁定环境，不保证裸机部署。

复现命令（解包目录cwd，使用已安装环境）：

```sh
/Volumes/work/OpenCode/VoiceAgent/.venv/bin/python -m pytest -q tests/test_td_serial_output.py tests/test_td_identifier_output.py tests/test_td_local_fixture_safety.py
```

需要用户决定：本次无新增产品决定；未来真实新批次费用授权及受控RTC正式采用仍须明确范围，不在本报告替用户批准。

## 冻结点后增量

上述692文件包保持原SHA，不重建。外层r83 README/config-b*.txt/restart-failed-history.json及本独立报告晚于封包，故包内文档仍是旧状态；当前结果以外层增量为准。核对源码关键模块与包一致，未用文档增量声称重跑全部715。

## 最终冻结包只读核验（2026-10-26）

研发已冻结r87包1049文件，评审独立逐文件hash与9项关键当前源码核对一致。archive SHA-256：`99db07ce117e9b73f2c37056830a305216a16acfd74b8dd6fbc0ac42f8cb9826`。包含22ID当前矩阵与任务/状态收口，R87-INDEPENDENT-HANDOFF-TRACEABILITY已Resolved。包不再重打；本冻结核验补记仅在外层报告，不声称已在包内。研发phase=ready_for_independent_review表示可以交完整审核，非产品接受。

## 最终r89冻结包只读核验（2026-10-26）

评审独立核验1176个包内文件逐项hash、13项关键当前生产/测试与前端demo.html/login.html入口一致；package-reproduction-check所列238项实测运行/测试输入hash均与最终归档清单相符。archive SHA-256：`b15cf0ac6b6bd7a5faca0e575447b8d9a88615a5577c2d282375e4e854f33e8a`。当前独立报告、68Scenario、22ID及历史任务原文存在，清单无.env/数据库/录音/trace/node_modules。

研发新目录复现126核心后端、25客户端及完整前端构建通过，不冒称包内重跑完整756；初次遗漏两个Vite HTML入口导致构建失败和依赖/缓存前置失败均保留，最终包补齐两入口且238输入一致。评审此次只读核验，不新增测试、不改包、不重打归档；本补记仅在外层报告。

**研发实现与自测交付包可交完整独立审核；全产品仍INSUFFICIENT EVIDENCE，非PASS/Checkpoint C/User Gate2。** 当前来源缺口及原六项返修支持关闭，原失败与历史非唯一归因边界保留。设备/真实完整效果/目标环境/精确性能及默认RTC采用仍如当前自测范围披露。
