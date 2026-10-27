# 研发自测报告 — 原轮次证据与编号混合修订增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** M1—M5和正式UI A/B未闭环，不申请独立审核、Checkpoint C或User Gate 2。D-050仍为最新产品决定；后台每会话100次，不增加控件，不授权真实收费测试。前轮实现/测试见[self-test-report.round12.md](self-test-report.round12.md)。

## 本轮实现与结果

- 同一尚未提交LLM的编号逻辑turn内，旧纯编号片段跨续说修订为混合表达时，撤销旧本地值并把整句回流普通TD。真实Pipecat聚合器/LLM工具/续生成验证工具写入与用户提交各一次；已提交旧turn的同类修订不重开、不进入新轮候选。
- Jev后端判断尝试固定原turn、文本修订与助手快照；厂商忽略取消后迟到结果仍记原turn。保存实际后端耗时和Noul/Choice/目标/剩余等待分解，不把后端尝试当成收费HTTP调用。
- 会话开始保存原TD设置、Jev模型/指令/选项等待；不保存endpoint或凭证。正式WS ASGI探针显式断线后等待原finish_call完成，再从正式历史API读取设置/回执，确认凭证不进入历史。首次失败来自TestClient退出立即取消ASGI任务，已保留失败及修正后证据，不改生产持久化语义掩盖问题。
- 正式历史组件显示这些实际事件并固定turn/response归属；原生旧历史保持缺证据，未归属事件不贴当前轮。修复跳转后粘性标题上方透出旧记录；实际桌面/390px顶端命中先失败后通过，不仅检查宽度。
- 最终全量 **574 passed，3项依赖弃用警告，33.37秒**：[pytest-final](development-20261022-r13/pytest-final.txt)。ruff通过；相关6源文件mypy通过。前轮相关34源文件通过，全目录仍受既有NumPy类型声明与目标Python3.11兼容限制，不能声称全目录类型检查通过。
- 正式配置/历史1440与390/AudioWorklet共 **6项浏览器回归通过，4.8秒**：[browser](development-20261022-r13/browser.txt)；Node历史/渲染4项通过；Vite build、JS语法和diff检查通过。外部ASR/LLM/Jev/TTS全部由离线替代，本地bundled Silero按原正式流程加载。
- Change门禁 **PASS，0 errors、22 warnings**：[change-gate](development-20261022-r13/change-gate.txt)。告警为未闭环范围及29项未勾选任务，不表示功能完成。

## 剩余实现与未验证范围

1. 完整浏览器WS网络/麦克风链路和WebRTC任务/实际渲染映射未闭环；当前ASGI真实传输、模拟回执与浏览器组件证据分开，不拼成端到端通过。
2. 未知ASR音频范围可靠切分、跨连接时钟与真实六模型回包/重连兼容未验证；无依据不猜范围或按字符串去重。
3. 主线程收到渲染消息时间不能冒充精确quantum/硬件首播；真实播放/E2E数值和逐响应版本指标尚未闭环，新记录继续明确缺失，旧数值标记unverified。
4. 正式UI完整状态/中英、缓存生成试听/失败矩阵、真实API持久化刷新重启、完整视觉diff与可访问性未完成，Checkpoint A/B未通过。
5. 未做真实Jev/TTS语言效果、P95、费用、耳机/外放双讲/AEC及目标环境资源测试；没有真实客户数据或付费外部调用。后续真实测试须另批授权数据/厂商/费用上限/停止条件。

原型v0.14字节未改，SHA-256：657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。未填写独立PASS/Gate2、合并主规格、归档、提交、推送或部署。r12/r13证据保留；/tmp/jev-r13-*.txt为临时追溯副本，生成dist/test-results已忽略，没有真实录音或厂商合成资源。验证用Vite仅本地运行，回合结束停止。
