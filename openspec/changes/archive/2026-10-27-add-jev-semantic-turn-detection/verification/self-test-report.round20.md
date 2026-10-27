# 研发自测报告 — 第二十轮原WebRTC音轨浏览器验证

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** D-052继续有效，没有切换数据通道音频。此前服务端清队列和后端578项证据见[self-test-report.round19.md](self-test-report.round19.md)。

- 发现并修复正式mobile-demo没有附着远端音轨到audio元素：锁定SmallWebRTC默认媒体管理器关闭内置播放，仅暴露track。现接单一原生audio元素，仅远端轨；旧连接回调隔离；结束pause并清srcObject。没有改RTP/音轨编码/信令/上行，不新增页面或服务端AEC。
- 先红后绿：连接已成功但RTP收包后解码/播放统计0，实际分析器静音；补音轨播放出口后收到Partial 440Hz与Final 880Hz合成音。旧答计划5秒，实际观察短于2秒；Final音出现后700ms观察窗旧音未回流。audio元素确实处于播放状态，结束后暂停且源释放；正式历史在结束持久化后保留一次response_restart。此门槛只针对合成fixture，不是停止延迟SLA或零残留证明。
- 浏览器测试使用正式demo文档/组件与真实API/SQLite/信令/SDK/RTP；Vite公开路由只映射同一demo.html。ASR/VAD/Jev/LLM/TTS为本地替代、麦克风为Chromium假设备；音频分析器是接收音轨观察分支，不替代正式audio播放。不把远端解码采样当扬声器硬件事实。Chromium测试允许自动播放，真实手机用户手势/后台/蓝牙仍未测。
- 初期观察器因既有NLTK punkt_tab缺资源异常，临时确定性分句替代仅用于定位；已从官方固定URL经certifi TLS及官方SHA-256核验安装到忽略的.venv/nltk_data，并移除分句替代复验。官方下载器代理拒绝/系统CA失败日志保留，没有关闭安全开关。[环境资源说明](runtime-prerequisites.md)。其他部署环境未验证。
- 26项移动/RTC矩阵通过（当时分句替代）；移除替代后10项RTC/WS/配置通过，1项重启协调跳过（此前独立验证）；最终实际资源下RTC桌面/窄屏2项通过。构建、ruff、diff检查通过。日志与合成音频统计在[本轮证据](development-20261022-r20/)。后端全量最近r19为578通过，本轮未改后端生产代码。

未闭环：RTC逐任务精确渲染回执与编号/缓存串行完整组合；精确时钟指标；未知ASR范围/重连、真实六模型及厂商效果；历史语言/完整UI视觉和可访问性；真实弱网/手机/耳机扬声器AEC。未使用真实Key、客户数据或付费推理，无独立PASS/Gate2/提交/推送/部署/主规格合并/归档。隔离服务8765/5174与/tmp/voiceagent-td-r15测试数据保留；NLTK资源在忽略的.venv/nltk_data，不提交。
