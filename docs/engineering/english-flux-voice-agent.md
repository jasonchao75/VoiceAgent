# English Flux Voice Agent：本地运行与验收

## 1. 当前实现

第一版使用浏览器 + FastAPI WebSocket + Pipecat 1.8.1，实时链路为：

```text
Browser PCM 16 kHz mono
  -> Deepgram Flux STT (flux-general-en)
  -> OpenAI-compatible or native Google Gemini streaming LLM
  -> Deepgram Flux TTS (/v2/speak, PCM 24 kHz mono)
  -> Browser playback
```

页面以"机器人（Bot）"为中心：机器人保存 ASR/TTS/LLM 选择与 Prompt，选中即可发起会话；API Key 两种模式由用户在机器人上二选一：

- **加密保存（可选）**：勾选后 Deepgram/LLM Key 经 Fernet 加密写入 SQLite（named volume 持久化），发起会话免填 Key；主密钥只存在于服务器环境变量 `VOICE_AGENT_STORAGE_KEY`，任何 API 响应都不返回 Key。
- **BYOK（默认）**：不保存 Key，发起会话时当次填写。Key 只在 `POST /api/sessions` 请求体中提交，后端只在进程内存中持有；WebSocket 使用短时、单次 opaque token。会话结束、异常或 token 过期后释放凭证引用。

不建机器人也可用页面底部 Quick start 发起一次性全字段会话。服务器没有共享厂商 Key；未配置 `VOICE_AGENT_STORAGE_KEY` 时保存 Key 功能关闭，其余能力不受影响。本地仅允许 `localhost` / `127.0.0.1` loopback HTTP，非本地地址必须使用 HTTPS。

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
- 入口使用 VoiceAgent 自有登录页；登录成功后由安全 Cookie 维持网站会话，不触发浏览器原生 Basic Auth 弹窗。共享用户名与密码仍从历史命名的 `VOICE_AGENT_BASIC_AUTH_USERNAME` / `VOICE_AGENT_BASIC_AUTH_PASSWORD` 环境变量读取。
- 密码明文不写入公开仓库；遗忘时可在已授权 Mac 上执行下列命令查看服务器保存的密码：

```bash
ssh -i ~/.ssh/id_ed25519 root@104.248.46.112 "sed -n 's/^VOICE_AGENT_BASIC_AUTH_PASSWORD=//p' /home/deploy/apps/voiceagent-platform/repo/.env"
```

- 修改密码：更新上述 `.env` 中的 `VOICE_AGENT_BASIC_AUTH_PASSWORD` 后，在 `/home/deploy/apps/voiceagent-platform/repo` 执行 `docker compose up -d` 重启生效；旧网站会话会按既有过期策略退出。

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
- Google Gemini：固定资源方使用原生 Gemini adapter；2.5 Flash/Flash-Lite 请求 `thinking_budget=0`，3.x Flash/Flash-Lite 请求最低 `thinking_level`。
- LLM model：默认 `gpt-4.1-mini`，页面提供推荐项和官方模型文档；实际可用模型受账号权限影响。
- Custom OpenAI-compatible：填写厂商提供的 HTTPS base URL 与准确 model ID；只支持兼容 OpenAI Chat Completions Streaming 的接口。
- Opening Script：非空时 Agent 先说，并作为 assistant message 加入上下文；留空时等待用户先说。

页面不会使用 Local Storage、Session Storage 或 Cookie 保存 Key。创建会话成功后，Key 输入框会立即清空。机器人勾选"加密保存"的 Key 只以密文落 SQLite，明文不会返回前端。

### 通话历史与容量

用户上行音频以无损 FLAC 默认保留 7 天，最终文本、逐轮延迟和安全诊断默认保留 30 天；不保存 TTS 音频和隐藏思考正文。数据位于 `VOICE_AGENT_DATA_DIR`，录音有效上限是 5GB 与数据卷总容量 20% 的较小值，并至少预留 1GB。可通过 `.env.example` 中四个 `VOICE_AGENT_*RETENTION*` / 容量变量调整，清理任务按最旧录音优先执行且不影响实时通话。

## 5. 人工验收清单

1. 新建一个机器人并勾选"Save API keys encrypted on the server"，保存后直接点击 **Start session**，确认免填 Key 即可授权麦克风开打。
2. 确认 Opening Script 先播放，完成至少三轮英文对话。
3. 新建会话并清空 Opening Script，确认 Agent 等待用户先说。
4. 编辑机器人更换 System Prompt 和 voice（Key 留空表示保留），分别新建会话确认生效。
5. 再建一个不保存 Key 的机器人，确认 Start 时要求当次填写两类 Key，对话正常。
6. 用 Quick start 不建机器人直接发起一次性会话，确认原有行为不回归。
7. Agent 播放长回复时开口，确认浏览器立即停止旧音频，新一轮仍能继续。
8. 输入无效 Key 或无权限 model，确认页面显示可恢复错误，结束后可重新开始。
9. 点击 **End session**，确认 WebSocket 断开；旧 token 不可再次连接。
10. 重启容器，确认机器人配置与加密 Key 仍然可用（volume 持久化）。

