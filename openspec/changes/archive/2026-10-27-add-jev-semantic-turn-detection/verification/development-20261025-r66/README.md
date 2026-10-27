# D-070分界定位：已执行、失败即停止

local-real；同正式入口，1连接、固定本地0.1秒开场，原生下行含静音硬限制2秒，无转写推断/Final/编号/厂商调用/费用。首次packet_deadline立即释放，服务8793与Vite5178已停。诊断脚本1passed仅代表捕获预定失败，不是RTC成功。

## 已确认分界
first-mapping-failure.json：native send完成51；浏览器关闭前收到audio/opus 48包、2620字节、packetsLost=0；audio sink paused=false/muted=true/readyState=4/hasStream=true。worker configured，mapping51、packets0、decoded0。排除“服务端只发元数据未完成发送”“浏览器没有收到任何音频”“sink未启动”作为本次唯一解释。问题位于浏览器编码transform入口；不证明解码/任务范围校验失败。

## 静态发现与离线修复
正式实现原先等track事件才装receiver.transform，测试更早注册的track监听器已先创建MediaStreamSource/原生分析器。安装点不能保证先于原生消费，测试也有不必要的抢先消费干扰。已将正式安装点提前到锁定SDK addInitialTransceivers完成后、SDP协商前；只改变接入时序，不改变RTP/上行/解码/任务范围容差/默认选择。新增时序测试先因缺少bindRTCTransform失败，修复后2项JS通过，生产构建通过。

该离线修复还没有真实浏览器确认，不能称上述时序就是此次失败唯一根因。下一确认必须去掉测试原生分析器，只留收包/渲染回执观测；同0.1秒开场1连接/原生源≤2秒，首失败停、不重试、不跑组合。D-070已用完，不自动执行。

## 未验证与产物
正式任务开播/结束、Final/编号组合、对照延迟和手机兼容仍未证明。首次失败/分界白名单见本目录；测试DB/加密主密钥/录音在/tmp/voiceagent-d070-formal，原始日志/tmp/voiceagent-d070-server.log含临时能力URL与本机地址，不复制审核包、不提交；前端构建frontend/dist忽略。未自签独立PASS/C/Gate2。
