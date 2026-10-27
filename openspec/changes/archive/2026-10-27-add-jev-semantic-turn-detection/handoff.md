# 开发、自测与独立审核交接

## 1．职责和先后顺序

| 角色 | 必须做 | 不能代替什么 |
|---|---|---|
| Integration-Developer | 按Spec与tasks实现，先做定向TDD、自测与回归，提交可复现证据 | 不自批独立审核或用户验收 |
| Codex独立审核方 | 研发自测后审查代码、状态机、真实链路、规格符合性并复跑必要测试 | 不只看研发总结，不替开发修代码后自称独立通过 |
| 用户 | Gate 1确认基线和范围，独立审核通过后Gate 2最终验收 | 不负责猜厂商字段或复核底层代码 |

本次用户要求已明确“开发完先自测，再由Codex审核实现”。后续研发就绪时交回本聊天；按项目要求由未参与实现的独立change-verifier审核。本文不是已执行的审核报告。

## 2．开工前

读取[README](README.md)指定资料和项目[AGENTS](../../../AGENTS.md)，检查工作区已有改动；当前用户工作不得覆盖。M0由当前评审Codex与用户完成：同步/核对原型、核对简版自测范围、冻结唯一基线并记录来源；Gate 1完整后研发从M1接手，不重复索要已有产品决定。已确认的D-001至D-043中被替代项以最新有效决定为准，不重问已经确定的规则。

遵循[项目开发流程](../../../docs/engineering/agent-workflow.md)、[UI交付流程](../../../docs/engineering/ui-prototype-delivery.md)及[change-delivery-guard](../../../.opencode/skills/change-delivery-guard/SKILL.md)，不另造审批流程。

## 3．研发自测交付包（审核前必备）

1. 实现版本：commit或可复现工作区标识、变更文件、启动方式及配置示例（不含密钥）。
2. Spec→测试映射：Scenario、测试文件/用例、实际命令、通过/失败、证据路径。
3. [self-test-report.md](verification/self-test-report.md)：填写实际结果，模板中的未执行不能直接勾通过；附按模型/场景的真实能力与效果范围。
4. 事件与状态证据：至少含分块/迟到Final、临界续说、编号工具、播放冲突、D-049取消重答和历史持久化。
5. UI Checkpoint A/B证据：同一正式路由/组件分别接fixture及真实API；冻结基线、桌面/窄屏、错误状态、刷新/重启与配置隔离。
6. delivery-status准确列出缺陷、未验证项、真实调用授权、剩余风险和回退步骤；原有已知缺口逐项闭环，不能换措辞隐藏。

自测不过，研发先修复并重跑受影响用例，不提交“全部通过”审核申请；无法验证的项目明确标注，不能用mock或静态证据顶替实测。

## 4．独立审核范围和结果

独立审核必须加载[Codex change-verifier](../../../.codex/skills/change-verifier/SKILL.md)及其[共享规范](../../../.opencode/skills/change-verifier/SKILL.md)。先跑Change门禁，再逐条核对Spec、决策、实现与自测证据；重点查重复提交、迟到串轮、工具副作用重放、音频取消、错误兜底及真实数据流。必要时复跑测试和请求补证，不默认研发自测结论正确。

审核结果写入`verification/independent-review.md`，包含PASS、BLOCKED或INSUFFICIENT EVIDENCE、发现项、严重程度、代码位置、复现步骤和未验证范围。当前尚未实现，因此不提前创建假PASS报告。

存在问题：研发修复→补回归自测→独立方复审。独立PASS且剩余阻塞已清除后，才进入Checkpoint C完成确认与User Gate 2；用户验收后合并主规格并归档。

## 5．门禁与边界

每个里程碑及交接前运行`python3 scripts/quality/verify_change.py add-jev-semantic-turn-detection`。planning结构PASS不是研发完成。真实付费/客户数据调用每批先明确数据、接收方、费用上限、停止条件并获授权；不自动推送、部署或更新视觉基线。

## 历史开工交接状态（2026-10-21）
User Gate 1已按D-048通过，唯一原型基线见prototypes/README.md。M0已由评审Codex与用户完成；研发从M1开始，先按Scenario写测试再实现。代码及真实链路未验证，不得跳过自测、独立审核或Gate 2，也不包含任何付费外部调用授权。

## 阶段提前审查（2026-10-23，本轮用户指定）

当前已存在实现与自测，不再沿用历史“尚未实现”描述。先交[阶段审核包](verification/stage-review/README.md)，包含阻塞归因、未接模块、候选A/B、源文件指纹、运行版本、正式入口、Spec/Scenario索引与已有证据。允许评审Codex提前提出缺陷/可实施性意见，不将它记入最终independent-review.md的PASS，也不替代完整自测及正式独立流程。阶段反馈建议独立写stage-review/reviewer-findings.md，开发者不代填。

未实现、真实失败与未验证分开；源树仍未提交/推送，其他任务改动不归本Change。材料提交后继续不受架构决定/费用阻塞的必要工作；已通过同类用例不重复扩展，最终候选收敛后再完整回归。