页面展示两个体验指标：用户停止说话到浏览器开始播放，以及 LLM 首个文本增量到浏览器开始播放。服务端另记录 ASR final、LLM first token、TTS first audio 和 interruption 时间，日志不记录 transcript 或 Key。

## 6. 已知限制

- 本地自动化测试使用 mock，不调用真实厂商；真实 Flux 音质、模型权限、三轮对话和打断延迟必须由用户使用自己的 Key 人工验收。
- Pipecat 1.8.1 会向 Flux TTS 发送 `Interrupt`，但当前适配器没有把浏览器精确 playback offset 传给 Deepgram，因此尚未实现 `text_spoken` 与 LLM assistant 上下文的逐字对账。
- 浏览器首播时间来自 Pipecat Client 的播放回调，适合体验对比，但不是声卡级测量。
- 本机已验证 Python 测试、lint、typecheck、前端生产构建和完整 Docker 镜像构建。macOS 自带 Node/npm 组合出现 npm CLI 退出异常时，以 Node 22 Docker 构建结果为交付依据。
- DigitalOcean 使用现有 Droplet 和独立域名 `platform.voiceagentdemo.org`；首次部署、DNS/HTTPS 和 GitHub Secrets 配置完成后，`main` 的 CI 全绿会自动发布。
- 公网环境已完成容器健康、HTTPS、WSS、HTTP 跳转、产品登录页和 Cookie 会话验证；真实三轮对话与 barge-in 仍需用户使用自己的 BYOK Key 和浏览器麦克风人工验收。

## 7. 常见问题

- 麦克风不可用：本地必须使用 `localhost` / `127.0.0.1`；公网必须是 HTTPS/WSS。
- LLM 报错：检查 Key、余额、model 权限，以及 Custom endpoint 是否真正兼容流式 Chat Completions。
- Flux 报错：检查 Deepgram Key 是否有权限、额度是否可用、voice 是否来自页面 Catalog。
- 页面连接失败：先访问 `/health`，再确认 8000 端口未被占用。

## Mobile WebRTC 部署前检查

移动 Demo 与现有 WebSocket 共用 FastAPI、Bot、Pipeline 和 3 路并发限制，但媒体改走
WebRTC/UDP。生产环境需要同时满足：

- `VOICE_AGENT_ALLOWED_ORIGINS` 包含公开 HTTPS 域名；
- `VOICE_AGENT_STUN_URLS` 配置一个可从中国大陆测试网络访问的 `stun:`/`stuns:` 地址；
- Linux 宿主机让 aiortc 能发布可达的主机候选。当前 Docker 仅映射 TCP 8000 时，优先在
  测试部署使用 `compose.webrtc.yaml` 的 host networking；生产部署脚本已固定叠加该文件，
  HTTP 服务继续监听宿主机 `127.0.0.1:8020` 供 Nginx 反向代理；
- DigitalOcean Cloud Firewall 与主机防火墙放行本次测试所需的 UDP 入站。aiortc 默认使用
  系统临时端口；未收窄端口范围前，不应把“只开放 TCP 8000”视为 WebRTC 已部署；
- 首版不支持 TURN。若 Wi-Fi/移动网矩阵达不到目标成功率，应暂停扩大测试并重新决策
  TURN/媒体网关，不得把失败网络静默降级成 WebSocket。

部署后先发布一个专用测试 Bot，再用 iOS Safari 与 Android Chrome 各执行 Wi-Fi、移动网
短通话。验收至少记录连接是否成功、连接耗时、最终 ICE candidate 类型和失败分类；日志
不得保存 SDP、candidate 地址、Provider Key 或音频内容。

### DigitalOcean 一次性配置

1. 在服务器仓库 `.env` 增加 `VOICE_AGENT_STUN_URLS=stun:stun.cloudflare.com:3478`。首版只接受
   `stun:`/`stuns:`，缺失或配置 TURN 时生产进程会拒绝启动。STUN 服务必须先从中国大陆
   Wi-Fi 和移动网验证可达，仓库不内置第三方公共 STUN。
2. 在 Droplet 上读取实际动态 UDP 范围：

   ```bash
   cat /proc/sys/net/ipv4/ip_local_port_range
   ```

   DigitalOcean Cloud Firewall 与 UFW 必须同时放行输出范围的 UDP 入站。不要照抄示例范围；
   以目标 Droplet 的输出为准。TCP 8020 不对公网开放，只由本机 Nginx 访问。
3. 静默验证 Compose，避免输出环境变量或密钥：

   ```bash
   docker compose -f compose.yaml -f compose.webrtc.yaml config --quiet
   ```

4. 部署脚本会在健康检查后运行 `verify_webrtc_production.py`，确认容器确实收到 STUN、
   host-network 声明并能读取 Linux UDP 范围。该检查不能替代 Cloud Firewall 与真机验证。

任何时候都不要运行会打印完整 Compose 配置的 `docker compose config`；它会展开 `.env`
中的敏感变量。只使用 `config --quiet`。
