# Spec: Pipecat Minimal Pipeline

## Requirement: Pipeline Boot (系统必须具备的能力)

系统必须能启动一个最小 Pipecat pipeline，并完成一次音频输入到文本输出的流转。

### Scenario: Local audio smoke test (具体场景下应该发生什么)

WHEN 输入一段本地 wav 音频  
THEN pipeline 能正常启动  
AND ASR 阶段能产生 transcript  
AND 过程不出现同步阻塞 I/O

## Requirement: Frame Flow (系统必须具备的能力)

自定义 processor 在不消费 frame 时，必须继续向下游传递 frame。

### Scenario: Unhandled frame passthrough (具体场景下应该发生什么)

WHEN processor 收到不处理的 frame  
THEN 必须传递给下游 processor  
AND pipeline 不得卡死
