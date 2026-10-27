# 研发自测计划（执行细则）

状态：测试准备文档；正式核心实现、自测执行、真实厂商测试均未完成。已有业务决定不重问；自测范围已由D-045确认；原型v0.14已按D-048确认冻结，User Gate 1通过，范围认可不代表真实测试已通过。

用户先看[自测范围简版](self-test-scope.md)。本文件保留研发执行细节；确认记录见决策文件，不能把讨论过范围误写成实际测试已通过。

## 1．SDD＋TDD执行规则

按有效Delta Scenario建立测试ID→测试文件/用例→实际结果→证据映射。先观察测试因缺少目标行为失败，再最小实现、转绿及必要重构。依赖/环境错误不能冒充需求测试红灯。未冻结的可观察行为不由测试作者自选答案。

复用pytest/pytest-asyncio及现有Playwright。只测有意义的边界/不变量，不堆与实现同形的测试，不为了覆盖率指标引入生产依赖。每个里程碑先做最小定向验证，再依新变更扩展回归。

## 2．测试矩阵

| ID | 场景 | 明确断言 | 对应Delta契约 |
|---|---|---|---|
| ASR-01 | 累计Partial、重复包、分块Final、新尾部、格式化更新 | 不重复追加、不丢旧前缀/新尾部，不误标整体Final | Transcript stability；Repeated partial update |
| ASR-02 | Flux Update、Speechmatics时间、Soniox稳定/可变token、六模型 | 源事件→frame→TD文本/时间/范围可追溯；缺证据明确标记 | Transcript stability；Explain speed evaluation |
| ASR-03 | 厂商同一turn跨TD提交、迟到Final、重连 | 旧范围不重交，新范围不漏交，连接代次不混用 | Single turn authority；Transcript stability |
| TIME-01 | 最短、目标、最长、Final窗口边界前/当帧/后 | 已耗静音一次；普通路径不突破最长等待 | Bounded silence；Configurable final transcript wait |
| TIME-02 | 临界续说、疑似开口回落、取消与截止同周期 | 有效提交仅一次；旧候选/Jev/定时器不提交新文字 | Speech resumes；Transcript revision |
| TIME-03 | 空转写后迟到文字、断流、处理积压 | 不发送空白用户消息；不把未知输入假作静音，不无限挂起 | Candidate pause；Session termination及主规格 |
| JEV-01 | 完整概率融合、825/375ms例子、权重、冲突 | 计算可解释；confidence不冒充概率；数值非上线默认 | Draft semantic waiting fusion preview及当前设计 |
| JEV-02 | 缺字段/异常概率、超时、401/429/5xx、请求过期 | 不伪造语义结果、不过期提交，兜底独立且调用有界 | Bounded silence；版本要求 |
| NUM-01 | 纯编号、独立单单元/两位、快/慢、one moment | 严格全输入校验；快念仍收集；跟读须所有条件 | Strict local identifier routing；Optional priority echo rules |
| NUM-02 | 我的号码是123；不是123是124；同句123＋提问 | 整句走LLM工具；不先抽数字、更正清空完整重念 | Controlled identifier tools；Identifier followed by a question |
| NUM-03 | 重复/过期/非法/失败工具、本地后工具再次处理 | 不重复加、不凭空加、不清新代次，不假报成功 | Controlled identifier tools |
| NUM-04 | 未满/满/超位、提醒、成功后新采集、Partial修订 | 状态/位数/计时/任务一致；同轮保留、新轮清空 | Number collection completeness；New collection after success |
| PLAY-01 | 播放表P01–P11、在途未知/回执丢失 | 严格遵守用户选择，不叠播，取消旧任务不串音 | Confirmed playback arbitration |
| REV-01 | 我要办理→我不要办理有效Final | 取消对应旧生成/播放，修订上下文后重答并留痕 | Controlled response restart after material final revision |
| REV-02 | 格式/同义、重复Final、旧轮次Final、新轮次已开始 | 不多次重答、不取消新轮、不混入旧输出 | 同上 |
| REV-03 | 重答前已有成功提交/清空工具 | 不无条件重放副作用；可定位操作和修订 | Controlled tools及D-049；研发细则E |
| CACHE-01 | 别名共享、重复数字、改间隔/音色、缺文件 | 素材去重但播放次数保留，失配阻发布、间隔不重合成 | Pre-generated echo audio；Compact vocabulary |
| CACHE-02 | 运行时读取失败、临时合成失败、清空后返回 | 发布配置固定、有界失败留痕、旧任务不播放 | Runtime echo cache recovery |
| HISTORY-01 | Partial先提交、Final后到、多候选、规则直出、重答 | 真指标不伪造Final/LLM耗时，轮次和回答版本分开 | Per-turn TD history；D-049与主规格指标 |
| PRODUCT-01 | 来源切换、配置隔离、凭证错误、刷新重启、旧历史 | 已保存设置恢复、密钥不回显、持久化准确 | bot-config Delta；voice-session主规格 |
| UI-01 | 正式UI A/B、语言、空/失败状态、窄屏浮层 | 同路由/组件、对冻结基线，浮层无横向滚动 | Conditional configuration；现有Sessions/Share及项目UI规则 |
| AUDIO-01 | 正常停顿、犹豫、轻声、噪声、耳机/扬声器双讲 | 实际停说/首播可追溯，回声不被误报成功消除 | Jev semantic turn mode；跟读续说规则 |

