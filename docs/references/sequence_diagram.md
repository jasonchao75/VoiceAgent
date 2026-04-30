### 1. 现状：串行阻塞架构 (Current Sequential Pipeline)
目前系统完全依赖绝对断句，导致 LLM 思考时间产生显著的端到端延迟（Awkward pauses）。

```mermaid
sequenceDiagram
    participant U as User
    participant V as Voice Agent Core
    participant STT as Speechmatics (ASR)
    participant LLM as Cloud LLM
    participant TTS as TTS Engine

    Note over U, TTS: 现状: 串行阻塞架构 (Current Sequential Pipeline)

    U->>V: Voice Input (Continuous stream)
    V->>STT: Audio Stream (WebSocket)
    
    Note right of STT: User is speaking...
    STT-->>V: [Partial] results (Ignored by LLM)
    
    Note right of STT: User stops speaking
    Note over STT, V: ⏳ Waiting for Silence Trigger (EndOfUtterance)
    STT-->>V: [Final] "I want to book a ticket." 
    
    Note over V, LLM: 🚨 Absolute Endpoint reached
    V->>LLM: Send Full Prompt
    activate LLM
    Note over LLM: ⏳ Heavy LLM Thinking Delay (Sequential)
    LLM-->>V: Streaming Output: "Sure,"
    V->>TTS: "Sure,"
    activate TTS
    TTS-->>U: Play Audio: "Sure,"
    LLM-->>V: Streaming Output: "where to?"
    deactivate LLM
    V->>TTS: "where to?"
    TTS-->>U: Play Audio: "where to?"
    deactivate TTS
```

### 2. 期望：利用 Partial 实现提前思考与智能断句 (Proposed Optimized Pipeline)
打破串行等待，让 LLM 的思考时间（Thinking Ahead）与 ASR 识别重叠，并结合多信号实现更敏捷的断句（Smart Turn Detection）。

```mermaid
sequenceDiagram
    participant U as User
    participant V as Voice Agent Core
    participant STT as Speechmatics (ASR)
    participant LLM as Cloud LLM
    participant TTS as TTS Engine

    Note over U, TTS: 期望: 并发优化架构 (Proposed Optimized Pipeline)

    U->>V: Voice Input (Continuous stream)
    V->>STT: Audio Stream (WebSocket)
    
    Note right of STT: User starts speaking
    STT-->>V: [Partial] "I want to..."
    V->>LLM: Stream [Partial] for Pre-thinking / Context building (Background)
    
    Note right of STT: User continues
    STT-->>V: [Partial] "I want to book a ticket"
    V->>LLM: Stream updated [Partial] context
    
    Note over V, LLM: 🧠 Smart Turn Detection (Multi-signal)
    V->>V: 1. Check VAD Silence? (False)
    V->>V: 2. Check Punctuation? (None)
    V->>LLM: 3. Is Semantic Complete?
    LLM-->>V: True
    
    Note right of STT: User paused / finished
    STT-->>V: [Final] "I want to book a ticket." + EndOfUtterance
    
    Note over V, LLM: ⚡ Agent takes the turn instantly!
    V->>LLM: Final Confirm
    activate LLM
    LLM-->>V: Streaming Output: "Sure,"
    V->>TTS: "Sure,"
    activate TTS
    TTS-->>U: Play Audio: "Sure,"
    LLM-->>V: Streaming Output: "where to?"
    V->>TTS: "where to?"
    TTS-->>U: Play Audio: "where to?"
    deactivate LLM
    deactivate TTS
```