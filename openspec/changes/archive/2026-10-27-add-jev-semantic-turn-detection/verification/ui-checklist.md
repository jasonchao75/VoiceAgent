# r90 当前增量

词表表头6场景红绿，中英1440/390截图及650/701断点与冻结计算样式一致；键盘10路径Chromium、14组合Google Chrome通过；Sessions刷新修复后受影响4条另行通过，不累加不同场景。补齐Jev切页/编辑行增删/Sessions和ASR抽屉焦点、禁用跳过、可访问名称/ID与ARIA快照。证据development-20261026-r90/README.md。VoiceOver/实体手机/Safari/弱网/硬件仍未验证，计划device-performance-test-plan.md。Checkpoint C已部分独立执行，完整未通过；下方旧未开始状态仅历史。冻结基线不变。

# 2026-10-26 r89独立UI复审增量

Checkpoint C：**已部分独立执行，未通过**（下方历史not started仅为旧状态）。本次正式页面fixture中英/1440与390等19条独立通过；完整性字段禁用已关闭。人工对比发现词表表头未分列P2，见stage-review/recheck-r89-ui.md及截图/计算样式证据。待修该项并补回归；完整键盘/焦点/屏幕阅读器与跨浏览器仍未覆盖，不能签完整C/User Gate2。未更改冻结基线。

# 当前r84增量

研发B真实本地API/存储范围已逐项核对，见[证据矩阵](development-20261025-r84/checkpoint-b-matrix.json)。厂商、设备、RTC源端、独立C与Gate2不在本完成声明中；下方r82 B待核是历史状态。

# UI verification — frozen prototype and production evidence

User Gate 1: confirmed 2026-10-21 (D-048), frozen v0.14. Engineering Checkpoint A: developer fixture matrix complete (r82); B: developer local API/storage checks complete (r84); C: not started. User Gate 2: not started. Historical v0.x entries below concern prototype fixtures only; production evidence is listed separately and does not prove external vendor compatibility.

## 当前正式实现结论（r82，2026-10-25）

| 范围 | 当前可证明 | 剩余完成条件 |
|---|---|---|
| A 正式固定fixture | r42六配置子页中英×1440/390；r82六模型来源、配置四错误态、Sessions列表/头/角色/旧历史/范围/空错恢复、Share禁用/恢复/草稿；关键冻结样式和截图人工核查；D-056/D-072/D-073保留 | 研发A完成，证据见[r82矩阵](development-20261025-r82/checkpoint-a-matrix.json)；独立完整视觉/可访问性与产品验收留C/Gate2 |
| B 真实本地API/存储 | r40/r45配置/缓存/失败草稿/隔离/实际进程重启；r68/r69受控RTC实际回执/仲裁；r78播放范围、r81WS源端E2E及实际API重启 | 核对完整发布资源/运行时故障组合及最终统一矩阵；fixture不替代B，厂商和实机另外列 |
| C／Gate2 | 未开始 | 当前最终包后独立Codex审核，不自签；不得将A当用户验收 |

r82实际差异/红绿/标题遮挡/人工截图/15范围核对见[本轮报告](development-20261025-r82/README.md)。以下历史记录保留当时状态，不作为最新未完成清单。

人工检查r44桌面/390px截图：保留Sessions列表与右侧抽屉；旧播放数值标明unverified client report，旧/新回答版本同轮展示、原文和标签区分。截图使用新证据目录；不覆盖冻结原型或旧轮次截图。

以下原型v0.x与r40记录为当时证据，不能据其中“待Q-044/尚未持久化”等旧状态否定或覆盖上表；Q-044现已按D-056关闭。

## Observed reference
- [x] 只读观察线上 Bot settings 与 Advanced，用户完成登录。
- [x] 保存线上参考截图和视觉变量；内嵌当前正式 CSS，正式 frontend 无改动。

