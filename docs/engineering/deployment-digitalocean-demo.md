# DigitalOcean Demo 部署手册

## 适用范围
本手册适用于轻量级 Demo 项目的服务器部署，特别是基于 FastAPI 后端 + 纯前端静态页面，并配合 GitHub Actions 实现手动 CD 的场景。本方案旨在快速提供一个可在线访问、稳定且带 HTTPS 的演示环境，而非完整的复杂生产级高可用发布。

## 架构概览
整个部署流程的架构链路如下：
`GitHub Repo -> GitHub Actions (CI/CD) -> SSH Deploy -> DigitalOcean Droplet -> Systemd (Backend Service) -> Nginx (Reverse Proxy & Static Files) -> HTTPS Domain`

## 一次性服务器初始化
对于一台全新的 DigitalOcean Droplet (建议使用 Ubuntu 24.04 LTS)，只需执行一次以下初始化操作：

1. **创建 Droplet**：选择基础配置，配置初始 Root 访问密码或 SSH Key。
2. **系统更新与基础工具**：
   ```bash
   apt update && apt upgrade -y
   apt install nginx python3-venv certbot python3-certbot-nginx -y
   ```
3. **UFW 防火墙配置**：
   ```bash
   ufw allow OpenSSH
   ufw allow 'Nginx Full'
   ufw enable
   ```
4. **创建 deploy 用户**：
   为了安全，不应使用 root 账户运行服务和进行 CD 部署。
   ```bash
   adduser deploy
   usermod -aG sudo deploy
   ```
5. **配置 SSH Key (针对 deploy 用户)**：
   为 `deploy` 用户生成/配置公私钥，以便后续 GitHub Actions 能免密登录。
   ```bash
   su - deploy
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   # 将 GitHub Actions 或管理者的公钥写入 authorized_keys
   nano ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```
6. **创建项目主目录**：
   统一规范存放各 Demo 仓库的目录，如 `/var/www/` 或 `/home/deploy/apps/`，并赋予 `deploy` 用户相应权限。

## 手动部署项目
在服务器初始化完毕后，首次接入一个新 Demo 仓库时需要手动跑通：

1. **Clone 仓库**：以 `deploy` 用户身份 clone 项目到指定目录。
2. **创建 venv 并安装依赖**：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```
3. **配置 `.env` 文件**：
   将所需的厂商 API Key 写入 `.env` 文件（**绝对不要提交到 Git**）。
4. **本地 Health Check**：
   手动运行一次 `python -m uvicorn backend.main:app`，确保服务正常启动。

## systemd 服务
为后端编写 systemd 配置文件（例如 `/etc/systemd/system/<service-name>.service`，如 `realtimeasr.service`），使其能后台常驻并自动重启：

```ini
[Unit]
Description=VoiceAgent Demo Backend (<service-name>)
After=network.target

[Service]
User=deploy
WorkingDirectory=/home/deploy/apps/<service-name>
EnvironmentFile=/home/deploy/apps/<service-name>/.env
ExecStart=/home/deploy/apps/<service-name>/venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port <PORT>
Restart=always

