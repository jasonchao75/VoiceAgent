# English Flux Voice Agent：本地运行与验收

## 1. 当前实现

第一版使用浏览器 + FastAPI WebSocket + Pipecat 1.8.1，实时链路为：

```text
Browser PCM 16 kHz mono
  -> Deepgram Flux STT (flux-general-en)
  -> OpenAI-compatible streaming LLM
  -> Deepgram Flux TTS (/v2/speak, PCM 24 kHz mono)
  -> Browser playback
```

Deepgram 与 LLM 都采用 BYOK。API Key 只在 `POST /api/sessions` 请求体中提交，后端只在进程内存中持有；WebSocket 使用短时、单次 opaque token。会话结束、异常或 token 过期后释放凭证引用。服务器没有共享厂商 Key。本地仅允许 `localhost` / `127.0.0.1` loopback HTTP，非本地地址必须使用 HTTPS。

## 2. 最简启动方式（推荐）

前提：安装并启动 Docker Desktop。

```bash
docker compose up --build
```

浏览器打开：<http://localhost:8000>

停止服务：

```bash
docker compose down
```

健康检查：<http://localhost:8000/health>。该接口不会调用任何付费 API。

### 公网验收环境

- URL：<https://platform.voiceagentdemo.org>
- 入口使用 HTTP Basic Auth；用户名为 `voiceagent`，密码为固定值（至少 8 个字符）。
- 密码明文不写入公开仓库；遗忘时可在已授权 Mac 上执行下列命令查看服务器保存的密码：

```bash
ssh -i ~/.ssh/id_ed25519 root@104.248.46.112 "sed -n 's/^VOICE_AGENT_BASIC_AUTH_PASSWORD=//p' /home/deploy/apps/voiceagent-platform/repo/.env"
```

- 修改密码：更新上述 `.env` 中的 `VOICE_AGENT_BASIC_AUTH_PASSWORD` 后，在 `/home/deploy/apps/voiceagent-platform/repo` 执行 `docker compose up -d` 重启生效。

服务器只保存访问保护参数，不保存 Deepgram 或 LLM API Key；两类厂商 Key 仍由用户在每次会话开始时通过 HTTPS 页面提交。

## 3. 开发模式

仅供需要调试代码时使用：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cd frontend && npm ci && npm run build && cd ..
uvicorn src.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

不需要把 Deepgram 或 LLM Key 写入 `.env`。`.env.example` 仅包含非厂商运行参数。

## 4. 页面配置指引

- Deepgram Key：从 <https://console.deepgram.com/> 获取，需具备 Flux STT/TTS 使用权限和可用额度。
- Flux Voice：页面只能选择后端 Catalog 中已核对的 voice；旁边提供官方 Voice Catalog 和试听入口。
- OpenAI Key：从 <https://platform.openai.com/api-keys> 获取。
- LLM model：默认 `gpt-4.1-mini`，页面提供推荐项和官方模型文档；实际可用模型受账号权限影响。
- Custom OpenAI-compatible：填写厂商提供的 HTTPS base URL 与准确 model ID；只支持兼容 OpenAI Chat Completions Streaming 的接口。
- Opening Script：非空时 Agent 先说，并作为 assistant message 加入上下文；留空时等待用户先说。

页面不会使用 Local Storage、Session Storage 或 Cookie 保存 Key。创建会话成功后，两个 Key 输入框会立即清空。

## 5. 人工验收清单

1. 填写两类 Key，保持默认模型与 voice，点击 **Start session** 并授权麦克风。
2. 确认 Opening Script 先播放，完成至少三轮英文对话。
3. 新建会话并清空 Opening Script，确认 Agent 等待用户先说。
4. 更换 System Prompt 和 Flux voice，分别新建会话确认生效。
5. Agent 播放长回复时开口，确认浏览器立即停止旧音频，新一轮仍能继续。
6. 输入无效 Key 或无权限 model，确认页面显示可恢复错误，结束后可重新开始。
7. 点击 **End session**，确认 WebSocket 断开；旧 token 不可再次连接。

页面展示两个体验指标：用户停止说话到浏览器开始播放，以及 LLM 首个文本增量到浏览器开始播放。服务端另记录 ASR final、LLM first token、TTS first audio 和 interruption 时间，日志不记录 transcript 或 Key。

## 6. 已知限制

- 本地自动化测试使用 mock，不调用真实厂商；真实 Flux 音质、模型权限、三轮对话和打断延迟必须由用户使用自己的 Key 人工验收。
- Pipecat 1.8.1 会向 Flux TTS 发送 `Interrupt`，但当前适配器没有把浏览器精确 playback offset 传给 Deepgram，因此尚未实现 `text_spoken` 与 LLM assistant 上下文的逐字对账。
- 浏览器首播时间来自 Pipecat Client 的播放回调，适合体验对比，但不是声卡级测量。
- 本机已验证 Python 测试、lint、typecheck、前端生产构建和完整 Docker 镜像构建。macOS 自带 Node/npm 组合出现 npm CLI 退出异常时，以 Node 22 Docker 构建结果为交付依据。
- DigitalOcean 使用现有 Droplet 和独立域名 `platform.voiceagentdemo.org`；首次部署、DNS/HTTPS 和 GitHub Secrets 配置完成后，`main` 的 CI 全绿会自动发布。
- 公网环境已完成容器健康、HTTPS、WSS、HTTP 跳转和 Basic Auth 验证；真实三轮对话与 barge-in 仍需用户使用自己的 BYOK Key 和浏览器麦克风人工验收。

## 7. 常见问题

- 麦克风不可用：本地必须使用 `localhost` / `127.0.0.1`；公网必须是 HTTPS/WSS。
- LLM 报错：检查 Key、余额、model 权限，以及 Custom endpoint 是否真正兼容流式 Chat Completions。
- Flux 报错：检查 Deepgram Key 是否有权限、额度是否可用、voice 是否来自页面 Catalog。
- 页面连接失败：先访问 `/health`，再确认 8000 端口未被占用。
