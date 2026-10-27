# r85 独立增量审查（2026-10-25）

**整体结论：BLOCKED。** 本次为提前阶段审查，不是最终Checkpoint C，不设置独立PASS或User Gate 2。仅检查r85新增探针、授权、六模型基本来源矩阵与8项实现任务补勾；未修改实现、未真实重跑、未扩展调查。

## 独立核查结果

- 当前探针离线 **25 passed /2依赖警告/4.43s**，见[r85独立日志](r85-independent/probe-tests.txt)。未重复完整715后端或UI。门禁0 errors/40 warnings，48项任务未勾，仅结构通过。
- 三份新厂商plan重新生成与冻结文件完全相等，selfhash与delivery-status D-077/078/079授权hash相同；确认来源/原话齐备，各最多1连接。三个已消费授权均在读Key/建连前被verify_authorization拒绝。没有借旧额度重跑的证据。
- 连接守卫落在实际SDK握手层；Speechmatics RT Transport.connect守卫及固定eu2 endpoint，AssemblyAI/Soniox实际_websocket_connect守卫，先计数再握手，恢复原方法。Soniox原生async迭代器保持、重复token也计数，>1000关连接并拒绝后续发送；**客户端异常停止保护不是厂商硬费用封顶**。D-079明确授权该取舍，实际64/1000，账单未知。
- 六模型原始安全jsonl的hash与矩阵一致，均status=ok、实际1连接；missing_reason均为空，所有实际输出段0≤start≤end≤8167.5ms。固定模型是请求模型，不虚构未返回的服务端build版本。真实证据仅单段虚构英文数字，不证明重连/语义效果/完整工具取消。
- `implementation-task-audit.json`引用的JUnit具体用例全部存在且passed；99项src/frontend生产输入hash与r83一致。M1-2、M3-1/2/3/4/6、M4-1/2的补勾限于实现与明确本地证据，与所列排除范围相容；不能据此勾整个M1/M3/M4或完整M5。原文未把这8项当最终独立通过。

## 发现的一处证据措辞问题

r85 README最初写“每个来源事件……存在有效归一化段”，过强：AssemblyAI13个转写帧中5帧输出空，Speechmatics14帧中1帧输出空。应分别记录**转写帧、非空归一化事件、实际输出段**：

| 请求模型 | 转写帧 | 非空归一化事件 | 输出段 |
|---|---:|---:|---:|
| Flux英文 |18|18|18|
| Flux多语种 |18|18|18|
| Nova3英文 |7|7|7|
| AssemblyAI 3.5 |13|8|8|
| Speechmatics Enhanced |14|13|13|
| Soniox v5 |18|18|34|

空帧文字与前帧一致；AssemblyAI对应词时间、Speechmatics对应metadata/fragments也一致。`SourceNormalizer.normalize`契约只返回changed ranges，`_segment`比较起止/文本/Final/词时间完全相同即返回None；有效Final仍有新修订。因此这六帧是重复快照去重，**不是已确认的来源缺失或实现失败**。已登记R85-INDEPENDENT-EVENT-COUNT-CLAIM；研发随后修正README及矩阵，新增transcription_frames/nonempty_normalized_events/normalized_segment_count/deduplicated_snapshot_frames并明确changed-ranges不变式。评审只读复核全部字段与上表相符，该问题Resolved且已向用户披露；原jsonl未改，无需新增收费重跑。

## 包与冻结点

只读核验r85包 **928文件**逐文件hash及archive SHA-256：`f7148910c80d5cfd143f7b5a3c163bc8589060ac33d312d9d686ab4e7fdc1a86`。路径`verification/development-20261025-r85/review-package/`。未擅自重建包。此包早于本次独立措辞发现，后续报告/矩阵更正应以外层文档为准，显式说明包内旧措辞。源码与用例没有因更正文档而变化。评审未把旧cwd运行15项当当前25项或解包新版本证据。

## 尚未关闭与下一步

1. **H1 RTC/来源计时**：下行任务对应、实播/停止和Final/编号组合已证；上行采集→编码RTP→解码/重采样→VAD边界、跨连接绝对时钟仍不完整。可靠映射后再在原正式入口验证区间及缺锚拒绝；默认候选不自行采用，不换传输。
2. **H2完整真实兼容**：此次关闭六模型基本单例接通与来源范围缺口；续说/主动修订/真实重连、多语/效果、实际LLM工具与完整TTS取消仍未证。只为明确缺失事实准备新最小授权，不重跑已通过同例或复用D-075–079。
3. 设备/AEC/手机/Safari/弱网、目标Python3.11与1核1G性能、最终统一回归及独立功能/视觉/可访问性仍需完成；不由这次探针25项通过代替。

本次新增实现缺陷：**未发现**。新增证据问题：上述计数/措辞已校正并独立只读核对。新增产品决定：**无**。所有历史授权已消费，无新厂商调用许可。
