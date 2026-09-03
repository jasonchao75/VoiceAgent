# Delta: Change Governance

## ADDED Requirements

### Requirement: Current-state specification library

项目必须在 `openspec/specs/<capability>/spec.md` 中维护已经验收并生效的系统行为。主规格不得包含尚未完成的计划。

#### Scenario: Agent starts a behavior-changing task

- **WHEN** Agent 准备修改某项系统行为
- **THEN** Agent 先读取相关 capability 的主规格，再起草本次 Change

### Requirement: Delta specification

影响系统行为的 Change 必须在 `specs/<capability>/spec.md` 中用 `ADDED`、`MODIFIED`、`REMOVED` 或 `RENAMED` 描述相对主规格的变化。

#### Scenario: Existing behavior changes

- **WHEN** Change 调整主规格中已有 Requirement
- **THEN** Delta Spec 使用 `MODIFIED Requirements` 写出修改后的完整 Requirement 及验收场景

### Requirement: Spec merge before archive

Change 完成实现、验证和用户验收后，必须先把 Delta Specs 合并进主规格，再归档完整 Change。

#### Scenario: Archive an accepted Change

- **WHEN** 用户确认 Change 已通过验收
- **THEN** 主规格反映最终实际行为，Change 被移动到带日期的 archive 目录
