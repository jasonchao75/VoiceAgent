# Adopt OpenSpec Workflow

## Why

原有 Change 能约束单次开发，但缺少持续描述系统现状的主规格库，也无法清晰区分本次行为变化与实现设计。

## What Changes

- 建立 `openspec/specs/` 主规格库。
- 后续 Change 使用 capability 级 Delta Specs 表达新增、修改和删除的行为。
- 行为规格与技术设计分离。
- 保留旧 Change，避免迁移进行中任务造成执行上下文变化。

## Impact

- 修改项目协作规范和文档导航，不改变 VoiceAgent 运行逻辑。
- 新流程从本 Change 完成后创建的需求开始适用。
