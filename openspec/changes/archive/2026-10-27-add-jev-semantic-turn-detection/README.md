> 2026-10-27：用户D-088通过Gate2并授权上线，Change已归档且Delta合入主规格。剩余验证转线上，未测事实保留；不代表技术全范围PASS。当前发布记录见verification/release-20261027.md。下文为历史交接记录。

> 最新外部增量 r97：D085真实Flux TTS接正式WS浏览器单例通过，1连接2Speak；[证据与边界](verification/development-20261026-r97/README.md)。本批已消费，独立限定证据核查已完成；非真实ASR/Jev/LLM整链、RTC/移动/声学验收。

> 最新增量 r96：正式浏览器TTS离线组合与失败停机夹具，见 [证据/复现](verification/development-20261026-r96/README.md) 和 [独立预检](verification/stage-review/preflight-review-r96.md)。真实TTS浏览器新批授权待用户；D084已消费。本增量不签独立完整PASS、C或Gate2。

# r95当前：本批真实Flux TTS取消验证

[本批授权、真实结果与边界](verification/development-20261026-r95/README.md)：D084已消费1连接2Speak，取消ACK/19200在途旧字节隔离/新49920样本有真实SDK证据；源码沿用r94修复。不是浏览器/物理停播或完整厂商整链通过，完整C/Gate2仍未通过。下方r94“待授权”是当时记录，当前以r95及delivery-status为准。

# r94当前：TTS取消边界修复与待授权单例

[本轮实现/红绿/最终773后端/证据](verification/development-20261026-r94/README.md) · [限定独立复审](verification/stage-review/repair-review-r94.md)。取消回执前旧PCM归属、新Speak越界、网络回压本地控制及后台任务代次生命周期已修并复审关闭。真实TTS专属196字符批次仍待费用授权，尚未执行；LLM按用户选择暂缓。整体C/Gate2未通过，以下历次报告保留版本边界。

# r93当前推进

[目标Linux资源测试与Docker原生排除规则纠正](verification/development-20261026-r93/README.md)。D083启动隔离Docker测试已获批；r92旧“四输入缺项”静态归因已撤回，真实问题为父目录放行过宽，现按原生Docker验证收紧。完整性能/厂商/设备/C/Gate2边界保持，下方为历次专项证据。

# r92当前推进

[真实Jev＋留存ASR受控回放报告](verification/development-20261026-r92/README.md)：D082两请求已消费，实际更长等待目标未被旧Final抢交；明确不替代实时整链/性能。Docker构建输入缺项已静态修复，等待可运行Linux环境，不部署。此前r90/r91实现与证据保留如下，完整C/Gate2未通过。

# r91当前推进

[Python3.11实际回归与最小厂商批次准备](verification/development-20261026-r91/README.md)：756后端、79源类型及依赖检查通过；D081否定/续说ASR单例已授权执行1连接并观察真实Partial修订/完整来源，授权已消费；不代表整链效果。r90界面修复及独立复审证据保留如下；完整设备/厂商效果/性能与C/Gate2未完成。

# 当前r90返修入口

[本轮CSS/键盘红绿、截图与复现](verification/development-20261026-r90/README.md) · [厂商专项计划](verification/vendor-specialist-test-plan.md) · [设备/性能专项计划](verification/device-performance-test-plan.md) · [最新独立审核](verification/independent-review.md)。本轮是r89冻结核心包后的界面增量，原六项已独立关闭；未签完整C/Gate2，未调用付费服务或默认启用RTC候选。下方r89入口作为核心历史证据保留。

# 自建 TD：当前研发交付入口（r89，2026-10-26）

[实现与自测包/复现/剩余范围](verification/development-20261026-r89/README.md) · [当前自测报告](verification/self-test-report.md) · [22项场景矩阵](verification/current-scenario-matrix.md) · [独立审核](verification/independent-review.md)。

原r87六项问题已在r88返修复审Resolved；新增RTC晚到/替换音轨来源覆盖缺陷在r89修复。当前完整756后端/25客户端及质量构建通过，严格RTC冷/暖各两响应与历史重启/正式1440/390页通过。独立r89支持关闭当前来源缺口；r88原失败和无法唯一历史归因边界保留，不用探针错误0计数归因生产。

当前原子输入以r89/review-package/snapshot.json为准；r87/r88及旧包仅历史。Gate1冻结v0.14 SHA不变，D056/072/073/080有效决定保持。物理设备、完整厂商效果/性能及RTC默认采用仍未验证或待决定；不是独立全Change PASS、C或Gate2，不自动合规格/归档/提交推送部署，不授权新费用。

## 从哪里开始

| 阅读顺序 | 文件 | 用途 |
|---|---|---|
| 1 | [需求理解与关键注意事项](design.md) | 简短说明要做什么及开发必须守住的边界 |
| 2 | [行为规格](specs/voice-pipeline/spec.md)、[配置规格](specs/bot-config/spec.md) | 用户已确认的行为与验收契约 |
| 3 | [开发执行清单](tasks.md) | 按依赖顺序推进，每阶段都有输出和自测 |
| 4 | [交接与审核流程](handoff.md) | 研发先自测，独立审核后再交用户验收 |
| 按需 | [研发细则](appendices/development-guide.md)、[自测计划](verification/self-test-plan.md) | 实现细节、测试矩阵、证据与审核输入 |

接手还必须读取主规格、项目AGENTS、[决策记录](decisions/decision-log.md)、[开放问题](decisions/open-questions.md)、[工程假设](decisions/assumptions.md)及[真实交付状态](verification/delivery-status.json)。[proposal](proposal.md)只说明背景和范围。

## 目录职责

```text
add-jev-semantic-turn-detection/
├── README.md             # 导航与状态，不重复需求正文
├── proposal.md           # 目标、范围
├── design.md             # 需求理解＋关键注意事项（简版）
├── tasks.md              # 唯一当前开发任务清单
├── handoff.md            # 自测、独立审核、验收交接
├── specs/                # 行为与配置Delta；WHAT
├── appendices/           # 流程、适配、工具、缓存细节；HOW
├── decisions/            # 用户决定、原话、开放问题、播放选择
├── prototypes/           # v0.14已确认冻结基线
├── verification/         # 自测计划、交付状态、实际证据；后续自测/独立审核报告
└── history/              # 旧设计、旧任务与讨论解释，仅追溯
```

行为冲突先对照Delta与最新有效决定；不得由历史稿恢复已被替代的前缀本地抽取或更正正则方案。视觉以用户确认后的唯一原型基线为准，当前v0.14已按D-048冻结。

M0已完成；研发从M1执行，按[自测范围简版](verification/self-test-scope.md)与详细计划自测后提交独立审核。

## 开发顺序

M0基线与测试准备 → M1 ASR/状态底座 → M2普通TD与修订重答 → M3编号/工具/播放 → M4缓存/历史/正式页面 → M5研发自测留证 → M6独立审核 → User Gate 2。

接手及每里程碑运行：`python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection`。planning阶段结构PASS不代表功能通过；付费调用另行逐批授权。

资料索引：[ASR映射](appendices/asr-event-mapping.md) · [缓存](appendices/echo-audio-cache.md) · [更正注意事项](appendices/corrections-and-cautions.md) · [行为细节](appendices/behavior-details.md) · [已确认播放选择](decisions/playback-decisions.md) · [原型说明](prototypes/README.md) · [历史说明](history/README.md)。
