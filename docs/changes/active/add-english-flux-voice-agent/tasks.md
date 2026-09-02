# Tasks: English Flux Voice Agent MVP

## 1. Requirement and Version Validation

- [x] 阅读并遵守 `AGENTS.md` 和 `.opencode/skills/pipecat-integration/SKILL.md`
- [x] 核对 Deepgram Flux ASR `/v2/listen`、Flux TTS `/v2/speak` 当前官方协议、鉴权、事件、超时和音频格式
- [x] 验证并锁定支持 `DeepgramFluxSTTService`、`DeepgramFluxTTSService` 的 Pipecat 版本
- [x] 核对该版本的 barge-in、`Interrupt`、playback offset、`text_spoken` 和跨轮状态实际支持范围
- [x] 确认首个 OpenAI-compatible LLM 的 base URL、model、BYOK 传递方式和调用超时

## 2. Project Bootstrap

- [x] 建立 Python 3.11+ 项目依赖、锁文件、格式化、lint 和测试配置
- [x] 增加只包含非厂商运行参数的 `.env.example`，确认 `.env` 已被忽略且不存在共享 Deepgram/LLM Key
- [x] 建立 `configs/runtime/` Agent 配置及校验模型
- [x] 建立可独立更新的 Flux Voice Catalog 与 LLM Provider Catalog，记录来源和核对日期
- [x] 提供 Dockerfile、Docker Compose 和一条主启动命令
- [x] 增加不访问付费 API 的 `/health`
- [x] 实现会话级 BYOK 凭证容器、opaque token、TTL、单会话绑定和确定性清理
- [x] 为日志、异常和遥测增加 API Key 脱敏与禁止记录检查

## 3. Provider Layer

- [x] 实现 Flux ASR service 构造与运行配置映射
- [x] 使用会话级 BYOK 实现 Deepgram Flux ASR/TTS service 构造
- [x] 使用会话级 BYOK 实现 OpenAI-compatible streaming LLM 构造与显式 timeout
- [x] 实现 TTS Provider Registry/Factory
- [x] 只注册 Deepgram Flux TTS，并保留 ElevenLabs 的稳定扩展边界
- [x] 校验 encoding、sample rate、sample width 和 channel；在明确边界处理重采样

## 4. Pipecat Pipeline

- [x] 实现 Browser → Flux ASR → LLM → Flux TTS → Browser 的全异步 Pipeline
- [x] 实现 System Prompt 注入和会话上下文
- [x] 实现 assistant-first Opening Script，并写入 assistant 上下文
- [x] 实现 user-first 空 Opening Script 行为
- [x] 实现 interruption、LLM 取消、TTS 中断和旧音频清理
- [x] 实现会话关闭、超时、厂商异常和资源清理
- [x] 增加 session ID 和基础延迟探针

## 5. Frontend

- [x] 实现参考 Vapi 信息架构的单页测试界面
- [x] 实现 Deepgram/LLM Key 遮罩输入、LLM provider/base URL/model、System Prompt、Opening Script 和 Flux voice 配置区
- [x] 实现带口音、性别、年龄、声音特征和用途说明的 Flux Voice 下拉框
- [x] 实现 LLM Provider 预设、推荐 model 组合框和 Custom OpenAI-compatible 高级输入
- [x] 在 Deepgram/LLM 字段旁提供受控的官方 Key、Voice 和模型文档链接及 BYOK 说明
- [x] 使用初始 HTTPS POST 提交 Key，成功后清空前端凭证引用，后续 WebSocket 只使用 opaque session token
- [x] 实现 Start/End Session、麦克风授权和会话配置锁定
- [x] 实现实时用户/Agent transcript 与当前发言状态
- [x] 实现流式音频播放、浏览器本地立即停止和 playback 时间回传
- [x] 展示连接状态、组件状态、基础延迟和可恢复错误
- [x] 验证 Key 不进入 URL、浏览器存储、响应或后续 WebSocket 消息

## 6. Automated Verification

- [x] 增加配置校验和 TTS Provider Factory 单元测试
- [x] 增加 Voice/LLM Catalog schema、合法 HTTPS 帮助链接、推荐项和自定义 model 校验测试
- [x] 使用 mock ASR/LLM/TTS 增加不调用付费 API 的 Pipeline smoke test
- [x] 增加 Opening Script、空 Opening Script 和上下文行为测试
- [x] 增加 interruption、异常关闭和重新连接测试
- [x] 增加 BYOK 创建失败、TTL、会话结束清理、token 失效和日志脱敏测试
- [x] 增加音频格式与采样率断言测试
- [x] 运行 format、lint、typecheck、unit test 和 build
- [x] 扫描仓库、构建产物和日志，确认没有密钥或临时录音

## 7. Local Acceptance

- [ ] 由用户通过 BYOK 页面提交真实 Deepgram 与 LLM Key，执行受控连通性测试
- [ ] 通过 localhost 页面完成人工麦克风、Opening Script、三轮对话和 barge-in 验收
- [ ] 记录 TTFA、端到端响应延迟和打断停止延迟
- [x] 汇报未验证范围、已知限制、测试日志和临时产物路径
- [x] 更新 README 与本地运行/验收说明

## 8. DigitalOcean Demo

- [x] 用户确认复用现有 Droplet、使用 `platform.voiceagentdemo.org` 并授权部署；DNS A 记录已生效
- [x] 配置非 root deploy 身份、服务目录和非厂商运行环境变量；服务器不得保存共享 Deepgram/LLM Key
- [x] 配置 Nginx、API、WebSocket、HTTPS/WSS 和 Basic Auth
- [x] 配置会话时长、并发与访问限制
- [x] 部署前再次运行本地检查并确认无敏感/临时文件
- [x] 部署后验证容器健康、`/health`、HTTPS、WSS、HTTP 跳转和访问保护
- [ ] 用户通过公网页面完成麦克风、三轮对话和 barge-in 人工验收
- [x] 将公网 URL 与安全获取访问凭证的方式交给用户

## 9. Automatic CI/CD

- [x] CI 覆盖仓库安全检查、format、lint、typecheck、unit test、前端 build 和生产 Docker image build
- [x] 增加只接受 `main` push 且 CI 成功事件的自动部署 workflow，并保留手动重跑入口
- [x] 增加固定主机指纹、commit 归属校验、部署串行化、容器健康检查和上一镜像回滚
- [x] 将 CD 权限收敛为 root 管理的固定部署命令，禁止 `deploy` 用户直接访问 Docker daemon
- [x] 增加 `PLATFORM_DEPLOY_ENABLED` 部署总开关，避免环境初始化前误触发
- [x] 配置 GitHub 部署 Secrets 与总开关，并验证 Secret 不出现在日志
- [x] 完成手动 CD 演练；通过本次状态提交验证 `main` CI 成功后的自动触发

## 10. Closeout

- [ ] 对照 `spec.md` 完成最终检查并记录偏差
- [ ] 用户验收通过后，将 Change 整体归档到 `docs/changes/archive/`
- [ ] 评估是否把 Flux TTS、Pipecat interruption 和公网 Demo 防滥用经验提炼到 `.opencode/skills/`
