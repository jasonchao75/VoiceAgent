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
