# MODIFIED Requirements
## Requirement: 本地编号来源修订
尚未提交给LLM的完整ASR来源的本地编号贡献 MUST 随该来源最新版本替换，MUST NOT 因数字合并为单词而要求按旧本地消费边界拆词。已交LLM范围保持原严格归属保护。
### Scenario: 累计数字
- GIVEN 本地收集12但未提交LLM
- WHEN 同来源更新123并以一个词Final
- THEN 收集结果123，不追加成12123，不因该本地边界断线
### Scenario: 更正/清空
- WHEN 同来源修订124或清空后迟到
- THEN 更正替换该贡献；清空前来源不回灌
## Requirement: 正式RTC编号跟读
启用自建TD编号规则的正式RTC会话 MUST 接通已有RTP任务播放链路；满足条件后派发跟读，实际播放由客户端确认。
### Scenario: 正式入口
- WHEN 非开发开关的正式会话启用编号跟读
- THEN 返回匹配播放协议，安装RTP输入输出和IdentifierOutput；普通模式保持原路径

## Requirement: 连接失败释放
客户端在会话分配后、RTC连接前失败时 MUST 经当前会话凭证立即释放未激活名额，清除凭证并记录失败；MUST NOT 取消别人的会话；pending取消本身不得误取消active会话。当前浏览器明确报告终止失败时，系统须独立验证其凭证后关闭对应RTC会话（包括已认领但尚未完成连接的offer），防止孤立管线和名额占用。页面等待失败上报 MUST 有上限，清理音频资源 MUST 不因上报失败跳过。
### Scenario: 浏览器能力缺失
- WHEN 编号任务播放所需浏览器接口缺失
- THEN 显式说明不支持，释放本次未激活名额，不调用ASR/LLM/TTS；重复重试不积压并发名额

## Requirement: 新旧RTP接口兼容
浏览器支持旧createEncodedStreams且具备所需解码能力时，系统 MUST 接入与新版ScriptTransform相同的任务播放链路，并保留严格包身份、停止和播放回执契约。
### Scenario: Chrome旧接口
- WHEN ScriptTransform不存在而旧RTP编码流接口可用
- THEN 使用旧接口接入同一worker，不因缺少新版API拒绝连接，音频仍走RTP

### Scenario: 连接初期静音缺包
- WHEN 丢失RTP包的来源范围完整由服务端无任务静音覆盖
- THEN 不将其误判为回答/跟读失败，不生成该范围的播放回执；任务音频缺失仍不可伪报成功
### Scenario: 播放失败导致连接取消
- WHEN 明确播放失败后SDK又抛通用连接错误
- THEN 保留首个安全原因且仅清理/上报一次，不覆盖为通用错误

### Scenario: 控制通道晚于音频连接
- WHEN ICE/DTLS已连接但任务控制通道尚未就绪
- THEN 源音频等待控制通道就绪后按实时节奏开始，不能先发无可用归属的音频或补发连接等待期间的静音；沿用SDK10秒控制通道边界超时结束，不无限占用
### Scenario: offer认领后浏览器失败
- WHEN 已认证当前会话失败与offer注册并发
- THEN 关闭该会话、释放名额、保留失败历史；迟到注册不能启动孤立管线，不影响别的会话

### Scenario: 扫码者没有后台登录Cookie
- WHEN 已持有效当前通话Bearer的扫码用户上报播放、时钟或RTP输入证据
- THEN 按通话凭证及对应任务/时钟验证，不要求网站后台登录；缺失、错误及别的会话凭证仍拒绝，管理接口继续要求网站登录

### Scenario: 标记与音频齐备但等待解码
- WHEN 某包的音频及有效任务标记均已到达，因前序有序解码而尚未消费
- THEN 不得按缺失任务标记判为匹配超时；仍受单次解码及队列容量限制，证据真正缺失或不一致仍失败
