# Bot Configuration Delta Specification

## MODIFIED Requirements

### Requirement: Componentized Bot editor

系统 MUST 将 Bot-owned 配置与 provider-owned 配置分离。Bot settings 主页面 MUST 只保留 Bot 名称、Opening message 和 System prompt；ASR、LLM、TTS 参数及凭证 MUST 分别进入对应组件的非模态右侧抽屉。抽屉打开时 MUST 压缩主工作区而不是使用阻塞遮罩。顶层 Bot 导航 MUST 增加 `Share`，用于管理当前 Bot 的发布状态、公开 Demo Link 与二维码；Share 管理接口 MUST 继续受 VoiceAgent 网站登录保护。

#### Scenario: Open and collapse a component drawer

- **WHEN** 用户点击 ASR、LLM 或 TTS 卡片
- **THEN** 对应卡片显示选中状态，右侧抽屉打开并压缩主区域；再次点击同一卡片或收起按钮时恢复原布局

#### Scenario: Keep Bot settings provider-neutral

- **WHEN** 用户查看 Bot settings 主页面
- **THEN** 页面不显示 provider 参数、API Key 或重复的 Primary language，组件卡片也不展示无历史测量来源的 latency

#### Scenario: View current navigation scope

- **WHEN** 用户查看产品栏和顶部 Tab
- **THEN** 产品栏仅包含可收缩的 VoiceAgent，顶部包含 Bot settings、Share、Sessions、Advanced；Advanced 仅展示当前 Bot 的 LLM timeout Fallback script，且不出现 Evaluation、账户、SIP line、说话顺序或 Prompt 自动生成入口

#### Scenario: Open Share for a published Bot

- **WHEN** 已登录管理员选择一个 Published Bot 并打开 `Share`
- **THEN** 页面按已确认原型展示同一 Demo Link 的二维码与 Web Link，以及 Copy、Download QR、Open demo page 和 Disable link 操作

#### Scenario: Open Share for an unpublished Bot

- **WHEN** 当前 Bot 尚未发布或不具备真实会话所需凭证
- **THEN** 页面展示不可分享状态，不产生可用公开入口，也不得伪造 Active 状态

## ADDED Requirements

### Requirement: Explicit public profile and immutable publication snapshot

系统 MUST 在 Share 页允许管理员配置独立的 `Public title` 和可选 `Public description`。首次编辑时 Public title MUST 从 Bot name 自动带入且可修改；两个公开字段不得回写 Bot name、Opening Message 或 System Prompt。发布 MUST 原子保存公开文案和完整 Bot 配置的不可变快照；后续保存草稿不得改变公开 Demo，直到管理员显式点击 `Publish updates`。

发布快照 MUST 只保存 Bot+component+provider 凭据引用，不得复制 API Key 明文或密文。同一 Provider 的 Key 被替换时旧快照 MUST 立即使用新 Key；未发布的 Provider 草稿切换不得改变旧快照；被快照引用的 Key 被清除时公开 Demo MUST 变为 unavailable，直到该凭据恢复或管理员成功重新发布。

#### Scenario: Prepare the first public profile

- **WHEN** 管理员首次打开未发布 Bot 的 Share 页
- **THEN** Public title 默认为当前 Bot name，Public description 可选且可留空，两字段都可在发布前编辑

#### Scenario: Edit a published Bot without publishing updates

- **WHEN** 管理员修改 Bot 配置或公开文案草稿并保存，但未点击 `Publish updates`
- **THEN** Share 页显示 `Unpublished changes`，已有 Demo Link 继续使用上一个发布快照

#### Scenario: Publish updates atomically

- **WHEN** 管理员点击 `Publish updates` 且配置与凭证检查通过
- **THEN** 系统在单一事务中保存新 revision、公开文案和 Bot 配置快照，保持原 Demo Link 不变，之后的新公开 Session 使用该 revision

#### Scenario: Publication fails

- **WHEN** 快照、Demo Link 或持久化任一步骤失败
- **THEN** 系统回滚本次发布，保留上一个完整已发布版本，不得产生部分更新的公开 Demo

#### Scenario: Credential rotation follows the Bot

- **GIVEN** 已发布快照引用 Bot 的 Deepgram ASR 凭据
- **WHEN** 管理员为该 Bot 替换 Deepgram ASR Key
- **THEN** 新公开 Session 使用替换后的 Key，发布 revision 与 Demo Link 不变

#### Scenario: Clearing a referenced credential suspends the Demo

- **WHEN** 管理员清除已发布快照引用的组件 Provider Key
- **THEN** Share 与公开 metadata 将 Demo 标记为 unavailable，且不得创建公开 Session；恢复该 Key 后同一链接恢复可用

#### Scenario: Hide an empty public description

- **WHEN** 已发布 Public description 为空
- **THEN** 公开 metadata 返回空值且移动 Ready 页不渲染介绍占位，不使用 Opening Message 或 Prompt 补齐

### Requirement: Stable single-Bot demo link

系统 MUST 为每个 Published Bot 最多维护一个稳定、不可枚举的 Demo Link 标识。二维码 MUST 编码该 Web Link，不得形成独立访问凭证。链接状态 MUST 在服务重启后保持；停用后不得创建新公开 Session，重新启用 MUST 恢复同一 URL。

#### Scenario: Publish a Bot for the first time

- **WHEN** 管理员发布一个配置与凭证齐备的 Bot
- **THEN** 系统原子保存 Published 状态和唯一 Demo Link，并在 Share 页展示二维码与 Web Link

#### Scenario: Disable and re-enable a link

- **WHEN** 管理员停用后重新启用 Demo Link
- **THEN** 停用期间所有新公开会话被拒绝；重新启用后原 URL 恢复有效，既有二维码无需重新下载

#### Scenario: Delete a shared Bot

- **WHEN** 管理员删除拥有 Demo Link 的 Bot
- **THEN** 对应公开入口立即不可用，且不得解析到其他 Bot

#### Scenario: Protect share management

- **WHEN** 未登录访客请求发布、启用、停用或读取后台 Share 管理数据
- **THEN** 系统使用现有产品登录策略拒绝请求，不得因为持有公开 Demo Link 获得管理权限
