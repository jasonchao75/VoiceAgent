# Design: Adopt OpenSpec Workflow

## Decisions

1. 使用 OpenSpec 默认 `spec-driven` schema：`proposal → specs → design → tasks`。
2. 主规格按 capability 拆分，避免 Agent 为局部修改加载整份系统文档。
3. 第一版主规格以仓库已提交代码、测试和强制项目规范为事实来源。
4. 暂不安装 CLI 或修改 CI；先建立兼容目录和写作流程，后续单独评估自动校验。
5. `docs/changes/active/` 的已有 Change 原地完成；不批量迁移历史材料。