## Interaction checks
- [x] Advanced / Sessions / Bot settings 导航及 TD 三个子页切换。
- [x] 规则关闭后子项禁用，恢复开启后可编辑。
- [x] 新增词表映射并保存预览；保存不访问服务器。
- [x] 最短静音大于最长静音时展示错误，修正后可保存。
- [x] 七种场景：命中、语速过快、关键词未命中、缺时间戳、续说、最长兜底、重复 Partial。
- [x] Publish 打开原型说明弹窗，不调用发布。
- [x] 输入有标签，开关有可访问名称，表单错误使用 alert，状态使用 status；未执行完整可访问性审计。

## Responsive checks
- [x] 1440×1000 规则、语义、VAD、对话记录截图。
- [x] 1024×1000 规则页面无整页横向溢出（scrollWidth 1009 <= 1024）。
- [x] 390×844 规则、语义、VAD 与记录页面稳定布局无整页横向溢出（scrollWidth 375 <= 390）。
- [x] 390px 提示弹窗 scrollWidth=356，clientWidth=356。

首次视口切换后瞬间读取过 scrollWidth 572；重新取得稳定 UI 状态后为 375，未复现持久溢出，不修改公共布局以掩盖瞬时测量。窄屏现有顶层页签采用原产品的横向滚动行为；新浮层没有横向滚动。

## Evidence
- live-advanced-reference.png
- prototype-preview-desktop.png
- prototype-rules-desktop.png / prototype-rules-narrow.png
- prototype-semantic-desktop.png / prototype-vad-desktop.png
- prototype-decisions-desktop.png / prototype-decisions-narrow.png

## Not verified
- [ ] Real Jev / ASR / TTS, persisted configuration, real timer and echo cancellation.
- [ ] Full accessibility audit, cross-browser behavior, real phone audio.
- [ ] User acceptance and independent implementation review.

## v0.2 定向复查
- [x] Semantic TD / Silero VAD / Priority rules 改为透明底色、下划线页签；实际点击可切换对应内容。
- [x] 截图 prototype-tabs-v02.png；本轮不重复全部响应式矩阵。

## v0.3 定向验证
- [x] Semantic TD → Configure Jev → 独立页面，Connection/Decision questions/Request preview 切换。
- [x] Connection 本地校验仅显示 fields valid，明确 connectivity not tested。
- [x] 新增空枚举行后保存报错；填充 label/meaning 后保存预览成功。
- [x] Request preview 包含编辑后的枚举与示例上下文，Key 不纳入请求体。
- [x] 390×844 三个子页稳定状态 scrollWidth=375 <= 390；JSON 自动换行。
- [x] 普通计时提示无按钮边框；保存对应截图。
- [ ] 未验证真实凭证存储、Jev 鉴权/连通、限流、超时、计费、真实模型列表及指令效果。

## v0.4 定向检查
- [x] complete: p_yield 0.92、selected option p 0.84，示例 700ms 总静音减去 450ms 已过，显示剩余 250ms。
- [x] incomplete: p_yield 0.20，同样已过 450ms，显示 1500ms 总静音、1050ms 剩余。
- [x] complete 与 p_yield 0.20 冲突时显示 Tmax 示例 2500ms、2050ms 剩余。
- [x] 请求页可见固定模拟 Noul/Choice 数值，不是模型实测。
- [ ] 本轮未重复窄屏矩阵，未验证真实输出分布或概率校准。


## v0.7 定向检查（fixture）
- [x] 默认中文；TD、Jev、判断记录切换。
- [x] 切换语言不改变请求内容。
- [x] TN=790、TC=860、目标825、剩余375 ms。
- [x] α=0/1、强冲突取长等待、概率和不为1报错、超时剩余0。
- [x] 桌面与390px 判断问题 / 请求预览无横向溢出。
- [ ] 实际 Jev 返回结构、延迟与效果：未调用。

## v0.8 定向配置检查
- [x] 编号目标位数、独立保护与提醒话术展示。
- [x] 完整性开关禁用 / 启用相关字段；中英切换保留话术。
- [x] 窄屏字段不横向溢出。
- [ ] 实际计时、超时播放、关键词状态迁移未实现；满位与跨提醒累积待 Q-008。

