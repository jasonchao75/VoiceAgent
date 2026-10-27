# 当前研发实现与自测交付包 r89（2026-10-26）

**研发交包就绪，已交未参与实现的Codex复审。原r87六项返修和新增RTC来源覆盖缺陷已复审支持关闭；不是全Change独立PASS、Checkpoint C或User Gate2。** 当前软件结果/源码标识/实际证据以本目录及review-package为准，旧r87/r88包不覆盖。详细22项场景映射见../current-scenario-matrix.md，交付要求核对见completion-audit.md。

## 本轮关闭与证据

原r88六项：独立英文词边界与Soniox subword空格；跨范围Final全文词覆盖不丢否定；D080新Jev目标优先但不延长Tmax/重启Final窗；客户端3秒回执截止及服务端5秒stop确认保护；完整性四字段禁用；README当前入口。原红灯、修复、自测/真实故障和独立Resolved见../development-20261026-r88/README.md及../stage-review/repair-review-r88.md，不重跑无变化同类测试。

本轮明确缺陷：原观察器只包装reader启动时的track，锁定SDK晚赋/替换真实track会继续产音频却绕过decoded来源观察。late-track-red.txt两失败后，改在**同一原生Resampler.resample入口**观察实际decoded AV帧；SDK track由SDK自己管理，原codec/resampler/PCM/pts与严格SSRC/epoch/hash/覆盖/时钟条件不变。late-track-green.txt19通过；独立21通过见../stage-review/repair-review-r89.md。

严格同正式入口RTC_E2E=1：cold一次8.0秒、同进程第二通warm一次7.8秒，各两响应1:1/1:2均保留来源样本/同包摘要/双端认证锚/实际Worklet回执。源epoch互不相同（cold-warm-epoch-check.json），原Partial取消与Final新答、唯一用户提交均核对。不是关闭E2E断言的限域通过。重启后两个完整HTTP历史与原件逐值相等（restart-history-check.json）；正式Sessions页1440/390实际API故障恢复/过滤/数据原样/当前响应范围可见/浮层无横向溢出2通过2.1秒。

## 最终当前版本验证
| 检查 | 实际结果 | 证据 |
|---|---|---|
| 全后端（包括原6返修、SDK晚到/替换） | 756 passed、5依赖弃用警告、40.55秒 | backend-full.txt / backend-junit.xml |
| 全客户端单元 | 25 passed、0 fail、2.118秒 | client-full.txt |
| 质量/类型/构建 | Ruff src/tests通过、实际Python3.13 mypy79源通过、Vite构建通过 | ruff-full.txt / mypy-full.txt / build.txt |
| 严格RTC冷/暖 | 各1通过；同正式公开入口/RTP/原音轨、推理替身 | strict-cold.txt / strict-warm.txt及对应JSON |
| 应用重启/真实历史页 | 两历史逐值相同，1440/390两通过 | restart-history-check.json / history-real-api.txt |
| 原型 | v0.14 SHA不变，657d49b9abf71c872eeaf7f6ccc0b3dfd96b1e4dc9bcd52bb92f43b0778902b4 | frozen-baseline-check.json |
| Change门禁 | 见gate-final.txt，仅结构门禁，不代替行为/独立验收 | gate-final.txt |

r88 UI完整性加载/切换/保存null/刷新1440/390、RTC回执响应丢失且错误遥测也挂起的真实故障组合沿用未变生产源码证据；source-delta-from-r88.json证明本轮只改原生来源reader及对应测试/fixture。当前所有src/frontend源码哈希见review-package/snapshot.json；共享工作区未提交，不代表包中全部上下文由本Change修改。

