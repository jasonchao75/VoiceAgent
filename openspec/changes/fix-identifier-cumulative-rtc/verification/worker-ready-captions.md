# 2026-10-28 无声与重复字幕修复

## 生产关联（只读external-real）
通话2002b221-6170-4a83-9d0a-1480a3cb0230，01:21UTC，Android10 Chrome138。正常连接，用户约61秒主动挂断。服务端4次TTS首音频/任务派发；3次task_stopped全为rendered_samples=0，无task_started/finished。不能把停止回执当可听证据。
同时间nginx：手机请求旧td-rtp-candidate-worker-CMWK8wxh.js为404；音频worklet/inputworker200。服务器7752141应worker-7WgU_t1y。证明使用旧资源引用；未推断手机系统音量。旧Worker异步加载失败未捕获，native音轨已静音，足以导致本次无声表现。
历史3用户/3助手，无相邻同role同text重复；TD3提交，原ASR/来源7帧。RTVIObserver按frame.id去重，ASR Final和私有TDSubmission具有不同ID，两份均发送给同一字幕回调；不是根据用户猜测认定。

## 修复边界
- worker模块ready握手后才继续初始化与连接，10秒有界等待；捕获模块404/import/error/messageerror，锁存ready后到bridge建立前错误；清理worker/音频/麦克风/名额，提示刷新。模块ready不是播放成功。
- /demo/{id}及/demo.html返回no-store；已缓存/已打开旧页面无法追溯修复，用户需刷新获取新版，不声称自动兼容删除的旧chunk。
- 自建TD专用RTVI工厂只忽略TDSubmissionFrame；保留ASR Interim/Final、真实相同文本多次、其他RTVI消息与LLM提交。
- 手机原UI为final-only；私有TD Partial提交不再伪作厂商Final。迟到厂商Final仍显示；可修订Partial字幕不是本次新增功能。
- 无重播/漏音/传输变化，无收费调用、配置或数据库迁移。

## 验证
- 819后端全量通过/9 skipped/10 warnings（依赖弃用），51前端Node；31后端定向（publication/RTVI）、mypy80文件、ruff及build通过。
- Chrome138真实本机生产入口：4043.6s通过，确认无peer、错误204、名额0、micended；正常13.6s通过，有真实renderer receipt、跟读/清空/LLM链路。
- 现代Chromium同一正式入口桌面13.6s、窄屏13.3s通过。
- 首次正常回归在通话前导航上下文销毁，Vite对应src/td-rtc-entry.js热重载；trace保留/tmp/voiceagent-worker-ready-138/initial-navigation-trace.zip，停止编辑后复跑通过，未隐瞒失败。
- 单测原SDK4条/过滤后3条（Interim+2次同文Final），先Final后TD/先TD后迟到Final均覆盖，不按文本去重。
- 独立审核发现ready后bridge前错误窗口，锁存及assertHealthy后复核PASS；仅Partial的展示边界经规格审核记录。
- 证据/tmp/voiceagent-worker404-138、/tmp/voiceagent-worker-ready-138-fixed、/tmp/voiceagent-worker-ready-modern；日志/tmp/voiceagent-worker-ready-{server,unit,pytest}.log；隔离DB/tmp/voiceagent-worker-ready-20261028。不提交日志、DB、录音。

## 发布和手机边界
独立审核限定补丁；手机刷新后可听及字幕需一次实际复测，不把本机渲染事实当手机听感。部署结果见deployment.md。
