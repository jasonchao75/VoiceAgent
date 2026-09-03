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
    │   └── specs/<capability>/spec.md
    └── archive/<YYYY-MM-DD-change-name>/
```

- 主规格只描述已经完成验收并生效的行为，不记录待开发计划。
- Delta Spec 使用 `ADDED`、`MODIFIED`、`REMOVED`、`RENAMED` 表达本次变化。
- `design.md` 描述实现方式；行为要求及验收场景写入 Spec。
- 归档时先把 Delta 合并进主规格，再将完整 Change 移入 `archive/`。
- OpenSpec 引入前的 Change 保留在 `docs/changes/archive/` 作为历史记录，不转换格式。