## v0.9 定向检查（fixture，非正式实现验收）
- [x] 只读查看线上 Share / Sessions / ASR 抽屉，没有保存、发布、启动会话。
- [x] 四家六个模型均可选择 Self-developed。
- [x] provider_native / off 时隐藏自建 TD 入口，选回 self_developed 可进入；General 保留。
- [x] Bot 切换保留各自来源草稿；Nova-3 off 与原生来源禁用限制保留。
- [x] Sessions 使用筛选/列表/详情抽屉；Share 使用线上产品卡片 DOM。
- [x] 桌面会话抽屉 scrollWidth=clientWidth=544；窄屏 ASR=358/358、会话=343/343，Share 文档375<=390。
- [x] 浏览器无 JS error；通用 Off 翻译误用已修复。
- [ ] 真正全厂商自建 TD 运行、后端持久化、正式页面 A/B/C 检查未实施。

## v0.10 逐轮详情检查（fixture）
- [x] 3 条会话列表；普通语义 4 Turn / 4 TD 区 / 5 次候选，编号 2 组 / 2 TD 区 / 4 次判断，原生旧会话 2 Turn / 2 缺失提示。
- [x] 同一 Turn 续说取消与最终提交关联到一次普通回复；保留普通对话和延迟字段。
- [x] 编号用户片段与跟读交替，未提交 LLM 的收集分组不伪装为独立 LLM 轮次。
- [x] 旧会话不编造 Noul/Choice；缺失 Final 与 reasoning 指标明确未观察/未报告。
- [x] 日期筛选、轮次跳转、展开/收起、中英文切换正常；语言切换不改对话。
- [x] 390px 会话抽屉 scrollWidth=clientWidth=343；浏览器未记录 JS error。
- [ ] 真实历史API、持久化、录音与指标采集未接入；数据仅为合成fixture。

## v0.11 缓存配置原型检查（fixture）
- [x] 词表下当前 TTS 摘要、永久保存提示、生成与试听入口。
- [x] 初始4单元，两个识别词映射1时只保留3个去重单元。
- [x] 111按80ms预览为三次1，两段间隙；改间隔不发TTS请求。
- [x] 无真实音频时试听禁用；Publish显示缺失并阻止，不自动合成。
- [x] 桌面对话框宽度518/518，390px文档375<=390；浏览器无JS错误。
- [ ] 真实TTS、音频持久化、声学间隔、首播延迟与故障恢复未验证。

## v0.12 紧凑词表
- [x] 每行逗号别名、目标、音频状态、试听；标题一键合成，间隔独立下置，无重复清单。
- [x] 半角/全角逗号接受；跨行重复one被阻止。
- [x] 浏览器无JS错误；窄屏文档宽度不超过视口。
- [ ] 真实TTS/音频/存储仍未实现，不用模拟音频冒充试听。

2026-10-20文案修订检查：实现说明已显示“去重/续说不打断”和工程时间戳/串行队列任务，浏览器核对通过。未做真实ASR或播放队列验证。截图prototype-engineering-notes-v013.png。


## v0.14最新规则同步（D-048已冻结）

- [x] 关键词不可单独关闭，空值校验；整体规则开关联动。
- [x] 原型不含编号分流演示选择器；中英切换不改关键词输入。
- [x] 语义改义重答说明、新增4轮工具/重答/播放会话、原会话保留。
- [x] AssemblyAI ID修正，六模型可选self_developed；Jev825/375ms例仍正常。
- [x] 1440×1000桌面、390×844窄屏，1024设置页；会话/ASR抽屉358/358、弹窗356/356，无页面JS错误或外部请求。
- [x] 初始390px顶部操作溢出已修复，最终复测证据见prototype-v014/browser-check.json。
- [x] 用户确认来源D-048；冻结v0.14 SHA-256为657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。此项引用既有用户确认，不是研发新增验收。
- [ ] 真实厂商/音频/工具/持久化、物理AEC及完整跨浏览器/可访问性验收。

### D-047 原型说明清理复核
- [x] 设置页移除播放行为、Final修订、已耗时、上下文与AEC验收说明。
- [x] 保留真实配置字段，浏览器交互与桌面/窄屏检查通过。

