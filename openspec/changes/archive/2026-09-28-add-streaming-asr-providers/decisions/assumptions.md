# Engineering Assumptions

## Status

- Active assumptions: 2
- Last reviewed: 2026-09-24

## Assumptions

### A-001：复用 Pipecat Service 作为协议客户端

- Status: Active
- Assumption: 优先使用项目锁定 Pipecat 版本提供的 Speechmatics、Soniox、AssemblyAI Service，并在应用层增加薄 Adapter；只有被测试证明缺失的协议能力才自定义实现。
- Basis: 当前 Deepgram Flux 已采用 Pipecat；锁定版本存在三家 Service 接口。
- Why it is low risk: 不改变 PRD 行为，Adapter 公共契约允许替换底层客户端。
- Affected work: ASR adapters、dependency extras、mock tests。
- Validation: 对照官方 wire contract 与 mock frame tests；external-real 前再次核对版本。
- Rollback: 替换单个 Registry factory，不改变 Bot/API/Pipeline 公共契约。

### A-002：Provider 专属配置采用版本化 JSON

- Status: Active
- Assumption: Provider 专属字段持久化为严格 Pydantic 校验后的版本化 JSON，而不是继续扩展大量可空列。
- Basis: 三家字段差异大且将继续变化；现有 Bot 表已包含大量 Flux 专属列。
- Why it is low risk: API 与 UI 仍使用明确字段；持久化形式不可见且可迁移回列式结构。
- Affected work: Bot storage migration、models、API tests。
- Validation: migration round-trip、schema-version compatibility、旧 Bot regression。
- Rollback: 在迁移层展开为独立列，外部契约不变。