[Install]
WantedBy=multi-user.target
```
*提示：启用并启动服务 `sudo systemctl enable <service-name> && sudo systemctl start <service-name>`*

## Nginx 配置
配置 Nginx 代理请求到前端静态文件和后端 API/WebSocket。创建 `/etc/nginx/sites-available/<DEMO_DOMAIN>` (例如 `demo.example.com`)：

```nginx
server {
    listen 80;
    server_name <DEMO_DOMAIN>; # 例如 demo.example.com

    root /home/deploy/apps/<service-name>/frontend;
    index index.html;

    # 静态文件代理
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:<PORT>/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket 代理
    location /ws/ {
        proxy_pass http://127.0.0.1:<PORT>/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```
*提示：做好软链接并重启 Nginx `sudo ln -s /etc/nginx/sites-available/<DEMO_DOMAIN> /etc/nginx/sites-enabled/ && sudo systemctl restart nginx`*

## 域名与 HTTPS
录音和 WebSocket 通常要求在安全上下文（HTTPS）下运行。
1. **Namecheap DNS A 记录**：在域名提供商后台，添加一个 A 记录（如 `demo`）指向你的 `<SERVER_HOST>` (Droplet IP)。
2. **Certbot 配置 HTTPS**：
   ```bash
   sudo certbot --nginx -d <DEMO_DOMAIN>
   ```
3. **自动续期**：Certbot 安装时通常已配置好了 systemd timer 用于自动续期，可通过 `sudo systemctl status certbot.timer` 检查。

## GitHub Actions
我们使用 GitHub Actions 来完成自动质量检查与手动部署：
- **基础 CI**：每次 push 自动检查 Python 语法和 JSON 格式，阻断语法错误。
- **手动 Smoke Test**：在部署前验证代码打包和内部逻辑的自动化测试（按需）。
- **手动 Deploy CD**：使用 `workflow_dispatch` 触发。我们**不默认 push 自动触发部署**，以防高频提交导致服务器不断重启、影响正在体验 Demo 的用户，以及防止不稳定的构建破坏在线演示。

## GitHub Secrets
在 Demo 仓库的 Settings -> Secrets and variables -> Actions 中配置以下凭证：
- `SPEECHMATICS_API_KEY`: 存储真实的 API Key，不要直接放进代码里。
- `SERVER_HOST`: 服务器的公网 IP。
- `SERVER_USER`: 部署专用用户名，如 `deploy`。
- `SSH_PRIVATE_KEY`: 对应于 `deploy` 用户 `authorized_keys` 中公钥的私钥，用于 GitHub Actions 远程 SSH 连接。

## 服务器 sudoers 权限
在自动部署脚本中，通常需要重启 systemd 服务。为了安全，`deploy` 用户不应拥有任意 `sudo` 权限，而是通过 `visudo` 配置免密重启特定服务的权限：
```bash
# 执行 sudo visudo
deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart <service-name>
```

## 日常发布流程
在首次部署跑通后，日常的开发和发布链路为：
1. **开发**：在 OpenCode 中修改代码和功能。
2. **提交**：Push 代码到 GitHub。
3. **CI**：GitHub Actions CI 自动运行，保证基础质量通过。
4. **触发 CD**：在 GitHub 仓库的 Actions 页面，手动触发 Deploy Workflow。
5. **验收**：部署完成（显示绿色成功）后，进行人工验收。

## 常用发布指令
在已经配置好 GitHub Actions CD 的 Demo 仓库中，为了方便通过 OpenCode Agent 收尾发布流程，建议使用以下标准提示词。

> **提示：部署决策权始终在产品经理/用户手中**
> 请注意，如果是单纯的文档修改，完全可以不触发部署。如果 CI 环节失败，必须先让 Agent 修复 CI，绝对不要带病部署。此外，即便 Deploy 亮起绿灯，也仅代表代码传到了服务器，仍需人工打开 HTTPS 页面完成核心功能的走查。

**可复制提示词 (给 Agent 的 Prompt)：**
```markdown
请完成本次改动，运行与本次改动相关的本地检查；如果产生临时文件、日志、缓存、测试录音或测试数据库，请汇报路径并清理无用脏数据。push 后确认 GitHub CI 通过，并在我确认后触发 Deploy to DigitalOcean。部署完成后检查 /health，并提醒我进行人工验收。
```

## 人工验收清单
每次发布新 Demo 到服务器后，务必人工通过以下流程体验：
- [ ] 打开 HTTPS 页面，无证书报错。
- [ ] 浏览器提示麦克风权限，并允许访问。
- [ ] 点击 Start Session，WebSocket 成功连接。
- [ ] 说话能看到实时转写结果（或者预期的交互结果）。
- [ ] 点击 Stop Session，连接正常关闭。
- [ ] 检查 History / 日志页面是否有对应的数据沉淀。

## 多仓库复用方式
一台 Droplet 可以部署并承载多个 Demo，只需在配置时进行逻辑隔离：
- **目录**：每个 Demo 创建独立的存放目录。
- **端口**：每个 Demo 的后端占用不同的本地端口（如 8010, 8011）。
- **服务名**：创建各自独立的 systemd `.service` 文件。
- **Nginx**：创建各自独立的 Nginx `server block` 配置文件。
- **子域名**：分配不同的子域名解析并申请独立证书。
- **GitHub**：在对应的 GitHub 仓库里维护各自的 Actions Workflow 和 Secrets。

## 常见问题
- **DNS 未生效**：修改 A 记录后可能需要几分钟到几小时的全球同步时间，遇到无法访问可先通过 ping 测试解析。
- **HTTP 页面能打开但麦克风不可用**：现代浏览器安全限制，调用 `navigator.mediaDevices.getUserMedia` 必须在 localhost 或 HTTPS 环境下，请确保配置了 SSL。
- **GitHub token 缺少 workflow scope**：当通过 CLI push 包含 `.github/workflows/` 修改的提交被拒绝时，请在 GitHub 设置中生成带有 `workflow` 权限的新 Personal Access Token。
- **SSH_PRIVATE_KEY 格式错误**：确保在 GitHub Secret 中粘贴私钥时包含 `-----BEGIN PRIVATE KEY-----` 和 `-----END PRIVATE KEY-----`，并且没有多余的换行符或空格。
- **deploy workflow 遇到 sudo 需要密码**：说明 sudoers 配置有误，请仔细检查 `visudo` 中是否正确配置了 `NOPASSWD`，并且命令路径与 workflow 中使用的绝对一致。
- **Nginx 配置错误**：修改 Nginx 配置后务必先执行 `sudo nginx -t` 检查语法，再 `systemctl restart nginx`。常见报错可能来源于代理的端口填错，或 `try_files` 设置不当。
- **systemd 服务启动失败**：通过 `sudo journalctl -u <service-name> -f` 实时查看报错日志，通常是因为 `.env` 路径错误、端口占用或 venv 路径错误引起。
- **本地公司代理导致域名访问异常，但手机网络可访问**：部分公司或网络存在 DNS 污染或强制拦截，如确认配置无误，可尝试切换个人热点或更换网络环境。
