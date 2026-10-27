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
客户端在会话分配后、RTC连接前失败时 MUST 经当前会话凭证立即释放未激活名额，清除凭证并记录失败；MUST NOT 取消别人的或已激活的会话。页面等待失败上报 MUST 有上限，清理音频资源 MUST 不因上报失败跳过。
### Scenario: 浏览器能力缺失
- WHEN 编号任务播放所需浏览器接口缺失
- THEN 显式说明不支持，释放本次未激活名额，不调用ASR/LLM/TTS；重复重试不积压并发名额
