# r88 独立评审返修自测包（2026-10-26）

**六项评审问题已按下表修复自测，独立复审均Resolved；不是全Change通过。新增严格RTC E2E缺失红灯仍Open，不用r87旧成功覆盖。** 原评审及失败日志保留；没有外部厂商调用、新依赖、传输架构变更、默认RTC采用、提交/推送/部署。

## 逐项关闭条件与实际证据

| 问题 | 实现与正式回归 | 自测结论/证据 |
|---|---|---|
| B1 英文段边界 | SourceSegment明确subword来源；独立词段保留边界，原数字/CJK连续，自带空格保留；customTD pending混合共用规则。跨提交/Final切片使用完整覆盖后的原文本span，不直接join词 | transcript-red.txt先失败；backend-fix-first.txt35通过；test_td_transcript.py参数场景及test_td_runtime.py混合回流；Soniox hel+lo+空格world不被插成hel lo |
| B2 Final漏否定 | resolve_snapshot跨范围切片前要求全文词覆盖；缺do/not的词时间返回None，原始Final保留，禁止错误重答。相同完整范围不必切片 | 原review backend-review-red.txt三失败；正式test_td_review_regressions.py原复现、test_td_runtime.py实际适配入口提交后Final，均含backend-full.txt |
| B3 D080旧截止 | 每次poll先检查当前有效target，旧Final窗口不再授权修订文字；原Tmax不延长，已开始窗口不重启叠加 | test_td_timing.py：600开窗口、修订target2000、800/1999不交、2000可交；无新Jev则2500，backend-full.txt |
| RTC回执挂起 | PlaybackReceiptSender有序发送、3秒截止/abort、关闭取消、失败一次后bridge中断。服务端stop控制独立5秒确认守卫，未知则永久错误、不释放新答；failCall错误遥测不阻塞媒体清理 | rtc-sender-red/first.txt、stop-guard-red/first.txt；正式RTC故障真实HTTP先204接受started但响应挂起、错误遥测也挂起，媒体关闭/错误页/Final不叠播，rtc-fault.txt 1通过9.2秒；正常播放/Final/历史缺失如实记录rtc-playback.txt 1通过7.8秒 |
| 完整性4字段禁用 | enabled/load/change统一按规则与完整性开关禁用/启用；关闭正常保存collection=null | ui-fields-red.txt失败；ui-confirm.txt桌面1440/1024两通过，ui-390.txt另390px1通过1.8秒；实际正式路由/组件fixture，保存开启16位→关闭null→刷新禁用，#td无横向溢出 |
| README过时 | Change README、self-test、任务/状态/当前矩阵统一指r88，r87封包保持历史，不冒充当前源码 | 新review-package的snapshot.json；旧独立BLOCKED保留，当前独立结论见stage-review/repair-review-r88.md（原六项Resolved，整体仍BLOCKED） |

## 当前最终软件回归
- 后端754 passed、5条依赖弃用警告、38.43秒（backend-full.txt/backend-junit.xml），含已提升到正式tests/的3项评审复现。先前749未含最后追加3评审+2正式入口回归，保留first而不冒称最新。
- 客户端25 passed（client-full.txt），含4种发送故障及生产prepareRTCPlayback实际绑定/中断。
- Ruff src/tests通过；实际Python3.13 mypy79源通过；Vite构建通过。3.11目标/依赖环境仍未验证，不隐藏旧失败。
- 原始后端3红灯、转写边界红灯、stop守卫红灯与RTC遥测阻塞/字段红灯均保留。UI第一次修复后失败是测试仅1个Jev选项被正确拒绝，改为合法2选项后通过，没有放宽生产校验；Optional类型首轮失败修复后通过。

## 当前新增失败与真实性边界（不能视为已关闭）
1. 正常RTC严格E2E场景等待5秒仍0；播放/停止/Final、认证播放范围已通过前置断言。rtc-normal-first-failure.txt及rtc-source-failure-evidence保留。另一个明确限域的正常播放组合仍保存source_end_clock_unavailable、e2e=0，未绕过严格RTC_E2E=1的两响应断言。r87曾成功不证明当前稳定覆盖；不重放旧有限实验/不赌重试。请独立审查此Open来源缺口后确定最小工程关闭步骤。
2. 故障组合的错误遥测故意挂起，客户端实际错误关闭，但服务端顶层history.status仍completed、error_category为空；只能证明已接started+playback_session_ended ended_started/未知stop，不能声称服务端已取得确定客户端失败原因。rtc-fault-evidence/receipt-response-lost-history.json保留原值，未伪造failed或stop。此记录含义/送达边界继续Open，不自行改用户正常结束的语义。

## 仍未验证
D045无麦克风：物理外放/双讲/AEC、真实声学首播；手机/Safari/弱网、目标1核1GB/Python3.11。四家六模型基本英文数字外部证据仍为r85版本，本轮仅离线适配器回归，没有费用或新真实多语种/WPM/修订重连/完整LLM工具/TTS取消/P95效果。新RTC默认采用未批准、时钟误差/新增延迟未达标证明。独立C/PASS/User Gate2由审核/用户负责。

## 复现、版本、临时数据与回退
源码未提交；review-package/snapshot.json逐文件SHA和package-check.json归档SHA标识工作区，运行Python3.13锁定环境及前端package-lock。仓库根：`.venv/bin/python -m pytest -q`、`node --test frontend/tests/unit/*.test.js`、`.venv/bin/ruff check src tests`、`.venv/bin/mypy --python-version 3.13 src`；frontend内`npm run build`。原独立三复现可直接pytest stage-review/backend_repros_20261026.py，已正式提升到tests/test_td_review_regressions.py。

正式RTC：tests/ui/td_local_app.py ordinary、VOICE_AGENT_TD_LOCAL_RTP_CANDIDATE=1，仅loopback替身；Vite代理该端口；td-rtc-entry.spec.js开启LOCAL_RUNTIME。故障加RTC_RECEIPT_HANG=1（先向真实本地API提交第二次started，挂HTTP响应与error遥测）；正常播放加RENDER_CLOCK_PROBE=1；严格源指标另加RTC_E2E=1，当前该项失败，不混作正常播放通过。配置页td-settings.spec.js API fixture使用正式路由及DOM。

临时DB/本地录音：/tmp/voiceagent-r88-rtc；浏览器原件/tmp/voiceagent-r88-*，构建frontend/dist已忽略；安全JSON/截图/文本和JUnit保留本目录，录音/数据库/密钥/原始server日志/trace不进包。无用户文件删除。默认development_rtp_candidate=False保持原链，必要时停用开发候选；不得通过移除保护恢复未确认叠播。
