# VoiceAgent OpenSpec

`openspec/specs/` 是系统当前有效行为的主规格库；`openspec/changes/` 保存尚未生效的变更及其 Delta Specs。

## 目录约定

```text
openspec/
├── config.yaml
├── specs/<capability>/spec.md
└── changes/
    ├── <change-name>/
    │   ├── proposal.md
    │   ├── design.md
    │   ├── tasks.md
    │   ├── decisions/
    │   │   ├── open-questions.md
    │   │   ├── assumptions.md
    │   │   └── decision-log.md
    │   └── specs/<capability>/spec.md
    └── archive/<YYYY-MM-DD-change-name>/
```

- 主规格只描述已经完成验收并生效的行为，不记录待开发计划。
- Delta Spec 使用 `ADDED`、`MODIFIED`、`REMOVED`、`RENAMED` 表达本次变化。
- `design.md` 描述实现方式；行为要求及验收场景写入 Spec。
- `decisions/` 管理开发中才暴露的未知问题、低风险工程假设和用户已确认决定；它不是让产品经理重新检查完整需求，而是要求开发 Agent 主动识别并缩小需要确认的决策。
- `verification/delivery-status.json` 记录交付阶段、生产路径、真实外部调用授权、已知问题和未验证范围；问题一经发现必须登记并主动向用户披露。新 Change 从 `docs/engineering/templates/change-decisions/delivery-status.json` 创建。
- 归档时先把 Delta 合并进主规格，再将完整 Change 移入 `archive/`。
- OpenSpec 引入前的 Change 保留在 `docs/changes/archive/` 作为历史记录，不转换格式。
