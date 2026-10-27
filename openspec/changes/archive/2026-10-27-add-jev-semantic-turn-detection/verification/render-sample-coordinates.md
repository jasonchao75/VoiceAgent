# Worklet渲染采样坐标（r37，非硬件时间）

本项沿用正式WebSocket任务播放器、认证回执和历史，不改音频传输、不新增服务端AEC。它补齐可追溯的原始时间证据，不直接生成端到端延迟。

## 坐标定义

- render_frame：AudioWorklet全局currentFrame加当前quantum内偏移。task_started为首个实际写入输出buffer的采样位置；task_finished为最后写入采样之后的排他边界，即使task_end标记晚到也不改成标记接收时刻；task_stopped为确认已无该任务输出的quantum边界。
- render_sample_rate：同一Worklet的实际sampleRate。累计rendered_samples仍独立保留；首尾间可能有流式饥饿间隙，不把二者差值强行当累计发声时长。
- render_clock_id：正式TaskMediaManager为每个Worklet端口分配一次随机作用域，端口重建即变化。不同作用域不比较；这不是跨会话用户标识。

没有实际Worklet时钟时不伪造0坐标。渲染帧坐标不等于performance.now、服务端单调时钟、RTP时间或扬声器硬件呈现时间。停止的渲染边界不能撤回设备中已经排队的声音。

## 接口与保留

认证playback-events继续验证会话token和已准备的任务身份。三个坐标字段要么全部省略（旧客户端兼容），要么一起提供；帧坐标及采样率有整数/范围校验、作用域有格式校验。同一任务不能混用时钟作用域/采样率；同一事件的重复回执不能篡改坐标。client_elapsed_ms仍是客户端主线程发回执时刻，明确不当作渲染时刻。

CallCapture将原始坐标写入该任务原turn/response的TD事件，沿用历史JSON持久化。正式历史明细显示中英字段和值；旧记录缺字段保持缺失。不写browser_playback_ms，不把这些原始坐标直接升级为跨时钟毫秒指标或硬件播放确认。

## 实测

- Node先红后绿：同一quantum两个任务从1024/1026开始，最后边界1026/1029；晚到end不改变最后采样坐标，停止边界1408。
- 真实AudioWorklet浏览器：同作用域、24kHz，2400个采样首尾差2400；桌面/窄屏均通过。
- 认证API保留坐标并拒绝篡改/残缺字段，旧回执兼容；HistoryStore重启后字段保留，数字时延仍未伪造。
- 正式历史1440/390px中英/字面值/无横向溢出回归通过。证据在development-20261022-r37/。

后续仍需验证AudioContext输出时间映射、跨服务端/客户端时钟边界与误差，以及真实设备/RTC任务身份。当前不宣称精确端到端或物理停止指标通过。