涉及尚未完全细化的工程边界，研发先补可复现输入与实现设计；若改变体验且规格不能唯一决定，走项目澄清流程，不用mock掩盖。

## 3．证据等级与通过条件

| 类型 | 能证明 | 不能证明 |
|---|---|---|
| static | 文档/代码映射、路径与参数 | 实际接口、音质、时延 |
| fixture/mock | 状态流转、乱序、失败、假时钟 | 厂商真实事件覆盖、语义质量 |
| local-real | 本地VAD真实音频、真实持久化/页面 | 远端厂商效果、物理AEC（仅混音不够） |
| external-real | 已授权厂商实包和链路 | 未测语言、未测设备或大并发 |

确定性场景必须全部符合已冻结预期；禁止事件（重复提交、串轮、清空后旧任务回写）在用例集中为0。真实体验报告误截断、编号准确率、WPM覆盖、实际首播P50/P95、Jev调用量、队列/资源，按语言和场景分项，不用小样本冒充可靠P95。

先取基线再提出明确质量阈值及默认参数建议，请用户确认后用于最终验收；不能只看“有改善”宣称合格。未测项必须在报告及delivery-status标注，不因文档门禁PASS视为通过。

## 4．真实调用与实机范围

第一批仅验证六模型Partial时间：Deepgram Flux英文/多语种、Nova-3、Speechmatics enhanced、Soniox stt-rt-v5、AssemblyAI universal-3-5-pro。建议3段无客户信息英文念号录音，每段≤20秒，每模型各1次，最多18连接、总音频≤6分钟；不自动重试，不调用TTS造素材。

执行前提供精确文件/转写/时长/SHA-256、模型/接收方/次数、按实际费率核算的费用上限及停止条件。此前人民币10元只是建议预算，不是授权；无法确认费用上限、权限/模型/凭证异常立即停止。授权写入decision-log和delivery-status后再调用。

Jev、TTS、完整会话及客户数据另列批次授权。范围按模型支持语言执行：英文、阿语、阿英混说为主要效果目标，中文覆盖已约定编号/控制表达；并非要求英语模型支持阿语。浏览器WebSocket与已有WebRTC分别验证；电话8k接入不属于本轮自动扩大范围。

AEC实机矩阵：目标浏览器/系统＋耳机/扬声器＋人单讲/机单讲/双讲，检查实际音轨设置及机器人数字误收。没有相应设备就标未验证。目标1核1GB环境测CPU/RSS、调度延迟、队列积压及断流，不能用开发机结果冒充生产容量。

## 5．命令与结果记录

基于仓库现有工具，在项目根目录使用已配置的Python环境执行相关`pytest`、`ruff check`、`mypy`；前端按实际改动执行`npm --prefix frontend run build`及已有Playwright脚本。新增测试文件在实现阶段确定，报告写确切命令，不能只写“tests passed”。禁止普通验证使用更新快照命令覆盖冻结基线。

每里程碑运行`python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection`。研发先填[自测报告](self-test-report.md)，修复失败并回归后按[handoff](../handoff.md)交独立审核。开发者不得自行签发独立PASS或用户验收。

> 当前有效修订：D-049替代本文所有“实质改义才重答/同义不重答”旧表述。已提交Partial的当前同范围首个有效Final一律取消旧答并重答；重复/旧轮次Final不重答，已执行工具不重放。

D-050新增有效契约：Jev每会话统一100次（含失败尝试），无新页面控件；缺省及历史正数预算规范为100，耗尽后不发第101次，仍走原有最长等待保护。关闭Q-041；不授权付费测试。

## D-061：ASR范围缺失的有界失败

ASR来源身份/音频范围缺口 MUST 明确保留，MUST NOT 被无关正常帧或重连掩盖。同一轮在既有最长等待截止前取得可证明的恢复可继续；达到截止仍缺证据 MUST 以明确ASR证据错误结束当前通话并取消生成/播放、保留原转写与失败原因，MUST NOT 提交不完整用户消息、执行工具、猜来源或无限挂起。不新增页面控件/时限参数，不授权收费测试。

### Scenario: Missing source evidence reaches maximum silence
- **GIVEN** 当前停顿候选仍有未恢复的来源/范围缺口
- **WHEN** 达到当前既有最长连续静音截止，且没有新开口/待分析音频阻止截止
- **THEN** 系统记录可诊断的ASR证据错误，结束本次通话并取消生成/播放；不新增用户提交或工具副作用，原始转写/缺失原因保留

### Scenario: Proven recovery before the maximum
- **GIVEN** 当前候选存在来源/范围缺口
- **WHEN** 同来源或同SDK快照范围的真实证据在最长等待前恢复
- **THEN** 正常重新计算候选；无关新来源、下一轮或重连不能冒充恢复
