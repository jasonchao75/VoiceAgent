# r80 正式WS采集来源接入

输入来源封装沿用锁定SDK Worklet原始代码，以子类旁路记录currentFrame与初始静音裁剪后的实际样本范围；保留原PCM转换、分包、上行传输。复用protobuf audio.name携带版本来源，未知字段保持；无来源则原样发包，不生成指标。断开恢复原Blob地址，重连不复用已撤销地址。

实际证据：锁定SDK原/封装Worklet PCM逐字节一致、初始静音裁剪与原SDK protobuf解码一致检查通过。正式路由/假麦克风/本机隔离服务组合1 passed / 7.7秒，Final取消及实际播放回执原断言通过。捕获最多8个二进制包，Python官方protobuf解析得到7个audio包、28672样本，全部来源offset、span数量、采样率及声道与实际PCM吻合，见actual-input-identity.json。

当前仅上行身份闭环，不证明源帧对应服务端时刻；尚无源时钟nonce采样、源停声边界冻结或E2E区间，不能宣称E2E已实现。RTC上行未改变。默认RTC/配置页面/冻结HTML不变，没有外部调用。

构建通过。一次Node直接导入SDK dist/index.js错误（CJS命名导出），改为包公开入口后同一检查通过；一次状态登记误在frontend目录，未写入后立即按根目录补录。均不是正式产品失败。

临时数据：/tmp/voiceagent-r80-input保留本地DB、惰性加密测试Key和假音频包（非客户数据）；原包可能含会话消息，不并入审核包。test-results/playwright忽略产物保留。当前阶段包r78不含r79/r80新增源码，最终包待收敛重建。
