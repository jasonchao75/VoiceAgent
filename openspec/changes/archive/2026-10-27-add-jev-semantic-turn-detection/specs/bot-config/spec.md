## ADDED Requirements

### Requirement: Self-developed TD source for every catalog ASR model
Every supported ASR provider/model SHALL offer self_developed alongside its existing permitted sources. Provider-native/off constraints remain unchanged. This change extends the earlier capability scope that excluded Self-developed.

#### Scenario: Select self-developed for any supported ASR
- WHEN the user selects any catalog ASR provider/model
- THEN Self-developed SHALL be selectable in Turn detection source; the user SHALL be able to enter Advanced → Turn Detection only while it is selected.

### Requirement: Conditional custom TD configuration
Advanced SHALL preserve the existing General fallback configuration and show custom TD and Jev settings only for self_developed. Switching away SHALL hide these settings without silently deleting the entered configuration.

#### Scenario: Switch source away and back
- GIVEN entered TD settings with self_developed
- WHEN the user switches to an allowed provider_native or off source
- THEN custom TD settings and entry are hidden, General remains accessible, and switching back restores access to the entered draft.

### Requirement: Existing Sessions and Share visual structure
Sessions SHALL retain the current product filter/list and detail drawer layout, placing TD diagnostics inside the existing details pattern. Share SHALL retain the current profile/QR/Web Link card structure. Prototype actions SHALL NOT publish, create links or start calls.

#### Scenario: Inspect sample TD record
- WHEN the user opens the prototype Sessions page and selects the clearly labelled sample session
- THEN the right-side details drawer shows conversation and TD evidence without replacing the entire Sessions list page.

### Requirement: Per-turn TD history evidence
The session details SHALL retain ordinary conversation and existing latency information, associate a TD record with each user turn, and show all candidate pause decisions within that turn. Legacy sessions without self-developed evidence SHALL display its absence rather than invent probabilities.

#### Scenario: Resumed speech creates multiple attempts in one turn
- WHEN the first pause candidate is cancelled by resumed speech and a later candidate commits
- THEN the same user turn displays both attempts with distinct outcomes and exactly one ordinary reply.

#### Scenario: Preview normal and legacy conversations
- WHEN the user opens a sample session in the prototype
- THEN multiple turns, normal replies and clearly labelled fixture metrics are shown, each with its own TD section; a provider-native legacy sample explicitly shows that self-developed evidence was not captured.

### Requirement: Pre-generated echo audio and publish validation
The content vocabulary section SHALL offer generation and listening using the current Bot TTS configuration, deduplicate output audio units, and configure inter-unit silence with a suggested default of 50ms. Generated assets SHALL be persistently retained without automatic session/page/restart expiry. Every Publish SHALL validate required assets against the current vocabulary and effective TTS configuration, blocking on missing, failed or mismatched assets rather than automatically synthesizing.

#### Scenario: Change playback gap
- WHEN only the inter-unit gap changes
- THEN the assets remain reusable and no resynthesis is required.

#### Scenario: Publish with missing audio
- WHEN a Bot with active self-developed echo rules lacks any required matching asset
- THEN Publish is blocked with guidance to generate audio first; the publish action makes no TTS generation request.

#### Scenario: Prototype without real audio
- WHEN the user opens the prototype generation entry
- THEN a clearly marked plan is shown, listening remains disabled without actual audio, and no paid call or actual publish is performed.

### Requirement: Compact vocabulary audio controls
Recognized aliases SHALL be configurable as a comma-separated list per vocabulary row mapping to one echo text. Each row SHALL show audio status and listening control; the vocabulary heading SHALL provide bulk generation. Playback gap SHALL be separately configured below the vocabulary without a duplicate audio list. Alias duplicates within or across rows SHALL be rejected.

#### Scenario: Multiple aliases share audio
- WHEN a row contains one, 一, 1 mapped to 1
- THEN the aliases share the same target audio and row listening control; the bulk action does not synthesize once per alias.

### Requirement: Configurable overlength reminder
The identifier collection settings SHALL provide separate editable reminders for incomplete timeout and overlength. Overlength SHALL trigger a normal assistant reminder after a short pause, rather than waiting for the incomplete timeout or silently truncating the identifier.

#### Scenario: Configure distinct reminders
- WHEN the user edits the overlength reminder
- THEN the incomplete-timeout reminder remains independent; both are disabled when completeness configuration is disabled.

### Requirement: Runtime echo cache recovery and fixed echo speed
数字跟读 MUST 使用发布时匹配的 TTS 音色及语速，普通回复的动态语速调整 MUST NOT 改变跟读速度。发布后的缓存读取失败 MUST 临时调用 TTS 补合成并跟读，在对应会话及轮次中记录缓存失败、临时合成结果和耗时。此恢复策略 MUST NOT 放宽 Publish 的缓存完整性检查。

#### Scenario: Cache unavailable after publication
- **WHEN** 已发布机器人运行时无法读取所需跟读音频
- **THEN** 使用发布时跟读配置临时合成，按串行队列播放，并在对话记录中显示降级和耗时；不伪造缓存命中

#### Scenario: Temporary echo synthesis also fails
- **WHEN** 缓存读取失败后的临时补合成失败（D-074）
- **THEN** 跳过本次跟读，保留已采集编号并继续通话；记录失败及对应来源/轮次/任务；尚无实际回执时不伪报播放，已有部分音频时停止剩余并保留真实已播/停止事实，不声称完整跟读成功，不阻塞后续有效输入和工具

### Requirement: Jev budget requires no product control
Jev单会话请求预算 MUST 由后台统一为100，正式配置页 MUST NOT 为此新增输入控件。新Bot无需传隐藏预算字段；旧草稿的max_calls正数载入后规范为100，不能改变实际统一上限。

#### Scenario: Create configuration without a hidden budget
- **WHEN** 用户保存完整Jev/TD配置且没有提供max_calls
- **THEN** 后台保存统一100次预算，页面不新增控件