## 2026-10-22 正式组件增量（非完整Checkpoint A/B）
- [x] 正式Sessions抽屉：多候选/取消/提交、Partial与Final回答版本、迟到旧范围归属、会话级未归属事件、旧会话缺证据及未验证播放数值。
- [x] 1440/390px固定fixture：跳转/展开/恶意文本转义、抽屉无横向溢出、标题顶部遮挡；桌面双列还原冻结媒体范围。截图development-20261021-r12/history-turns-*.png。
- [x] 正式历史展示已记录的等待分解与原设置；6项历史/配置/渲染浏览器回归通过，development-20261022-r13/browser.txt。
- [ ] 未完成真实API状态矩阵、重启/刷新、中英切换、完整可访问性及冻结原型完整视觉diff；不标Checkpoint A/B通过。

## 2026-10-22 正式页面本地API与恢复增量
- [x] 正式Advanced修改TD并调用完整Bot保存接口；保留其他配置和已存凭证；动态词表删除发生在保存期间时保留新草稿。
- [x] 正式顶部Publish接已有发布API；缺缓存阻止且不暗中生成；显式生成、实际WebAudio试听、改间隔保持缓存版本、成功发布、Bot隔离。
- [x] 503保存失败保留草稿和服务器旧值；重试成功清除两处错误；旧Bot迟到失败不污染新Bot。
- [x] 本地测试后端明确停进程再启动：配置、四类凭证标记、两份缓存SHA版本及音频读取保持，前后各1项通过（r15 restart-before/after）。
- [x] 正式WS/SDK/假麦克风/实际AudioWorklet回执，经正式API持久化并刷新逐轮历史；厂商全部替代。
- [x] 390px正式配置无横向溢出，数字输入空间先红后绿修复，保存通过；截图r16 formal-rules-390.png。
- [ ] 完整Checkpoint A：正式中英、所有状态/抽屉、冻结原型视觉diff和可访问性仍缺，不标通过。
- [ ] 完整Checkpoint B：本地真实API覆盖仅为上述路径；真实厂商/实机、完整失效恢复与WebRTC仍缺，不标通过。
- [ ] Checkpoint C/独立审核/User Gate2未执行，研发不自填PASS。
- [x] 正式缓存生成503后保留配置和未发布状态、按钮可用；显式重试本地API完成且不自动发布，桌面/窄屏2通过（r16 cache-failure-recovery.txt）。不证明真实TTS故障/音质。
- [x] 正式移动页本地RTC原音轨接单一audio元素，旧答截短/Final接续及结束释放通过；实际本地分句资源下双视口2通过（r20）。合成音源/假麦克风不证明真实厂商或硬件。
- [x] 正式逐轮TD历史语言入口、字段标签与原文/原始事件值隔离；同名词典对话也保持。r21中英文截图与8项固定视口矩阵通过。旧会话/动态组合标签及完整UI验收仍未闭环。
- [x] r22旧会话语言入口、缺证据标签、原文/旧指标保持及重复打开单控件；动态候选状态/回复标签翻译；8固定视口回归通过。完整UI矩阵仍未完成。
- [x] r23未知来源转写在会话级历史保留原文/连接/帧种类，不挂到错误轮次；4固定视口通过。非完整ASR恢复证明。

## r40正式UI A/B补齐（仍未签发完整检查点）

- [x] 同一正式路由/DOM由数据适配拦截fixture，冻结HTML只读对照；1440/390px rules/semantic/vad/Jev questions/preview的全部输入（含动态词表/枚举）样式/外宽一致，无匿名无名称字段和横溢。
- [x] 修复正式窄屏外层边距、独立Jev页头、语言控件、词表箭头/枚举等待单位/概率行；不新造验收产品页。
- [ ] A剩余：连接页保存Key控件原型未画，Q-044待决定；严格对照2失败保留，不更新baseline或豁免以伪报绿。
- [x] B同正式页面接真实本地API/存储：缓存准备/试听/发布阻止/失败重试/保存并发/隔离/中英/390px输入可读；actual process restart before/after保留配置、四组件保存状态及永久音频资源。素材为合成fixture，不证明厂商效果。
- [x] 正式WS实际Worklet回执验证Final取消及编号清空完整组合；历史跨钟不可算值仍缺失且原因真实。
- [ ] RTC逐任务、实机手机/弱网/AEC、完整独立可访问性/视觉回归仍未验证；Checkpoint C/Gate2不开始。

