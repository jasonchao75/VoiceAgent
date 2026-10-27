# 研发自测报告 — 正式Advanced配置增量

**IN PROGRESS / NOT READY FOR INDEPENDENT REVIEW。** Q-041新Bot的Jev调用上限待用户选择，Change门禁为BLOCKED；暂停该默认填充，继续其他已授权开发。M1—M5未整体闭环，未申请独立审核、Checkpoint C或User Gate 2。

## 本轮实际实现/验证

- 冻结原型TD/Jev区域在正式Advanced路由/组件根节点加载；保留General/fallback，表单API适配层供fixture或正式服务共用，没有单独验收页。
- TD/VAD/优先规则/关键词/词表/完整性、Jev问题/Choice等待/融合/连接密钥保存及本地预览已接表单与正式保存接口。新参数不沿用原型数字，已有明确配置往返；新Bot max_calls缺口不擅自填100。
- 词表音频状态/手动生成/试听已连接永久资源接口；不主动合成、不在预览下发key。未保存TTS/词表拒绝生成/试听。该部分仍欠完整浏览器回归及真实API UI验证，不能声称完成。
- 正式页面fixture浏览器测试：保存650、禁用优先规则仍保留词表草稿；Jev预览状态大小写和问题结构准确、无key、无本地等待字段；增选项同步手工分布；延迟保存期间新值700保留并可再次保存。真实外部调用0。
- Playwright **3 passed，2.7秒**（TD配置1＋历史桌面/390两项）；证据[ui-final](development-20261021-r9/jev-r9-ui-final.txt)。最初正式入口缺失的红灯与中间窄屏失败也保留。
- 390px首次切换产生207>72过渡宽度；稳定后1440/390均无持续横向溢出，Jev截图在r9。该检查不替代完整浮层状态矩阵或视觉diff。
- 新表单脚本及main语法检查、Vite生产build、git diff --check通过；本轮未修改后端，所以未无意义重复全量Python。前一全量542项及额外1项保护用例见[self-test-report.round8.md](self-test-report.round8.md)。

## 未完成与未验证

1. Q-041新Bot首次配置的Jev调用上限待确认；这是新增规格缺口，不复问Gate1。已有保存值不受影响。门禁1个未关闭产品问题，不能宣称里程碑完成。
2. 词表音频生成/重试/试听、Bot切换与key各状态仍需更多回归；真实API刷新/重启UI、全部状态/中英/视觉diff未完成，Checkpoint A/B均未通过。
3. 跟读串行输出、客户端实际开播/停止、旧纯编号变混合句推理调度、修订补读、未知范围/重连时间仍未闭环。
4. 真实六模型、Jev/TTS效果与费用、物理AEC/双讲、目标资源环境未测；未做真实或付费外部请求，Gate1不是费用授权。

原型SHA-256保持657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4。无独立PASS/Gate2、合并主规格、归档、提交、推送或部署。本机Vite服务已停止；frontend/dist、test-results为忽略产物；r9截图/日志保留。历史回归按既有脚本刷新r3同名来源标记截图，不是更改冻结baseline。/tmp/jev-r9-*.txt为追溯副本，无真实音频/厂商合成资源。
