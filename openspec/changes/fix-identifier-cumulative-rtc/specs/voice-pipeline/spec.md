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

### Scenario: 静音缺包在解码队列中等待
- WHEN 已有服务端完整静音范围证据的缺包超时，但前序解码尚未完成
- THEN 按来源顺序退休该静音范围，不误报任务音频缺失，不伪造PCM或播放回执
### Scenario: 关闭后迟到控制消息
- WHEN 播放器关闭后收到迟到控制事件
- THEN 不重启时钟请求或继续使用旧麦克风/播放器资源
### Scenario: 首次播放失败诊断
- WHEN 首次播放失败
- THEN 按当前通话保存有界计数、构建标识及队首等待类型，不保存任意文本或凭证，不被清理错误覆盖

### Scenario: 接收不等待前序解码
- WHEN 已接收音频正在按来源顺序解码
- THEN 后续RTP接收不得等待前序解码完成；有界队列、身份校验、缺包截止和播放回执保持原契约

### Scenario: 播放器脚本不可用
- WHEN 浏览器播放器脚本404、模块加载失败或初始化期间报错
- THEN 在继续连接和静音原音轨前确认加载失败，明确提示刷新，释放本次资源和名额；加载成功不冒充实际播放
### Scenario: 私有TD提交不重复显示为ASR字幕
- WHEN 同一输入已经产生厂商Final，又被TD内部提交给LLM
- THEN 客户端ASR字幕不因内部TDSubmission再追加一次；真实不同输入即使文本相同仍各显示，迟到ASR Final照常显示，LLM提交不受影响

## Requirement: Approved native playback replacement
正式RTC编号会话MUST使用浏览器原生RTP/Opus音轨，替代上文任务映射及解码接口要求。保留服务端串行队列和取消，MUST NOT等待客户端任务回执。最多20ms音频在原生track等待消费；服务端发送完成MUST NOT标记客户端播完。清空、打断及有效Final重答取消对应未发声音，允许短暂浏览器缓冲尾音。
### Scenario: Native without decoder APIs
- WHEN 正式编号RTC连接的浏览器没有WebCodecs或encoded transform
- THEN 原生播放可用，不加载逐包播放器；真实连接失败仍释放资源并报告
### Scenario: Append after partial send
- GIVEN 同来源123仅1已开始发送，23待发
- WHEN 更新为123456
- THEN 保留23并追加456，不重发1、不漏23；格式变化不新增音频，真实更正合并最新完整片段
## Requirement: Final content comparison
本条替代主规格中相同Final也重答的规则。已提交Partial的首个有效Final，去Unicode标点和空白后文字相同MUST继续原回答并更新有效转写及后续上下文；其他字符变化MUST取消对应旧回答并重答，不再调用语义模型。
### Scenario: Same or formatting Final
- WHEN 我要办理的Final为我要办理或我 要办理。
- THEN 不新增LLM/TTS请求，不取消原回答，不重复字幕或工具副作用
### Scenario: Changed Final
- WHEN Final为我不要办理
- THEN 同轮取消旧生成及未发声音，以新文字重答；重复或旧轮Final不再次触发
