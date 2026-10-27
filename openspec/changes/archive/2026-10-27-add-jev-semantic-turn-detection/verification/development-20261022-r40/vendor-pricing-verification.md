# R2公开价格核验（2026-10-22，只读）

没有登录厂商账户、发送素材或调用计费API。价格核验不代表测试授权。

- Deepgram官方[定价](https://deepgram.com/pricing)：Flux英文$0.0065/min、多语$0.0078/min、Nova-3英文$0.0048/min；Flux TTS $0.045/1k字符。ASR固定9连接、每连接≤30秒，按最高单价保守估算$0.03510；拟授权上限$0.10。TTS固定35字符、3次，估算$0.001575，另批上限$0.10。
- Speechmatics：静态抓取[计算页](https://www.speechmatics.com/pricing/calculator)不能唯一确认实时模式；已用背景浏览器打开[官方定价](https://www.speechmatics.com/pricing)，选择Real-time并关闭网页报价演示的训练/预付量折扣（不是修改任何账号设置）。可见状态明确为实时、两折扣关闭，Enhanced显示$0.80/hr。原静态页$0.75/hr不再作为本批实时费率。当前实时3条×30秒对应公开费用上界$0.02；仍须冻结具体连接/脚本/授权。
- AssemblyAI官方[Changelog](https://www.assemblyai.com/changelog?3b7e7275_page=11&b942b364_page=2)明确Universal-3.5 Pro Realtime基础费率$0.45/hr，并给出speech_model=universal-3-5-pro固定快照选择。无需自动升级3.6。账号权限/实际请求仍未验证；不套用异步3.5或OpenRouter Sync价格。
- Soniox[官方定价](https://soniox.com/pricing)实际按输入音频/文本及输出文本token计算；约$0.12/hr不是硬上限，待探针纳入usage/输出上界和批次预算后再申请授权。

Speechmatics当前可见AX依据（短摘）：`Real-time models` / `Enhanced` / `$0.80` / `/ hr`；两个演示折扣switch均Value:0。未开启真实账号训练或新增留存授权。
