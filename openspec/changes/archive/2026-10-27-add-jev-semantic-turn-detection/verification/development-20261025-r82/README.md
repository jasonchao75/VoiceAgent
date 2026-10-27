# r82 正式UI Checkpoint A收敛

## 本轮关闭的阻塞

正式Sessions缺少冻结Turn头/结果徽标/User角色标签；Turn标题18.72px而冻结14px；抽屉元信息没有进入冻结样式作用域，字号为24/16而冻结18/11；列表标题/窄屏筛选与列规则同样未应用。已复用正式路由/组件的冻结局部样式，保留D-072全局手机顺序。结果徽标只读取实际td_commit/候选/本地收集事件，不伪造提交。

截图进一步发现固定抽屉头遮住会话标题8px；几何红灯title.y=67<header.bottom=75。正式内容增加8px padding阻止margin折叠/遮挡，双视口修复后title.y=89>=75，390px截图人工核查完整可见。没有修改冻结HTML或设计基线。原来仅比较样式的检查不能证明可见性，本次补独立几何断言。

新增E2E源锚/来源跨度已在展开历史字段显示，数值/原文保持literal，不翻译或重算。配置四类静态错误此前缺中文，实际中文关键词错误红灯后补齐词条；无效草稿不保存，修正后唯一保存且保留原提示指令。

## 实际结果与Spec映射

| 规格/场景 | 当前结果 | 证据 |
|---|---|---|
| Frozen UI baseline / Per-turn TD history evidence | 正式Sessions列表/详情关键结构/字号/颜色/边框与冻结一致，1440/390；原标题遮挡已修 | final/签名/几何/截图、history-final.txt |
| 历史原文、旧指标、Final版本、D-073来源范围、失败空态 | 改动相关10 passed / 6.0秒，覆盖中英和两视口 | history-final.txt |
| Self-developed TD source for every catalog ASR model | 六模型逐一self_developed可进入、native/off隐藏、同Bot草稿保留、抽屉无横溢；2 passed / 6.7秒 | sources-final.txt、sources-fixed/ |
| 配置校验 / 双语草稿与失败状态 | 空关键词、重复别名、反向等待、空Jev选项×中英×两视口；4 passed / 4.1秒；错误不发送PUT，修正后一次有效PUT | validation-final.txt、errors-fixed/ |
| Share冻结卡片/D-072/禁用与恢复/未发布草稿 | 2 passed / 1.9秒；仅fixture，不证明实际发布/持久化 | share-final.txt、share-fixed/ |
| 未变更的六设置子页 | 复用r42六状态×中英×两视口的实际对照及控件命名/无溢出，不重复稳定矩阵 | checkpoint-a-matrix.json引证原始证据 |

checkpoint-a-matrix.json核对15个验收范围的原始文件/hash、控件/关键样式、源入口、无效保存数及冻结SHA。研发Checkpoint A固定fixture主要矩阵已完成；它不等于独立C、User Gate2、实际厂商兼容或完整B。

## 失败分流

- history-header-red：目标头部0而预期1，确为缺实现；history-font-red及metadata/list红灯是计算样式差异，随后修复。
- title-red：样式已一致但几何遮挡，不能抹去或把样式通过当全部视觉通过。
- sources-probe-red：脚本在默认Rules找Semantic的隐藏minimum超时；显式切页后同一矩阵通过。不是产品行为红灯。
- validation-red：2个英文例已过，中文关键词仍原英文，缺翻译已修；完整4例最终通过。
- share-server-stopped：中断后旧5177进程已不存在，两个例均ERR_CONNECTION_REFUSED，未执行产品断言。新本机5178同目标通过，不称产品修复。

## 剩余完成条件

- B：核对实际API/发布资源/故障恢复组合的证据，补真正缺失项；不能用本轮fixture代替真实HTTP、存储或厂商。
- RTC：上行源时钟/新增延迟与平台兼容仍缺，默认正式采用仍未授权；WS结论不扩展到RTC。
- 真实厂商：已有Jev/Flux continuation/TTS one部分成功，其余范围/修订/重连/取消不证明；原批授权不能重放，替换素材必须新单批授权。
- 候选收敛后一次完整回归、重建当前源快照/自测包并交独立审核；不填写独立PASS/C/Gate2。

临时日志/截图/fixture产物在/tmp/voiceagent-r82-*及/tmp/voiceagent-r82-history，无客户数据或外部调用；忽略test-results/playwright保留失败trace。新启动5178仅本轮fixture服务，结束时停止，不操作其他任务数据。r78阶段包仍是旧源码，不代表r79–r82。
