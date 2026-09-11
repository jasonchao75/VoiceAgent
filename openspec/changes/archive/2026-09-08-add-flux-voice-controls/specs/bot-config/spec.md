## ADDED Requirements

### Requirement: Deepgram Flux voice tuning

系统 MUST 允许用户按 Bot 配置 Deepgram Flux `expressivity` 与 `speed`，保存后再次编辑必须完整回显。现有 Bot 必须保持 `expressivity=0`、`speed=1.0` 的既有声音行为。

#### Scenario: Configure a more expressive Flux voice

- **WHEN** 用户选择 Deepgram Flux，将 Expressivity 设为 `1`，并将 Speed 设为 `1.05`
- **THEN** Bot 保存两个值，页面再次打开时回显相同配置，后续会话使用相同配置

#### Scenario: Reject invalid Flux controls

- **WHEN** Expressivity 不是 `-2..2` 的整数，或 Speed 不在 `0.85..1.15` 的 `0.05` 步长内
- **THEN** API 拒绝保存，不得静默截断或修正

#### Scenario: Edit a legacy Bot

- **WHEN** 数据库中的旧 Bot 没有 Expressivity 字段
- **THEN** 系统迁移为 `0`，并保留既有 Speed；声音行为不发生隐式变化

## MODIFIED Requirements

### Requirement: Approved prototype conformance

Bot 编辑器的 TTS 配置 MUST 遵循已确认的 Voice Picker 与 Voice tuning 视觉和交互语言。Deepgram Flux 被选中时，必须在 Voice 选择区域后显示同风格的 Flux voice tuning 卡片，包含 Expressivity 离散滑杆和 Speed 滑杆；ElevenLabs 的现有布局和行为不得改变。

#### Scenario: Implement the approved Bot editor

- **WHEN** 开发完成 TTS 配置页面
- **THEN** 字段顺序、分组、控件形态、默认值、provider/model 联动、禁用状态、Voice Picker 弹层、卡片、试听、筛选、分页、手工 ID 和响应式布局与原型一致

#### Scenario: Prevent a simplified voice selector regression

- **WHEN** 实现或后续改动 Voice 选择器
- **THEN** 自动化 UI 检查与人工截图对照必须确认搜索、动态筛选、试听、选中卡片、分页与手工 Voice ID 入口均可用，不得退化为原生下拉框

#### Scenario: Switch between TTS providers

- **WHEN** 用户在 Deepgram Flux 与 ElevenLabs 之间切换
- **THEN** 页面仅展示当前 provider 对应的 tuning 控件，Voice Picker 与 ElevenLabs 已验收交互保持不变
