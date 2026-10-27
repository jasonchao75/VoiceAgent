# 原型迭代历史（仅供追溯）

当前状态与入口见[README](README.md)，以下旧的待确认描述和试算方案不代表当前规则。

# TD 页面原型 v0.13（待确认）

入口：[打开原型](index.html)。单文件、离线可直接打开，无 CDN、生产请求或付费 API 调用。推荐本机预览：http://127.0.0.1:8767/prototypes/index.html 。服务停止后可直接打开 HTML。

版本：v0.13，2026-10-20。草稿文件指纹：`645a450281b013036467da166e82f44c9ad5c2ea995679a110690db45146ce84`。
用户确认状态：**Pending**。本版不是冻结 baseline，不代表用户接受参数、交互或产品范围。

## 样式依据

用户亲自登录后，Agent 只读查看 https://platform.voiceagentdemo.org/ 的 Bot settings 与 Advanced，未点击保存、发布或发起通话。参考截图：`../verification/live-advanced-reference.png`。实时读取的视觉变量见 `style-reference.json`。

将当前 `frontend/src/styles.css` 原样内嵌，新增 TD 局部样式；布局保持 48px 产品栏、270px Bot 列表、52px 顶栏与 42px 页签。字体、背景、边框、薄荷绿操作色沿用线上。新增内容位于既有 Advanced 和 Sessions 上下文；没有编辑 frontend/ 正式文件，也没有部署。

## 原型路径

- Advanced → Turn Detection → Priority rules：关键词、词表、WPM、跟读停顿、规则开关。
- Advanced → Turn Detection → Silero VAD：四项 VAD 配置。
- Advanced → Turn Detection → Semantic TD：Jev 职责、三个等待配置及待确认策略。
- Advanced → General：原有 fallback 表单视觉参照。
- Sessions / Test bot：示例对话与七种 TD 判断状态，展开查看证据。

## 规格映射与确认状态

| 区域 | Delta Requirement / Scenario | 状态 |
|---|---|---|
| Semantic TD | Jev semantic turn mode; Bounded silence and cancellation; Configurable final transcript wait | 原型待确认，数值为示例 |
| Silero VAD | Jev semantic turn mode / Candidate pause；design.md Silero 参数 | 原型待确认，默认值未冻结 |
| Priority rules | Optional priority echo rules / Slow variable-length sequence pauses, User continues during echo playback, Repeated partial update | 原型待确认 |
| Assistant keywords | Assistant keyword rule condition; Stable assistant keyword context | 原型待确认；任一匹配仅示意 |
| Vocabulary / WPM / pause | Advanced rule configuration and diagnostics / Explain speed evaluation, Account for pause elapsed | 原型待确认 |
| Sessions | 上述规则与 Bounded silence / Speech resumes, Deadline without semantic result 的示例记录 | 静态场景展示，不是算法实测 |

## 验证与限制

已实际操作：页签切换、规则开关禁用、词表新增、参数错误、预览保存、七状态切换、弹窗；1440×1000、1024×1000、390×844 视口检查。页面完整记录与截图见 `../verification/ui-checklist.md`。

所有样例数字（包括 90 WPM、350ms 等）仅供看布局；无真实推理、录音、计时器、后台持久化或生效权限。保存仅更新预览状态文案，刷新会还原；Publish 不连接线上。新增第二个 Bot 仅切换展示名称，不证明配置隔离实现。

缺时间戳、生成/已播放上下文、标签到等待映射及权限/留存等 Open 产品边界显式标注，不因本次原型视为确认。Share/LLM/TTS 配置等非本次范围入口仅说明，不另做功能。

后续 Checkpoint A 必须使用正式路由和组件承载 fixture；本文件只用于 User Gate 1 原型评审，不充当正式功能或 Checkpoint A。

## v0.9 Jev 独立配置页

入口：Advanced → Turn Detection → Semantic TD → Configure Jev。页面保持同一工作区外壳，独立于 TD 等待参数，带返回入口。

- Connection：官方地址只读，API key 示意输入（请勿输入真实凭证），模型别名/指定模型、超时；Check configuration 仅校验本地字段，不声称连通成功。
- Decision questions：Noul 判断指令、Choice 分类指令及枚举增删；不是聊天式 system prompt。
- Request preview：编辑合成上下文和用户文字，查看 state/questions 请求体；排除 Key，不请求真实接口。
- 原 Elapsed time counts once 改为无底色、无边框的说明段落。

映射：Jev semantic turn mode / Candidate pause，新增 Jev configuration prototype requirement。全部为原型待确认。判断指令、枚举、800ms 超时等均为示例，不转为默认值。新增截图：prototype-jev-connection-v03.png、prototype-jev-questions-v03.png、prototype-jev-preview-v03.png、prototype-jev-preview-narrow-v03.png、prototype-semantic-help-v03.png。

## v0.9 输出与等待预览

Jev Request preview 增加明确标注的模拟输出：Noul 0.18，以及 Choice 各选项概率。此固定样例不是模型返回，不随输入自动变化。