## 失败保留与归因边界
- r88严格E2E=0红灯完整保留；当时未存server native快照，不能唯一回溯其全部原因。当前关闭依据为明确两生命周期红灯→修复→严格冷暖实际复验，不声称历史只有一种根因。
- r89首个fixture诊断动态赋slots capture属性，导致observer退出。该计数0是**探针错误**，不是生产漏帧事实；diagnostic-probe-error.txt及旧source-join-diagnostic.json保留。改外部sidecar后离线slots检查通过，有效限定诊断观察/接受101帧且可冻源锚（source-join-diagnostic-fixed.json），仅作为定位材料，不用偶然诊断绿替代修复。首次格式失败也保留，最终Ruff通过。共两次诊断（首无效）及修复后冷/暖两次确认，无旧有限实验重放，无厂商调用。
- RTC故障用例阻断错误遥测时，UI实际错误关闭，后端仅保留started+ended_started/未知stop，顶层可仍completed/error_category为空；不谎称后端已取得确定客户端失败原因。独立r88认定非新增确认规范缺陷，完整送达/异常归因效果仍未验证。
- E2E约590–1334/804–1845ms（冷），544–1277/1272–1815ms（暖），误差边界宽；不是精确延迟/低延迟达标/P95/物理ADC或声学出声。

## 明确未验证及审批边界
D045当前Mac无麦克风：物理耳机/外放双讲/AEC/声学首播待设备；手机/Safari/弱网、跨连接可靠时钟、1核1GB/Python3.11、新增链路精确延迟/容量未测。四家六模型英文数字ASR、Jev两文本及TTS one有逐批授权external-real历史基本结果；本轮未收费，不能扩为新源码完整多语种/WPM/真实修订重连、LLM工具/TTS取消/语义质量通过。所有旧批次已消费，无新费用授权。默认RTC保持原链，开发候选采用/部署需用户后续决定，不加控件、不加服务端AEC。

## 复现、材料与回退
Python3.13锁定requirements.lock及前端package-lock。仓库根执行 `.venv/bin/python -m pytest -q`、`node --test frontend/tests/unit/*.test.js`、`.venv/bin/ruff check src tests`、`.venv/bin/mypy --python-version 3.13 src`；frontend内`npm run build`。SDK明确红绿见tests/test_td_rtp_input.py两个late/replaced测试；原独立3条复现已在正式tests/test_td_review_regressions.py。
正式本机RTC：tests/ui/td_local_app.py ordinary、LOCAL_RTP_CANDIDATE=1、独立/tmp数据目录、Vite只代理loopback；td-rtc-entry.spec.js开LOCAL_RUNTIME、RENDER_CLOCK_PROBE、RTC_E2E，首通可再开ASSERT_RTP_INPUT/ASSERT_RTC_CAPTURE。故障模式RTC_RECEIPT_HANG仅r88已执行；诊断SOURCE_DIAGNOSTIC在隔离fixture下最多16快照/单测试15秒，仅记录元数据，不改变生产判定。各实际命令/版本在completion-audit与日志，不使用真实Key。

本机临时资料/tmp/voiceagent-r89-*，包括diagnostic、diagnostic-fixed、confirm的本地录音/SQLite；只安全JSON/截图/文本/JUnit进包。frontend/dist已忽略；.env忽略且未打印Key。自身测试服务交包前停止；不删除用户数据。没有提交/推送/部署、主规格合并/归档或基线修改。回退保持development_rtp_candidate=False；不能移除回执保护或放宽来源判断来换通过。

复现前置：解包目录不含venv/node_modules；Python使用按requirements.lock安装的环境，frontend内先运行 `npm ci --ignore-scripts --no-audit --no-fund` 安装package-lock既有依赖，再从仓库根跑Node单元/构建。离线缓存可能不全，离线安装失败不能当源码失败；准备日志完整保留。

## 独立目录复现闭包
组装版独立目录实际126核心后端/25客户端及完整Vite构建通过，import路径均指解包源；不是借原工作区源码假复现。初始漏demo.html/login.html导致构建失败已保留并补清单；已核补入文件及全部运行/测试输入与最终源SHA一致，最终包必须包含这些入口。node_modules不入包，先按原lock安装；原缓存离线不全/权限失败未改用户缓存权限，使用/tmp任务缓存后成功，失败日志保留。见package-reproduction-check.json（含实测输入SHA）；这不是声称解包后重跑全756。初始assembly快照和最终冻结点分开。
