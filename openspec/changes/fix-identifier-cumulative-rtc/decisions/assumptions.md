# Engineering assumptions
- 复用已存在RTP任务播放器，无新增依赖或数据通道音频；仅自建TD编号开启的正式会话采用该链路。旧WebSocket和普通native行为不改。回退本次提交恢复原接线。
