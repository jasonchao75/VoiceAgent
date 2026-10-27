# r90 限定界面/专项计划独立复审（2026-10-26）

**限定增量结论：当前未发现剩余确认实现缺陷；全Change仍INSUFFICIENT EVIDENCE，不签完整Checkpoint C、全Change PASS或User Gate 2。**

评审加载change-verifier，仅检查本轮冻结表头、键盘/焦点及两份专项计划，未修改实现/测试/原型；未调用厂商、未启动RTC、未重跑756后端/25客户端或整个既有验收矩阵。当前旧六项返修独立关闭结论不重做。

## 1. 冻结表头与断点

对比r89冻结源码与当前差异，以及v0.14实际CSS/HTML：仅补正式`.vocab-head`缺失的grid显示、10px文字、muted颜色、14px上边距，原列模板/gap22px保留；`max-width:700px`与原型一致隐藏表头，音频行仍在第二行。没有改冻结文件或校验值，也没有新造验收页。

研发同正式路由/DOM与原型计算样式/列几何双向比较，1440px中英、390px中英、650px/701px英文 **6项通过**；Google Chrome同批相关 **14项通过**。仅fixture数据适配，不能声称真实API/手机/Safari兼容。

701px首次额外断言“表头中心一定落在实际输入框内部”，冻结原型自身在该宽度也不满足。按原型实际header/cell相对几何比较改正oracle是合理纠错，不是降低已确认视觉基线。原header-red记录缺grid等真实样式差异，与后续oracle错误应分开。

## 2. 键盘与焦点

Jev入口/返回显式去往可见返回/触发按钮；新增编辑行聚焦首输入，删焦点所在行后聚焦相邻可编辑行或新增按钮；ASR非模态抽屉打开/关闭记录其触发卡片。禁用字段由原生disabled跳过，未引入焦点陷阱或新产品流程。脚本检查Tab/ShiftTab/Enter/Space/Home/End/Escape、focus-visible、可访问名称、唯一ID/ARIA快照。

### 独立发现并修复的确认缺陷：R90-SESSIONS-REFRESH-FOCUS

独立真实浏览器fixture复现：进入Sessions产生的列表请求尚未返回，使用仍可见旧行打开详情；关闭按钮已获焦。列表晚返回时`renderHistory.replaceChildren`令原返回行脱离DOM。Escape隐藏抽屉后，焦点仍是`#close-history`且visible=false。该窗口是生产可达竞态，**不是单纯测试没等待加载**；原用例先等list response会避开它。

研发最小修复以稳定callId找当前重建的同一行，找不到才用可见Sessions入口；仅焦点仍在drawer内部才恢复，不抢用户主动移走的焦点。评审只读核补丁并用原同一复现重跑：triggerDetached=true、drawerHidden=true，但焦点返回visible=true的按钮，不再留隐藏close。当前该缺陷**支持Resolved**。研发双视口新增稳定ID用例和完整10键盘 **10通过5.4秒**；Google Chrome仅追加受影响Sessions四路径 **4通过2.9秒**，无需重复未变表头和其他已过路径。

独立脚本与前后结果见`stage-review/r90-independent/`。这是原生产JS/真实DOM+fixture HTTP，未代修代码或创建另一套验收壳。

## 3. 失败证据分流

- **真实产品红灯**：表头计算样式缺失；Jev/编辑行/抽屉焦点去向缺失；本次独立Sessions刷新后焦点留隐藏节点。
- **测试oracle/选择器问题**：701px额外中心包含断言并非冻结要求；词表行`locator('button')`同时命中Listen和Delete产生strict mode错误；新增刷新回归第一版以多行innerText做hasText不稳定，后改稳定callId。
- `refresh-red.txt`因定位本身失败，不能单独作产品红灯；本次独立before JSON明确记录hidden close焦点才是确认复现。修后after JSON及最终稳定ID测试证明闭环。所有旧错误留存，不写成产品“曾坏又修”的同类计数。

## 4. 专项计划边界

`vendor-specialist-test-plan.md`明确尚未执行/授权，缺专用素材hash/时间真值/逐模型支持核对及当日费用预算；按ASR否定/续说重连/多语/WPM、LLM工具、TTS取消分批。不复用旧授权，首错误/范围缺口即停，不因目标修订未触发就循环重跑。预算不等于厂商硬封顶，没有借Gate1授权费用；不存在已测试效果的假结论。

`device-performance-test-plan.md`将手机/Safari、VoiceOver、UDP弱网、物理双讲AEC、Python3.11、1核1GB和原链/候选配对增量延迟各自列方法/实际缺项。桌面Chromium与Google Chrome同属Chromium体系，不能当跨引擎、iOS、读屏或声学证明；DOM可访问名称/键盘证据也不等于完整可访问性验收。计划明确无服务端AEC、新架构/默认采用或部署许可。

两个计划是可继续拆分执行的专项准备，**不是已经冻结可直接收费的授权清单**。本次只审核范围与真实性，不验证未来厂商协议/费率或实机效果。

## 5. 独立范围与交接

独立有限复现确认并复核上述刷新缺陷；研发本轮表头6、Chromium最终键盘10、Google Chrome原14+受影响4、Vite build证据已只读检查。结构门禁在评审时0 errors/40 warnings，不能替代全功能/视觉/可访问性结论。复查源码仅本轮CSS及焦点实现发生目标差异，没有要求无变化后端重复全量。

当前可将限定UI修复与计划交给后续完整独立审核，保留全部设备/真实效果/性能与默认采用边界。没有新增产品决定，本次不授权任何费用。最终r90源包尚待冻结，若需要包核验另做只读hash确认，不拿r89包hash代表新焦点代码。

## 限定收口

研发最终R90-SESSIONS-REFRESH-FOCUS已Resolved并披露，最终门禁0 errors/39 warnings，Google Chrome受影响Sessions4路径2.9秒及当前Vite构建通过日志已只读核对。原独立复现从frontend工作目录运行，依赖当时本机Vite5192及显式fixture，不含外部调用。后续r90增量包应以r89冻结包为基线并逐hash核验，不重写旧tar。
