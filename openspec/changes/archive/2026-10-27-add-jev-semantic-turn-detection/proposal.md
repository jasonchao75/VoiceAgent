# Jev semantic Turn Detection — Draft

## Why
现有 Pipeline 主要消费厂商端点。用户提出本地敏感 Silero VAD 加云端 Jev，在保留机器人上下文的同时避免在当前 1 核、1GB 服务器加载本地语义或声学 TD 模型。

## Scope
候选停顿触发 Jev；输入上一轮机器人文本与本轮最新转写；输出结束概率及有限标签；应用策略确定等待。续说撤销候选，使用最短和最长静音边界。复用现有聚合器，只保留一处最终提交权。

## Status
用户已确认本轮9项产品选择，见 D-026 至 D-034；播放与混合表达分工已确认；普通回复迟到改义按D-043停止旧回答并重答，当前产品开放问题0项；自测范围见[verification/self-test-plan.md](verification/self-test-plan.md)。设计与行为规格已同步，示例参数仍需工程校准，原型v0.14已同步并待用户评审。正式实现、真实厂商兼容性验证和用户验收均未完成；没有新增外部付费调用授权。

## ASR 事件契约补充
[appendices/asr-event-mapping.md](appendices/asr-event-mapping.md) 记录 Partial / Complete(Final)、厂商边界与自建 TD 提交信号的映射及当前接入缺口；2026-10-20 静态核对，未进行厂商付费测试。
