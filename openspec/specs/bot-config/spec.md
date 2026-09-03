# Bot Configuration Specification

## Purpose

定义单实例 Demo 中 Bot 配置的持久化、密钥保存、管理接口及降级行为。

## Requirements

### Requirement: Shared Bot configuration

系统必须允许在受 Basic Auth 保护的单实例内创建、读取、更新和删除共享 Bot。Bot 保存会话所需的 ASR、TTS、LLM、Prompt 和 Opening Script 配置。

#### Scenario: Restart after creating a Bot

- **WHEN** 用户创建 Bot 后重启应用或容器，并继续使用相同数据卷
- **THEN** Bot 配置仍然存在

### Requirement: Catalog-backed Bot validation

Bot 的 provider、voice 和 LLM endpoint 必须复用服务器 Catalog 与会话配置的校验来源。

#### Scenario: Submit an unsupported configuration

- **WHEN** 用户提交非法 provider、voice 或受控 provider 的错误 base URL
- **THEN** 系统拒绝写入 Bot

### Requirement: Optional encrypted key storage

用户必须显式选择是否保存 Bot API Key。选择保存时，系统必须使用 `VOICE_AGENT_STORAGE_KEY` 加密后写入 SQLite；API 响应只能返回是否已保存密钥的布尔状态。

#### Scenario: Read a saved-key Bot

- **WHEN** 客户端查询已保存密钥的 Bot
- **THEN** 响应包含 `has_saved_keys`，但不包含密钥明文或密文

#### Scenario: Storage key is unavailable

- **WHEN** 服务未配置有效的 `VOICE_AGENT_STORAGE_KEY`
- **THEN** 应用仍可启动且纯 BYOK 路径可用，但保存或解密 Bot Key 的操作返回明确错误

### Requirement: Bot key update semantics

更新 Bot 时必须支持保留、替换和清除已保存 Key，且 Deepgram Key 与 LLM Key 必须同时存在或同时为空。

#### Scenario: Edit configuration without submitting keys

- **WHEN** 用户修改已保存 Key 的 Bot 配置但不提交新 Key
- **THEN** 系统保留原有加密 Key