Semantic TD 增加按状态设置的示例总静音时间和两个概率门槛，以及可编辑的模拟结果。例：complete 0.92 / selected option 0.84 → 700ms 总静音；已静音 450ms 则剩余 250ms。incomplete 示例 1500ms；低选项概率或二者冲突示例走最长静音。所有数字、映射、冲突处理均为待评审建议，不是冻结产品决定。Choice confidence 与选项概率分开，不伪装成同一个字段。新增自定义标签需要显式等待映射，当前不自动构造。

## v0.9 配置位置修正

每个 Choice 选项的“label / meaning / total wait”在 Jev → Decision questions 同行配置，Request preview 读取同一份配置试算；语义 TD 保留全局最短/最长/Final 等待。等待时间不发送给 Jev。已检查 incomplete=1800ms、已静音450ms，试算剩余1350ms；请求体未包含1800ms。当前两个概率的门槛/组合仍是示意，用户新提出加权问题，尚未冻结，不应把当前试算视为正确策略。


## v0.9 更新与验证
- 顶部提供中文 / English，默认中文；TD、Jev、判断记录共享语言选择。表单内容和协议标识不自动翻译。
- 判断问题设置 α 及选项等待；请求预览模拟完整 Choice 分布。TN / TC / 冲突 / 总等待 / 剩余等待分项可见。
- 浏览器 fixture：825/375 ms 示例、α=0/1、冲突取较长、概率和非法、已静音超过目标归零、中英切换请求不变均通过。
- 390px 判断问题、请求试算无横向溢出。截图：`../verification/prototype-fusion-zh-v07.png`、`prototype-questions-zh-v07.png`、`prototype-fusion-narrow-v07.png`。
- 仍为待确认原型，不构成正式路由、真实 Jev 集成或生产效果证明。

## v0.9 编号完整性
优先规则新增完整编号位数、独立等待保护、超时普通回复话术。16 位与 8000ms 均为示例；静音计时及提醒后关键词重判已确认；跨提醒累积及满位 / 超位待 Q-008，不提供模拟真实运行。历史 v0.7 融合截图保留原文件名。

## v0.9 页面路径和联动
- Bot settings → ASR 卡片 → 配置抽屉：四家厂商与现有模型均显示 Self-developed；其他来源仍按 Catalog 限制。
- 来源为 self_developed 才显示 Advanced → Turn Detection，General 保留；切换隐藏不删除内存草稿。
- Sessions 使用原有筛选和列表；查看样例进入详情抽屉，内含 TD 记录。Share 复用产品实际 DOM；全部发布/分享操作为原型提示。
- 本版待确认；尚未修改正式页面、Catalog、ASR 服务或持久化。Delta 映射：specs/bot-config/spec.md 的三个新增 Requirement。

## v0.10 逐 Turn 会话详情（待确认）
- 会话列表三条：demo-semantic-01 四轮、demo-number-02 两个交互分组、demo-native-03 两轮。均为 synthetic fixture。
- 对话 / 普通回复 / 延迟指标依次展示，每轮独立折叠 TD；一轮多次候选不增加普通回复次数。提供轮次跳转。
- 取代旧单一场景选择器。历史截图和已做检查保留，不能作为本版当前 DOM 的证明。
- 映射：specs/bot-config/spec.md → Per-turn TD history evidence。原型尚未冻结，无真实 API、录音或模型调用。

## v0.11 音频缓存配置
词表下新增单元音频合成 / 试听入口、当前TTS摘要、永久保存提示、50ms可调间隔、去重清单与拼接预览。无真实音频时试听禁用，Publish提示缓存缺失并阻止；不产生TTS请求。映射：Pre-generated echo audio and publish validation。详细设计见 ../echo-audio-cache.md。

## v0.12 词表行内复用
每行别名逗号分隔，共用目标、状态和试听。标题旁一键合成；间隔独立在下方。取代v0.11重复音频清单及整串试听，历史截图仅供追溯。映射：Compact vocabulary audio controls。仍为未调用TTS的待确认原型。

## v0.13 超位提醒补漏
编号完整性配置中增加独立超位话术，与未满位超时话术并列；提示短停顿提醒、不截断。映射：Configurable overlength reminder。尚无实际提醒状态机。

2026-10-20 v0.13文案修订：将笼统“时间戳/修订/重叠待确认”改为已明确的去重/续说行为和工程实现说明。时间戳专项证据见asr-event-mapping.md第8节。


## v0.14：已确认规则同步候选

本轮修正关键词必需门槛、严格分流与工具、收集/播放选择、Final改义重答、AssemblyAI ID及AEC/缓存边界；增加4轮固定会话。定向浏览器检查通过；用户尚未确认本版，未冻结基线。见[修正对照](../verification/prototype-v014/changes.md)。

### v0.14候选修订：删除额外演示区（2026-10-21）
按用户原话“原型里面不需要加这个……去掉他”，删除编号处理路径示例区、选择器和关联脚本，不迁移到其他原型区域；不改变编号业务契约。候选仍待确认。

### v0.14候选修订：清理研发说明（2026-10-21）
按D-047删除设置中的播放行为、Final修订、时序/上下文/AEC等研发说明，保留真实配置与必要填写提示。

## v0.14冻结确认（2026-10-21）
D-048记录用户对D-047清理后的当前页面确认；唯一有效基线及校验值以prototypes/README.md为准。此前候选与历史记录仅用于追溯。
