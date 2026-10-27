# r87 研发候选交接增量（2026-10-25启动，26日收敛）

当前源码未提交，SHA清单见review-package/snapshot.json；不覆盖共享工作区其他任务。未自签独立PASS、Checkpoint C、User Gate 2。

## 本轮关闭
RTC保留RTP，在受控正式入口增加同worker原生captureTime、RTP负载hash、服务器processed PCM范围的严格关联；认证capture-clock与渲染锚组成保守E2E区间。未知、冲突、换代、过期保持缺失。音频不等待元数据，默认原链不变。

正式RTC组合1通过（rtc-formal-final.txt）：原任务实际停止、Final新答、两个响应各自范围/双端锚/同包hash证据。formal-final-history.json为真实本地替身会话；restart-history-check.json证明应用停启后HTTP历史完全相同。编号仲裁沿用r69及r83当前未改的相关实现证据，不冒充本轮新RTC编号组合。

## 实际回归
- 全后端739 passed /5 warnings /39.37秒（backend-full.txt）。
- 客户端单元20 passed（client-full.txt）；Ruff src/tests通过；Vite构建通过。
- 实际Python3.13类型检查79源通过（mypy-py313.txt）。默认3.11目标被本机NumPy类型语法阻断，保留mypy-default-environment-failure.txt，不能声称3.11通过。
- 初次RTC失败为测试在通话结束前读仅结束落库的历史；第二次误把同轮实时指标数量当两个响应数。两次失败原样保留，修复后live按轮次核对、结束历史仍严格要求两个响应及各自证据；没有放宽来源/计时条件。

## 有限剩余范围与完成条件
1. 当前研发候选完整审核：独立评审核对Spec映射、当前源码/所有证据及r87增量；发现实际缺陷由研发修复，未签PASS前不进Gate2。
2. 受控RTC正式采用：仍仅开发候选；需同输入新增延迟对照和支持设备/弱网结果，再由用户决定默认采用。不得把此次本地通过作为正式替换许可。
3. 设备/声学：本机无麦克风；手机/Safari、耳机/外放双讲、硬件ADC/物理出声、目标1核1GB未实测，按D045明确未验证，不用mock替代。
4. 厂商效果：四家六模型仅冻结英文数字基本Partial/Final范围通过；续说/改写/重连/多语种质量/WPM/P95及完整真实TTS取消未测。现有授权全部消费；无新付费调用。
5. 当前UI A/B沿用r82/r84正式页面矩阵；本轮只改RTC旁路和组合测试，无配置控件/冻结HTML修改。独立C和User Gate2由评审/用户负责。

## 复现
本地Python3.13环境安装requirements.lock及frontend/package-lock.json；不需要真实Key。后端 `.venv/bin/python -m pytest -q`；客户端 `node --test frontend/tests/unit/*.test.js`；类型 `.venv/bin/mypy --python-version 3.13 src`；质量 `.venv/bin/ruff check src tests`；frontend内 `npm run build`。
RTC：按tests/ui/td_local_app.py启动loopback替身，development candidate与ASSERT_RTP_INPUT开启、ordinary场景、独立/tmp数据目录；Vite代理同端口，td-rtc-entry.spec.js开启LOCAL_RUNTIME、ASSERT_RTC_CAPTURE、RTC_E2E、RENDER_CLOCK_PROBE，desktop-chromium。API/浏览器全部替身，不能代表厂商效果或物理出声。

临时运行数据/录音在/tmp/voiceagent-r87-rtc，浏览器原件/tmp/voiceagent-r87-browser-final，日志/tmp/voiceagent-r87-*；不进包、不提交。安全JSON/测试结果保留本目录。回退：保持development_rtp_candidate=False；无数据迁移、默认链路/部署修改。

补充指标边界：本次1:1范围598.448–1334.633ms、1:2范围814.830–1840.835ms；采样双锚形成较宽区间，不作为精确延迟、低延迟达标或硬件声学指标。