证据：development-20261022-r40/的baseline-*.png/formal-*.png、baseline-comparison-*.json及UI/WS日志。原型SHA未变。

## D-056明确批准的UI差异（2026-10-23）

Jev连接页保留显式保存Key复选框；不勾选不保存新Key。仅此控件允许偏离冻结v0.14，冻结文件及SHA不变，其他配置/布局仍按基线验证。Q-044关闭，不代表Checkpoint A/B或整包已完成。

## r45正式WS缓存恢复／历史修复

- [x] 本地正式WS：一次SDK补合成→实际Worklet开播/清空停止→持久化中英恢复记录，10.2秒通过。修复资源事件与恢复字段漏显、资源耗时误标静音。
- [x] 实际历史中英1440/390截图，播放/工具标题不回落原始英文，352个原始字段切语言保持，清空结果/位数/代次/范围可查看、无横溢。人工复核窄屏清空工具和恢复截图。
- [ ] 本例为草稿Web测试，发布资源版本明确缺失；不当作公开发布RTC入口、外部TTS或整体A/B通过。

证据development-20261023-r45/，首次UI缺字段和标题红灯保留；测试准备/locator失败不冒充行为红灯。

## r51 Sessions异常/恢复增量

- [x] 正式Sessions刷新503在本页显示alert，原错误位于隐藏通话面板已修复；重试成功清除，空列表不留旧行。1440/390px fixture两例通过，窄屏截图人工查看。
- [ ] 不证明真实API失败、厂商兼容、整体A/B或独立审核。证据development-20261023-r51/。

## D-072：已确认手机布局差异

用户选择 Q-047=B：窄屏保留现有正式全局顺序，当前页面内容在前、Bot 列表在后；桌面及 TD/Share 内容规则不变。此为明确批准的单处视觉差异，不更新冻结 v0.14 文件或校验值。对比入口为 prototypes/shell-comparison/index.html，实际正式页证据见 verification/development-20261025-r71/ui/。批准差异不等于整页或 Checkpoint A/B 已通过。

## D-073：播放指标范围

批准仅为真实播放/E2E显示有证据的范围与误差/来源，证据不足仍缺失；补认证时钟关联与持久化，不改音频传输或冻结HTML/SHA，不默认采用候选播放器，不授权费用。r78播放范围和r81 WS源端E2E/保存/展示已有本地证据；RTC源端/真实厂商/设备仍缺，不扩展范围。

### D-072正式窄屏回归

r76/ui-d072.txt：1 passed/1.3秒。正式Share卡片继续匹配冻结结构，无横溢；新增明确检查正式列表在内容后、冻结列表在内容前，approvedMobileOrder见r76/ui/share-shell-390.json。首次沙箱浏览器启动失败未执行断言，提权本机进程后通过；不当作产品行为红灯，不覆盖冻结HTML。


### r96 正式浏览器混合TTS准备
- [x] 正式 `/` 页面与原播放器；离线厂商socket/推理替身，旧任务认证开播后触发Final，实际停止后同钟新开播，真实API历史保存。证据：development-20261026-r96/wire-first。
- [ ] 同一入口真实TTS厂商组合尚待新批授权；不是物理扬声器、手机或弱网验证；不签Checkpoint C/Gate2。

- [x] r97 D085：正式WS页面真实Flux TTS，旧实播后Final实停、新答后播及认证历史单例通过，见development-20261026-r97；仅Chromium，非物理声学/RTC/移动兼容。


### G2-02历史返修
- [x] 未满位/超位无普通提交的编号/提醒仍可见，刷新、中英字面值与1440/390浮层无横向溢出；既有旧历史、正常多轮、未归属证据回归通过。
- [x] 原审核满位/超位真实本机WS/Worklet/HTTP历史2项通过，原断言未改；截图与JSON在gate2-intake/identifier/history-repair。
- [x] 独立限定复审支持关闭本缺陷，见history-repair/independent-review.md；不代签Gate2，真实厂商、设备声学、手机弱网仍未验证。
