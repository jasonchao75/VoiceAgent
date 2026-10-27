# r81 WS源端认证时钟和E2E闭环

## 关闭的实现阻塞

正式WS输入/输出使用独立认证nonce账本；采集Worklet在实际process量子回报帧，来源标记仍保留原PCM/分包。配置VAD源终点通过精确PCM累计offset映射到同一输入时钟，floor/ceil完整覆盖小数样本边界，缺失或断层不猜。暂停候选及时冻结来源区间/跨度，最长等待超出活锚寿命仍保存已证明事实；未提交续说失效，提交后按原turn保持。

E2E=[max(0,Rlo-Shi),Rhi-Slo]；不取中点或RTT/2，不用TD提交/HTTP收件伪代实际事件。源锚迟到可与已冻结输出证据汇合。范围和完整两端证据按response/playback/turn存入历史，正式页面原回复旁、共享实时/历史指标显示来源/误差。旧标量仍null，旧记录不回填。

起点明确为配置VAD停声源样本，终点为Worklet渲染；不是ADC采集或硬件声学出声。RTC上行尚无来源映射，继续缺失，不能将本轮WS结论扩展为RTC或物理用户感知E2E。

## Spec对应证据

- voice-pipeline/spec.md“实际播放范围指标”及缺证据场景 → tests/test_capture_source_clock.py、test_render_clock.py、test_playback_receipts_api.py。初始红灯capture_clock不存在；实现后源/渲染nonce隔离、缺跨度、精确offset、长TD等待冻结和区间减法均通过。
- 正式WS/假麦克风/原SDK/本地替身三段服务/Final取消/实际回执/持久范围组合：1 passed / 6.6秒，包含原回复与Final两个E2E卡片。增加可审计跨度后同一目标组合再次1 passed / 6.6秒。非厂商语言/性能证据。
- ws-timing-proof.json为第二次实际组合的白名单metrics/事件；proof-audit.json独立读取保存数据逐项验证两回复源span映射、两端严格前后锚及区间减法。
- api-process-restart.json与api-proof-process-restart.json分别在应用进程停启后通过真实HTTP核对原范围及新增完整源跨度，metrics/全部TD事件逐字结构相同。不是仅重开SQLite对象。
- 正式历史1440/390px、中英及抽屉无横溢：2 passed / 1.4秒，ui.txt、ui/（fixture截图）。修正fixture仍标源缺失而已有E2E的矛盾，新增来源和中文检查。
- 当前相关后端40 passed / 1.97秒、2依赖警告，backend.txt。客户端3 passed，client.txt。本轮不重复无变化的完整706项。

## 局限和剩余任务

RTC上行源时间未接；真实厂商/取消、ADC/扬声器物理时间、手机/Safari/弱网/AEC/目标容量未验证。区间可能宽；首轮本机示例约703–1314ms只是配置VAD/合成替身，不代表精确延迟、P95或厂商性能。默认RTC未替换、没有新控件、RTP架构/音频未变，无付费调用。

新增功能后正式UI/构建和定向检查如本目录记录。一次UI修改命令误在frontend目录失败，第一次只运行旧断言；纠正路径后新增E2E断言的实际2项结果见ui.txt，不把旧检查冒充新检查。

临时DB、惰性加密Key、原包和完整本地历史在/tmp/voiceagent-r81-clock；原始服务日志/tmp/voiceagent-r81-*.log可能含测试能力URL，不打包。Playwright trace在忽略test-results目录。8793/5178本轮服务已停止，其他任务服务未动。只保留脱敏白名单JSON/截图作为证据。

r78阶段源快照不包含r79–r81代码，不能用其hash代表当前实现；最终全范围包及独立审核仍待剩余里程碑收敛。不填写独立PASS、Checkpoint C或User Gate 2。


## 最后类型/文档修正

项目标准skip导入模式全src77文件通过（mypy-full.txt）；额外silent导入5源曾报5项API凭证/厂商静态类型错误（mypy.txt）。已补可空凭证注解、Literal边界cast和诊断SecretStr包装，值及产品规则不变；相同额外模式当前5源通过（mypy-target-fixed.txt），API/鉴权14 passed / 3.23秒（api-type-regression.txt）。默认部署3.11仍未验证。交接首页/自测顶部遗留“47错误/E2E全未实现”已修正，历史失败不删除。
